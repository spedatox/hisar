"""Compatibility Finder view of managed Hall records, never the blob directory."""
from pathlib import Path

from fastapi import HTTPException

from . import library
from .paths import normalize

MOUNT = "/Documents/Library"


def contains(path):
    p = normalize(path)
    return p.casefold() == MOUNT.casefold() or p.casefold().startswith(MOUNT.casefold() + "/")


def protects_container(path):
    p = normalize(path).casefold()
    return contains(path) or (p != "/" and MOUNT.casefold().startswith(p + "/"))


def list_entries(root, path):
    p = normalize(path)
    if p != MOUNT:
        raise HTTPException(409, "Open Iacon Hall of Records to browse collections")
    with library.get_connection(root) as conn:
        rows = conn.execute("SELECT id FROM documents WHERE is_tombstone=0 AND is_archived=0 ORDER BY title,id").fetchall()
        entries = []
        for row in rows:
            record = library.record_response(conn, row["id"])
            rev = record.active_revision
            if rev is None:
                continue
            extension = Path(rev.original_filename).suffix.lower()
            name = record.document.id + extension
            entries.append({"name": name, "display_name": record.document.title, "path": MOUNT + "/" + name,
                            "kind": "file", "size": rev.size_bytes, "modified": record.document.updated_at,
                            "ext": extension.lstrip("."), "provider": "library"})
        return entries


def upload(root, path, file, *, overwrite=False):
    if normalize(path) != MOUNT or overwrite:
        raise HTTPException(409, "Use Hall of Records to select an entry for a new edition")
    with library.get_connection(root) as conn:
        record = library.create_record(root, conn, Path(file.filename or "Record").stem, file)
        rev = record.active_revision
        name = record.document.id + Path(rev.original_filename).suffix.lower()
        return {"name": name, "display_name": record.document.title, "path": MOUNT + "/" + name,
                "kind": "file", "size": rev.size_bytes, "ext": Path(rev.original_filename).suffix.lstrip("."),
                "provider": "library"}


def original(root, path, *, inline=False):
    relative = normalize(path)[len(MOUNT)+1:]
    if not relative or "/" in relative:
        raise HTTPException(404, "Record not found")
    with library.get_connection(root) as conn:
        doc = library._require_document(conn, Path(relative).stem)
        if not doc.active_revision_id:
            raise HTTPException(404, "Record has no active edition")
        return library.original_response(root, conn, doc.active_revision_id, inline=inline)
