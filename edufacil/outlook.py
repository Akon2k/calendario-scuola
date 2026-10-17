# -*- coding: utf-8 -*-
"""Exportación directa al calendario de Outlook (escritorio, Windows).

Requiere Outlook instalado y `pywin32` (``pip install pywin32``).

Las citas se guardan en su propia carpeta de *Mis Calendarios*, **Scuola
Rafaela** (se crea sola si no existe, y el nombre es configurable con
``--outlook-carpeta``), para no mezclarlas con el calendario personal.

Cada evaluación se crea como **cita de día completo** con:
* asunto  ``ASIGNATURA: EVALUACION (N° x)``
* cuerpo  con todos los datos (contenido, profesor, coeficiente…)
* recordatorio 1 día antes (o el que se indique)
* categoría ``EvaScuola`` → así puedes borrar todo lo importado de una vez
  desde Outlook (clic derecho en la categoría → Eliminar categoría y elementos)

**No se duplican aunque cambien las fechas.** Cada cita se identifica por su
*clave estable* (asignatura + número + tipo, o la fecha del sábado para los
resúmenes semanales), nunca por la fecha. Si una evaluación se muda de día se
**actualiza la cita existente**; sólo se crea una nueva cuando no hay con qué
emparejarla. El emparejamiento es por la fecha más cercana, de modo que las dos
«E1» que puede tener una misma asignatura en el año no se pisen.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta

from .semana import TIPO_RESUMEN, campos_item, nombre_solo

OL_FOLDER_CALENDAR = 9     # olFolderCalendar (también en Folders.Add)
OL_APPOINTMENT = 1         # olAppointmentItem
OL_FREE = 0                # olFree: no bloquea el horario
CATEGORIA = "EvaScuola"
CARPETA_POR_DEFECTO = "Scuola Rafaela"   # aparece en «Mis Calendarios»


class ErrorOutlook(Exception):
    """No se pudo hablar con Outlook."""


def _sesion():
    try:
        import win32com.client as win32  # noqa: WPS433 (import tardío a propósito)
    except ImportError as exc:
        raise ErrorOutlook(
            "Falta pywin32. Instálalo con: pip install pywin32"
        ) from exc
    try:
        aplicacion = win32.Dispatch("Outlook.Application")
        sesion = aplicacion.GetNamespace("MAPI")
    except Exception as exc:
        raise ErrorOutlook(
            f"No pude conectar con Outlook: {exc}. "
            "Abre Outlook y vuelve a intentarlo."
        ) from exc
    if sesion.GetDefaultFolder(OL_FOLDER_CALENDAR) is None:
        raise ErrorOutlook("Outlook no tiene una carpeta de calendario configurada.")
    return sesion


def _carpeta(sesion, nombre: str | None):
    """Carpeta destino en «Mis Calendarios»; la crea si aún no existe.

    Devuelve ``(carpeta, se_acaba_de_crear)``. Si el nombre viene vacío o
    coincide con el calendario principal, se usa ese sin crear nada.
    """
    defecto = sesion.GetDefaultFolder(OL_FOLDER_CALENDAR)
    nombre = (nombre or "").strip()
    if not nombre or nombre == defecto.Name:
        return defecto, False

    raiz = defecto.Parent          # nivel de «Mis Calendarios»
    try:
        for hermana in raiz.Folders:
            if hermana.Name == nombre:
                return hermana, False
    except Exception:
        pass

    try:
        nueva = raiz.Folders.Add(nombre, OL_FOLDER_CALENDAR)
    except Exception as exc:
        raise ErrorOutlook(
            f"No pude crear la carpeta «{nombre}» en Mis Calendarios: {exc}"
        ) from exc
    return nueva, True


# --------------------------------------------------------------------------
# Identidad estable (la clave que evita duplicados)
# --------------------------------------------------------------------------
def _clave(registro: dict) -> str:
    """Identidad del registro que **no cambia si cambia la fecha**.

    Las evaluaciones se identifican por asignatura + número + tipo; el texto
    de la evaluación y la fecha quedan fuera a propósito: si el profesor
    mueve la prueba o la renombra, hay que actualizar la misma cita.
    Los resúmenes semanales se identifican por su sábado.
    """
    if registro.get("TIPO") == TIPO_RESUMEN:
        return f"SEMANA|{registro.get('FECHA') or ''}"
    asignatura = str(registro.get("ASIGNATURA") or "").strip().upper()
    numero = str(registro.get("NUMERO") or "").strip()
    tipo = str(registro.get("TIPO") or "").strip().upper()
    return f"{asignatura}|{numero}|{tipo}"


def _etiqueta_normalizada(texto: str) -> str:
    """«Número» → «NUMERO» (sin acentos): `upper()` deja el acento y rompe
    la comparación con las claves de los registros)."""
    sin_acentos = unicodedata.normalize("NFD", str(texto)).encode(
        "ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9]+", "", sin_acentos).upper()


def _campos_desde_cuerpo(cuerpo: str) -> dict[str, str]:
    """Lee las líneas «CLAVE: valor» que esta herramienta escribe en el cuerpo."""
    campos: dict[str, str] = {}
    for linea in (cuerpo or "").splitlines():
        clave, separador, valor = linea.partition(":")
        if not separador or not clave.strip() or len(clave) > 40:
            continue
        campos.setdefault(_etiqueta_normalizada(clave), valor.strip())
    return campos


def _clave_desde_campos(campos: dict[str, str]) -> str:
    """Identidad leída de las líneas «Etiqueta: valor» de un cuerpo.

    El cuerpo escribe «Número» y «Sub-número» por separado, igual que los
    diálogos de la fuente, pero la identidad sigue siendo el «2.2» crudo
    del registro: aquí se vuelven a juntar para que la misma cita no se
    duplique.
    """
    tipo = campos.get("TIPO", "")
    if tipo.upper() == TIPO_RESUMEN.upper():
        return f"SEMANA|{campos.get('FECHA', '')}"
    asignatura = campos.get("ASIGNATURA", "")
    if not asignatura:
        return ""
    numero = campos.get("NUMERO", "")
    sub = campos.get("SUBNUMERO", "")
    if sub and "." not in numero:
        numero = f"{numero}.{sub}"
    return "|".join([asignatura.upper(), numero, tipo.upper()])


def _clave_cita(item) -> str:
    """Clave de una cita ya existente, leída de su propio cuerpo."""
    return _clave_desde_campos(
        _campos_desde_cuerpo(getattr(item, "Body", "") or ""))


def _existe_en(carpeta) -> tuple[dict, dict]:
    """(índice por clave, índice de respaldo por fecha+asunto) de las citas.

    Las citas legibles van sólo al primer índice: así nunca se emparejan dos
    veces la misma (evita que un registro «robe» la cita de otro).
    """
    por_clave: dict[str, list[tuple]] = {}
    por_fecha: dict[tuple, list] = {}
    try:
        items = carpeta.Items.Restrict(f"[Categories] = '{CATEGORIA}'")
    except Exception:
        return por_clave, por_fecha   # sin filtro no deduplicamos a ciegas

    for item in items:
        try:
            fecha = item.Start.date()
            asunto = item.Subject or ""
        except Exception:
            continue
        clave = _clave_cita(item)
        if clave:
            por_clave.setdefault(clave, []).append((item, fecha))
        else:                          # cuerpo ilegible: respaldo por fecha
            por_fecha.setdefault((fecha, asunto), []).append(item)
    return por_clave, por_fecha


def _tomar(indice: dict, clave: str, fecha: date):
    """Saca del índice la cita con la fecha más cercana a la indicada."""
    lista = indice.get(clave)
    if not lista:
        return None
    posicion = min(range(len(lista)),
                   key=lambda i: abs((lista[i][1] - fecha).days))
    cita, _ = lista.pop(posicion)
    return cita


# --------------------------------------------------------------------------
# Creación y actualización
# --------------------------------------------------------------------------
def _asunto(registro: dict) -> str:
    """Título de la cita, igual que el de la página: la asignatura y el
    nombre **sin el «E3:»/«SE2-2:»** que trae la lista y sin el «(N° 3)»
    que la fuente no enseña en su detalle."""
    asignatura = str(registro.get("ASIGNATURA") or "").strip()
    evaluacion = nombre_solo(registro.get("EVALUACION"))
    if asignatura and evaluacion:
        return f"{asignatura}: {evaluacion}"
    return asignatura or evaluacion or "Evaluación"


def _cuerpo(registro: dict) -> str:
    """El cuerpo de la cita: los mismos campos, en el mismo orden y con las
    mismas etiquetas que el `.ics` que se descarga de la página."""
    lineas = campos_item(registro, con_tipo=True)
    lineas.append("")
    lineas.append("Descargado de EduFácil por CalendarioEvaScuola")
    return "\r\n".join(linea.replace("\r\n", "\n").replace("\n", "\r\n")
                       for linea in lineas)


def _mismo_cuerpo(guardado: str, nuevo: str) -> bool:
    """Compara cuerpos ignorando lo que Outlook normaliza solo.

    Al guardar y releer ``Body``, Outlook agrega un espacio antes de cada salto
    de línea y parte las líneas largas en párrafos vacíos (9 líneas escritas
    se leen 11). Con los espacios colapsados el texto vuelve a coincidir, y un
    cambio real de contenido sigue detectándose.
    """
    return " ".join((guardado or "").split()) == " ".join((nuevo or "").split())


def _aplicar(cita, registro: dict, fecha: date, asunto: str,
             recordatorio_min: int | None) -> bool:
    """Escribe los datos en la cita. Devuelve True si hubo cambios."""
    cambios = False
    es_resumen = registro.get("TIPO") == TIPO_RESUMEN

    if es_resumen:
        # El resumen semanal es a las 08:00 AM del sábado (no a medianoche),
        # con recordatorio de 0 minutos para que Outlook avise exactamente a las 8:00 AM.
        try:
            inicio_local = cita.Start.astimezone()
            necesita_inicio = (
                inicio_local.date() != fecha
                or inicio_local.hour != 8
                or inicio_local.minute != 0
            )
        except Exception:
            necesita_inicio = True

        if necesita_inicio:
            cita.Start = datetime(fecha.year, fecha.month, fecha.day, 8, 0, 0)
            cambios = True

        try:
            fin_local = cita.End.astimezone()
            necesita_fin = (
                fin_local.date() != fecha
                or fin_local.hour != 9
                or fin_local.minute != 0
            )
        except Exception:
            necesita_fin = True

        if necesita_fin:
            cita.End = datetime(fecha.year, fecha.month, fecha.day, 9, 0, 0)
            cambios = True

        if cita.AllDayEvent:
            cita.AllDayEvent = False
            cambios = True

        if recordatorio_min is not None:
            if not cita.ReminderSet:
                cita.ReminderSet = True
                cambios = True
            if cita.ReminderMinutesBeforeStart != 0:
                cita.ReminderMinutesBeforeStart = 0
                cambios = True
        elif cita.ReminderSet:
            cita.ReminderSet = False
            cambios = True
    else:
        if cita.Start.date() != fecha:
            cita.Start = datetime(fecha.year, fecha.month, fecha.day)
            cambios = True
        fin = fecha + timedelta(days=1)
        if cita.End.date() != fin:
            cita.End = datetime(fin.year, fin.month, fin.day)
            cambios = True

        if not cita.AllDayEvent:
            cita.AllDayEvent = True
            cambios = True

        if recordatorio_min:
            if not cita.ReminderSet:
                cita.ReminderSet = True
                cambios = True
            if cita.ReminderMinutesBeforeStart != int(recordatorio_min):
                cita.ReminderMinutesBeforeStart = int(recordatorio_min)
                cambios = True
        elif cita.ReminderSet:
            cita.ReminderSet = False
            cambios = True

    if cita.BusyStatus != OL_FREE:
        cita.BusyStatus = OL_FREE
        cambios = True
    if (cita.Categories or "") != CATEGORIA:
        cita.Categories = CATEGORIA
        cambios = True

    if (cita.Subject or "") != asunto:
        cita.Subject = asunto
        cambios = True

    cuerpo = _cuerpo(registro)
    if not _mismo_cuerpo(getattr(cita, "Body", ""), cuerpo):
        cita.Body = cuerpo
        cambios = True

    if cambios:
        cita.Save()
    return cambios


def exportar_a_outlook(
    registros: list[dict],
    *,
    carpeta_nombre: str | None = CARPETA_POR_DEFECTO,
    recordatorio_min: int | None = 1440,
    limite: int | None = None,
    purgar: bool = False,
    verbose: bool = False,
) -> dict:
    """Sincroniza las citas con Outlook (crea, actualiza y opcionalmente purga)."""
    resultado = {"creadas": 0, "actualizadas": 0, "omitidas": 0, "borradas": 0,
                 "sin_pareja": 0, "totales": len(registros), "carpeta": "-"}
    if not registros:
        return resultado

    sesion = _sesion()
    carpeta, creada = _carpeta(sesion, carpeta_nombre)
    resultado["carpeta"] = carpeta.Name
    if verbose:
        extra = " (recién creada)" if creada else ""
        print(f"  · carpeta destino: «{carpeta.Name}»{extra}")

    por_clave, por_fecha = _existe_en(carpeta)
    if verbose:
        print(f"  · {sum(len(v) for v in por_clave.values())} citas ya creadas antes")

    ordenados = sorted(
        (r for r in registros if r.get("FECHA")),
        key=lambda r: str(r["FECHA"]),
    )

    for registro in ordenados:
        fecha = date.fromisoformat(str(registro["FECHA"]))
        asunto = _asunto(registro)
        clave = _clave(registro)

        cita = _tomar(por_clave, clave, fecha)
        if cita is None:
            # citas antiguas que no pudimos leer: se emparejan por fecha+asunto
            lista = por_fecha.get((fecha, asunto))
            cita = lista.pop(0) if lista else None

        if cita is not None:
            if _aplicar(cita, registro, fecha, asunto, recordatorio_min):
                resultado["actualizadas"] += 1
                if verbose:
                    print(f"  · actualizada {fecha} {asunto[:60]}")
            else:
                resultado["omitidas"] += 1
            continue

        if limite is not None and resultado["creadas"] >= limite:
            continue

        try:
            nueva = carpeta.Items.Add(OL_APPOINTMENT)
            _aplicar(nueva, registro, fecha, asunto, recordatorio_min)
            nueva.Save()
        except Exception as exc:
            if verbose:
                print(f"  · falló {fecha} {asunto[:60]!r}: {exc}")
            continue
        resultado["creadas"] += 1
        if verbose and resultado["creadas"] % 25 == 0:
            print(f"  · {resultado['creadas']} citas creadas…")

    # Lo que quedó sin pareja: resúmenes caducos siempre, evaluaciones sólo
    # si se pidió purgar (nunca borramos datos sin que lo pidas).
    sueltas = [cita for lista in por_clave.values() for cita, _ in lista]
    sueltas += [cita for lista in por_fecha.values() for cita in lista]
    for cita in sueltas:
        try:
            clave = _clave_cita(cita)
            es_resumen = clave.startswith("SEMANA|")
            if es_resumen or purgar:
                cita.Delete()
                resultado["borradas"] += 1
            else:
                resultado["sin_pareja"] += 1
        except Exception:
            continue

    return resultado
