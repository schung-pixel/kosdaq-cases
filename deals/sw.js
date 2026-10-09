// 신약 기술거래 딜북 - 오프라인 캐시
const VERSION = 'dealbook-2026-10-09';
const CORE = ['./', './index.html', './manifest.webmanifest', './data/deals.json', './data/runs.json', './icons/icon-192.png', './icons/icon-512.png', './icons/maskable-512.png', './icons/apple-touch-icon.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(CORE)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('dealbook-') && k !== VERSION && k !== 'dealbook-fonts').map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
const networkFirst = (req, key) => fetch(req, {cache: 'no-store'}).then(res => {
  if (res.ok) { const copy = res.clone(); caches.open(VERSION).then(c => c.put(key, copy)); }
  return res;
}).catch(() => caches.match(key));
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com') {
    e.respondWith(caches.open('dealbook-fonts').then(c => c.match(req).then(hit => hit || fetch(req).then(res => { c.put(req, res.clone()); return res; }).catch(() => hit))));
    return;
  }
  if (url.origin !== location.origin) return;
  // 페이지와 데이터: 네트워크 우선(월간 업데이트 즉시 반영), 오프라인이면 캐시
  if (req.mode === 'navigate') { e.respondWith(networkFirst(req, './index.html')); return; }
  if (url.pathname.endsWith('/data/deals.json')) { e.respondWith(networkFirst(req, './data/deals.json')); return; }
  if (url.pathname.endsWith('/data/runs.json')) { e.respondWith(networkFirst(req, './data/runs.json')); return; }
  e.respondWith(caches.match(req).then(hit => hit || fetch(req)));
});
