"""Lecturas públicas para la vista LOCAL de Coronel; nunca envía avisos.

Sólo títulos/enlaces de BioBioChile, estimaciones de Open-Meteo y reportes
del formulario público de Transporte Informa. No lee config ni credenciales.
"""
from __future__ import annotations

import json
import math
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

CHILE = ZoneInfo("America/Santiago")
BIOBIO = "https://www.biobiochile.cl/lista/categorias/region-del-bio-bio"
TRANSITO = "https://biobio.transporteinforma.cl/estado-de-movilidad/"
AJAX_TRANSITO = "https://biobio.transporteinforma.cl/wp-admin/admin-ajax.php"
METEO = "https://api.open-meteo.com/v1/forecast"
MESES = {m: i for i, m in enumerate(("enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"), 1)}


def descargar(url: str, *, metodo="GET", datos=None, parametros=None) -> str:
    """Timeout y tamaño acotados. Los destinos los fija este módulo."""
    respuesta = requests.request(metodo, url, data=datos, params=parametros,
        timeout=(5, 20), stream=True, headers={"User-Agent": "CalendarioScuola-Local/1.0"})
    try:
        respuesta.raise_for_status()
        partes, total = [], 0
        for parte in respuesta.iter_content(65536):
            total += len(parte)
            if total > 2_000_000:
                raise ValueError("Respuesta demasiado grande")
            partes.append(parte)
        return b"".join(partes).decode("utf-8-sig", errors="replace")
    finally:
        respuesta.close()


def texto(valor) -> str:
    return re.sub(r"\s+", " ", str(valor or "")).strip()


def fecha_es(valor: str) -> datetime | None:
    m = re.search(r"(\d{1,2})\s+(?:de\s+)?([a-záéíóú]+),?\s+(?:de\s+)?(\d{4})(?:\s*\|\s*(\d{2}):(\d{2}))?",
                  texto(valor).lower())
    if not m or m[2] not in MESES:
        return None
    try:
        return datetime(int(m[3]), MESES[m[2]], int(m[1]), int(m[4] or 0), int(m[5] or 0), tzinfo=CHILE)
    except ValueError:
        return None


def enlace_valido(url: str, dominio: str) -> bool:
    try:
        u = urlparse(url)
        return (u.scheme == "https" and u.hostname == dominio and not u.username
                and not u.password and (u.port is None or u.port == 443))
    except ValueError:
        return False


def base(tipo: str, ahora: datetime) -> dict:
    nombres = {"ruta": ("160", "Ruta 160 · Coronel", "Transporte Informa Biobío", TRANSITO),
               "clima": ("☁", "Tiempo en Coronel", "Open-Meteo", "https://open-meteo.com/"),
               "noticias": ("BB", "BioBioChile", "BioBioChile", BIOBIO)}
    icono, categoria, fuente, url = nombres[tipo]
    return {"id": tipo, "icono": icono, "categoria": categoria, "fuente": fuente, "url": url,
            "estado": "ok", "consultado": ahora.isoformat(), "publicado": "", "enlaces": [],
            "vigencia_segundos": {"ruta": 3600, "clima": 10800, "noticias": 86400}[tipo]}


def parsear_noticias(html: str, ahora: datetime) -> list[dict]:
    sopa = BeautifulSoup(html, "html.parser")
    noticias, vistos = [], set()
    for bloque in sopa.select(".article-text-container"):
        a = bloque.find("a", href=lambda h: h and "/noticias/nacional/region-del-bio-bio/" in h)
        fecha = bloque.select_one(".article-date-hour")
        if not a or not fecha:
            continue
        url, titulo = a.get("href", ""), texto(a.get_text(" ", strip=True))
        publicada = fecha_es(fecha.get_text(" ", strip=True))
        if not titulo or not publicada or not enlace_valido(url, "www.biobiochile.cl") or url in vistos:
            continue
        if not ahora - timedelta(days=7) <= publicada <= ahora + timedelta(minutes=15):
            continue
        vistos.add(url)
        noticias.append({"titulo": titulo[:220], "url": url, "fecha": publicada.isoformat()})
    return sorted(noticias, key=lambda n: (
        "coronel" not in n["titulo"].lower(), -datetime.fromisoformat(n["fecha"]).timestamp()))[:4]


def noticias(ahora: datetime) -> dict:
    dato = base("noticias", ahora)
    titulares = parsear_noticias(descargar(BIOBIO), ahora)
    if not titulares:
        dato.update(estado="sinreportes", titulo="Sin titulares regionales recientes verificados",
                    resumen="La portada consultada no entregó titulares recientes con fecha verificable.",
                    detalle="Consulta BioBioChile para revisar otras publicaciones. No se muestran titulares inventados.")
        return dato
    primero = titulares[0]
    dato.update(titulo=primero["titulo"], publicado=primero["fecha"], url=primero["url"],
                resumen="BioBioChile · Coronel y Región del Biobío. Títulos y enlaces a las publicaciones originales.",
                detalle="Titulares de la portada regional consultada. Se prioriza Coronel; no se copia el texto completo de los artículos.",
                enlaces=titulares)
    return dato


def numero(valor, minimo, maximo) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) or not minimo <= valor <= maximo:
        raise ValueError("Dato meteorológico no válido")
    return float(valor)


def formato(valor) -> str:
    return f"{valor:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def tiempo(ahora: datetime) -> dict:
    dato = base("clima", ahora)
    respuesta = json.loads(descargar(METEO, parametros={
        "latitude": -37.03386, "longitude": -73.14019, "timezone": "America/Santiago",
        "current": "temperature_2m,weather_code,precipitation,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "forecast_days": 3, "temperature_unit": "celsius", "wind_speed_unit": "kmh"}))
    actual = respuesta["current"]
    offset = numero(respuesta["utc_offset_seconds"], -43200, 50400)
    publicada = datetime.fromisoformat(actual["time"])
    if publicada.tzinfo is None:
        publicada = publicada.replace(tzinfo=timezone(timedelta(seconds=offset)))
    if not ahora - timedelta(hours=3) <= publicada <= ahora + timedelta(minutes=30):
        raise ValueError("Datos del tiempo fuera de vigencia")
    temperatura = numero(actual["temperature_2m"], -80, 65)
    viento = numero(actual["wind_speed_10m"], 0, 500)
    lluvia = numero(actual["precipitation"], 0, 1000)
    codigo = numero(actual["weather_code"], 0, 99)
    if codigo in (0, 1): condicion = "despejado"
    elif codigo in (2, 3): condicion = "nubosidad"
    elif codigo in (45, 48): condicion = "niebla"
    elif 51 <= codigo <= 67 or 80 <= codigo <= 82: condicion = "lluvia o llovizna"
    elif 71 <= codigo <= 77 or codigo in (85, 86): condicion = "nieve"
    elif codigo in (95, 96, 97, 99): condicion = "tormentas según el modelo"
    else: condicion = "condiciones sin descripción"
    pronostico = []
    diario = respuesta.get("daily") or {}
    for i, fecha in enumerate(diario.get("time", [])[:3]):
        try:
            f = datetime.strptime(fecha, "%Y-%m-%d")
            if not ahora.astimezone(CHILE).date() <= f.date() <= (ahora.astimezone(CHILE) + timedelta(days=2)).date():
                continue
            minima = numero(diario["temperature_2m_min"][i], -80, 65)
            maxima = numero(diario["temperature_2m_max"][i], -80, 65)
            prob = numero(diario["precipitation_probability_max"][i], 0, 100)
            pronostico.append(f"{f:%d/%m}: {formato(minima)}–{formato(maxima)} °C · probabilidad de lluvia {prob:g}%")
        except (ValueError, KeyError, IndexError):
            continue
    dato.update(titulo=f"Coronel: {formato(temperatura)} °C · {condicion}",
                resumen=f"Viento {formato(viento)} km/h · precipitación {formato(lluvia)} mm. Estimación de Open-Meteo, no alerta oficial.",
                publicado=publicada.astimezone(CHILE).isoformat(),
                detalle="Tiempo estimado para Coronel por modelos meteorológicos.\n\n" + "\n".join(pronostico)
                        + "\n\nLas alertas oficiales de DMC/SENAPRED no están integradas en esta vista.")
    return dato


def parsear_ruta(html: str, ahora: datetime) -> tuple[list[dict], int]:
    sopa = BeautifulSoup(html, "html.parser")
    tarjetas = sopa.select(".card--state")
    reportes = []
    for tarjeta in tarjetas:
        for icono in tarjeta.select("i"):
            icono.decompose()
        contenido = texto(tarjeta.get_text(" ", strip=True))
        if "coronel" not in contenido.lower() or not re.search(r"ruta\s*160", contenido, re.I):
            continue
        enlace = tarjeta.find("a", href=True)
        caja = tarjeta.select_one(".card--state__text")
        fecha = fecha_es(caja.get_text(" ", strip=True)) if caja else None
        if not fecha or not ahora - timedelta(hours=24) <= fecha <= ahora:
            continue
        if not enlace or not enlace_valido(enlace["href"], "biobio.transporteinforma.cl"):
            continue
        descripcion = caja.find("p", recursive=False)
        descripcion = texto(descripcion.get_text(" ", strip=True)) if descripcion else contenido
        descripcion = re.sub(r"^Descripción\s*", "", descripcion, flags=re.I)
        reportes.append({"titulo": descripcion[:300], "url": enlace["href"], "fecha": fecha.isoformat(), "precision": "dia"})
    return sorted(reportes, key=lambda r: r["fecha"], reverse=True)[:3], len(tarjetas)


def ruta(ahora: datetime) -> dict:
    dato = base("ruta", ahora)
    # Es la misma consulta de lectura que usa el formulario público del sitio.
    respuesta = json.loads(descargar(AJAX_TRANSITO, metodo="POST", datos={
        "action": "get_incidents", "zone_slug": "zona-region-del-biobio",
        "category_slug": "", "number_posts": 24}))
    if respuesta.get("success") is not True or not isinstance(respuesta.get("data"), str):
        raise ValueError("El servicio vial no entregó reportes")
    reportes, cantidad = parsear_ruta(respuesta["data"], ahora)
    if not cantidad:
        raise ValueError("No se pudo reconocer el formato del servicio vial")
    if not reportes:
        dato.update(estado="sinreportes", titulo="Ruta 160 · Coronel: sin reportes recientes verificados",
                    resumen="No apareció un reporte de las últimas 24 h para este sector en la lista consultada. No significa que la ruta esté despejada.",
                    detalle=f"Se revisaron {cantidad} reportes de la lista pública de Transporte Informa Biobío.\n"
                            "Se filtró por Ruta 160 y Coronel y por fecha de publicación.\n"
                            "La consulta no cubre todos los canales ni mide congestión en tiempo real. Revisa la fuente antes de viajar.")
    else:
        dato.update(titulo=reportes[0]["titulo"], publicado=reportes[0]["fecha"],
                    publicado_precision="dia",
                    resumen="Reporte publicado recientemente sobre Ruta 160 y Coronel. Su fecha no garantiza que el incidente continúe vigente.",
                    detalle="Reportes de la fuente consultada. Comprueba las actualizaciones y el término de cada incidente en la publicación original.",
                    enlaces=reportes, url=reportes[0]["url"])
    return dato


def recopilar(ahora: datetime | None = None) -> dict:
    ahora = ahora or datetime.now(CHILE)
    if ahora.tzinfo is None:
        raise ValueError("La consulta necesita zona horaria")
    def segura(par):
        tipo, funcion = par
        try:
            return funcion(ahora)
        except (requests.RequestException, ValueError, KeyError, TypeError, IndexError):
            dato = base(tipo, ahora)
            dato.update(estado="error", titulo=f"{dato['categoria']}: información no disponible",
                        resumen="No pude consultar o validar esta fuente. No se muestran datos inventados ni información anterior como actual.",
                        detalle="Puedes abrir la fuente original e intentarlo de nuevo más tarde.")
            return dato
    with ThreadPoolExecutor(max_workers=3) as grupo:
        lecturas = list(grupo.map(segura, [("ruta", ruta), ("clima", tiempo), ("noticias", noticias)]))
    return {"consultado": ahora.isoformat(), "lecturas": lecturas}
