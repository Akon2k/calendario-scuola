"""Sin red: fuentes reales se inyectan, la copia no toca la página publicable."""
import json
import re
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

from edufacil.informacion_local import CHILE, base
from publicar import ARCHIVOS
from vista_previa_alertas import consultar_mensajes, crear_vista_previa, generar


def main():
    ahora = datetime(2026, 10, 27, 21, 30, tzinfo=CHILE)
    lecturas = []
    for tipo in ('ruta', 'clima', 'noticias'):
        dato = base(tipo, ahora)
        dato.update(titulo='Titular de prueba ' + tipo, resumen='Contenido de prueba', detalle='Detalle verificable')
        lecturas.append(dato)
    datos = {'consultado': ahora.isoformat(), 'lecturas': lecturas}
    html = ('<html><head><style>body{color:black}</style></head><body><header>Calendario</header>'
            '<script type="application/json" id="nube">{"url":"https://prueba.supabase.co","key":"publica"}</script>'
            '<main id="vista-calendario">Datos</main></body></html>')
    vista = crear_vista_previa(html, datos, [])
    assert '<script type="application/json" id="nube">null</script>' in vista
    assert vista.index('id="franja-local"') > vista.index('</header>')
    assert vista.index('id="franja-local"') < vista.index('<main')
    paquete = json.loads(re.search(r'id="franja-datos">(.*?)</script>', vista, re.S)[1])
    assert paquete == datos
    assert 'Datos de ejemplo' not in vista and 'Fuente prevista' not in vista
    assert 'id="vista-local-sin-cache"' in vista
    assert 'localStorage.clear' not in vista and 'sessionStorage.clear' not in vista
    assert 'max-width: 1180px' in vista and 'margin: 0 auto 16px' in vista
    assert not any(origen in ('vista_previa_alertas.html', 'informacion_local.json') for origen, _ in ARCHIVOS)
    mensajes = [{'id': 'real-1', 'asunto': 'Comunicado </script> intacto',
                 'fecha': ahora.isoformat(), 'puntos': ['Texto original'], 'eventos': [], 'accion': ''}]
    con_mensajes = crear_vista_previa(html, datos, mensajes)
    assert json.loads(re.search(r'id="mensajes-locales">(.*?)</script>', con_mensajes, re.S)[1]) == mensajes
    assert 'window.__calendario.mensajes(JSON.parse(' in con_mensajes
    assert 'Comunicado </script>' not in con_mensajes
    origen_nube = ('<script type="application/json" id="nube">'
                  '{"url":"https://prueba.supabase.co","key":"publica","mensajes":"comunicados"}</script>')
    respuesta = MagicMock()
    respuesta.__enter__.return_value = respuesta
    respuesta.json.return_value = mensajes
    with patch('vista_previa_alertas.requests.get', return_value=respuesta) as get:
        assert consultar_mensajes(origen_nube) == mensajes
        assert get.call_args.args[0] == 'https://prueba.supabase.co/rest/v1/comunicados'
        assert ('offset', 0) in get.call_args.kwargs['params']
    with patch('vista_previa_alertas.requests.get', side_effect=requests.Timeout):
        try:
            consultar_mensajes(origen_nube)
        except ValueError:
            pass
        else:
            raise AssertionError('No debe ocultar un fallo de consulta como lista vacía')
    with tempfile.TemporaryDirectory() as tmp:
        salida = Path(tmp)
        fuente = salida / 'calendario_evaluaciones.html'
        fuente.write_text(html, encoding='utf-8')
        destino = generar(salida, datos)
        assert fuente.read_text(encoding='utf-8') == html
        assert destino.read_text(encoding='utf-8') == vista
        assert json.loads((salida / 'informacion_local.json').read_text(encoding='utf-8')) == datos
    for contenido, paquete in [('<html>incompleto</html>', datos), (html, {})]:
        try:
            crear_vista_previa(contenido, paquete)
        except ValueError:
            pass
        else:
            raise AssertionError('No debe generar sin poder desactivar nube o sin datos de las fuentes')
    print('TODO OK: datos inyectados, copia de lectura, ancho alineado y archivos fuera del publicador')


if __name__ == '__main__':
    main()
