/* Service worker del Calendario de Evaluaciones.
   - Navegación: red primero (la página siempre es la más nueva) y la copia
     en caché queda como respaldo si no hay red.
   - Iconos y manifest: caché primero.
   - Otros dominios (Supabase): nunca se tocan, van directo a la red.
   - push: muestra el aviso diario que envía avisos.py a las 07:00. */
'use strict';
const CACHE = 'calendario-v1';
const ESTATICOS = ['./', './manifest.webmanifest', './icon-192.png',
                   './icon-512.png', './icon-maskable-512.png',
                   './apple-touch-icon.png'];

self.addEventListener('install', (e) => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE)
    .then((c) => c.addAll(ESTATICOS))
    .catch(() => undefined));
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const viejas = await caches.keys();
    await Promise.all(viejas.filter((k) => k !== CACHE)
      .map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

function guardar(resp) {
  const copia = resp.clone();
  caches.open(CACHE).then((c) => c.put(resp.url, copia)).catch(() => undefined);
  return resp;
}

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  if (new URL(req.url).origin !== self.location.origin) return;
  if (req.mode === 'navigate') {
    e.respondWith(fetch(req).then(guardar)
      .catch(() => caches.match(req).then((m) => m || caches.match('./'))));
    return;
  }
  e.respondWith(caches.match(req).then((m) => m || fetch(req).then(guardar)));
});

self.addEventListener('push', (e) => {
  let datos = { titulo: 'Calendario de Evaluaciones', cuerpo: '',
                url: './', tag: 'calendario' };
  if (e.data) {
    try { datos = Object.assign(datos, e.data.json()); }
    catch (err) { datos.cuerpo = e.data.text(); }
  }
  e.waitUntil(self.registration.showNotification(datos.titulo, {
    body: datos.cuerpo,
    icon: './icon-192.png',
    badge: './icon-192.png',
    tag: datos.tag || 'calendario',
    data: { url: datos.url || './' }
  }));
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || './';
  e.waitUntil((async () => {
    const ventanas = await self.clients.matchAll(
      { type: 'window', includeUncontrolled: true });
    for (const v of ventanas) {
      if ('focus' in v) { await v.focus().catch(() => undefined); return; }
    }
    if (self.clients.openWindow) await self.clients.openWindow(url);
  })());
});
