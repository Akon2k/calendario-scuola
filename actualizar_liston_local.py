# -*- coding: utf-8 -*-
"""Refresca sólo el JSON del listón LOCAL cada 15 minutos. Ctrl+C para parar.

    python actualizar_liston_local.py
    python actualizar_liston_local.py --una-vez

No publica, no consulta Supabase y no modifica calendario ni comunicados.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from pathlib import Path

from edufacil.informacion_local import recopilar

SALIDA = Path(__file__).resolve().parent / 'salida'
INTERVALO = 15 * 60


def actualizar(salida: Path = SALIDA, datos: dict | None = None) -> dict:
    datos = recopilar() if datos is None else datos
    temporal = None
    try:
        # Reemplazo atómico: el navegador nunca recibe medio JSON.
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=salida,
                                         prefix='liston-', suffix='.tmp', delete=False) as f:
            temporal = Path(f.name)
            json.dump(datos, f, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(temporal, salida / 'informacion_local.json')
    finally:
        if temporal is not None and temporal.exists():
            temporal.unlink()
    return datos


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--una-vez', action='store_true')
    args = parser.parse_args()
    print('Actualizador LOCAL: fuentes cada 15 minutos. No publica ni envía avisos.', flush=True)
    try:
        while True:
            inicio = time.monotonic()
            try:
                datos = actualizar()
                estados = ', '.join(d['id'] + ': ' + d['estado'] for d in datos['lecturas'])
                print(datos['consultado'] + ' · ' + estados, flush=True)
            except (OSError, ValueError):
                print('No se pudo actualizar: se conserva la lectura y su fecha anterior.', flush=True)
                if args.una_vez:
                    raise SystemExit(1)
            if args.una_vez:
                return
            time.sleep(max(1, INTERVALO - (time.monotonic() - inicio)))
    except KeyboardInterrupt:
        print('Actualizador local detenido.', flush=True)


if __name__ == '__main__':
    main()
