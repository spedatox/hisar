"""Thin, authenticated owner and ingestion doors to the Hall of Records."""
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Request, UploadFile, HTTPException

from . import library
from .auth import Principal, require_owner, require_library_reader, require_library_sync
from .config import get_settings
from .library_models import CreateDocumentRequest, UpdateDocumentRequest, ResolveRequest

router = APIRouter(prefix="/library", tags=["library"])


def get_db():
    conn = library.get_connection(get_settings().sandbox_root)
    try:
        yield conn
    finally:
        conn.close()


@router.get("/documents")
def documents(include_archived: bool = False, offset: int = Query(0, ge=0),
              limit: int = Query(100, ge=1, le=100), conn=Depends(get_db), principal=Depends(require_owner)):
    return library.list_records(conn, include_archived=include_archived, offset=offset, limit=limit)


@router.post("/documents")
def create_document(req: CreateDocumentRequest, request: Request, tasks: BackgroundTasks, conn=Depends(get_db), principal=Depends(require_owner)):
    tasks.add_task(request.app.state.library_delivery.notify)
    return library.record_response(conn, library.create_document(conn, **req.model_dump()).id)


@router.post("/records")
def upload_record(request: Request, tasks: BackgroundTasks, title: str = Form(...), file: UploadFile = File(...),
                  category: str | None = Form(None), doc_type: str | None = Form(None),
                  issue_date: str | None = Form(None), coverage_start: str | None = Form(None),
                  coverage_end: str | None = Form(None), term: str | None = Form(None),
                  conn=Depends(get_db), principal=Depends(require_owner)):
    tasks.add_task(request.app.state.library_delivery.notify)
    return library.create_record(get_settings().sandbox_root, conn, title, file, category=category, doc_type=doc_type,
                                 issue_date=issue_date, coverage_start=coverage_start, coverage_end=coverage_end, term=term)


@router.patch("/documents/{doc_id}")
def update_document(doc_id: str, req: UpdateDocumentRequest, request: Request, tasks: BackgroundTasks, conn=Depends(get_db), principal=Depends(require_owner)):
    library.update_document(conn, doc_id, req.expected_version, req.model_dump(exclude_unset=True, exclude={"expected_version"}))
    tasks.add_task(request.app.state.library_delivery.notify)
    return library.record_response(conn, doc_id)


@router.delete("/documents/{doc_id}")
def withdraw(doc_id: str, request: Request, tasks: BackgroundTasks, expected_version: int = Query(..., ge=1),
             conn=Depends(get_db), principal=Depends(require_owner)):
    library.purge_document(conn, doc_id, expected_version)
    tasks.add_task(request.app.state.library_delivery.notify)
    return {"ok": True, "originals_retained": True}


@router.post("/documents/{doc_id}/revisions")
def upload_revision(doc_id: str, request: Request, tasks: BackgroundTasks, file: UploadFile = File(...), expected_version: int = Form(...),
                    issue_date: str | None = Form(None), coverage_start: str | None = Form(None),
                    coverage_end: str | None = Form(None), term: str | None = Form(None),
                    conn=Depends(get_db), principal=Depends(require_owner)):
    tasks.add_task(request.app.state.library_delivery.notify)
    return library.save_revision_blob(get_settings().sandbox_root, conn, doc_id, file,
                                      expected_version=expected_version, issue_date=issue_date,
                                      coverage_start=coverage_start, coverage_end=coverage_end, term=term)


@router.get("/documents/{doc_id}/revisions")
def revisions(doc_id: str, conn=Depends(get_db), principal=Depends(require_owner)):
    return library.get_revisions_for_document(conn, doc_id)


@router.get("/revisions/{rev_id}/download")
def original(rev_id: str, inline: bool = False, conn=Depends(get_db), principal=Depends(require_owner)):
    return library.original_response(get_settings().sandbox_root, conn, rev_id, inline=inline)


@router.post("/documents/{doc_id}/retry")
def retry(doc_id: str, request: Request, tasks: BackgroundTasks, conn=Depends(get_db), principal=Depends(require_owner)):
    tasks.add_task(request.app.state.library_delivery.notify)
    return library.request_reindex(conn, doc_id)


@router.get("/documents/{doc_id}/index-status")
def index_status(doc_id: str, conn=Depends(get_db), principal=Depends(require_owner)):
    return library.record_response(conn, doc_id)


@router.get("/manifest")
def manifest(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100),
             conn=Depends(get_db), principal=Depends(require_library_sync)):
    return library.manifest(conn, offset=offset, limit=limit)


@router.get("/catalog/{doc_id}")
def catalog_record(doc_id: str, conn=Depends(get_db), principal=Depends(require_library_sync)):
    return library.record_response(conn, doc_id, history=True, include_withdrawn=True)


@router.get("/originals/{rev_id}")
def ingestion_original(rev_id: str, conn=Depends(get_db), principal=Depends(require_library_sync)):
    return library.original_response(get_settings().sandbox_root, conn, rev_id)


@router.post("/resolve")
def resolve(req: ResolveRequest, conn=Depends(get_db), principal=Depends(require_library_reader)):
    return library.resolve_documents(conn, req.document_ids, req.agent_id)


@router.get("/events")
def events(after: int = Query(0, ge=0), conn=Depends(get_db), principal=Depends(require_library_sync)):
    records, has_more = library.get_events(conn, after)
    return {"events": records, "has_more": has_more, "next_cursor": records[-1].sequence if records else after}


@router.post("/index-receipts")
def receipt(document_id: str = Form(...), revision_id: str = Form(...), sync_status: str = Form(...),
            conn=Depends(get_db), principal=Depends(require_library_sync)):
    library.set_index_receipt(conn, document_id, revision_id, sync_status)
    return {"ok": True}


@router.post("/reconcile")
async def refresh(request: Request, principal=Depends(require_owner)):
    try:
        return await request.app.state.library_delivery.reconcile(full=True)
    except Exception as exc:
        raise HTTPException(503, "Igor synchronization is unavailable; originals are safely stored") from exc
