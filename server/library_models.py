"""Typed catalog contracts for Iacon Hall of Records."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class LibraryDocument(BaseModel):
    id: str
    title: str
    aliases: list[str] = Field(default_factory=list)
    category: str | None = None
    type: str | None = None
    institution: str | None = None
    subject: str | None = None
    active_revision_id: str | None = None
    access_policy: dict = Field(default_factory=dict)
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
    issue_date: str | None = None
    coverage_start: str | None = None
    coverage_end: str | None = None
    term: str | None = None
    superseded_by: str | None = None
    created_at: datetime


class LibraryEvent(BaseModel):
    sequence: int
    event_id: str
    event_type: str
    document_id: str
    revision_id: str | None = None
    catalog_version: int
    created_at: datetime


class LibraryIndexReceipt(BaseModel):
    document_id: str
    revision_id: str
    status: str
    reported_at: datetime


class CreateDocumentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    type: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=200)
    aliases: list[str] = Field(default_factory=list, max_length=30)
    institution: str | None = Field(default=None, max_length=240)
    subject: str | None = Field(default=None, max_length=240)
    access_policy: dict = Field(default_factory=dict)


class UpdateDocumentRequest(BaseModel):
    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=240)
    type: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=200)
    aliases: list[str] | None = Field(default=None, max_length=30)
    institution: str | None = Field(default=None, max_length=240)
    subject: str | None = Field(default=None, max_length=240)
    access_policy: dict | None = None
    active_revision_id: str | None = None
    is_archived: bool | None = None


class DocumentResponse(BaseModel):
    document: LibraryDocument
    active_revision: LibraryRevision | None = None
    index_status: str = "no_edition"


class CatalogRecord(DocumentResponse):
    revisions: list[LibraryRevision] = Field(default_factory=list)


class CreateRevisionMetadata(BaseModel):
    issue_date: date | None = None
    coverage_start: date | None = None
    coverage_end: date | None = None
    term: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def coverage(self):
        if bool(self.coverage_start) != bool(self.coverage_end):
            raise ValueError("Both coverage dates are required")
        if self.coverage_start and self.coverage_end < self.coverage_start:
            raise ValueError("Coverage end precedes start")
        return self


class ResolveRequest(BaseModel):
    document_ids: list[str] = Field(max_length=100)
    agent_id: str = Field(min_length=1, max_length=64)


class ResolveResponseItem(BaseModel):
    document_id: str
    active_revision_id: str | None = None
    access_granted: bool
    is_archived: bool = False
    record: DocumentResponse | None = None


class ResolveResponse(BaseModel):
    items: list[ResolveResponseItem]


class ManifestResponse(BaseModel):
    events: list[LibraryEvent]
    has_more: bool
    next_cursor: int