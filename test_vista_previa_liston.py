"""Listón local: conserva la información y nunca toca la página publicable."""
import json
import re
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from edufacil.informacion_local import CHILE, base
from publicar import ARCHIVOS
from vista_previa_liston import crear_liston, generar_liston
from actualizar_liston_local import INTERVALO, actualizar


def main():
    ahora = datetime(2026, 10, 27, 21, 30, tzinfo=CHILE)
    lecturas = []
    for tipo in ('ruta', 'clima', 'noticias'):
        lectura = base(tipo, ahora)
        lectura.update(titulo='Título de prueba ' + tipo, resumen='Resumen', detalle='Detalle')
        lecturas.append(lectura)
    datos = {'consultado': ahora.isoformat(), 'lecturas': lecturas}
    html = ('<html><head><style></style></head><body><header>Calendario'
            '<div class="acciones"><button id="tema">Sol</button><button id="imprimir">Imprimir</button>'
            '<button id="descargar" class="primario">Descargar .ics</button></div></header>'
            '<script type="application/json" id="nube">{"url":"https://ficticio.supabase.co"}</script>'
            '<main>Calendario</main><details id="ayuda"><summary>Ayuda antigua</summary>'
            '<p>Contenido anterior</p></details></body></html>')
    vista = crear_liston(html, datos, [])
    assert 'class="liston-local"' in vista
    assert vista.count('id="franja-local"') == 1
    assert vista.count('id="franja-titulo"') == 1
    assert '<a id="franja-titulo" target="_blank" rel="noopener noreferrer"' in vista
    imprimir = re.search(r'<button id="imprimir"[^>]*>(.*?)</button>', vista, re.S)
    assert imprimir and '<svg' in imprimir[1] and '>Imprimir<' not in vista
    assert 'title="Imprimir" aria-label="Imprimir"' in imprimir[0]
    assert 'aria-hidden="true" focusable="false"' in imprimir[1]
    descargar = re.search(r'<button id="descargar"[^>]*>(.*?)</button>', vista, re.S)
    assert descargar and '<svg' in descargar[1] and '>Descargar .ics<' not in vista
    assert 'title="Descargar calendario (.ics)" aria-label="Descargar calendario (.ics)"' in descargar[0]
    assert 'aria-hidden="true" focusable="false"' in descargar[1]
    assert '.acciones #tema, .acciones #imprimir, .acciones #descargar {' in vista
    assert vista.count('id="botones-icono-locales"') == 1
    assert 'titular.href = fuente.href;' in vista
    assert "ver.hidden = tipo === 'noticias' || (tipo === 'ruta' && caja.dataset.estado !== 'ok');" in vista
    assert 'ver.disabled = ver.hidden;' in vista
    assert '<script type="application/json" id="nube">null</script>' in vista
    assert json.loads(re.search(r'id="franja-datos">(.*?)</script>', vista, re.S)[1]) == datos
    assert 'prefers-reduced-motion: reduce' in vista and '8000' in vista and '9000' not in vista
    assert "frames = [{tipo: 'clima'}, {tipo: 'ruta'}, {tipo: 'noticias'}];" in vista
    assert '<span id="liston-categoria">Tiempo en Coronel</span>' in vista
    assert ": 'informacion_local.json';" in vista and 'fetch(urlLectura' in vista and '60000' in vista
    assert 'informacion-local-actualizada' in vista
    assert INTERVALO == 900
    assert 'id="mensajes-locales"' in vista
    assert 'window.__calendario.mensajes(JSON.parse(' in vista
    ayuda = re.search(r'<details id="ayuda">(.*?)</details>', vista, re.S)[1]
    assert '<ol>' in ayuda and '<svg' not in ayuda and '<img' not in ayuda
    assert '&#' not in ayuda and 'Ayuda antigua' not in ayuda
    assert ayuda.count('<li>') == 10 and 'Supabase' not in ayuda and 'Vista de prueba' not in ayuda
    assert all(t in ayuda for t in ('Noticias Scuola', 'Contadores de lectura', '8 segundos', '15 minutos', 'Ver detalle', 'Volver'))
    assert all('id="liston-' + c + '"' in vista for c in ('anterior', 'pausa', 'siguiente', 'contador'))
    assert not any(a == 'vista_previa_liston.html' for a, _ in ARCHIVOS)
    repetida = crear_liston(vista, datos, [])
    for ident in ('franja-local', 'franja-datos', 'franja-ver', 'liston-pausa', 'mensajes-locales', 'vista-local-sin-cache',
                  'imprimir', 'descargar', 'botones-icono-locales'):
        assert repetida.count('id="' + ident + '"') == 1, 'no duplicar ' + ident
    assert repetida.count('var paquete = JSON.parse(document.getElementById(\'franja-datos\')') == 2, 'un control de franja y uno de listón'
    assert repetida.count('#franja-local.liston-local { padding:') == 1
    assert '-vista-coronel-vista-coronel' not in repetida
    con_pestanas = html.replace('<main>Calendario</main>',
        '<nav id="pestanas"><button id="tab-calendario">Calendario</button>'
        '<button id="tab-mensajes">Mensajes</button></nav><main id="vista-calendario">Calendario</main>'
        '<section id="mensajes" hidden><div id="mensajes-lista"></div></section>')
    noticia = {'url': 'https://scuola.scuolaitalianadiconcepcion.cl/2026/10/27/noticia/',
               'fecha': '2026-10-27', 'titulo': 'Titolo', 'titulo_es': 'Título', 'titulo_es_proveedor': 'manual'}
    integrada = crear_liston(con_pestanas, datos, [], {'noticias': [noticia]})
    integrada = crear_liston(integrada, datos, [], {'noticias': [dict(noticia, titulo='Actualizado')]})
    for ident in ('tab-calendario', 'tab-mensajes', 'tab-noticias-scuola', 'noticias-scuola', 'control-noticias-scuola',
                  'scuola-datos', 'scuola-lector', 'franja-local', 'franja-datos', 'mensajes-locales'):
        assert integrada.count('id="' + ident + '"') == 1, 'regeneración completa sin duplicar ' + ident
    assert integrada.count('class="noticia-scuola"') == 1
    assert 'Actualizado' in integrada and '<main id="vista-calendario">Calendario</main>' in integrada
    with tempfile.TemporaryDirectory() as tmp:
        salida = Path(tmp)
        origen = salida / 'calendario_evaluaciones.html'
        origen.write_text(html, encoding='utf-8')
        with patch('vista_previa_liston.recopilar_noticias_nube', return_value=None), patch('vista_previa_liston.recopilar_noticias', return_value=None):
            destino = generar_liston(salida, datos)
        assert destino.name == 'vista_previa_liston.html'
        assert destino.read_text(encoding='utf-8') == vista
        assert origen.read_text(encoding='utf-8') == html
        assert (salida / 'vista_previa_alertas.html').is_file(), 'conserva la alternativa anterior'
        anterior = destino.read_bytes()
        assert actualizar(salida, datos) == datos
        assert json.loads((salida / 'informacion_local.json').read_text(encoding='utf-8')) == datos
        assert destino.read_bytes() == anterior and origen.read_text(encoding='utf-8') == html
        assert not list(salida.glob('liston-*.tmp'))
        try:
            actualizar(salida, {'invalido': float('nan')})
        except ValueError:
            pass
        else:
            raise AssertionError('No debe reemplazar una lectura con JSON no válido')
        assert json.loads((salida / 'informacion_local.json').read_text(encoding='utf-8')) == datos
        assert not list(salida.glob('liston-*.tmp'))
    print('TODO OK: listón local, datos intactos, controles accesibles y fuera del publicador')


if __name__ == '__main__':
    main()
