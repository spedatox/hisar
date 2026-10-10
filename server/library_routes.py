from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Response
from fastapi.responses import FileResponse
from typing import List, Optional
from pathlib import Path

from . import library
from .config import get_settings
from .auth import Principal, require_owner, require_library_reader, require_library_sync
from .library_models import (
    CreateDocumentRequest, UpdateDocumentRequest, DocumentResponse,
    ResolveRequest, ResolveResponse, ResolveResponseItem, ManifestResponse,
    LibraryEvent
)

router = APIRouter(prefix="/library", tags=["library"])

def get_db():
    settings = get_settings()
    conn = library.get_connection(settings.sandbox_root)
    try:
        yield conn
    finally:
        conn.close()

# --- Owner CRUD ---

@router.get("/documents", response_model=List[DocumentResponse])
def get_documents(include_archived: bool = False, conn = Depends(get_db), principal: Principal = Depends(require_library_reader)):
    docs = library.list_documents(conn, include_archived=include_archived)
    resp = []
    for doc in docs:
        active_rev = None
        if doc.active_revision_id:
            active_rev = library.get_revision(conn, doc.active_revision_id)
        
        index_status = None
        if doc.active_revision_id:
            receipt = library.get_index_receipt(conn, doc.id, doc.active_revision_id)
            if receipt:
                index_status = receipt.status
                
        resp.append(DocumentResponse(
            document=doc,
            active_revision=active_rev,
            index_status=index_status
        ))
    return resp

@router.post("/documents", response_model=DocumentResponse)
def create_document(req: CreateDocumentRequest, conn = Depends(get_db), principal: Principal = Depends(require_owner)):
    doc = library.create_document(
        conn, title=req.title, doc_type=req.type, category=req.category,
        aliases=req.aliases, institution=req.institution, subject=req.subject,
        access_policy=req.access_policy
    )
    return DocumentResponse(document=doc)

@router.patch("/documents/{doc_id}", response_model=DocumentResponse)
def update_document(doc_id: str, req: UpdateDocumentRequest, conn = Depends(get_db), principal: Principal = Depends(require_owner)):
    updates = req.dict(exclude_unset=True)
    updates.pop('expected_version', None)
    
    doc = library.update_document(conn, doc_id, req.expected_version, updates)
    active_rev = None
    if doc.active_revision_id:
        active_rev = library.get_revision(conn, doc.active_revision_id)
    return DocumentResponse(document=doc, active_revision=active_rev)

@router.delete("/documents/{doc_id}")
def purge_document(doc_id: str, conn = Depends(get_db), principal: Principal = Depends(require_owner)):
    library.purge_document(conn, doc_id)
    return {"ok": True}

# --- Revisions & Uploads ---

@router.post("/documents/{doc_id}/revisions")
def upload_revision(
    doc_id: str, 
    file: UploadFile = File(...),
    issue_date: Optional[str] = Form(None),
    coverage_start: Optional[str] = Form(None),
    coverage_end: Optional[str] = Form(None),
    term: Optional[str] = Form(None),
    conn = Depends(get_db), 
    principal: Principal = Depends(require_owner)
):
    settings = get_settings()
    rev = library.save_revision_blob(
        settings.sandbox_root, conn, doc_id, file, 
        original_filename=file.filename,
        mime_type=file.content_type,
        issue_date=issue_date,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        term=term
    )
    return rev

@router.get("/documents/{doc_id}/revisions")
def list_revisions(doc_id: str, conn = Depends(get_db), principal: Principal = Depends(require_library_reader)):
    return library.get_revisions_for_document(conn, doc_id)

@router.get("/revisions/{rev_id}/download")
def download_revision(rev_id: str, conn = Depends(get_db), principal: Principal = Depends(require_library_reader)):
    rev = library.get_revision(conn, rev_id)
    if not rev:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Revision not found")
        
    doc = library.get_document(conn, rev.document_id)
    if not doc or doc.is_tombstone:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document purged")
        
    # Check access policy here if it's an agent reader. 
    # For now, simple reader token allows read. Advanced policy check can be added.
    
    settings = get_settings()
    blob_path = library.get_blobs_dir(settings.sandbox_root) / rev.blob_sha256
    
    if not blob_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Blob missing")
        
    return FileResponse(
        path=blob_path,
        filename=rev.original_filename,
        media_type=rev.mime_type
    )

# --- Igor Sync & Resolve ---

@router.post("/resolve", response_model=ResolveResponse)
def resolve_documents(req: ResolveRequest, conn = Depends(get_db), principal: Principal = Depends(require_library_reader)):
    items = []
    for doc_id in req.document_ids:
        doc = library.get_document(conn, doc_id)
        if not doc or doc.is_tombstone:
            continue
            
        access_granted = True
        if not principal.is_owner:
            policy = doc.access_policy
            if policy and req.agent_id:
                allowed_agents = policy.get('allowed_agents')
                if allowed_agents is not None and req.agent_id not in allowed_agents:
                    access_granted = False

        items.append(ResolveResponseItem(
            document_id=doc.id,
            active_revision_id=doc.active_revision_id,
            access_granted=access_granted,
            is_archived=doc.is_archived
        ))
    return ResolveResponse(items=items)

@router.get("/events", response_model=ManifestResponse)
def get_events(after: int = 0, conn = Depends(get_db), principal: Principal = Depends(require_library_sync)):
    events, has_more = library.get_events(conn, after_sequence=after)
    next_cursor = after
    if events:
        next_cursor = events[-1].sequence
    return ManifestResponse(events=events, has_more=has_more, next_cursor=next_cursor)

@router.post("/index-receipts")
def report_index_receipt(
    document_id: str = Form(...),
    revision_id: str = Form(...),
    sync_status: str = Form(...),
    conn = Depends(get_db), 
    principal: Principal = Depends(require_library_sync)
):
    library.set_index_receipt(conn, document_id, revision_id, sync_status)
    return {"ok": True}

@router.get("/documents/{doc_id}/index-status")
def get_index_status(doc_id: str, conn = Depends(get_db), principal: Principal = Depends(require_owner)):
    doc = library.get_document(conn, doc_id)
    if not doc or not doc.active_revision_id:
        return {"status": "none"}
        
    receipt = library.get_index_receipt(conn, doc_id, doc.active_revision_id)
    if not receipt:
        return {"status": "processing"}
        
    return {
        "status": receipt.status,
        "reported_at": receipt.reported_at
    }
