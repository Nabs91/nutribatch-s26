// Network-first Service Worker (v4 - Apple HIG Edition + Daily Promo Pruner)
const CACHE_NAME = "nutribatch-hig-v4";
self.addEventListener("install", e => self.skipWaiting());
self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.map(k => caches.delete(k)))).then(() => self.clients.claim())
  );
});
self.addEventListener("fetch", e => {
  e.respondWith(fetch(e.request, { cache: "no-store" }).catch(() => caches.match(e.request)));
});
