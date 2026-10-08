# -*- coding: utf-8 -*-
"""Genera `salida/calendario.html`: un calendario que se abre con doble clic.

Es un archivo **autocontenido** (sin internet, sin servidor): trae los datos,
los colores y el texto `.ics` incrustados. Dentro tiene:

* navegación por meses con el año escolar,
* cada día con sus evaluaciones y el **resumen del sábado** (📚),
* panel de detalle al hacer clic en un día (profesor, contenido, coeficiente…),
* botón **«Descargar .ics»** que entrega el calendario completo para
  Google Calendar / Outlook web / iPhone (el `.ics` **no** se escribe en
  `salida/`, sólo se genera al pulsar),
* leyenda con colores por asignatura y vista de impresión.

El `.ics` que se descarga es el mismo que alimenta a Outlook, y Outlook a su
vez lo tiene sincronizado en la carpeta *Scuola Rafaela* con la tarea diaria.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path

from .ediciones import ConfigNube, claves_unicas
from .ics import texto_ics
from .pwa import copiar_recursos
from .semana import TIPO_RESUMEN

# Paleta fija por asignatura (se reparte por orden alfabético, así el color
# no cambia entre corridas ni entre la página y el resto de las herramientas).
PALETA = [
    "#2563eb", "#dc2626", "#059669", "#d97706", "#7c3aed", "#0891b2",
    "#db2777", "#65a30d", "#4f46e5", "#ea580c", "#0d9488", "#a16207",
    "#be123c", "#1d4ed8", "#15803d", "#b45309",
]

_PLANTILLA = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport"
      content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Calendario de Evaluaciones — Scuola Italiana - Prima Elementare</title>
<meta name="theme-color" content="#2563eb">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Calendario Eva">
<style>
  :root {
    --borde: #e5e7eb;
    --texto: #111827;
    --suave: #6b7280;
    --azul: #2563eb;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    padding: 0 max(16px, env(safe-area-inset-right)) 40px
             max(16px, env(safe-area-inset-left));
    font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    color: var(--texto); background: #f3f4f6;
    -webkit-text-size-adjust: 100%;
  }
  header {
    max-width: 1180px; margin: 0 auto; padding: 22px 0 14px;
    display: flex; flex-wrap: wrap; gap: 14px;
    align-items: center; justify-content: space-between;
  }
  h1 { margin: 0; font-size: 22px; letter-spacing: -.02em; }
  .sub { margin: 4px 0 0; color: var(--suave); font-size: 13px; }
  .acciones { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
  button {
    font: inherit; padding: 7px 13px; border-radius: 8px;
    border: 1px solid var(--borde); background: #fff; color: var(--texto);
    cursor: pointer;
  }
  button:hover { background: #f9fafb; border-color: #d1d5db; }
  button.primario { background: var(--azul); border-color: var(--azul); color: #fff; }
  button.primario:hover { background: #1d4ed8; }
  #mes-actual { font-weight: 600; min-width: 132px; text-align: center; }
  main {
    max-width: 1180px; margin: 0 auto;
    display: grid; grid-template-columns: 1fr 320px; gap: 16px;
    /* stretch: el cuadro del detalle baja hasta la misma altura que el
       calendario y las dos tarjetas quedan emparejadas (arriba y abajo) */
    align-items: stretch;
  }
  .tarjeta { background: #fff; border: 1px solid var(--borde); border-radius: 12px; }
  .dias-semana {
    display: grid; grid-template-columns: repeat(7, minmax(0, 1fr));
    gap: 6px; padding: 10px 10px 0;
  }
  .dias-semana span { font-size: 11px; text-transform: uppercase;
    letter-spacing: .08em; color: var(--suave); text-align: center; }
  .rejilla {
    display: grid; grid-template-columns: repeat(7, minmax(0, 1fr));
    gap: 6px; padding: 6px 10px 10px; overflow-x: auto;
  }
  .celda {
    min-height: 104px; padding: 6px; border: 1px solid var(--borde);
    border-radius: 9px; background: #fff; cursor: pointer; overflow: hidden;
  }
  .celda:hover { border-color: #93c5fd; }
  .celda.vacio { background: #fafafa; border-color: #f1f1f1; cursor: default; }
  .celda.sabado, .celda.domingo { background: #f9fafb; }
  .celda.hoy { box-shadow: inset 0 0 0 2px var(--azul); }
  .celda.elegida { background: #eff6ff; border-color: #93c5fd; }
  .numero { font-size: 13px; font-weight: 600; color: var(--suave); }
  .celda.hoy .numero { color: var(--azul); }
  .ev {
    margin-top: 4px; padding: 2px 6px; font-size: 11.5px; line-height: 1.35;
    border-left: 3px solid var(--c, #9ca3af); background: #fff;
    border-radius: 4px; box-shadow: 0 1px 1px rgba(0,0,0,.05);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .ev b { font-weight: 700; }
  .ev.resumen { border-left-color: #7c3aed; background: #f5f3ff; color: #5b21b6; }
  .mas { margin-top: 4px; font-size: 11px; color: var(--suave); }
  aside { padding: 14px; }
  aside h2 { margin: 0 0 4px; font-size: 17px; }
  aside .cuando { color: var(--suave); font-size: 13px; margin-bottom: 12px; }
  .item { padding: 10px 0; border-top: 1px solid var(--borde); }
  .item .asig { font-size: 12px; font-weight: 700; color: var(--c, #111827); }
  .item .tit { font-weight: 600; }
  .item .meta { font-size: 12.5px; color: var(--suave); margin-top: 3px;
    white-space: pre-line; }
  .vacio-detalle { color: var(--suave); padding: 14px 0; }
  .caja-resumen {
    margin-top: 14px; padding: 10px 12px; border-radius: 10px;
    background: #f5f3ff; border: 1px solid #ddd6fe; font-size: 13px;
  }
  .caja-resumen strong { color: #5b21b6; }
  .caja-resumen pre {
    margin: 6px 0 0; white-space: pre-wrap;
    font: inherit; color: #4c1d95;
  }
  #leyenda {
    max-width: 1180px; margin: 18px auto 0; padding: 12px 14px;
    background: #fff; border: 1px solid var(--borde); border-radius: 12px;
    display: flex; flex-wrap: wrap; gap: 10px 16px; align-items: center;
    /* space-between: cada fila llena el cuadro de borde a borde */
    justify-content: space-between;
    font-size: 13px;
  }
  .punto { display: inline-flex; align-items: center; gap: 6px; }
  .punto i { width: 11px; height: 11px; border-radius: 3px; display: inline-block; }
  footer {
    max-width: 1180px; margin: 16px auto 0; color: var(--suave); font-size: 12.5px;
  }
  #ayuda {
    max-width: 1180px; margin: 16px auto 0; padding: 10px 14px;
    background: #fff; border: 1px solid var(--borde); border-radius: 12px;
    color: var(--suave); font-size: 12.5px;
  }
  #ayuda h2 { margin: 0 0 6px; font-size: 13.5px; color: #111827; }
  #ayuda ul { margin: 0; padding-left: 18px; }
  #ayuda li { margin: 3px 0; }
  #ayuda strong { color: #111827; }
  #ayuda h3 { margin: 10px 0 2px; font-size: 13px; color: #111827; }
  #ayuda .pasos { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 18px; }
  #ayuda .pasos ol { margin: 4px 0 6px; padding-left: 18px; }
  #ayuda .pasos li { margin: 2px 0; }
  #ayuda .nota { margin: 6px 0 0; }
  @media (max-width: 980px) {
    main { grid-template-columns: 1fr; gap: 12px; }
    /* la semana y la rejilla comparten el mismo scroll horizontal */
    .rejilla, .dias-semana { min-width: 620px; }
    .scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  }
  /* ---------- edición comunitaria (Supabase) ---------- */
  .nube { font-size: 12.5px; color: var(--suave); display: inline-flex;
          align-items: center; gap: 6px; }
  .nube::before { content: ''; width: 9px; height: 9px; border-radius: 50%;
                  background: #9ca3af; display: inline-block; }
  .nube.ok::before { background: #16a34a; }
  .nube.mal::before { background: #dc2626; }
  .acciones-item { display: flex; align-items: center; gap: 8px; margin-top: 6px;
                   flex-wrap: wrap; }
  .corregido { font-size: 11.5px; color: #0f766e; background: #ecfdf5;
               border: 1px solid #a7f3d0; border-radius: 999px; padding: 2px 8px; }
  button.mini { font-size: 12px; padding: 3px 9px; border-radius: 999px; }
  #modal {
    position: fixed; inset: 0; background: rgba(17, 24, 39, .45);
    display: flex; align-items: center; justify-content: center;
    padding: 16px; z-index: 20;
  }
  #modal[hidden] { display: none; }
  .panel-modal {
    background: #fff; border-radius: 14px; width: min(560px, 100%);
    max-height: 92vh; overflow: auto; padding: 18px;
    box-shadow: 0 18px 50px rgba(0, 0, 0, .25);
  }
  .panel-modal h3 { margin: 0 0 12px; font-size: 17px; }
  .campo { display: block; margin: 0 0 10px; font-size: 13px; color: var(--suave); }
  .campo > span { display: block; margin-bottom: 4px; font-weight: 600; }
  .campo input, .campo textarea, .campo select {
    font: inherit; width: 100%; padding: 7px 9px; border: 1px solid var(--borde);
    border-radius: 8px; color: var(--texto); background: #fff;
  }
  .campo textarea { min-height: 76px; resize: vertical; }
  .grid-campos { display: grid; grid-template-columns: 1fr 1fr; gap: 0 12px; }
  .grid-campos .ancho { grid-column: 1 / -1; }
  .pie-modal { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
  .modal-error { color: #b91c1c; font-size: 13px; margin: 8px 0 0; min-height: 18px; }
  /* ---------- teléfono (iPhone 13 ≈ 390px, Moto Edge 60 Pro ≈ 412-456px) ------
     Todo cabe en pantalla: sin scroll horizontal y con objetivos táctiles. */
  @media (max-width: 640px) {
    body {
      padding: 0 max(12px, env(safe-area-inset-right)) 36px
               max(12px, env(safe-area-inset-left));
      font-size: 14.5px;
    }
    header { padding: 14px 0 8px; gap: 8px; align-items: flex-start; }
    h1 { font-size: 19px; }
    .sub { font-size: 12px; }
    .acciones { width: 100%; gap: 6px; }
    button {
      min-height: 40px; padding: 8px 12px;
      touch-action: manipulation;    /* sin retardo de doble toque */
    }
    #mes-actual { flex: 1 1 110px; min-width: 110px; font-size: 14px; }

    main { gap: 10px; }
    /* la caja del calendario se ajusta al ancho: nada se sale de la pantalla */
    .dias-semana { min-width: 0; gap: 4px; padding: 8px 6px 0; }
    .dias-semana span { font-size: 10px; letter-spacing: .04em; }
    .rejilla { min-width: 0; gap: 4px; padding: 4px 6px 8px; }
    .celda { min-height: 84px; padding: 4px; border-radius: 8px; }
    .numero { font-size: 12px; }
    .ev { margin-top: 3px; padding: 1px 4px; font-size: 10px; }
    .mas { margin-top: 2px; font-size: 10px; }

    aside { padding: 12px; }
    aside h2 { font-size: 16px; }
    .item .tit { font-size: 15px; }
    button.mini { min-height: 34px; font-size: 12.5px; padding: 6px 11px; }

    .grid-campos { grid-template-columns: 1fr; }

    /* el modal entra como hoja desde abajo, sin que iOS haga zoom al enfocar */
    #modal { align-items: flex-end; padding: 0; }
    .panel-modal {
      width: 100%; border-radius: 16px 16px 0 0; max-height: 94vh;
      padding: 16px 16px max(16px, env(safe-area-inset-bottom));
    }
    .campo input, .campo textarea, .campo select { font-size: 16px; }
    .pie-modal {
      position: sticky; bottom: 0; background: #fff;
      margin-top: 8px; padding-top: 10px;
    }
    .pie-modal button { flex: 1; min-height: 44px; }

    #leyenda { font-size: 12px; padding: 10px 12px; gap: 8px 12px; margin-top: 12px; }
    #ayuda { font-size: 12px; }
    #ayuda .pasos { grid-template-columns: 1fr; }
    footer { font-size: 12px; line-height: 1.45; }
  }
  @media print {
    body { background: #fff; padding: 0; }
    .acciones, aside { display: none; }
    main { display: block; }
    .tarjeta { border: none; }
    .celda { min-height: 92px; }
  }
</style>
</head>
<body>

<header>
  <div>
    <h1>Calendario de Evaluaciones</h1>
    <p class="sub">EduFácil · Scuola Italiana - Prima Elementare · {{RANGO}} · generado {{GENERADO}}</p>
  </div>
  <div class="acciones">
    <button id="anterior" title="Mes anterior">&#8249;</button>
    <span id="mes-actual"></span>
    <button id="siguiente" title="Mes siguiente">&#8250;</button>
    <button id="hoy">Hoy</button>
    <button id="imprimir">Imprimir</button>
    <button id="nuevo" class="primario">&#65291; Nuevo evento</button>
    <button id="descargar" class="primario">&#11015; Descargar .ics</button>
    <button id="instalar" class="primario">&#128241; Instalar app</button>
    <button id="avisos" class="primario" hidden>&#128276; Avisos</button>
    <button id="probar" hidden>&#129514; Probar aviso</button>
    <span id="avisos-estado" class="nube" title="Avisos de los sábados y de los cambios"></span>
    <span id="nube-estado" class="nube" title="Correcciones comunitarias"></span>
  </div>
</header>

<main>
  <section class="tarjeta">
    <div class="scroll">
      <div class="dias-semana">
        <span>Lun</span><span>Mar</span><span>Mié</span><span>Jue</span>
        <span>Vie</span><span>Sáb</span><span>Dom</span>
      </div>
      <div id="rejilla" class="rejilla"></div>
    </div>
  </section>

  <aside class="tarjeta" id="detalle"></aside>
</main>

<div id="modal" hidden>
  <div class="panel-modal">
    <h3 id="m-titulo">Editar evento</h3>
    <label class="campo ancho"><span>Tu nombre</span>
      <input id="m-autor" maxlength="60"
             placeholder="Quien corrige o agrega (queda en la bitácora)">
    </label>
    <div id="m-campos" class="grid-campos"></div>
    <p class="modal-error" id="m-error"></p>
    <div class="pie-modal">
      <button id="m-cancelar">Cancelar</button>
      <button id="m-guardar" class="primario">Guardar</button>
    </div>
  </div>
</div>

<section id="leyenda"></section>

<section id="ayuda">
  <h2>&#128214; Instrucciones de uso</h2>
  <ul>
    <li><strong>Ver el calendario:</strong> cambia de mes con <em>&#8249; &#8250;</em>,
      <em>Hoy</em> vuelve al día de hoy, <em>Imprimir</em> da una copia en papel.</li>
    <li><strong>Un día:</strong> toca cualquier fecha y se abren sus evaluaciones,
      cada dato en su propia línea (prueba, profesor, tipo, coeficiente y
      ponderación).</li>
    <li><strong>Sábado (&#128218;):</strong> el cuadro muestra el resumen de la
      semana que viene, con una línea en blanco entre cada fecha.</li>
    <li><strong>Corregir o agregar:</strong> en cada evento están
      <em>&#9998; Editar</em> y <em>&#65291; Nuevo evento</em>: escribes tu nombre,
      eliges el campo, Guardar — y el cambio se ve al instante para todos.</li>
    <li><strong>Conservar una copia:</strong> <em>&#11015; Descargar .ics</em> entrega
      el archivo sólo si lo pulsas; se importa con Google Calendar
      (<em>Ajustes &#8594; Importar y exportar</em>), Outlook web o el iPhone.</li>
    <li><strong>App y avisos:</strong> instala la app en tu teléfono con los
      pasos de abajo y activa <em>&#128276; Avisos</em>: el sábado llega el
      resumen y, si alguien corrige o cambia algo, avisa ese mismo día.</li>
  </ul>
  <h3>&#128241; Instalar en el teléfono (para recibir los avisos)</h3>
  <div class="pasos">
    <div>
      <strong>&#129302; Android (Chrome)</strong>
      <ol>
        <li>Abre la página en <strong>Chrome</strong> (no en Firefox ni en el
          navegador de la marca).</li>
        <li>Toca <em>&#128241; Instalar app</em> de la página, o el menú
          <em>&#8942; → Instalar aplicación</em>; si sólo aparece
          «Añadir a pantalla de inicio», también sirve.</li>
        <li>Confirma <strong>Instalar</strong>: el ícono queda en tu pantalla.</li>
        <li>Ábrela desde el ícono y toca <em>&#128276; Avisos</em> →
          <strong>Permitir</strong>.</li>
      </ol>
    </div>
    <div>
      <strong>&#127822; iPhone (Safari, iOS 16.4 o superior)</strong>
      <ol>
        <li>Abre la página en <strong>Safari</strong> (no en Chrome ni en
          otra app).</li>
        <li>Toca <em>Compartir</em> (cuadro con flecha) → «Agregar a pantalla
          de inicio» → <strong>Agregar</strong>.</li>
        <li>Ábrela desde el ícono nuevo: queda a pantalla completa.</li>
        <li>Toca <em>&#128276; Avisos</em> → <strong>Permitir</strong>.</li>
      </ol>
    </div>
  </div>
  <p class="nota">En iPhone los avisos llegan <strong>sólo</strong> desde la app
    agregada a la pantalla de inicio; en Android, desde Chrome instalada o no.</p>
</section>

<footer>
  Outlook se sincroniza solo cada mañana a las 07:00 (tarea programada),
  así el calendario queda al día sin tocar nada. Las instrucciones de uso
  están justo arriba, en «Instrucciones de uso».
</footer>

<script type="application/json" id="datos">{{DATOS}}</script>
<script type="application/json" id="ics-b64">{{ICS}}</script>
<script type="application/json" id="nube">{{NUBE}}</script>
<script>
(function () {
  var D = JSON.parse(document.getElementById('datos').textContent);
  var TIPO_RESUMEN = 'Resumen semanal';

  // ---------- estado ----------
  var NUBE = null;
  var nubeEl = document.getElementById('nube');
  if (nubeEl && nubeEl.textContent && nubeEl.textContent.trim()) {
    try { NUBE = JSON.parse(nubeEl.textContent.trim()); } catch (e) { NUBE = null; }
  }
  // Base embebida (trae las correcciones que había al generarse a las 07:00);
  // las filas de la nube se leen en vivo y se aplican encima con la misma regla
  // que edufacil/ediciones.py, de modo que repetirlas no cambia nada dos veces.
  var eventosBase = (D.eventos || []).slice();
  var filasNube = [];
  var porDia = {}, resumenDia = {}, colores = {};

  var MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio',
               'Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
  var DIAS = ['domingo','lunes','martes','miércoles','jueves','viernes','sábado'];
  var DIAS_ES = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'];
  var MESES_CORTOS = ['','ene','feb','mar','abr','may','jun','jul','ago','sep',
                      'oct','nov','dic'];
  var DIAS_CORTOS = ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'];
  var CAMPOS = ['FECHA','DIA','ASIGNATURA','ABREVIATURA','EVALUACION','CONTENIDO',
                'PROFESOR','NUMERO','COEFICIENTE','PONDERACION','TIPO'];
  var MAXIMOS = {ASIGNATURA:80, ABREVIATURA:12, EVALUACION:300, CONTENIDO:4000,
                 PROFESOR:120, NUMERO:20, COEFICIENTE:12, PONDERACION:12};
  var TIPOS = ['Evaluación', 'Sub-evaluación'];

  // Campo largo (de la nube) <-> campo corto (del JSON embebido)
  var UI = [
    {c:'FECHA',       s:'f',  et:'Fecha',                tipo:'date', req:true},
    {c:'ASIGNATURA',  s:'a',  et:'Asignatura',           req:true},
    {c:'ABREVIATURA', s:'ab', et:'Abreviatura (EFYS)'},
    {c:'EVALUACION',  s:'e',  et:'Nombre de la evaluación', req:true, ancho:true},
    {c:'CONTENIDO',   s:'c',  et:'Contenido',            tipo:'textarea', ancho:true},
    {c:'PROFESOR',    s:'p',  et:'Profesor'},
    {c:'NUMERO',      s:'n',  et:'Número (E1, T2…)'},
    {c:'COEFICIENTE', s:'co', et:'Coeficiente'},
    {c:'PONDERACION', s:'po', et:'Ponderación'},
    {c:'TIPO',        s:'t',  et:'Tipo',                 tipo:'select'}
  ];
  var SOLO_RESUMEN = ['EVALUACION', 'CONTENIDO'];

  // ------------------------------------------------------------------
  // Nube: mismas reglas que edufacil/ediciones.py (espejo)
  // ------------------------------------------------------------------
  function fechaValida(t) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(t)) return false;
    var d = new Date(t + 'T00:00:00');
    return !isNaN(d.getTime()) && iso(d) === t;
  }

  function validarCampos(campos) {
    var limpios = {};
    if (!campos || typeof campos !== 'object') return limpios;
    Object.keys(campos).forEach(function (clave) {
      var valor = campos[clave];
      if (valor && typeof valor === 'object') return;
      var nombre = String(clave).trim().toUpperCase();
      if (CAMPOS.indexOf(nombre) < 0) return;
      var texto = String(valor === undefined || valor === null ? '' : valor).trim();
      var limite = MAXIMOS[nombre] || 200;
      if (texto.length > limite) texto = texto.slice(0, limite);
      if (nombre === 'FECHA' && texto && !fechaValida(texto)) return;
      if (nombre === 'TIPO' && texto && TIPOS.indexOf(texto) < 0) return;
      limpios[nombre] = texto;
    });
    return limpios;
  }

  function claveBase(reg) {
    if (reg.TIPO === TIPO_RESUMEN) return 'SEMANA|' + (reg.FECHA || '');
    return String(reg.ASIGNATURA || '').trim().toUpperCase() + '|'
         + String(reg.NUMERO || '').trim() + '|'
         + String(reg.TIPO || '').trim().toUpperCase();
  }

  function abreviar(asignatura) {
    var palabras = String(asignatura).split(/[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+/)
                     .filter(function (p) { return p; });
    var inicial = palabras.slice(0, 5).map(function (p) { return p[0]; })
                    .join('').toUpperCase();
    return inicial || 'EV';
  }

  function diaDe(fechaIso) {
    if (!fechaValida(fechaIso)) return '';
    return DIAS_ES[(new Date(fechaIso + 'T00:00:00').getDay() + 6) % 7];
  }

  function registroNuevo(campos) {
    var limpio = validarCampos(campos);
    if (!limpio.FECHA || !limpio.ASIGNATURA || !limpio.EVALUACION) return null;
    var reg = {};
    CAMPOS.forEach(function (c) { reg[c] = ''; });
    Object.keys(limpio).forEach(function (c) { reg[c] = limpio[c]; });
    reg.DIA = diaDe(reg.FECHA);
    reg.TIPO = reg.TIPO || TIPOS[0];
    reg.ABREVIATURA = reg.ABREVIATURA || abreviar(reg.ASIGNATURA);
    return reg;
  }

  function aLargo(ev) {
    return {FECHA: ev.f, ASIGNATURA: ev.a, ABREVIATURA: ev.ab, EVALUACION: ev.e,
            CONTENIDO: ev.c, PROFESOR: ev.p, NUMERO: ev.n, COEFICIENTE: ev.co,
            PONDERACION: ev.po, TIPO: ev.t, DIA: diaDe(ev.f),
            _k: ev.k, _filas: []};
  }

  function aCorto(reg) {
    return {k: reg._k, f: reg.FECHA, a: reg.ASIGNATURA, ab: reg.ABREVIATURA,
            e: reg.EVALUACION, c: reg.CONTENIDO, p: reg.PROFESOR, n: reg.NUMERO,
            co: reg.COEFICIENTE, po: reg.PONDERACION, t: reg.TIPO,
            filas: reg._filas || []};
  }

  function ordenClave(r) {
    return [r.FECHA || '9999-99-99', r.ASIGNATURA || '',
            String(r.NUMERO || '').split(/[.\-]/).map(function (p) {
              return /^\d+$/.test(p) ? Number(p) : 999;
            })];
  }

  function compararNum(a, b) {
    for (var i = 0; i < Math.max(a.length, b.length); i++) {
      var x = a[i] === undefined ? -1 : a[i];
      var y = b[i] === undefined ? -1 : b[i];
      if (x !== y) return x < y ? -1 : 1;
    }
    return 0;
  }

  function comparar(x, y) {
    var a = ordenClave(x), b = ordenClave(y);
    if (a[0] !== b[0]) return a[0] < b[0] ? -1 : 1;
    if (a[1] !== b[1]) return a[1] < b[1] ? -1 : 1;
    return compararNum(a[2], b[2]);
  }

  // Aplica las filas de la nube sobre una lista de registros «largos».
  function aplicarFilas(registros, filas, soloSemana) {
    var canceladas = {};
    filas.forEach(function (f) { if (f.anula) canceladas[String(f.anula)] = true; });
    var activas = filas.filter(function (f) {
      return f.id && !canceladas[String(f.id)] && !f.anula &&
             (f.tipo === 'correccion' || f.tipo === 'nuevo');
    }).sort(function (a, b) {
      var x = String(a.creado || ''), y = String(b.creado || '');
      return x < y ? -1 : x > y ? 1 : 0;
    });

    var indice = {}, conteo = {};
    registros.forEach(function (r) {
      if (r._k) indice[r._k] = r;
      var b = claveBase(r);
      conteo[b] = (conteo[b] || 0) + 1;
    });

    var extra = [], nuevos = {};
    var est = {corregidas:0, agregadas:0, caducas:0, sin_destino:0, avisos:[]};

    activas.forEach(function (fila) {
      var clave = String(fila.clave || '').trim();
      if ((clave.indexOf('SEMANA|') === 0) !== !!soloSemana) return;
      var campos = validarCampos(fila.campos);

      if (fila.tipo === 'correccion') {
        var destino = indice[clave];
        if (!destino) {
          est.sin_destino++;
          est.avisos.push('corrección sin destino: ' + clave);
          return;
        }
        if (!Object.keys(campos).length) {
          est.sin_destino++;
          est.avisos.push('corrección vacía: ' + clave);
          return;
        }
        var previo = (fila.previo && typeof fila.previo === 'object') ? fila.previo : {};
        var aplicados = 0, coinciden = 0, total = 0, fechaOk = false;
        for (var nombre in campos) {
          total++;
          var valor = campos[nombre];
          var actual = String(destino[nombre] || '');
          if (valor === actual) { coinciden++; continue; }
          if (nombre in previo && String(previo[nombre] || '') !== actual) {
            est.caducas++;
            est.avisos.push('caducada ' + clave + ': ' + nombre
                            + ' en la página ya no coincide');
            continue;
          }
          destino[nombre] = valor;
          aplicados++;
          if (nombre === 'FECHA') fechaOk = true;
        }
        if (aplicados) {
          est.corregidas++;
          if (fechaOk) destino.DIA = diaDe(destino.FECHA);
        }
        if (aplicados || (total && coinciden === total)) {
          destino._filas = (destino._filas || []).concat(
            {id: fila.id, autor: String(fila.autor || '')});
        }
        return;
      }

      // alta de un evento nuevo (o de un resumen, que la nube sólo corrige)
      var reg = registroNuevo(fila.campos);
      if (!clave || !reg) {
        est.sin_destino++;
        est.avisos.push('alta inválida: ' + (clave || '(sin clave)'));
        return;
      }
      var bk = claveBase(reg);
      var repetida = Object.keys(indice).some(function (k) {
        var r = indice[k];
        return claveBase(r) === bk && String(r.FECHA || '') === reg.FECHA &&
               String(r.EVALUACION || '').trim() === reg.EVALUACION;
      });
      if (repetida) {
        est.sin_destino++;
        est.avisos.push('alta repetida: ' + bk + ' el ' + reg.FECHA);
        return;
      }
      nuevos[bk] = (nuevos[bk] || 0) + 1;
      var k = bk + '#' + ((conteo[bk] || 0) + nuevos[bk]);
      reg._k = k;
      reg._filas = [{id: fila.id, autor: String(fila.autor || '')}];
      indice[k] = reg;
      extra.push(reg);
      est.agregadas++;
    });

    return registros.concat(extra);
  }

  // ------------------------------------------------------------------
  // Resúmenes del sábado (espejo de edufacil/semana.py)
  // ------------------------------------------------------------------
  function etiquetaFechas(fechas) {
    var mismoMes = fechas.every(function (f) { return f.slice(5, 7) === fechas[0].slice(5, 7); });
    var partes = fechas.map(function (f) {
      var dia = String(Number(f.slice(8, 10)));
      return mismoMes ? dia : dia + ' ' + MESES_CORTOS[Number(f.slice(5, 7))];
    });
    var texto = partes.length === 1 ? partes[0]
              : partes.slice(0, -1).join(', ') + ' y ' + partes[partes.length - 1];
    return mismoMes ? texto + ' ' + MESES_CORTOS[Number(fechas[0].slice(5, 7))] : texto;
  }

  function filaResumen(fecha, r) {
    // un item, un salto: cada dato en su propia línea
    var lineas = [DIAS_CORTOS[(fecha.getDay() + 6) % 7] + ' ' + fecha.getDate()
                + ' ' + MESES_CORTOS[fecha.getMonth() + 1]];
    var asignatura = String(r.ASIGNATURA || '').trim();
    if (asignatura) lineas.push(asignatura);
    var evaluacion = String(r.EVALUACION || '').trim();
    var numero = String(r.NUMERO || '').trim();
    if (evaluacion) lineas.push(numero ? evaluacion + ' (N° ' + numero + ')'
                                       : evaluacion);
    var profesor = String(r.PROFESOR || '').trim();
    if (profesor) lineas.push('Prof. ' + profesor);
    var tipo = String(r.TIPO || '').trim();
    if (tipo) lineas.push(tipo);
    var coef = String(r.COEFICIENTE || '').trim();
    if (coef) lineas.push('coef. ' + coef);
    var po = String(r.PONDERACION || '').trim();
    if (po) lineas.push(/%$/.test(po) ? 'ponderación ' + po
                                      : 'ponderación ' + po + '%');
    return lineas.join('\n');
  }

  function resumenesDesde(registros) {
    var grupos = {}, orden = [];
    registros.forEach(function (r) {
      if (r.TIPO === TIPO_RESUMEN) return;
      if (!fechaValida(String(r.FECHA || ''))) return;
      var f = new Date(r.FECHA + 'T00:00:00');
      if (f.getDay() === 0 || f.getDay() === 6) return;   // sólo lunes a viernes
      var lunes = new Date(f);
      lunes.setDate(f.getDate() - ((f.getDay() + 6) % 7));
      var sab = new Date(lunes);
      sab.setDate(lunes.getDate() - 2);
      var k = iso(sab);
      if (!grupos[k]) { grupos[k] = []; orden.push(k); }
      grupos[k].push([f, r]);
    });

    return orden.sort().map(function (k) {
      var filas = grupos[k].slice().sort(function (x, y) {
        var a = [iso(x[0]), String(x[1].ASIGNATURA || ''), String(x[1].NUMERO || '')];
        var b = [iso(y[0]), String(y[1].ASIGNATURA || ''), String(y[1].NUMERO || '')];
        return a[0] !== b[0] ? (a[0] < b[0] ? -1 : 1)
             : a[1] !== b[1] ? (a[1] < b[1] ? -1 : 1)
             : (a[2] < b[2] ? -1 : a[2] > b[2] ? 1 : 0);
      });
      var fechas = [];
      filas.forEach(function (p) {
        var s = iso(p[0]);
        if (fechas.indexOf(s) < 0) fechas.push(s);
      });
      var plural = filas.length === 1 ? 'evaluación' : 'evaluaciones';
      return {
        FECHA: k, DIA: 'Sábado', ASIGNATURA: '📚 Resumen de la semana',
        ABREVIATURA: 'SEMANA',
        EVALUACION: etiquetaFechas(fechas) + ' · ' + filas.length + ' ' + plural,
        CONTENIDO: filas.map(function (p) { return filaResumen(p[0], p[1]); })
                        .join('\n\n'),
        PROFESOR: '', NUMERO: '', COEFICIENTE: '', PONDERACION: '',
        TIPO: TIPO_RESUMEN, _k: 'SEMANA|' + k + '#1', _filas: []
      };
    });
  }

  function coloresDe(eventos) {
    var vistos = {};
    eventos.forEach(function (ev) { if (ev.a) vistos[ev.a] = true; });
    var paleta = D.paleta || [];
    var salida = {};
    Object.keys(vistos).sort().forEach(function (a, i) {
      salida[a] = (D.colores && D.colores[a]) ||
                  (paleta.length ? paleta[i % paleta.length] : '#9ca3af');
    });
    return salida;
  }

  // Base embebida + filas de la nube -> lo que se pinta
  function reconstruir() {
    var largos = eventosBase.map(aLargo);
    largos = aplicarFilas(largos, filasNube, false);
    largos.sort(comparar);
    var resumenes = aplicarFilas(resumenesDesde(largos), filasNube, true);

    var eventos = largos.map(aCorto);
    colores = coloresDe(eventos);
    D.colores = colores;

    porDia = {};
    eventos.forEach(function (ev) { (porDia[ev.f] = porDia[ev.f] || []).push(ev); });
    resumenDia = {};
    resumenes.map(aCorto).forEach(function (r) { resumenDia[r.f] = r; });

    var fechas = Object.keys(porDia).concat(Object.keys(resumenDia)).sort();
    if (fechas.length) { D.desde = fechas[0]; D.hasta = fechas[fechas.length - 1]; }
  }

  function iso(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0')
         + '-' + String(d.getDate()).padStart(2, '0');
  }

  var hoy = iso(new Date());
  var dentro = hoy >= D.desde && hoy <= D.hasta;
  var inicial = dentro ? hoy : D.desde;
  var partes = inicial.split('-');
  var anio = Number(partes[0]);
  var mes = Number(partes[1]) - 1;
  var elegida = inicial;

  function pintarMes() {
    document.getElementById('mes-actual').textContent = MESES[mes] + ' ' + anio;
    var rejilla = document.getElementById('rejilla');
    rejilla.innerHTML = '';
    var primero = new Date(anio, mes, 1).getDay();
    var offset = (primero + 6) % 7;                 // lunes = 0
    var dias = new Date(anio, mes + 1, 0).getDate();
    var total = Math.ceil((offset + dias) / 7) * 7;

    for (var i = 0; i < total; i++) {
      var dia = i - offset + 1;
      var celda = document.createElement('div');
      if (dia < 1 || dia > dias) {
        celda.className = 'celda vacio';
        rejilla.appendChild(celda);
        continue;
      }
      var fecha = anio + '-' + String(mes + 1).padStart(2, '0')
                + '-' + String(dia).padStart(2, '0');
      var dow = new Date(anio, mes, dia).getDay();
      celda.className = 'celda'
        + (dow === 6 ? ' sabado' : '')
        + (dow === 0 ? ' domingo' : '')
        + (fecha === hoy ? ' hoy' : '')
        + (fecha === elegida ? ' elegida' : '');
      celda.dataset.fecha = fecha;

      var num = document.createElement('div');
      num.className = 'numero';
      num.textContent = dia;
      celda.appendChild(num);

      var lista = porDia[fecha] || [];
      var resumen = resumenDia[fecha];
      if (resumen) {
        var chip = document.createElement('div');
        chip.className = 'ev resumen';
        chip.title = resumen.e;
        chip.textContent = '\u{1F4DA} ' + resumen.e;
        celda.appendChild(chip);
      }
      lista.slice(0, 4).forEach(function (ev) {
        var el = document.createElement('div');
        el.className = 'ev';
        el.style.setProperty('--c', D.colores[ev.a] || '#9ca3af');
        el.title = ev.a + ' — ' + ev.e + (ev.p ? ' · ' + ev.p : '');
        var b = document.createElement('b');
        b.textContent = ev.ab + (ev.n ? ' ' + ev.n : '');
        el.appendChild(b);
        celda.appendChild(el);
      });
      var resto = lista.length - 4;
      if (resto > 0) {
        var mas = document.createElement('div');
        mas.className = 'mas';
        mas.textContent = '+' + resto + ' más';
        celda.appendChild(mas);
      }

      celda.addEventListener('click', function (ev2) {
        elegida = ev2.currentTarget.dataset.fecha;
        pintarMes();
        pintarDetalle();
        // En teléfono el detalle queda bajo el calendario: acérquelo a la vista.
        if (typeof window.matchMedia === 'function'
            && window.matchMedia('(max-width: 640px)').matches) {
          var det = document.getElementById('detalle');
          if (det && typeof det.scrollIntoView === 'function') {
            det.scrollIntoView({behavior: 'smooth', block: 'start'});
          }
        }
      });
      rejilla.appendChild(celda);
    }
  }

  function pintarDetalle() {
    var caja = document.getElementById('detalle');
    var p = elegida.split('-');
    var fecha = new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2]));
    caja.innerHTML = '<h2>' + DIAS[fecha.getDay()] + ' ' + fecha.getDate()
      + ' de ' + MESES[fecha.getMonth()].toLowerCase()
      + '</h2><div class="cuando">' + elegida + '</div>';

    var lista = porDia[elegida] || [];
    if (!lista.length) {
      var vacio = document.createElement('div');
      vacio.className = 'vacio-detalle';
      vacio.textContent = 'Sin evaluaciones este día.';
      caja.appendChild(vacio);
    }

    // Todo se llena con textContent: nunca se inyecta HTML del sitio.
    lista.forEach(function (ev) {
      var bloque = document.createElement('div');
      bloque.className = 'item';
      bloque.style.setProperty('--c', D.colores[ev.a] || '#111827');

      var asig = document.createElement('div');
      asig.className = 'asig';
      asig.textContent = ev.a;

      var tit = document.createElement('div');
      tit.className = 'tit';
      tit.textContent = ev.e + (ev.n ? ' (N° ' + ev.n + ')' : '');

      var meta = document.createElement('div');
      meta.className = 'meta';
      // un item, un salto: igual que en el resumen del sábado
      var partes = [];
      if (ev.p) partes.push('Prof. ' + ev.p);
      if (ev.t) partes.push(ev.t);
      if (ev.co) partes.push('coef. ' + ev.co);
      if (ev.po) partes.push(/%$/.test(ev.po) ? 'ponderación ' + ev.po
                                              : 'ponderación ' + ev.po + '%');
      meta.textContent = partes.join('\n');

      bloque.appendChild(asig);
      bloque.appendChild(tit);
      bloque.appendChild(meta);
      if (ev.c) {
        var cont = document.createElement('div');
        cont.className = 'meta';
        cont.textContent = ev.c;
        bloque.appendChild(cont);
      }
      if (NUBE) bloque.appendChild(barraAcciones(ev, ev.e));
      caja.appendChild(bloque);
    });

    var resumen = resumenDia[elegida];
    if (resumen) {
      var caja2 = document.createElement('div');
      caja2.className = 'caja-resumen';
      var fuerte = document.createElement('strong');
      fuerte.textContent = '\u{1F4DA} ' + resumen.e;
      caja2.appendChild(fuerte);
      var pre = document.createElement('pre');
      pre.textContent = resumen.c || '';
      caja2.appendChild(pre);
      if (NUBE) caja2.appendChild(barraAcciones(resumen, resumen.e));
      caja.appendChild(caja2);
    }
  }

  // Corrección, alta y deshacer se hacen desde acá.
  function barraAcciones(reg, titulo) {
    var barra = document.createElement('div');
    barra.className = 'acciones-item';
    var ultima = (reg.filas && reg.filas.length)
               ? reg.filas[reg.filas.length - 1] : null;

    if (ultima) {
      var chip = document.createElement('span');
      chip.className = 'corregido';
      chip.textContent = '✎ corregido por ' + (ultima.autor || 'alguien');
      barra.appendChild(chip);

      var deshacer = document.createElement('button');
      deshacer.className = 'mini';
      deshacer.textContent = '✕ deshacer';
      deshacer.title = 'Quita esta corrección: se agrega un registro anulado, '
                     + 'nada se borra de la bitácora.';
      deshacer.addEventListener('click', function () { deshacerFila(reg, ultima); });
      barra.appendChild(deshacer);
    }

    var editar = document.createElement('button');
    editar.className = 'mini';
    editar.textContent = reg.t === TIPO_RESUMEN ? '✎ Editar resumen' : '✎ Editar';
    editar.title = 'Corregir «' + titulo + '» (lo ven todos)';
    editar.addEventListener('click', function () {
      abrir(reg.t === TIPO_RESUMEN ? 'resumen' : 'correccion', reg);
    });
    barra.appendChild(editar);
    return barra;
  }

  function pintarLeyenda() {
    var leyenda = document.getElementById('leyenda');
    leyenda.innerHTML = '';
    Object.keys(D.colores).sort().forEach(function (asig) {
      var span = document.createElement('span');
      span.className = 'punto';
      var i = document.createElement('i');
      i.style.background = D.colores[asig];
      span.appendChild(i);
      span.appendChild(document.createTextNode(asig));
      leyenda.appendChild(span);
    });
  }

  document.getElementById('anterior').addEventListener('click', function () {
    mes--; if (mes < 0) { mes = 11; anio--; } pintarMes();
  });
  document.getElementById('siguiente').addEventListener('click', function () {
    mes++; if (mes > 11) { mes = 0; anio++; } pintarMes();
  });
  document.getElementById('hoy').addEventListener('click', function () {
    var base = (hoy >= D.desde && hoy <= D.hasta) ? hoy : D.desde;
    var p = base.split('-');
    anio = Number(p[0]); mes = Number(p[1]) - 1; elegida = base;
    pintarMes(); pintarDetalle();
  });
  document.getElementById('imprimir').addEventListener('click', function () {
    window.print();
  });
  document.getElementById('descargar').addEventListener('click', function () {
    var b64 = document.getElementById('ics-b64').textContent.trim();
    var bin = atob(b64);
    var bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) { bytes[i] = bin.charCodeAt(i); }
    var url = URL.createObjectURL(
      new Blob([bytes], { type: 'text/calendar;charset=utf-8' }));
    var a = document.createElement('a');
    a.href = url;
    a.download = 'Evaluacion Scuola.ics';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
  });

  // ------------------------------------------------------------------
  // Correcciones: leer la nube, guardar y deshacer
  // ------------------------------------------------------------------
  function repintar() {
    pintarMes();
    pintarDetalle();
    pintarLeyenda();
  }

  function almacenar(clave, valor) {
    try {
      var ls = (typeof window !== 'undefined') ? window.localStorage : null;
      if (!ls) return null;
      if (valor === undefined) return ls.getItem(clave);
      ls.setItem(clave, valor);
    } catch (e) { /* sin almacenamiento local */ }
    return null;
  }

  function token() {
    var t = almacenar('edufacil-token');
    if (!t) {
      t = 'anon-' + Math.random().toString(36).slice(2, 10)
        + Date.now().toString(36);
      almacenar('edufacil-token', t);
    }
    return t;
  }

  function nombreAutor() {
    var campo = document.getElementById('m-autor');
    var valor = campo && campo.value ? String(campo.value).trim() : '';
    return valor || almacenar('edufacil-autor') || '';
  }

  function estado(texto, clase) {
    var el = document.getElementById('nube-estado');
    if (!el) return;
    el.textContent = texto || '';
    el.className = 'nube' + (clase ? ' ' + clase : '');
  }

  function contarFilas() {
    var anuladas = {};
    filasNube.forEach(function (f) { if (f.anula) anuladas[String(f.anula)] = true; });
    return filasNube.filter(function (f) {
      return f.id && !anuladas[String(f.id)] && !f.anula &&
             (f.tipo === 'correccion' || f.tipo === 'nuevo');
    }).length;
  }

  function encabezado(extra) {
    var h = {'apikey': NUBE.key, 'Authorization': 'Bearer ' + NUBE.key,
             'Accept': 'application/json'};
    if (extra) Object.keys(extra).forEach(function (k) { h[k] = extra[k]; });
    return h;
  }

  function enviar(fila) {
    return fetch(NUBE.url + '/rest/v1/' + NUBE.tabla, {
      method: 'POST',
      headers: encabezado({'Content-Type': 'application/json',
                           'Prefer': 'return=representation'}),
      body: JSON.stringify(fila)
    }).then(function (r) {
      return r.text().then(function (t) {
        if (!r.ok) throw new Error(String(t).slice(0, 200) || ('HTTP ' + r.status));
        try { return JSON.parse(t || '[]'); } catch (e) { return []; }
      });
    });
  }

  function cargarFilas() {
    if (!NUBE) { estado('solo lectura'); return Promise.resolve(false); }
    if (typeof fetch !== 'function') {
      estado('sin conexión', 'mal');
      return Promise.resolve(false);
    }
    estado('conectando…');
    return fetch(NUBE.url + '/rest/v1/' + NUBE.tabla + '?select=*&order=creado.asc',
                 {headers: encabezado()})
      .then(function (r) {
        if (r.status === 404) throw new Error('falta el SQL en Supabase');
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (filas) {
        filasNube = Array.isArray(filas) ? filas : [];
        reconstruir();
        repintar();
        var n = contarFilas();
        estado(n + (n === 1 ? ' corrección' : ' correcciones'), 'ok');
        return true;
      })
      .catch(function (err) {
        estado('sin conexión (' + String(err.message || err).slice(0, 42) + ')', 'mal');
        return false;
      });
  }

  // Si la corrección venía ya embebida en la base (se hizo antes de las 07:00),
  // al deshacerla hay que devolver la base a su valor anterior para que se vea
  // ya; la fila anulada se encarga del resto a partir de mañana.
  function revertirBase(k, fila) {
    if (!fila || fila.tipo !== 'correccion') return;
    var base = null;
    eventosBase.forEach(function (ev) { if (ev.k === k) base = ev; });
    if (!base) return;
    UI.forEach(function (u) {
      if (!(u.c in (fila.campos || {})) || !(u.c in (fila.previo || {}))) return;
      if (String(base[u.s] || '') !== String(fila.campos[u.c] || '')) return;
      base[u.s] = String(fila.previo[u.c] || '');
    });
  }

  function deshacerFila(reg, ultima) {
    if (!NUBE) return;
    var ok = true;
    if (typeof window !== 'undefined' && typeof window.confirm === 'function') {
      ok = window.confirm('¿Quitar el último cambio de «' + (reg.e || '') + '»?');
    }
    if (!ok) return;
    var previa = null;
    filasNube.forEach(function (f) { if (f.id === ultima.id) previa = f; });
    var envio = {tipo: 'anula', clave: reg.k || '', anula: ultima.id,
                 campos: {}, previo: {}, autor: nombreAutor() || 'alguien',
                 token: token()};
    enviar(envio).then(function (filas) {
      revertirBase(reg.k, previa);
      filasNube = filasNube.concat(filas);
      reconstruir();
      repintar();
      var n = contarFilas();
      estado(n + (n === 1 ? ' corrección' : ' correcciones'), 'ok');
    }).catch(function (err) {
      estado('no se pudo deshacer: ' + String(err.message || err).slice(0, 40), 'mal');
    });
  }

  // ------------------------------------------------------------------
  // Modal de edición
  // ------------------------------------------------------------------
  var modo = null, origen = null;

  function camposUsados() {
    return modo === 'resumen'
      ? UI.filter(function (u) { return SOLO_RESUMEN.indexOf(u.c) >= 0; })
      : UI;
  }

  function errorModal(msg) {
    var el = document.getElementById('m-error');
    if (el) el.textContent = msg || '';
  }

  function cerrarModal() {
    var modal = document.getElementById('modal');
    if (modal) modal.hidden = true;
    modo = null;
    origen = null;
    errorModal('');
  }

  function abrir(modoNuevo, reg) {
    if (!NUBE) return;
    var cont = document.getElementById('m-campos');
    if (!cont) return;
    modo = modoNuevo;
    origen = reg || null;
    errorModal('');

    var titulo = document.getElementById('m-titulo');
    if (titulo) {
      titulo.textContent = modo === 'nuevo' ? 'Nuevo evento'
                         : modo === 'resumen' ? 'Editar resumen del sábado'
                         : 'Corregir evaluación';
    }
    var autor = document.getElementById('m-autor');
    if (autor) autor.value = almacenar('edufacil-autor') || '';

    cont.innerHTML = '';
    camposUsados().forEach(function (u) {
      var label = document.createElement('label');
      label.className = 'campo' + (u.ancho || u.tipo === 'textarea' ? ' ancho' : '');
      var titulo2 = document.createElement('span');
      titulo2.textContent = u.et;
      label.appendChild(titulo2);

      var input;
      if (u.tipo === 'textarea') {
        input = document.createElement('textarea');
      } else if (u.tipo === 'select') {
        input = document.createElement('select');
        TIPOS.forEach(function (t) {
          var op = document.createElement('option');
          op.value = t;
          op.textContent = t;
          input.appendChild(op);
        });
      } else {
        input = document.createElement('input');
        if (u.tipo) input.type = u.tipo;
      }
      input.id = 'm-' + u.c;
      if (modo === 'nuevo' && u.c === 'FECHA') input.value = elegida;
      else if (origen) input.value = origen[u.s] || '';
      label.appendChild(input);
      cont.appendChild(label);
    });

    var modal = document.getElementById('modal');
    if (modal) modal.hidden = false;
  }

  function leerCampos() {
    var salida = {};
    camposUsados().forEach(function (u) {
      var el = document.getElementById('m-' + u.c);
      var valor = el && el.value !== undefined && el.value !== null ? el.value : '';
      salida[u.c] = String(valor).trim();
    });
    return salida;
  }

  function guardarModal() {
    if (!NUBE || (modo !== 'nuevo' && modo !== 'correccion' && modo !== 'resumen')) return;
    var autor = nombreAutor();
    if (!autor) {
      errorModal('Escribe tu nombre: queda registrado quién hizo el cambio.');
      return;
    }
    almacenar('edufacil-autor', autor);

    var valores = leerCampos();
    var fila = null;
    if (modo === 'nuevo') {
      var nuevo = registroNuevo(valores);
      if (!nuevo) {
        errorModal('Faltan datos: fecha, asignatura y nombre de la evaluación.');
        return;
      }
      fila = {tipo: 'nuevo', clave: claveBase(nuevo) + '#1',
              campos: validarCampos(valores), previo: {}, autor: autor,
              token: token()};
    } else {
      var campos = {}, previo = {};
      camposUsados().forEach(function (u) {
        var valor = valores[u.c];
        var anterior = String(origen ? (origen[u.s] || '') : '');
        if (valor !== anterior) { campos[u.c] = valor; previo[u.c] = anterior; }
      });
      if (!Object.keys(campos).length) { errorModal('No se cambió nada.'); return; }
      if ('FECHA' in campos && !fechaValida(campos.FECHA)) {
        errorModal('La fecha no es válida (aaaa-mm-dd).');
        return;
      }
      fila = {tipo: 'correccion', clave: origen.k, campos: campos, previo: previo,
              autor: autor, token: token()};
    }

    var boton = document.getElementById('m-guardar');
    if (boton) boton.disabled = true;
    errorModal('');
    enviar(fila).then(function (filas) {
      if (boton) boton.disabled = false;
      filasNube = filasNube.concat(filas);
      reconstruir();
      cerrarModal();
      repintar();
      var n = contarFilas();
      estado(n + (n === 1 ? ' corrección' : ' correcciones') + ' · guardado', 'ok');
    }).catch(function (err) {
      if (boton) boton.disabled = false;
      errorModal('No se pudo guardar: ' + String(err.message || err).slice(0, 120));
    });
  }

  // ------------------------------------------------------------------
  // Arranque
  // ------------------------------------------------------------------
  var botonNuevo = document.getElementById('nuevo');
  if (botonNuevo) {
    if (!NUBE) botonNuevo.hidden = true;
    botonNuevo.addEventListener('click', function () { abrir('nuevo', null); });
  }
  var botonCancelar = document.getElementById('m-cancelar');
  if (botonCancelar) botonCancelar.addEventListener('click', cerrarModal);
  var botonGuardar = document.getElementById('m-guardar');
  if (botonGuardar) botonGuardar.addEventListener('click', guardarModal);

  // ------------------------------------------------------------------
  // PWA: instalar como app y avisos diarios (Web Push)
  // ------------------------------------------------------------------
  var nav = (typeof navigator !== 'undefined') ? navigator : null;
  var enApp = !!(window.matchMedia &&
                 window.matchMedia('(display-mode: standalone)').matches) ||
              !!(nav && nav.standalone);
  var esIos = !!(nav && /iphone|ipad|ipod/i.test(nav.userAgent || ''));
  var pwaPrompt = null;
  var btnInstalar = document.getElementById('instalar');
  var btnAvisos = document.getElementById('avisos');

  function msgAvisos(texto) {
    var el = document.getElementById('avisos-estado');
    if (el) el.textContent = texto || '';
  }

  // el service worker deja la página en caché y recibe los avisos
  if (nav && nav.serviceWorker && nav.serviceWorker.register) {
    nav.serviceWorker.register('sw.js').catch(function () {});
  }

  if (btnInstalar && enApp) btnInstalar.hidden = true;
  if (window.addEventListener) {
    window.addEventListener('beforeinstallprompt', function (ev) {
      ev.preventDefault();            // no salta el banner: esperamos al botón
      pwaPrompt = ev;
      if (btnInstalar) btnInstalar.hidden = false;
    });
  }
  if (btnInstalar) {
    btnInstalar.addEventListener('click', function () {
      if (pwaPrompt) {
        var p = pwaPrompt;
        pwaPrompt = null;
        p.prompt();
        if (p.userChoice && p.userChoice.catch) p.userChoice.catch(function () {});
        return;
      }
      msgAvisos(esIos
        ? 'iPhone: toca Compartir → «Agregar a pantalla de inicio».'
        : 'Elige «Instalar aplicación» en el menú del navegador.');
    });
  }

  if (btnAvisos) {
    btnAvisos.hidden = !window.Notification;   // oculto si el navegador no avisa
    btnAvisos.addEventListener('click', pedirAvisos);
  }

  // Al abrir la app: si el permiso ya está dado, se comprueba la suscripción y
  // el botón sale «✓ activos» sin volver a pulsar nada; si la suscripción se
  // perdió, se reactiva sola sin pedir permiso otra vez.
  function restaurarAvisos() {
    if (!window.Notification || window.Notification.permission !== 'granted') return;
    if (!NUBE || !NUBE.vapid) return;
    if (!nav || !nav.serviceWorker || !nav.serviceWorker.register) return;
    nav.serviceWorker.register('sw.js').then(function (reg) {
      return reg.pushManager.getSubscription().then(function (existe) {
        return existe || reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: llavePublica(NUBE.vapid)
        });
      });
    }).then(function (sub) {
      if (!sub) return null;
      return guardarSuscripcion(sub).then(function () {
        msgAvisos('✓ Avisos activos: sábados y cambios.');
        if (btnAvisos) btnAvisos.disabled = true;
      });
    }).catch(function () { /* sin red u otro fallo: se queda como estaba */ });
  }
  if (btnAvisos) restaurarAvisos();

  // Prueba al instante: la misma notificación del sábado, sin esperar.
  // «Probar aviso» queda escondido a propósito: el botón existe en el HTML
  // pero jamás se muestra (el atributo hidden se conserva por si algún día
  // se quiere reactivar, sin tocar nada más).
  var btnProbar = document.getElementById('probar');
  if (btnProbar) {
    btnProbar.addEventListener('click', function () {
      if (!window.Notification) {
        msgAvisos('Este navegador no admite avisos.'); return;
      }
      if (window.Notification.permission !== 'granted') {
        msgAvisos('Primero activa «\u{1F514} Avisos» y vuelve a probar.'); return;
      }
      if (!nav || !nav.serviceWorker || !nav.serviceWorker.register) {
        msgAvisos('Este navegador no admite avisos.'); return;
      }
      var hoy = new Date();
      hoy.setHours(0, 0, 0, 0);
      var fechas = Object.keys(resumenDia).sort();
      var clave = null;
      for (var i = 0; i < fechas.length; i++) {
        if (new Date(fechas[i] + 'T00:00:00') >= hoy) { clave = fechas[i]; break; }
      }
      if (!clave && fechas.length) clave = fechas[fechas.length - 1];
      var r = clave ? resumenDia[clave] : null;
      if (!r) {
        msgAvisos('Todavía no hay resumen de sábado para probar.'); return;
      }
      msgAvisos('Enviando prueba…');
      nav.serviceWorker.register('sw.js').then(function (reg) {
        // Cerramos la prueba anterior: si queda con la misma etiqueta, el
        // sistema la reemplaza en silencio y no vuelve a salir el cartel.
        var cerrar = reg.getNotifications
          ? reg.getNotifications({ tag: 'prueba-aviso' }).then(function (v) {
              v.forEach(function (n) { n.close(); });
            })
          : Promise.resolve();
        return cerrar.then(function () {
          // título, cuerpo e icono: idénticos al aviso real del sábado
          return reg.showNotification('\u{1F4DA} Resumen del sábado: ' + r.e, {
            body: r.c || '',
            icon: './icon-192.png',
            badge: './icon-192.png',
            tag: 'prueba-aviso',
            data: { url: './' }
          });
        });
      }).then(function () {
        msgAvisos('✓ Prueba enviada: mira la notificación (igual que el sábado).');
      }).catch(function (err) {
        msgAvisos('No se pudo probar: ' +
                  String((err && err.message) || err).slice(0, 90));
      });
    });
  }

  function llavePublica(b64) {
    var s = String(b64).replace(/-/g, '+').replace(/_/g, '/');
    while (s.length % 4) s += '=';
    var bin = atob(s);
    var out = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }

  function pedirAvisos() {
    if (!window.Notification) {
      msgAvisos('Este navegador no admite avisos.'); return;
    }
    if (!NUBE || !NUBE.vapid) {
      msgAvisos('Los avisos no están configurados en esta página.'); return;
    }
    if (esIos && !enApp) {
      msgAvisos('iPhone: primero Compartir → «Agregar a pantalla de inicio» '
                + 'y vuelve a pulsar.');
      return;
    }
    if (!nav || !nav.serviceWorker || !nav.serviceWorker.register) {
      msgAvisos('Este navegador no admite avisos.'); return;
    }
    Promise.resolve(window.Notification.requestPermission()).then(function (p) {
      if (p !== 'granted') { msgAvisos('Permiso de avisos no concedido.'); return null; }
      msgAvisos('Activando…');
      return nav.serviceWorker.register('sw.js').then(function (reg) {
        return reg.pushManager.getSubscription().then(function (existe) {
          return existe || reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: llavePublica(NUBE.vapid)
          });
        });
      }).then(guardarSuscripcion).then(function () {
        msgAvisos('✓ Avisos activos: sábados y cambios.');
        if (btnAvisos) btnAvisos.disabled = true;
      });
    }).catch(function (err) {
      msgAvisos('No se pudo activar: ' +
                String((err && err.message) || err).slice(0, 90));
    });
  }

  function guardarSuscripcion(sub) {
    var json = sub.toJSON();
    var fila = {
      endpoint: json.endpoint,
      p256dh: json.keys.p256dh,
      auth: json.keys.auth,
      agente: String((nav && nav.userAgent) || '').slice(0, 200),
      token: 'anon'
    };
    var base = NUBE.url + '/rest/v1/suscripciones';
    return fetch(base + '?endpoint=eq.' + encodeURIComponent(json.endpoint) +
                 '&select=endpoint',
                 { headers: encabezado() })
      .then(function (r) { return r.json().catch(function () { return []; }); })
      .then(function (ya) {
        if (ya && ya.length) return null;         // ya estaba dada de alta
        return fetch(base, {
          method: 'POST',
          headers: encabezado({'Content-Type': 'application/json',
                               'Prefer': 'return=minimal'}),
          body: JSON.stringify(fila)
        }).then(function (r) {
          if (!r.ok && r.status !== 409) throw new Error('HTTP ' + r.status);
          return null;
        });
      });
  }

  reconstruir();
  repintar();
  if (NUBE) cargarFilas();

  // gancho para pruebas (y para mirar el estado desde la consola)
  window.__calendario = {
    datos: D,
    resumenes: function () {
      return Object.keys(resumenDia).sort().map(function (k) {
        var r = resumenDia[k];
        return {k: r.k, f: r.f, e: r.e, c: r.c};
      });
    },
    eventos: function () { return eventosBase; },
    filas: function () { return filasNube; },
    recargar: cargarFilas
  };
})();
</script>
</body>
</html>
"""


def _colores(eventos: list[dict]) -> dict[str, str]:
    """Color estable por asignatura, en orden alfabético."""
    asignaturas = sorted({str(r.get("ASIGNATURA") or "").strip()
                          for r in eventos if r.get("ASIGNATURA")})
    return {a: PALETA[i % len(PALETA)] for i, a in enumerate(asignaturas)}


def _asegurar(ruta: Path) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    return ruta


def a_html(registros: list[dict], ruta: Path,
           recordatorio_min: int | None = 1440,
           nube: ConfigNube | None = None,
           claves: list[str] | None = None,
           avisos_clave: str | None = None) -> Path:
    """Escribe `calendario.html` (autocontenido, se abre con doble clic).

    Cada evento lleva su clave de identidad ``k`` (para poder corregirlo desde
    la página) y, si viene ``nube``, la página queda conectada a Supabase para
    leer y escribir correcciones en vivo. Con ``avisos_clave`` (llave pública
    VAPID) se habilita el botón «🔔 Avisos». Junto al HTML siempre quedan
    `manifest.webmanifest`, `sw.js` y los iconos (ver `edufacil/pwa.py`).
    """
    ruta = _asegurar(ruta)

    eventos = [r for r in registros if r.get("TIPO") != TIPO_RESUMEN]
    resumenes = [r for r in registros if r.get("TIPO") == TIPO_RESUMEN]
    if claves is None:
        claves = claves_unicas(registros)
    if len(claves) != len(registros):
        claves = claves_unicas(registros)

    fechas = [str(r.get("FECHA")) for r in registros if r.get("FECHA")]
    desde, hasta = (min(fechas), max(fechas)) if fechas else ("", "")

    # Cada registro se empareja con su clave de identidad «k»: es lo que la
    # página usa para decirle a la nube cuál evento se corrigió.
    pares_eventos = [(claves[i], r) for i, r in enumerate(registros)
                     if r.get("TIPO") != TIPO_RESUMEN]
    pares_resumenes = [(claves[i], r) for i, r in enumerate(registros)
                       if r.get("TIPO") == TIPO_RESUMEN]
    colores = _colores([r for _, r in pares_eventos])
    datos = {
        "desde": desde,
        "hasta": hasta,
        "colores": colores,
        # la paleta viaja para que una asignatura agregada por la gente pueda
        # recibir color sin romper los que ya existen
        "paleta": PALETA,
        "eventos": [
            {
                "k": k,
                "f": str(r.get("FECHA") or ""),
                "a": str(r.get("ASIGNATURA") or ""),
                "ab": str(r.get("ABREVIATURA") or ""),
                "e": str(r.get("EVALUACION") or ""),
                "c": str(r.get("CONTENIDO") or ""),
                "p": str(r.get("PROFESOR") or ""),
                "n": str(r.get("NUMERO") or ""),
                "co": str(r.get("COEFICIENTE") or ""),
                "po": str(r.get("PONDERACION") or ""),
                "t": str(r.get("TIPO") or ""),
            }
            for k, r in pares_eventos
        ],
        "resumenes": [
            {
                "k": k,
                "f": str(r.get("FECHA") or ""),
                "e": str(r.get("EVALUACION") or ""),
                "c": str(r.get("CONTENIDO") or ""),
            }
            for k, r in pares_resumenes
        ],
    }
    # «</» dentro del JSON cerraría la etiqueta <script>: se escape como "<\/".
    json_texto = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    json_texto = json_texto.replace("</", "<\\/")

    nube_dict = (None if nube is None
                 else {"url": nube.url, "tabla": nube.tabla, "key": nube.clave})
    if nube_dict is not None and avisos_clave:
        nube_dict["vapid"] = str(avisos_clave)
    nube_json = json.dumps(nube_dict, ensure_ascii=False, separators=(",", ":"))

    ics = texto_ics(registros, recordatorio_min=recordatorio_min)
    ics_b64 = base64.b64encode(ics.encode("utf-8")).decode("ascii")

    rango = f"del {desde} al {hasta}" if fechas else "sin fechas"
    html = (
        _PLANTILLA
        .replace("{{DATOS}}", json_texto)
        .replace("{{ICS}}", ics_b64)
        .replace("{{NUBE}}", nube_json)
        .replace("{{RANGO}}", rango)
        .replace("{{GENERADO}}", datetime.now().strftime("%d/%m/%Y %H:%M"))
    )
    ruta.write_text(html, encoding="utf-8")
    copiar_recursos(ruta.parent)    # manifest, sw.js e iconos junto al HTML
    return ruta
