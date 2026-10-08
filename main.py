# -*- coding: utf-8 -*-
"""Punto de entrada: entra a EduFácil, baja el Calendario de Evaluaciones y lo exporta.

Flujo real del sitio (descubierto en vivo):
  1. POST control3.php                    -> sesión
  2. frameset estudiantes/aplicacion.php  -> frame menu.php
  3. enlace «Calendario evaluaciones»     -> onclick -> funciones.js -> calendario.php
  4. calendario.php                       -> variable calendarioAlumnos (curso y subsector)
  5. calendarioEvaluaciones.php           -> meses del año y asignaturas
  6. obtenerCalendarioMensual.php         -> días + evaluaciones (JSON), por mes
  7. obtenerDatosPrueba.php               -> profesor y ponderación, por evaluación

Uso:
    python main.py                      # exporta a Excel, CSV y JSON
    python main.py --probar-login       # sólo valida las credenciales
    python main.py --sin-detalle        # omite profesor/ponderación (más rápido)
    python main.py --formatos csv,json  # formatos concretos
    python main.py --sin-nube           # ignora las correcciones comunitarias

Correcciones comunitarias (Supabase):
    la página permite corregir una fecha o agregar una evaluación; esas filas
    se leen en cada corrida y se aplican encima del scrapeo (Excel/CSV/JSON/
    .ics y Outlook quedan corregidos a las 07:00).  Ver edufacil/ediciones.py
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Las consolas de Windows suelen venir en cp1252: sin esto, un carácter como «→»
# rompe la ejecución con UnicodeEncodeError. Aquí se degrada a «?» y sigue.
for _salida in (sys.stdout, sys.stderr):
    try:
        _salida.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

from edufacil.outlook import CARPETA_POR_DEFECTO as CARPETA_OUTLOOK
from edufacil.outlook import ErrorOutlook, exportar_a_outlook
from edufacil.semana import resumenes_semanales
from edufacil import ediciones
from edufacil import (
    EdufacilClient,
    ErrorEdufacil,
    agregar_detalle,
    a_csv,
    a_excel,
    a_html,
    a_json,
    limpiar,
    ordenar,
    registros_desde_dias,
)

RAIZ = Path(__file__).resolve().parent
CONFIG = RAIZ / "config.json"
CARPETA_SALIDA = RAIZ / "salida"
CARPETA_DEBUG = RAIZ / "debug"

MENU_CALENDARIO = ["CALENDARIO DE EVALUACIONES", "CALENDARIO", "EVALUACIONES"]
FORMATOS_TODOS = ("xlsx", "csv", "json", "html")


def cargar_configuracion(ruta: Path) -> dict:
    """Devuelve el JSON completo: credenciales + bloque «supabase» opcional."""
    import json

    if not ruta.exists():
        sys.exit(
            f"No encuentro {ruta.name}. Copia config.example.json a config.json "
            "y pon ahí tu RUT y contraseña."
        )
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except ValueError as exc:
        sys.exit(f"{ruta.name} no es un JSON válido: {exc}")
    if not isinstance(datos, dict) or "rut" not in datos or "password" not in datos:
        sys.exit(f"{ruta.name} necesita al menos «rut» y «password».")
    return datos


def _normalizar_fecha(valor: str | None) -> str | None:
    """Acepta «2026-10» o «2026-10-01» y devuelve «2026-10-01»."""
    if not valor:
        return None
    import re

    texto = str(valor).strip()
    if re.fullmatch(r"\d{4}-\d{2}", texto):
        return texto + "-01"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", texto):
        return texto
    sys.exit(f"--outlook-desde no se entiende: {texto!r}. Usa AAAA-MM-DD (p.ej. 2026-10-01).")


def registrar(mensaje: str) -> None:
    sello = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{sello}] {mensaje}"
    print(linea)
    try:
        log = RAIZ / "logs"
        log.mkdir(exist_ok=True)
        with (log / "ejecucion.log").open("a", encoding="utf-8") as archivo:
            archivo.write(linea + "\n")
    except OSError:
        pass


def cargar_correcciones(config: dict, sin_nube: bool) -> tuple[object, list[dict]]:
    """(config de la nube, filas de correcciones). Nunca corta la corrida.

    Si Supabase no responde se cae al respaldo local de la corrida anterior;
    si tampoco hay respaldo, se sigue sin correcciones.
    """
    if sin_nube:
        return None, []
    try:
        cfg = ediciones.cargar_nube(config)
    except ediciones.ErrorNube as exc:
        registrar(f"Correcciones comunitarias mal configuradas: {exc}")
        return None, []
    if cfg is None:
        return None, []

    try:
        filas = ediciones.obtener_filas(cfg)
    except ediciones.ErrorNube as exc:
        filas = ediciones.leer_respaldo(RAIZ / "logs" / "ediciones.json")
        if filas:
            registrar(f"Supabase no responde ({exc}); se aplican "
                      f"{len(filas)} correcciones del respaldo local")
        else:
            registrar(f"Supabase no responde ({exc}); se sigue sin correcciones")
        return cfg, filas

    ediciones.respaldar(filas, RAIZ / "logs" / "ediciones.json")
    uno = "" if len(filas) == 1 else "s"
    registrar(f"Correcciones comunitarias: {len(filas)} registro{uno} en Supabase")
    return cfg, filas


def registrar_ediciones(est: dict, resumenes: bool = False) -> None:
    partes = []
    if est.get("corregidas"):
        n = est["corregidas"]
        partes.append(f"{n} corrección" if n == 1 else f"{n} correcciones")
    if est.get("agregadas"):
        n = est["agregadas"]
        partes.append(f"{n} alta" if n == 1 else f"{n} altas")
    if est.get("caducas"):
        n = est["caducas"]
        partes.append(f"{n} caducada" if n == 1 else f"{n} caducadas")
    if est.get("sin_destino"):
        partes.append(f"{est['sin_destino']} sin destino")
    if est.get("anuladas"):
        n = est["anuladas"]
        partes.append(f"{n} anulación" if n == 1 else f"{n} anulaciones")
    if not partes:
        return                       # nada activo: ya se informó cuántas filas hay
    etiqueta = "Resúmenes corregidos" if resumenes else "Correcciones"
    registrar(f"{etiqueta}: " + ", ".join(partes))
    for aviso in est.get("avisos", [])[:8]:
        registrar(f"  · {aviso}")


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Descarga el Calendario de Evaluaciones de EduFácil.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", type=Path, default=CONFIG,
                        help="archivo con RUT y contraseña")
    parser.add_argument("--salida", type=Path, default=CARPETA_SALIDA,
                        help="carpeta donde se guardan los archivos")
    parser.add_argument("--formatos", default=",".join(FORMATOS_TODOS),
                        help="xlsx,csv,json,html o 'todos'")
    parser.add_argument("--probar-login", action="store_true",
                        help="sólo valida las credenciales y sale")
    parser.add_argument("--sin-detalle", action="store_true",
                        help="no pide profesor ni ponderación (una llamada por evaluación)")
    parser.add_argument("--outlook", action="store_true",
                        help="crea las citas directamente en el calendario de Outlook")
    parser.add_argument("--outlook-limite", type=int, default=None, metavar="N",
                        help="crea sólo las primeras N citas de Outlook (para probar)")
    parser.add_argument("--outlook-desde", default=None, metavar="AAAA-MM-DD",
                        help="en Outlook, sólo evalúa desde esa fecha (p.ej. 2026-10-01). "
                             "Los archivos de salida siguen completos")
    parser.add_argument("--outlook-carpeta", default=CARPETA_OUTLOOK, metavar="NOMBRE",
                        help="carpeta de «Mis Calendarios» donde se crean las citas; "
                             "vacío = calendario principal")
    parser.add_argument("--outlook-purgar", action="store_true",
                        help="borra de Outlook las evaluaciones que ya no aparecen "
                             "en el sitio (por defecto nunca se borra nada)")
    parser.add_argument("--sin-resumen", action="store_true",
                        help="no agrega el resumen del sábado (sábado anterior "
                             "con las evaluaciones de esa semana)")
    parser.add_argument("--sin-nube", action="store_true",
                        help="no consulta Supabase: usa sólo lo que dice "
                             "EduFácil (las correcciones de la página se ignoran)")
    parser.add_argument("--sin-recordatorio", action="store_true",
                        help="sin aviso 1 día antes en las citas de Outlook")
    parser.add_argument("--menu", nargs="+", default=MENU_CALENDARIO,
                        help="texto del menú que se debe abrir")
    parser.add_argument("--guardar-html", action="store_true",
                        help="guarda las respuestas crudas en debug/ para depurar")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="muestra detalle de cada paso")
    return parser.parse_args()


def obtener_registros(cliente: EdufacilClient, args) -> tuple[list[dict], dict]:
    """Recorre el menú y baja todo el año escolar. Devuelve registros y metadatos."""
    meta: dict = {}
    texto, url_pagina = cliente.buscar_enlace(args.menu_base, args.menu)
    registrar(f"Menú «{texto}» -> {url_pagina}")

    alumno = cliente.parametros_alumno(url_pagina)
    curso, sxc = alumno["codigo_curso"], alumno["codigo_subsector"]
    meta.update({"alumno_rut": alumno.get("rut_alumno", ""),
                 "codigo_curso": curso, "pagina": url_pagina})

    meses, subsectores = cliente.meses_y_subsectores(curso, sxc)
    meta["ano_escolar"] = f"{meses[0]['anio']}-{meses[-1]['anio']}" if meses else ""
    meta["meses"] = [f"{m['mes_nombre']} {m['anio']}" for m in meses]
    registrar("Año escolar: " + ", ".join(meta["meses"]))

    dias: list[dict] = []
    for mes in meses:
        dias += cliente.calendario_mensual(curso, sxc, mes["mes"], mes["anio"])
    registrar(f"{len(dias)} días leídos en {len(meses)} meses")

    registros = registros_desde_dias(dias, subsectores)
    if args.guardar_html:
        import json as _json

        carpeta = CARPETA_DEBUG
        carpeta.mkdir(exist_ok=True)
        destino = carpeta / f"calendario_{datetime.now():%Y%m%d_%H%M%S}.json"
        destino.write_text(_json.dumps({"dias": dias, "subsectores": subsectores},
                                       ensure_ascii=False, indent=2), encoding="utf-8")
        registrar(f"Respuesta cruda guardada en {destino}")

    if not args.sin_detalle:
        registrar(f"Descargando detalle de {len(registros)} evaluaciones…")
        for posicion, registro in enumerate(registros, start=1):
            try:
                detalle = cliente.detalle_prueba(registro["_fecha"], registro["_sxc"],
                                                 registro["_numero"], registro["_subnumero"])
            except ErrorEdufacil as exc:
                registrar(f"  detalle {posicion}/{len(registros)} omitido: {exc}")
                detalle = None
            agregar_detalle(registro, detalle)
        registrar("Detalle completado")

    return registros, meta


def main() -> int:
    args = argumentos()
    config = cargar_configuracion(args.config)
    rut, password = str(config["rut"]), str(config["password"])

    registrar(f"Inicio · RUT {rut}")
    cliente = EdufacilClient(rut, password, verbose=args.verbose)

    try:
        sesion = cliente.login()
    except ErrorEdufacil as exc:
        registrar(f"ERROR DE LOGIN: {exc}")
        return 2

    registrar(f"Sesión iniciada con {sesion.rut_usado}")
    if args.probar_login:
        print("\n✔ Credenciales correctas. El scraper está listo.")
        return 0

    args.menu_base = sesion.pagina_app
    try:
        registros, meta = obtener_registros(cliente, args)
    except ErrorEdufacil as exc:
        registrar(f"ERROR AL DESCARGAR: {exc}")
        return 3

    if not registros:
        registrar("No se encontró ninguna evaluación en el año escolar.")
        return 4

    registros = ordenar(registros)
    registrar(f"{len(registros)} evaluaciones "
              f"(del {registros[0]['FECHA']} al {registros[-1]['FECHA']})")

    exportables = limpiar(registros)
    recordatorio = None if args.sin_recordatorio else 1440

    # Llave pública VAPID: si está en config.json, la página ofrece «🔔 Avisos».
    clave_avisos = str(
        (config.get("avisos") or {}).get("vapid_publica") or "").strip() or None
    if clave_avisos:
        registrar("Avisos diarios: habilitados (Web Push con llave VAPID)")

    # Correcciones hechas por la comunidad desde la página (Supabase): el
    # scrapeo es la base y lo corregido se aplica encima.
    nube, filas = cargar_correcciones(config, args.sin_nube)
    if filas:
        exportables, claves, est = ediciones.aplicar(exportables, filas)
        registrar_ediciones(est)
    else:
        claves = ediciones.claves_unicas(exportables)

    # Se reordena por fecha perdiendo el parejo: cada registro conserva su
    # clave de identidad (la que usa la página para señalarlo).
    por_objeto = {id(r): k for r, k in zip(exportables, claves)}
    exportables = ordenar(exportables)
    claves = [por_objeto[id(r)] for r in exportables]

    # El resumen del sábado se agrega a Outlook, nunca a Excel/CSV/JSON.
    resumenes = [] if args.sin_resumen else resumenes_semanales(exportables)
    if resumenes:
        registrar(f"Resúmenes semanales: {len(resumenes)} sábados "
                  f"({resumenes[0]['FECHA']} al {resumenes[-1]['FECHA']})")
    claves_resumen: list[str] = []
    if resumenes:
        if filas:
            resumenes, claves_resumen, est = ediciones.aplicar(
                resumenes, filas, resumenes=True)
            if any(est.get(c) for c in ("corregidas", "caducas", "sin_destino")):
                registrar_ediciones(est, resumenes=True)
        else:
            claves_resumen = ediciones.claves_unicas(resumenes)

    formatos = [f.strip().lower() for f in args.formatos.split(",") if f.strip()]
    if "todos" in formatos:
        formatos = list(FORMATOS_TODOS)
    base = args.salida / "calendario_evaluaciones"

    try:
        for formato in formatos:
            if formato in ("xlsx", "excel"):
                ruta = a_excel(exportables, base.with_suffix(".xlsx"))
            elif formato == "csv":
                ruta = a_csv(exportables, base.with_suffix(".csv"))
            elif formato == "json":
                ruta = a_json(exportables, base.with_suffix(".json"), meta)
            elif formato in ("html", "web"):
                ruta = a_html(exportables + resumenes,
                              base.with_suffix(".html"),
                              recordatorio_min=recordatorio,
                              nube=nube,
                              claves=claves + claves_resumen,
                              avisos_clave=clave_avisos)
            else:
                registrar(f"Formato desconocido, se omite: {formato}")
                continue
            registrar(f"Guardado: {ruta}")
    except RuntimeError as exc:
        registrar(f"ERROR AL EXPORTAR: {exc}")
        return 5

    if args.outlook:
        desde = _normalizar_fecha(args.outlook_desde)
        para_outlook = exportables
        resumenes_outlook = resumenes
        if desde:
            para_outlook = [r for r in exportables
                            if (r.get("FECHA") or "") >= desde]
            resumenes_outlook = [r for r in resumenes
                                 if (r.get("FECHA") or "") >= desde]
            registrar(f"Outlook: {len(para_outlook)} de {len(exportables)} "
                      f"evaluaciones desde {desde}")
            if not para_outlook and not resumenes_outlook:
                registrar("No hay evaluaciones desde esa fecha; nada que crear.")
                registrar("Listo")
                return 0
        registrar(f"Sincronizando con Outlook: {len(para_outlook)} evaluaciones "
                  f"+ {len(resumenes_outlook)} resúmenes de sábado…")
        try:
            resumen = exportar_a_outlook(
                para_outlook + resumenes_outlook,
                carpeta_nombre=args.outlook_carpeta,
                recordatorio_min=recordatorio,
                limite=args.outlook_limite,
                purgar=args.outlook_purgar,
                verbose=args.verbose,
            )
        except ErrorOutlook as exc:
            registrar(f"ERROR DE OUTLOOK: {exc}")
            return 6
        sin_pareja = resumen.get("sin_pareja", 0)
        extra = (f" | {sin_pareja} sin pareja "
                 f"(usa --outlook-purgar si quieres borrarlas)") if sin_pareja else ""
        registrar(
            f"Outlook: {resumen['creadas']} nuevas, "
            f"{resumen['actualizadas']} actualizadas, "
            f"{resumen['omitidas']} sin cambios, "
            f"{resumen['borradas']} borradas{extra} "
            f"-> «{resumen['carpeta']}»"
        )

    registrar("Listo")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nCancelado.")
        sys.exit(130)
    except ErrorEdufacil as exc:
        registrar(f"ERROR: {exc}")
        sys.exit(1)
