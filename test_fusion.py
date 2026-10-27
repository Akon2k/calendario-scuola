"""Unión manual/oficial y ordinales estables, sin conexión a la nube."""
import copy
import json
import re
import tempfile
from pathlib import Path

from edufacil import ediciones
from edufacil.pagina import a_html


def main():
    oficial = {"FECHA": "2026-11-05", "ASIGNATURA": "LENGUAJE Y COMUNICACIÓN",
               "ABREVIATURA": "LEYCO", "NUMERO": "8", "TIPO": "Evaluación",
               "EVALUACION": "Evaluación de escritura", "CONTENIDO": "Del colegio"}
    altas = []
    for n, fecha in [(7, "2026-10-21"), (8, "2026-11-04"), (9, "2026-11-18")]:
        altas.append({"id": f"alta-{n}", "tipo": "nuevo",
                      "clave": "LENGUAJE Y COMUNICACIÓN||EVALUACIÓN#1",
                      "campos": {"FECHA": fecha, "ASIGNATURA": oficial["ASIGNATURA"],
                                 "EVALUACION": f"Dictado {n}", "CONTENIDO": f"Mi material {n}"},
                      "creado": f"2026-10-27T10:00:0{n}+00:00"})
    registros, claves, est = ediciones.aplicar([copy.deepcopy(oficial)], altas)
    k_oficial, k_7, k_8, k_9 = claves
    assert est["manuales"] == {k_7: "alta-7", k_8: "alta-8", k_9: "alta-9"}
    lote = [
        {"id": "copia-pdf", "tipo": "adjunto", "clave": k_oficial,
         "campos": {"archivo": "dictado8.pdf", "nombre": "Ficha dictado 8.pdf"}},
        {"id": "datos-unidos", "tipo": "correccion", "clave": k_oficial,
         "campos": {"FECHA": "2026-11-04", "CONTENIDO": "Mi material 8"},
         "previo": {"FECHA": "2026-11-05", "CONTENIDO": "Del colegio"},
         "creado": "2026-10-27T12:00:00+00:00"},
        {"id": "retira-manual", "tipo": "anula", "clave": k_8, "anula": "alta-8",
         "campos": {"fusion_destino": k_oficial}, "creado": "2026-10-27T12:00:01+00:00"},
    ]
    unido, keys, despues = ediciones.aplicar([copy.deepcopy(oficial)], altas + lote)
    assert len(unido) == 3 and keys == [k_oficial, k_7, k_9]
    assert unido[0]["FECHA"] == "2026-11-04" and unido[0]["CONTENIDO"] == "Mi material 8"
    assert unido[0]["EVALUACION"] == oficial["EVALUACION"]
    assert despues["manuales"] == {k_7: "alta-7", k_9: "alta-9"}
    assert k_9.endswith("#3"), "retirar el dictado 8 no debe cambiar la identidad del 9"
    with tempfile.TemporaryDirectory() as tmp:
        ruta = a_html(registros, Path(tmp) / "vista.html", claves=claves, manuales=est["manuales"])
        datos = json.loads(re.search(r'id="datos">(.*?)</script>', ruta.read_text(encoding="utf-8"), re.S)[1])
        assert datos["eventos"][0]["nuevo"] == ""
        assert [e["nuevo"] for e in datos["eventos"][1:]] == ["alta-7", "alta-8", "alta-9"]
    assert not any(k.startswith("_") for r in unido for k in r), "sin metadatos internos en los exportables"
    print("TODO OK: unión, fecha/contenido elegidos, procedencia embebida y claves de otras tarjetas estables")


if __name__ == "__main__":
    main()
