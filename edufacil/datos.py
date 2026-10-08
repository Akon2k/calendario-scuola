# -*- coding: utf-8 -*-
"""Convierte los datos JSON del calendario en filas exportables."""

from __future__ import annotations

import json
import re
from datetime import date, datetime

COLUMNAS = [
    "FECHA", "DIA", "ASIGNATURA", "ABREVIATURA", "EVALUACION", "CONTENIDO",
    "PROFESOR", "NUMERO", "COEFICIENTE", "PONDERACION", "TIPO",
]

DIAS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES_ES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
            "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def _fecha_iso(valor: str) -> str:
    """Admite 2026-09-28 y 28-09-2026 y devuelve 2026-09-28 (o '' si no se puede)."""
    valor = str(valor or "").strip()
    if not valor:
        return ""
    for formato in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(valor, formato).date().isoformat()
        except ValueError:
            continue
    return ""


def _dia_semana(iso: str) -> str:
    if not iso:
        return ""
    return DIAS_ES[date.fromisoformat(iso).weekday()]


def registros_desde_dias(dias: list[dict], subsectores: dict | None = None) -> list[dict]:
    """Une los días del calendario con sus evaluaciones en filas con COLUMNAS."""
    subsectores = subsectores or {}
    registros: list[dict] = []

    for dia in dias:
        fecha = _fecha_iso(dia.get("fecha", ""))
        try:
            pruebas = dia.get("pruebas") or []
            if isinstance(pruebas, str):
                pruebas = json.loads(pruebas) if pruebas else []
        except ValueError:
            pruebas = []

        for prueba in pruebas:
            sxc = str(prueba.get("sxc", ""))
            ficha = subsectores.get(sxc, {})
            asignatura = (prueba.get("subsector") or ficha.get("subsector") or "").strip()
            abreviatura = (prueba.get("abreviatura") or ficha.get("abreviatura") or "").strip()

            numero = str(prueba.get("orden_prueba") or "").strip()
            subnumero = str(prueba.get("sub_orden_prueba") or "0").strip()
            if subnumero not in ("", "0"):
                numero = f"{numero}.{subnumero}"
                tipo = "Sub-evaluación"
            else:
                tipo = "Evaluación"

            registros.append({
                "FECHA": _fecha_iso(prueba.get("fecha") or dia.get("fecha", "")),
                "DIA": _dia_semana(fecha),
                "ASIGNATURA": asignatura,
                "ABREVIATURA": abreviatura,
                "EVALUACION": str(prueba.get("nombre_prueba") or "").strip(),
                "CONTENIDO": re.sub(r"\s+", " ", str(prueba.get("contenido") or "")).strip(),
                "PROFESOR": "",
                "NUMERO": numero,
                "COEFICIENTE": str(prueba.get("coeficiente") or "").strip(),
                "PONDERACION": "",
                "TIPO": tipo,
                # datos internos para pedir el detalle y después limpiar
                "_sxc": sxc,
                "_fecha": _fecha_iso(prueba.get("fecha") or dia.get("fecha", "")),
                "_numero": str(prueba.get("orden_prueba") or "").strip(),
                "_subnumero": subnumero,
            })
    return registros


def agregar_detalle(registro: dict, detalle: dict | None) -> None:
    """Completa profesor, ponderación y contenido con el detalle de la evaluación."""
    if not detalle:
        return
    registro["PROFESOR"] = str(detalle.get("profesor") or "").strip()
    registro["PONDERACION"] = str(detalle.get("ponderacion") or "").strip()
    if detalle.get("contenido"):
        registro["CONTENIDO"] = re.sub(r"\s+", " ", str(detalle["contenido"])).strip()
    if detalle.get("coeficiente"):
        registro["COEFICIENTE"] = str(detalle["coeficiente"]).strip()
    if not registro["ASIGNATURA"] and detalle.get("asignatura"):
        registro["ASIGNATURA"] = str(detalle["asignatura"]).strip()
    if not registro["EVALUACION"] and detalle.get("prueba"):
        registro["EVALUACION"] = str(detalle["prueba"]).strip()


def ordenar(registros: list[dict]) -> list[dict]:
    """Ordena por fecha, asignatura y número de evaluación."""

    def clave(registro: dict):
        numero = registro.get("NUMERO", "")
        partes = re.split(r"[.\-]", str(numero))
        return (
            registro.get("FECHA") or "9999-99-99",
            registro.get("ASIGNATURA") or "",
            tuple(int(p) if p.isdigit() else 999 for p in partes),
        )

    return sorted(registros, key=clave)


def limpiar(registros: list[dict]) -> list[dict]:
    """Quita las claves internas que empiezan por «_»."""
    return [{k: v for k, v in registro.items() if not k.startswith("_")}
            for registro in registros]
