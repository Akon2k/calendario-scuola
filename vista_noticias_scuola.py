# -*- coding: utf-8 -*-
"""Noticias oficiales de 2026, exclusivamente en la copia local del calendario."""
from __future__ import annotations

import re
import json
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from edufacil.informacion_local import CHILE, descargar, enlace_valido, texto

DOMINIO = 'scuola.scuolaitalianadiconcepcion.cl'
FUENTE = 'https://' + DOMINIO + '/noticia/'
ANIO = 2026
API = 'https://' + DOMINIO + '/wp-json/wp/v2/posts'
AGENTE = 'Mozilla/5.0 (compatible; ScuolaCalendarioLocal/1.0)'


def recopilar_noticias_nube() -> dict | None:
    """Sólo clave pública del HTML ya generado; nunca lee secretos privados."""
    try:
        html = (Path(__file__).resolve().parent / 'salida/calendario_evaluaciones.html').read_text(encoding='utf-8')
        marca = re.search(r'<script type="application/json" id="nube">(.*?)</script>', html, re.S)
        config = json.loads(marca[1]) if marca else None
        if not config:
            return None
        u = urlparse(config.get('url', ''))
        key = config.get('key', '')
        if u.scheme != 'https' or not (u.hostname or '').endswith('.supabase.co') or u.username or u.password or u.port:
            return None
        # Las claves secretas nunca deben entrar en un HTML. Esta instalación
        # usa una publishable; no aceptar service_role ni sb_secret como fallback.
        if not isinstance(key, str) or not key.startswith('sb_publishable_'):
            return None
        revision = None
        with requests.get(config['url'].rstrip('/') + '/rest/v1/noticias_scuola_revision',
                params={'select': 'version'}, headers={'apikey': key}, timeout=(5, 15)) as revision_r:
            if revision_r.ok:
                revisiones = revision_r.json()
                if isinstance(revisiones, list) and revisiones:
                    revision = revisiones[0].get('version')
        with requests.get(config['url'].rstrip('/') + '/rest/v1/noticias_scuola',
                params={'select': 'id,url,fecha,titulo,titulo_es,titulo_es_proveedor,detalle,miniatura', 'order': 'fecha.desc,url.asc',
                        'fecha': 'lte.' + datetime.now(CHILE).date().isoformat(), 'limit': 1000},
                headers={'apikey': key}, timeout=(5, 20)) as respuesta:
            respuesta.raise_for_status()
            if len(respuesta.content) > 2_000_000:
                return None
            filas = respuesta.json()
        if not isinstance(filas, list) or not filas:
            return None
        return {'estado': 'ok', 'consultado': datetime.now(CHILE).isoformat(), 'noticias': filas,
                'nube': {'url': config['url'], 'key': key, 'revision': revision}}
    except (OSError, ValueError, TypeError, requests.RequestException):
        return None


def texto_html(html: str) -> str:
    sopa = BeautifulSoup(html, 'html.parser')
    for nodo in sopa.select('script, style, iframe'):
        nodo.decompose()
    return texto(sopa.get_text(' ', strip=True))


def parsear_noticias(html: str, ahora: datetime) -> list[dict]:
    sopa = BeautifulSoup(html, 'html.parser')
    noticias, vistos = [], set()
    for tarjeta in sopa.select('.vc_grid-item'):
        enlace = tarjeta.select_one('a.vc_gitem-link[href]')
        titulo = tarjeta.select_one('.vc_gitem-post-data-source-post_title')
        if not enlace or not titulo:
            continue
        url = urljoin(FUENTE, enlace['href'])
        if not enlace_valido(url, DOMINIO):
            continue
        ruta = urlparse(url)
        fecha = re.fullmatch(r'/2026/(\d{2})/(\d{2})/[^/]+/?', ruta.path)
        if not fecha or ruta.query or ruta.fragment or url in vistos:
            continue
        try:
            publicada = datetime(ANIO, int(fecha[1]), int(fecha[2]), tzinfo=CHILE)
        except ValueError:
            continue
        nombre = texto(titulo.get_text(' ', strip=True))
        if not nombre or publicada.date() > ahora.astimezone(CHILE).date():
            continue
        imagen = tarjeta.select_one('img[src]')
        imagen_url = urljoin(FUENTE, imagen['src']) if imagen else ''
        if not enlace_valido(imagen_url, DOMINIO) or not urlparse(imagen_url).path.startswith('/wp-content/uploads/'):
            imagen_url = ''
        vistos.add(url)
        extracto = tarjeta.select_one('.vc_gitem-post-data-source-post_excerpt')
        detalle = texto_html(str(extracto)) if extracto else ''
        noticias.append({'titulo': nombre, 'url': url, 'fecha': publicada.date().isoformat(),
                         'imagen': imagen_url, 'miniatura': '', 'detalle': detalle})
    return sorted(noticias, key=lambda n: n['fecha'], reverse=True)[:250]


def completar_miniaturas(noticias: list[dict]) -> None:
    """Dos lecturas públicas para el año, sin descargar 105 fotos grandes.

    El archivo /noticia/ sigue siendo la lista autorizada. La API sólo aporta
    extractos y tamaños reales de WordPress a esas mismas publicaciones.
    """
    por_url = {n['url']: n for n in noticias}
    for pagina in range(1, 4):
        try:
            for intento in range(2):
                try:
                    respuesta = descargar(API, agente=AGENTE, parametros={
                        'categories': 32,  # Categoría pública «2026» del sitio oficial.
                        'after': '2026-01-01T00:00:00', 'before': '2027-01-01T00:00:00',
                        'per_page': 100, 'page': pagina, '_embed': 'wp:featuredmedia',
                        '_fields': 'link,excerpt,_links,_embedded'})
                    break
                except requests.RequestException:
                    if intento == 1:
                        raise
            entradas = json.loads(respuesta)
            if not isinstance(entradas, list):
                return
            for entrada in entradas:
                if not isinstance(entrada, dict) or entrada.get('link') not in por_url:
                    continue
                noticia = por_url[entrada['link']]
                extracto = texto_html((entrada.get('excerpt') or {}).get('rendered') or '')
                if extracto:
                    noticia['detalle'] = extracto
                candidatos = []
                for medio in (entrada.get('_embedded') or {}).get('wp:featuredmedia', []):
                    if not isinstance(medio, dict):
                        continue
                    for tamano in (medio.get('media_details') or {}).get('sizes', {}).values():
                        w, h, url = tamano.get('width', 0), tamano.get('height', 0), tamano.get('source_url', '')
                        if (isinstance(w, int) and isinstance(h, int) and 0 < w <= 300 and 0 < h <= 300
                                and enlace_valido(url, DOMINIO) and urlparse(url).path.startswith('/wp-content/uploads/')):
                            candidatos.append((abs(w - 150) + abs(h - 150), w * h, url))
                if candidatos:
                    noticia['miniatura'] = min(candidatos)[2]
            if len(entradas) < 100:
                return
        except (requests.RequestException, ValueError, TypeError, AttributeError):
            # Si falla la API, conservar el texto del archivo y NO recurrir a
            # la imagen grande: es preferible una fila sin foto a gastar datos.
            return


def recopilar_noticias(ahora: datetime | None = None) -> dict:
    ahora = ahora or datetime.now(CHILE)
    paquete = {'consultado': ahora.isoformat(), 'estado': 'error', 'noticias': []}
    for intento in range(2):
        try:
            html = descargar(FUENTE, agente=AGENTE)
            noticias = parsear_noticias(html, ahora)
            if noticias:
                completar_miniaturas(noticias)
                paquete.update(estado='ok', noticias=noticias)
            break
        except requests.RequestException:
            if intento == 1:
                break
        except (ValueError, TypeError):
            break
    return paquete


ESTILO = r"""
#noticias-scuola { position: absolute; inset: 0; overflow-y: auto; scrollbar-gutter: stable;
  padding: 14px; background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 12px;
  overflow-wrap: anywhere; }
#noticias-scuola[hidden], .noticia-scuola[hidden], #scuola-mas[hidden] { display: none; }
.scuola-cabecera { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
  gap: 6px 12px; margin-bottom: 14px; }
.scuola-cabecera h2 { font-size: 16px; margin: 0; }
.scuola-cabecera a { font-size: 12px; color: var(--verde-texto); }
.scuola-noticias-rejilla { display: grid; grid-template-columns: minmax(0, 1fr); gap: 10px; }
.noticia-scuola { min-width: 0; border: 1px solid var(--borde); border-radius: 10px;
  overflow: hidden; background: var(--tarjeta-secundaria); }
.noticia-scuola a { display: flex; align-items: flex-start; gap: 12px; padding: 12px;
  color: var(--texto); text-decoration: none; }
.noticia-scuola a:hover { background: var(--boton-hover); }
.noticia-scuola a:focus-visible { outline: 2px solid var(--verde-texto); outline-offset: -3px; }
.noticia-scuola img { display: block; width: 88px; height: 72px; flex: 0 0 88px;
  object-fit: cover; border-radius: 6px; background: var(--borde); }
.noticia-scuola .scuola-texto { min-width: 0; flex: 1; }
.noticia-scuola time { display: block; font-size: 11px; color: var(--suave); margin-top: 7px; }
.noticia-scuola h3 { font-size: 14px; line-height: 1.45; margin: 0; }
.noticia-scuola .scuola-extracto { font-size: 12.5px; line-height: 1.5; margin: 6px 0 0; color: var(--texto-secundario); }
.scuola-traduccion { margin: 5px 0 0; font-size: 13px; line-height: 1.5; color: var(--texto-secundario); }
.scuola-google[hidden], #scuola-google-legal[hidden] { display: none; }
.scuola-google img { display: block; width: 160px; max-width: 100%; height: auto; border-radius: 0; }
#scuola-google-legal { margin-top: 14px; font-size: 11px; color: var(--suave); }
#scuola-lector { width: min(740px, calc(100% - 28px)); max-height: 85vh; overflow: auto;
  box-sizing: border-box; border: 1px solid var(--borde); border-radius: 12px; padding: 18px;
  color: var(--texto); background: var(--tarjeta); }
#scuola-lector::backdrop { background: rgba(0,0,0,.55); }
.scuola-lector-barra { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
.scuola-lector-barra a { font-size: 12px; color: var(--verde-texto); }
#scuola-lector h2 { font-size: 19px; line-height: 1.4; margin: 0; }
#scuola-lector-fecha { display: block; margin: 10px 0 16px; color: var(--suave); font-size: 12px; }
#scuola-lector-texto p { white-space: pre-wrap; font-size: 14px; line-height: 1.7; margin: 0 0 15px; }
#scuola-lector-estado { color: var(--suave); font-size: 13px; }
.scuola-pie { text-align: center; margin-top: 16px; }
#pestanas .experimental { display: none; }
#pestanas button { min-width: 0; }
@media (max-width: 640px) {
  #pestanas { gap: 6px; }
  #pestanas button { font-size: 12px; padding: 9px 5px; line-height: 1.4; }
  #pestanas .icono { width: 14px; height: 14px; }
  #pestanas .cuenta { padding: 1px 5px; margin-left: 3px; }
  #noticias-scuola { padding: 11px; }
  .noticia-scuola a { padding: 10px; gap: 10px; }
  .noticia-scuola img { width: 64px; height: 64px; flex-basis: 64px; }
}
@media print { #noticias-scuola { display: none !important; } }
"""

PESTANA = """<button id="tab-noticias-scuola" type="button" aria-controls="noticias-scuola">
<svg class="icono" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/>
<path d="M7 8h4v4H7zM14 8h3M14 12h3M7 16h10"/></svg> Noticias Scuola<span id="cuenta-noticias-scuola" class="cuenta" hidden></span></button>"""

LECTOR = """<dialog id="scuola-lector" aria-labelledby="scuola-lector-titulo">
<div class="scuola-lector-barra"><button id="scuola-volver" type="button">← Volver</button>
<a id="scuola-original" target="_blank" rel="noopener noreferrer">Ver publicación original ↗</a></div>
<h2 id="scuola-lector-titulo"></h2><p id="scuola-lector-traduccion" class="scuola-traduccion"></p>
<a id="scuola-google-lector" class="scuola-google" href="https://translate.google.com/" target="_blank" rel="noopener noreferrer" hidden>
<img data-google-badge width="640" height="91" alt="Powered by Google Translate" referrerpolicy="no-referrer"></a>
<time id="scuola-lector-fecha"></time><p id="scuola-lector-estado" role="status" aria-live="polite"></p>
<div id="scuola-lector-texto"></div></dialog>"""

CONTROL = r"""
<script id="control-noticias-scuola">
(function () {
  'use strict';
  var cal = document.getElementById('tab-calendario');
  var mensajes = document.getElementById('tab-mensajes');
  var noticias = document.getElementById('tab-noticias-scuola');
  var panel = document.getElementById('noticias-scuola');
  var datos = JSON.parse(document.getElementById('scuola-datos').textContent);
  var nube = JSON.parse(document.getElementById('scuola-config').textContent);
  var lista = panel.querySelector('.scuola-noticias-rejilla');
  var mas = document.getElementById('scuola-mas');
  var cuenta = document.getElementById('cuenta-noticias-scuola');
  var claveLeidas = 'edufacil-noticias-scuola-leidas';
  var dialogo = document.getElementById('scuola-lector');
  var textoLector = document.getElementById('scuola-lector-texto');
  var estadoLector = document.getElementById('scuola-lector-estado');
  var volverA = null, peticion = null, consultando = false;
  var cacheTextos = new Map();
  var revision = nube && nube.revision;
  function google(n) { return n && n.titulo_es && n.titulo_es_proveedor === 'google'; }
  function insignia(elemento, visible) {
    elemento.hidden = !visible;
    var img = elemento.querySelector('img');
    if (visible && img && !img.getAttribute('src')) img.src = 'https://docs.cloud.google.com/static/translate/images/text-attribution.png';
  }
  function atribucion() {
    var usaGoogle = datos.some(google);
    insignia(document.getElementById('scuola-google-lista'), usaGoogle);
    document.getElementById('scuola-google-legal').hidden = !usaGoogle;
    var nota = document.getElementById('scuola-google-ayuda');
    if (usaGoogle && !nota) {
      var li = document.querySelector('#ayuda ol > li:nth-child(3)');
      if (li) {
        nota = document.createElement('p'); nota.id = 'scuola-google-ayuda';
        nota.appendChild(document.createTextNode('Algunos títulos usan traducciones automáticas de Google Translate. '));
        var enlace = document.createElement('a'); enlace.href = 'https://cloud.google.com/translate';
        enlace.target = '_blank'; enlace.rel = 'noopener noreferrer'; enlace.textContent = 'Información del servicio de traducción.';
        nota.appendChild(enlace); li.appendChild(nota);
      }
    } else if (!usaGoogle && nota) nota.remove();
  }
  function permitida(url) {
    try { var u = new URL(url); return u.protocol === 'https:' && u.hostname === 'scuola.scuolaitalianadiconcepcion.cl'
      && !u.port && !u.username && !u.password && !u.search && !u.hash && /^\/2026\/\d{2}\/\d{2}\/[a-z0-9-]+\/$/.test(u.pathname); }
    catch (e) { return false; }
  }
  function miniPermitida(url) {
    try { var u = new URL(url); return u.protocol === 'https:' && u.hostname === 'scuola.scuolaitalianadiconcepcion.cl'
      && !u.port && !u.username && !u.password && u.pathname.indexOf('/wp-content/uploads/') === 0; }
    catch (e) { return false; }
  }
  function configurada() {
    try { var u = new URL(nube.url); return u.protocol === 'https:' && u.hostname.endsWith('.supabase.co')
      && !u.port && !u.username && !u.password && /^sb_publishable_/.test(nube.key); } catch (e) { return false; }
  }
  function leidas() {
    try { var p = JSON.parse(localStorage.getItem(claveLeidas) || '{}'); return p && typeof p === 'object' && !Array.isArray(p) ? p : {}; }
    catch (e) { return {}; }
  }
  var leidasSesion = leidas();
  function contador() {
    if (!panel.hidden) {
      datos.forEach(function (n) { leidasSesion[n.url] = 1; });
      try { localStorage.setItem(claveLeidas, JSON.stringify(leidasSesion)); } catch (e) {}
    }
    var numero = datos.filter(function (n) { return !leidasSesion[n.url]; }).length;
    cuenta.textContent = numero ? String(numero) : ''; cuenta.hidden = numero === 0;
  }
  function fecha(valor) { var partes = valor.split('-'); return partes.length === 3 ? partes.reverse().join('/') : valor; }
  function cargar(img) {
    if (!img.dataset.src) return;
    img.src = img.dataset.src; delete img.dataset.src;
  }
  var observador = window.IntersectionObserver ? new IntersectionObserver(function (entradas) {
    entradas.forEach(function (e) { if (e.isIntersecting) { cargar(e.target); observador.unobserve(e.target); } });
  }, {root: panel, rootMargin: '120px'}) : null;
  function cargarVisibles() {
    if (!observador) panel.querySelectorAll('.noticia-scuola:not([hidden]) img[data-src]').forEach(cargar);
  }
  function observar() {
    panel.querySelectorAll('img').forEach(function (img) {
      img.addEventListener('error', function () { img.hidden = true; img.style.display = 'none'; });
      if (observador) observador.observe(img);
    });
  }
  function renderizar(nuevos) {
    var visibles = Math.max(12, lista.querySelectorAll('.noticia-scuola:not([hidden])').length);
    var scroll = panel.scrollTop;
    if (observador) observador.disconnect();
    var fragmento = document.createDocumentFragment();
    nuevos.forEach(function (n, i) {
      var articulo = document.createElement('article'); articulo.className = 'noticia-scuola'; articulo.hidden = i >= visibles;
      var a = document.createElement('a'); a.href = n.url; a.dataset.noticiaUrl = n.url; a.target = '_blank'; a.rel = 'noopener noreferrer';
      if (n.miniatura && miniPermitida(n.miniatura)) {
        var img = document.createElement('img'); img.dataset.src = n.miniatura; img.alt = ''; img.width = 88; img.height = 72;
        img.loading = 'lazy'; img.decoding = 'async'; img.referrerPolicy = 'no-referrer'; a.appendChild(img);
      }
      var caja = document.createElement('div'); caja.className = 'scuola-texto';
      var h = document.createElement('h3'); h.textContent = n.titulo; caja.appendChild(h);
      if (n.titulo_es) { var es = document.createElement('p'); es.className = 'scuola-traduccion'; es.lang = google(n) ? 'es-x-mtfrom-it' : 'es';
        if (google(n)) es.title = 'Traducción automática de Google Translate';
        es.textContent = '(' + n.titulo_es + ')'; caja.appendChild(es); }
      if (n.detalle) { var p = document.createElement('p'); p.className = 'scuola-extracto'; p.textContent = n.detalle; caja.appendChild(p); }
      var time = document.createElement('time'); time.dateTime = n.fecha; time.textContent = fecha(n.fecha); caja.appendChild(time);
      a.appendChild(caja); articulo.appendChild(a); fragmento.appendChild(articulo);
    });
    lista.replaceChildren(fragmento); datos = nuevos; mas.hidden = nuevos.length <= visibles;
    panel.scrollTop = scroll; observar(); if (!panel.hidden) cargarVisibles(); contador(); atribucion();
  }
  async function revisar() {
    if (consultando || document.visibilityState === 'hidden' || !configurada()) return;
    consultando = true;
    try {
      var rev = await fetch(nube.url + '/rest/v1/noticias_scuola_revision?select=version',
        {headers: {apikey: nube.key}, cache: 'no-store', signal: AbortSignal.timeout(10000)});
      if (!rev.ok) return;
      var revisiones = await rev.json();
      if (!Array.isArray(revisiones) || !revisiones[0] || !Number.isSafeInteger(revisiones[0].version)) return;
      var nuevaRevision = revisiones[0].version;
      if (nuevaRevision === revision) { contador(); return; }
      var u = nube.url + '/rest/v1/noticias_scuola?select=id,url,fecha,titulo,titulo_es,titulo_es_proveedor,detalle,miniatura&order=fecha.desc,url.asc&limit=1000';
      var r = await fetch(u, {headers: {apikey: nube.key}, cache: 'no-store', signal: AbortSignal.timeout(15000)});
      if (!r.ok) return;
      var filas = await r.json();
      if (!Array.isArray(filas) || filas.length > 1000 || !filas.length) return;
      var hoy = new Intl.DateTimeFormat('en-CA', {timeZone: 'America/Santiago', year: 'numeric', month: '2-digit', day: '2-digit'}).format(new Date());
      if (!filas.every(function (n) { return n && permitida(n.url) && typeof n.titulo === 'string' && n.titulo.length <= 1000
          && /^2026-\d{2}-\d{2}$/.test(n.fecha) && n.fecha <= hoy && typeof n.id === 'string'
          && (n.titulo_es === null || typeof n.titulo_es === 'string') && typeof n.detalle === 'string'; })) return;
      if (JSON.stringify(filas) !== JSON.stringify(datos)) renderizar(filas);
      else contador();
      revision = nuevaRevision;
    } catch (e) { /* conservar la copia y los contadores; nunca borrar por un fallo */ }
    finally { consultando = false; }
  }
  function estado(activo) {
    [cal, mensajes, noticias].forEach(function (b) {
      if (b === activo) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
    });
  }
  // Reutilizar las pestañas originales para conservar los contadores de
  // mensajes y el estado del calendario. No reactivar Supabase.
  [cal, mensajes].forEach(function (b) {
    b.addEventListener('click', function () {
      panel.hidden = true; noticias.classList.remove('activa'); estado(b);
      history.replaceState(null, '', b === cal ? '#calendario' : '#mensajes');
      contador();
    });
  });
  noticias.addEventListener('click', function () {
    cal.click();
    document.getElementById('vista-calendario').hidden = true;
    document.getElementById('mensajes').hidden = true;
    panel.hidden = false;
    cal.classList.remove('activa'); mensajes.classList.remove('activa');
    noticias.classList.add('activa'); estado(noticias);
    history.replaceState(null, '', '#noticias');
    cargarVisibles();
    contador(); revisar();
  });
  mas.addEventListener('click', function () {
    var ocultas = Array.from(panel.querySelectorAll('.noticia-scuola[hidden]'));
    ocultas.slice(0, 12).forEach(function (n) { n.hidden = false; });
    mas.hidden = ocultas.length <= 12;
    cargarVisibles();
    if (mas.hidden) {
      var enlace = ocultas[0] && ocultas[0].querySelector('a');
      if (enlace) enlace.focus();
    }
  });
  function mostrarTexto(texto) {
    textoLector.replaceChildren();
    texto.split(/\n\s*\n/).forEach(function (t) { if (t.trim()) { var p = document.createElement('p'); p.textContent = t; textoLector.appendChild(p); } });
    estadoLector.textContent = '';
  }
  panel.addEventListener('click', async function (e) {
    var a = e.target.closest('a[data-noticia-url]');
    if (!a || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey || e.button > 0) return;
    e.preventDefault();
    var n = datos.filter(function (d) { return d.url === a.dataset.noticiaUrl; })[0];
    if (!n) return;
    volverA = a; if (peticion) peticion.abort(); peticion = new AbortController();
    var esta = peticion;
    document.getElementById('scuola-lector-titulo').textContent = n.titulo;
    document.getElementById('scuola-lector-traduccion').textContent = n.titulo_es ? '(' + n.titulo_es + ')' : '';
    document.getElementById('scuola-lector-traduccion').lang = google(n) ? 'es-x-mtfrom-it' : 'es';
    insignia(document.getElementById('scuola-google-lector'), google(n));
    document.getElementById('scuola-lector-fecha').textContent = fecha(n.fecha);
    document.getElementById('scuola-original').href = n.url;
    textoLector.replaceChildren(); estadoLector.textContent = 'Cargando noticia…';
    dialogo.showModal(); dialogo.scrollTop = 0;
    if (cacheTextos.has(n.id)) { mostrarTexto(cacheTextos.get(n.id)); return; }
    if (!configurada() || !/^[0-9a-f-]{36}$/i.test(n.id || '')) {
      estadoLector.textContent = 'No pude cargar el texto. Puedes abrir la publicación original.'; return;
    }
    try {
      for (var intento = 0; intento < 3; intento++) {
        var r = await fetch(nube.url + '/functions/v1/noticias-scuola?id=' + encodeURIComponent(n.id),
          {headers: {apikey: nube.key}, signal: AbortSignal.any([esta.signal, AbortSignal.timeout(25000)])});
        if (r.status === 202 && intento < 2) { await new Promise(function (resolver) { setTimeout(resolver, 3000); }); if (esta.signal.aborted) return; continue; }
        if (!r.ok || r.status === 202) throw new Error('Texto no disponible');
        var contenido = await r.json();
        if (contenido.id !== n.id || typeof contenido.texto !== 'string' || contenido.texto.length > 100000) throw new Error('Texto no válido');
        if (esta.signal.aborted || peticion !== esta) return;
        cacheTextos.set(n.id, contenido.texto); mostrarTexto(contenido.texto); break;
      }
    } catch (error) {
      if (!esta.signal.aborted && peticion === esta) estadoLector.textContent = 'No pude cargar el texto. Puedes abrir la publicación original.';
    }
  });
  document.getElementById('scuola-volver').addEventListener('click', function () { dialogo.close(); });
  dialogo.addEventListener('close', function () { if (peticion) peticion.abort(); if (volverA && volverA.isConnected) volverA.focus(); else noticias.focus(); });
  window.addEventListener('storage', function (e) { if (e.key === claveLeidas) { leidasSesion = leidas(); contador(); } });
  document.addEventListener('visibilitychange', function () { if (document.visibilityState !== 'hidden') revisar(); });
  window.setInterval(revisar, 60000);
  observar(); contador(); atribucion();
  if (location.hash === '#noticias') noticias.click();
  else estado(mensajes.classList.contains('activa') ? mensajes : cal);
  revisar();
})();
</script>
"""


def integrar_noticias(html: str, paquete: dict) -> str:
    # La página de entrada puede ser una copia local ya integrada. Reemplazar
    # sólo nuestros bloques, sin volver a serializar ni tocar el calendario.
    for etiqueta, ident in (('button', 'tab-noticias-scuola'), ('section', 'noticias-scuola'),
                            ('dialog', 'scuola-lector'), ('script', 'scuola-config'),
                            ('script', 'scuola-datos'), ('script', 'control-noticias-scuola')):
        html = re.sub(r'<' + etiqueta + r'\b[^>]*\bid="' + ident + r'"[^>]*>.*?</' + etiqueta + r'>',
                      '', html, flags=re.S)
    html = re.sub(r'\n#noticias-scuola \{.*?@media print \{ #noticias-scuola \{ display: none !important; \} \}\n',
                  '', html, flags=re.S)
    for marca in ('<nav id="pestanas">', '<section id="mensajes" hidden>', '</style>', '</body>'):
        if marca not in html:
            raise ValueError('No se pudo agregar Noticias Scuola: falta ' + marca)
    tarjetas = []
    validas = []
    for n in paquete.get('noticias', []):
        # Validar también lecturas inyectadas: nunca publicar HTML remoto crudo.
        if not enlace_valido(n.get('url', ''), DOMINIO) or not re.match(r'/2026/\d{2}/\d{2}/', urlparse(n['url']).path):
            continue
        try:
            fecha = datetime.strptime(n['fecha'], '%Y-%m-%d')
            if fecha.year != ANIO:
                continue
        except (KeyError, ValueError, TypeError):
            continue
        imagen = n.get('miniatura', '')
        img = ('<img data-src="' + escape(imagen, quote=True) + '" width="88" height="72" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">'
               if enlace_valido(imagen, DOMINIO) and urlparse(imagen).path.startswith('/wp-content/uploads/') else '')
        validas.append({k: n.get(k) for k in ('id', 'url', 'fecha', 'titulo', 'titulo_es', 'titulo_es_proveedor', 'detalle', 'miniatura')})
        tarjetas.append('<article class="noticia-scuola"' + (' hidden' if len(tarjetas) >= 12 else '') + '><a href="'
            + escape(n['url'], quote=True) + '" data-noticia-url="' + escape(n['url'], quote=True) + '" target="_blank" rel="noopener noreferrer">' + img
            + '<div class="scuola-texto"><h3>' + escape(str(n.get('titulo', 'Noticia'))) + '</h3>'
            + ('<p class="scuola-traduccion" lang="' + ('es-x-mtfrom-it' if n.get('titulo_es_proveedor') == 'google' else 'es') + '">('
               + escape(str(n['titulo_es'])) + ')</p>' if n.get('titulo_es') else '')
            + ('<p class="scuola-extracto">' + escape(str(n['detalle'])) + '</p>' if n.get('detalle') else '')
            + '<time datetime="' + fecha.strftime('%Y-%m-%d') + '">'
            + fecha.strftime('%d/%m/%Y') + '</time></div></a></article>')
    vacio = '<p>No se pudieron cargar las noticias de 2026. Puedes revisarlas en el sitio de la Scuola.</p>' if not tarjetas else ''
    panel = ('<section id="noticias-scuola" aria-label="Noticias Scuola 2026" hidden>'
             '<div class="scuola-cabecera"><h2>Noticias Scuola · 2026</h2>'
             '<a href="' + FUENTE + '" target="_blank" rel="noopener noreferrer">Sitio de la Scuola ↗</a>'
             '<a id="scuola-google-lista" class="scuola-google" href="https://translate.google.com/" target="_blank" rel="noopener noreferrer" hidden>'
             '<img data-google-badge width="640" height="91" alt="Powered by Google Translate" referrerpolicy="no-referrer"></a></div>'
             + vacio + '<div class="scuola-noticias-rejilla">' + ''.join(tarjetas) + '</div>'
             '<div class="scuola-pie"><button id="scuola-mas" type="button"'
             + (' hidden' if len(tarjetas) <= 12 else '') + '>Ver más noticias</button></div>'
             '<details id="scuola-google-legal" hidden><summary>Sobre las traducciones automáticas</summary><p>'
             'THIS SERVICE MAY CONTAIN TRANSLATIONS POWERED BY GOOGLE. GOOGLE DISCLAIMS ALL WARRANTIES RELATED TO THE TRANSLATIONS, '
             'EXPRESS OR IMPLIED, INCLUDING ANY WARRANTIES OF ACCURACY, RELIABILITY, AND ANY IMPLIED WARRANTIES OF MERCHANTABILITY, '
             'FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.</p></details></section>\n')
    html = re.sub(r'(<nav id="pestanas">.*?)(</nav>)', lambda m: m[1] + PESTANA + '\n' + m[2], html, count=1, flags=re.S)
    html = html.replace('<section id="mensajes" hidden>', panel + '<section id="mensajes" hidden>', 1)
    html = html.replace('</style>', ESTILO + '\n</style>', 1)
    config = paquete.get('nube') or None
    if config and (not isinstance(config.get('key'), str) or not config['key'].startswith('sb_publishable_')):
        raise ValueError('Noticias Scuola sólo admite una clave pública')
    scripts = '<script type="application/json" id="scuola-config">' + json.dumps(config, ensure_ascii=False).replace('</', '<\\/') + '</script>\n'
    scripts += '<script type="application/json" id="scuola-datos">' + json.dumps(validas, ensure_ascii=False).replace('</', '<\\/') + '</script>\n'
    return html.replace('</body>', LECTOR + scripts + CONTROL + '\n</body>', 1)
