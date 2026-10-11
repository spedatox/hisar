"""Hall API tests using disposable vaults and real staged immutable originals."""
import io
import json
from pathlib import Path

import pytest

from .test_api import client, owner
from server import library
from server.config import get_settings

SYNC = {"X-Library-Sync-Token": "isolated-sync"}
READER = {"X-Library-Reader-Token": "isolated-reader"}


@pytest.fixture(autouse=True)
def hall_credentials(monkeypatch):
    monkeypatch.setenv("HISAR_LIBRARY_SYNC_TOKEN", "isolated-sync")
    monkeypatch.setenv("HISAR_LIBRARY_READER_TOKEN", "isolated-reader")
    monkeypatch.setenv("HISAR_IGOR_API_KEY", "")
    monkeypatch.setenv("HISAR_IGOR_N8N_SECRET", "")


def add(owner, title="Academic calendar", content=b"Final exam: January 18", **metadata):
    response = owner.post("/library/records", data={"title": title, **metadata},
                          files={"file": ("calendar.txt", content, "text/plain")})
    assert response.status_code == 200, response.text
    return response.json()


def test_named_upload_catalog_and_original_roundtrip(owner):
    record = add(owner, category="Academics", coverage_start="2026-10-01", coverage_end="2027-06-30")
    assert record["index_status"] == "pending"
    revision = record["active_revision"]
    assert revision["mime_type"] == "text/plain"
    assert owner.get("/library/revisions/" + revision["id"] + "/download").content == b"Final exam: January 18"
    listed = owner.get("/library/documents").json()
    assert listed["records"][0]["document"]["id"] == record["document"]["id"]
    feed = owner.get("/library/events", headers=SYNC).json()
    assert [e["event_type"] for e in feed["events"]] == ["document_created", "revision_added"]


def test_finder_upload_enrolls_instead_of_bypassing_catalog(owner):
    response = owner.post("/files/upload", params={"path": "/Documents/Library"},
                          files={"file": ("notes.md", b"Original notes", "text/markdown")})
    assert response.status_code == 200
    assert response.json()["provider"] == "library"
    assert owner.get("/files/download", params={"path": response.json()["path"]}).content == b"Original notes"
    assert len(owner.get("/library/documents").json()["records"]) == 1
    assert not (get_settings().sandbox_root / "Documents" / "Library" / "notes.md").exists()


def test_editions_retained_same_bytes_idempotent_and_cas(owner):
    record = add(owner)
    doc, old = record["document"], record["active_revision"]
    repeated = owner.post(f"/library/documents/{doc['id']}/revisions", data={"expected_version": doc["metadata_version"]},
                          files={"file": ("calendar.txt", b"Final exam: January 18", "text/plain")})
    assert repeated.status_code == 200 and repeated.json()["id"] == old["id"]
    new = owner.post(f"/library/documents/{doc['id']}/revisions", data={"expected_version": doc["metadata_version"]},
                     files={"file": ("calendar.txt", b"Final exam: January 25", "text/plain")})
    assert new.status_code == 200 and new.json()["sequence"] == 2
    conflict = owner.patch(f"/library/documents/{doc['id']}", json={"expected_version": doc["metadata_version"], "title": "stale"})
    assert conflict.status_code == 409
    editions = owner.get(f"/library/documents/{doc['id']}/revisions").json()
    assert len(editions) == 2 and editions[1]["superseded_by"] == new.json()["id"]
    assert owner.get(f"/library/revisions/{old['id']}/download").content == b"Final exam: January 18"


def test_archive_restore_and_wrong_document_activation(owner):
    first, second = add(owner), add(owner, title="Menu", content=b"Dinner: soup")
    doc = first["document"]
    wrong = owner.patch(f"/library/documents/{doc['id']}",
                        json={"expected_version": doc["metadata_version"], "active_revision_id": second["active_revision"]["id"]})
    assert wrong.status_code == 422
    archived = owner.patch(f"/library/documents/{doc['id']}", json={"expected_version": doc["metadata_version"], "is_archived": True})
    assert archived.status_code == 200
    assert archived.json()["index_status"] == "archived"
    assert len(owner.get("/library/documents").json()["records"]) == 1
    restored = owner.patch(f"/library/documents/{doc['id']}",
                           json={"expected_version": archived.json()["document"]["metadata_version"], "is_archived": False})
    assert restored.status_code == 200
    assert len(owner.get("/library/documents").json()["records"]) == 2


def test_scoped_reader_cannot_bypass_policy_through_download_or_manifest(owner):
    record = add(owner)
    doc = record["document"]
    owner.patch(f"/library/documents/{doc['id']}", json={"expected_version": doc["metadata_version"], "access_policy": {"allowed_agents": []}})
    owner.cookies.clear()
    denied = owner.post("/library/resolve", headers=READER, json={"document_ids": [doc["id"]], "agent_id": "ultron"})
    assert denied.status_code == 200
    assert not denied.json()["items"][0]["access_granted"]
    assert denied.json()["items"][0]["record"] is None
    assert owner.get(f"/library/revisions/{record['active_revision']['id']}/download", headers=READER).status_code == 401
    assert owner.get("/library/manifest", headers=READER).status_code == 401
    assert owner.get("/library/manifest", headers=SYNC).status_code == 200
    assert owner.post("/library/resolve", headers=READER, json={"document_ids": [doc["id"]], "agent_id": ""}).status_code == 422


def test_original_format_size_and_date_validation(owner, monkeypatch):
    for filename, content in [("bad.pdf", b"not a pdf"), ("unsafe.exe", b"MZ"), ("binary.txt", b"\x00data")]:
        assert owner.post("/library/records", data={"title": "Bad"},
                          files={"file": (filename, content, "application/octet-stream")}).status_code == 415
    assert owner.post("/library/records", data={"title": "Bad", "coverage_start": "2026-10-10", "coverage_end": "2026-01-01"},
                      files={"file": ("text.txt", b"data", "text/plain")}).status_code == 422
    monkeypatch.setattr(get_settings(), "library_max_bytes", 4)
    assert owner.post("/library/records", data={"title": "Large"},
                      files={"file": ("text.txt", b"12345", "text/plain")}).status_code == 413
    assert not owner.get("/library/documents").json()["records"]


def test_receipts_are_revision_scoped_and_reindex_is_durable(owner):
    first, second = add(owner), add(owner, title="Other")
    assert owner.post("/library/index-receipts", headers=SYNC,
                      data={"document_id": first["document"]["id"], "revision_id": second["active_revision"]["id"],
                            "sync_status": "ready_keyword"}).status_code == 422
    response = owner.post("/library/index-receipts", headers=SYNC,
                          data={"document_id": first["document"]["id"], "revision_id": first["active_revision"]["id"],
                                "sync_status": "ready_keyword"})
    assert response.status_code == 200
    response = owner.post("/library/index-receipts", headers=SYNC,
                          data={"document_id": first["document"]["id"], "revision_id": first["active_revision"]["id"],
                                "sync_status": "ready_ocr"})
    assert response.status_code == 200
    records = owner.get("/library/documents").json()["records"]
    assert next(r for r in records if r["document"]["id"] == first["document"]["id"])["index_status"] == "ready_ocr"
    assert owner.post(f"/library/documents/{first['document']['id']}/retry").status_code == 200
    assert owner.get("/library/events", headers=SYNC).json()["events"][-1]["event_type"] == "index_requested"


def test_generic_vault_cannot_mutate_hall_or_reach_internals(owner):
    record = add(owner)
    for path in ["/Documents/Library", "/Documents", "/Documents/Library/" + record["document"]["id"] + ".txt"]:
        assert owner.delete("/files/delete", params={"path": path}).status_code == 409
        assert owner.post("/files/rename", json={"path": path, "name": "other"}).status_code == 409
    for path in ["/.hisar/library/catalog.sqlite3", "/.hisar/library/blobs", "/.trash"]:
        assert owner.get("/files/list", params={"path": path}).status_code == 400
        assert owner.get("/files/download", params={"path": path}).status_code == 400
    owner.cookies.clear()
    assert owner.get("/files/list", params={"path": "/Documents/Library"},
                     headers={"X-Hisar-Token": "machine-token-for-tests"}).status_code == 403


def test_legacy_enrollment_is_lossless_and_restart_idempotent(owner):
    root = get_settings().sandbox_root
    folder = root / "Documents" / "Library" / "Academics"
    folder.mkdir(parents=True)
    original = folder / "old.txt"
    original.write_bytes(b"Owner original")
    library.bootstrap_library(root)
    first = owner.get("/library/documents").json()["records"]
    assert len(first) == 1 and first[0]["document"]["category"] == "Academics"
    library.bootstrap_library(root)
    second = owner.get("/library/documents").json()["records"]
    assert first[0]["document"]["id"] == second[0]["document"]["id"]
    assert original.read_bytes() == b"Owner original"
    with library.get_connection(root) as conn:
        assert conn.execute("SELECT COUNT(*) FROM uploads WHERE state='committed'").fetchone()[0] == 1


def test_withdrawal_hides_records_but_preserves_bytes(owner):
    record = add(owner)
    doc, rev = record["document"], record["active_revision"]
    assert owner.delete(f"/library/documents/{doc['id']}", params={"expected_version": doc["metadata_version"]}).status_code == 200
    assert not owner.get("/library/documents").json()["records"]
    assert owner.get(f"/library/revisions/{rev['id']}/download").status_code == 404
    assert (library.get_blobs_dir(get_settings().sandbox_root) / rev["blob_sha256"]).read_bytes() == b"Final exam: January 18"
    manifest = owner.get("/library/manifest", headers=SYNC).json()["records"]
    assert manifest[0]["document"]["is_tombstone"]
