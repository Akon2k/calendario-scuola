# -*- coding: utf-8 -*-
"""Prepara un archivo privado. --comprobar lista idiomas, no traduce ni activa."""
import argparse
import re
from pathlib import Path

import requests

ARCHIVO = Path(__file__).resolve().parent / 'logs/noticias-scuola/google.env'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comprobar', action='store_true')
    args = parser.parse_args()
    ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
    if not ARCHIVO.exists():
        ARCHIVO.write_text('# Privado: no copiar al chat, HTML ni GitHub.\nGOOGLE_TRANSLATE_API_KEY=\n', encoding='utf-8')
    if not args.comprobar:
        print('Archivo privado: logs/noticias-scuola/google.env')
        print('Guarda allí la clave, después de habilitar la API y configurar cuotas en Google Cloud.')
        print('La traducción automática sigue desactivada.')
        return
    lineas = [l for l in ARCHIVO.read_text(encoding='utf-8').splitlines() if l.startswith('GOOGLE_TRANSLATE_API_KEY=')]
    key = lineas[0].split('=', 1)[1].strip() if len(lineas) == 1 else ''
    if not re.fullmatch(r'[A-Za-z0-9_-]{20,200}', key):
        raise SystemExit('Falta una clave válida en el archivo privado. No la pegues en el chat.')
    try:
        r = requests.get('https://translation.googleapis.com/language/translate/v2/languages',
                         params={'target': 'es'}, headers={'x-goog-api-key': key}, timeout=(5, 15), allow_redirects=False)
        if r.status_code != 200:
            raise SystemExit(f'Google respondió HTTP {r.status_code}. Revisar API, restricciones y facturación; la clave no se muestra.')
        idiomas = {n['language'] for n in r.json()['data']['languages']}
        if not {'it', 'es'} <= idiomas:
            raise SystemExit('No se pudieron confirmar italiano y español.')
    except (requests.RequestException, ValueError, KeyError, TypeError):
        raise SystemExit('No se pudo validar Google. Se conserva la configuración desactivada.') from None
    print('Credencial aceptada; italiano y español disponibles. No se ha traducido ni activado nada.')
    print('Antes de activar, confirmar cuotas y guardar la clave sólo como secreto de Supabase.')


if __name__ == '__main__':
    main()
