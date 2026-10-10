from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import uuid

# --- Core Catalog Records (Pydantic representations of SQLite rows) ---

class LibraryDocument(BaseModel):
    id: str
    title: str
    aliases: List[str] = Field(default_factory=list)
    category: Optional[str] = None
    type: Optional[str] = None
    institution: Optional[str] = None
    subject: Optional[str] = None
    active_revision_id: Optional[str] = None
    access_policy: Dict[str, Any] = Field(default_factory=dict)
    is_archived: bool = False
    is_tombstone: bool = False
    metadata_version: int = 1
    created_at: datetime
    updated_at: datetime

class LibraryRevision(BaseModel):
    id: str
    document_id: str
    sequence: int
    blob_sha256: str
    original_filename: str
    mime_type: str
    size_bytes: int
    issue_date: Optional[str] = None
    coverage_start: Optional[str] = None
    coverage_end: Optional[str] = None
    term: Optional[str] = None
    superseded_by: Optional[str] = None
    created_at: datetime

class LibraryEvent(BaseModel):
    sequence: int
    event_id: str
    event_type: str  # e.g., 'document_created', 'revision_added', 'document_archived', 'document_purged'
    document_id: str
    revision_id: Optional[str] = None
    catalog_version: int
    created_at: datetime

class LibraryIndexReceipt(BaseModel):
    document_id: str
    revision_id: str
    status: str  # processing, ready, ready_keyword, failed
    reported_at: datetime

# --- API Request/Response Models ---

class CreateDocumentRequest(BaseModel):
    title: str
    type: Optional[str] = None
    category: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    institution: Optional[str] = None
    subject: Optional[str] = None
    access_policy: Dict[str, Any] = Field(default_factory=dict)

class UpdateDocumentRequest(BaseModel):
    expected_version: int
    title: Optional[str] = None
    type: Optional[str] = None
    category: Optional[str] = None
    aliases: Optional[List[str]] = None
    institution: Optional[str] = None
    subject: Optional[str] = None
    access_policy: Optional[Dict[str, Any]] = None
    active_revision_id: Optional[str] = None
    is_archived: Optional[bool] = None

class DocumentResponse(BaseModel):
    document: LibraryDocument
    active_revision: Optional[LibraryRevision] = None
    index_status: Optional[str] = None

class CreateRevisionMetadata(BaseModel):
    issue_date: Optional[str] = None
    coverage_start: Optional[str] = None
    coverage_end: Optional[str] = None
    term: Optional[str] = None

class ResolveRequest(BaseModel):
    document_ids: List[str]
    agent_id: str

class ResolveResponseItem(BaseModel):
    document_id: str
    active_revision_id: Optional[str]
    access_granted: bool
    is_archived: bool

class ResolveResponse(BaseModel):
    items: List[ResolveResponseItem]

class ManifestResponse(BaseModel):
    events: List[LibraryEvent]
    has_more: bool
    next_cursor: int
