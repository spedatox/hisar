self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET" || request.mode !== "navigate" || request.destination !== "document") return;

  // Only the launcher gets a fallback. Vault, authentication and OAuth
  // traffic stays on the network, including when opened as a document.
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || url.pathname !== "/") return;

  event.respondWith(fetch(request).catch(() => new Response(OFFLINE_PAGE, {
    status: 503,
    headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" },
  })));
});
