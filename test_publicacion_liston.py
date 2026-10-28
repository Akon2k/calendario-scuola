"""Producción: diseño aprobado, fuentes públicas y capacidades originales intactas."""
import json
import re
from unittest.mock import patch

from edufacil.informacion_local import base, CHILE
from datetime import datetime
from edufacil.noticias_liston import aplicar_noticias_y_liston
from vista_previa_liston import crear_liston


def main():
    nube = {'url': 'https://ejemplo.supabase.co', 'key': 'sb_publishable_prueba', 'vapid': 'publica'}
    html = ('<html><head><style></style></head><body><header><div class="acciones">'
            '<button id="tema">Tema</button><button id="imprimir">Imprimir</button>'
            '<button id="descargar">Descargar</button><button id="nuevo">Nuevo evento</button>'
            '<button id="instalar">Instalar</button><button id="avisos">Avisos</button></div></header>'
            '<nav id="pestanas"><button id="tab-calendario">Calendario</button><button id="tab-mensajes">Mensajes</button></nav>'
            '<main id="vista-calendario">Calendario intacto</main><section id="mensajes" hidden>Mensajes intactos</section>'
            '<details id="ayuda"><summary>Ayuda</summary></details>'
            '<script type="application/json" id="nube">' + json.dumps(nube) + '</script>'
            '<script id="datos">{"eventos":[]}</script><script id="ics-b64">ICS intacto</script>'
            '<script>navigator.serviceWorker.register("sw.js");</script></body></html>')
    ahora = datetime(2026, 10, 28, 10, 0, tzinfo=CHILE)
    datos = {'consultado': ahora.isoformat(), 'lecturas': [base(t, ahora) for t in ('ruta', 'noticias', 'clima')]}
    noticias = {'noticias': [{'url': 'https://scuola.scuolaitalianadiconcepcion.cl/2026/10/27/noticia/',
                 'fecha': '2026-10-27', 'titulo': 'Titolo', 'titulo_es': 'Título'}]}
    vista = aplicar_noticias_y_liston(html, datos, noticias)
    repetida = aplicar_noticias_y_liston(vista, datos, noticias)
    for contenido in (vista, repetida):
        for ident in ('franja-local', 'franja-datos', 'liston-config', 'tab-noticias-scuola', 'scuola-lector',
                      'control-noticias-scuola', 'imprimir', 'descargar', 'botones-icono-locales', 'posicion-liston'):
            assert contenido.count('id="' + ident + '"') == 1, ident
        cfg = json.loads(re.search(r'id="nube">(.*?)</script>', contenido, re.S)[1])
        assert cfg == nube
        assert 'ICS intacto' in contenido and 'Calendario intacto' in contenido and 'Mensajes intactos' in contenido
        assert 'navigator.serviceWorker.register("sw.js");' in contenido
        assert 'vista-local-sin-cache' not in contenido and 'mensajes-locales' not in contenido
        assert '#instalar, #avisos' not in contenido
        assert 'Nuevo evento' in contenido and 'Instalar' in contenido and '>Avisos<' in contenido
        assert "frames = [{tipo: 'clima'}, {tipo: 'ruta'}, {tipo: 'noticias'}];" in contenido
        assert '/rest/v1/liston_publico?select=datos&id=eq.true' in contenido
        assert contenido.count('var paquete = JSON.parse') == 2
        assert 'Descargar calendario (.ics)' in contenido
        assert contenido.index('<header>') < contenido.index('id="franja-local"') < contenido.index('<div class="acciones">') < contenido.index('</header>')
    local = crear_liston(vista, datos, [], noticias)
    assert 'id="liston-config"' not in local, 'la vista local no se conecta a la fuente de producción'
    assert '<script type="application/json" id="nube">null</script>' in local
    try:
        aplicar_noticias_y_liston(local, datos, noticias)
    except ValueError:
        pass
    else:
        raise AssertionError('No publicar la vista previa')
    from actualizar_liston_local import publicar_snapshot
    with patch('actualizar_liston_local.subprocess.run') as proceso:
        proceso.return_value.returncode = 0
        publicar_snapshot(datos)
        args = proceso.call_args[0][0]
        assert '--file' in args and 'query' in args and '--project-ref' in args
        assert not any('secret' in str(a).lower() for a in args)
    print('TODO OK: publicación conserva nube/PWA/edición, impresión/ICS, orden del listón y noticias; regeneración sin duplicados y aislamiento de vistas locales.')


if __name__ == '__main__':
    main()
