"""One-shot post-commit delivery. Startup/owner refresh/n8n recover missed events."""
import logging

import httpx

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

    async def aclose(self):
        await self.http.aclose()