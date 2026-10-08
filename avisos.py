# -*- coding: utf-8 -*-
"""Avisos por Web Push: el resumen del sábado y los cambios del calendario.

Sólo dos avisos, y ninguno diario:

* **Sábados** — el resumen de la semana que viene (el mismo que se ve en la
  página, en Outlook y en el `.ics`), calculado con las correcciones de la
  comunidad ya aplicadas, así que siempre refleja lo último. Si la semana que
  viene no tiene evaluaciones no hay resumen y no se avisa nada.
* **Cualquier otro día** — si algo cambió desde el último aviso llega el aviso
  **ese mismo día**: correcciones y altas de la comunidad (con el nombre de
  quien lo hizo) o cambios del propio sitio (EduFácil agregó, movió o sacó
  una prueba).

La cadena de las 07:00 corre `avisos.py` tras `main.py`, y la tarea por hora
(`avisos_dia.bat`, de 08:00 a 22:00) lo vuelve a correr para que una
corrección hecha a media tarde se anuncie el mismo día. Todo lo que se envía
se decide en `preparar_mensajes()`, que es pura y se prueba sin red; lo que
ya quedó contado vive en `logs/avisos_estado.json`:

    python avisos.py             # envía a quienes pulsaron «🔔 Avisos»
    python avisos.py --probar    # arma los mensajes y los imprime, sin enviar
    python avisos.py --probar-sabado   # manda el resumen del sábado, como prueba
    python avisos.py --sin-correcciones   # sólo el resumen del sábado

Requiere el bloque «avisos» de config.json (llave VAPID privada) y la tabla
«suscripciones» de Supabase (alta anónima con INSERT/SELECT). Quien no quiera
avisos no hace nada y la corrida sigue: si algo falla queda en
`logs/avisos.log` con código de salida 0 salvo configuración ilegible.

Las suscripciones caducas (HTTP 404/410) se anotan en
`logs/suscripciones_caducas.txt` y no se vuelven a intentar: la RLS no
permite borrarlas en la nube (append-only, igual que `ediciones`).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict, deque
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

# Consolas cp1252 de Windows: que un emoji no corte la corrida.
for _salida in (sys.stdout, sys.stderr):
    try:
        _salida.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

from edufacil import ediciones
from edufacil.semana import TIPO_RESUMEN, resumenes_semanales

RAIZ = Path(__file__).resolve().parent
CONFIG = RAIZ / "config.json"
LOGS = RAIZ / "logs"
ARCHIVO_JSON = RAIZ / "salida" / "calendario_evaluaciones.json"
CADUCAS = LOGS / "suscripciones_caducas.txt"
ESTADO = LOGS / "avisos_estado.json"
SUJETO_POR_DEFECTO = "https://edufacil.cl"


def registrar(mensaje: str) -> None:
    sello = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{sello}] {mensaje}"
    print(linea)
    try:
        LOGS.mkdir(exist_ok=True)
        with (LOGS / "avisos.log").open("a", encoding="utf-8") as archivo:
            archivo.write(linea + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Mensajes (funciones puras: se prueban sin red)
# ---------------------------------------------------------------------------
def _fecha_corta(valor) -> str:
    """`2026-10-08` -> `08-10` (si no se entiende, tal cual)."""
    try:
        d = date.fromisoformat(str(valor)[:10])
        return f"{d.day:02d}-{d.month:02d}"
    except ValueError:
        return str(valor)


def _corto(texto, tope=30) -> str:
    texto = str(texto or "").strip()
    return texto if len(texto) <= tope else texto[:tope - 1] + "…"


def _identidad(fila: dict) -> str:
    """`ASIGNATURA|NUMERO|TIPO` -> nombre legible."""
    base = str(fila.get("clave") or "").split("#")[0].split("|")
    nombre = (base[0] if base and base[0] else "corrección").strip()
    if len(base) > 1 and base[1].strip():
        nombre += f" n° {base[1].strip()}"
    return nombre


def _describir_correccion(fila: dict) -> str:
    """Una fila de la nube en una línea humana (sin emoji: lo pone quien llama)."""
    campos = fila.get("campos") if isinstance(fila.get("campos"), dict) else {}
    previo = fila.get("previo") if isinstance(fila.get("previo"), dict) else {}
    autor = str(fila.get("autor") or "").strip()
    sufijo = f" ({autor})" if autor else ""

    if str(fila.get("tipo") or "") == "nuevo":
        fecha = campos.get("FECHA")
        extra = f" · {_fecha_corta(fecha)}" if fecha else ""
        return f"Nueva: {_identidad(fila)}{extra}{sufijo}"

    partes = []
    for campo, valor in list(campos.items())[:3]:
        antes = previo.get(campo)
        if campo == "FECHA":
            if antes and str(antes) != str(valor):
                partes.append(f"fecha {_fecha_corta(antes)} → {_fecha_corta(valor)}")
            else:
                partes.append(f"fecha {_fecha_corta(valor)}")
        elif antes and str(antes) != str(valor):
            partes.append(f"{campo.lower()}: {str(antes)[:24]} → {str(valor)[:40]}")
        else:
            partes.append(f"{campo.lower()}: {str(valor)[:40]}")
    cuerpo = "; ".join(partes) or "campos varios"
    return f"{_identidad(fila)}: {cuerpo}{sufijo}"


def _describir_anulacion(fila: dict) -> str:
    """Un registro «anula» (alguien deshizo una corrección)."""
    autor = str(fila.get("autor") or "").strip()
    sufijo = f" ({autor})" if autor else ""
    if str(fila.get("clave") or "").strip():
        return f"{_identidad(fila)}: corrección anulada{sufijo}"
    return f"Corrección anulada{sufijo}"


# --- instantánea del calendario: para detectar cambios del sitio ------------
def instantanea(registros: list[dict], filas: list[dict] | None = None) -> dict:
    """Foto de las evaluaciones: ``{identidad: ["FECHA|EVALUACION", …]}``.

    Aplica antes las correcciones de la nube para que la foto sea la misma
    haya o no corrido `main.py`: así una corrección anunciada a media tarde
    no vuelve a anunciarse mañana como «cambio del sitio». Se copian los
    registros antes de aplicar, para no tocar la lista de origen.
    """
    base = [dict(registro) for registro in registros]
    if filas:
        try:
            base, _, _ = ediciones.aplicar(base, list(filas))
        except Exception:          # una fila rara no puede romper el aviso
            base = [dict(registro) for registro in registros]
    grupos: dict[str, list[str]] = {}
    for registro in base:
        if str(registro.get("TIPO") or "") == TIPO_RESUMEN:
            continue
        fecha = str(registro.get("FECHA") or "")
        if len(fecha) != 10:
            continue
        nombre = str(registro.get("EVALUACION") or "").strip()
        grupos.setdefault(ediciones.clave_base(registro), []).append(
            f"{fecha}|{nombre}")
    return {clave: sorted(valores) for clave, valores in sorted(grupos.items())}


def _emparejar(pend_v: list, pend_n: list, clave_de):
    """Une lo que coincide por `clave_de`: devuelve (pares, sobra_v, sobra_n)."""
    grupos: dict = defaultdict(deque)
    for item in pend_v:
        grupos[clave_de(item)].append(item)
    pares, sobra_n = [], []
    for item in pend_n:
        cola = grupos.get(clave_de(item))
        if cola:
            pares.append((cola.popleft(), item))
        else:
            sobra_n.append(item)
    sobra_v = [x for cola in grupos.values() for x in cola]
    return pares, sobra_v, sobra_n


def diff_instantaneas(vieja: dict, nueva: dict,
                      omitir: set[str] | None = None) -> list[str]:
    """Líneas humanas de lo que cambió entre dos instantáneas.

    Dentro de cada identidad se emparejan primero los elementos iguales, luego
    por fecha y después por nombre: mover una prueba se lee «17-10 → 16-10» y
    no como «una alta y una baja». `omitir` son identidades que ya cubre una
    corrección de la comunidad, para no contar la misma cosa dos veces.
    """
    omitir = omitir or set()
    lineas: list[str] = []
    for base in sorted(set(vieja) | set(nueva)):
        if base in omitir:
            continue
        cont_v = Counter(vieja.get(base) or [])
        cont_n = Counter(nueva.get(base) or [])
        comunes = cont_v & cont_n
        cont_v -= comunes
        cont_n -= comunes
        resto_v = sorted(cont_v.elements())
        resto_n = sorted(cont_n.elements())
        if not resto_v and not resto_n:
            continue
        nombre = _identidad({"clave": base})

        # misma fecha, distinto nombre (el profesor renombró la prueba)
        pares, resto_v, resto_n = _emparejar(
            resto_v, resto_n, lambda i: i.partition("|")[0])
        for viejo, nuevo in pares:
            fecha, _, nom_v = viejo.partition("|")
            _, _, nom_n = nuevo.partition("|")
            lineas.append(f"🔄 {nombre}: «{_corto(nom_v, 22)}» → "
                          f"«{_corto(nom_n, 22)}» ({_fecha_corta(fecha)})")

        # mismo nombre, otra fecha (la prueba se movió de día)
        pares, resto_v, resto_n = _emparejar(
            resto_v, resto_n, lambda i: i.partition("|")[2])
        for viejo, nuevo in pares:
            fecha_v, _, nom = viejo.partition("|")
            fecha_n, _, _ = nuevo.partition("|")
            lineas.append(f"🔄 {nombre}: {_fecha_corta(fecha_v)} → "
                          f"{_fecha_corta(fecha_n)} ({_corto(nom)})")

        for item in resto_v:
            fecha, _, nom = item.partition("|")
            lineas.append(f"➖ {nombre}: estaba {_fecha_corta(fecha)} "
                          f"({_corto(nom)})")
        for item in resto_n:
            fecha, _, nom = item.partition("|")
            lineas.append(f"➕ {nombre}: {_fecha_corta(fecha)} ({_corto(nom)})")
    return lineas


# --- cambios de la comunidad ------------------------------------------------
def _corte_iso(desde) -> datetime | None:
    try:
        corte = datetime.fromisoformat(str(desde).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if corte.tzinfo is None:
        corte = corte.replace(tzinfo=timezone.utc)
    return corte


def _filas_desde(filas: list[dict], desde) -> tuple[list[dict], list[dict]]:
    """(correcciones y altas, anulaciones) posteriores a `desde` (ISO).

    Las filas que otra fila anuló se saltan: de ellas sólo avisa su «↩️».
    """
    corte = _corte_iso(desde)
    if corte is None:
        return [], []
    canceladas = {str(f.get("anula")) for f in filas
                  if isinstance(f, dict) and f.get("anula")}
    recientes: list[dict] = []
    anulaciones: list[dict] = []
    for fila in filas:
        if not isinstance(fila, dict):
            continue
        creado = _corte_iso(fila.get("creado"))
        if creado is None or creado <= corte:
            continue
        tipo = str(fila.get("tipo") or "")
        if tipo == "anula":
            anulaciones.append(fila)
        elif tipo in ("correccion", "nuevo") and fila.get("id") \
                and str(fila["id"]) not in canceladas:
            recientes.append(fila)
    orden = lambda f: str(f.get("creado") or "")   # noqa: E731
    return sorted(recientes, key=orden), sorted(anulaciones, key=orden)


def _sello_nuevo(filas: list[dict], desde) -> str:
    """ISO del último cambio ya anunciado: lo anterior no se vuelve a contar."""
    corte = _corte_iso(desde)
    recientes, anulaciones = _filas_desde(filas, desde)
    for fila in recientes + anulaciones:
        creado = _corte_iso(fila.get("creado"))
        if creado is not None and (corte is None or creado > corte):
            corte = creado
    return (corte or datetime.now().astimezone()).isoformat()


def _lineas_de_cambios(registros: list[dict], filas: list[dict],
                       estado: dict) -> list[str]:
    """Líneas de lo que cambió desde el último aviso (comunidad y sitio)."""
    lineas: list[str] = []
    cubiertas: set[str] = set()

    desde = estado.get("ultima_edicion")
    if desde:
        recientes, anulaciones = _filas_desde(filas, desde)
        for fila in recientes:
            lineas.append("✏️ " + _describir_correccion(fila))
            clave = str(fila.get("clave") or "").strip()
            if clave:
                cubiertas.add(clave.split("#")[0])
        for fila in anulaciones:
            lineas.append("↩️ " + _describir_anulacion(fila))
            clave = str(fila.get("clave") or "").strip()
            if clave:
                cubiertas.add(clave.split("#")[0])

    vieja = estado.get("huellas")
    if isinstance(vieja, dict) and vieja:
        lineas += diff_instantaneas(vieja, instantanea(registros, filas),
                                    omitir=cubiertas)
    return lineas


def _resumen_de(registros: list[dict], hoy: date) -> dict | None:
    """El resumen del sábado `hoy` (si esa semana tiene evaluaciones)."""
    for fila in resumenes_semanales(registros):
        if str(fila.get("FECHA") or "") == hoy.isoformat():
            return fila
    return None


def _recorte(lineas: list[str], tope=4) -> str:
    if len(lineas) <= tope:
        return "\n".join(lineas)
    return "\n".join(lineas[:tope] + [f"+{len(lineas) - tope} más"])


def preparar_mensajes(registros: list[dict], filas: list[dict],
                      hoy: date | None = None,
                      estado: dict | None = None) -> list[dict]:
    """Payloads de notificación listos para enviar (sin red, bien testeable).

    * **Sábado** → el resumen de la semana que viene; si hubo cambios desde el
      último aviso cuelgan de él bajo un «Cambios:», así el resumen siempre
      sale actualizado con lo que se cambió.
    * **Cualquier otro día** → sólo los cambios (de la comunidad o del sitio),
      y sólo si los hay.
    * Sin cambios y sin resumen: sin mensajes — las evaluaciones de todos los
      días ya no avisan.
    """
    hoy = hoy or date.today()
    estado = estado or {}
    cambios = _lineas_de_cambios(registros, filas, estado)

    resumen = None
    if (hoy.weekday() == 5
            and str(estado.get("ultimo_resumen") or "") != hoy.isoformat()):
        resumen = _resumen_de(registros, hoy)

    if resumen is not None:
        cuerpo = str(resumen.get("CONTENIDO") or "").strip() or str(
            resumen.get("EVALUACION") or "").strip()
        if cambios:
            cuerpo += "\n\nCambios:\n" + _recorte(cambios)
        return [{
            "titulo": f"📚 Resumen del sábado: {resumen.get('EVALUACION')}",
            "cuerpo": cuerpo,
            "tag": "resumen",
            "incluye_cambios": bool(cambios),
        }]
    if cambios:
        hay_edicion = any(l.startswith(("✏️", "↩️")) for l in cambios)
        return [{
            "titulo": "✏️ Cambios en el calendario" if hay_edicion
                      else "🔄 El calendario cambió",
            "cuerpo": _recorte(cambios),
            "tag": "cambios",
        }]
    return []


# ---------------------------------------------------------------------------
# Estado: lo que ya quedó contado
# ---------------------------------------------------------------------------
def cargar_estado() -> dict:
    try:
        datos = json.loads(ESTADO.read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def guardar_estado(estado: dict) -> None:
    try:
        LOGS.mkdir(exist_ok=True)
        ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    except OSError as exc:
        registrar(f"no se pudo guardar el estado de los avisos: {exc}")


# ---------------------------------------------------------------------------
# Nube: suscripciones y envío
# ---------------------------------------------------------------------------
def mensaje_prueba() -> dict:
    """El aviso que manda `--enviar-prueba` (para probar el botón 🔔)."""
    return {
        "titulo": "🔔 Aviso de prueba",
        "cuerpo": "¡Así llegan los avisos! Los sábados verás el resumen de la "
                  "semana que viene y, si alguien corrige o cambia algo, te "
                  "avisamos ese mismo día.",
        "tag": "prueba",
    }


def mensajes_de_sabado(registros: list[dict],
                       hoy: date | None = None) -> list[dict]:
    """El aviso real del próximo sábado, para `--probar-sabado`.

    Calcula el mismo mensaje que se enviará el sábado (resumen puro, sin
    cambios ni estado) para poder verlo sin tocar nada de lo contado.
    """
    hoy = hoy or date.today()
    sabado = hoy + timedelta(days=(5 - hoy.weekday()) % 7)
    return [m for m in preparar_mensajes(registros, [], hoy=sabado, estado={})
            if m.get("tag") == "resumen"]


def cargar_suscripciones(sup: dict) -> list[dict]:
    respuesta = requests.get(
        f"{sup['url']}/rest/v1/suscripciones",
        headers={"apikey": sup["key"], "Accept": "application/json"},
        params={"select": "endpoint,p256dh,auth"}, timeout=20)
    respuesta.raise_for_status()
    filas = respuesta.json()
    return filas if isinstance(filas, list) else []


def leer_caducas() -> set[str]:
    try:
        return {linea.strip() for linea in
                CADUCAS.read_text(encoding="utf-8").splitlines() if linea.strip()}
    except OSError:
        return set()


def anotar_caduca(endpoint: str) -> None:
    try:
        caducas = leer_caducas()
        if endpoint in caducas:
            return
        LOGS.mkdir(exist_ok=True)
        with CADUCAS.open("a", encoding="utf-8") as archivo:
            archivo.write(endpoint + "\n")
    except OSError:
        pass


def enviar(sup: dict, avisos: dict, suscripcion: dict, mensaje: dict) -> str:
    """Un push. Devuelve 'ok', 'caduca' (404/410) o 'error'."""
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info={
                "endpoint": suscripcion["endpoint"],
                "keys": {"p256dh": suscripcion["p256dh"],
                         "auth": suscripcion["auth"]},
            },
            data=json.dumps({
                "titulo": mensaje["titulo"],
                "cuerpo": mensaje["cuerpo"],
                "url": "./",
                "tag": mensaje.get("tag") or "calendario",
            }, ensure_ascii=False),
            vapid_private_key=avisos["vapid_privada"],
            vapid_claims={"sub": str(avisos.get("sujetos") or SUJETO_POR_DEFECTO)},
        )
        return "ok"
    except WebPushException as exc:
        codigo = getattr(getattr(exc, "response", None), "status_code", None)
        if codigo in (404, 410):
            return "caduca"
        registrar(f"  fallo del envío (HTTP {codigo}): {str(exc)[:120]}")
        return "error"
    except Exception as exc:  # noqa: BLE001 - un push jamás corta la corrida
        registrar(f"  fallo del envío: {str(exc)[:140]}")
        return "error"


# ---------------------------------------------------------------------------
# Corrida completa
# ---------------------------------------------------------------------------
def principal(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Avisos por Web Push: resumen del sábado y cambios.")
    parser.add_argument("--probar", action="store_true",
                        help="arma los mensajes y los imprime, sin enviar")
    parser.add_argument("--sin-correcciones", action="store_true",
                        help="sólo el resumen del sábado (no consulta la nube)")
    parser.add_argument("--enviar-prueba", action="store_true",
                        help="manda un aviso de prueba a los suscritos aunque "
                             "hoy no toque (para verificar el botón 🔔)")
    parser.add_argument("--probar-sabado", action="store_true",
                        help="manda a los suscritos el resumen real del "
                             "próximo sábado, sin tocar el estado")
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args(argv)

    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        registrar(f"No se pudo leer {args.config.name}: {exc}")
        return 1

    sup = config.get("supabase") or {}
    avisos = config.get("avisos") or {}
    if not sup or not str(avisos.get("vapid_privada") or "").strip():
        registrar("Avisos no configurados (falta «supabase» o «avisos."
                  "vapid_privada»): nada que hacer")
        return 0
    clave_sup = str(sup.get("anon_key") or sup.get("key") or "")
    if not clave_sup or not sup.get("url"):
        registrar("Supabase mal configurado en config.json: no se envía nada")
        return 0

    try:
        datos = json.loads(ARCHIVO_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        registrar(f"No hay salida/calendario_evaluaciones.json ({exc}): "
                  "corre `python main.py` primero")
        return 1
    registros = datos.get("registros") or []

    filas: list[dict] = []
    nube_ok = True
    if not args.sin_correcciones:
        try:
            nube = ediciones.cargar_nube(config)
            if nube is None:
                nube_ok = False
            else:
                filas = ediciones.obtener_filas(nube)
        except ediciones.ErrorNube as exc:
            nube_ok = False
            registrar(f"Supabase no responde ({exc}): sólo el resumen, "
                      "sin cambios")

    # Sin nube no se toca el estado de cambios: lo que quedó pendiente se
    # cuenta en la próxima corrida buena (si no, se anunciaría «al revés»).
    cambios_activos = nube_ok and not args.sin_correcciones
    hoy = date.today()
    estado = cargar_estado()
    estado_prepara = estado if cambios_activos else {
        "ultimo_resumen": estado.get("ultimo_resumen")}

    mensajes = preparar_mensajes(registros, filas, hoy=hoy,
                                 estado=estado_prepara)
    if args.probar_sabado:
        mensajes = mensajes_de_sabado(registros, hoy=hoy)
        if not mensajes:
            registrar("--probar-sabado: la semana que viene no tiene "
                      "resumen de sábado para probar")
            return 0
    if args.enviar_prueba:
        mensajes = [mensaje_prueba()]
    if args.probar:
        print(json.dumps(mensajes, ensure_ascii=False, indent=2))
        return 0

    por_resumen = {i for i, m in enumerate(mensajes)
                   if m.get("tag") == "resumen"}
    por_cambios = {i for i, m in enumerate(mensajes)
                   if m.get("tag") == "cambios" or m.get("incluye_cambios")}

    if not mensajes:
        registrar("Sin cambios ni resumen pendiente: no se envía nada")
        if cambios_activos:                     # 1ª corrida: sólo la instantánea
            nuevo = dict(estado)
            nuevo.setdefault("huellas", instantanea(registros, filas))
            nuevo.setdefault("ultima_edicion",
                             datetime.now().astimezone().isoformat())
            guardar_estado(nuevo)
        return 0

    try:
        suscripciones = cargar_suscripciones(
            {"url": sup["url"], "key": clave_sup})
    except requests.RequestException as exc:
        registrar(f"No se pudo leer las suscripciones ({exc}): no se envía nada")
        return 1
    caducas = leer_caducas()
    vivas = [s for s in suscripciones
             if s.get("endpoint") and s["endpoint"] not in caducas]
    if not vivas:
        registrar("0 suscripciones vivas: nadie ha pulsado «🔔 Avisos» todavía "
                  "(lo pendiente queda para la próxima corrida)")
        return 0

    sup_envio = {"url": sup["url"], "key": clave_sup}
    enviados = fallidos = fuera = 0
    entregados: set[int] = set()
    for suscripcion in vivas:
        for indice, mensaje in enumerate(mensajes):
            resultado = enviar(sup_envio, avisos, suscripcion, mensaje)
            if resultado == "ok":
                enviados += 1
                entregados.add(indice)
            elif resultado == "caduca":
                fuera += 1
                anotar_caduca(suscripcion["endpoint"])
                break                       # ya no sirve esta suscripción
            else:
                fallidos += 1

    # El estado sólo avanza con lo que de verdad llegó: si un envío falló,
    # queda pendiente y la próxima corrida lo reintenta. Las pruebas
    # (--enviar-prueba, --probar-sabado) jamás tocan el estado.
    if not (args.enviar_prueba or args.probar_sabado):
        nuevo = dict(estado)
        if cambios_activos:
            if entregados & por_cambios:
                nuevo["huellas"] = instantanea(registros, filas)
                nuevo["ultima_edicion"] = _sello_nuevo(
                    filas, estado.get("ultima_edicion"))
            elif not por_cambios:
                nuevo.setdefault("huellas", instantanea(registros, filas))
                nuevo.setdefault("ultima_edicion",
                                 datetime.now().astimezone().isoformat())
        if entregados & por_resumen:
            nuevo["ultimo_resumen"] = hoy.isoformat()
        guardar_estado(nuevo)

    resumen = (f"Avisos: {enviados} enviados, {fallidos} con error, "
               f"{fuera} caducas · {len(vivas)} suscripciones vivas de "
               f"{len(suscripciones)}")
    registrar(resumen)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(principal())
    except KeyboardInterrupt:
        print("\nCancelado.")
        sys.exit(130)
