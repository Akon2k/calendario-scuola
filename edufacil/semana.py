# -*- coding: utf-8 -*-
"""Resumen semanal: el sábado anterior lista las evaluaciones de esa semana.

Regla: toda evaluación de lunes a viernes se muestra también en el **sábado
anterior**, en un único evento con el detalle de la semana completa.

    Sáb 2026-10-10  →  "14, 15 y 16 oct · 3 evaluaciones"
                       Mié 14 oct
                       IDIOMA EXTRANJERO (ITALIANO)
                       SE4-1: Canción (N° 4.1)
                       Prof. VALENTINA ANDREA PÉREZ DÍAZ
                       Sub-evaluación
                       coef. 1
                       ponderación 1%

                       Jue 15 oct
                       ARTES VISUALES
                       …

Cada evaluación es **un ítem por línea** (fecha, asignatura, prueba,
profesor, tipo, coeficiente y ponderación — sólo los que traiga el registro)
y cada fecha se separa de la siguiente por una **línea en blanco**, igual en
el aviso, en Outlook, en el `.ics` y en la página del calendario.

Los resumenes usan las mismas columnas que las evaluaciones, así que los
exportadores no necesitan cambios. Su identidad es la **fecha del sábado**
(por eso un resumen se actualiza en su lugar si cambian las fechas de la
semana y no se duplica).
"""

from __future__ import annotations

from datetime import date, timedelta

MESES_CORTOS = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago",
                "sep", "oct", "nov", "dic"]
DIAS_CORTOS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

TIPO_RESUMEN = "Resumen semanal"
ASIGNATURA_RESUMEN = "📚 Resumen de la semana"
ABREVIATURA_RESUMEN = "SEMANA"


def sabado_anterior(fecha: date) -> date:
    """Sábado de la semana (lun-vie) a la que pertenece esa fecha."""
    lunes = fecha - timedelta(days=fecha.weekday())
    return lunes - timedelta(days=2)


def _corta(fecha: date) -> str:
    return f"{fecha.day} {MESES_CORTOS[fecha.month]}"


def _etiqueta_fechas(fechas: list[date]) -> str:
    """«14, 15 y 16 oct» — con mes sólo si las fechas cruzan de mes."""
    mismo_mes = len({f.month for f in fechas}) == 1
    partes = [str(f.day) if mismo_mes else _corta(f) for f in fechas]
    if len(partes) == 1:
        texto = partes[0]
    else:
        texto = ", ".join(partes[:-1]) + " y " + partes[-1]
    return f"{texto} {MESES_CORTOS[fechas[0].month]}" if mismo_mes else texto


def _fila(fecha: date, registro: dict) -> str:
    """Un item, un salto: cada dato del registro en su propia línea."""
    lineas = [f"{DIAS_CORTOS[fecha.weekday()]} {_corta(fecha)}"]
    asignatura = str(registro.get("ASIGNATURA") or "").strip()
    if asignatura:
        lineas.append(asignatura)
    evaluacion = str(registro.get("EVALUACION") or "").strip()
    numero = str(registro.get("NUMERO") or "").strip()
    if evaluacion:
        lineas.append(f"{evaluacion} (N° {numero})" if numero else evaluacion)
    profesor = str(registro.get("PROFESOR") or "").strip()
    if profesor:
        lineas.append(f"Prof. {profesor}")
    tipo = str(registro.get("TIPO") or "").strip()
    if tipo:
        lineas.append(tipo)
    coeficiente = str(registro.get("COEFICIENTE") or "").strip()
    if coeficiente:
        lineas.append(f"coef. {coeficiente}")
    ponderacion = str(registro.get("PONDERACION") or "").strip()
    if ponderacion:
        lineas.append(f"ponderación {ponderacion}"
                      if ponderacion.endswith("%")
                      else f"ponderación {ponderacion}%")
    return "\n".join(lineas)


def resumenes_semanales(registros: list[dict]) -> list[dict]:
    """Un registro-resumen por sábado que tenga evaluaciones de lunes a viernes."""
    grupos: dict[date, list[tuple[date, dict]]] = {}

    for registro in registros:
        if registro.get("TIPO") == TIPO_RESUMEN:
            continue
        iso = str(registro.get("FECHA") or "")
        if len(iso) != 10:
            continue
        try:
            fecha = date.fromisoformat(iso)
        except ValueError:
            continue
        if fecha.weekday() > 4:            # sólo lunes a viernes
            continue
        grupos.setdefault(sabado_anterior(fecha), []).append((fecha, registro))

    resumenes: list[dict] = []
    for sabado in sorted(grupos):
        filas = sorted(
            grupos[sabado],
            key=lambda par: (par[0], str(par[1].get("ASIGNATURA") or ""),
                             str(par[1].get("NUMERO") or "")),
        )
        fechas = sorted({fecha for fecha, _ in filas})
        plural = "evaluación" if len(filas) == 1 else "evaluaciones"
        resumenes.append({
            "FECHA": sabado.isoformat(),
            "DIA": "Sábado",
            "ASIGNATURA": ASIGNATURA_RESUMEN,
            "ABREVIATURA": ABREVIATURA_RESUMEN,
            "EVALUACION": f"{_etiqueta_fechas(fechas)} · {len(filas)} {plural}",
            "CONTENIDO": "\n\n".join(_fila(fecha, reg) for fecha, reg in filas),
            "PROFESOR": "",
            "NUMERO": "",
            "COEFICIENTE": "",
            "PONDERACION": "",
            "TIPO": TIPO_RESUMEN,
        })
    return resumenes
