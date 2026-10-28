# -*- coding: utf-8 -*-
"""Servidor de pruebas sin caché, sólo accesible desde este PC.

    python servidor_vista_local.py

Sirve salida/ en http://127.0.0.1:8765. No publica ni modifica datos.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class SinCache(SimpleHTTPRequestHandler):
    def send_head(self):
        # No responder 304 con una copia que el navegador pueda tener antigua.
        for cabecera in ('If-Modified-Since', 'If-None-Match'):
            if cabecera in self.headers:
                del self.headers[cabecera]
        return super().send_head()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()


if __name__ == '__main__':
    carpeta = Path(__file__).resolve().parent / 'salida'
    handler = partial(SinCache, directory=str(carpeta))
    with ThreadingHTTPServer(('127.0.0.1', 8765), handler) as servidor:
        print('Vista LOCAL sin caché: http://127.0.0.1:8765/vista_previa_liston.html', flush=True)
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            pass
