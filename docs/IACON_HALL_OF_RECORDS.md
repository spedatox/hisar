# Iacon Hall of Records

The owner opens Iacon from the desktop, Finder sidebar or dock. HallOfRecords.jsx
and iacon.css implement a records catalog and edition inspector, in English and
Turkish. Add a named original, choose collection/type and edition dates, upload
a replacement, open an exact original, activate a retained edition, edit access,
retry indexing, archive or restore.

server/library.py owns the SQLite catalog, immutable SHA-256 originals, staged
upload receipts, revisions and ordered events. server/library_models.py defines
typed metadata contracts; server/library_routes.py is the authenticated API.
server/library_vault.py provides the managed Finder compatibility mount.
server/library_delivery.py sends a one-shot post-commit reconciliation request
to Igor; no polling timer exists. Startup retains originals and enrolls supported
legacy files once without removing their sources.

Owner JWT is required for management and downloads. Scoped sync credentials
read manifests/catalog/originals and write indexing receipts. Scoped reader
credentials can resolve only records granted to the caller's assistant profile,
without a raw-download bypass. Generic machine vault access cannot read the
managed library or internal .hisar state.

Copy the Iacon fields from .env.example into deployment configuration. Match
HISAR_LIBRARY_SYNC_TOKEN and HISAR_LIBRARY_READER_TOKEN with Igor. Delivery uses
HISAR_IGOR_URL, HISAR_IGOR_API_KEY and HISAR_IGOR_N8N_SECRET. It is optional for
storage; missing delivery is recoverable by owner refresh or n8n. No token is
sent to browser code.

Original uploads accept PDF, text/Markdown/CSV, images, DOCX and XLSX up to
25 MiB. Igor extracts text PDF, UTF-8 text/CSV, text DOCX and XLSX, preserving
heading/table or sheet/row/cell provenance. Optional local Tesseract/Poppler OCR
returns ready_ocr and labeled machine transcription with verification warnings;
the UI keeps these distinct from ordinary keyword-ready evidence. Disabled or
failed extraction retains originals with needs_review. Optional semantic jobs
and hybrid search are owned by Igor, and require explicit configuration there.
Readiness receipts describe a specific edition;
old fake ready statuses become pending.

The full implementation contract, limits, migration, backup/deployment notes
and cross-service verification live in the sibling SPEDA source:
docs/IACON_HALL_OF_RECORDS.md. The verification script is
packages/igor/scripts/verify_iacon.py --hisar-checkout <this source checkout>.

Run python -m pytest -p no:cacheprovider tests and npm run build. Keep test
scratch and Python caches outside this checkout. Dockerfile explicitly includes
the Hall UI files, and deploy/docker-compose.yml exposes the Iacon env fields.
Local tests and UI verification do not assert production deployment.
