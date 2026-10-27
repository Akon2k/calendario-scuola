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

# Nombres cortos de las asignaturas oficiales. Viajan también a la plantilla
# ({{CORTOS}}) para que Python y la página reconozcan exactamente las mismas.
NOMBRES_ASIGNATURA = {
    "ARTES VISUALES": "Artes",
    "CIENCIAS NATURALES": "Ciencias",
    "EDUCACIÓN FÍSICA Y SALUD": "Ed. física",
    "HISTORIA, GEOGRAFÍA Y CIENCIAS SOCIALES": "Historia",
    "IDIOMA EXTRANJERO (INGLÉS)": "Inglés",
    "IDIOMA EXTRANJERO (ITALIANO)": "Italiano",
    "LENGUAJE Y COMUNICACIÓN": "Lenguaje",
    "MATEMÁTICA": "Matemática",
    "MÚSICA": "Música",
    "TECNOLOGÍA": "Tecnología",
}


def _canonica(asignatura: str) -> str:
    """«Matemáticas» -> «MATEMÁTICA»; un nombre desconocido queda tal cual."""
    nombre = " ".join(str(asignatura).split()).upper()
    if nombre in NOMBRES_ASIGNATURA:
        return nombre
    # Sólo se acepta el plural si el singular es una asignatura oficial: así
    # «MATEMÁTICAS» cuenta como «MATEMÁTICA», pero un nombre inventado se
    # respeta tal como lo escribió su autor.
    singular = nombre[:-1]
    if nombre.endswith("S") and singular in NOMBRES_ASIGNATURA:
        return singular
    return nombre


# Color fijo de cada asignatura oficial: el que la página viene usando. No se
# reparte por posición porque entonces basta que aparezca una asignatura nueva
# (o una variante con otro nombre) para que se corran todas las demás.
COLORES_ASIGNATURA = {
    "ARTES VISUALES": "#2563eb",
    "CIENCIAS NATURALES": "#dc2626",
    "EDUCACIÓN FÍSICA Y SALUD": "#059669",
    "HISTORIA, GEOGRAFÍA Y CIENCIAS SOCIALES": "#d97706",
    "IDIOMA EXTRANJERO (INGLÉS)": "#7c3aed",
    "IDIOMA EXTRANJERO (ITALIANO)": "#0891b2",
    "LENGUAJE Y COMUNICACIÓN": "#db2777",
    "MATEMÁTICA": "#4f46e5",
    "MÚSICA": "#ea580c",
    "TECNOLOGÍA": "#0d9488",
}

_PLANTILLA = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport"
      content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Calendario de Evaluaciones - Prima Elementare</title>
<meta name="theme-color" content="#008837">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Calendario Scuola">
<script id="tema-fouc">
  (function () {
    // El modo lo manda el teléfono: se lee en cada carga. Si una versión
    // anterior guardó una elección manual, se descarta.
    var oscuro = false;
    try {
      var ls = (typeof window !== 'undefined' && window.localStorage) ? window.localStorage : null;
      if (ls) ls.removeItem('edufacil-tema');
      oscuro = !!(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
    } catch (e) {}
    if (oscuro) {
      document.documentElement.setAttribute('data-tema', 'oscuro');
      var m = document.querySelector('meta[name="theme-color"]');
      if (m) m.setAttribute('content', '#0f172a');
    } else {
      document.documentElement.setAttribute('data-tema', 'claro');
    }
  })();
</script>
<style>
  :root {
    --borde: #e5e7eb;
    --texto: #111827;
    --texto-secundario: #374151;
    --suave: #6b7280;
    --verde: #008837;
    --verde-hover: #006b2b;
    --rojo: #cd212a;
    --fondo: #f3f4f6;
    --tarjeta: #ffffff;
    --tarjeta-secundaria: #f9fafb;
    --hora-color: #006b2b;
    --dia-pronostico-fondo: #f9fafb;
    --boton-fondo: #ffffff;
    --boton-borde: #b7d8bf;
    --boton-texto: #006b2b;
    --boton-hover: #eef8f0;
    --boton-hover-borde: #9acfa9;
    --celda-vacio: #fafafa;
    --celda-borde-vacio: #f1f1f1;
    --celda-finsem: #f9fafb;
    --celda-hover-borde: #9acfa9;
    --celda-elegida: #eef8f0;
    --celda-elegida-borde: #9acfa9;
    --ev-fondo: #ffffff;
    --ev-sombra: rgba(0, 0, 0, .05);
    --resumen-borde-color: #7c3aed;
    --resumen-chip-fondo: #f5f3ff;
    --resumen-chip-texto: #5b21b6;
    --resumen-caja-fondo: #f5f3ff;
    --resumen-caja-borde: #ddd6fe;
    --resumen-caja-texto: #4c1d95;
    --resumen-caja-titulo: #5b21b6;
    --resumen-caja-pre: #4c1d95;
    --pestana-activa-fondo: #eef8f0;
    --pestana-activa-borde: #9acfa9;
    --pestana-activa-texto: #006b2b;
    --pestana-activa-hover: #def0e3;
    --chip-cuenta-fondo: #def0e3;
    --chip-cuenta-texto: #006b2b;
    --mes-cabecera-hover: #eef8f0;
    --verde-texto: #006b2b;
    --alerta-accion-fondo: #fffbeb;
    --alerta-accion-borde: #fde68a;
    --alerta-accion-texto: #92400e;
    --alerta-evento-texto: #1e40af;
    --modal-overlay: rgba(17, 24, 39, .45);
    --input-fondo: #ffffff;
    --corregido-fondo: #ecfdf5;
    --corregido-borde: #a7f3d0;
    --corregido-texto: #0f766e;
    color-scheme: light;
  }

  [data-tema="oscuro"] {
    --borde: #334155;
    --texto: #f1f5f9;
    --texto-secundario: #cbd5e1;
    --suave: #94a3b8;
    --verde: #059669;
    --verde-hover: #047857;
    --rojo: #ef4444;
    --fondo: #0f172a;
    --tarjeta: #1e293b;
    --tarjeta-secundaria: #182234;
    --hora-color: #34d399;
    --dia-pronostico-fondo: #182234;
    --boton-fondo: #1e293b;
    --boton-borde: #334155;
    --boton-texto: #34d399;
    --boton-hover: #28374d;
    --boton-hover-borde: #475569;
    --celda-vacio: #141d2e;
    --celda-borde-vacio: #1e293b;
    --celda-finsem: #162032;
    --celda-hover-borde: #34d399;
    --celda-elegida: #064e3b;
    --celda-elegida-borde: #059669;
    --ev-fondo: #28374d;
    --ev-sombra: rgba(0, 0, 0, .4);
    --resumen-borde-color: #a78bfa;
    --resumen-chip-fondo: #3b1b68;
    --resumen-chip-texto: #ddd6fe;
    --resumen-caja-fondo: #271442;
    --resumen-caja-borde: #5b21b6;
    --resumen-caja-texto: #e9d5ff;
    --resumen-caja-titulo: #d8b4fe;
    --resumen-caja-pre: #e9d5ff;
    --pestana-activa-fondo: #064e3b;
    --pestana-activa-borde: #059669;
    --pestana-activa-texto: #6ee7b7;
    --pestana-activa-hover: #047857;
    --chip-cuenta-fondo: #064e3b;
    --chip-cuenta-texto: #6ee7b7;
    --mes-cabecera-hover: #1a3028;
    --verde-texto: #34d399;
    --alerta-accion-fondo: #451a03;
    --alerta-accion-borde: #78350f;
    --alerta-accion-texto: #fde68a;
    --alerta-evento-texto: #93c5fd;
    --modal-overlay: rgba(0, 0, 0, .75);
    --input-fondo: #0f172a;
    --corregido-fondo: #064e3b;
    --corregido-borde: #059669;
    --corregido-texto: #6ee7b7;
    color-scheme: dark;
  }

  @media (prefers-color-scheme: dark) {
    :root:not([data-tema="claro"]) {
      --borde: #334155;
      --texto: #f1f5f9;
      --texto-secundario: #cbd5e1;
      --suave: #94a3b8;
      --verde: #059669;
      --verde-hover: #047857;
      --rojo: #ef4444;
      --fondo: #0f172a;
      --tarjeta: #1e293b;
      --tarjeta-secundaria: #182234;
      --hora-color: #34d399;
      --dia-pronostico-fondo: #182234;
      --boton-fondo: #1e293b;
      --boton-borde: #334155;
      --boton-texto: #34d399;
      --boton-hover: #28374d;
      --boton-hover-borde: #475569;
      --celda-vacio: #141d2e;
      --celda-borde-vacio: #1e293b;
      --celda-finsem: #162032;
      --celda-hover-borde: #34d399;
      --celda-elegida: #064e3b;
      --celda-elegida-borde: #059669;
      --ev-fondo: #28374d;
      --ev-sombra: rgba(0, 0, 0, .4);
      --resumen-borde-color: #a78bfa;
      --resumen-chip-fondo: #3b1b68;
      --resumen-chip-texto: #ddd6fe;
      --resumen-caja-fondo: #271442;
      --resumen-caja-borde: #5b21b6;
      --resumen-caja-texto: #e9d5ff;
      --resumen-caja-titulo: #d8b4fe;
      --resumen-caja-pre: #e9d5ff;
      --pestana-activa-fondo: #064e3b;
      --pestana-activa-borde: #059669;
      --pestana-activa-texto: #6ee7b7;
      --pestana-activa-hover: #047857;
      --chip-cuenta-fondo: #064e3b;
      --chip-cuenta-texto: #6ee7b7;
      --mes-cabecera-hover: #1a3028;
      --verde-texto: #34d399;
      --alerta-accion-fondo: #451a03;
      --alerta-accion-borde: #78350f;
      --alerta-accion-texto: #fde68a;
      --alerta-evento-texto: #93c5fd;
      --modal-overlay: rgba(0, 0, 0, .75);
      --input-fondo: #0f172a;
      --corregido-fondo: #064e3b;
      --corregido-borde: #059669;
      --corregido-texto: #6ee7b7;
      color-scheme: dark;
    }
  }

  * { box-sizing: border-box; }
  body {
    margin: 0;
    padding: 0 max(16px, env(safe-area-inset-right)) 40px
             max(16px, env(safe-area-inset-left));
    font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    color: var(--texto); background: var(--fondo);
    -webkit-text-size-adjust: 100%;
  }
  header {
    max-width: 1180px; margin: 0 auto; padding: 22px 0 14px;
    display: flex; flex-wrap: wrap; gap: 14px;
    align-items: center; justify-content: space-between;
  }
  h1 { margin: 0; font-size: 22px; letter-spacing: -.02em; }
  .marca { display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1; }
  .marca .logo { width: 76px; height: 55px; object-fit: contain;
                 border-radius: 8px; flex-shrink: 0; background: #fff; padding: 2px; }
  .identidad { min-width: 0; }
  .sub { margin: 4px 0 0; color: var(--suave); font-size: 13px; }
  .sub span { display: inline-block; }
  .acciones { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; flex-basis: 100%; }
  #clima {
    flex: 0 1 auto; align-self: flex-start; padding: 6px 10px;
    display: grid; grid-template-columns: auto minmax(85px, auto) minmax(0, 1fr);
    column-gap: 8px; align-items: center;
    text-align: center; background: var(--tarjeta); border: 1px solid var(--borde);
    border-radius: 10px; line-height: 1.25;
  }
  #clima-pronostico {
    grid-column: 3; grid-row: 1 / 3; display: grid; grid-template-columns: repeat(3, 1fr);
    gap: 4px; margin: 0; padding: 0 0 0 8px; border-left: 1px solid var(--borde);
    text-align: center; align-items: stretch; height: 100%;
  }
  #clima-pronostico:empty { display: none; }
  .dia-pronostico {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 1px; padding: 3px 4px; border-radius: 6px; background: var(--dia-pronostico-fondo); min-width: 0;
  }
  .dia-pronostico .dia-nombre { font-weight: 600; color: var(--suave); font-size: 10px; line-height: 1.1; }
  .dia-pronostico .dia-icono {
    font-size: 14px; line-height: 1.1; margin: 1px 0;
    font-family: "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", "Segoe UI Symbol", "Android Emoji", emoji, sans-serif;
    display: inline-flex; align-items: center; justify-content: center;
  }
  .dia-pronostico .dia-icono svg { display: block; width: 16px; height: 16px; }
  .dia-pronostico .dia-temp { font-size: 9.5px; color: var(--texto); white-space: nowrap; line-height: 1.1; }
  #clima-icono {
    font-family: "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", "Segoe UI Symbol", "Android Emoji", emoji, sans-serif;
  }
  #clima .ciudad { display: block; font-size: 11px; color: var(--suave); }
  #clima .actual { grid-column: 2; display: block; margin: 1px 0; font-size: 16px; font-weight: 600; white-space: nowrap; color: var(--texto); }
  #clima .hora {
    grid-column: 1; grid-row: 1 / 3; display: flex; align-items: center; justify-content: center;
    margin: 0; padding: 0 8px 0 2px; border-right: 1px solid var(--borde);
    font-size: 19px; color: var(--hora-color); white-space: nowrap; font-variant-numeric: tabular-nums;
    height: 100%;
  }
  #clima .horas { font-weight: 700; color: var(--hora-color); }
  #clima .minutos { color: var(--rojo, #cd212a); font-weight: 400; }
  #clima-ubicacion {
    grid-column: 2; display: block; width: 100%; margin: 0; min-height: 24px;
    padding: 2px 4px; font-size: 10px; white-space: normal; overflow-wrap: anywhere;
  }
  button {
    font: inherit; padding: 7px 13px; border-radius: 8px;
    border: 1px solid var(--boton-borde); background: var(--boton-fondo); color: var(--boton-texto);
    cursor: pointer;
  }
  button:hover { background: var(--boton-hover); border-color: var(--boton-hover-borde); }
  button.primario { background: var(--verde); border-color: var(--verde); color: #fff; }
  button.primario:hover { background: var(--verde-hover); }
  button:focus-visible { outline: 2px solid var(--verde); outline-offset: 2px; }
  button:disabled { cursor: wait; opacity: .7; }
  #tema { font-size: 15px; padding: 7px 11px; display: inline-flex; align-items: center; justify-content: center; }
  #mes-actual { font-weight: 600; min-width: 132px; text-align: center; }
  #vistas { max-width: 1180px; margin: 12px auto 0; position: relative; }
  main {
    max-width: 1180px; margin: 0 auto;
    display: grid; grid-template-columns: 1fr 320px; gap: 16px;
    /* stretch: el cuadro del detalle baja hasta la misma altura que el
       calendario y las dos tarjetas quedan emparejadas (arriba y abajo) */
    align-items: stretch;
  }
  .tarjeta { background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 12px; }
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
    border-radius: 9px; background: var(--tarjeta); cursor: pointer; overflow: hidden;
  }
  .celda:hover { border-color: var(--celda-hover-borde); }
  .celda.vacio { background: var(--celda-vacio); border-color: var(--celda-borde-vacio); cursor: default; }
  .celda.sabado, .celda.domingo { background: var(--celda-finsem); }
  .celda.hoy { box-shadow: inset 0 0 0 2px var(--verde); }
  .celda.elegida { background: var(--celda-elegida); border-color: var(--celda-elegida-borde); }
  .numero { font-size: 13px; font-weight: 600; color: var(--suave); }
  .celda.hoy .numero { color: var(--verde); }
  .ev {
    margin-top: 4px; padding: 2px 6px; font-size: 11.5px; line-height: 1.35;
    border-left: 3px solid var(--c, #9ca3af); background: var(--ev-fondo); color: var(--texto);
    border-radius: 4px; box-shadow: 0 1px 1px var(--ev-sombra);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .ev b { font-weight: 700; }
  .ev.resumen { border-left-color: var(--resumen-borde-color); background: var(--resumen-chip-fondo); color: var(--resumen-chip-texto); }
  .mas { margin-top: 4px; font-size: 11px; color: var(--suave); }
  aside { padding: 14px; }
  aside h2 { margin: 0 0 4px; font-size: 17px; }
  aside .cuando { color: var(--suave); font-size: 13px; margin-bottom: 12px; }
  .item { padding: 10px 0; border-top: 1px solid var(--borde); }
  .item .asig { font-size: 12px; font-weight: 700; color: var(--c, var(--texto)); }
  .item .tit { font-weight: 600; }
  .item .meta { font-size: 12.5px; color: var(--suave); margin-top: 3px;
    white-space: pre-line; }
  .vacio-detalle { color: var(--suave); padding: 14px 0; }
  .caja-resumen {
    margin-top: 14px; padding: 10px 12px; border-radius: 10px;
    background: var(--resumen-caja-fondo); border: 1px solid var(--resumen-caja-borde); font-size: 13px;
  }
  .caja-resumen strong { color: var(--resumen-caja-titulo); }
  .caja-resumen pre {
    margin: 6px 0 0; white-space: pre-wrap;
    font: inherit; color: var(--resumen-caja-pre);
  }
  #leyenda {
    max-width: 1180px; margin: 12px auto 0; padding: 8px 12px;
    background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 12px;
    display: flex; flex-wrap: wrap; gap: 5px 14px; align-items: center;
    justify-content: center;
    font-size: 12px;
  }
  .punto { display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; }
  .punto i { width: 8px; height: 8px; border-radius: 3px; display: inline-block; }
  footer {
    max-width: 1180px; margin: 16px auto 0; color: var(--suave); font-size: 12.5px;
  }
  #ayuda {
    max-width: 1180px; margin: 16px auto 0; padding: 0; overflow: hidden;
    background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 12px;
    color: var(--suave); font-size: 12.5px;
  }
  #ayuda > summary {
    display: flex; align-items: center; justify-content: space-between; gap: 8px;
    padding: 10px 14px; cursor: pointer; user-select: none; list-style: none;
  }
  #ayuda > summary::-webkit-details-marker { display: none; }
  #ayuda > summary:hover { background: var(--mes-cabecera-hover); }
  #ayuda > summary:hover h2 { color: var(--verde-texto); }
  #ayuda[open] > summary { border-bottom: 1px solid var(--borde); }
  #ayuda[open] > summary .mes-flecha { transform: rotate(90deg); }
  #ayuda .ayuda-cuerpo { padding: 10px 14px 12px; }
  #ayuda h2 { margin: 0; font-size: 13.5px; color: var(--texto); }
  #ayuda ul { margin: 0; padding-left: 18px; }
  #ayuda li { margin: 3px 0; }
  #ayuda strong { color: var(--texto); }
  #ayuda h3 { margin: 10px 0 2px; font-size: 13px; color: var(--texto); }
  #ayuda .pasos { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 18px; }
  #ayuda .pasos ol { margin: 4px 0 6px; padding-left: 18px; }
  #ayuda .pasos li { margin: 2px 0; }
  #ayuda .nota { margin: 6px 0 0; }
  /* ---------- comunicados de la Scuola ---------- */
  #mensajes {
    position: absolute; inset: 0; margin: 0; padding: 10px 14px 12px;
    overflow-y: auto; scrollbar-gutter: stable; overflow-wrap: anywhere;
    background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 12px;
  }
  #mensajes h2 { margin: 0 0 6px; font-size: 13.5px; color: var(--texto); }
  .mes-grupo {
    margin-bottom: 12px; border: 1px solid var(--borde);
    border-radius: 10px; background: var(--tarjeta); overflow: hidden;
  }
  .mes-grupo:last-child { margin-bottom: 0; }
  .mes-cabecera {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 14px; background: var(--tarjeta-secundaria); font-size: 13.5px;
    font-weight: 600; color: var(--texto); cursor: pointer; user-select: none;
    list-style: none;
  }
  .mes-cabecera::-webkit-details-marker { display: none; }
  .mes-cabecera:hover { background: var(--mes-cabecera-hover); color: var(--verde-texto); }
  .mes-grupo[open] > .mes-cabecera {
    border-bottom: 1px solid var(--borde);
    background: var(--mes-cabecera-hover); color: var(--verde-texto);
  }
  .mes-titulo-wrap { display: flex; align-items: center; gap: 8px; }
  .mes-flecha {
    display: inline-block; font-size: 10px; transition: transform .2s ease;
  }
  .mes-grupo[open] .mes-flecha { transform: rotate(90deg); }
  .mes-cuenta {
    font-size: 11.5px; font-weight: 600; padding: 2px 8px;
    border-radius: 999px; background: var(--chip-cuenta-fondo); color: var(--chip-cuenta-texto);
  }
  .mes-grupo:not([open]) .mes-cuenta { background: var(--borde); color: var(--suave); }
  .mensaje { border-top: 1px solid var(--borde); padding: 10px 14px 8px; }
  .mensaje.cabecera { border-top: 0; }
  .mensaje .cab { display: flex; flex-wrap: wrap; gap: 4px 10px;
                  align-items: baseline; }
  .mensaje .asunto { font-weight: 600; font-size: 13.5px; color: var(--texto); }
  .mensaje .cuando { font-size: 12px; color: var(--suave); }
  .mensaje .puntos { margin: 5px 0 0; padding-left: 18px; font-size: 12.5px;
                     color: var(--texto-secundario); }
  .mensaje .puntos li { margin: 2px 0; }
  .mensaje .accion { margin: 6px 0 0; font-size: 12.5px; color: var(--alerta-accion-texto);
                     background: var(--alerta-accion-fondo); border: 1px solid var(--alerta-accion-borde);
                     border-radius: 8px; padding: 5px 8px; }
  .mensaje .evento { margin: 5px 0 0; font-size: 12.5px; color: var(--alerta-evento-texto); }
  /* ---------- pestañas: calendario / mensajes ---------- */
  #pestanas { max-width: 1180px; margin: 14px auto 0; display: flex; gap: 8px; }
  #pestanas button {
    flex: 1; padding: 11px 12px; font-size: 14.5px; font-weight: 600;
    border-radius: 10px; background: var(--tarjeta); color: var(--texto); border: 1px solid var(--borde);
  }
  #pestanas button.activa { background: var(--pestana-activa-fondo); border-color: var(--pestana-activa-borde);
                            color: var(--pestana-activa-texto); }
  #pestanas button.activa:hover { background: var(--pestana-activa-hover); }
  #pestanas .cuenta {
    font-size: 11.5px; font-weight: 700; margin-left: 7px;
    background: var(--chip-cuenta-fondo); color: var(--chip-cuenta-texto); border-radius: 999px; padding: 1px 8px;
  }
  #pestanas .cuenta:empty,
  #pestanas .cuenta[hidden] {
    display: none;
  }
  #pestanas button.activa .cuenta { background: var(--tarjeta); color: var(--pestana-activa-texto); }
  #pestanas .icono { width: 16px; height: 16px; vertical-align: -2px; }
  #pestanas .experimental { font-size: 11px; font-weight: 500; opacity: .7; margin-left: 4px; }
  /* El calendario reserva su tamaño: mensajes ocupa exactamente ese espacio. */
  main[hidden] { display: grid; visibility: hidden; pointer-events: none; }
  #impresion-mes, #impresion-actividades { display: none; }
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
  .corregido { font-size: 11.5px; color: var(--corregido-texto); background: var(--corregido-fondo);
               border: 1px solid var(--corregido-borde); border-radius: 999px; padding: 2px 8px; }
  button.mini { font-size: 12px; padding: 3px 9px; border-radius: 999px; }
  /* material adjunto (PDF) */
  .adjuntos { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
  .adjunto-link { display: inline-flex; align-items: center; gap: 4px; font-size: 12.5px;
                  text-decoration: none; color: var(--verde-texto); background: var(--tarjeta-secundaria);
                  border: 1px solid var(--borde); border-radius: 999px; padding: 3px 10px; }
  .adjunto-link:hover { text-decoration: underline; }
  .adjunto-caja { margin-top: 12px; border-top: 1px dashed var(--borde); padding-top: 10px; }
  .adjunto-cabecera { display: flex; align-items: baseline; justify-content: space-between;
                      gap: 8px; font-size: 13px; font-weight: 600; }
  .adjunto-nota { font-size: 11.5px; font-weight: 400; color: var(--suave); }
  .adjunto-item { display: flex; align-items: center; gap: 8px; font-size: 12.5px;
                  padding: 4px 0; color: var(--texto); }
  .adjunto-item .nombre { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .adjunto-item a { color: var(--verde-texto); }
  .adjunto-vacio { font-size: 12px; color: var(--suave); padding: 4px 0; }
  .adjunto-boton { display: inline-block; margin-top: 6px; cursor: pointer; font-size: 13px;
                   padding: 7px 12px; border-radius: 9px; border: 1px dashed var(--borde);
                   background: var(--tarjeta-secundaria); color: var(--texto); }
  .adjunto-boton:hover { border-color: var(--verde); }
  #modal {
    position: fixed; inset: 0; background: var(--modal-overlay);
    display: flex; align-items: center; justify-content: center;
    padding: 16px; z-index: 20;
  }
  #modal[hidden] { display: none; }
  .panel-modal {
    background: var(--tarjeta); color: var(--texto); border-radius: 14px; width: min(560px, 100%);
    max-height: 92vh; overflow: auto; padding: 18px; border: 1px solid var(--borde);
    box-shadow: 0 18px 50px rgba(0, 0, 0, .35);
  }
  .panel-modal h3 { margin: 0 0 12px; font-size: 17px; color: var(--texto); }
  .campo { display: block; margin: 0 0 10px; font-size: 13px; color: var(--suave); }
  .campo > span { display: block; margin-bottom: 4px; font-weight: 600; }
  .campo input, .campo textarea, .campo select {
    font: inherit; width: 100%; padding: 7px 9px; border: 1px solid var(--borde);
    border-radius: 8px; color: var(--texto); background: var(--input-fondo);
  }
  .campo textarea { min-height: 76px; resize: vertical; }
  .grid-campos { display: grid; grid-template-columns: 1fr 1fr; gap: 0 12px; }
  .grid-campos .ancho { grid-column: 1 / -1; }
  .pie-modal { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
  .modal-error { color: #b91c1c; font-size: 13px; margin: 8px 0 0; min-height: 18px; }
  /* modal específico para editar el resumen semanal */
  #modal.modal-modo-resumen .panel-modal {
    display: flex; flex-direction: column;
    height: 85vh; max-height: 85vh;
  }
  #modal.modal-modo-resumen #m-campos {
    flex: 1; display: flex; flex-direction: column;
    min-height: 0; overflow-y: auto;
  }
  #modal.modal-modo-resumen .campo-resumen-detalle {
    flex: 1; display: flex; flex-direction: column; min-height: 180px;
  }
  #modal.modal-modo-resumen .campo-resumen-detalle textarea {
    flex: 1; min-height: 160px; height: 100%; resize: none;
    font-size: 14.5px; line-height: 1.5;
  }
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
    .marca { gap: 10px; flex-basis: 100%; }
    .marca .logo { width: 60px; height: 43px; }
    #clima {
      flex: 1 1 100%; width: 100%; margin: 2px 0; padding: 5px 8px;
      grid-template-columns: auto minmax(75px, auto) minmax(0, 1fr); column-gap: 6px;
    }
    #clima .actual { font-size: 15px; }
    #clima .hora { font-size: 17px; padding: 0 6px 0 0; }
    #clima-pronostico { padding-left: 6px; gap: 3px; }
    .dia-pronostico { padding: 2px 2px; }
    .dia-pronostico .dia-nombre { font-size: 9.5px; }
    .dia-pronostico .dia-icono { font-size: 13px; }
    .dia-pronostico .dia-icono svg { width: 14px; height: 14px; }
    .dia-pronostico .dia-temp { font-size: 9px; }
    .sub { font-size: 12px; }
    .acciones { width: 100%; gap: 6px; }
    .acciones .primario {
      flex: 1 1 0; min-width: 80px; padding: 8px 6px;
      font-size: 12.5px; text-align: center; justify-content: center;
      white-space: nowrap;
    }
    .acciones .nube { flex: 1 1 100%; margin-top: 2px; }
    button {
      min-height: 40px; padding: 8px 12px;
      touch-action: manipulation;    /* sin retardo de doble toque */
    }
    #tema { font-size: 17px; min-width: 44px; }
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
    #modal.modal-modo-resumen .panel-modal {
      height: 90vh; height: 90dvh; max-height: 94vh;
      border-radius: 16px 16px 0 0;
      padding-bottom: max(16px, env(safe-area-inset-bottom));
    }
    .campo input, .campo textarea, .campo select { font-size: 16px; }
    #modal.modal-modo-resumen .campo-resumen-detalle textarea { font-size: 16px; }
    .pie-modal {
      position: sticky; bottom: 0; background: var(--tarjeta);
      margin-top: 8px; padding-top: 10px;
    }
    .pie-modal button { flex: 1; min-height: 44px; }

    #leyenda { font-size: 11.5px; padding: 8px 10px; gap: 4px 12px; margin-top: 10px; }
    #ayuda { font-size: 12px; }
    #ayuda .pasos { grid-template-columns: 1fr; }
    footer { font-size: 12px; line-height: 1.45; }
  }
  @media print {
    @page { size: A4 portrait; margin: 12mm; }
    body { background: #fff; padding: 0; font-size: 10pt; }
    header { padding: 0 0 8px; }
    h1 { font-size: 16pt; }
    .sub { font-size: 9pt; }
    .acciones, aside, #clima, #pestanas, #mensajes, #modal, #leyenda, #ayuda, footer {
      display: none !important;
    }
    #impresion-mes { display: block; margin: 4px 0 8px; font-size: 14pt; }
    #vistas { margin: 0; break-inside: avoid; }
    main, main[hidden] { display: block; visibility: visible; }
    .tarjeta { border: none; background: #fff; }
    .scroll { overflow: visible; }
    .rejilla, .dias-semana { min-width: 0; gap: 4px; padding-left: 0; padding-right: 0; }
    .celda { min-height: 62px; padding: 4px; }
    .celda.hoy { box-shadow: none; }
    .celda.elegida { background: #fff; border-color: var(--borde); }
    .numero { font-size: 9pt; }
    .ev { font-size: 7.5pt; }
    #impresion-actividades { display: block; margin-top: 16px; }
    #impresion-actividades h2 { margin: 0 0 10px; font-size: 13pt; }
    .impresion-dia h3 { margin: 10px 0 5px; font-size: 10pt; break-after: avoid; }
    .impresion-dia ul { margin: 0; padding-left: 18px; }
    .impresion-item { margin: 0 0 8px; break-inside: avoid; overflow-wrap: anywhere; }
    .impresion-item .meta { font-size: 9pt; white-space: pre-wrap; }
  }
</style>
</head>
<body>

<header>
  <div class="marca">
    <img class="logo" src="data:image/jpeg;base64,{{LOGO}}" width="152" height="109"
         alt="Logo de la Scuola Italiana">
    <div class="identidad">
      <h1>Calendario de Evaluaciones - Prima Elementare</h1>
      <p class="sub"><span>{{RANGO}}</span> <span>· generado {{GENERADO}}</span></p>
    </div>
  </div>
  <div id="clima" role="status" aria-live="polite" title="Clima actual de Concepción">
    <span class="hora" aria-live="off">
      <time id="clima-hora" title="Hora local de este dispositivo"><span id="clima-horas" class="horas">--</span>:<span id="clima-minutos" class="minutos">--</span></time></span>
    <button id="clima-ubicacion" type="button"
      title="Usar mi ubicación con permiso; Open-Meteo y BigDataCloud reciben coordenadas aproximadas">
      <span class="ciudad" id="clima-ciudad">Mi ubicación</span>
    </button>
    <span class="actual"><span id="clima-icono" aria-hidden="true">&#127777;</span>
      <span id="clima-temperatura">— °C</span></span>
    <div id="clima-pronostico" aria-label="Pronóstico para los próximos tres días"></div>
  </div>
  <div class="acciones">
    <button id="anterior" title="Mes anterior">&#8249;</button>
    <span id="mes-actual"></span>
    <button id="siguiente" title="Mes siguiente">&#8250;</button>
    <button id="hoy">Hoy</button>
    <button id="tema" type="button" title="Cambiar a modo oscuro" aria-label="Cambiar tema">🌙</button>
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

<nav id="pestanas">
  <button id="tab-calendario" class="activa"><svg class="icono" aria-hidden="true"
    viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
    stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18"
    height="16" rx="2"/><path d="M7 3v4M17 3v4M3 11h18"/></svg> Calendario</button>
  <button id="tab-mensajes" hidden><svg class="icono" aria-hidden="true"
    viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
    stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20"
    height="16" rx="2"/><path d="m22 7-10 7L2 7"/></svg> Mensajes <span class="experimental">(Experimental)</span><span class="cuenta"
    id="cuenta-mensajes"></span></button>
</nav>

<h2 id="impresion-mes"></h2>
<div id="vistas">
<main id="vista-calendario">
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

<section id="mensajes" hidden>
  <div id="mensajes-lista"></div>
</section>
</div>

<section id="impresion-actividades" aria-label="Actividades del mes para imprimir"></section>

<div id="modal" hidden>
  <div class="panel-modal">
    <h3 id="m-titulo">Editar evento</h3>
    <label class="campo ancho"><span>Tu nombre</span>
      <input id="m-autor" maxlength="60"
             placeholder="Quien corrige o agrega (queda en la bitácora)">
    </label>
    <div id="m-campos" class="grid-campos"></div>
    <div class="adjunto-caja" id="m-adjunto">
      <div class="adjunto-cabecera">
        <span>&#128206; Material de la actividad</span>
        <span class="adjunto-nota">PDF &middot; hasta 8 MB</span>
      </div>
      <div id="m-adjunto-lista"></div>
      <label class="adjunto-boton" for="m-adjunto-archivo">Elegir PDF</label>
      <input id="m-adjunto-archivo" type="file" accept="application/pdf,.pdf" hidden>
    </div>
    <p class="modal-error" id="m-error"></p>
    <div class="pie-modal">
      <button id="m-cancelar">Cancelar</button>
      <button id="m-guardar" class="primario">Guardar</button>
    </div>
  </div>
</div>

<section id="leyenda"></section>

<details id="ayuda">
  <summary>
    <h2>&#128214; Instrucciones de uso</h2>
    <span class="mes-flecha" aria-hidden="true">&#9654;</span>
  </summary>
  <div class="ayuda-cuerpo">
  <ul>
    <li><strong>Ver el calendario:</strong> cambia de mes con <em>&#8249; &#8250;</em>,
      <em>Hoy</em> vuelve al día de hoy, <em>Imprimir</em> da una copia del mes
      con sus actividades listadas debajo (sólo en la impresión).</li>
    <li><strong>Un día:</strong> toca cualquier fecha y se abren sus evaluaciones,
      cada dato en su propia línea (prueba, profesor, número, sub-número si
      la hay, y coeficiente).</li>
    <li><strong>Sábado (&#128218;):</strong> el cuadro muestra el resumen de la
      semana que viene, con una línea en blanco entre cada fecha.</li>
    <li><strong>Corregir o agregar:</strong> en cada evento están
      <em>&#9998; Editar</em> y <em>&#65291; Nuevo evento</em>: escribes tu nombre,
      eliges el campo, Guardar — y el cambio se ve al instante para todos.
      En esa misma ventana puedes <strong>adjuntar el material en PDF</strong>
      (hasta 8 MB): el enlace queda en el detalle del día.</li>
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
  </div>
</details>

<footer>
  Outlook se sincroniza solo cada mañana a las 08:00 (tarea programada),
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
  // Base embebida (trae las correcciones que había al generarse a las 08:00);
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
      // El alta pudo quedar incorporada al generar la página (el scrapeo de la
      // mañana ya la incluye). Se reconoce porque conserva la clave que se le
      // dio al crearla; volver a agregarla duplicaría el evento, y con los
      // textos sin corregir no coincidiría con la copia ya corregida.
      var yaEnDatos = indice[clave];
      if (yaEnDatos && String(yaEnDatos.FECHA || '') === String(reg.FECHA || '')) {
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

  // Espejo de edufacil/semana.py: mismo formato que la fuente.
  // El sitio trae «E3:» / «SE2-2:» delante del nombre en la lista, pero sus
  // diálogos de detalle lo muestran solo.
  var PREFIJO_NOMBRE = /^(?:E|SE)\d+(?:-\d+)?:\s*/;

  function nombreSolo(nombre) {
    return String(nombre || '').trim().replace(PREFIJO_NOMBRE, '').trim();
  }

  // «Número» y, si es sub-evaluación, «Sub-número».
  function numerosDe(numero, tipo) {
    var n = String(numero || '').trim();
    if (!n) return [];
    if (String(tipo || '').indexOf('Sub') >= 0 && n.indexOf('.') > 0) {
      var partes = n.split('.');
      return partes[1] === '' ? ['Número ' + partes[0]]
                              : ['Número ' + partes[0], 'Sub-número ' + partes[1]];
    }
    return ['Número ' + n];
  }

  function filaResumen(fecha, r) {
    // un item, un salto: cada dato en su propia línea
    var lineas = [DIAS_CORTOS[(fecha.getDay() + 6) % 7] + ' ' + fecha.getDate()
                + ' ' + MESES_CORTOS[fecha.getMonth() + 1]];
    var asignatura = String(r.ASIGNATURA || '').trim();
    if (asignatura) lineas.push(asignatura);
    var evaluacion = nombreSolo(r.EVALUACION);
    if (evaluacion) lineas.push(evaluacion);
    var profesor = String(r.PROFESOR || '').trim();
    if (profesor) lineas.push('Prof. ' + profesor);
    numerosDe(r.NUMERO, r.TIPO).forEach(function (l) { lineas.push(l); });
    var coef = String(r.COEFICIENTE || '').trim();
    if (coef) lineas.push('coef. ' + coef);
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
    // Se resuelve por nombre canónico: las variantes de una misma asignatura
    // («MATEMÁTICAS», «Matemáticas») comparten color. Una asignatura que no
    // esté en el mapa toma el primer color de la paleta que quede libre, así
    // no le roba el suyo a ninguna otra.
    var vistos = {};
    eventos.forEach(function (ev) {
      if (ev.a) vistos[nombreAsignatura(ev.a)] = true;
    });
    var paleta = D.paleta || [];
    var usados = {};
    Object.keys(D.colores || {}).forEach(function (k) { usados[D.colores[k]] = true; });
    var porNombre = {};
    Object.keys(vistos).sort().forEach(function (nombre, i) {
      var color = (D.colores && D.colores[nombre]) ||
                  paleta.filter(function (c) { return !usados[c]; })[0] ||
                  (paleta.length ? paleta[i % paleta.length] : '#9ca3af');
      porNombre[nombre] = color;
      usados[color] = true;
    });
    var salida = {};
    eventos.forEach(function (ev) {
      if (ev.a) salida[ev.a] = porNombre[nombreAsignatura(ev.a)];
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
        el.title = ev.a + ' — ' + nombreSolo(ev.e)
                 + (ev.p ? ' · ' + ev.p : '');
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
      tit.textContent = nombreSolo(ev.e);

      var meta = document.createElement('div');
      meta.className = 'meta';
      // un item, un salto: los mismos campos del detalle de la fuente
      var partes = [];
      if (ev.p) partes.push('Prof. ' + ev.p);
      numerosDe(ev.n, ev.t).forEach(function (l) { partes.push(l); });
      if (ev.co) partes.push('coef. ' + ev.co);
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
      var adjs = adjuntosDe(ev.k);
      if (adjs.length) bloque.appendChild(listaAdjuntos(adjs));
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
      var adjsResumen = adjuntosDe(resumen.k);
      if (adjsResumen.length) caja2.appendChild(listaAdjuntos(adjsResumen));
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

  // Nombres cortos de las asignaturas oficiales. Sirven además para
  // reconocerlas: quien agregue un evento desde la página puede escribir
  // «MATEMÁTICAS» o «Músicas», y eso no debe abrir una entrada nueva en la
  // leyenda ni robarle el color a la asignatura real. La lista llega desde
  // Python (NOMBRES_ASIGNATURA) para no mantener dos copias.
  var CORTOS = {{CORTOS}};

  function nombreAsignatura(asig) {
    var nombre = String(asig).trim().replace(/\s+/g, ' ').toUpperCase();
    if (CORTOS[nombre]) return nombre;
    // Sólo se acepta la forma plural si el singular es una oficial: así
    // «MATEMÁTICAS» cuenta como «MATEMÁTICA», pero un nombre desconocido
    // cualquiera se muestra tal como lo escribió su autor.
    var singular = nombre.slice(0, -1);
    return (/S$/.test(nombre) && CORTOS[singular]) ? singular : nombre;
  }

  function pintarLeyenda() {
    var leyenda = document.getElementById('leyenda');
    leyenda.innerHTML = '';
    var vistos = {};
    Object.keys(D.colores).sort().forEach(function (asig) {
      var nombre = nombreAsignatura(asig);
      if (vistos[nombre]) return;
      vistos[nombre] = true;
      var span = document.createElement('span');
      span.className = 'punto';
      span.title = asig;
      var i = document.createElement('i');
      i.style.background = D.colores[nombre] || D.colores[asig];
      span.appendChild(i);
      span.appendChild(document.createTextNode(CORTOS[nombre] || asig));
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
  function prepararImpresion() {
    var titulo = document.getElementById('impresion-mes');
    var caja = document.getElementById('impresion-actividades');
    titulo.textContent = MESES[mes] + ' ' + anio;
    caja.innerHTML = '';
    var encabezado = document.createElement('h2');
    encabezado.textContent = 'Actividades del mes';
    caja.appendChild(encabezado);
    var prefijo = anio + '-' + String(mes + 1).padStart(2, '0') + '-';
    var fechas = Object.keys(porDia).filter(function (f) {
      return f.indexOf(prefijo) === 0;
    }).sort();
    if (!fechas.length) {
      var vacio = document.createElement('p');
      vacio.textContent = 'Sin actividades registradas para este mes.';
      caja.appendChild(vacio);
    }
    fechas.forEach(function (f) {
      var dia = document.createElement('section');
      dia.className = 'impresion-dia';
      var fecha = document.createElement('h3');
      fecha.textContent = f.split('-').reverse().join('/');
      dia.appendChild(fecha);
      var lista = document.createElement('ul');
      (porDia[f] || []).forEach(function (ev) {
        var item = document.createElement('li');
        item.className = 'impresion-item';
        var nombre = document.createElement('strong');
        nombre.textContent = ev.a + ' — ' + nombreSolo(ev.e);
        item.appendChild(nombre);
        var lineas = [];
        if (ev.p) lineas.push('Prof. ' + ev.p);
        numerosDe(ev.n, ev.t).forEach(function (l) { lineas.push(l); });
        if (ev.co) lineas.push('coef. ' + ev.co);
        if (ev.c) lineas.push(ev.c);
        if (lineas.length) {
          var detalle = document.createElement('div');
          detalle.className = 'meta';
          detalle.textContent = lineas.join('\n');
          item.appendChild(detalle);
        }
        lista.appendChild(item);
      });
      dia.appendChild(lista);
      caja.appendChild(dia);
    });
  }

  function limpiarImpresion() {
    document.getElementById('impresion-mes').textContent = '';
    document.getElementById('impresion-actividades').innerHTML = '';
  }

  window.addEventListener('beforeprint', prepararImpresion);
  window.addEventListener('afterprint', limpiarImpresion);
  document.getElementById('imprimir').addEventListener('click', function () {
    prepararImpresion();
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
  // Modo claro / oscuro: manda el teléfono (prefers-color-scheme) y se vuelve
  // a leer en cada carga. El botón sirve para cambiarlo mientras la página
  // está abierta; si el teléfono cambia de modo, ese cambio se impone.
  // ------------------------------------------------------------------
  var botonTema = document.getElementById('tema');
  var metaTema = (typeof document !== 'undefined' && document.querySelector)
    ? document.querySelector('meta[name="theme-color"]') : null;
  var temaManual = null;                    // null = el que diga el teléfono

  function prefiereOscuro() {
    return !!(typeof window !== 'undefined' && window.matchMedia
      && window.matchMedia('(prefers-color-scheme: dark)').matches);
  }

  function esTemaOscuroActivo() {
    return temaManual === null ? prefiereOscuro() : temaManual;
  }

  function actualizarTemaVisual(oscuro) {
    var doc = (typeof document !== 'undefined') ? document.documentElement : null;
    if (doc && doc.setAttribute) {
      doc.setAttribute('data-tema', oscuro ? 'oscuro' : 'claro');
    }
    if (metaTema && metaTema.setAttribute) {
      metaTema.setAttribute('content', oscuro ? '#0f172a' : '#008837');
    }
    if (botonTema) {
      botonTema.textContent = oscuro ? '☀️' : '🌙';
      botonTema.title = oscuro ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro';
      if (botonTema.setAttribute) {
        botonTema.setAttribute('aria-label', oscuro ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro');
      }
    }
  }

  if (botonTema) {
    botonTema.addEventListener('click', function () {
      temaManual = !esTemaOscuroActivo();
      actualizarTemaVisual(temaManual);
    });
  }

  if (typeof window !== 'undefined' && window.matchMedia) {
    try {
      var mediaOscuro = window.matchMedia('(prefers-color-scheme: dark)');
      var alCambiarMedia = function (e) {
        temaManual = null;                  // el teléfono vuelve a mandar
        actualizarTemaVisual(!!e.matches);
      };
      if (mediaOscuro.addEventListener) {
        mediaOscuro.addEventListener('change', alCambiarMedia);
      } else if (mediaOscuro.addListener) {
        mediaOscuro.addListener(alCambiarMedia);
      }
    } catch (e) {}
  }

  actualizarTemaVisual(esTemaOscuroActivo());

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
      if (valor === null || valor === '') {
        if (ls.removeItem) ls.removeItem(clave);
        return null;
      }
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

  // Si la corrección venía ya embebida en la base (se hizo antes de las 08:00),
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

  // ------------------------------------------------------------------
  // Material adjunto (PDF) de cada actividad
  // ------------------------------------------------------------------
  var BUCKET_ADJUNTOS = 'adjuntos';
  var ADJUNTO_MAX = 8 * 1024 * 1024;
  var adjuntoElegido = null;

  function adjuntosDe(clave) {
    if (!NUBE) return [];
    var k = String(clave || '');
    if (!k) return [];
    var canceladas = {};
    filasNube.forEach(function (f) { if (f.anula) canceladas[String(f.anula)] = true; });
    return filasNube.filter(function (f) {
      return f.tipo === 'adjunto' && String(f.clave || '') === k
          && f.id && !canceladas[String(f.id)];
    }).map(function (f) {
      var c = (f.campos && typeof f.campos === 'object') ? f.campos : {};
      return {id: f.id, archivo: String(c.archivo || ''),
              nombre: String(c.nombre || 'material.pdf')};
    }).filter(function (a) { return !!a.archivo; });
  }

  function urlAdjunto(archivo) {
    return NUBE.url + '/storage/v1/object/public/' + BUCKET_ADJUNTOS + '/'
         + String(archivo).split('/').map(encodeURIComponent).join('/');
  }

  function tamanoLegible(bytes) {
    var n = Number(bytes) || 0;
    return n >= 1048576 ? (n / 1048576).toFixed(1).replace('.0', '') + ' MB'
         : Math.max(1, Math.round(n / 1024)) + ' KB';
  }

  function listaAdjuntos(adjs) {
    var caja = document.createElement('div');
    caja.className = 'adjuntos';
    adjs.forEach(function (a) {
      var enlace = document.createElement('a');
      enlace.className = 'adjunto-link';
      enlace.href = urlAdjunto(a.archivo);
      enlace.target = '_blank';
      enlace.rel = 'noopener';
      enlace.textContent = '\u{1F4CE} ' + a.nombre;
      caja.appendChild(enlace);
    });
    return caja;
  }

  function pintarAdjuntosModal() {
    var caja = document.getElementById('m-adjunto-lista');
    if (!caja) return;
    caja.innerHTML = '';
    var guardados = (origen && origen.k) ? adjuntosDe(origen.k) : [];

    guardados.forEach(function (a) {
      var fila = document.createElement('div');
      fila.className = 'adjunto-item';
      var enlace = document.createElement('a');
      enlace.href = urlAdjunto(a.archivo);
      enlace.target = '_blank';
      enlace.rel = 'noopener';
      enlace.className = 'nombre';
      enlace.textContent = '\u{1F4CE} ' + a.nombre;
      var quitar = document.createElement('button');
      quitar.className = 'mini';
      quitar.textContent = '✕ quitar';
      quitar.title = 'Quita el enlace: el archivo queda en la bitácora, no se borra.';
      quitar.addEventListener('click', function () { quitarAdjunto(a); });
      fila.appendChild(enlace);
      fila.appendChild(quitar);
      caja.appendChild(fila);
    });

    if (adjuntoElegido) {
      var elegido = document.createElement('div');
      elegido.className = 'adjunto-item';
      var nombre = document.createElement('span');
      nombre.className = 'nombre';
      nombre.textContent = '\u{1F4CE} ' + adjuntoElegido.name + ' · '
                         + tamanoLegible(adjuntoElegido.size);
      var sacar = document.createElement('button');
      sacar.className = 'mini';
      sacar.textContent = '✕';
      sacar.title = 'No adjuntar este archivo';
      sacar.addEventListener('click', function () {
        adjuntoElegido = null;
        pintarAdjuntosModal();
      });
      elegido.appendChild(nombre);
      elegido.appendChild(sacar);
      caja.appendChild(elegido);
    }

    if (!guardados.length && !adjuntoElegido) {
      var vacio = document.createElement('div');
      vacio.className = 'adjunto-vacio';
      vacio.textContent = 'Sin material adjunto.';
      caja.appendChild(vacio);
    }
  }

  function quitarAdjunto(a) {
    if (!NUBE || !origen) return;
    var envio = {tipo: 'anula', clave: origen.k || '', anula: a.id,
                 campos: {}, previo: {}, autor: nombreAutor() || 'alguien',
                 token: token()};
    enviar(envio).then(function (filas) {
      filasNube = filasNube.concat(filas);
      reconstruir();
      repintar();
      pintarAdjuntosModal();
    }).catch(function (err) {
      errorModal('No se pudo quitar: ' + String(err.message || err).slice(0, 100));
    });
  }

  function subirAdjunto(clave, archivo) {
    var limpio = String(archivo.name || 'material.pdf')
                   .replace(/[^0-9A-Za-z._-]+/g, '-')
                   .replace(/-+/g, '-').replace(/^-|-$/g, '').slice(-60) || 'material.pdf';
    var ruta = 'a' + Date.now().toString(36) + '-' + limpio;
    if (!/\.pdf$/i.test(ruta)) ruta += '.pdf';
    return fetch(NUBE.url + '/storage/v1/object/' + BUCKET_ADJUNTOS + '/'
                 + encodeURIComponent(ruta), {
      method: 'POST',
      headers: encabezado({'Content-Type': 'application/pdf', 'x-upsert': 'false'}),
      body: archivo
    }).then(function (r) {
      return r.text().then(function (t) {
        if (!r.ok) throw new Error(String(t).slice(0, 160) || ('HTTP ' + r.status));
        return {tipo: 'adjunto', clave: clave, previo: {},
                campos: {archivo: ruta,
                         nombre: String(archivo.name || 'material.pdf').slice(0, 120),
                         bytes: Number(archivo.size) || 0},
                autor: nombreAutor(), token: token()};
      });
    });
  }

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
    if (modal) {
      modal.hidden = true;
      modal.className = '';
    }
    modo = null;
    origen = null;
    adjuntoElegido = null;
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
      var clase = 'campo' + (u.ancho || u.tipo === 'textarea' ? ' ancho' : '');
      if (modo === 'resumen' && u.c === 'CONTENIDO') clase += ' campo-resumen-detalle';
      var label = document.createElement('label');
      label.className = clase;
      var titulo2 = document.createElement('span');
      var etiqueta = u.et;
      if (modo === 'resumen') {
        if (u.c === 'EVALUACION') etiqueta = 'Título del resumen';
        else if (u.c === 'CONTENIDO') etiqueta = 'Detalle de la semana (un ítem por línea)';
      }
      titulo2.textContent = etiqueta;
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
      if (modo === 'resumen') {
        if (u.c === 'EVALUACION') {
          input.placeholder = 'ej: 19, 21 y 23 oct · 3 evaluaciones';
        } else if (u.c === 'CONTENIDO') {
          input.placeholder = 'Detalle de las evaluaciones de la próxima semana';
        }
      }
      if (modo === 'nuevo' && u.c === 'FECHA') input.value = elegida;
      else if (origen) input.value = origen[u.s] || '';
      label.appendChild(input);
      cont.appendChild(label);
    });

    adjuntoElegido = null;
    pintarAdjuntosModal();

    var modal = document.getElementById('modal');
    if (modal) {
      modal.className = (modo === 'resumen') ? 'modal-modo-resumen' : '';
      modal.hidden = false;
    }
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
    var fila = null, claveDestino = '';
    if (modo === 'nuevo') {
      var nuevo = registroNuevo(valores);
      if (!nuevo) {
        errorModal('Faltan datos: fecha, asignatura y nombre de la evaluación.');
        return;
      }
      claveDestino = claveBase(nuevo) + '#1';
      fila = {tipo: 'nuevo', clave: claveDestino,
              campos: validarCampos(valores), previo: {}, autor: autor,
              token: token()};
    } else {
      claveDestino = origen ? String(origen.k || '') : '';
      var campos = {}, previo = {};
      camposUsados().forEach(function (u) {
        var valor = valores[u.c];
        var anterior = String(origen ? (origen[u.s] || '') : '');
        if (valor !== anterior) { campos[u.c] = valor; previo[u.c] = anterior; }
      });
      if (!Object.keys(campos).length && !adjuntoElegido) {
        errorModal('No se cambió nada ni se adjuntó material.');
        return;
      }
      if ('FECHA' in campos && !fechaValida(campos.FECHA)) {
        errorModal('La fecha no es válida (aaaa-mm-dd).');
        return;
      }
      if (Object.keys(campos).length) {
        fila = {tipo: 'correccion', clave: claveDestino, campos: campos, previo: previo,
                autor: autor, token: token()};
      }
    }

    var boton = document.getElementById('m-guardar');
    if (boton) boton.disabled = true;
    errorModal('');
    var archivo = adjuntoElegido;

    function acabar(aviso) {
      if (boton) boton.disabled = false;
      reconstruir();
      cerrarModal();
      repintar();
      var n = contarFilas();
      estado(aviso ? aviso
                   : n + (n === 1 ? ' corrección' : ' correcciones') + ' · guardado',
             aviso ? 'mal' : 'ok');
    }

    function claveDeFila(idFila) {
      var hallada = '';
      Object.keys(porDia).forEach(function (f) {
        porDia[f].forEach(function (ev) {
          (ev.filas || []).forEach(function (x) {
            if (x.id === idFila) hallada = ev.k;
          });
        });
      });
      return hallada;
    }

    if (modo === 'nuevo' && archivo) {
      // La clave del evento nuevo recién se conoce al aplicarlo: si ya había
      // otro con la misma asignatura/número/tipo, le toca #2 y no #1. Se da
      // de alta primero y después se pega el PDF en la clave real.
      enviar(fila).then(function (hechas) {
        filasNube = filasNube.concat(hechas);
        reconstruir();
        var k = claveDeFila(hechas[0] && hechas[0].id) || claveDestino;
        return subirAdjunto(k, archivo).then(function (adjuntoFila) {
          return enviar(adjuntoFila).then(function (r) {
            filasNube = filasNube.concat(r);
            acabar();
          });
        }).catch(function () {
          acabar('evento guardado; el PDF no se pudo subir');
        });
      }).catch(function (err) {
        if (boton) boton.disabled = false;
        errorModal('No se pudo guardar: ' + String(err.message || err).slice(0, 120));
      });
      return;
    }

    // Correcciones y resumen: primero el archivo, después la fila (si la subida
    // falla, no se guarda nada a medias).
    var subida = archivo ? subirAdjunto(claveDestino, archivo) : Promise.resolve(null);
    subida.then(function (adjuntoFila) {
      var envios = [];
      if (adjuntoFila) envios.push(adjuntoFila);
      if (fila) envios.push(fila);
      return envios.reduce(function (p, f) {
        return p.then(function (hechas) {
          return enviar(f).then(function (r) { return hechas.concat(r); });
        });
      }, Promise.resolve([]));
    }).then(function (filas) {
      filasNube = filasNube.concat(filas);
      acabar();
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
  var entradaAdjunto = document.getElementById('m-adjunto-archivo');
  if (entradaAdjunto) {
    entradaAdjunto.addEventListener('change', function () {
      var archivo = entradaAdjunto.files && entradaAdjunto.files[0];
      var nombre = archivo ? String(archivo.name || '') : '';
      try { entradaAdjunto.value = ''; } catch (e) {}
      if (!archivo) return;
      if (!/\.pdf$/i.test(nombre) || (archivo.type && archivo.type !== 'application/pdf')) {
        errorModal('Sólo se puede adjuntar un PDF.');
        return;
      }
      if (archivo.size > ADJUNTO_MAX) {
        errorModal('El PDF pesa ' + tamanoLegible(archivo.size)
                   + '; el máximo es 8 MB.');
        return;
      }
      adjuntoElegido = archivo;
      errorModal('');
      pintarAdjuntosModal();
    });
  }

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

  if (btnInstalar && (enApp || almacenar('edufacil-app-instalada') === '1')) {
    btnInstalar.hidden = true;
  }
  if (nav && nav.getInstalledRelatedApps) {
    nav.getInstalledRelatedApps().then(function (apps) {
      if (apps && apps.length > 0) {
        if (btnInstalar) btnInstalar.hidden = true;
        almacenar('edufacil-app-instalada', '1');
      }
    }).catch(function () {});
  }
  if (window.addEventListener) {
    window.addEventListener('beforeinstallprompt', function (ev) {
      ev.preventDefault();            // no salta el banner: esperamos al botón
      pwaPrompt = ev;
      almacenar('edufacil-app-instalada', null);
      if (btnInstalar && !enApp) btnInstalar.hidden = false;
    });
    window.addEventListener('appinstalled', function () {
      pwaPrompt = null;
      if (btnInstalar) btnInstalar.hidden = true;
      almacenar('edufacil-app-instalada', '1');
    });
  }
  if (btnInstalar) {
    btnInstalar.addEventListener('click', function () {
      if (pwaPrompt) {
        var p = pwaPrompt;
        pwaPrompt = null;
        p.prompt();
        if (p.userChoice && p.userChoice.catch) {
          p.userChoice.then(function (choice) {
            if (choice && choice.outcome === 'accepted') {
              if (btnInstalar) btnInstalar.hidden = true;
              almacenar('edufacil-app-instalada', '1');
            }
          }).catch(function () {});
        }
        return;
      }
      if (nav && nav.getInstalledRelatedApps) {
        nav.getInstalledRelatedApps().then(function (apps) {
          if (apps && apps.length > 0) {
            if (btnInstalar) btnInstalar.hidden = true;
            almacenar('edufacil-app-instalada', '1');
            msgAvisos('✓ La aplicación ya está instalada en tu teléfono.');
            return;
          }
          msgAvisos(esIos
            ? 'iPhone: toca Compartir → «Agregar a pantalla de inicio».'
            : 'Elige «Instalar aplicación» en el menú del navegador.');
        }).catch(function () {
          msgAvisos(esIos
            ? 'iPhone: toca Compartir → «Agregar a pantalla de inicio».'
            : 'Elige «Instalar aplicación» en el menú del navegador.');
        });
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

  // ---- comunicados generales, desde el 1 de septiembre de 2026 en Chile ----
  var MENSAJES_DESDE = new Date('2026-09-01T00:00:00-04:00');
  var CLAVE_LEIDOS = 'edufacil-mensajes-leidos';
  var ultimosMensajes = [];

  function fechaLarga(iso) {
    var f = new Date(iso);
    if (isNaN(f.getTime())) return '';
    return DIAS[f.getDay()] + ' ' + f.getDate() + ' de '
         + MESES[f.getMonth()].toLowerCase();
  }

  function idMensaje(m) {
    return (m && m.id) ? String(m.id) : (m ? String(m.fecha || '') + '|' + String(m.asunto || '') : '');
  }

  function leerMensajesLeidos() {
    try {
      var guardado = almacenar(CLAVE_LEIDOS);
      if (guardado) {
        var parsed = JSON.parse(guardado);
        if (parsed && typeof parsed === 'object') return parsed;
      }
    } catch (e) {}
    return {};
  }

  function marcarMensajesLeidos(filas) {
    if (!Array.isArray(filas) || !filas.length) return;
    var mapa = leerMensajesLeidos();
    var cambio = false;
    filas.forEach(function (m) {
      var id = idMensaje(m);
      if (id && !mapa[id]) {
        mapa[id] = 1;
        cambio = true;
      }
    });
    if (cambio) {
      try {
        almacenar(CLAVE_LEIDOS, JSON.stringify(mapa));
      } catch (e) {}
    }
  }

  function refrescarCuentaMensajes() {
    var cuenta = document.getElementById('cuenta-mensajes');
    if (!cuenta) return;
    if (!ultimosMensajes.length) {
      cuenta.textContent = '';
      cuenta.hidden = true;
      return;
    }
    if (vistaActiva === 'mensajes') {
      marcarMensajesLeidos(ultimosMensajes);
      cuenta.textContent = '';
      cuenta.hidden = true;
      return;
    }
    var mapa = leerMensajesLeidos();
    var noLeidos = 0;
    ultimosMensajes.forEach(function (m) {
      var id = idMensaje(m);
      if (id && !mapa[id]) noLeidos++;
    });
    if (noLeidos > 0) {
      cuenta.textContent = String(noLeidos);
      cuenta.hidden = false;
    } else {
      cuenta.textContent = '';
      cuenta.hidden = true;
    }
  }

  function pintarMensajes(filas) {
    var seccion = document.getElementById('mensajes');
    var lista = document.getElementById('mensajes-lista');
    if (!seccion || !lista) return;
    var hasta = Date.now();
    filas = (Array.isArray(filas) ? filas : []).filter(function (m) {
      var fecha = new Date(m.fecha).getTime();
      return fecha >= MENSAJES_DESDE.getTime() && fecha <= hasta;
    });
    ultimosMensajes = filas.slice();
    lista.innerHTML = '';
    if (!filas.length) {
      document.getElementById('tab-mensajes').hidden = true;
      document.getElementById('cuenta-mensajes').textContent = '0';
      pestana('calendario');
      return;
    }
    var gruposMes = [];
    var porMes = {};
    filas.forEach(function (m) {
      var f = new Date(m.fecha);
      var clave = isNaN(f.getTime()) ? 'sin-fecha' : f.getFullYear() + '-' + String(f.getMonth() + 1).padStart(2, '0');
      var nombre = isNaN(f.getTime()) ? 'Otros comunicados' : (MESES[f.getMonth()] + ' ' + f.getFullYear());
      if (!porMes[clave]) {
        var g = { clave: clave, nombre: nombre, mensajes: [] };
        porMes[clave] = g;
        gruposMes.push(g);
      }
      porMes[clave].mensajes.push(m);
    });

    gruposMes.forEach(function (g, idx) {
      var det = document.createElement('details');
      det.className = 'mes-grupo';
      if (idx === 0) det.open = true;

      var sum = document.createElement('summary');
      sum.className = 'mes-cabecera';

      var wrap = document.createElement('div');
      wrap.className = 'mes-titulo-wrap';
      var flecha = document.createElement('span');
      flecha.className = 'mes-flecha';
      flecha.textContent = '▶';
      var tit = document.createElement('span');
      tit.className = 'mes-titulo';
      tit.textContent = g.nombre;
      wrap.appendChild(flecha);
      wrap.appendChild(tit);
      sum.appendChild(wrap);

      var cuenta = document.createElement('span');
      cuenta.className = 'mes-cuenta';
      var cant = g.mensajes.length;
      cuenta.textContent = cant === 1 ? '1 comunicado' : cant + ' comunicados';
      sum.appendChild(cuenta);

      det.appendChild(sum);

      g.mensajes.forEach(function (m, i) {
        var caja = document.createElement('article');
        caja.className = 'mensaje' + (i === 0 ? ' cabecera' : '');

        var cab = document.createElement('div');
        cab.className = 'cab';
        var asunto = document.createElement('span');
        asunto.className = 'asunto';
        asunto.textContent = m.asunto || 'Comunicado';
        cab.appendChild(asunto);
        var cuando = document.createElement('span');
        cuando.className = 'cuando';
        cuando.textContent = fechaLarga(m.fecha);
        cab.appendChild(cuando);
        caja.appendChild(cab);

        var puntos = Array.isArray(m.puntos) ? m.puntos : [];
        if (puntos.length) {
          var ul = document.createElement('ul');
          ul.className = 'puntos';
          puntos.forEach(function (p) {
            var li = document.createElement('li');
            li.textContent = p;
            ul.appendChild(li);
          });
          caja.appendChild(ul);
        }

        (Array.isArray(m.eventos) ? m.eventos : []).forEach(function (e) {
          var linea = document.createElement('p');
          linea.className = 'evento';
          linea.textContent = (e.fecha_inicio || '').slice(0, 10)
                            + ' · ' + (e.titulo || '');
          caja.appendChild(linea);
        });

        if (m.accion) {
          var accion = document.createElement('p');
          accion.className = 'accion';
          accion.textContent = 'Recomendación: ' + m.accion;
          caja.appendChild(accion);
        }

        det.appendChild(caja);
      });

      lista.appendChild(det);
    });
    var pestana2 = document.getElementById('tab-mensajes');
    if (pestana2) pestana2.hidden = false;
    refrescarCuentaMensajes();
    pestana(typeof location !== 'undefined' && location.hash === '#mensajes'
            ? 'mensajes' : vistaActiva);
  }

  function cargarMensajes() {
    if (!NUBE || !NUBE.mensajes) return;
    var limite = 500, filas = [];
    var consulta = NUBE.url + '/rest/v1/' + NUBE.mensajes +
          '?select=id,asunto,fecha,puntos,accion,eventos&order=fecha.desc,id.desc&limit=' + limite +
          '&fecha=gte.' + encodeURIComponent(MENSAJES_DESDE.toISOString()) + '&fecha=lte.' +
          encodeURIComponent(new Date().toISOString());
    function lote(offset) {
      return fetch(consulta + '&offset=' + offset, {headers: encabezado()})
        .then(function (r) {
          if (r.status === 404) throw new Error('falta el SQL en Supabase');
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        })
        .then(function (parte) {
          if (!Array.isArray(parte)) throw new Error('respuesta de mensajes no válida');
          filas = filas.concat(parte);
          return parte.length === limite ? lote(offset + limite) : filas;
        });
    }
    return lote(0).then(pintarMensajes)
      .catch(function () {});      // un fallo no borra los mensajes ya visibles
  }

  function actualizarHoraClima() {
    var reloj = document.getElementById('clima-hora');
    var elH = document.getElementById('clima-horas');
    var elM = document.getElementById('clima-minutos');
    var ahora = new Date();
    var hh = String(ahora.getHours()).padStart(2, '0');
    var mm = String(ahora.getMinutes()).padStart(2, '0');
    var hora = hh + ':' + mm;
    if (elH && elM) {
      if (elH.textContent !== hh) elH.textContent = hh;
      if (elM.textContent !== mm) elM.textContent = mm;
    } else if (reloj && reloj.textContent !== hora) {
      reloj.textContent = hora;
    }
    if (reloj) reloj.dateTime = ahora.toISOString();
  }

  // La ubicación se pide al pulsar el botón y se recuerda en este navegador.
  var lugarClimaDefecto = { latitud: -36.83, longitud: -73.05, nombre: 'Concepción' };
  var lugarClima = (function () {
    try {
      var guardado = almacenar('edufacil-clima-lugar');
      if (guardado) {
        var obj = JSON.parse(guardado);
        if (obj && typeof obj.latitud === 'number' && Number.isFinite(obj.latitud)
            && typeof obj.longitud === 'number' && Number.isFinite(obj.longitud)
            && typeof obj.nombre === 'string' && obj.nombre.trim()) {
          return {
            latitud: Math.round(obj.latitud * 100) / 100,
            longitud: Math.round(obj.longitud * 100) / 100,
            nombre: obj.nombre.trim().slice(0, 60),
            propia: true
          };
        }
      }
    } catch (e) {}
    return { latitud: lugarClimaDefecto.latitud, longitud: lugarClimaDefecto.longitud,
             nombre: lugarClimaDefecto.nombre };
  })();
  var versionClima = 0;
  function estadoDelClima(codigo, esDia) {
    if (codigo === 0) return [esDia ? '☀️' : '🌙', 'Despejado'];
    if (codigo === 1 || codigo === 2) return [esDia ? '⛅' : '☁️', 'Parcialmente nublado'];
    if (codigo === 3) return ['☁️', 'Nublado'];
    if (codigo === 45 || codigo === 48) return ['🌁', 'Niebla'];
    if ([51, 53, 55, 56, 57].indexOf(codigo) >= 0) return ['☔', 'Llovizna'];
    if ([61, 63, 65, 66, 67, 80, 81, 82].indexOf(codigo) >= 0) return ['☔', 'Lluvia'];
    if ([71, 73, 75, 77, 85, 86].indexOf(codigo) >= 0) return ['❄️', 'Nieve'];
    if ([95, 96, 99].indexOf(codigo) >= 0) return ['⚡', 'Tormenta'];
    return ['🌡️', 'Tiempo actual'];
  }

  function svgClima(codigo, esDia) {
    if (codigo === 0) {
      if (esDia) {
        return '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4" fill="#fbbf24"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>';
      }
      return '<svg viewBox="0 0 24 24" aria-hidden="true" fill="#fbbf24" stroke="#f59e0b" stroke-width="1.5" stroke-linecap="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
    }
    if (codigo === 1 || codigo === 2) {
      return '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke-linecap="round"><circle cx="12" cy="8" r="3" fill="#fbbf24" stroke="#f59e0b" stroke-width="1.5"/><path d="M12 2v2M4.93 4.93l1.41 1.41M19.07 4.93l-1.41 1.41" stroke="#f59e0b" stroke-width="1.5"/><path d="M7 19h10a4 4 0 0 0 0-8 6 6 0 0 0-11.6 1.8A3.5 3.5 0 0 0 7 19z" fill="#94a3b8" stroke="#64748b" stroke-width="1.5"/></svg>';
    }
    if (codigo === 3) {
      return '<svg viewBox="0 0 24 24" aria-hidden="true" fill="#94a3b8" stroke="#64748b" stroke-width="1.5" stroke-linecap="round"><path d="M17.5 19H7a4.5 4.5 0 0 1-.5-8.97 6 6 0 0 1 11.9 1.47A4 4 0 0 1 17.5 19z"/></svg>';
    }
    if (codigo === 45 || codigo === 48) {
      return '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round"><path d="M4 8h16M2 12h20M5 16h14M7 20h10"/></svg>';
    }
    if ([51, 53, 55, 56, 57].indexOf(codigo) >= 0) {
      return '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke-linecap="round"><path d="M17 15H7a4 4 0 0 1-.5-7.97 5.5 5.5 0 0 1 10.9 1.47A3.5 3.5 0 0 1 17 15z" fill="#94a3b8" stroke="#64748b" stroke-width="1.5"/><path d="M8 18v2M12 18v2M16 18v2" stroke="#38bdf8" stroke-width="2"/></svg>';
    }
    if ([61, 63, 65, 66, 67, 80, 81, 82].indexOf(codigo) >= 0) {
      return '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke-linecap="round"><path d="M17 14H7a4 4 0 0 1-.5-7.97 5.5 5.5 0 0 1 10.9 1.47A3.5 3.5 0 0 1 17 14z" fill="#64748b" stroke="#475569" stroke-width="1.5"/><path d="M8 17l-1 3M12 17l-1 3M16 17l-1 3" stroke="#0284c7" stroke-width="2"/></svg>';
    }
    if ([71, 73, 75, 77, 85, 86].indexOf(codigo) >= 0) {
      return '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="#38bdf8" stroke-width="2" stroke-linecap="round"><path d="M12 2v20M2 12h20M5 5l14 14M5 19L19 5"/></svg>';
    }
    if ([95, 96, 99].indexOf(codigo) >= 0) {
      return '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke-linecap="round"><path d="M17 13H7a4 4 0 0 1-.5-7.97 5.5 5.5 0 0 1 10.9 1.47A3.5 3.5 0 0 1 17 13z" fill="#475569" stroke="#334155" stroke-width="1.5"/><path d="M13 13l-3 4h3l-1 4 5-5h-3l1-3z" fill="#facc15" stroke="#eab308" stroke-width="1"/></svg>';
    }
    return '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="8"/></svg>';
  }

  function cargarClima() {
    var widget = document.getElementById('clima');
    if (!widget) return;
    var version = ++versionClima;
    var lugar = lugarClima;
    document.getElementById('clima-ciudad').textContent = lugar.propia ? lugar.nombre : 'Mi ubicación';
    document.getElementById('clima-temperatura').textContent = '— °C';
    document.getElementById('clima-icono').textContent = '🌡️';
    var control = new AbortController();
    var tiempo = setTimeout(function () { control.abort(); }, 8000);
    return fetch('https://api.open-meteo.com/v1/forecast?latitude=' + lugar.latitud + '&longitude=' + lugar.longitud +
          '&current=temperature_2m,weather_code,is_day&daily=weather_code,temperature_2m_max,temperature_2m_min&forecast_days=4&timezone=auto',
          {signal: control.signal})
      .then(function (r) {
        if (!r.ok) throw new Error('clima no disponible');
        return r.json();
      })
      .then(function (datos) {
        if (version !== versionClima) return;
        var actual = datos && datos.current;
        if (!actual || typeof actual.temperature_2m !== 'number' || !isFinite(actual.temperature_2m)
            || actual.temperature_2m < -100 || actual.temperature_2m > 70
            || !Number.isInteger(actual.weather_code) || [0, 1].indexOf(actual.is_day) < 0
            || !datos.current_units || datos.current_units.temperature_2m !== '°C') {
          throw new Error('datos de clima no válidos');
        }
        var estado = estadoDelClima(actual.weather_code, actual.is_day === 1);
        document.getElementById('clima-icono').textContent = estado[0];
        document.getElementById('clima-temperatura').textContent = Math.round(actual.temperature_2m) + ' °C';
        widget.title = lugar.nombre + ' · ' + estado[1] +
          (typeof actual.time === 'string' ? ' · ' + actual.time.slice(11, 16) + ' (hora local)' : '');

        var contenedorPronostico = document.getElementById('clima-pronostico');
        if (contenedorPronostico) {
          contenedorPronostico.innerHTML = '';
          var daily = datos && datos.daily;
          if (daily && Array.isArray(daily.time)) {
            for (var i = 1; i <= 3 && i < daily.time.length; i++) {
              var d = new Date(daily.time[i] + 'T12:00:00');
              var diaSemana = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'][d.getDay()];
              var etiqueta = (i === 1) ? 'Mañana' : (diaSemana + ' ' + d.getDate());
              var code = daily.weather_code[i];
              var min = daily.temperature_2m_min[i];
              var max = daily.temperature_2m_max[i];
              var estDia = estadoDelClima(code, true);

              var diaEl = document.createElement('div');
              diaEl.className = 'dia-pronostico';
              diaEl.title = diaSemana + ' ' + d.getDate() + ': ' + estDia[1] +
                ' (mín ' + Math.round(min) + ' °C / máx ' + Math.round(max) + ' °C)';

              var nomEl = document.createElement('span');
              nomEl.className = 'dia-nombre';
              nomEl.textContent = etiqueta;
              diaEl.appendChild(nomEl);

              var icoEl = document.createElement('span');
              icoEl.className = 'dia-icono';
              icoEl.setAttribute('aria-label', estDia[1]);
              icoEl.innerHTML = svgClima(code, true);
              diaEl.appendChild(icoEl);

              var tempEl = document.createElement('span');
              tempEl.className = 'dia-temp';
              tempEl.textContent = Math.round(min) + '° / ' + Math.round(max) + '°';
              diaEl.appendChild(tempEl);

              contenedorPronostico.appendChild(diaEl);
            }
          }
        }
      })
      .catch(function () {
        if (version !== versionClima) return;
        document.getElementById('clima-icono').textContent = '🌡️';
        document.getElementById('clima-temperatura').textContent = 'Sin datos';
        widget.title = 'Clima de ' + lugar.nombre + ' no disponible; se reintentará al actualizar.';
        var cont = document.getElementById('clima-pronostico');
        if (cont) cont.innerHTML = '';
      })
      .then(function () { clearTimeout(tiempo); });
  }

  function nombreUbicacionClima(lugar) {
    var control = new AbortController();
    var tiempo = setTimeout(function () { control.abort(); }, 4000);
    // Sólo tras permiso; la consulta se hace desde el navegador, sin guardar coordenadas.
    return fetch('https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=' +
          lugar.latitud + '&longitude=' + lugar.longitud + '&localityLanguage=es',
          {signal: control.signal})
      .then(function (r) {
        if (!r.ok) throw new Error('nombre de ubicación no disponible');
        return r.json();
      })
      .then(function (datos) {
        var nombre = datos && [datos.city, datos.locality, datos.principalSubdivision].find(function (n) {
          return typeof n === 'string' && n.trim();
        });
        return nombre ? nombre.trim().slice(0, 60) : '';
      })
      .catch(function () { return ''; })
      .then(function (nombre) { clearTimeout(tiempo); return nombre; });
  }

  function usarUbicacionClima() {
    var boton = document.getElementById('clima-ubicacion');
    boton.disabled = true;
    document.getElementById('clima-ciudad').textContent = 'Buscando…';
    return new Promise(function (resolver) {
      function terminar(motivo) {
        boton.disabled = false;
        document.getElementById('clima-ciudad').textContent = lugarClima.propia ? lugarClima.nombre : 'Mi ubicación';
        boton.title = motivo;
        resolver(cargarClima());
      }
      function sinUbicacion() {
        lugarClima = { latitud: lugarClimaDefecto.latitud, longitud: lugarClimaDefecto.longitud,
                       nombre: lugarClimaDefecto.nombre };
        almacenar('edufacil-clima-lugar', null);
        terminar('No se pudo obtener permiso o ubicación. Se muestra Concepción. Puedes intentarlo otra vez.');
      }
      if (typeof navigator === 'undefined' || !navigator.geolocation) { sinUbicacion(); return; }
      try {
        navigator.geolocation.getCurrentPosition(function (posicion) {
          var lat = posicion.coords.latitude, lon = posicion.coords.longitude;
          if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) {
            sinUbicacion(); return;
          }
          // Aproximadamente un kilómetro: el clima no necesita una posición exacta.
          lugarClima = { latitud: Math.round(lat * 100) / 100,
            longitud: Math.round(lon * 100) / 100, nombre: 'Zona actual', propia: true };
          nombreUbicacionClima(lugarClima).then(function (nombre) {
            lugarClima.nombre = nombre || 'Zona actual';
            almacenar('edufacil-clima-lugar', JSON.stringify({
              latitud: lugarClima.latitud,
              longitud: lugarClima.longitud,
              nombre: lugarClima.nombre
            }));
            terminar(nombre ? 'Clima de ' + nombre + '. Ubicación guardada en tu navegador.' :
              'No se pudo obtener el nombre de la ciudad. Se muestra el clima de tu ubicación aproximada.');
          });
        }, sinUbicacion, { enableHighAccuracy: false, timeout: 10000, maximumAge: 1800000 });
      } catch (e) { sinUbicacion(); }
    });
  }

  document.getElementById('clima-ubicacion').addEventListener('click', usarUbicacionClima);

  // ---- pestañas: calendario y mensajes ----
  var vistaActiva = 'calendario';
  function pestana(nombre) {
    var cal = document.getElementById('vista-calendario');
    var men = document.getElementById('mensajes');
    var tcal = document.getElementById('tab-calendario');
    var tmen = document.getElementById('tab-mensajes');
    // sin mensajes no hay pestaña de mensajes: se cae al calendario
    if (nombre === 'mensajes' && (!tmen || tmen.hidden)) nombre = 'calendario';
    vistaActiva = nombre;
    if (cal) cal.hidden = (nombre !== 'calendario');
    if (men) men.hidden = (nombre !== 'mensajes');
    if (tcal) tcal.className = (nombre === 'calendario') ? 'activa' : '';
    if (tmen) tmen.className = (nombre === 'mensajes') ? 'activa' : '';
    refrescarCuentaMensajes();
  }

  function alCambiarPestana(ev) {
    var id = (ev && ev.currentTarget && ev.currentTarget.id) || '';
    pestana(id === 'tab-mensajes' ? 'mensajes' : 'calendario');
  }

  ['tab-calendario', 'tab-mensajes'].forEach(function (id) {
    var b = document.getElementById(id);
    if (b) b.addEventListener('click', alCambiarPestana);
  });
  if (typeof location !== 'undefined'
      && location.hash === '#mensajes') pestana('mensajes');

  reconstruir();
  repintar();
  if (NUBE) { cargarFilas(); cargarMensajes(); }
  cargarClima();
  actualizarHoraClima();
  window.addEventListener('focus', actualizarHoraClima);
  window.setInterval(function () {
    if (document.visibilityState !== 'hidden') actualizarHoraClima();
  }, 1000);
  window.setInterval(function () {
    if (document.visibilityState !== 'hidden') cargarClima();
  }, 30 * 60 * 1000);

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
    mensajes: pintarMensajes,
    recargarMensajes: cargarMensajes,
    recargarClima: cargarClima,
    recargar: cargarFilas,
    tema: esTemaOscuroActivo,
    cambiarTema: function (oscuro) {
      temaManual = !!oscuro;
      actualizarTemaVisual(temaManual);
    }
  };
})();
</script>
</body>
</html>
"""


def _colores(eventos: list[dict]) -> dict[str, str]:
    """Color estable por asignatura: fijo para las oficiales.

    Se resuelve por nombre **canónico**, así «MATEMÁTICAS» y «Matemática»
    comparten el color de «MATEMÁTICA» y no desplazan al resto. Una asignatura
    desconocida recibe el primer color de la paleta que quede libre.
    """
    crudos: dict[str, str] = {}
    asignados: dict[str, str] = {}
    for r in eventos:
        crudo = str(r.get("ASIGNATURA") or "").strip()
        if not crudo:
            continue
        nombre = _canonica(crudo)
        crudos[crudo] = nombre
        if nombre in asignados:
            continue
        if nombre in COLORES_ASIGNATURA:
            asignados[nombre] = COLORES_ASIGNATURA[nombre]
        else:
            usados = set(asignados.values())
            asignados[nombre] = next(
                (c for c in PALETA if c not in usados),
                PALETA[len(asignados) % len(PALETA)])
    return {crudo: asignados[nombre] for crudo, nombre in crudos.items()}


def _asegurar(ruta: Path) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    return ruta


def _logo_base64() -> str:
    """Logo incrustado para conservar el HTML autocontenido y sin rutas locales."""
    ruta = Path(__file__).resolve().parent / "web" / "logo.jpeg"
    return base64.b64encode(ruta.read_bytes()).decode("ascii")


def _rango_fechas(desde: str, hasta: str) -> str:
    if not desde or not hasta:
        return "sin fechas"
    inicio = datetime.strptime(desde, "%Y-%m-%d").strftime("%d/%m/%Y")
    fin = datetime.strptime(hasta, "%Y-%m-%d").strftime("%d/%m/%Y")
    return f"del {inicio} al {fin}"


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
    if nube_dict is not None:
        nube_dict["mensajes"] = "comunicados"
    if nube_dict is not None and avisos_clave:
        nube_dict["vapid"] = str(avisos_clave)
    nube_json = json.dumps(nube_dict, ensure_ascii=False, separators=(",", ":"))

    ics = texto_ics(registros, recordatorio_min=recordatorio_min)
    ics_b64 = base64.b64encode(ics.encode("utf-8")).decode("ascii")

    rango = _rango_fechas(desde, hasta)
    html = (
        _PLANTILLA
        .replace("{{DATOS}}", json_texto)
        .replace("{{CORTOS}}", json.dumps(NOMBRES_ASIGNATURA, ensure_ascii=False))
        .replace("{{ICS}}", ics_b64)
        .replace("{{NUBE}}", nube_json)
        .replace("{{LOGO}}", _logo_base64())
        .replace("{{RANGO}}", rango)
        .replace("{{GENERADO}}", datetime.now().strftime("%d/%m/%Y %H:%M"))
    )
    ruta.write_text(html, encoding="utf-8")
    copiar_recursos(ruta.parent)    # manifest, sw.js e iconos junto al HTML
    return ruta
