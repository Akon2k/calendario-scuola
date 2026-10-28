# -*- coding: utf-8 -*-
"""Alternativa LOCAL: listón compacto con las mismas fuentes reales.

    python vista_previa_liston.py

No cambia la plantilla ni el publicador. Conserva la vista anterior para comparar.
"""
from __future__ import annotations

from pathlib import Path
import json
import re

from edufacil.informacion_local import recopilar
from vista_previa_alertas import BANDA, RAIZ, consultar_mensajes, crear_vista_previa, generar
from vista_noticias_scuola import integrar_noticias, recopilar_noticias, recopilar_noticias_nube

AYUDA = """
<details id="ayuda">
  <summary><h2>Instrucciones de uso</h2></summary>
  <div class="ayuda-cuerpo">
    <ol>
      <li><strong>Calendario.</strong> Usa anterior y siguiente para cambiar de mes.
        Hoy vuelve a la fecha actual. Selecciona un día para ver sus evaluaciones,
        actividades, profesor, contenido y documentos disponibles. Los sábados
        muestran el resumen de la semana siguiente.</li>
      <li><strong>Mensajes.</strong> Revisa los comunicados del colegio agrupados por mes.
        Abre el mes que quieras consultar. El número de la pestaña indica los
        mensajes que todavía no has leído en este dispositivo.</li>
      <li><strong>Noticias Scuola.</strong> Muestra sólo noticias oficiales de 2026,
        con miniatura pequeña, título original, traducción al español entre
        paréntesis cuando está disponible y una breve descripción. Pulsa una
        noticia para leer su texto dentro de la aplicación, sin fotos ni videos.
        Volver cierra el lector. Ver publicación original abre el sitio del colegio.
        Ver más noticias permite continuar con las publicaciones anteriores.</li>
      <li><strong>Contadores de lectura.</strong> Mensajes y Noticias Scuola tienen
        contadores independientes. Al entrar en una pestaña, su contenido se marca
        como leído y su contador se oculta. Si aparece otra publicación, vuelve
        a mostrarse. Cada navegador y dispositivo conserva su propio estado.</li>
      <li><strong>Listón Al día.</strong> Muestra primero el tiempo en Coronel,
        después Ruta 160 y luego las noticias de BioBioChile, cambiando cada 5 segundos. Usa anterior y siguiente para cambiar
        de información, y pausa para detener o reanudar el cambio automático.
        Se detiene mientras usas el teclado, pasas el mouse por encima, abres
        un detalle o dejas la pestaña oculta.</li>
      <li><strong>Detalles del listón.</strong> Pulsa un titular de BioBioChile para
        abrir la noticia original en otra pestaña. El botón Ver detalle permite
        consultar el tiempo y el pronóstico de varios días. La hora de actualización
        aparece al final. Ruta 160 sólo tiene detalle cuando hay un reporte reciente;
        sin reportes no significa que la ruta esté despejada. El botón de cierre
        vuelve a ocultar el detalle.</li>
      <li><strong>Actualizaciones.</strong> Las noticias del colegio y los datos
        del listón se revisan cada 15 minutos. La aplicación comprueba las
        novedades cada minuto mientras la pestaña está visible.
        El calendario mantiene sus
        horarios de las 00:00, 08:00, 12:00, 16:00 y 20:00.</li>
      <li><strong>Imprimir y guardar en otro calendario.</strong> Imprimir prepara
        el mes y sus actividades para papel o PDF. Descargar .ics entrega un archivo
        que puedes importar en Google Calendar, Outlook o el calendario del teléfono.
        Importar ese archivo no crea una suscripción automática a futuros cambios.</li>
      <li><strong>Correcciones y documentos en la versión publicada.</strong>
        Editar permite corregir una evaluación y Nuevo evento permite agregar una
        actividad. Escribe tu nombre y confirma el guardado. Puedes adjuntar un PDF
        de hasta 8 MB. Si hay tarjetas duplicadas, revisa los datos y el destino
        antes de confirmar su unión.</li>
      <li><strong>Instalación y avisos en la versión publicada.</strong> En Android,
        abre la página en Chrome y elige Instalar aplicación o Añadir a pantalla
        de inicio. En iPhone, usa Safari, Compartir y Agregar a pantalla de inicio;
        abre después la aplicación desde ese acceso. Para recibir avisos, pulsa
        Avisos y concede permiso. Los contadores de las pestañas no son avisos
        del teléfono; las noticias nuevas no envían notificaciones push.</li>
    </ol>
  </div>
</details>
"""

BOTON_IMPRIMIR = """<button id="imprimir" type="button" title="Imprimir" aria-label="Imprimir">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
<path d="M6 9V3h12v6M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/>
<rect x="6" y="14" width="12" height="8"/><path d="M18 12h.01"/></svg></button>"""

BOTON_DESCARGAR = """<button id="descargar" class="primario" type="button"
title="Descargar calendario (.ics)" aria-label="Descargar calendario (.ics)">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
<rect x="3" y="4" width="18" height="17" rx="2"/>
<path d="M8 2v4M16 2v4M3 9h18M12 12v6m-3-3 3 3 3-3"/></svg></button>"""

ESTILO_BOTONES = """<style id="botones-icono-locales">
.acciones #tema, .acciones #imprimir, .acciones #descargar {
  display: inline-flex; align-items: center; justify-content: center;
  box-sizing: border-box; width: 44px; height: 40px; min-width: 44px; min-height: 40px;
  flex: 0 0 44px; padding: 0;
}
.acciones #imprimir svg, .acciones #descargar svg { display: block; width: 20px; height: 20px; }
</style>"""

ESTILO = r"""
#ayuda .ayuda-cuerpo > ol { margin: 0; padding-left: 24px; }
#ayuda .ayuda-cuerpo > ol > li { margin: 0 0 10px; }
#ayuda .ayuda-cuerpo > ol > li:last-child { margin-bottom: 0; }
#franja-local.liston-local { padding: 0; border-left: 1px solid var(--borde);
  border-radius: 9px; margin: 0 auto 12px; overflow: hidden; }
.liston-fila { display: grid; grid-template-columns: 132px minmax(0, 1fr) auto;
  align-items: stretch; min-height: 48px; }
.liston-marca { display: flex; flex-direction: column; justify-content: center; min-width: 0;
  padding: 6px 10px; background: var(--pestana-activa-fondo); color: var(--verde-texto);
  border-right: 1px solid var(--borde); line-height: 1.35; }
.liston-marca strong { font-size: 11px; text-transform: uppercase; letter-spacing: .025em; }
#liston-categoria { font-size: 10.5px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
#franja-local.liston-local #franja-titulo { display: block; min-height: 0; width: 100%;
  margin: 0; padding: 8px 12px; border: 0; border-radius: 0; background: transparent;
  font-size: 13px; font-weight: 500; color: var(--texto); text-align: left;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.5;
  text-decoration: none; cursor: pointer; align-content: center; }
#franja-local.liston-local #franja-titulo:hover { background: var(--boton-hover); }
#franja-local.liston-local #franja-titulo:focus-visible { outline: 2px solid var(--verde); outline-offset: -3px; }
.liston-controles { --liston-control-tamano: 32px; display: flex; align-items: center;
  justify-content: center; gap: 6px; padding: 6px 9px; }
.liston-controles button[hidden] { display: none !important; }
.liston-controles button, #franja-local.liston-local #franja-ver { min-height: 28px; width: 28px;
  padding: 2px; margin: 0; border-radius: 6px; font-size: 14px; flex-shrink: 0; }
#franja-local .liston-controles :is(#liston-anterior, #liston-pausa, #liston-siguiente, #franja-ver) {
  display: inline-flex; align-items: center; justify-content: center;
  width: var(--liston-control-tamano); min-height: var(--liston-control-tamano);
  background: var(--boton-fondo); border: 1px solid var(--boton-borde); color: var(--boton-texto);
  line-height: 1; border-radius: 8px; box-shadow: none; }
#franja-local .liston-controles :is(#liston-anterior, #liston-pausa, #liston-siguiente, #franja-ver) svg {
  width: 18px; height: 18px; flex-shrink: 0; }
#franja-local .liston-controles :is(#liston-anterior, #liston-pausa, #liston-siguiente, #franja-ver):hover {
  background: var(--boton-hover); border-color: var(--boton-hover-borde); }
#franja-local .liston-controles :is(#liston-anterior, #liston-pausa, #liston-siguiente, #franja-ver):focus-visible {
  outline: 2px solid var(--verde-texto); outline-offset: 2px; }
.liston-controles #liston-pausa[aria-pressed="true"] {
  background: var(--boton-hover); border-color: var(--boton-hover-borde); color: var(--boton-texto); }
#franja-local .liston-controles #franja-ver[aria-expanded="true"] {
  background: var(--boton-hover); border-color: var(--boton-hover-borde); }
#liston-contador { font-size: 10px; min-width: 25px; text-align: center; color: var(--suave); }
#franja-local.liston-local #franja-detalle { margin: 0 12px 10px; padding-top: 10px; }
.liston-detalle-cabecera { white-space: normal; }
.liston-detalle-cabecera p { margin: 0 0 6px; }
.liston-fecha { color: var(--suave); font-size: 11px; }
.liston-solo-local { color: var(--suave); font-size: 10.5px; margin: 8px 0 0; }
@media (max-width: 640px) {
  .liston-fila { grid-template-columns: 87px minmax(0, 1fr); }
  .liston-marca { grid-row: 1 / 3; padding: 6px 8px; }
  .liston-marca strong { font-size: 10px; }
  #liston-categoria { font-size: 10px; }
  #franja-local.liston-local #franja-titulo { grid-column: 2; padding: 6px 9px 0;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    white-space: normal; font-size: 12px; line-height: 1.4; height: 40px; min-height: 40px; }
  .liston-controles { --liston-control-tamano: 34px; grid-column: 2; padding: 3px 7px 5px; }
  .liston-controles button { min-height: 30px; width: 30px; }
}
"""

LISTON = """
<section id="franja-local" class="liston-local" aria-label="Listón local de tiempo, Ruta 160 y noticias">
  <div class="liston-fila">
    <div class="liston-marca" title="Vista local. Consulta las fechas y fuentes al abrir el detalle.">
      <strong>Al día</strong><span id="liston-categoria">Tiempo en Coronel</span>
    </div>
    <a id="franja-titulo" target="_blank" rel="noopener noreferrer" role="button" tabindex="0"
       aria-controls="franja-detalle" aria-expanded="false"></a>
    <div class="liston-controles" aria-label="Controles del listón">
      <span id="liston-contador"></span>
      <button id="liston-anterior" type="button" aria-label="Información anterior" title="Anterior"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m14 6-6 6 6 6"/></svg></button>
      <button id="liston-pausa" type="button" aria-label="Pausar alternancia" aria-pressed="false" title="Pausar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M8 5v14M16 5v14"/></svg></button>
      <button id="liston-siguiente" type="button" aria-label="Información siguiente" title="Siguiente"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m10 6 6 6-6 6"/></svg></button>
      <button id="franja-ver" type="button" aria-controls="franja-detalle" aria-expanded="false" title="Ver detalle"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/></svg></button>
    </div>
  </div>
  <div id="franja-detalle" hidden></div>
  <div hidden>
    <span id="franja-icono"></span><p id="franja-resumen"></p>
    <a id="franja-fuente" target="_blank" rel="noopener noreferrer"></a><time id="franja-fecha"></time>
    <button data-franja="clima" type="button" aria-pressed="true"></button>
    <button data-franja="ruta" type="button" aria-pressed="false"></button>
    <button data-franja="noticias" type="button" aria-pressed="false"></button>
  </div>
</section>
"""

CONTROL = r"""
<script>
(function () {
  'use strict';
  var paquete = JSON.parse(document.getElementById('franja-datos').textContent);
  var configuracionListon = document.getElementById('liston-config');
  var nubeListon = configuracionListon ? JSON.parse(configuracionListon.textContent) : null;
  var datos = paquete.lecturas;
  var pendiente = null, consultando = false;
  var caja = document.getElementById('franja-local');
  var titular = document.getElementById('franja-titulo');
  var detalle = document.getElementById('franja-detalle');
  var ver = document.getElementById('franja-ver');
  var pausa = document.getElementById('liston-pausa');
  var medios = {noticias: 'BioBioChile', clima: 'Tiempo en Coronel', ruta: 'Ruta 160'};
  var botones = Array.from(document.querySelectorAll('[data-franja]'));
  var frames;
  function crearFrames() {
    frames = [{tipo: 'clima'}, {tipo: 'ruta'}, {tipo: 'noticias'}];
    var noticias = datos.filter(function (d) { return d.id === 'noticias'; })[0];
    if (noticias && noticias.estado === 'ok') {
      (noticias.enlaces || []).slice(1).forEach(function (n) { frames.push({tipo: 'noticias', noticia: n}); });
    }
  }
  crearFrames();
  var indice = 0;
  var reducido = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)');
  var detenido = !!(reducido && reducido.matches);
  function formato(valor) {
    var f = new Date(valor);
    return isNaN(f.getTime()) ? '' : f.toLocaleString('es-CL', {timeZone: 'America/Santiago',
      day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false});
  }
  function noticiaSegura(n) {
    try { var u = new URL(n.url); return u.protocol === 'https:' && u.hostname === 'www.biobiochile.cl'
      && !u.username && !u.password && (!u.port || u.port === '443'); } catch (e) { return false; }
  }
  function actualizarControl() {
    pausa.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
      + (detenido ? '<path d="m9 5 10 7-10 7Z"/>' : '<path d="M8 5v14M16 5v14"/>') + '</svg>';
    pausa.setAttribute('aria-pressed', String(detenido));
    pausa.setAttribute('aria-label', detenido ? 'Reanudar alternancia' : 'Pausar alternancia');
    pausa.title = detenido ? 'Reanudar' : 'Pausar';
  }
  function actualizarDetalle() {
    var abierto = !detalle.hidden;
    ver.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/>'
      + (abierto ? '<path d="m9 9 6 6m0-6-6 6"/>' : '<path d="M12 11v6M12 7h.01"/>') + '</svg>';
    ver.title = abierto ? 'Ocultar detalle' : 'Ver detalle';
    ver.setAttribute('aria-label', ver.title);
    if (ver.hidden) {
      titular.removeAttribute('aria-expanded'); titular.removeAttribute('aria-controls');
    } else {
      titular.setAttribute('aria-expanded', String(abierto)); titular.setAttribute('aria-controls', 'franja-detalle');
    }
  }
  function preparar(tipo) {
    if (frames[indice].tipo !== tipo) indice = frames.findIndex(function (f) { return f.tipo === tipo; });
    var frame = frames[indice];
    var fuente = document.getElementById('franja-fuente');
    var meta = document.getElementById('franja-fecha');
    if (frame.noticia && caja.dataset.estado !== 'vencido' && noticiaSegura(frame.noticia)) {
      titular.textContent = frame.noticia.titulo;
      fuente.href = frame.noticia.url;
      meta.textContent = 'Publicado: ' + formato(frame.noticia.fecha) + ' · Consulta: ' + formato(meta.dateTime);
    }
    document.getElementById('liston-categoria').textContent = medios[tipo];
    document.getElementById('liston-contador').textContent = (indice + 1) + '/' + frames.length;
    titular.title = titular.textContent + '\n' + document.getElementById('franja-resumen').textContent + '\n' + meta.textContent;
    if (tipo === 'noticias' && caja.dataset.estado === 'ok' && !fuente.hidden && noticiaSegura({url: fuente.href})) {
      titular.href = fuente.href;
      titular.removeAttribute('role'); titular.removeAttribute('tabindex');
      titular.title = titular.textContent + ' · Abrir noticia en BioBioChile (otra pestaña)';
    } else {
      titular.removeAttribute('href'); titular.setAttribute('role', 'button'); titular.tabIndex = 0;
    }
    ver.hidden = tipo === 'noticias' || (tipo === 'ruta' && caja.dataset.estado !== 'ok');
    ver.disabled = ver.hidden;
    if (ver.hidden) {
      detalle.replaceChildren(); detalle.hidden = true;
      if (tipo === 'ruta') titular.title = titular.textContent;
      if (!titular.hasAttribute('href')) { titular.removeAttribute('role'); titular.removeAttribute('tabindex'); }
      actualizarDetalle();
      return;
    }
    var climaSimple = tipo === 'clima' && caja.dataset.estado === 'ok';
    if (climaSimple) detalle.replaceChildren();
    var encabezado = document.createElement('div');
    encabezado.className = 'liston-detalle-cabecera';
    var completo = document.createElement('p');
    var negrita = document.createElement('strong');
    negrita.textContent = titular.textContent;
    completo.appendChild(negrita); encabezado.appendChild(completo);
    var resumen = document.createElement('p');
    resumen.textContent = document.getElementById('franja-resumen').textContent;
    if (climaSimple) resumen.textContent = resumen.textContent.split('. Estimación de Open-Meteo')[0];
    encabezado.appendChild(resumen);
    var fecha = document.createElement('p');
    fecha.className = 'liston-fecha';
    fecha.textContent = climaSimple ? 'Actualizado: ' + formato(datos.filter(function (d) { return d.id === 'clima'; })[0].publicado) : meta.textContent;
    if (!climaSimple) encabezado.appendChild(fecha);
    if (climaSimple) titular.title = titular.textContent + '\n' + resumen.textContent + '\n' + fecha.textContent;
    if (climaSimple) {
      datos.filter(function (d) { return d.id === 'clima'; })[0].detalle.split('\n')
        .filter(function (linea) { return /^\d{2}\/\d{2}:/.test(linea); }).forEach(function (linea) {
          var dia = document.createElement('p'); dia.className = 'liston-pronostico';
          dia.textContent = linea; encabezado.appendChild(dia);
        });
      encabezado.appendChild(fecha);
    }
    if (!fuente.hidden && tipo !== 'clima') {
      var enlace = fuente.cloneNode(true); enlace.removeAttribute('id'); encabezado.appendChild(enlace);
    }
    detalle.insertBefore(encabezado, detalle.firstChild);
    actualizarDetalle();
  }
  function ir(posicion) {
    if (pendiente) {
      paquete = pendiente; pendiente = null; datos = paquete.lecturas;
      document.dispatchEvent(new CustomEvent('informacion-local-actualizada', {detail: paquete}));
      crearFrames();
    }
    indice = (posicion + frames.length) % frames.length;
    botones.filter(function (b) { return b.dataset.franja === frames[indice].tipo; })[0].click();
  }
  botones.forEach(function (b) { b.addEventListener('click', function () { preparar(b.dataset.franja); }); });
  document.getElementById('liston-anterior').addEventListener('click', function () { ir(indice - 1); });
  document.getElementById('liston-siguiente').addEventListener('click', function () { ir(indice + 1); });
  pausa.addEventListener('click', function () { detenido = !detenido; actualizarControl(); });
  titular.addEventListener('click', function (e) {
    if (!titular.hasAttribute('href')) { e.preventDefault(); ver.click(); }
  });
  titular.addEventListener('keydown', function (e) {
    if (!titular.hasAttribute('href') && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault(); ver.click();
    }
  });
  ver.addEventListener('click', actualizarDetalle);
  if (reducido && reducido.addEventListener) reducido.addEventListener('change', function (e) {
    if (e.matches) { detenido = true; actualizarControl(); }
  });
  // No mover el contenido mientras se lee, se usa el teclado o la pestaña no
  // está visible. Sin animación de desplazamiento; movimiento reducido pausa.
  window.setInterval(function () {
    if (!detenido && detalle.hidden && document.visibilityState !== 'hidden'
        && !caja.matches(':hover') && !caja.querySelector(':focus-visible')) ir(indice + 1);
  }, 5000);
  function paqueteValido(p) {
    if (!p || !Array.isArray(p.lecturas) || p.lecturas.length !== 3
        || !Number.isFinite(Date.parse(p.consultado)) || Date.parse(p.consultado) > Date.now() + 300000) return false;
    return ['noticias', 'clima', 'ruta'].every(function (tipo) {
      var filas = p.lecturas.filter(function (d) { return d && d.id === tipo; });
      if (filas.length !== 1) return false;
      var d = filas[0];
      return ['titulo', 'resumen', 'detalle', 'icono', 'categoria', 'fuente', 'url', 'estado'].every(function (k) {
        return typeof d[k] === 'string';
      }) && ['ok', 'error', 'sinreportes'].indexOf(d.estado) >= 0
        && Number.isFinite(Date.parse(d.consultado)) && Date.parse(d.consultado) <= Date.now() + 300000
        && Number.isFinite(d.vigencia_segundos) && d.vigencia_segundos > 0 && d.vigencia_segundos <= 86400
        && Array.isArray(d.enlaces) && d.enlaces.every(function (n) {
          return n && typeof n.titulo === 'string' && typeof n.url === 'string' && typeof n.fecha === 'string';
        });
    });
  }
  function actualizarLectura() {
    // La vista local lee su JSON; la web publicada sólo lee el snapshot público.
    if (consultando || document.visibilityState === 'hidden'
        || (!nubeListon && (location.protocol !== 'http:'
          || ['127.0.0.1', 'localhost', '[::1]'].indexOf(location.hostname) < 0))) return;
    consultando = true;
    var control = new AbortController();
    var limite = window.setTimeout(function () { control.abort(); }, 10000);
    var urlLectura = nubeListon ? nubeListon.url + '/rest/v1/liston_publico?select=datos&id=eq.true' : 'informacion_local.json';
    fetch(urlLectura, {cache: 'no-store', signal: control.signal,
      headers: nubeListon ? {apikey: nubeListon.key} : {}})
      .then(function (r) { if (!r.ok) throw new Error('Lectura no disponible'); return r.json(); })
      .then(function (p) {
        if (nubeListon) p = Array.isArray(p) && p[0] ? p[0].datos : null;
        if (paqueteValido(p) && Date.parse(p.consultado) > Date.parse((pendiente || paquete).consultado)) pendiente = p;
      })
      .catch(function () { /* Conservar la lectura anterior y su fecha; su vigencia no se renueva. */ })
      .finally(function () { window.clearTimeout(limite); consultando = false; });
  }
  // La consulta externa la hace el actualizador cada 15 min. El navegador
  // revisa su JSON cada minuto y aplica cambios sin interrumpir la lectura.
  window.setInterval(actualizarLectura, 60000);
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState !== 'hidden') actualizarLectura();
  });
  actualizarControl();
  ir(0);
  actualizarLectura();
})();
</script>
"""


def colocar_liston(html: str, liston: str) -> str:
    """Sitúa el listón en una fila completa, justo encima de la barra del mes."""
    marca = '<div class="acciones">'
    if marca not in html:
        raise ValueError('No se encontró la barra del calendario para colocar el listón')
    html = re.sub(r'<style id="posicion-liston">.*?</style>', '', html, flags=re.S)
    estilo = ('<style id="posicion-liston">\n'
              'header #franja-local.liston-local { flex: 0 0 100%; margin: 0; }\n</style>\n')
    html = html.replace('</head>', estilo + '</head>', 1)
    html = re.sub(r'(?m)^[ \t]+(?=\n\s*<div class="acciones">)', '', html)
    return html.replace(marca, liston.lstrip('\n') + '\n' + marca, 1)


def crear_liston(html: str, datos: dict, mensajes: list[dict] | None = None,
                 noticias: dict | None = None) -> str:
    html = html.replace(ESTILO, '')
    html = re.sub(r'<style id="botones-icono-locales">.*?</style>', '', html, flags=re.S)
    vista = crear_vista_previa(html, datos, mensajes)
    vista = re.sub(r'<button\b[^>]*\bid="imprimir"[^>]*>.*?</button>', BOTON_IMPRIMIR, vista, count=1, flags=re.S)
    vista = re.sub(r'<button\b[^>]*\bid="descargar"[^>]*>.*?</button>', BOTON_DESCARGAR, vista, count=1, flags=re.S)
    vista = re.sub(r'<details id="ayuda">.*?</details>', AYUDA, vista, count=1, flags=re.S)
    vista = colocar_liston(vista.replace(BANDA, '', 1), LISTON)
    vista = vista.replace('</style>', ESTILO + '\n</style>\n' + ESTILO_BOTONES, 1)
    vista = vista.replace('</body>', CONTROL + '\n</body>', 1)
    return integrar_noticias(vista, noticias) if noticias is not None else vista


def generar_liston(salida: Path = RAIZ / 'salida', datos: dict | None = None,
                   noticias: dict | None = None) -> Path:
    datos = datos if datos is not None else recopilar()
    html = (salida / 'calendario_evaluaciones.html').read_text(encoding='utf-8')
    mensajes = consultar_mensajes(html)
    generar(salida, datos, mensajes)  # Una sola consulta para ambas alternativas.
    noticias = (recopilar_noticias_nube() or recopilar_noticias()) if noticias is None else noticias
    destino = salida / 'vista_previa_liston.html'
    destino.write_text(crear_liston(html, datos, mensajes, noticias), encoding='utf-8')
    if noticias is not None:
        (salida / 'noticias_scuola.json').write_text(json.dumps(noticias, ensure_ascii=False, indent=2), encoding='utf-8')
    return destino


if __name__ == '__main__':
    try:
        generar_liston()
    except (OSError, ValueError):
        raise SystemExit('No se pudo generar el listón. Primero genera el calendario local.')
    print('Listón LOCAL: http://127.0.0.1:8765/vista_previa_liston.html')
    print('Fuentes reales con fecha de consulta. No se publica ni se envían avisos.')
