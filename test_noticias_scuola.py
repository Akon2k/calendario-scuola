"""Noticias de la Scuola: sólo 2026, contenido seguro y pestaña sólo local."""
from datetime import datetime
import json
from unittest.mock import patch

import requests

from edufacil.informacion_local import CHILE
from publicar import ARCHIVOS
from vista_noticias_scuola import API, DOMINIO, FUENTE, completar_miniaturas, integrar_noticias, parsear_noticias, recopilar_noticias


def tarjeta(url, titulo='Titular real &amp; original', imagen=None):
    return ('<div class="vc_grid-item"><a class="vc_gitem-link" href="' + url + '"></a>'
            '<div class="vc_gitem-post-data-source-post_title"><h4>' + titulo + '</h4></div>'
            '<div class="vc_gitem-post-data-source-post_excerpt"><p>Detalle real de la publicación.</p></div>'
            '<img src="' + (imagen or 'https://' + DOMINIO + '/wp-content/uploads/2026/foto.jpg') + '"></div>')


def main():
    ahora = datetime(2026, 10, 27, 23, 30, tzinfo=CHILE)
    base = 'https://' + DOMINIO
    url = base + '/2026/10/27/noticia/'
    html = (tarjeta(url) + tarjeta(url) + tarjeta(base + '/2025/10/27/antigua/')
            + tarjeta(base + '/2027/01/01/futura/') + tarjeta(base + '/2026/12/01/futura/')
            + tarjeta(base + '/2026/02/31/invalida/') + tarjeta('https://evil.example/2026/10/27/falsa/')
            + tarjeta(base + '/2026/10/26/otra/', imagen='javascript:alert(1)')
            + tarjeta('javascript:alert(1)'))
    noticias = parsear_noticias(html, ahora)
    assert len(noticias) == 2 and noticias[0]['url'] == url
    assert noticias[0]['titulo'] == 'Titular real & original'
    assert noticias[1]['imagen'] == ''
    assert noticias[0]['detalle'] == 'Detalle real de la publicación.'
    assert noticias[0]['miniatura'] == ''
    assert all(n['fecha'].startswith('2026-') for n in noticias)
    with patch('vista_noticias_scuola.descargar', return_value=html) as descarga:
        datos = recopilar_noticias(ahora)
    assert datos['estado'] == 'ok' and datos['noticias'] == noticias
    assert descarga.call_args_list[0].args[0] == FUENTE
    mini = base + '/wp-content/uploads/2026/foto-150x150.jpg'
    entradas = [{'link': url, 'excerpt': {'rendered': '<p>Detalle <b>completo</b>, sin recortes.</p>'},
                 '_embedded': {'wp:featuredmedia': [{'media_details': {'sizes': {
                     'full': {'width': 1920, 'height': 800, 'source_url': base + '/wp-content/uploads/grande.jpg'},
                     'thumbnail': {'width': 150, 'height': 150, 'source_url': mini},
                     'insegura': {'width': 100, 'height': 100, 'source_url': 'https://evil.example/foto.jpg'}
                 }}}]}}]
    with patch('vista_noticias_scuola.descargar', return_value=json.dumps(entradas)) as api:
        completar_miniaturas(noticias)
    assert api.call_args.args[0] == API and api.call_args.kwargs['parametros']['per_page'] == 100
    assert noticias[0]['miniatura'] == mini
    assert noticias[0]['detalle'] == 'Detalle completo , sin recortes.'
    assert noticias[1]['miniatura'] == '', 'si no hay miniatura, no descargar foto grande'
    with patch('vista_noticias_scuola.descargar', side_effect=requests.Timeout):
        assert recopilar_noticias(ahora)['estado'] == 'error'
    base_html = ('<html><head><style></style></head><body><nav id="pestanas">'
                 '<button id="tab-calendario">Calendario</button><button id="tab-mensajes">Mensajes</button></nav>'
                 '<div id="vistas"><main id="vista-calendario">Calendario intacto</main>'
                 '<section id="mensajes" hidden>Mensajes intactos</section></div></body></html>')
    maliciosa = dict(noticias[0], titulo='<script>alert(1)</script>', titulo_es='Traducción <b>segura</b>', detalle='<img src=x onerror=alert(1)>')
    vista = integrar_noticias(base_html, {'estado': 'ok', 'noticias': [maliciosa] * 14 + [
        dict(noticias[0], url=base + '/2025/01/01/no/'), dict(noticias[0], fecha='2025-01-01')]})
    assert vista.index('id="tab-calendario"') < vista.index('id="tab-mensajes"') < vista.index('id="tab-noticias-scuola"')
    assert vista.count('class="noticia-scuola"') == 14
    assert vista.count('class="noticia-scuola" hidden') == 2
    assert 'Calendario intacto' in vista and 'Mensajes intactos' in vista
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in vista and '<script>alert(1)</script>' not in vista
    assert 'Noticias Scuola · 2026' in vista
    assert 'target="_blank" rel="noopener noreferrer"' in vista
    assert 'data-src="' + mini + '"' in vista and '<img src="' not in vista
    assert 'class="scuola-extracto"' in vista and '&lt;img src=x onerror=alert(1)&gt;' in vista
    assert 'IntersectionObserver' in vista
    assert '(Traducción &lt;b&gt;segura&lt;/b&gt;)' in vista
    assert 'id="scuola-lector"' in vista and 'id="cuenta-noticias-scuola"' in vista
    assert 'noticias_scuola_revision?select=version' in vista
    assert 'edufacil-noticias-scuola-leidas' in vista
    assert 'p.textContent = t;' in vista, 'el lector nunca inserta HTML de las noticias'
    renovada = integrar_noticias(vista, {'noticias': [dict(noticias[0], titulo='Título actualizado')]})
    for ident in ('tab-noticias-scuola', 'noticias-scuola', 'cuenta-noticias-scuola', 'scuola-lector',
                  'scuola-config', 'scuola-datos', 'control-noticias-scuola'):
        assert renovada.count('id="' + ident + '"') == 1, 'no duplicar ' + ident
    assert renovada.count('#noticias-scuola { position:') == 1
    assert renovada.count('class="noticia-scuola"') == 1 and 'Título actualizado' in renovada
    assert 'Calendario intacto' in renovada and 'Mensajes intactos' in renovada
    try:
        integrar_noticias(base_html, {'noticias': [], 'nube': {'key': 'privada-no-usar'}})
    except ValueError:
        pass
    else:
        raise AssertionError('No incrustar claves no públicas')
    assert 'No se pudieron cargar' in integrar_noticias(base_html, {'noticias': []})
    assert not any(a in ('vista_previa_liston.html', 'noticias_scuola.json') for a, _ in ARCHIVOS)
    print('TODO OK: sólo 2026, URLs oficiales, fechas válidas, duplicados, fallos, HTML seguro y tres pestañas locales.')


if __name__ == '__main__':
    main()
