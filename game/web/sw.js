// Offline cache for the installable web app (code only; the user's game data lives in the browser's own storage, never here).
const CACHE = 'ccr-shell-v2';
const SHELL = ['./ccr.html', './ccr.js', './ccr.wasm', './manifest.webmanifest'];
self.addEventListener('install', e => e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())));
self.addEventListener('activate', e => e.waitUntil(caches.delete('ccr-shell-v1').then(() => self.clients.claim())));
self.addEventListener('fetch', e => { if (e.request.method !== 'GET') return; e.respondWith(caches.open(CACHE).then(cache => cache.match(e.request)).then(r => r || fetch(e.request))); });
