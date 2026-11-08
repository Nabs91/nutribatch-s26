// Network-first Service Worker (v7 - 100% Exact Shelf Prices & Whole Package Scaling)
const CACHE_NAME = "nutribatch-hig-v7";
self.addEventListener("install", e => self.skipWaiting());
self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.map(k => caches.delete(k)))).then(() => self.clients.claim())
  );
});
self.addEventListener("fetch", e => {
  e.respondWith(fetch(e.request, { cache: "no-store" }).catch(() => caches.match(e.request)));
});
