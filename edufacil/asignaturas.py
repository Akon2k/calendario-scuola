# -*- coding: utf-8 -*-
"""Catálogo de asignaturas con su código EFYS, tal como los da el colegio.

Es sólo el respaldo: cada corrida de ``main.py`` trae el catálogo real desde
EduFácil (``subsectores``) y lo incrusta en la página, así que si el colegio
agrega una asignatura aparece sola en los combos sin tocar el código.

Sirve para que la página tenga combos decentes incluso cuando se genera sin
conexión al sitio (pruebas, vistas previas) y para que ``ABREVIATURA`` se
proponga con el código del colegio —«IDIOMA EXTRANJERO (INGLÉS)» -> «IEXIN»—
y no con las iniciales automáticas (que darían «IEXIS»).
"""

from __future__ import annotations

ASIGNATURAS_EFYS: list[tuple[str, str]] = [
    ("ARTES VISUALES", "ARTVI"),
    ("CIENCIAS NATURALES", "CINA"),
    ("EDUCACIÓN FÍSICA Y SALUD", "EFYS"),
    ("HISTORIA, GEOGRAFÍA Y CIENCIAS SOCIALES", "HGYCS"),
    ("IDIOMA EXTRANJERO (INGLÉS)", "IEXIN"),
    ("IDIOMA EXTRANJERO (ITALIANO)", "IEXIT"),
    ("LENGUAJE Y COMUNICACIÓN", "LEYCO"),
    ("MATEMÁTICA", "MATEM"),
    ("MÚSICA", "MUSIC"),
    ("ORIENTACIÓN", "ORIEN"),
    ("RELIGIÓN", "RELIG"),
    ("TECNOLOGÍA", "TECNO"),
]


def catalogo(extras=None) -> list[dict]:
    """Lista ordenada ``[{a: asignatura, ab: código}]`` sin repetidos.

    ``extras`` puede ser otro catálogo (por ejemplo el que viene del sitio) y
    manda sobre el de respaldo: si una asignatura cambia de código, se usa el
    nuevo. Un código vacío nunca borra uno conocido.
    """
    por_nombre: dict[str, str] = {}
    for nombre, abreviatura in ASIGNATURAS_EFYS:
        por_nombre[nombre] = abreviatura
    for nombre, abreviatura in _pares(extras):
        por_nombre[nombre] = abreviatura or por_nombre.get(nombre, "")
    return [{"a": nombre, "ab": ab} for nombre, ab in sorted(por_nombre.items())]


def _pares(extras) -> list[tuple[str, str]]:
    """Acepta ``[(nombre, código)]`` o ``[{a, ab}]`` y devuelve pares limpios."""
    pares: list[tuple[str, str]] = []
    for elemento in extras or []:
        if isinstance(elemento, dict):
            nombre = str(elemento.get("a") or elemento.get("subsector") or "")
            abreviatura = str(elemento.get("ab") or elemento.get("abreviatura") or "")
        else:
            try:
                nombre, abreviatura = elemento
            except (TypeError, ValueError):
                continue
            nombre, abreviatura = str(nombre), str(abreviatura)
        nombre, abreviatura = " ".join(nombre.split()), abreviatura.strip()
        if nombre:
            pares.append((nombre, abreviatura))
    return pares
