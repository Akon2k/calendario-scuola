# -*- coding: utf-8 -*-
"""Prueba local de datos + exportadores con la forma real de la API."""
import base64
import json
import re
import sys
from datetime import date
from pathlib import Path

from edufacil import a_csv, a_excel, a_html, a_json, agregar_detalle, ediciones, limpiar, ordenar
from edufacil.datos import DIAS_ES, registros_desde_dias
from edufacil.outlook import _clave
from edufacil.semana import resumenes_semanales

SUBSECTORES = {
    "216794": {"subsector": "MATEMÁTICA", "abreviatura": "MATEM", "color": "#aa5e6d"},
    "216797": {"subsector": "EDUCACIÓN FÍSICA Y SALUD", "abreviatura": "EFYS", "color": "#e35b9c"},
}

DIAS = [
    {
        "fecha": "14-10-2026", "fecha_dia": "14", "fecha_mes": "10",
        "vacaciones": "f", "dia_lectivo": "t", "dia_habil": "t",
        "detalle_feriado": "",
        "pruebas": json.dumps([
            {"sxc": 216794, "subsector": "MATEMÁTICA", "abreviatura": "MATEM",
             "nombre_prueba": "E2: Números hasta 100", "contenido": "Composición",
             "coeficiente": 2, "fecha": "2026-10-14", "orden_sxc": 1,
             "orden_prueba": 2, "sub_orden_prueba": 0},
            {"sxc": 216797, "subsector": "EDUCACIÓN FÍSICA Y SALUD",
             "abreviatura": "EFYS", "nombre_prueba": "SE1-1: Quizz",
             "contenido": "Cooperación", "coeficiente": 1, "fecha": "2026-10-14",
             "orden_sxc": 10, "orden_prueba": 1, "sub_orden_prueba": 1},
        ], ensure_ascii=False),
    },
    {"fecha": "15-10-2026", "fecha_dia": "15", "fecha_mes": "10", "vacaciones": "f",
     "dia_lectivo": "t", "dia_habil": "t", "detalle_feriado": "", "pruebas": "[]"},
    {"fecha": "16-10-2026", "fecha_dia": "16", "fecha_mes": "10", "vacaciones": "f",
     "dia_lectivo": "f", "dia_habil": "f", "detalle_feriado": "Día no lectivo",
     "pruebas": "[]"},
]

DETALLE = {"asignatura": "MATEMÁTICA", "profesor": "ANA PÉREZ", "numero": "2",
           "sub_numero": "0", "prueba": "Números hasta 100",
           "contenido": "Composición y descomposición", "coeficiente": "2",
           "ponderacion": "100"}


def main() -> int:
    registros = registros_desde_dias(DIAS, SUBSECTORES)
    print(f"\n== {len(registros)} registros ==")
    for r in registros:
        print("   ", {k: v for k, v in r.items() if not k.startswith("_")})
    assert len(registros) == 2, registros

    agregar_detalle(registros[0], DETALLE)
    registros = ordenar(registros)
    exportables = limpiar(registros)

    matematica = next(r for r in exportables if r["ASIGNATURA"] == "MATEMÁTICA")
    sub = next(r for r in exportables if r["TIPO"] == "Sub-evaluación")

    assert matematica["PROFESOR"] == "ANA PÉREZ"
    assert matematica["NUMERO"] == "2"
    assert matematica["PONDERACION"] == "100"
    assert sub["NUMERO"] == "1.1", sub
    assert not any(k.startswith("_") for r in exportables for k in r)
    assert all(r["FECHA"] == "2026-10-14" for r in exportables)
    assert [r["ASIGNATURA"] for r in exportables] == sorted(
        r["ASIGNATURA"] for r in exportables), "no quedó ordenado por asignatura"

    salida = Path("_prueba_salida")
    salida.mkdir(exist_ok=True)
    print("\n== exportadores ==")
    print(" xlsx:", a_excel(exportables, salida / "prueba.xlsx"))
    print(" csv :", a_csv(exportables, salida / "prueba.csv"))
    print(" json:", a_json(exportables, salida / "prueba.json"))
    # ---- resumen semanal: el sábado anterior lista la semana lun-vie ----
    resumenes = resumenes_semanales(exportables)
    assert len(resumenes) == 1, resumenes
    sabado = resumenes[0]
    assert sabado["FECHA"] == "2026-10-10", f"debió ser el sábado previo: {sabado}"
    assert sabado["DIA"] == "Sábado"
    assert sabado["TIPO"] == "Resumen semanal"
    assert sabado["EVALUACION"] == "14 oct · 2 evaluaciones", sabado["EVALUACION"]
    assert "MATEMÁTICA" in sabado["CONTENIDO"], sabado["CONTENIDO"]
    bloques = sabado["CONTENIDO"].split("\n\n")
    assert len(bloques) == 2, f"cada evaluación su bloque: {sabado['CONTENIDO']!r}"
    assert all(len(b.split("\n")) >= 3 for b in bloques), \
        "fecha, asignatura y prueba van cada una en su línea"
    print(" resumen:", sabado["EVALUACION"], "->", sabado["FECHA"])

    # ---- la identidad no depende de la fecha: cambiarla no duplica ----
    clave = _clave(exportables[0])
    movido = dict(exportables[0])
    movido["FECHA"] = "2026-11-30"
    assert _clave(movido) == clave, "la clave cambió al mover la fecha"
    assert _clave(sabado) == f"SEMANA|{sabado['FECHA']}"
    otro = dict(exportables[0])
    otro["NUMERO"] = "9"
    assert _clave(otro) != clave, "dos evaluaciones distintas no pueden cruzarse"
    print(" claves: estable al cambiar la fecha y única por evaluación")

    csv_texto = (salida / "prueba.csv").read_text(encoding="utf-8-sig")
    assert "MATEMÁTICA" in csv_texto and csv_texto.splitlines()[0].startswith("FECHA;")
    assert "Resumen semanal" not in csv_texto, "el resumen no va al CSV"
    assert not (salida / "prueba.ics").exists(), "ya no debe generarse .ics"

    # ---- página del calendario: datos + .ics incrustado para descargar ----
    ruta_html = a_html(exportables + resumenes, salida / "prueba.html")
    print(" html:", ruta_html)
    pagina = ruta_html.read_text(encoding="utf-8")
    assert "MATEMÁTICA" in pagina, "faltan los datos en la página"
    assert "Descargar .ics" in pagina, "falta el botón de descarga"
    assert "2 evaluaciones" in pagina, "falta el resumen del sábado en la página"
    assert not (salida / "prueba.ics").exists(), "la página no debe escribir el .ics"

    embebido = re.search(r'id="ics-b64">([^<]+)</script>', pagina)
    assert embebido, "no encontré el .ics incrustado"
    ics = base64.b64decode(embebido.group(1)).decode("utf-8")
    assert "DTSTART;VALUE=DATE:20261014" in ics, ics[:400]
    assert "DTSTART;VALUE=DATE:20261010" in ics, "falta el resumen del sábado"
    assert "TRIGGER:PT0S" in ics, "el resumen avisa al empezar el sábado"
    assert "TRIGGER:-P1D" in ics, "las evaluaciones avisan 1 día antes"
    assert "X-WR-CALNAME:Evaluacion Scuola" in ics, \
        "el calendario debe llamarse «Evaluacion Scuola»"
    # El plegado puede partir el par, así que se despliega antes de mirar.
    assert "\\n\\n" in ics.replace("\r\n ", ""), \
        "el .ics debe conservar la línea en blanco entre fechas"
    uids = re.findall(r"^UID:(.+)$", ics, re.M)
    assert len(uids) == 3 and len(set(uids)) == 3, uids
    lineas = ics.split("\r\n")
    assert ics.startswith("BEGIN:VCALENDAR\r\n"), "las líneas deben ser CRLF"
    assert max(len(l.encode("utf-8")) for l in lineas) <= 75, "falta plegar"
    print(" ics embebido:", len(uids), "eventos, UID únicos, plegado OK")

    # ---- PWA: manifest, service worker e iconos junto al HTML ----
    man = json.loads((salida / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert man["display"] == "standalone" and len(man["icons"]) == 3, man
    assert man["start_url"] == "./" and man["theme_color"] == "#2563eb", man
    sw = (salida / "sw.js").read_text(encoding="utf-8")
    for gancho in ("addEventListener('push'", "addEventListener('notificationclick'",
                   "addEventListener('fetch'"):
        assert gancho in sw, f"sw.js sin {gancho}"
    for icono in ("icon-192.png", "icon-512.png", "icon-maskable-512.png",
                  "apple-touch-icon.png"):
        assert (salida / icono).stat().st_size > 500, f"falta o está vacío {icono}"
    assert '<link rel="manifest" href="manifest.webmanifest">' in pagina
    assert '<link rel="apple-touch-icon" href="apple-touch-icon.png">' in pagina
    assert 'id="instalar"' in pagina and 'id="avisos"' in pagina
    print(" pwa: manifest + sw.js (push) + 4 iconos + botones")

    # ==== correcciones comunitarias (tabla «ediciones» de Supabase) ====
    print("\n== ediciones (nube) ==")

    # a) la identidad lleva ordinal y NO depende de la fecha: el mismo número
    #    se repite en el año (E1 en abril y E1 en agosto)
    par = [
        {"FECHA": "2026-04-06", "ASIGNATURA": "MATEMÁTICA", "NUMERO": "1",
         "TIPO": "Evaluación", "EVALUACION": "E1"},
        {"FECHA": "2026-08-03", "ASIGNATURA": "MATEMÁTICA", "NUMERO": "1",
         "TIPO": "Evaluación", "EVALUACION": "E1"},
    ]
    k_abril, k_agosto = ediciones.claves_unicas(par)
    assert k_abril.endswith("#1") and k_agosto.endswith("#2"), (k_abril, k_agosto)
    assert k_abril.rsplit("#", 1)[0] == k_agosto.rsplit("#", 1)[0]
    movidos = [dict(par[0], FECHA="2026-12-01"), par[1]]
    assert ediciones.claves_unicas(movidos) == [k_abril, k_agosto], \
        "mover la fecha no puede cambiar a quién apunta la clave"
    claves_base = ediciones.claves_unicas(exportables)
    assert len(set(claves_base)) == len(exportables), claves_base
    print(" identidad:", claves_base[0], "(ordinal por orden del scrapeo)")

    def nueva_base():
        return [dict(r) for r in exportables]

    clave0 = claves_base[0]
    fecha0 = exportables[0]["FECHA"]
    correccion = [{
        "id": "f-1", "tipo": "correccion", "clave": clave0,
        "campos": {"FECHA": "2026-11-02"},
        "previo": {"FECHA": fecha0},
        "autor": "Rafaela", "creado": "2026-10-07T12:00:00+00:00",
    }]

    # b) corrección: cambia la fecha y recalcula el día de la semana
    corregidos, claves_ok, est = ediciones.aplicar(nueva_base(), correccion)
    assert corregidos[0]["FECHA"] == "2026-11-02", corregidos[0]
    assert corregidos[0]["DIA"] == DIAS_ES[date(2026, 11, 2).weekday()]
    assert est["corregidas"] == 1 and not est["caducas"], est
    assert claves_ok == claves_base, "las claves deben seguir alineadas"
    print(" corrección: 1 aplicada, día recalculado ->", corregidos[0]["DIA"])

    # c) aplicarla dos veces no cambia nada más (la base ya trae el cambio)
    _, _, est2 = ediciones.aplicar(corregidos, correccion)
    assert est2["corregidas"] == 0 and est2["caducas"] == 0, \
        "reaplicar no debe marcar caducada la corrección que ya está"
    print(" idempotente: segunda pasada sin cambios")

    # d) caducidad: si EduFácil cambió el dato por su cuenta, se ignora sola
    caduca = nueva_base()
    caduca[0]["FECHA"] = "2026-11-30"
    _, _, est3 = ediciones.aplicar(caduca, correccion)
    assert caduca[0]["FECHA"] == "2026-11-30", "no debe pisar al scrapeo"
    assert est3["caducas"] == 1 and est3["corregidas"] == 0, est3
    print(" caduca: se respeta lo que dice EduFácil y se anota el aviso")

    # e) deshacer = un registro «anula» (no se borra nada)
    con_anula = correccion + [{
        "id": "f-2", "tipo": "anula", "clave": clave0, "anula": "f-1",
        "campos": {}, "previo": {}, "autor": "Rafaela",
        "creado": "2026-10-07T13:00:00+00:00",
    }]
    deshecho, _, est4 = ediciones.aplicar(nueva_base(), con_anula)
    assert deshecho[0]["FECHA"] == fecha0, "la corrección anulada no debe aplicarse"
    assert est4["anuladas"] == 1 and est4["corregidas"] == 0, est4
    print(" anula: la corrección anulada queda fuera (bitácora intacta)")

    # f) alta de un evento nuevo, y que no se duplique al día siguiente
    alta = {
        "id": "f-3", "tipo": "nuevo", "clave": "MATEMÁTICA|T9|EVALUACIÓN#1",
        "campos": {"FECHA": "2026-10-21", "ASIGNATURA": "MATEMÁTICA",
                   "EVALUACION": "Prueba de la comunidad", "NUMERO": "T9"},
        "previo": {}, "autor": "Rafaela", "creado": "2026-10-07T14:00:00+00:00",
    }
    con_alta, claves_alta, est5 = ediciones.aplicar(nueva_base(), [alta])
    assert len(con_alta) == len(exportables) + 1 and est5["agregadas"] == 1, est5
    assert con_alta[-1]["DIA"] and con_alta[-1]["ABREVIATURA"], con_alta[-1]
    assert claves_alta[-1].startswith("MATEMÁTICA|T9|EVALUACIÓN#"), claves_alta[-1]
    repetida, _, est6 = ediciones.aplicar(con_alta, [alta])
    assert len(repetida) == len(con_alta) and est6["agregadas"] == 0, est6
    print(" alta: evento agregado con clave propia y sin duplicarse")

    # g) las claves SEMANA| sólo tocan los resúmenes, nunca las evaluaciones
    filas_semana = [{
        "id": "f-4", "tipo": "correccion",
        "clave": f"SEMANA|{sabado['FECHA']}#1",
        "campos": {"EVALUACION": "Título corregido"},
        "previo": {"EVALUACION": sabado["EVALUACION"]},
        "autor": "Rafaela", "creado": "2026-10-07T15:00:00+00:00",
    }]
    tocados, _, est7 = ediciones.aplicar(nueva_base(), filas_semana)
    assert est7["corregidas"] == 0 and \
        all(r["EVALUACION"] != "Título corregido" for r in tocados), est7
    res_con, _, est8 = ediciones.aplicar([dict(sabado)], filas_semana, resumenes=True)
    assert res_con[0]["EVALUACION"] == "Título corregido" and est8["corregidas"] == 1
    print(" resúmenes: corregidos aparte de las evaluaciones")

    # h) lo que llega de la nube se valida dos veces
    limpios = ediciones.validar_campos({
        "FECHA": "2026-13-45", "HACK": "x", "TIPO": "Pipa",
        "EVALUACION": "   ok   ", "NUMERO": 3, "CONTENIDO": ["no"]})
    assert "FECHA" not in limpios and "HACK" not in limpios and "TIPO" not in limpios
    assert "CONTENIDO" not in limpios
    assert limpios["EVALUACION"] == "ok" and limpios["NUMERO"] == "3", limpios
    assert ediciones.registro_nuevo({"FECHA": "2026-10-21"}) is None, \
        "un alta sin asignatura no puede entrar"
    print(" validación: campos ajenos, fechas imposibles y tipos raros fuera")

    # i) configuración y respaldo local
    assert ediciones.cargar_nube({}) is None and \
        ediciones.cargar_nube({"supabase": {}}) is None, \
        "sin nube configurada todo debe seguir igual"
    try:
        ediciones.cargar_nube({"supabase": {"url": "http://x", "anon_key": "k"}})
    except ediciones.ErrorNube:
        pass
    else:
        raise AssertionError("debió rechazar una url sin https")
    archivo = salida / "ediciones.json"
    ediciones.respaldar(correccion, archivo)
    assert ediciones.leer_respaldo(archivo)[0]["id"] == "f-1"
    assert ediciones.leer_respaldo(salida / "no-existe.json") == []
    print(" configuración: sin nube se sigue igual; respaldo local OK")

    print("\nTODO OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
