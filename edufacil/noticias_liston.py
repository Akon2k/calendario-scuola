# -*- coding: utf-8 -*-
"""Integra el diseño aprobado sin aplicar las restricciones de la copia local."""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from edufacil.informacion_local import recopilar
from vista_noticias_scuola import integrar_noticias, recopilar_noticias, recopilar_noticias_nube
from vista_previa_alertas import CSS as CSS_ALERTA, SCRIPT as SCRIPT_ALERTA, retirar_franja
from vista_previa_liston import (
    AYUDA, BOTON_DESCARGAR, BOTON_IMPRIMIR, CONTROL, ESTILO, ESTILO_BOTONES, LISTON, colocar_liston,
)

# Compatibilidad con la integración anterior; nunca ocultar edición/PWA/avisos.
CSS_ANTERIOR = re.sub(r'/\* Exclusivo de la copia local.*?\*/\s*#instalar.*?\n(\.acciones.*?\n)?', '', CSS_ALERTA, flags=re.S)
CSS_PUBLICO = CSS_ALERTA.replace(
    '#instalar, #avisos, #avisos-estado, #avisos-ayuda, #nube-estado { display: none !important; }', ''
).replace('.acciones #descargar { flex: 0 1 auto; }', '')


def aplicar_noticias_y_liston(html: str, datos: dict | None = None, noticias: dict | None = None) -> str:
    """Reemplaza la integración conservando nube, datos, PDF y service worker."""
    if 'id="vista-local-sin-cache"' in html or 'id="mensajes-locales"' in html:
        raise ValueError('No se puede publicar una vista previa de sólo lectura')
    marca = re.search(r'<script type="application/json" id="nube">(.*?)</script>', html, re.S)
    nube = json.loads(marca[1]) if marca else None
    u = urlparse((nube or {}).get('url', ''))
    if (not nube or u.scheme != 'https' or not (u.hostname or '').endswith('.supabase.co')
            or u.username or u.password or u.port or not str(nube.get('key', '')).startswith('sb_publishable_')):
        raise ValueError('La publicación necesita su configuración pública de producción')
    datos = recopilar() if datos is None else datos
    noticias = (recopilar_noticias_nube() or recopilar_noticias()) if noticias is None else noticias
    if not noticias:
        raise ValueError('No se pudieron preparar las noticias')
    html = retirar_franja(html)
    for css in (CSS_ALERTA, CSS_ANTERIOR, CSS_PUBLICO, ESTILO):
        html = html.replace(css, '')
    html = re.sub(r'<style id="botones-icono-locales">.*?</style>', '', html, flags=re.S)
    html = re.sub(r'<details id="ayuda">.*?</details>', AYUDA, html, count=1, flags=re.S)
    for ident, boton in (('imprimir', BOTON_IMPRIMIR), ('descargar', BOTON_DESCARGAR)):
        html = re.sub(r'<button\b[^>]*\bid="' + ident + r'"[^>]*>.*?</button>', boton, html, count=1, flags=re.S)
    liston = LISTON.replace('title="Vista local. Consulta las fechas y fuentes al abrir el detalle."',
                            'title="Consulta las fechas y fuentes al abrir el detalle."')
    liston = liston.replace('aria-label="Listón local de tiempo, Ruta 160 y noticias"',
                            'aria-label="Listón de tiempo, Ruta 160 y noticias"')
    html = colocar_liston(html, liston)
    html = html.replace('</style>', CSS_PUBLICO + '\n' + ESTILO + '\n</style>\n' + ESTILO_BOTONES, 1)
    def serializar(valor):
        return json.dumps(valor, ensure_ascii=False, allow_nan=False).replace('</', '<\\/')
    config = {'url': nube['url'].rstrip('/'), 'key': nube['key']}
    scripts = '<script type="application/json" id="franja-datos">' + serializar(datos) + '</script>\n'
    scripts += '<script type="application/json" id="liston-config">' + serializar(config) + '</script>\n'
    html = html.replace('</body>', scripts + SCRIPT_ALERTA + '\n' + CONTROL + '\n</body>', 1)
    return integrar_noticias(html, noticias)
