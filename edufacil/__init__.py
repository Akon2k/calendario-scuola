# -*- coding: utf-8 -*-
"""Scraper del Calendario de Evaluaciones de EduFácil (edufacil.cl)."""

from .cliente import (
    BASE,
    URL_APP,
    ErrorEdufacil,
    ErrorLogin,
    ErrorNavegacion,
    EdufacilClient,
)
from .datos import COLUMNAS, agregar_detalle, limpiar, ordenar, registros_desde_dias
from .exportar import a_csv, a_excel, a_json
from .pagina import a_html

__all__ = [
    "BASE",
    "URL_APP",
    "COLUMNAS",
    "EdufacilClient",
    "ErrorEdufacil",
    "ErrorLogin",
    "ErrorNavegacion",
    "registros_desde_dias",
    "agregar_detalle",
    "ordenar",
    "limpiar",
    "a_excel",
    "a_csv",
    "a_json",
    "a_html",
]
