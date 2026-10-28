# -*- coding: utf-8 -*-
"""Refresca el JSON local cada 15 minutos. --publicar replica el snapshot público.

    python actualizar_liston_local.py
    python actualizar_liston_local.py --una-vez

Sin --publicar no consulta Supabase. Nunca modifica tarjetas ni envía avisos.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from edufacil.informacion_local import recopilar

SALIDA = Path(__file__).resolve().parent / 'salida'
INTERVALO = 15 * 60
PROYECTO = 'icblrmookmpmzpnjeeeh'


def publicar_snapshot(datos: dict) -> None:
    """Actualiza sólo el snapshot público, con la CLI administradora del PC."""
    if set(datos) != {'consultado', 'lecturas'} or {d.get('id') for d in datos['lecturas']} != {'noticias', 'clima', 'ruta'}:
        raise ValueError('Snapshot del listón no válido')
    contenido = json.dumps(datos, ensure_ascii=False, allow_nan=False).replace("'", "''")
    sql = ("insert into public.liston_publico(id,datos) values(true,'" + contenido + "'::jsonb) "
           "on conflict(id) do update set datos=excluded.datos,actualizado=now() "
           "where (public.liston_publico.datos->>'consultado')::timestamptz "
           "< (excluded.datos->>'consultado')::timestamptz;")
    carpeta = SALIDA.parent / 'logs/noticias-scuola'
    carpeta.mkdir(parents=True, exist_ok=True)
    temporal = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=carpeta,
                                         prefix='liston-', suffix='.sql', delete=False) as f:
            temporal = Path(f.name)
            f.write(sql)
        proceso = subprocess.run(['npx.cmd' if os.name == 'nt' else 'npx', '--yes', 'supabase',
            'db', 'query', '--linked', '--project-ref', PROYECTO, '--file', str(temporal)],
            cwd=SALIDA.parent, capture_output=True, timeout=90)
        if proceso.returncode:
            raise ValueError('No se pudo actualizar el snapshot público; se conserva el anterior')
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError('La conexión del snapshot público no está disponible') from None
    finally:
        if temporal is not None:
            temporal.unlink(missing_ok=True)


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
    parser.add_argument('--publicar', action='store_true', help='actualiza también el snapshot público; nunca envía avisos')
    args = parser.parse_args()
    print('Actualizador: fuentes cada 15 minutos. No envía avisos.', flush=True)
    if args.publicar:
        print('Snapshot público habilitado expresamente; sólo datos del listón, sin modificar tarjetas ni avisos.', flush=True)
    try:
        while True:
            inicio = time.monotonic()
            try:
                datos = actualizar()
                if args.publicar:
                    publicar_snapshot(datos)
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
