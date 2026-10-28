"""Parsers, vigencia y fallos de fuentes públicas: pruebas sin red."""
import json
from datetime import datetime
from unittest.mock import patch

import requests

from edufacil import informacion_local as info

AHORA = datetime(2026, 10, 27, 21, 30, tzinfo=info.CHILE)


def noticia(titulo, fecha, url):
    return f'<div class="article-text-container"><a href="{url}"><h2>{titulo}</h2></a><div class="article-date-hour">{fecha}</div></div>'


URL = 'https://www.biobiochile.cl/noticias/nacional/region-del-bio-bio/2026/10/27/'
HTML_NOTICIAS = (
    noticia('Noticias regionales', 'Martes 27 Octubre, 2026 | 20:00', URL + 'regional.shtml')
    + noticia('Actividad en Coronel', 'Martes 27 Octubre, 2026 | 11:00', URL + 'coronel.shtml')
    + noticia('No debe salir del futuro', 'Miércoles 28 Octubre, 2026 | 20:00', URL + 'futura.shtml')
    + noticia('Muy antigua', 'Lunes 01 Junio, 2026 | 12:00', URL + 'vieja.shtml')
    + noticia('Coronel insegura', 'Martes 27 Octubre, 2026 | 12:00', 'https://evil.example/noticias/nacional/region-del-bio-bio/robo')
)


def tarjeta(fecha, sector='Ruta 160 - Coronel'):
    return f'''<div class="card--state"><div class="card--state__header">{sector}</div>
    <div class="card--state__text"><div><strong>Categoría:</strong> Trabajos <strong>{fecha}</strong></div>
    <p><strong>Descripción</strong> Obras informadas por la fuente.</p>
    <a href="https://biobio.transporteinforma.cl/estado-de-la-movilidad/informe/">Ver</a></div></div>'''


METEO = {'utc_offset_seconds': -10800,
         'current': {'time': '2026-10-27T21:00', 'temperature_2m': 12.4,
                     'wind_speed_10m': 8.2, 'precipitation': 0, 'weather_code': 3},
         'daily': {'time': ['2026-10-27'], 'temperature_2m_min': [8],
                   'temperature_2m_max': [16], 'precipitation_probability_max': [20]}}


def main():
    titulares = info.parsear_noticias(HTML_NOTICIAS, AHORA)
    assert [n['titulo'] for n in titulares] == ['Actividad en Coronel', 'Noticias regionales']
    regional = noticia('Actualidad del Biobío', 'Martes 27 Octubre, 2026 | 20:00', URL + 'regional.shtml')
    nacional = (
        noticia('Noticias de Santiago', 'Martes 27 Octubre, 2026 | 20:30',
                'https://www.biobiochile.cl/noticias/nacional/region-metropolitana/2026/10/27/santiago.shtml')
        + noticia('Noticias de Coquimbo', 'Martes 27 Octubre, 2026 | 20:00',
                'https://www.biobiochile.cl/noticias/nacional/region-de-coquimbo/2026/10/27/coquimbo.shtml')
        + noticia('No incluir internacionales', 'Martes 27 Octubre, 2026 | 20:45',
                'https://www.biobiochile.cl/noticias/internacional/2026/10/27/internacional.shtml')
        + noticia('No incluir futuro', 'Miércoles 28 Octubre, 2026 | 20:00',
                'https://www.biobiochile.cl/noticias/nacional/chile/2026/10/28/futuro.shtml')
        + noticia('No incluir enlace ajeno', 'Martes 27 Octubre, 2026 | 20:00',
                'https://evil.example/noticias/nacional/2026/10/27/falsa.shtml')
    )
    for fuente_regional in (regional, '', noticia('Coronel antigua', 'Lunes 01 Junio, 2026 | 12:00', URL + 'antigua.shtml')):
        with patch.object(info, 'descargar', side_effect=[fuente_regional, nacional]) as descarga:
            respaldo = info.noticias(AHORA)
        assert [c.args[0] for c in descarga.call_args_list] == [info.BIOBIO, info.BIOBIO_NACIONAL]
        assert [n['titulo'] for n in respaldo['enlaces']] == ['Noticias de Santiago', 'Noticias de Coquimbo']
        assert respaldo['estado'] == 'ok' and 'Noticias de Chile' in respaldo['resumen']
    with patch.object(info, 'descargar', return_value=HTML_NOTICIAS) as descarga:
        local = info.noticias(AHORA)
    assert descarga.call_count == 1 and local['titulo'] == 'Actividad en Coronel'
    with patch.object(info, 'descargar', side_effect=[regional, '']):
        sin_nacionales = info.noticias(AHORA)
    assert sin_nacionales['estado'] == 'sinreportes' and sin_nacionales['enlaces'] == []
    assert sin_nacionales['url'] == info.BIOBIO_NACIONAL
    muchas_regionales = ''.join(noticia('Regional ' + str(i), 'Martes 27 Octubre, 2026 | 20:00',
        URL + 'regional-' + str(i) + '.shtml') for i in range(15))
    local_prioritaria = noticia('Coronel tiene prioridad', 'Martes 27 Octubre, 2026 | 11:00', URL + 'coronel-prioritaria.shtml')
    seleccion = info.parsear_noticias(muchas_regionales + local_prioritaria * 2, AHORA)
    assert info.MAX_NOTICIAS == 10 and len(seleccion) == 10
    assert seleccion[0]['titulo'] == 'Coronel tiene prioridad'
    assert len({n['url'] for n in seleccion}) == 10, 'no repetir titulares para completar el cupo'
    muchas_nacionales = ''.join(noticia('Nacional ' + str(i), 'Martes 27 Octubre, 2026 | 20:00',
        'https://www.biobiochile.cl/noticias/nacional/chile/2026/10/27/nacional-' + str(i) + '.shtml') for i in range(15))
    with patch.object(info, 'descargar', side_effect=[regional, muchas_nacionales]):
        seleccion_nacional = info.noticias(AHORA)
    assert len(seleccion_nacional['enlaces']) == 10
    assert 'Noticias de Chile' in seleccion_nacional['resumen']
    assert info.fecha_es('23 de octubre de 2026').day == 23
    assert info.fecha_es('31 de febrero de 2026') is None
    assert not info.enlace_valido('https://www.biobiochile.cl.evil.example/', 'www.biobiochile.cl')
    assert not info.enlace_valido('javascript:alert(1)', 'www.biobiochile.cl')
    assert not info.enlace_valido('https://www.biobiochile.cl:8443/', 'www.biobiochile.cl')
    reportes, cantidad = info.parsear_ruta(tarjeta('27 de octubre de 2026')
        + tarjeta('26 de octubre de 2026') + tarjeta('27 de octubre de 2026', 'Otra comuna'), AHORA)
    assert cantidad == 3 and len(reportes) == 1 and reportes[0]['precision'] == 'dia'

    def descargar(url, **kwargs):
        if url == info.BIOBIO:
            return HTML_NOTICIAS
        if url == info.METEO:
            assert kwargs['parametros']['latitude'] == -37.03386
            assert kwargs['parametros']['longitude'] == -73.14019
            return json.dumps(METEO)
        if url == info.AJAX_TRANSITO:
            assert kwargs['metodo'] == 'POST'
            assert kwargs['datos']['action'] == 'get_incidents'
            return json.dumps({'success': True, 'data': tarjeta('26 de octubre de 2026')})
        raise AssertionError('Destino imprevisto')

    with patch.object(info, 'descargar', side_effect=descargar):
        datos = info.recopilar(AHORA)
    por_tipo = {d['id']: d for d in datos['lecturas']}
    assert por_tipo['noticias']['titulo'] == 'Actividad en Coronel'
    assert por_tipo['noticias']['detalle'] == '', 'sin explicación del proceso en el detalle de noticias'
    assert '12,4 °C' in por_tipo['clima']['titulo']
    assert 'no alerta oficial' in por_tipo['clima']['resumen']
    assert por_tipo['ruta']['estado'] == 'sinreportes'
    assert 'No significa' in por_tipo['ruta']['resumen']
    assert all('consultado' in d for d in datos['lecturas'])
    def fallo_parcial(url, **kwargs):
        if url == info.BIOBIO:
            raise requests.Timeout()
        return descargar(url, **kwargs)
    with patch.object(info, 'descargar', side_effect=fallo_parcial):
        parcial = {d['id']: d for d in info.recopilar(AHORA)['lecturas']}
    assert parcial['noticias']['estado'] == 'error' and parcial['clima']['estado'] == 'ok'

    for valor in [True, None, '12', float('nan'), float('inf'), 10000]:
        try:
            info.numero(valor, -80, 65)
        except ValueError:
            pass
        else:
            raise AssertionError('Número no válido aceptado')
    vieja = json.loads(json.dumps(METEO))
    vieja['current']['time'] = '2025-10-27T21:00'
    with patch.object(info, 'descargar', return_value=json.dumps(vieja)):
        try:
            info.tiempo(AHORA)
        except ValueError:
            pass
        else:
            raise AssertionError('No mostrar clima antiguo como actual')
    with patch.object(info, 'descargar', side_effect=requests.Timeout):
        fallos = info.recopilar(AHORA)
    assert all(d['estado'] == 'error' for d in fallos['lecturas'])
    assert all('no disponible' in d['titulo'] for d in fallos['lecturas'])
    print('TODO OK: fuentes, Coronel, fechas, títulos, URLs, fallos y datos caducados sin inventar estado vial')


if __name__ == '__main__':
    main()
