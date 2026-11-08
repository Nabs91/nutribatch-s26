// Network-first Service Worker (v8 - Apple visionOS / iOS 18 Liquid Glassmorphism)
const CACHE_NAME = "nutribatch-hig-v8";
self.addEventListener("install", e => self.skipWaiting());
self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.map(k => caches.delete(k)))).then(() => self.clients.claim())
  );
});
self.addEventListener("fetch", e => {
  e.respondWith(fetch(e.request, { cache: "no-store" }).catch(() => caches.match(e.request)));
});
