const CACHE_NAME = 'attendiq-v2';
const ASSETS = [
  '/',
  '/index.html',
  '/style.css',
  '/app.js',
  '/mock-api.js',
  '/lucide.min.js',
  '/chart.js',
  '/icon.png',
  '/manifest.json'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS);
    })
  );
});

self.addEventListener('fetch', (e) => {
  // Let streaming / API requests go straight to network
  if (e.request.url.includes('/api/')) {
    return;
  }
  
  e.respondWith(
    caches.match(e.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }
      return fetch(e.request);
    })
  );
});
