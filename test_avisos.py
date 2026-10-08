# -*- coding: utf-8 -*-
"""Prueba de avisos.py: resumen del sábado, cambios y caducas (sin red)."""
import sys
import tempfile
from datetime import date
from pathlib import Path

# Consolas cp1252 de Windows: los emojis de los mensajes van a «?» y no truena.
for _salida in (sys.stdout, sys.stderr):
    try:
        _salida.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import avisos  # noqa: E402  (está en la raíz del proyecto)
from edufacil import ediciones  # noqa: E402

HOY = date(2026, 10, 7)          # miércoles
SABADO = date(2026, 10, 10)      # sábado: resume la semana del 14 al 16

REGISTROS = [
    # semana pasada (mié 7 y jue 8)
    {"FECHA": "2026-10-07", "DIA": "Miércoles", "ASIGNATURA": "MATEMÁTICA",
     "NUMERO": "5", "EVALUACION": "E5: Datos y gráficos", "TIPO": "Evaluación"},
    {"FECHA": "2026-10-07", "ASIGNATURA": "ARTES VISUALES", "NUMERO": "3",
     "EVALUACION": "E3: Mi entorno", "TIPO": "Evaluación"},
    {"FECHA": "2026-10-08", "ASIGNATURA": "IDIOMA EXTRANJERO (ITALIANO)",
     "NUMERO": "1.1", "EVALUACION": "SE4-1: Canción", "TIPO": "Sub-evaluación"},
    # semana que viene (mié 14, jue 15 y vie 16)
    {"FECHA": "2026-10-14", "ASIGNATURA": "LENGUAJE Y COMUNICACIÓN",
     "NUMERO": "6", "EVALUACION": "E6: Prueba escrita", "TIPO": "Evaluación",
     "PROFESOR": "MARÍA LÓPEZ", "COEFICIENTE": "2", "PONDERACION": "40"},
    {"FECHA": "2026-10-15", "ASIGNATURA": "ARTES VISUALES", "NUMERO": "4",
     "EVALUACION": "E4: Proyecto", "TIPO": "Evaluación"},
    {"FECHA": "2026-10-16", "ASIGNATURA": "IDIOMA EXTRANJERO (ITALIANO)",
     "NUMERO": "2.2", "EVALUACION": "SE2-2: Audio 2", "TIPO": "Sub-evaluación"},
]
BASE_16 = ediciones.clave_base(REGISTROS[5])

FILAS = [
    {"id": "f1", "tipo": "correccion", "clave": "MATEMÁTICA|5|EVALUACIÓN#1",
     "campos": {"FECHA": "2026-10-08"}, "previo": {"FECHA": "2026-10-07"},
     "autor": "Iván", "creado": "2026-10-07T10:00:00+00:00"},
    {"id": "f2", "tipo": "nuevo", "clave": "HISTORIA|2|EVALUACIÓN#1",
     "campos": {"FECHA": "2026-10-20", "ASIGNATURA": "HISTORIA",
                "NUMERO": "2", "EVALUACION": "E2: Revolución industrial",
                "TIPO": "Evaluación"},
     "previo": {}, "autor": "Rafaela", "creado": "2026-10-07T11:30:00+00:00"},
    {"id": "f3", "tipo": "anula", "clave": "MATEMÁTICA|5|EVALUACIÓN#1",
     "anula": "f1", "autor": "Iván",
     "creado": "2026-10-07T12:00:00+00:00"},       # deshace f1
    {"id": "f4", "tipo": "correccion", "clave": "FÍSICA|9|EVALUACIÓN#1",
     "campos": {"EVALUACION": "vieja"}, "previo": {}, "autor": "X",
     "creado": "2026-09-01T10:00:00+00:00"},       # vieja: fuera del corte
]


def estado_base(registros=None, **extra) -> dict:
    """Estado de partida: instantánea al día y ningún cambio por contar."""
    datos = REGISTROS if registros is None else registros
    estado = {"huellas": avisos.instantanea(datos),
              "ultima_edicion": "2026-10-06T00:00:00+00:00"}
    estado.update(extra)
    return estado


def main() -> int:
    print("\n== avisos: entre semana, silencio ==")
    mensajes = avisos.preparar_mensajes(REGISTROS, [], hoy=HOY,
                                        estado=estado_base())
    assert mensajes == [], mensajes
    print(" miércoles con evaluaciones: sin avisos (ya no hay aviso diario)")

    print("\n== avisos: resumen del sábado ==")
    mensajes = avisos.preparar_mensajes(REGISTROS, [], hoy=SABADO,
                                        estado=estado_base())
    assert len(mensajes) == 1, mensajes
    resumen = mensajes[0]
    assert resumen["tag"] == "resumen" and not resumen["incluye_cambios"]
    assert resumen["titulo"] == \
        "📚 Resumen del sábado: 14, 15 y 16 oct · 3 evaluaciones", resumen
    cuerpo = resumen["cuerpo"]
    assert cuerpo.split("\n\n")[0] == (
        "Mié 14 oct\n"
        "LENGUAJE Y COMUNICACIÓN\n"
        "E6: Prueba escrita (N° 6)\n"
        "Prof. MARÍA LÓPEZ\n"
        "Evaluación\n"
        "coef. 2\n"
        "ponderación 40%"), cuerpo
    assert "Vie 16 oct\nIDIOMA EXTRANJERO (ITALIANO)\nSE2-2: Audio 2 (N° 2.2)" \
        in cuerpo, cuerpo
    assert cuerpo.count("\n\n") == 2, "línea en blanco entre fechas"
    print(" ", resumen["titulo"])
    print("  ", cuerpo.replace("\n\n", " | ").replace("\n", " › "))

    # ya enviado hoy: no se repite (la tarea corre varias veces)
    mensajes = avisos.preparar_mensajes(
        REGISTROS, [], hoy=SABADO,
        estado=estado_base(ultimo_resumen="2026-10-10"))
    assert mensajes == [], mensajes
    print(" ya mandado hoy: no se repite")

    # sábado de semana sin evaluaciones: no hay resumen y no se avisa nada
    mensajes = avisos.preparar_mensajes(REGISTROS, [], hoy=date(2026, 9, 26),
                                        estado=estado_base())
    assert mensajes == [], mensajes
    print(" sábado sin evaluaciones: sin avisos")

    print("\n== avisos: cambió el sitio ==")
    vieja = avisos.instantanea(REGISTROS)
    vieja[BASE_16] = ["2026-10-17|SE2-2: Audio 2"]     # la movían al 17
    mensajes = avisos.preparar_mensajes(
        REGISTROS, [], hoy=HOY,
        estado={"huellas": vieja, "ultima_edicion": "2026-10-06T00:00:00+00:00"})
    assert len(mensajes) == 1 and mensajes[0]["tag"] == "cambios", mensajes
    cambio = mensajes[0]
    assert cambio["titulo"] == "🔄 El calendario cambió", cambio
    assert "IDIOMA EXTRANJERO (ITALIANO) n° 2.2: 17-10 → 16-10" \
        in cambio["cuerpo"], cambio
    assert "➕" not in cambio["cuerpo"] and "➖" not in cambio["cuerpo"], \
        "mover una prueba no debe leerse como baja+alta"
    print(" ", cambio["titulo"], "->", cambio["cuerpo"])

    # el sitio agregó una prueba que antes no estaba
    vieja = avisos.instantanea(REGISTROS)
    del vieja[BASE_16]
    mensajes = avisos.preparar_mensajes(
        REGISTROS, [], hoy=HOY,
        estado={"huellas": vieja, "ultima_edicion": "2026-10-06T00:00:00+00:00"})
    assert "➕ IDIOMA EXTRANJERO (ITALIANO) n° 2.2: 16-10 (SE2-2: Audio 2)" \
        in mensajes[0]["cuerpo"], mensajes
    print(" alta del sitio:", mensajes[0]["cuerpo"])

    print("\n== avisos: correcciones de la comunidad ==")
    mensajes = avisos.preparar_mensajes(REGISTROS, FILAS, hoy=HOY,
                                        estado=estado_base())
    assert len(mensajes) == 1, mensajes
    corr = mensajes[0]
    assert corr["tag"] == "cambios"
    assert corr["titulo"] == "✏️ Cambios en el calendario", corr
    cuerpo = corr["cuerpo"]
    assert "✏️ Nueva: HISTORIA n° 2 · 20-10 (Rafaela)" in cuerpo, cuerpo
    assert "↩️ MATEMÁTICA n° 5: corrección anulada (Iván)" in cuerpo, cuerpo
    assert "f1" not in cuerpo and "f4" not in cuerpo and "vieja" not in cuerpo, \
        "no deben salir ni la corrección anulada ni la fila vieja"
    print(" ", cuerpo.replace("\n", " | "))

    # la corrección de la comunidad tapa el «cambio del sitio» equivalente:
    # f1 mueve la fecha y la instantánea también la ve, pero se cuenta una vez
    assert "🔄 MATEMÁTICA" not in cuerpo and "🔄 HISTORIA" not in cuerpo, \
        "una corrección no debe anunciarse dos veces"

    # más de cuatro líneas: se recortan con «+N más»
    extras = [dict(FILAS[1], id=f"x{i}", clave=f"ASIG{i}|1|EVALUACIÓN#1",
                   creado=f"2026-10-07T12:{i + 1:02d}:00+00:00")
              for i in range(4)]
    mensajes = avisos.preparar_mensajes(
        [], FILAS + extras, hoy=HOY, estado={"huellas": {},
                                             "ultima_edicion": "2026-10-06T00:00:00+00:00"})
    assert len(mensajes) == 1, mensajes
    assert "+2 más" in mensajes[0]["cuerpo"], mensajes[0]["cuerpo"]
    assert len(mensajes[0]["cuerpo"].splitlines()) == 5, mensajes[0]["cuerpo"]
    print(" recorte: +2 más")

    print("\n== avisos: sábado con cambios pendientes ==")
    vieja = avisos.instantanea(REGISTROS)
    del vieja[BASE_16]
    mensajes = avisos.preparar_mensajes(
        REGISTROS, [], hoy=SABADO,
        estado={"huellas": vieja, "ultima_edicion": "2026-10-06T00:00:00+00:00"})
    assert len(mensajes) == 1 and mensajes[0]["tag"] == "resumen", mensajes
    assert mensajes[0]["incluye_cambios"]
    assert "Cambios:" in mensajes[0]["cuerpo"]
    assert "Mié 14 oct" in mensajes[0]["cuerpo"]
    assert "➕ IDIOMA EXTRANJERO (ITALIANO) n° 2.2" in mensajes[0]["cuerpo"]
    print(" un solo aviso: resumen + lo que cambió debajo")

    print("\n== avisos: instantánea idempotente ==")
    aplicada, _, _ = ediciones.aplicar([dict(r) for r in REGISTROS], FILAS)
    assert avisos.instantanea(REGISTROS, FILAS) == \
        avisos.instantanea(aplicada, FILAS), \
        "aplicar dos veces no debe cambiar la foto (o se anunciaría doble)"
    print(" aplicar otra vez da la misma foto")

    print("\n== avisos: aviso de prueba ==")
    prueba = avisos.mensaje_prueba()
    assert prueba["tag"] == "prueba" and prueba["titulo"].startswith("🔔")
    assert "sábado" in prueba["cuerpo"] and len(prueba["cuerpo"]) > 40
    print(" prueba:", prueba["titulo"], "->", prueba["cuerpo"][:46], "…")

    print("\n== avisos: resumen del sábado como prueba (--probar-sabado) ==")
    for hoy in (HOY, SABADO):        # jueves o sábado: da el mismo resumen
        mensajes = avisos.mensajes_de_sabado(REGISTROS, hoy=hoy)
        assert len(mensajes) == 1 and mensajes[0]["tag"] == "resumen", mensajes
        assert mensajes[0]["titulo"].startswith("📚 Resumen del sábado:"), \
            mensajes[0]["titulo"]
        assert mensajes[0]["cuerpo"].count("\n\n") == 2, "3 fechas en blanco"
        assert "Mié 14 oct" in mensajes[0]["cuerpo"], mensajes[0]["cuerpo"]
    print(" ", mensajes[0]["titulo"], "->",
          mensajes[0]["cuerpo"].count("\n\n") + 1, "fechas")

    print("\n== avisos: estado ==")
    original = avisos.ESTADO
    with tempfile.TemporaryDirectory() as tmp:
        avisos.ESTADO = Path(tmp) / "estado.json"
        try:
            assert avisos.cargar_estado() == {}
            avisos.guardar_estado({"ultimo_resumen": "2026-10-10"})
            assert avisos.cargar_estado() == {"ultimo_resumen": "2026-10-10"}
        finally:
            avisos.ESTADO = original
    print(" guardar/cargar: el estado queda en logs/avisos_estado.json")

    print("\n== avisos: suscripciones caducas ==")
    original = avisos.CADUCAS
    with tempfile.TemporaryDirectory() as tmp:
        avisos.CADUCAS = Path(tmp) / "caducas.txt"
        try:
            assert avisos.leer_caducas() == set()
            avisos.anotar_caduca("https://push.example/abc")
            avisos.anotar_caduca("https://push.example/abc")   # repetir no duplica
            avisos.anotar_caduca("https://push.example/otra")
            assert avisos.leer_caducas() == {"https://push.example/abc",
                                             "https://push.example/otra"}
        finally:
            avisos.CADUCAS = original
    print(" caducas: apunta una vez y se acuerda de ambas")

    print("\nTODO OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
