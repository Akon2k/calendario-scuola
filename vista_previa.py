# -*- coding: utf-8 -*-
"""Vista previa local de la pestaña «Mensajes de la Scuola».

Copia la página generada y le inyecta comunicados de ejemplo, para ver cómo
queda **antes** de tocar Supabase ni de publicar nada.

    python vista_previa.py

Sale `salida/vista_previa_mensajes.html` en tu navegador. Ese archivo no se
sube a ningún lado: `salida/` está en `.gitignore`.
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EJEMPLOS = [
    {
        "id": "ejemplo-1",
        "asunto": "3ª Reunión de Apoderados — miércoles 21 de octubre",
        "fecha": "2026-10-15T18:40:00-03:00",
        "puntos": [
            "Reunión el miércoles 21 de octubre a las 18:30 en el salón de la "
            "Scuola.",
            "Se solicita no asistir con alumnos, o mantenerlos en sala sin "
            "patinetas ni pelotas.",
            "Los estacionamientos quedan habilitados de forma ordenada en el "
            "sector del Stadio Italiano.",
        ],
        "accion": "Asistir puntualmente el miércoles 21 a las 18:30 hrs.",
        "eventos": [{"titulo": "3ª Reunión de Apoderados",
                     "fecha_inicio": "2026-10-21T18:30:00"}],
    },
    {
        "id": "ejemplo-2",
        "asunto": "Excursión a Villa Grimaldi — 4º básico",
        "fecha": "2026-10-13T09:15:00-03:00",
        "puntos": [
            "Salida el viernes 23 de octubre a las 08:45 desde el patio de "
            "la Scuola.",
            "Colación propia, botella de agua y ropa cómoda. Sin celulares.",
            "Volvemos al establecimiento alrededor de las 16:30 hrs.",
        ],
        "accion": ("Autorizar la salida con la firma en la hoja que enviaron "
                   "por la profesora jefe."),
        "eventos": [{"titulo": "Excursión Villa Grimaldi",
                     "fecha_inicio": "2026-10-23T08:45:00"}],
    },
    {
        # Sin acción ni eventos: comprueba que esos renglones no aparecen.
        "id": "ejemplo-3",
        "asunto": "Informe de notas — 2ª etapa",
        "fecha": "2026-10-09T12:05:00-03:00",
        "puntos": [
            "El informe se entrega el lunes 26 de octubre por la intranet de "
            "EduFácil.",
            "Las observaciones de conducta se envían aparte por correo a los "
            "apoderados registrados.",
        ],
        "accion": "",
        "eventos": [],
    },
]


def main() -> int:
    salida = Path("salida")
    origen = salida / "calendario_evaluaciones.html"
    if not origen.exists():
        print("  falta la página: corre «python main.py» primero")
        return 1

    html = origen.read_text(encoding="utf-8")
    datos = json.dumps(EJEMPLOS, ensure_ascii=False).replace("</", "<\\/")
    destino = salida / "vista_previa_mensajes.html"
    destino.write_text(
        html.replace("</body>",
                     f"<script>\n  window.__calendario.mensajes({datos});\n"
                     "</script>\n</body>", 1),
        encoding="utf-8")
    print(f"  vista previa: {destino.resolve()}")
    print("  ábrela en el navegador y toca la pestaña «Mensajes»")
    return 0


if __name__ == "__main__":
    sys.exit(main())
