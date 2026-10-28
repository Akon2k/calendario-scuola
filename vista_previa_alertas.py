# -*- coding: utf-8 -*-
"""Franja LOCAL con lecturas reales y fecha de consulta. Nunca publica.

    python vista_previa_alertas.py

Genera salida/vista_previa_alertas.html, fuera de la lista de publicar.py.
Consulta fuentes públicas y desactiva Supabase sólo en esta copia de lectura.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

from edufacil.informacion_local import recopilar

RAIZ = Path(__file__).resolve().parent

SIN_CACHE = r"""
<script id="vista-local-sin-cache">
(function () {
  // Sólo la vista de este PC: no borra almacenamiento, permisos ni datos.
  if (location.protocol !== 'http:' || ['127.0.0.1', 'localhost', '[::1]'].indexOf(location.hostname) < 0) return;
  var tareas = [];
  if (navigator.serviceWorker && navigator.serviceWorker.getRegistration) {
    tareas.push(navigator.serviceWorker.getRegistration().then(function (reg) {
      if (!reg) return;
      var worker = reg.active || reg.waiting || reg.installing;
      if (worker && new URL(worker.scriptURL).origin === location.origin
          && new URL(worker.scriptURL).pathname.endsWith('/sw.js')) return reg.unregister();
    }));
  }
  if (window.caches) tareas.push(caches.keys().then(function (claves) {
    return Promise.all(claves.filter(function (c) { return /^calendario-v\d+$/.test(c); })
      .map(function (c) { return caches.delete(c); }));
  }));
  window.__vistaLocalSinCache = Promise.all(tareas).catch(function () {});
})();
</script>
"""

CSS = r"""
/* Exclusivo de la copia local: no se integra en la plantilla publicada. */
#instalar, #avisos, #avisos-estado, #avisos-ayuda, #nube-estado { display: none !important; }
.acciones #descargar { flex: 0 1 auto; }
#franja-local {
  width: 100%; max-width: 1180px; min-width: 0; box-sizing: border-box;
  border: 1px solid var(--borde); border-left: 4px solid var(--verde);
  background: var(--tarjeta); border-radius: 12px; margin: 0 auto 16px;
  padding: 12px 14px; color: var(--texto);
}
.franja-cabecera { display: flex; align-items: center; justify-content: space-between; min-width: 0;
  flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
.franja-marca { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.franja-marca strong { font-size: 13px; color: var(--verde-texto); }
.franja-demo { border: 1px dashed var(--borde); padding: 2px 7px; border-radius: 6px;
  font-size: 10px; letter-spacing: .04em; color: var(--suave); }
.franja-filtros { display: flex; flex-wrap: wrap; gap: 5px; }
.franja-filtros button { font-size: 11.5px; padding: 4px 10px; border-radius: 999px; min-width: 0;
  background: var(--tarjeta); color: var(--suave); }
.franja-filtros button[aria-pressed="true"] { color: var(--verde-texto);
  border-color: var(--verde); background: var(--tarjeta-secundaria); font-weight: 600; }
.franja-cuerpo { display: grid; grid-template-columns: 38px minmax(0, 1fr) auto;
  gap: 12px; align-items: center; min-width: 0; min-height: 78px; }
.franja-icono { display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  width: 38px; height: 38px; border-radius: 10px; background: var(--tarjeta-secundaria);
  color: var(--verde-texto); font-size: 15px; font-weight: 700; }
.franja-texto { flex: 1; min-width: 0; }
#franja-titulo { font-size: 13.5px; line-height: 1.4; margin: 0 0 3px; font-weight: 650;
  overflow-wrap: anywhere; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
#franja-resumen { font-size: 12px; color: var(--suave); margin: 0; line-height: 1.5;
  overflow-wrap: anywhere; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
#franja-fuente { display: inline-block; margin-top: 4px; font-size: 11px;
  color: var(--verde-texto); text-decoration: none; }
#franja-fuente:hover { text-decoration: underline; }
#franja-fecha { display: block; font-size: 10.5px; color: var(--suave); margin-top: 2px; }
#franja-ver { flex-shrink: 0; padding: 5px 10px; border-radius: 8px; font-size: 11.5px; }
#franja-detalle { white-space: pre-wrap; font-size: 12.5px; line-height: 1.6;
  border-top: 1px dashed var(--borde); padding-top: 10px; margin-top: 10px;
  max-height: 280px; overflow: auto; overflow-wrap: anywhere; }
#franja-detalle ul { white-space: normal; margin: 8px 0; padding-left: 20px; }
#franja-detalle li { margin-bottom: 7px; }
#franja-detalle a { color: var(--verde-texto); }
#franja-detalle[hidden] { display: none; }
.franja-pie { display: block; margin: 9px 0 0; font-size: 10.5px;
  color: var(--suave); line-height: 1.5; }
@media (max-width: 640px) {
  #franja-local { padding: 10px 11px; margin: 0 auto 12px; }
  .franja-cabecera { margin-bottom: 9px; gap: 8px; }
  .franja-filtros { display: grid; width: 100%; grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .franja-filtros button { min-height: 36px; font-size: 11.5px; padding: 5px 6px; line-height: 1.3; }
  .franja-cuerpo { grid-template-columns: 30px minmax(0, 1fr); gap: 8px; align-items: start; min-height: 0; }
  #franja-titulo { min-height: 2.8em; }
  #franja-resumen { min-height: 3em; }
  #franja-fecha { min-height: 3em; }
  .franja-icono { width: 32px; height: 32px; font-size: 13px; }
  #franja-ver { grid-column: 2; justify-self: start; margin: 0; min-height: 32px; }
  .franja-texto { min-width: 0; }
}
@media print { #franja-local { display: none !important; } }
"""

BANDA = """
<section id="franja-local" aria-label="Información local de Coronel, fuentes consultadas">
  <div class="franja-cabecera">
    <div class="franja-marca"><strong>Coronel al día</strong>
      <span class="franja-demo">SÓLO LOCAL</span></div>
    <div class="franja-filtros" aria-label="Elegir tipo de información">
      <button type="button" data-franja="noticias" aria-pressed="true">BioBioChile</button>
      <button type="button" data-franja="clima" aria-pressed="false">Tiempo en Coronel</button>
      <button type="button" data-franja="ruta" aria-pressed="false">Ruta 160 · Coronel</button>
    </div>
  </div>
  <div class="franja-cuerpo">
    <span id="franja-icono" class="franja-icono" aria-hidden="true">160</span>
    <div class="franja-texto" aria-live="polite" aria-atomic="true">
      <p id="franja-titulo"></p><p id="franja-resumen"></p>
      <a id="franja-fuente" target="_blank" rel="noopener noreferrer"></a>
      <time id="franja-fecha"></time>
    </div>
    <button type="button" id="franja-ver" aria-expanded="false"
            aria-controls="franja-detalle">Ver detalle</button>
  </div>
  <div id="franja-detalle" hidden></div>
  <small class="franja-pie">Fuentes consultadas al generar esta vista; revisa su fecha.
    Copia local de lectura: no modifica tarjetas ni envía notificaciones.</small>
</section>
"""

SCRIPT = r"""
<script>
(function () {
  'use strict';
  var paquete = JSON.parse(document.getElementById('franja-datos').textContent);
  var datos = paquete.lecturas;
  var botones = document.querySelectorAll('[data-franja]');
  var ver = document.getElementById('franja-ver');
  var detalle = document.getElementById('franja-detalle');
  function fecha(valor, dia) {
    var d = new Date(valor);
    if (!valor || isNaN(d.getTime())) return '';
    var op = {timeZone: 'America/Santiago', day: '2-digit', month: '2-digit', year: 'numeric'};
    if (!dia) { op.hour = '2-digit'; op.minute = '2-digit'; op.hour12 = false; }
    return d.toLocaleString('es-CL', op);
  }
  function urlSegura(url) {
    try {
      var u = new URL(url);
      return u.protocol === 'https:' && !u.username && !u.password && (!u.port || u.port === '443') &&
        ['www.biobiochile.cl', 'biobio.transporteinforma.cl', 'open-meteo.com'].indexOf(u.hostname) >= 0;
    } catch (e) { return false; }
  }
  function pintar(id) {
    var info = datos.filter(function (d) { return d.id === id; })[0];
    if (!info) return;
    var edad = Date.now() - new Date(info.consultado).getTime();
    var vencido = !isFinite(edad) || edad < -300000 || edad > info.vigencia_segundos * 1000;
    document.getElementById('franja-local').dataset.estado = vencido ? 'vencido' : info.estado;
    document.getElementById('franja-icono').textContent = info.icono;
    document.getElementById('franja-titulo').textContent = vencido ? info.categoria + ': datos desactualizados' : info.titulo;
    document.getElementById('franja-resumen').textContent = vencido
      ? 'Abre la fuente para revisar información reciente. Esta consulta local ya no se presenta como actual.' : info.resumen;
    var fuente = document.getElementById('franja-fuente');
    fuente.textContent = info.fuente + ' ↗';
    fuente.hidden = !urlSegura(info.url);
    if (!fuente.hidden) fuente.href = info.url;
    var meta = document.getElementById('franja-fecha');
    meta.textContent = (info.publicado ? (info.id === 'clima' ? 'Datos del: ' : 'Publicado: ')
      + fecha(info.publicado, info.publicado_precision === 'dia') + ' · ' : '')
      + 'Consulta: ' + fecha(info.consultado);
    meta.dateTime = info.consultado;
    detalle.textContent = vencido ? 'Vuelve a consultar las fuentes para disponer de datos recientes.'
      : (info.id === 'noticias' && info.estado === 'ok' ? '' : info.detalle);
    if (!vencido && info.enlaces && info.enlaces.length) {
      var lista = document.createElement('ul');
      info.enlaces.forEach(function (entrada) {
        if (!urlSegura(entrada.url)) return;
        var li = document.createElement('li'), a = document.createElement('a');
        a.textContent = entrada.titulo + ' · ' + fecha(entrada.fecha, entrada.precision === 'dia');
        a.href = entrada.url; a.target = '_blank'; a.rel = 'noopener noreferrer';
        li.appendChild(a); lista.appendChild(li);
      });
      detalle.appendChild(lista);
    }
    detalle.hidden = true;
    ver.textContent = 'Ver detalle';
    ver.setAttribute('aria-expanded', 'false');
    botones.forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.franja === id)); });
  }
  botones.forEach(function (b) { b.addEventListener('click', function () { pintar(b.dataset.franja); }); });
  // El listón local puede recibir otra lectura sin reactivar la nube.
  document.addEventListener('informacion-local-actualizada', function (e) { datos = e.detail.lecturas; });
  ver.addEventListener('click', function () {
    detalle.hidden = !detalle.hidden;
    ver.setAttribute('aria-expanded', String(!detalle.hidden));
    ver.textContent = detalle.hidden ? 'Ver detalle' : 'Ocultar detalle';
  });
  pintar('noticias');
})();
</script>
"""


def consultar_mensajes(html: str) -> list[dict]:
    """GET con la configuración pública del HTML; nunca usa secretos locales."""
    marca = re.search(r'<script type="application/json" id="nube">(.*?)</script>', html, re.S)
    nube = json.loads(marca[1]) if marca else None
    if not nube or not nube.get('mensajes'):
        return []
    url = urlparse(nube['url'])
    if (url.scheme != 'https' or not (url.hostname or '').endswith('.supabase.co')
            or url.username or url.password or url.port not in (None, 443)
            or not re.fullmatch(r'[a-zA-Z_][a-zA-Z_0-9]*', nube['mensajes'])):
        raise ValueError('Origen de comunicados no válido')
    parametros = [('select', 'id,asunto,fecha,puntos,accion,eventos'),
                  ('order', 'fecha.desc,id.desc'), ('limit', 500),
                  ('fecha', 'gte.2026-09-01T00:00:00-04:00'),
                  ('fecha', 'lte.' + datetime.now(timezone.utc).isoformat())]
    filas = []
    try:
        for offset in range(0, 10000, 500):
            with requests.get(nube['url'].rstrip('/') + '/rest/v1/' + nube['mensajes'],
                    params=parametros + [('offset', offset)],
                    headers={'apikey': nube['key'], 'Authorization': 'Bearer ' + nube['key']},
                    timeout=(5, 20)) as respuesta:
                respuesta.raise_for_status()
                parte = respuesta.json()
            if not isinstance(parte, list) or not all(isinstance(m, dict) for m in parte):
                raise ValueError('Respuesta de comunicados no válida')
            filas.extend(parte)
            if len(parte) < 500:
                return filas
    except requests.RequestException:
        raise ValueError('No se pudieron consultar los comunicados; se conserva la vista anterior') from None
    raise ValueError('Demasiados comunicados para la copia local')


def crear_vista_previa(html: str, datos: dict, mensajes: list[dict] | None = None) -> str:
    for marca in ("</style>", "</header>", "</body>"):
        if marca not in html:
            raise ValueError("La página base no contiene " + marca)
    # Desconectar Supabase sólo en la copia, sin modificar config ni la página real.
    html, cambios = re.subn(r'(<script type="application/json" id="nube">).*?(</script>)',
                            r'\g<1>null\g<2>', html, count=1, flags=re.S)
    if cambios != 1:
        raise ValueError("No se pudo poner la vista previa en modo lectura")
    if {d.get('id') for d in datos.get('lecturas', [])} != {'ruta', 'clima', 'noticias'}:
        raise ValueError("Falta información o estado de alguna fuente")
    # El worker de la PWA no debe guardar las pruebas locales. Desactivar sólo
    # su registro automático en esta copia; conservar el calendario original.
    html = html.replace("nav.serviceWorker.register('sw.js').catch(function () {});",
                        '// Vista local: sin registro automático del service worker.')
    html = html.replace('</head>', SIN_CACHE + '\n</head>', 1)
    # El clima de la cabecera también usa Coronel sólo en esta copia. No tocar
    # la ubicación guardada del calendario normal ni pedir permiso de ubicación.
    html = html.replace("var lugarClimaDefecto = { latitud: -36.83, longitud: -73.05, nombre: 'Concepción' };",
                        "var lugarClimaDefecto = { latitud: -37.03386, longitud: -73.14019, nombre: 'Coronel' };")
    html = html.replace('edufacil-clima-lugar', 'edufacil-clima-lugar-vista-coronel')
    html = html.replace("lugar.propia ? lugar.nombre : 'Mi ubicación'", "lugar.propia ? lugar.nombre : 'Coronel'")
    if mensajes is not None:
        # Reutilizar el renderizador y las pestañas originales, sin reactivar
        # Supabase ni escrituras desde el navegador de la vista previa.
        mensajes_json = json.dumps(mensajes, ensure_ascii=False).replace('</', '<\\/')
        html = html.replace('<div id="mensajes-lista">',
            '<p class="sub">Copia local de los comunicados al generar esta vista; no se actualiza en vivo.</p>'
            '<div id="mensajes-lista">', 1)
        html = html.replace('</body>',
            '<script type="application/json" id="mensajes-locales">' + mensajes_json + '</script>\n'
            '<script>window.__calendario.mensajes(JSON.parse(document.getElementById("mensajes-locales").textContent));</script>\n</body>', 1)
    html = html.replace("</style>", CSS + "\n</style>", 1)
    html = html.replace("</header>", "</header>\n" + BANDA, 1)
    datos_json = json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")
    html = html.replace("</body>", '<script type="application/json" id="franja-datos">'
                         + datos_json + "</script>\n" + SCRIPT + "\n</body>", 1)
    return html


def generar(salida: Path = RAIZ / "salida", datos: dict | None = None,
            mensajes: list[dict] | None = None) -> Path:
    origen = salida / "calendario_evaluaciones.html"
    destino = salida / "vista_previa_alertas.html"
    html = origen.read_text(encoding="utf-8")
    mensajes = consultar_mensajes(html) if mensajes is None else mensajes
    datos = datos if datos is not None else recopilar()
    destino.write_text(crear_vista_previa(html, datos, mensajes), encoding="utf-8")
    (salida / "informacion_local.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


if __name__ == "__main__":
    try:
        generar()
    except (OSError, ValueError):
        raise SystemExit("No se pudo generar la vista. Primero genera el calendario local.")
    print("Vista previa LOCAL: http://127.0.0.1:8765/vista_previa_alertas.html")
    print("Fuentes consultadas. Datos con fecha de consulta; no se publica ni se envían avisos.")
