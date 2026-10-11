"""One-shot post-commit delivery. Startup/owner refresh/n8n recover missed events."""
import logging

import httpx
from fastapi import HTTPException

log = logging.getLogger(__name__)


class LibraryDelivery:
    def __init__(self, settings):
        self.url = settings.igor_url.rstrip("/")
        self.headers = {"X-API-Key": settings.igor_api_key, "X-N8N-Secret": settings.igor_n8n_secret}
        self.http = httpx.AsyncClient(timeout=30, follow_redirects=False)

    @property
    def configured(self):
        return bool(self.url and all(self.headers.values()))

    async def reconcile(self, *, full=False):
        if not self.configured:
            return {"status": "unconfigured"}
        response = await self.http.post(self.url + "/library/reconcile", headers=self.headers, params={"full": full})
        response.raise_for_status()
        return response.json()

    async def notify(self):
        try:
            await self.reconcile()
        except Exception:
            # The event is already durable. Do not undo uploads for delivery outages.
            log.warning("Hall event delivery deferred to reconciliation", exc_info=True)

    async def control(self, method, path, payload=None):
        if not self.configured:
            raise HTTPException(503, "Indexing engine is not connected. Configure HISAR_IGOR_URL, HISAR_IGOR_API_KEY and HISAR_IGOR_N8N_SECRET on Hisar.")
        try:
            response = await self.http.request(method, self.url + path, headers=self.headers, json=payload)
            if response.status_code == 422:
                detail = response.json().get("detail")
                raise HTTPException(422, detail if isinstance(detail, str) else "Check the Iacon settings values")
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(503, "Igor indexing engine is unavailable. Your originals and indexing requests are safely stored; reconnect and retry.") from exc

    async def retry(self, conn, doc_id):
        from . import library
        library.request_reindex(conn, doc_id)
        result = await self.control("POST", "/library/reconcile")
        if result.get("status") == "unconfigured":
            raise HTTPException(503, "Igor cannot connect to the Hisar catalog. Your retry request is saved; configure Igor's Hisar library tokens.")
        return {**result, "document_id": doc_id, "message": "Retry accepted. Watch the indexing status for completion."}

    async def aclose(self):
        await self.http.aclose()
