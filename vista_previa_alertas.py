# -*- coding: utf-8 -*-
"""Diseño LOCAL de una franja informativa. No publica ni consulta noticias.

    python vista_previa_alertas.py

Genera salida/vista_previa_alertas.html, fuera de la lista de publicar.py.
Usa ejemplos explícitos y desactiva Supabase sólo en esta copia de lectura.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

EJEMPLOS = [
    {
        "id": "ruta", "icono": "160", "categoria": "Ruta 160",
        "titulo": "Ejemplo de informe vial de Ruta 160",
        "resumen": "Aquí aparecerían congestión, obras o desvíos, con el tramo y la hora del reporte.",
        "detalle": "PROPUESTA DE DISEÑO, NO ES UN REPORTE REAL.\n\n"
                   "Zona de referencia: San Pedro de la Paz, Coronel y accesos a la Ruta 160.\n"
                   "Cada informe tendría tramo, sentido del tránsito, hora y enlace a la fuente.\n"
                   "Fuente por conectar: información vial oficial o del operador de la ruta.",
    },
    {
        "id": "clima", "icono": "☁", "categoria": "Meteorología",
        "titulo": "Ejemplo de aviso meteorológico para Biobío",
        "resumen": "Un aviso oficial de lluvia o viento mostraría su zona y vigencia. No es una alerta real.",
        "detalle": "PROPUESTA DE DISEÑO, NO HAY UNA ALERTA OFICIAL CONECTADA.\n\n"
                   "Se mostrarían el organismo emisor, zona afectada y periodo de vigencia.\n"
                   "Posibles fuentes a integrar: Dirección Meteorológica de Chile y SENAPRED.\n"
                   "El pronóstico habitual del clima no se presentaría como una alerta oficial.",
    },
    {
        "id": "noticias", "icono": "i", "categoria": "Noticias locales",
        "titulo": "Ejemplo de noticia de interés para las familias",
        "resumen": "Un titular breve sobre Concepción y San Pedro de la Paz, con fecha y enlace a la publicación.",
        "detalle": "PROPUESTA DE DISEÑO, NO ES UNA NOTICIA PUBLICADA.\n\n"
                   "Cada noticia llevaría titular, resumen, fecha y medio o institución de origen.\n"
                   "El enlace permitiría leer la publicación original.\n"
                   "Todavía no se ha elegido ni conectado una fuente de noticias.",
    },
]

CSS = r"""
/* Exclusivo de la copia local: no se integra en la plantilla publicada. */
#instalar, #avisos, #avisos-estado, #avisos-ayuda, #nube-estado { display: none !important; }
.acciones #descargar { flex: 0 1 auto; }
#franja-local {
  border: 1px solid var(--borde); border-left: 4px solid var(--verde);
  background: var(--tarjeta); border-radius: 12px; margin: 0 0 16px;
  padding: 12px 14px; color: var(--texto);
}
.franja-cabecera { display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
.franja-marca { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.franja-marca strong { font-size: 13px; color: var(--verde-texto); }
.franja-demo { border: 1px dashed var(--borde); padding: 2px 7px; border-radius: 6px;
  font-size: 10px; letter-spacing: .04em; color: var(--suave); }
.franja-filtros { display: flex; flex-wrap: wrap; gap: 5px; }
.franja-filtros button { font-size: 11.5px; padding: 4px 10px; border-radius: 999px;
  background: var(--tarjeta); color: var(--suave); }
.franja-filtros button[aria-pressed="true"] { color: var(--verde-texto);
  border-color: var(--verde); background: var(--tarjeta-secundaria); font-weight: 600; }
.franja-cuerpo { display: flex; gap: 12px; align-items: center; min-width: 0; }
.franja-icono { display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  width: 38px; height: 38px; border-radius: 10px; background: var(--tarjeta-secundaria);
  color: var(--verde-texto); font-size: 15px; font-weight: 700; }
.franja-texto { flex: 1; min-width: 0; }
#franja-titulo { font-size: 13.5px; line-height: 1.4; margin: 0 0 3px; font-weight: 650; }
#franja-resumen { font-size: 12px; color: var(--suave); margin: 0; line-height: 1.5; }
#franja-ver { flex-shrink: 0; padding: 5px 10px; border-radius: 8px; font-size: 11.5px; }
#franja-detalle { white-space: pre-wrap; font-size: 12.5px; line-height: 1.6;
  border-top: 1px dashed var(--borde); padding-top: 10px; margin-top: 10px; }
#franja-detalle[hidden] { display: none; }
.franja-pie { display: block; margin: 9px 0 0; font-size: 10.5px;
  color: var(--suave); line-height: 1.5; }
@media (max-width: 640px) {
  #franja-local { padding: 10px 11px; margin-bottom: 12px; }
  .franja-cabecera { margin-bottom: 9px; gap: 8px; }
  .franja-filtros { width: 100%; }
  .franja-filtros button { flex: 1; min-height: 34px; font-size: 12px; padding: 5px 8px; }
  .franja-cuerpo { flex-wrap: wrap; gap: 8px; align-items: flex-start; }
  .franja-icono { width: 32px; height: 32px; font-size: 13px; }
  #franja-ver { margin-left: 40px; min-height: 32px; }
  .franja-texto { flex-basis: calc(100% - 42px); }
}
@media print { #franja-local { display: none !important; } }
"""

BANDA = """
<section id="franja-local" aria-label="Vista previa de información local, sólo ejemplos">
  <div class="franja-cabecera">
    <div class="franja-marca"><strong>En ruta y al día</strong>
      <span class="franja-demo">VISTA PREVIA LOCAL</span></div>
    <div class="franja-filtros" aria-label="Elegir tipo de información">
      <button type="button" data-franja="ruta" aria-pressed="true">Ruta 160</button>
      <button type="button" data-franja="clima" aria-pressed="false">Meteorología</button>
      <button type="button" data-franja="noticias" aria-pressed="false">Noticias</button>
    </div>
  </div>
  <div class="franja-cuerpo">
    <span id="franja-icono" class="franja-icono" aria-hidden="true">160</span>
    <div class="franja-texto" aria-live="polite" aria-atomic="true">
      <p id="franja-titulo"></p><p id="franja-resumen"></p>
    </div>
    <button type="button" id="franja-ver" aria-expanded="false"
            aria-controls="franja-detalle">Ver detalle</button>
  </div>
  <div id="franja-detalle" hidden></div>
  <small class="franja-pie">Datos de ejemplo, no reportes en vivo. Calendario en modo lectura;
    esta vista no modifica tarjetas ni envía notificaciones.</small>
</section>
"""

SCRIPT = r"""
<script>
(function () {
  'use strict';
  var datos = JSON.parse(document.getElementById('franja-datos').textContent);
  var botones = document.querySelectorAll('[data-franja]');
  var ver = document.getElementById('franja-ver');
  var detalle = document.getElementById('franja-detalle');
  function pintar(id) {
    var info = datos.filter(function (d) { return d.id === id; })[0];
    if (!info) return;
    document.getElementById('franja-icono').textContent = info.icono;
    document.getElementById('franja-titulo').textContent = info.titulo;
    document.getElementById('franja-resumen').textContent = info.resumen;
    detalle.textContent = info.detalle;
    detalle.hidden = true;
    ver.textContent = 'Ver detalle';
    ver.setAttribute('aria-expanded', 'false');
    botones.forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.franja === id)); });
  }
  botones.forEach(function (b) { b.addEventListener('click', function () { pintar(b.dataset.franja); }); });
  ver.addEventListener('click', function () {
    detalle.hidden = !detalle.hidden;
    ver.setAttribute('aria-expanded', String(!detalle.hidden));
    ver.textContent = detalle.hidden ? 'Ver detalle' : 'Ocultar detalle';
  });
  pintar('ruta');
})();
</script>
"""


def crear_vista_previa(html: str) -> str:
    for marca in ("</style>", "</header>", "</body>"):
        if marca not in html:
            raise ValueError("La página base no contiene " + marca)
    # Desconectar Supabase sólo en la copia, sin modificar config ni la página real.
    html, cambios = re.subn(r'(<script type="application/json" id="nube">).*?(</script>)',
                            r'\g<1>null\g<2>', html, count=1, flags=re.S)
    if cambios != 1:
        raise ValueError("No se pudo poner la vista previa en modo lectura")
    html = html.replace("</style>", CSS + "\n</style>", 1)
    html = html.replace("</header>", "</header>\n" + BANDA, 1)
    datos = json.dumps(EJEMPLOS, ensure_ascii=False).replace("</", "<\\/")
    html = html.replace("</body>", '<script type="application/json" id="franja-datos">'
                        + datos + "</script>\n" + SCRIPT + "\n</body>", 1)
    return html


def generar(salida: Path = RAIZ / "salida") -> Path:
    origen = salida / "calendario_evaluaciones.html"
    destino = salida / "vista_previa_alertas.html"
    destino.write_text(crear_vista_previa(origen.read_text(encoding="utf-8")), encoding="utf-8")
    return destino


if __name__ == "__main__":
    try:
        generar()
    except (OSError, ValueError):
        raise SystemExit("No se pudo generar la vista. Primero genera el calendario local.")
    print("Vista previa LOCAL: http://127.0.0.1:8765/vista_previa_alertas.html")
    print("Son ejemplos; no hay noticias reales conectadas ni se publica nada.")
