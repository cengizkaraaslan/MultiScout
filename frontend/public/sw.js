/* MultiScout Service Worker
   v1 — basit cache stratejileri:
   - app shell + static → cache-first
   - /api/category-tree, /api/category-counts, /api/stores-status → stale-while-revalidate
   - /api/deals → network-first (fiyatlar taze olmalı)
   - other API → network-only
*/
const VERSION = "ms-v1";
const SHELL_CACHE = `${VERSION}-shell`;
const RUNTIME_CACHE = `${VERSION}-runtime`;
const API_CACHE = `${VERSION}-api`;

const SHELL_URLS = [
  "/",
  "/manifest.json",
  "/icon-192.svg",
  "/icon-512.svg",
  "/icon-maskable.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL_URLS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => !k.startsWith(VERSION))
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

function isStaleWhileRevalidateAPI(url) {
  return (
    url.pathname.startsWith("/api/category-tree") ||
    url.pathname.startsWith("/api/category-counts") ||
    url.pathname.startsWith("/api/categories") ||
    url.pathname.startsWith("/api/stores-status")
  );
}

function isNetworkFirstAPI(url) {
  return (
    url.pathname.startsWith("/api/deals") ||
    url.pathname.startsWith("/api/scrape-all-status")
  );
}

async function staleWhileRevalidate(req) {
  const cache = await caches.open(API_CACHE);
  const cached = await cache.match(req);
  const networkPromise = fetch(req)
    .then((res) => {
      if (res && res.ok) cache.put(req, res.clone());
      return res;
    })
    .catch(() => null);
  return cached || (await networkPromise) || new Response(JSON.stringify({ status: "error", offline: true }), { headers: { "Content-Type": "application/json" } });
}

async function networkFirst(req) {
  const cache = await caches.open(API_CACHE);
  try {
    const res = await fetch(req);
    if (res && res.ok) cache.put(req, res.clone());
    return res;
  } catch {
    const cached = await cache.match(req);
    if (cached) return cached;
    return new Response(JSON.stringify({ status: "error", offline: true, data: [], total: 0 }), { headers: { "Content-Type": "application/json" } });
  }
}

async function cacheFirstStatic(req) {
  const cache = await caches.open(RUNTIME_CACHE);
  const cached = await cache.match(req);
  if (cached) return cached;
  try {
    const res = await fetch(req);
    if (res && res.ok) cache.put(req, res.clone());
    return res;
  } catch {
    return cached || Response.error();
  }
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  let url;
  try { url = new URL(req.url); } catch { return; }

  // Sadece http/https
  if (url.protocol !== "https:" && url.protocol !== "http:") return;

  // Aynı origin değilse — kendi backend de farklı origin'de olabilir; sadece /api yollarına bak
  const isAPI = url.pathname.startsWith("/api/");

  if (isAPI) {
    if (isStaleWhileRevalidateAPI(url)) {
      event.respondWith(staleWhileRevalidate(req));
      return;
    }
    if (isNetworkFirstAPI(url)) {
      event.respondWith(networkFirst(req));
      return;
    }
    return; // diğer API çağrıları için doğal davranış
  }

  // Statik (Next.js /_next/static, favicon, icons, svg, png)
  if (
    url.pathname.startsWith("/_next/static/") ||
    url.pathname.endsWith(".svg") ||
    url.pathname.endsWith(".png") ||
    url.pathname.endsWith(".webp") ||
    url.pathname.endsWith(".woff2") ||
    url.pathname === "/manifest.json"
  ) {
    event.respondWith(cacheFirstStatic(req));
    return;
  }

  // HTML navigation (offline fallback)
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(async () => {
        const cache = await caches.open(SHELL_CACHE);
        const shell = await cache.match("/");
        return shell || Response.error();
      })
    );
  }
});

// Push notification (backend ileride VAPID gönderirse)
self.addEventListener("push", (event) => {
  if (!event.data) return;
  let payload = {};
  try { payload = event.data.json(); } catch { payload = { title: "MultiScout", body: event.data.text() }; }
  const title = payload.title || "MultiScout fırsatı";
  const options = {
    body: payload.body || "Yeni indirim bulundu",
    icon: "/icon-192.svg",
    badge: "/icon-192.svg",
    data: { url: payload.url || "/" },
    tag: payload.tag || "multiscout-deal",
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window" }).then((clients) => {
      const existing = clients.find((c) => c.url.includes(self.registration.scope));
      if (existing) {
        existing.focus();
        existing.navigate(url).catch(() => {});
      } else {
        self.clients.openWindow(url);
      }
    })
  );
});
