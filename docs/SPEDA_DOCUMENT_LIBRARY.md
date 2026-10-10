# SPEDA document library integration

Design proposal · 10 October 2026 · No runtime implementation or deployment in this change.

Hisar will provide the owner's named, versioned document library; SPEDA Mark VI's Igor backend will extract, index and retrieve its contents. The detailed cross-application contract is maintained in the sibling Mark VI repository:

[Hisar document library for SPEDA Mark VI](../../speda-mark6/docs/HISAR_DOCUMENT_LIBRARY.md)

## Hisar's part

- Add Library / Kütüphane to the existing Finder desktop, with upload, title, category, relevant coverage dates, version history and extraction/index status.
- Keep the library in `HISAR_SANDBOX_ROOT`. The application source checkout is not document storage.
- Own stable document/revision IDs, immutable originals, current-edition selection, owner metadata/access edits and recoverable archive history.
- Use a managed `/Documents/Library` namespace backed by a hidden persistent `.hisar/library` catalog/blob store. Generic vault routes must delegate managed operations or reject bypasses.
- Publish source mutations through a transactional event feed, with immediate background delivery and startup/n8n reconciliation recovery.
- Add separate scoped library read/sync/report credentials. The existing machine deposit token stays write-only and confined to `/SPEDA` and `/Forge`.
- Keep all browser HTTP access in `api.js`, owner authentication in Hisar's session cookie, and server credentials out of the browser.
- Accept authenticated index receipts from Igor for a precise revision/generation; show when status was last reported.
- Preserve the existing path containment boundary and persistent vault mounts. Protect internal original blobs from generic path access and worker workspace mounts.

## Integration gap found in current source

Mark VI's `HisarSkill` currently assumes that its machine token can list/download files. This Hisar server rejects those operations through `require_owner`. The library integration must introduce an explicit scoped read contract rather than relying on the tool description or expanding the shared Forge credential.

The older `docs/README.md` and parts of `docs/architecture.md` describe a client-only prototype. The actual current code includes `server/`, authenticated vault/Drive APIs and `api.js`; the detailed proposal was based on those implementations.

## First release

Support named academic calendars, transcripts and cafeteria menus, including text documents and scanned/image menus. Existing files can be enrolled as explicit snapshots. A new edition preserves the previous original and immediately supersedes its current designation; Igor reports processing instead of silently answering from the older edition.

No autonomous whole-vault or whole-Drive crawl is proposed. No documents are promoted automatically into SPEDA's personal memory. Hisar remains the file and source authority; Igor remains the retrieval and assistant engine.
