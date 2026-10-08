# -*- coding: utf-8 -*-
"""Cliente HTTP para EduFácil (edufacil.cl).

EduFácil es una aplicación PHP con sesión cuyo «Calendario de Evaluaciones» no es
HTML estático: el menú vive en un frameset, la función de menú está en
``scripts/funciones.js`` y los datos llegan por AJAX en JSON. Por eso:

* el login es un POST plano a ``control3.php`` (no hay JavaScript ni CAPTCHA);
* se usa ``requests`` y no un navegador headless: Cloudflare deja pasar a
  ``requests`` pero challengea a otros clientes (httpx/Playwright lo comprobaron);
* el menú se resuelve leyendo el ``onclick`` del enlace y la función en
  ``funciones.js``, así que sobrevive a cambios de nombre de archivo.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.parse
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

BASE = "https://edufacil.cl"
URL_LOGIN = f"{BASE}/login.php"
URL_CONTROL = f"{BASE}/control3.php"
URL_APP = f"{BASE}/estudiantes/aplicacion.php"
URL_JS = f"{BASE}/scripts/funciones.js"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
)

MAX_FRAMES = 10
PAUSA_ENTRE_LLAMADAS = 0.05


class ErrorEdufacil(Exception):
    """Error base del scraper."""


class ErrorLogin(ErrorEdufacil):
    """El servidor rechazó las credenciales o la sesión expiró."""


class ErrorNavegacion(ErrorEdufacil):
    """No se encontró un elemento del menú interno."""


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
def normalizar(texto: str) -> str:
    """Mayúsculas, sin acentos y con espacios simples (para comparar textos)."""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().upper()


def _con_puntos(cuerpo: str) -> str:
    return f"{int(cuerpo):,}".replace(",", ".")


def variantes_rut(rut: str) -> list[str]:
    """Formatos que EduFácil acepta: ``123456789``, ``12345678-9``, ``12.345.678-9``."""
    original = str(rut).strip()
    limpio = re.sub(r"[^0-9kK]", "", original)
    salidas = [original] if original else []
    if limpio and limpio not in salidas:
        salidas.append(limpio)
    if len(limpio) >= 2:
        con_guion = f"{limpio[:-1]}-{limpio[-1].upper()}"
        if con_guion not in salidas:
            salidas.append(con_guion)
        puntos = f"{_con_puntos(limpio[:-1])}-{limpio[-1].upper()}"
        if puntos not in salidas:
            salidas.append(puntos)
    return salidas


def _mensaje_info(url: str) -> str:
    """Extrae y limpia el parámetro ``info`` de un redirect de error."""
    query = urllib.parse.urlsplit(url).query
    clave, _, valor = query.partition("=")
    if clave != "info" or not valor:
        return ""
    for codificacion in ("utf-8", "iso-8859-1"):
        try:
            texto = urllib.parse.unquote(valor, encoding=codificacion, errors="strict")
        except (UnicodeDecodeError, LookupError):
            continue
        if "�" not in texto:
            return texto.replace("+", " ")
    return valor.replace("+", " ")


def _json_desde(texto: str, variable: str):
    """Lee ``var nombre = {...};`` sin romperse si el JSON contiene ``};``."""
    marca = f"var {variable} ="
    posicion = texto.find(marca)
    if posicion < 0:
        marca = f"{variable} ="
        posicion = texto.find(marca)
    if posicion < 0:
        raise ErrorNavegacion(f"No encontré la variable «{variable}» en la respuesta.")
    inicio = posicion + len(marca)
    while inicio < len(texto) and texto[inicio] in " \t\r\n":
        inicio += 1
    try:
        datos, _ = json.JSONDecoder().raw_decode(texto, inicio)
    except ValueError as exc:
        raise ErrorNavegacion(f"La variable «{variable}» no es JSON válido: {exc}") from exc
    return datos


# --------------------------------------------------------------------------
# Cliente
# --------------------------------------------------------------------------
@dataclass
class Sesion:
    """Resultado del inicio de sesión."""

    rut_usado: str
    pagina_app: str
    intentos: list[str] = field(default_factory=list)


class EdufacilClient:
    def __init__(
        self,
        rut: str,
        password: str,
        *,
        timeout: int = 30,
        pausa: float = 1.0,
        pausa_llamadas: float = PAUSA_ENTRE_LLAMADAS,
        no_cerrar_sesion: bool = True,
        verbose: bool = False,
    ) -> None:
        self.rut = rut
        self.password = password
        self.timeout = timeout
        self.pausa = pausa
        self.pausa_llamadas = pausa_llamadas
        self.no_cerrar_sesion = no_cerrar_sesion
        self.verbose = verbose
        self.sesion = requests.Session()
        self.sesion.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                           "image/avif,image/webp,*/*;q=0.8"),
                "Accept-Language": "es-ES,es;q=0.9",
                "sec-ch-ua": '"Chromium";v="154", "Google Chrome";v="154", "Not A(Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "Upgrade-Insecure-Requests": "1",
            }
        )

    # -- logging ----------------------------------------------------------
    def _log(self, mensaje: str) -> None:
        if self.verbose:
            print(f"  · {mensaje}")

    # -- HTTP -------------------------------------------------------------
    def _get(self, url: str, params: dict | None = None) -> requests.Response:
        try:
            respuesta = self.sesion.get(url, params=params, timeout=self.timeout,
                                        allow_redirects=True)
        except requests.RequestException as exc:
            raise ErrorEdufacil(f"No se pudo conectar con edufacil.cl: {exc}") from exc
        return self._validar(respuesta)

    def _post(self, url: str, datos: dict) -> requests.Response:
        try:
            respuesta = self.sesion.post(url, data=datos, timeout=self.timeout,
                                         allow_redirects=True)
        except requests.RequestException as exc:
            raise ErrorEdufacil(f"No se pudo conectar con edufacil.cl: {exc}") from exc
        return self._validar(respuesta)

    def _validar(self, respuesta: requests.Response) -> requests.Response:
        destino = respuesta.url.lower()
        if "login.php" in destino or "salir.php" in destino:
            raise ErrorLogin(
                "La sesión ya no es válida (EduFácil redirigió al login). "
                "Vuelve a ejecutar el scraper."
            )
        return respuesta

    def obtener_pagina(self, url: str) -> tuple[str, BeautifulSoup]:
        respuesta = self._get(url)
        return respuesta.url, BeautifulSoup(respuesta.text, "lxml")

    def _json(self, url: str, datos: dict | None = None, metodo: str = "post"):
        """Llamada AJAX que devuelve JSON, con pausa para no golpear el servidor."""
        if self.pausa_llamadas:
            time.sleep(self.pausa_llamadas)
        try:
            if metodo == "post":
                respuesta = self.sesion.post(url, data=datos, timeout=self.timeout)
            else:
                respuesta = self.sesion.get(url, params=datos, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ErrorEdufacil(f"Falló la llamada a {url}: {exc}") from exc
        if respuesta.status_code in (403, 429):
            raise ErrorEdufacil(
                f"EduFácil/Cloudflare respondió {respuesta.status_code} en {url}. "
                "Espera un minuto y vuelve a ejecutar."
            )
        try:
            return respuesta.json()
        except ValueError as exc:
            raise ErrorEdufacil(
                f"Se esperaba JSON en {url} y llegó HTML/otro contenido."
            ) from exc

    # -- login ------------------------------------------------------------
    def login(self) -> Sesion:
        """Inicia sesión probando todos los formatos conocidos del RUT."""
        errores: list[str] = []
        for indice, rut in enumerate(variantes_rut(self.rut)):
            if indice:
                time.sleep(self.pausa)
            self._log(f"Probando RUT {rut}")
            datos: dict[str, str] = {"rut_usuario": rut, "pass": self.password}
            if self.no_cerrar_sesion:
                datos["no_cerrar_sesion"] = "yes"

            try:
                self.sesion.get(URL_LOGIN, timeout=self.timeout)
                respuesta = self.sesion.post(URL_CONTROL, data=datos, timeout=self.timeout,
                                             allow_redirects=True)
            except requests.RequestException as exc:
                raise ErrorEdufacil(f"No se pudo conectar con edufacil.cl: {exc}") from exc

            if "info=" in respuesta.url:
                mensaje = _mensaje_info(respuesta.url)
                errores.append(mensaje or "error desconocido")
                self._log(f"Rechazado: {mensaje}")
                continue

            app = self._get(URL_APP)
            if "aplicacion" not in app.url.lower():
                errores.append(f"la aplicación redirigió a {app.url}")
                continue

            self._log(f"Sesión iniciada con RUT {rut}")
            return Sesion(rut_usado=rut, pagina_app=app.url, intentos=errores)

        detalle = "; ".join(dict.fromkeys(errores)) or "sin detalle"
        raise ErrorLogin(
            f"No se pudo iniciar sesión con el RUT «{self.rut}». "
            f"El servidor respondió: {detalle}"
        )

    # -- menú -------------------------------------------------------------
    def documentos(self, url: str) -> list[tuple[str, BeautifulSoup]]:
        """Página principal más sus frames/iframes (el menú vive en un frame)."""
        final, sopa = self.obtener_pagina(url)
        documentos = [(final, sopa)]
        for etiqueta in sopa.find_all(["frame", "iframe"]):
            origen = etiqueta.get("src")
            if not origen or origen.startswith(("about:", "javascript:", "data:", "#")):
                continue
            direccion = urllib.parse.urljoin(final, origen)
            if not direccion.startswith("http"):
                continue
            try:
                documentos.append(self.obtener_pagina(direccion))
            except ErrorEdufacil as exc:
                self._log(f"No se pudo leer el frame {direccion}: {exc}")
            if len(documentos) > MAX_FRAMES:
                break
        return documentos

    @staticmethod
    def _resolver_href(href: str, base: str) -> str | None:
        href = (href or "").strip()
        if not href or href == "#" or href.lower().startswith("javascript"):
            return None
        direccion = urllib.parse.urljoin(base, href).split("#", 1)[0]
        return direccion if direccion.startswith("http") else None

    def buscar_enlace(self, url_base: str, claves: list[str]) -> tuple[str, str]:
        """Busca en el menú el enlace con más coincidencias de las claves dadas."""
        documentos = self.documentos(url_base)
        claves_norm = [normalizar(c) for c in claves]

        mejor: tuple[int, str, str, str, str] | None = None
        for base, sopa in documentos:
            for ancla in sopa.find_all("a"):
                texto = re.sub(r"\s+", " ", ancla.get_text(" ", strip=True))
                texto_norm = normalizar(texto)
                if not texto_norm:
                    continue
                coincidencias = sum(1 for clave in claves_norm if clave in texto_norm)
                if not coincidencias:
                    continue
                href = ancla.get("href")
                destino = self._resolver_href(href, base) if href else None
                puntaje = coincidencias * 100 + min(len(texto_norm), 60)
                candidato = (puntaje, texto, destino or "", ancla.get("onclick") or "", base)
                if mejor is None or candidato[0] > mejor[0]:
                    mejor = candidato

        if mejor is None:
            enlaces = sorted({
                re.sub(r"\s+", " ", a.get_text(" ", strip=True))
                for _, sopa in documentos for a in sopa.find_all("a")
            })
            raise ErrorNavegacion(
                "No encontré el menú «" + " / ".join(claves) + "».\n"
                "Enlaces disponibles:\n  - " + "\n  - ".join(t for t in enlaces if t)[:4000]
            )

        _, texto, destino, onclick, base = mejor
        if not destino and onclick:
            destino = self._url_desde_javascript(onclick, base)
        if not destino:
            raise ErrorNavegacion(
                f"El menú «{texto}» no apunta a una página "
                f"(onclick: {onclick or 'ninguno'}). Revisa el sitio a mano."
            )
        return texto, destino

    def _url_desde_javascript(self, onclick: str, base: str) -> str | None:
        """Traduce ``onclick="ircalendarioevaluaciones()"`` a su URL real.

        Esas funciones hacen ``parent['body'].document.location = "x.php"`` dentro
        de ``scripts/funciones.js``.
        """
        funcion = re.match(r"\s*([A-Za-z_$][\w$]*)\s*\(", onclick)
        if not funcion:
            return None
        nombre = funcion.group(1)
        try:
            js = self._get(URL_JS).text
        except ErrorEdufacil as exc:
            self._log(f"No pude leer funciones.js: {exc}")
            return None

        cuerpo = re.search(rf"function\s+{re.escape(nombre)}\s*\([^)]*\)\s*\{{", js)
        if not cuerpo:
            return None
        inicio = cuerpo.end()
        nivel, fin = 1, inicio
        while fin < len(js) and nivel:
            if js[fin] == "{":
                nivel += 1
            elif js[fin] == "}":
                nivel -= 1
            fin += 1
        bloque = cuerpo.group(0) + js[inicio:fin]

        objetivos = re.findall(
            r"""parent\s*\[\s*['"]body['"]\s*\]\s*\.\s*document\s*\.\s*location\s*=\s*['"]([^'"]+)['"]""",
            bloque,
        )
        if not objetivos:
            self._log(f"La función {nombre}() no asigna location de parent['body']")
            return None
        destino = urllib.parse.urljoin(base, objetivos[-1])
        self._log(f"{nombre}() -> {destino}")
        return destino

    # -- API del calendario ------------------------------------------------
    def parametros_alumno(self, url_pagina: str) -> dict:
        """Lee ``calendarioAlumnos = {...}`` de la página del calendario."""
        respuesta = self._get(url_pagina)
        if "calendarioAlumnos" not in respuesta.text:
            raise ErrorNavegacion(
                f"La página {url_pagina} no trae «calendarioAlumnos»: "
                "puede que el menú haya cambiado."
            )
        datos = _json_desde(respuesta.text, "calendarioAlumnos")
        self._log(f"Alumno/rut {datos.get('rut_alumno')} · curso {datos.get('codigo_curso')}")
        return datos

    def meses_y_subsectores(self, curso: str, sxc: str) -> tuple[list[dict], dict]:
        """Meses del año escolar y catálogo de asignaturas (subsectores)."""
        url = f"{BASE}/calendarioEvaluaciones/calendarioEvaluaciones.php"
        respuesta = self._get(url, params={"codigo_curso": curso, "sxc": sxc})
        meses = _json_desde(respuesta.text, "meses")
        subsectores = _json_desde(respuesta.text, "subsectores")
        self._log(f"Año escolar: {len(meses)} meses, {len(subsectores)} asignaturas")
        return meses, subsectores

    def calendario_mensual(self, curso: str, sxc: str, mes: str, anio: str) -> list[dict]:
        """Días de un mes con sus evaluaciones (JSON)."""
        url = f"{BASE}/calendarioEvaluaciones/obtenerCalendarioMensual.php"
        datos = self._json(url, {"codigo_curso": curso, "sxc": sxc, "mes": mes, "anio": anio})
        if datos.get("error"):
            raise ErrorEdufacil(f"Error al pedir el mes {mes}/{anio}: {datos.get('msj')}")
        dias = datos.get("calendario_mensual") or []
        # El endpoint devuelve también los días pegados al mes siguiente.
        return [d for d in dias if str(d.get("fecha_mes")) == str(int(mes))]

    def detalle_prueba(self, fecha: str, sxc, numero, sub_numero) -> dict | None:
        """Detalle de una evaluación: profesor, ponderación, contenido."""
        url = f"{BASE}/calendarioEvaluaciones/obtenerDatosPrueba.php"
        datos = self._json(url, {"fecha": fecha, "sxc": sxc, "numero": numero,
                                 "sub_numero": sub_numero})
        if datos.get("error"):
            self._log(f"Detalle no disponible para {fecha}: {datos.get('msj')}")
            return None
        return datos.get("prueba")
