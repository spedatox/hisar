"""Iacon Hall of Records: authoritative catalog, retained originals and outbox.

Public filesystem paths never address internal blobs. SQL catalog mutations and
their events commit together; staged upload receipts cover filesystem recovery.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from pydantic import ValidationError

from .config import get_settings
from .paths import check_name
from .library_models import (
    LibraryDocument, LibraryRevision, LibraryEvent, LibraryIndexReceipt,
    CreateDocumentRequest, CreateRevisionMetadata, DocumentResponse, CatalogRecord,
)

log = logging.getLogger(__name__)


def get_library_root(vault_root: Path) -> Path:
    root = vault_root.resolve()
    if (root / ".hisar").is_symlink() or (root / ".hisar" / "library").is_symlink():
        raise HTTPException(403, "Records storage cannot be a symbolic link")
    target = (root / ".hisar" / "library").resolve()
    if root not in target.parents:
        raise HTTPException(403, "Records storage escapes the vault")
    return target


def get_db_path(vault_root):
    return get_library_root(vault_root) / "catalog.sqlite3"


def get_blobs_dir(vault_root):
    return get_library_root(vault_root) / "blobs"


def get_staging_dir(vault_root):
    return get_library_root(vault_root) / "staging"


def _now():
    return datetime.now(timezone.utc).isoformat()


def get_connection(vault_root):
    conn = sqlite3.connect(get_db_path(vault_root), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def bootstrap_library(vault_root):
    root = get_library_root(vault_root)
    root.mkdir(parents=True, exist_ok=True)
    for directory in (get_blobs_dir(vault_root), get_staging_dir(vault_root)):
        directory.mkdir(exist_ok=True)
        if root not in directory.resolve().parents:
            raise HTTPException(403, "Records storage escapes the vault")
    with get_connection(vault_root) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, aliases TEXT NOT NULL,
                category TEXT, type TEXT, institution TEXT, subject TEXT,
                active_revision_id TEXT, access_policy TEXT NOT NULL,
                is_archived BOOLEAN NOT NULL DEFAULT 0, is_tombstone BOOLEAN NOT NULL DEFAULT 0,
                metadata_version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS revisions (
                id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
                sequence INTEGER NOT NULL, blob_sha256 TEXT NOT NULL, original_filename TEXT NOT NULL,
                mime_type TEXT NOT NULL, size_bytes INTEGER NOT NULL, issue_date TEXT, coverage_start TEXT,
                coverage_end TEXT, term TEXT, superseded_by TEXT, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL,
                event_type TEXT NOT NULL, document_id TEXT NOT NULL, revision_id TEXT,
                catalog_version INTEGER NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS index_receipts (
                document_id TEXT NOT NULL, revision_id TEXT NOT NULL, status TEXT NOT NULL,
                reported_at TEXT NOT NULL, PRIMARY KEY(document_id, revision_id)
            );
            CREATE TABLE IF NOT EXISTS uploads (
                id TEXT PRIMARY KEY, blob_sha256 TEXT, size_bytes INTEGER, state TEXT NOT NULL,
                revision_id TEXT, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS legacy_imports (
                source_path TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
                blob_sha256 TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS revisions_document_sequence ON revisions(document_id, sequence);
        """)
        # Crash remnants are retained for operator review; no blob is deleted here.
        conn.execute("UPDATE uploads SET state='interrupted' WHERE state IN ('staging','published')")
        conn.execute("UPDATE index_receipts SET status='pending' WHERE status NOT IN ('pending','processing','ready_keyword','needs_review','failed')")
        conn.commit()
        _enroll_legacy(vault_root, conn)


def _emit_event(cursor, event_type, document_id, catalog_version, revision_id=None):
    cursor.execute(
        "INSERT INTO events(event_id,event_type,document_id,revision_id,catalog_version,created_at) VALUES(?,?,?,?,?,?)",
        (str(uuid.uuid4()), event_type, document_id, revision_id, catalog_version, _now()),
    )


def _document(row):
    values = dict(row)
    values["aliases"] = json.loads(values["aliases"])
    values["access_policy"] = json.loads(values["access_policy"])
    return LibraryDocument(**values)


def get_document(conn, doc_id):
    row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    return _document(row) if row else None


def _require_document(conn, doc_id, *, include_withdrawn=False):
    doc = get_document(conn, doc_id)
    if doc is None or (doc.is_tombstone and not include_withdrawn):
        raise HTTPException(404, "Record not found")
    return doc


def _policy(value):
    if not isinstance(value, dict) or set(value) - {"allowed_agents"}:
        raise HTTPException(422, "Access policy must contain only allowed_agents")
    allowed = value.get("allowed_agents")
    if allowed is not None and (not isinstance(allowed, list) or len(allowed) > 100 or
                                any(not isinstance(a, str) or not a or len(a) > 64 for a in allowed)):
        raise HTTPException(422, "allowed_agents must be a bounded list of agent IDs")
    return value


def create_document(conn, title, type=None, category=None, aliases=None, institution=None,
                    subject=None, access_policy=None, *, commit=True):
    try:
        req = CreateDocumentRequest(title=title.strip(), type=type, category=category, aliases=aliases or [],
                                    institution=institution, subject=subject, access_policy=access_policy or {})
    except ValidationError as exc:
        raise HTTPException(422, "Record metadata is invalid") from exc
    doc_id, now = str(uuid.uuid4()), _now()
    conn.execute(
        "INSERT INTO documents(id,title,aliases,category,type,institution,subject,access_policy,created_at,updated_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        (doc_id, req.title, json.dumps(req.aliases), req.category, req.type, req.institution, req.subject,
         json.dumps(_policy(req.access_policy)), now, now),
    )
    _emit_event(conn, "document_created", doc_id, 1)
    if commit:
        conn.commit()
    return get_document(conn, doc_id)


def get_revision(conn, rev_id):
    row = conn.execute("SELECT * FROM revisions WHERE id=?", (rev_id,)).fetchone()
    return LibraryRevision(**dict(row)) if row else None


def get_revisions_for_document(conn, doc_id):
    _require_document(conn, doc_id)
    return [LibraryRevision(**dict(r)) for r in conn.execute(
        "SELECT * FROM revisions WHERE document_id=? ORDER BY sequence DESC", (doc_id,),
    )]


def get_index_receipt(conn, doc_id, rev_id):
    row = conn.execute("SELECT * FROM index_receipts WHERE document_id=? AND revision_id=?", (doc_id, rev_id)).fetchone()
    return LibraryIndexReceipt(**dict(row)) if row else None


def record_response(conn, doc_id, *, history=False, include_withdrawn=False):
    doc = _require_document(conn, doc_id, include_withdrawn=include_withdrawn)
    rev = get_revision(conn, doc.active_revision_id) if doc.active_revision_id else None
    receipt = get_index_receipt(conn, doc.id, rev.id) if rev else None
    state = "withdrawn" if doc.is_tombstone else "archived" if doc.is_archived else (
        receipt.status if receipt else "pending" if rev else "no_edition"
    )
    fields = dict(document=doc, active_revision=rev, index_status=state)
    if history:
        revisions = [LibraryRevision(**dict(r)) for r in conn.execute(
            "SELECT * FROM revisions WHERE document_id=? ORDER BY sequence DESC", (doc_id,),
        )]
        return CatalogRecord(**fields, revisions=revisions)
    return DocumentResponse(**fields)


def list_records(conn, *, include_archived=False, offset=0, limit=100):
    rows = conn.execute(
        "SELECT id FROM documents WHERE is_tombstone=0 AND (? OR is_archived=0) "
        "ORDER BY title COLLATE NOCASE,id LIMIT ? OFFSET ?", (include_archived, limit+1, offset),
    ).fetchall()
    return {"records": [record_response(conn, row["id"]) for row in rows[:limit]],
            "has_more": len(rows) > limit, "next_offset": offset+limit if len(rows) > limit else None}


def manifest(conn, *, offset=0, limit=100):
    rows = conn.execute("SELECT id FROM documents ORDER BY id LIMIT ? OFFSET ?", (limit+1, offset)).fetchall()
    return {"records": [record_response(conn, r["id"], history=True, include_withdrawn=True) for r in rows[:limit]],
            "has_more": len(rows) > limit, "next_offset": offset+limit}


def update_document(conn, doc_id, expected_version, updates):
    try:
        conn.execute("BEGIN IMMEDIATE")
        doc = _require_document(conn, doc_id)
        if doc.metadata_version != expected_version:
            raise HTTPException(409, "Record changed; refresh before saving")
        updates = dict(updates)
        for key in ("title", "aliases", "access_policy", "is_archived"):
            if key in updates and updates[key] is None:
                raise HTTPException(422, f"{key} cannot be null")
        if "title" in updates:
            updates["title"] = updates["title"].strip()
            if not updates["title"]:
                raise HTTPException(422, "Title is required")
        if "active_revision_id" in updates and updates["active_revision_id"]:
            revision = get_revision(conn, updates["active_revision_id"])
            if revision is None or revision.document_id != doc_id:
                raise HTTPException(422, "Edition belongs to another record")
        if "access_policy" in updates:
            _policy(updates["access_policy"])
        values, fields = [], []
        allowed = {"title", "category", "type", "institution", "subject", "aliases", "access_policy",
                   "active_revision_id", "is_archived"}
        for key, value in updates.items():
            if key not in allowed:
                raise HTTPException(422, "Unsupported metadata field")
            fields.append(f"{key}=?")
            values.append(json.dumps(value) if key in {"aliases", "access_policy"} else value)
        if fields:
            version = expected_version + 1
            fields.extend(["metadata_version=?", "updated_at=?"])
            values.extend([version, _now(), doc_id, expected_version])
            changed = conn.execute(f"UPDATE documents SET {','.join(fields)} WHERE id=? AND metadata_version=?", values)
            if changed.rowcount != 1:
                raise HTTPException(409, "Record changed")
            _emit_event(conn, "document_updated", doc_id, version)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return get_document(conn, doc_id)


def purge_document(conn, doc_id, expected_version):
    # Withdraw visibility while retaining all original bytes and revisions.
    try:
        conn.execute("BEGIN IMMEDIATE")
        doc = _require_document(conn, doc_id)
        changed = conn.execute(
            "UPDATE documents SET is_tombstone=1,metadata_version=metadata_version+1,updated_at=? "
            "WHERE id=? AND metadata_version=?", (_now(), doc_id, expected_version),
        )
        if changed.rowcount != 1:
            raise HTTPException(409, "Record changed; refresh before withdrawing")
        _emit_event(conn, "document_purged", doc_id, doc.metadata_version+1)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _metadata(**fields):
    try:
        return CreateRevisionMetadata(**fields).model_dump(mode="json")
    except ValidationError as exc:
        raise HTTPException(422, "Edition dates are invalid; supply a valid coverage interval") from exc


def _stage(vault_root, conn, upload):
    filename = check_name(upload.filename or "record.txt")
    extension = Path(filename).suffix.lower()
    types = {".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/markdown",
             ".csv": "text/csv", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
             ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    if extension not in types:
        raise HTTPException(415, "Supported originals: PDF, TXT, Markdown, CSV, PNG, JPEG, DOCX and XLSX")
    upload_id = str(uuid.uuid4())
    conn.execute("INSERT INTO uploads(id,state,created_at) VALUES(?,'staging',?)", (upload_id, _now()))
    conn.commit()
    staging = get_staging_dir(vault_root) / (upload_id + ".part")
    limit = get_settings().library_max_bytes
    hasher, size, prefix = hashlib.sha256(), 0, b""
    try:
        with staging.open("xb") as target:
            while chunk := upload.file.read(1024**2):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, "Original exceeds the Hall of Records upload limit")
                if len(prefix) < 16:
                    prefix += chunk[:16-len(prefix)]
                hasher.update(chunk)
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        if not size:
            raise HTTPException(422, "Original is empty")
        if extension == ".pdf" and not prefix.startswith(b"%PDF-"):
            raise HTTPException(415, "Original is not a PDF")
        if extension == ".png" and not prefix.startswith(b"\x89PNG\r\n\x1a\n"):
            raise HTTPException(415, "Original is not a PNG")
        if extension in {".jpg", ".jpeg"} and not prefix.startswith(b"\xff\xd8\xff"):
            raise HTTPException(415, "Original is not a JPEG")
        if extension in {".docx", ".xlsx"} and not prefix.startswith(b"PK\x03\x04"):
            raise HTTPException(415, "Original is not an Office document")
        if extension in {".txt", ".md", ".csv"}:
            try:
                content = staging.read_bytes().decode("utf-8-sig")
                if "\x00" in content:
                    raise ValueError("binary")
            except (UnicodeDecodeError, ValueError) as exc:
                raise HTTPException(415, "Text originals must be UTF-8, without binary content") from exc
        digest = hasher.hexdigest()
        destination = get_blobs_dir(vault_root) / digest
        if destination.exists():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                raise HTTPException(409, "Existing original failed integrity verification")
            staging.unlink()
        else:
            # Exclusive publication: never overwrite an immutable blob.
            try:
                os.link(staging, destination)
            except FileExistsError:
                if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                    raise HTTPException(409, "Original publication conflict")
            staging.unlink()
        if os.name != "nt":
            descriptor = os.open(get_blobs_dir(vault_root), os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        conn.execute("UPDATE uploads SET state='published',blob_sha256=?,size_bytes=? WHERE id=?", (digest, size, upload_id))
        conn.commit()
        return {"upload_id": upload_id, "blob_sha256": digest, "size_bytes": size,
                "original_filename": filename, "mime_type": types[extension]}
    except Exception:
        if staging.exists():
            staging.unlink()
        conn.execute("UPDATE uploads SET state='failed' WHERE id=?", (upload_id,))
        conn.commit()
        raise


def _publish(conn, doc_id, staged, metadata, expected_version):
    doc = _require_document(conn, doc_id)
    if doc.is_archived:
        raise HTTPException(409, "Restore the record before adding an edition")
    if doc.metadata_version != expected_version:
        raise HTTPException(409, "Record changed; refresh before uploading an edition")
    active = get_revision(conn, doc.active_revision_id) if doc.active_revision_id else None
    if active and active.blob_sha256 == staged["blob_sha256"] and all(
        getattr(active, key) == value for key, value in metadata.items()
    ):
        conn.execute("UPDATE uploads SET state='committed',revision_id=? WHERE id=?", (active.id, staged["upload_id"]))
        return active
    sequence = conn.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM revisions WHERE document_id=?", (doc_id,)).fetchone()[0]
    rev_id, now = str(uuid.uuid4()), _now()
    conn.execute(
        "INSERT INTO revisions(id,document_id,sequence,blob_sha256,original_filename,mime_type,size_bytes,"
        "issue_date,coverage_start,coverage_end,term,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (rev_id, doc_id, sequence, staged["blob_sha256"], staged["original_filename"], staged["mime_type"],
         staged["size_bytes"], metadata["issue_date"], metadata["coverage_start"],
         metadata["coverage_end"], metadata["term"], now),
    )
    if active:
        conn.execute("UPDATE revisions SET superseded_by=? WHERE id=?", (rev_id, active.id))
    changed = conn.execute(
        "UPDATE documents SET active_revision_id=?,metadata_version=metadata_version+1,updated_at=? "
        "WHERE id=? AND metadata_version=?", (rev_id, now, doc_id, expected_version),
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "Record changed")
    _emit_event(conn, "revision_added", doc_id, expected_version+1, rev_id)
    conn.execute("UPDATE uploads SET state='committed',revision_id=? WHERE id=?", (rev_id, staged["upload_id"]))
    return get_revision(conn, rev_id)


def save_revision_blob(vault_root, conn, doc_id, upload, *, expected_version, **metadata):
    metadata = _metadata(**metadata)
    _require_document(conn, doc_id)
    staged = _stage(vault_root, conn, upload)
    try:
        conn.execute("BEGIN IMMEDIATE")
        rev = _publish(conn, doc_id, staged, metadata, expected_version)
        conn.commit()
        return rev
    except Exception:
        conn.rollback()
        raise


def create_record(vault_root, conn, title, upload, *, category=None, doc_type=None, legacy_path=None, **metadata):
    metadata = _metadata(**metadata)
    try:
        req = CreateDocumentRequest(title=title.strip(), category=category, type=doc_type)
    except ValidationError as exc:
        raise HTTPException(422, "Record metadata is invalid") from exc
    staged = _stage(vault_root, conn, upload)
    try:
        conn.execute("BEGIN IMMEDIATE")
        doc = create_document(conn, **req.model_dump(), commit=False)
        _publish(conn, doc.id, staged, metadata, doc.metadata_version)
        if legacy_path:
            conn.execute("INSERT INTO legacy_imports(source_path,document_id,blob_sha256) VALUES(?,?,?)",
                         (legacy_path, doc.id, staged["blob_sha256"]))
        conn.commit()
        return record_response(conn, doc.id)
    except Exception:
        conn.rollback()
        raise


def set_index_receipt(conn, doc_id, rev_id, status):
    revision = get_revision(conn, rev_id)
    if revision is None or revision.document_id != doc_id:
        raise HTTPException(422, "Receipt edition does not belong to the record")
    if status not in {"pending", "processing", "ready_keyword", "needs_review", "failed"}:
        raise HTTPException(422, "Unknown indexing status")
    conn.execute(
        "INSERT INTO index_receipts(document_id,revision_id,status,reported_at) VALUES(?,?,?,?) "
        "ON CONFLICT(document_id,revision_id) DO UPDATE SET status=excluded.status,reported_at=excluded.reported_at",
        (doc_id, rev_id, status, _now()),
    )
    conn.commit()


def request_reindex(conn, doc_id):
    doc = _require_document(conn, doc_id)
    if doc.is_archived or not doc.active_revision_id:
        raise HTTPException(409, "Record has no active edition available for indexing")
    with conn:
        conn.execute("DELETE FROM index_receipts WHERE document_id=? AND revision_id=?", (doc_id, doc.active_revision_id))
        _emit_event(conn, "index_requested", doc_id, doc.metadata_version, doc.active_revision_id)
    return {"status": "pending"}


def original_response(vault_root, conn, rev_id, *, inline=False):
    revision = get_revision(conn, rev_id)
    if revision is None:
        raise HTTPException(404, "Edition not found")
    _require_document(conn, revision.document_id)
    path = get_blobs_dir(vault_root) / revision.blob_sha256
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != revision.blob_sha256:
        raise HTTPException(409, "Original is missing or failed integrity verification")
    return FileResponse(path, filename=revision.original_filename, media_type=revision.mime_type,
                        content_disposition_type="inline" if inline else "attachment")


def resolve_documents(conn, document_ids, agent_id):
    items = []
    for doc_id in document_ids:
        doc = get_document(conn, doc_id)
        allowed = bool(doc and not doc.is_tombstone)
        if allowed:
            policy = _policy(doc.access_policy)
            agents = policy.get("allowed_agents")
            allowed = agents is None or agent_id in agents
        items.append({"document_id": doc_id, "access_granted": allowed,
                      "active_revision_id": doc.active_revision_id if allowed else None,
                      "is_archived": doc.is_archived if allowed else False,
                      "record": record_response(conn, doc_id) if allowed else None})
    return {"items": items}


def get_events(conn, after_sequence=0, limit=100):
    rows = conn.execute("SELECT * FROM events WHERE sequence>? ORDER BY sequence LIMIT ?", (after_sequence, limit+1)).fetchall()
    return [LibraryEvent(**dict(r)) for r in rows[:limit]], len(rows) > limit


def _enroll_legacy(vault_root, conn):
    folder = vault_root / "Documents" / "Library"
    if not folder.is_dir():
        return
    from types import SimpleNamespace
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.is_symlink() or vault_root.resolve() not in path.resolve().parents:
            continue
        relative = path.relative_to(folder).as_posix()
        if conn.execute("SELECT 1 FROM legacy_imports WHERE source_path=?", (relative,)).fetchone():
            continue
        try:
            with path.open("rb") as original:
                upload = SimpleNamespace(filename=path.name, file=original)
                category = path.parent.relative_to(folder).as_posix()
                create_record(vault_root, conn, path.stem, upload, legacy_path=relative,
                              category=None if category == "." else category)
        except Exception:
            conn.rollback()
            log.warning("Legacy record enrollment requires review: %s", relative, exc_info=True)
