# -*- coding: utf-8 -*-
"""Genera el texto de un calendario `.ics` (RFC 5545).

**No escribe ningún archivo en `salida/`**: el texto se incrusta en base64
dentro de `salida/calendario.html` y lo entrega el navegador al pulsar el
botón «Descargar .ics» (para Google Calendar, Outlook web o el iPhone).

El texto cumple RFC 5545: fin de línea CRLF, líneas plegadas a 75 octetos,
escapes ``\\,`` ``\\;`` ``\\n``, ``UID`` estable (no depende de la posición
en la lista) y un ``VALARM`` por evento.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timezone

from .semana import TIPO_RESUMEN


def _escapar(valor) -> str:
    return (
        str(valor)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _plegar(linea: str) -> str:
    """Parte la línea en trozos de máximo 75 octetos (RFC 5545)."""
    if len(linea.encode("utf-8")) <= 75:
        return linea
    trozos, actual = [], ""
    for caracter in linea:
        if len((actual + caracter).encode("utf-8")) > 74:
            trozos.append(actual)
            actual = " " + caracter          # la continuación lleva un espacio
        else:
            actual += caracter
    if actual:
        trozos.append(actual)
    return "\r\n".join(trozos)


def _fecha_ics(fecha: date) -> str:
    """Fecha en formato básico AAAAMMDD (VALUE=DATE)."""
    return f"{fecha.year}{fecha.month:02d}{fecha.day:02d}"


def _trigger(minutos: int) -> str:
    """-P1D para un día, -PT30M para minutos."""
    if minutos % 1440 == 0:
        return f"-P{minutos // 1440}D"
    return f"-PT{minutos}M"


def _slug(texto: str) -> str:
    """Clave ASCII segura (sin acentos ni símbolos) para el UID."""
    sin_acentos = unicodedata.normalize("NFD", str(texto)).encode(
        "ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9]+", "-", sin_acentos).strip("-").upper() or "EVENTO"


def _buscar_fecha(registro: dict) -> date | None:
    """Devuelve la fecha del evento; los registros ya vienen como AAAA-MM-DD."""
    for clave, valor in registro.items():
        if valor and "FECHA" in str(clave).upper() and re.match(
                r"^\d{4}-\d{2}-\d{2}$", str(valor)):
            try:
                return date.fromisoformat(str(valor))
            except ValueError:
                return None
    return None


def _titulo(registro: dict) -> str:
    asignatura = str(registro.get("ASIGNATURA") or "").strip()
    evaluacion = str(registro.get("EVALUACION") or "").strip()
    numero = str(registro.get("NUMERO") or "").strip()
    if asignatura and evaluacion:
        base = f"{asignatura}: {evaluacion}"
    else:
        base = asignatura or evaluacion or "Evaluación"
    return f"{base} (N° {numero})" if numero else base


def _uid(registro: dict, fecha: date) -> str:
    """UID estable: depende de la identidad del evento y de su fecha.

    No depende de la posición en la lista, de modo que agregar una
    evaluación nueva no cambia los UID de las demás.
    """
    if registro.get("TIPO") == TIPO_RESUMEN:
        base = "semana-resumen"
    else:
        base = "-".join(str(registro.get(c) or "")
                        for c in ("ASIGNATURA", "NUMERO", "TIPO"))
    return f"edufacil-{_slug(base)}-{fecha.isoformat()}@calendarioevascuola"


def texto_ics(registros: list[dict], recordatorio_min: int | None = 1440) -> str:
    """Devuelve el archivo `.ics` completo como texto (con CRLF)."""
    ahora = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lineas = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Calendario EvaScuola//Edufacil//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Evaluacion Scuola",
    ]

    for registro in registros:
        fecha = _buscar_fecha(registro)
        if not fecha:
            continue
        titulo = _titulo(registro)
        descripcion = "\n".join(
            f"{clave}: {valor}" for clave, valor in registro.items() if valor
        )
        lineas += [
            "BEGIN:VEVENT",
            f"UID:{_uid(registro, fecha)}",
            f"DTSTAMP:{ahora}",
            f"DTSTART;VALUE=DATE:{_fecha_ics(fecha)}",
            f"DTEND;VALUE=DATE:{_fecha_ics(fecha.fromordinal(fecha.toordinal() + 1))}",
            f"SUMMARY:{_escapar(titulo)}",
            f"DESCRIPTION:{_escapar(descripcion)}",
            "TRANSP:TRANSPARENT",
        ]
        if recordatorio_min:
            # El resumen se avisa al empezar el sábado; las evaluaciones, 1 día antes.
            disparo = ("PT0S" if registro.get("TIPO") == TIPO_RESUMEN
                       else _trigger(int(recordatorio_min)))
            lineas += [
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{_escapar(titulo)}",
                f"TRIGGER:{disparo}",
                "END:VALARM",
            ]
        lineas.append("END:VEVENT")

    lineas.append("END:VCALENDAR")
    return "\r\n".join(_plegar(linea) for linea in lineas) + "\r\n"
