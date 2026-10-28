# -*- coding: utf-8 -*-
"""Integración de Noticias Scuola y listón informativo en la página publicada."""
from __future__ import annotations

import json
import re
from pathlib import Path

from edufacil.informacion_local import recopilar
from vista_noticias_scuola import integrar_noticias, recopilar_noticias, recopilar_noticias_nube
from vista_previa_alertas import CSS as CSS_ALERTA, SCRIPT as SCRIPT_ALERTA
from vista_previa_liston import AYUDA, CONTROL as CONTROL_LISTON, ESTILO as ESTILO_LISTON, LISTON

# Limpiar las reglas exclusivas de la prueba local (no ocultar botones de PWA/Avisos en producción)
CSS_LIMPIO = re.sub(r'/\* Exclusivo de la copia local.*?\*/\s*#instalar.*?\n(\.acciones.*?\n)?', '', CSS_ALERTA, flags=re.S)


def aplicar_noticias_y_liston(html: str) -> str:
    """Integra la pestaña Noticias Scuola, el listón y las instrucciones actualizadas."""
    # 1. Instrucciones de uso ordenadas y limpias (10 puntos)
    if '<details id="ayuda">' in html:
        html = re.sub(r'<details id="ayuda">.*?</details>', AYUDA, html, count=1, flags=re.S)

    # 2. Listón Al día (BioBioChile, tiempo Coronel, Ruta 160)
    if 'id="franja-local"' not in html:
        datos = recopilar()
        datos_json = json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")
        liston_html = LISTON.replace('title="Vista local. Consulta las fechas y fuentes al abrir el detalle."',
                                     'title="Titulares y datos al día. Consulta las fechas y fuentes al abrir el detalle."')
        liston_html = liston_html.replace('aria-label="Listón local de noticias, tiempo y Ruta 160"',
                                          'aria-label="Listón de noticias, tiempo y Ruta 160"')
        html = html.replace("</header>", "</header>\n" + liston_html, 1)
        # Inyectar tanto la base de la franja (estilos de caja, detalle, etc.) como los estilos del listón
        html = html.replace("</style>", CSS_LIMPIO + "\n" + ESTILO_LISTON + "\n</style>", 1)
        # Inyectar el motor base (SCRIPT_ALERTA) y el carrusel del listón (CONTROL_LISTON)
        html = html.replace("</body>", '<script type="application/json" id="franja-datos">'
                            + datos_json + "</script>\n" + SCRIPT_ALERTA + "\n" + CONTROL_LISTON + "\n</body>", 1)

    # 3. Pestaña Noticias Scuola (2026, traducciones, lector y Supabase)
    if 'id="noticias-scuola"' not in html:
        noticias = recopilar_noticias_nube() or recopilar_noticias()
        html = integrar_noticias(html, noticias)

    return html
