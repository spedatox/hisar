"""Thin, authenticated owner and ingestion doors to the Hall of Records."""
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Path, Query, Request, UploadFile, HTTPException
from pydantic import BaseModel, Field, StringConstraints

from . import library
from .auth import Principal, require_owner, require_library_reader, require_library_sync
from .config import get_settings
from .library_models import CreateDocumentRequest, UpdateDocumentRequest, ResolveRequest, LibrarySettingsUpdate, LibraryProgressRequest

router = APIRouter(prefix="/library", tags=["library"])
IncidentId = Annotated[str, Path(pattern=r"^[a-f0-9]{32}$")]
IncidentSeverity = Literal["critical", "error", "warning", "test"]


class IncidentSelection(BaseModel):
    ids: list[Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{32}$")]] | None = Field(
        default=None, min_length=1, max_length=1000)
    reviewed: bool = False
    severity: IncidentSeverity | None = None
    q: str = Field("", max_length=120)


class IncidentBulkReview(IncidentSelection):
    mark_reviewed: bool


@router.get("/incidents")
async def incident_list(request: Request, reviewed: bool = False,
                        severity: IncidentSeverity | None = None,
                        q: str = Query("", max_length=120), offset: int = Query(0, ge=0),
                        principal=Depends(require_owner)):
    params = {"reviewed": reviewed, "q": q, "offset": offset}
    if severity:
        params["severity"] = severity
    return await request.app.state.library_delivery.incident("GET", params=params)


@router.post("/incidents/export")
async def export_incidents(body: IncidentSelection, request: Request, principal=Depends(require_owner)):
    return await request.app.state.library_delivery.incident("POST", "/export",
        payload=body.model_dump(exclude_none=True), pdf=True)


@router.post("/incidents/selection")
async def incident_selection(body: IncidentSelection, request: Request, principal=Depends(require_owner)):
    return await request.app.state.library_delivery.incident("POST", "/selection",
        payload=body.model_dump(exclude_none=True))


@router.put("/incidents/review")
async def bulk_incident_review(body: IncidentBulkReview, request: Request, principal=Depends(require_owner)):
    return await request.app.state.library_delivery.incident("PUT", "/review",
        payload=body.model_dump(exclude_none=True))


@router.get("/incidents/{identity}")
async def incident_detail(identity: IncidentId, request: Request, principal=Depends(require_owner)):
    return await request.app.state.library_delivery.incident("GET", f"/{identity}")


@router.put("/incidents/{identity}/review")
async def incident_review(identity: IncidentId, request: Request, principal=Depends(require_owner)):
    return await request.app.state.library_delivery.incident("PUT", f"/{identity}/review")


@router.post("/incidents/{identity}/assessment")
async def incident_assessment(identity: IncidentId, request: Request, principal=Depends(require_owner)):
    return await request.app.state.library_delivery.incident("POST", f"/{identity}/assessment")


@router.get("/incidents/{identity}/pdf")
async def incident_pdf(identity: IncidentId, request: Request, principal=Depends(require_owner)):
    return await request.app.state.library_delivery.incident("GET", f"/{identity}/pdf", pdf=True)


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
async def retry(doc_id: str, request: Request, conn=Depends(get_db), principal=Depends(require_owner)):
    return await request.app.state.library_delivery.retry(conn, doc_id)


@router.get("/settings")
async def library_settings(request: Request, principal=Depends(require_owner)):
    return await request.app.state.library_delivery.control("GET", "/library/settings")


@router.put("/settings")
async def save_library_settings(values: LibrarySettingsUpdate, request: Request, principal=Depends(require_owner)):
    return await request.app.state.library_delivery.control("PUT", "/library/settings", values.transport_payload())


@router.post("/progress")
async def progress(values: LibraryProgressRequest, request: Request, principal=Depends(require_owner)):
    return await request.app.state.library_delivery.control("POST", "/library/progress", values.model_dump())


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
