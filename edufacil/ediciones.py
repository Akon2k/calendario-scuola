# -*- coding: utf-8 -*-
"""Correcciones comunitarias del calendario: tabla ``ediciones`` en Supabase.

Así el calendario queda **editable por el primero que lo lea**: quien note que
EduFácil cambió una fecha la corrige desde la página y el cambio sirve para
todos, sin esperar al scrapeo.

Cómo se combinan las dos fuentes::

    main.py     scrapeo  ⊕  filas de la nube  ->  Excel/CSV/JSON/.ics/Outlook
    la página   base embebida  ⊕  las mismas filas (las lee en vivo)

Reglas:

* **Sólo se agrega** en la nube (RLS sin UPDATE/DELETE): para deshacer se
  inserta un registro ``anula``; queda la bitácora de quién cambió qué.
* **Identidad única con ordinal**: el mismo número se repite en el año («E1»
  en abril y «E1» en agosto), así que la clave lleva posición:
  ``MATEMÁTICA|1|EVALUACIÓN#2``. Sin eso, un índice normal perdería 34 de las
  102 evaluaciones.
* **Caducidad**: ``previo`` guarda el valor reemplazado; si EduFácil cambia el
  dato por su cuenta, la corrección vieja se ignora sola y se anota el aviso.
* **Validación dos veces**: campos permitidos, fechas AAAA-MM-DD reales y
  longitudes razonables; lo que llegue de la nube no contamina los archivos.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import requests

from .datos import COLUMNAS, DIAS_ES
from .outlook import _clave
from .semana import TIPO_RESUMEN

CAMPOS = tuple(COLUMNAS)
TIPOS = ("Evaluación", "Sub-evaluación")
MAXIMOS = {
    "ASIGNATURA": 80, "ABREVIATURA": 12, "EVALUACION": 300, "CONTENIDO": 4000,
    "PROFESOR": 120, "NUMERO": 20, "COEFICIENTE": 12, "PONDERACION": 12,
}
_RE_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RE_PALABRAS = re.compile(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")


class ErrorNube(Exception):
    """No se pudo leer la nube (la corrida sigue adelante sin ella)."""


@dataclass(frozen=True)
class ConfigNube:
    url: str
    clave: str
    tabla: str = "ediciones"


# --------------------------------------------------------------------------
# Configuración
# --------------------------------------------------------------------------
def cargar_nube(config: dict | None) -> ConfigNube | None:
    """Lee ``config["supabase"]``. Vacío o ausente -> None (todo sigue igual)."""
    bloque = (config or {}).get("supabase") or {}
    url = str(bloque.get("url") or "").strip().rstrip("/")
    clave = str(bloque.get("anon_key") or "").strip()
    if not url and not clave:
        return None
    if not url.startswith("https://") or not clave:
        raise ErrorNube("config.json: «supabase» necesita url https:// y anon_key")
    return ConfigNube(url=url, clave=clave,
                      tabla=str(bloque.get("tabla") or "ediciones"))


def _headers(cfg: ConfigNube) -> dict:
    return {
        "apikey": cfg.clave,
        "Authorization": f"Bearer {cfg.clave}",
        "Accept": "application/json",
    }


def obtener_filas(cfg: ConfigNube, timeout: int = 20) -> list[dict]:
    """Baja todas las filas de la tabla, ordenadas por su fecha de creación."""
    url = f"{cfg.url}/rest/v1/{cfg.tabla}"
    try:
        respuesta = requests.get(url, params={"select": "*", "order": "creado.asc"},
                                 headers=_headers(cfg), timeout=timeout)
    except requests.RequestException as exc:
        raise ErrorNube(f"sin conexión con Supabase ({type(exc).__name__})") from exc
    if respuesta.status_code == 404:
        raise ErrorNube(f"la tabla «{cfg.tabla}» no existe: falta ejecutar el SQL")
    if respuesta.status_code != 200:
        raise ErrorNube(f"Supabase respondió {respuesta.status_code}: "
                        f"{respuesta.text[:160]}")
    try:
        datos = respuesta.json()
    except ValueError as exc:
        raise ErrorNube("Supabase devolvió algo que no es JSON") from exc
    if not isinstance(datos, list):
        raise ErrorNube(f"respuesta inesperada: {type(datos).__name__}")
    return datos


def respaldar(filas: list[dict], ruta: Path) -> None:
    """Copia local de las correcciones: si la nube se pierde, se puede restaurar."""
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(filas, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    except OSError:
        pass


def leer_respaldo(ruta: Path) -> list[dict]:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return datos if isinstance(datos, list) else []


# --------------------------------------------------------------------------
# Identidad: el mismo número se repite en el año
# --------------------------------------------------------------------------
def clave_base(registro: dict) -> str:
    """Identidad sin ordinal (los resúmenes usan su sábado)."""
    return _clave(registro)


def claves_unicas(registros: list[dict]) -> list[str]:
    """Una clave por registro, alineada con la lista, única aunque se repita.

    El mismo número se repite en el año («E1» en abril y «E1» en agosto), así
    que cada repetición lleva su posición **según el orden de la lista**, que
    sale del scrapeo y por lo tanto no cambia cuando alguien corrige una fecha
    o un nombre: si el ordinal dependiera de la fecha, una corrección podría
    mover el ordinal y la siguiente corrección apuntaría al registro equivocado.
    """
    salidas: list[str] = []
    vistas: dict[str, int] = {}
    for registro in registros:
        base = clave_base(registro)
        vistas[base] = vistas.get(base, 0) + 1
        salidas.append(f"{base}#{vistas[base]}")
    return salidas


# --------------------------------------------------------------------------
# Validación de lo que llega de la nube
# --------------------------------------------------------------------------
def _fecha_valida(texto: str) -> bool:
    if not _RE_FECHA.match(texto):
        return False
    try:
        date.fromisoformat(texto)
    except ValueError:
        return False
    return True


def validar_campos(campos) -> dict:
    """Sólo campos del calendario, con formato y longitud válidos."""
    if not isinstance(campos, dict):
        return {}
    limpios: dict[str, str] = {}
    for clave, valor in campos.items():
        if isinstance(valor, (dict, list)):
            continue
        nombre = str(clave).strip().upper()
        if nombre not in CAMPOS:
            continue
        texto = str(valor if valor is not None else "").strip()
        limite = MAXIMOS.get(nombre, 200)
        if len(texto) > limite:
            texto = texto[:limite]
        if nombre == "FECHA" and texto and not _fecha_valida(texto):
            continue
        if nombre == "TIPO" and texto and texto not in TIPOS:
            continue
        limpios[nombre] = texto
    return limpios


def abreviar(asignatura: str) -> str:
    """«EDUCACIÓN FÍSICA Y SALUD» -> «EFYS» (para las altas nuevas)."""
    palabras = [p for p in _RE_PALABRAS.split(asignatura) if p]
    return "".join(p[0] for p in palabras[:5]).upper() or "EV"


def _dia_de(fecha_iso: str) -> str:
    try:
        return DIAS_ES[date.fromisoformat(fecha_iso).weekday()]
    except ValueError:
        return ""


def registro_nuevo(campos) -> dict | None:
    """Construye un registro completo para un evento agregado por la gente."""
    limpio = validar_campos(campos)
    if not all(limpio.get(c) for c in ("FECHA", "ASIGNATURA", "EVALUACION")):
        return None
    registro = {c: "" for c in COLUMNAS}
    for nombre, valor in limpio.items():
        registro[nombre] = valor
    registro["DIA"] = _dia_de(registro["FECHA"])
    registro["TIPO"] = registro.get("TIPO") or TIPOS[0]
    registro["ABREVIATURA"] = registro.get("ABREVIATURA") or abreviar(
        registro["ASIGNATURA"])
    return registro


# --------------------------------------------------------------------------
# Combinación scrapeo ⊕ correcciones
# --------------------------------------------------------------------------
def aplicar(registros: list[dict], filas: list[dict],
            *, resumenes: bool = False) -> tuple[list[dict], list[str], dict]:
    """Combina los registros con las correcciones de la nube.

    Devuelve ``(registros, claves, estadísticas)``: las claves van **alineadas**
    con la lista devuelta (únicas y estables) para que la página pueda señalar
    cada evento y para que las altas conserven su identidad.

    ``resumenes=True`` aplica sólo las filas cuya clave empieza por ``SEMANA|``
    (los resúmenes se generan después, con las evaluaciones ya corregidas).
    """
    base = list(registros)
    filas = [f for f in (filas or []) if isinstance(f, dict)]
    canceladas = {str(f.get("anula")) for f in filas if f.get("anula")}
    activas = sorted(
        (f for f in filas
         if f.get("id") and str(f["id"]) not in canceladas
         and not f.get("anula")
         and str(f.get("tipo") or "") in ("correccion", "nuevo")),
        key=lambda f: str(f.get("creado") or ""))

    claves = claves_unicas(base)             # orden del scrapeo: no se mueve
    indice = {claves[i]: base[i] for i in range(len(base))}
    conteo: dict[str, int] = {}
    for registro in base:
        conteo[clave_base(registro)] = conteo.get(clave_base(registro), 0) + 1
    extra: list[dict] = []
    extra_claves: list[str] = []
    nuevos_por_base: dict[str, int] = {}
    est = {"corregidas": 0, "agregadas": 0, "caducas": 0, "sin_destino": 0,
           "anuladas": sum(1 for f in filas if str(f.get("id") or "") in canceladas),
           "avisos": []}

    for fila in activas:
        clave = str(fila.get("clave") or "").strip()
        if clave.startswith("SEMANA|") != bool(resumenes):
            continue                       # cada lista atiende su tipo de clave
        tipo = str(fila.get("tipo") or "")
        campos = validar_campos(fila.get("campos"))

        if tipo == "correccion":
            destino = indice.get(clave)
            if destino is None:
                est["sin_destino"] += 1
                est["avisos"].append(f"corrección sin destino: {clave}")
                continue
            if not campos:
                est["sin_destino"] += 1
                est["avisos"].append(f"corrección vacía: {clave}")
                continue
            previo = fila.get("previo")
            previo = previo if isinstance(previo, dict) else {}
            aplicados = 0
            fecha_ok = False
            for nombre, valor in campos.items():
                actual = str(destino.get(nombre) or "")
                if valor == actual:
                    continue            # la base ya lo trae: nada que tocar
                if nombre in previo and str(previo.get(nombre) or "") != actual:
                    est["caducas"] += 1
                    est["avisos"].append(
                        f"caducada {clave}: {nombre} en EduFácil ya no es "
                        f"«{previo.get(nombre)}»")
                    continue
                destino[nombre] = valor
                aplicados += 1
                if nombre == "FECHA":
                    fecha_ok = True
            if aplicados:
                est["corregidas"] += 1
                if fecha_ok:
                    destino["DIA"] = _dia_de(str(destino.get("FECHA") or ""))
            continue

        # alta de un evento nuevo: se le da identidad propia (el mismo número
        # puede repetirse en el año) sin pisar nada que ya esté en el sitio.
        registro = registro_nuevo(fila.get("campos"))
        if not clave or registro is None:
            est["sin_destino"] += 1
            est["avisos"].append(f"alta inválida: {clave or '(sin clave)'}")
            continue
        base_k = clave_base(registro)
        candidatos = [r for r in indice.values() if clave_base(r) == base_k]
        if any(str(r.get("FECHA") or "") == registro["FECHA"]
               and str(r.get("EVALUACION") or "").strip() == registro["EVALUACION"]
               for r in candidatos):
            est["sin_destino"] += 1
            est["avisos"].append(
                f"alta repetida, se ignora: {base_k} el {registro['FECHA']}")
            continue
        nuevos_por_base[base_k] = nuevos_por_base.get(base_k, 0) + 1
        k = f"{base_k}#{conteo.get(base_k, 0) + nuevos_por_base[base_k]}"
        indice[k] = registro
        extra.append(registro)
        extra_claves.append(k)
        est["agregadas"] += 1

    return base + extra, claves + extra_claves, est
