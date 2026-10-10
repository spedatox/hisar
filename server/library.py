"""H.İ.S.A.R. Library Operations. (IACON)
Manages the owner-scoped catalog, immutable blobs, and event feed.
"""

import os
import sqlite3
import json
import uuid
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, BinaryIO

from fastapi import HTTPException, status
from pydantic import ValidationError

from .config import get_settings
from .library_models import (
    LibraryDocument, LibraryRevision, LibraryEvent, LibraryIndexReceipt
)

LIBRARY_DIR_NAME = "library"
CATALOG_FILE = "catalog.sqlite3"
BLOBS_DIR = "blobs"
STAGING_DIR = "staging"

def get_library_root(vault_root: Path) -> Path:
    return vault_root / ".hisar" / LIBRARY_DIR_NAME

def get_db_path(vault_root: Path) -> Path:
    return get_library_root(vault_root) / CATALOG_FILE

def get_blobs_dir(vault_root: Path) -> Path:
    return get_library_root(vault_root) / BLOBS_DIR

def get_staging_dir(vault_root: Path) -> Path:
    return get_library_root(vault_root) / STAGING_DIR

def bootstrap_library(vault_root: Path):
    """Create necessary directories and SQLite tables."""
    root = get_library_root(vault_root)
    root.mkdir(parents=True, exist_ok=True)
    get_blobs_dir(vault_root).mkdir(exist_ok=True)
    get_staging_dir(vault_root).mkdir(exist_ok=True)

    db_path = get_db_path(vault_root)
    with sqlite3.connect(db_path) as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                aliases TEXT NOT NULL, -- JSON
                category TEXT,
                type TEXT,
                institution TEXT,
                subject TEXT,
                active_revision_id TEXT,
                access_policy TEXT NOT NULL, -- JSON
                is_archived BOOLEAN NOT NULL DEFAULT 0,
                is_tombstone BOOLEAN NOT NULL DEFAULT 0,
                metadata_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS revisions (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                blob_sha256 TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                issue_date TEXT,
                coverage_start TEXT,
                coverage_end TEXT,
                term TEXT,
                superseded_by TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(document_id) REFERENCES documents(id)
            );

            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                event_type TEXT NOT NULL,
                document_id TEXT NOT NULL,
                revision_id TEXT,
                catalog_version INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS index_receipts (
                document_id TEXT NOT NULL,
                revision_id TEXT NOT NULL,
                status TEXT NOT NULL,
                reported_at TEXT NOT NULL,
                PRIMARY KEY (document_id, revision_id)
            );
        ''')
        conn.commit()

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _emit_event(cursor, event_type: str, document_id: str, catalog_version: int, revision_id: Optional[str] = None):
    event_id = str(uuid.uuid4())
    cursor.execute('''
        INSERT INTO events (event_id, event_type, document_id, revision_id, catalog_version, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (event_id, event_type, document_id, revision_id, catalog_version, _now()))

def get_connection(vault_root: Path):
    db_path = get_db_path(vault_root)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# --- Document Operations ---

def create_document(conn: sqlite3.Connection, title: str, doc_type: Optional[str] = None,
                    category: Optional[str] = None, aliases: List[str] = None,
                    institution: Optional[str] = None, subject: Optional[str] = None,
                    access_policy: Dict[str, Any] = None) -> LibraryDocument:
    doc_id = str(uuid.uuid4())
    now = _now()
    if aliases is None:
        aliases = []
    if access_policy is None:
        access_policy = {}
    
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO documents (
            id, title, aliases, category, type, institution, subject,
            access_policy, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        doc_id, title, json.dumps(aliases), category, doc_type, institution, subject,
        json.dumps(access_policy), now, now
    ))
    
    _emit_event(cursor, 'document_created', doc_id, 1)
    conn.commit()
    return get_document(conn, doc_id)

def get_document(conn: sqlite3.Connection, doc_id: str) -> Optional[LibraryDocument]:
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM documents WHERE id = ?', (doc_id,))
    row = cursor.fetchone()
    if not row:
        return None
    
    return LibraryDocument(
        id=row['id'],
        title=row['title'],
        aliases=json.loads(row['aliases']),
        category=row['category'],
        type=row['type'],
        institution=row['institution'],
        subject=row['subject'],
        active_revision_id=row['active_revision_id'],
        access_policy=json.loads(row['access_policy']),
        is_archived=bool(row['is_archived']),
        is_tombstone=bool(row['is_tombstone']),
        metadata_version=row['metadata_version'],
        created_at=datetime.fromisoformat(row['created_at']),
        updated_at=datetime.fromisoformat(row['updated_at'])
    )

def list_documents(conn: sqlite3.Connection, include_archived: bool = False) -> List[LibraryDocument]:
    cursor = conn.cursor()
    query = 'SELECT * FROM documents WHERE is_tombstone = 0'
    if not include_archived:
        query += ' AND is_archived = 0'
    query += ' ORDER BY title COLLATE NOCASE'
    
    cursor.execute(query)
    docs = []
    for row in cursor.fetchall():
        docs.append(LibraryDocument(
            id=row['id'],
            title=row['title'],
            aliases=json.loads(row['aliases']),
            category=row['category'],
            type=row['type'],
            institution=row['institution'],
            subject=row['subject'],
            active_revision_id=row['active_revision_id'],
            access_policy=json.loads(row['access_policy']),
            is_archived=bool(row['is_archived']),
            is_tombstone=bool(row['is_tombstone']),
            metadata_version=row['metadata_version'],
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at'])
        ))
    return docs

def update_document(conn: sqlite3.Connection, doc_id: str, expected_version: int,
                    updates: Dict[str, Any]) -> LibraryDocument:
    cursor = conn.cursor()
    cursor.execute('SELECT metadata_version FROM documents WHERE id = ?', (doc_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found")
    if row['metadata_version'] != expected_version:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Document version mismatch")
    
    new_version = expected_version + 1
    
    fields = []
    values = []
    for k, v in updates.items():
        if k in ['title', 'category', 'type', 'institution', 'subject', 'active_revision_id', 'is_archived']:
            fields.append(f"{k} = ?")
            values.append(v)
        elif k in ['aliases', 'access_policy']:
            fields.append(f"{k} = ?")
            values.append(json.dumps(v))
    
    if not fields:
        return get_document(conn, doc_id)
        
    fields.append("metadata_version = ?")
    values.append(new_version)
    fields.append("updated_at = ?")
    values.append(_now())
    
    values.append(doc_id)
    
    query = f"UPDATE documents SET {', '.join(fields)} WHERE id = ?"
    cursor.execute(query, tuple(values))
    
    event_type = 'document_archived' if updates.get('is_archived') else 'document_updated'
    _emit_event(cursor, event_type, doc_id, new_version)
    
    conn.commit()
    return get_document(conn, doc_id)

def purge_document(conn: sqlite3.Connection, doc_id: str):
    cursor = conn.cursor()
    cursor.execute('SELECT metadata_version FROM documents WHERE id = ?', (doc_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    new_version = row['metadata_version'] + 1
    cursor.execute('UPDATE documents SET is_tombstone = 1, metadata_version = ?, updated_at = ? WHERE id = ?',
                   (new_version, _now(), doc_id))
    _emit_event(cursor, 'document_purged', doc_id, new_version)
    conn.commit()

# --- Blob & Revision Operations ---

def save_revision_blob(vault_root: Path, conn: sqlite3.Connection, doc_id: str, 
                       upload, original_filename: str, mime_type: str, max_bytes: int = 25 * 1024 * 1024,
                       issue_date: str = None, coverage_start: str = None, 
                       coverage_end: str = None, term: str = None) -> LibraryRevision:
    """Stream an upload to staging, hash it, move to blobs, and create revision."""
    doc = get_document(conn, doc_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    staging_dir = get_staging_dir(vault_root)
    blobs_dir = get_blobs_dir(vault_root)
    
    tmp_path = staging_dir / f"{uuid.uuid4().hex}.part"
    hasher = hashlib.sha256()
    size_bytes = 0
    
    try:
        with open(tmp_path, "wb") as fh:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"Exceeds limit of {max_bytes} bytes")
                hasher.update(chunk)
                fh.write(chunk)
        
        sha256_hex = hasher.hexdigest()
        blob_path = blobs_dir / sha256_hex
        
        # Move blob atomically if not exists
        if not blob_path.exists():
            os.replace(tmp_path, blob_path)
        else:
            tmp_path.unlink()
            
    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink()
        raise e
        
    # Now create revision in DB
    cursor = conn.cursor()
    cursor.execute('SELECT MAX(sequence) as m FROM revisions WHERE document_id = ?', (doc_id,))
    row = cursor.fetchone()
    seq = (row['m'] or 0) + 1
    
    rev_id = str(uuid.uuid4())
    now = _now()
    
    cursor.execute('''
        INSERT INTO revisions (
            id, document_id, sequence, blob_sha256, original_filename, mime_type,
            size_bytes, issue_date, coverage_start, coverage_end, term, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        rev_id, doc_id, seq, sha256_hex, original_filename, mime_type, size_bytes,
        issue_date, coverage_start, coverage_end, term, now
    ))
    
    # Auto-activate this revision
    new_version = doc.metadata_version + 1
    cursor.execute('UPDATE documents SET active_revision_id = ?, metadata_version = ?, updated_at = ? WHERE id = ?',
                   (rev_id, new_version, now, doc_id))
    
    _emit_event(cursor, 'revision_added', doc_id, new_version, rev_id)
    conn.commit()
    
    return get_revision(conn, rev_id)

def get_revision(conn: sqlite3.Connection, rev_id: str) -> Optional[LibraryRevision]:
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM revisions WHERE id = ?', (rev_id,))
    row = cursor.fetchone()
    if not row:
        return None
    return LibraryRevision(
        id=row['id'],
        document_id=row['document_id'],
        sequence=row['sequence'],
        blob_sha256=row['blob_sha256'],
        original_filename=row['original_filename'],
        mime_type=row['mime_type'],
        size_bytes=row['size_bytes'],
        issue_date=row['issue_date'],
        coverage_start=row['coverage_start'],
        coverage_end=row['coverage_end'],
        term=row['term'],
        superseded_by=row['superseded_by'],
        created_at=datetime.fromisoformat(row['created_at'])
    )

def get_revisions_for_document(conn: sqlite3.Connection, doc_id: str) -> List[LibraryRevision]:
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM revisions WHERE document_id = ? ORDER BY sequence DESC', (doc_id,))
    revs = []
    for row in cursor.fetchall():
        revs.append(LibraryRevision(
            id=row['id'],
            document_id=row['document_id'],
            sequence=row['sequence'],
            blob_sha256=row['blob_sha256'],
            original_filename=row['original_filename'],
            mime_type=row['mime_type'],
            size_bytes=row['size_bytes'],
            issue_date=row['issue_date'],
            coverage_start=row['coverage_start'],
            coverage_end=row['coverage_end'],
            term=row['term'],
            superseded_by=row['superseded_by'],
            created_at=datetime.fromisoformat(row['created_at'])
        ))
    return revs

def set_index_receipt(conn: sqlite3.Connection, doc_id: str, rev_id: str, status: str):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO index_receipts (document_id, revision_id, status, reported_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(document_id, revision_id) DO UPDATE SET status = excluded.status, reported_at = excluded.reported_at
    ''', (doc_id, rev_id, status, _now()))
    conn.commit()

def get_index_receipt(conn: sqlite3.Connection, doc_id: str, rev_id: str) -> Optional[LibraryIndexReceipt]:
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM index_receipts WHERE document_id = ? AND revision_id = ?', (doc_id, rev_id))
    row = cursor.fetchone()
    if not row:
        return None
    return LibraryIndexReceipt(
        document_id=row['document_id'],
        revision_id=row['revision_id'],
        status=row['status'],
        reported_at=datetime.fromisoformat(row['reported_at'])
    )

def get_events(conn: sqlite3.Connection, after_sequence: int = 0, limit: int = 100) -> Tuple[List[LibraryEvent], bool]:
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM events WHERE sequence > ? ORDER BY sequence ASC LIMIT ?', (after_sequence, limit + 1))
    rows = cursor.fetchall()
    
    has_more = len(rows) > limit
    rows = rows[:limit]
    
    events = []
    for row in rows:
        events.append(LibraryEvent(
            sequence=row['sequence'],
            event_id=row['event_id'],
            event_type=row['event_type'],
            document_id=row['document_id'],
            revision_id=row['revision_id'],
            catalog_version=row['catalog_version'],
            created_at=datetime.fromisoformat(row['created_at'])
        ))
    return events, has_more
