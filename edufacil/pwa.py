# -*- coding: utf-8 -*-
"""Recursos de la PWA: `manifest.webmanifest`, `sw.js` e iconos.

`a_html` los copia junto al HTML de salida, de modo que el Docker local,
GitHub Pages y un doble clic sobre el archivo sirvan exactamente lo mismo:

* el **manifest** hace que Chrome/Edge ofrezcan «Instalar aplicación» y que
  el iPhone, agregado a pantalla de inicio, abra a pantalla completa;
* el **service worker** (`sw.js`) cachea la página (se abre aunque falle la
  red) y muestra las notificaciones que envía `avisos.py` (el resumen del
  sábado y el aviso de los cambios);
* los **iconos** (generados una vez con `generar_iconos.ps1`) traen las
  variantes `any`, `maskable` y `apple-touch-icon`.

Fuera del dominio propio nada se cachea: Supabase se consulta siempre en
vivo.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

NOMBRE = "Calendario de Evaluaciones — Scuola Italiana - Prima Elementare"
_ICONOS = Path(__file__).resolve().parent / "web"


def texto_manifest() -> str:
    """El `manifest.webmanifest` como texto (rutas relativas al HTML)."""
    datos = {
        "name": NOMBRE,
        "short_name": "Calendario Eva",
        "description": "Evaluaciones de la Scuola Italiana: el calendario "
                       "completo, el resumen de los sábados y los avisos "
                       "de cambios.",
        "lang": "es",
        "id": "./",
        "start_url": "./",
        "scope": "./",
        "display": "standalone",
        "background_color": "#f3f4f6",
        "theme_color": "#2563eb",
        "icons": [
            {"src": "icon-192.png", "sizes": "192x192",
             "type": "image/png", "purpose": "any"},
            {"src": "icon-512.png", "sizes": "512x512",
             "type": "image/png", "purpose": "any"},
            {"src": "icon-maskable-512.png", "sizes": "512x512",
             "type": "image/png", "purpose": "maskable"},
        ],
    }
    return json.dumps(datos, ensure_ascii=False, indent=2) + "\n"


def texto_sw() -> str:
    """El `sw.js`: caché de la página + manejadores de notificación."""
    return """\
/* Service worker del Calendario de Evaluaciones.
   - Navegación: red primero (la página siempre es la más nueva) y la copia
     en caché queda como respaldo si no hay red.
   - Iconos y manifest: caché primero.
   - Otros dominios (Supabase): nunca se tocan, van directo a la red.
   - push: muestra el aviso que envía avisos.py (sábado o cambios). */
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
"""


def copiar_recursos(destino: Path) -> list[Path]:
    """Escribe manifest + `sw.js` y copia los iconos junto al HTML.

    Se llama desde `a_html`: lo que se publica (Docker o GitHub Pages) y
    lo que se prueba es exactamente lo mismo. Si faltan los iconos, avisa
    en lugar de publicar una PWA rota.
    """
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    escritos: list[Path] = []

    for nombre, texto in (("manifest.webmanifest", texto_manifest()),
                          ("sw.js", texto_sw())):
        ruta = destino / nombre
        ruta.write_text(texto, encoding="utf-8")
        escritos.append(ruta)

    iconos = sorted(_ICONOS.glob("*.png"))
    if not iconos:
        raise RuntimeError(
            f"Faltan los iconos de la PWA: corre generar_iconos.ps1 "
            f"(no hay .png en {_ICONOS})")
    for icono in iconos:
        copia = destino / icono.name
        shutil.copyfile(icono, copia)
        escritos.append(copia)
    return escritos
