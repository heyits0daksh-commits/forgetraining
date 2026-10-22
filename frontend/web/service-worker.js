// Service worker. Two jobs:
// 1) Its mere presence + registration is what makes Chrome/Android treat
//    this site as an installable PWA (manifest.json alone isn't enough).
// 2) Caches the app shell + static assets so repeat visits load instantly
//    from disk instead of re-downloading everything, and the UI still opens
//    (network calls will still need connectivity, but you won't get a
//    blank/error page) when offline or on a flaky connection.
const CACHE_NAME = 'forge-shell-v6';
const SHELL_FILES = [
  '/',
  '/index.html',
  '/css/styles.css',
  '/js/config.js',
  '/js/boot.js',
  '/js/a11y.js',
  '/assets/img/boxing.jpg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Static assets (js/css/images/fonts/vendor libs like Chart.js) rarely
// change between visits, so they're cached the first time they're fetched
// and served straight from disk after that - this is what makes the app
// feel instant on a second open instead of re-downloading ~1MB of JS every
// single time. HTML and API calls skip this and always go to the network
// first, so a fresh deploy or fresh data is never stuck behind a stale cache.
const RUNTIME_CACHEABLE = /\.(?:png|jpg|jpeg|webp|svg|woff2?)$/;
// JS/CSS are network-first: cache-first meant that after a deploy people kept
// running the OLD code until their second load (and could mix new HTML with old JS).
const CODE_ASSET = /\.(?:js|css)$/;

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Never cache API calls - those must always be live/fresh.
  if (url.pathname.includes('/api/v1/')) return;
  if (req.method !== 'GET') return;

  if (CODE_ASSET.test(url.pathname)) {
    event.respondWith(
      fetch(req).then((res) => {
        if (res && res.ok) {
          const copy = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
        }
        return res;
      }).catch(() => caches.match(req))
    );
    return;
  }

  if (RUNTIME_CACHEABLE.test(url.pathname)) {
    event.respondWith(
      caches.match(req).then((cached) => {
        const network = fetch(req).then((res) => {
          if (res && res.ok) {
            caches.open(CACHE_NAME).then((cache) => cache.put(req, res.clone()));
          }
          return res;
        }).catch(() => cached);
        // Cache-first: instant if we already have it, still refreshes the
        // cache quietly in the background for next time.
        return cached || network;
      })
    );
    return;
  }

  // Everything else (HTML, unknown types): network-first so navigations
  // and fresh deploys are never served stale, falling back to cache only
  // when there's no connectivity.
  event.respondWith(
    fetch(req).then((res) => {
      if (res && res.ok) {
        caches.open(CACHE_NAME).then((cache) => cache.put(req, res.clone()));
      }
      return res;
    }).catch(() => caches.match(req))
  );
});
