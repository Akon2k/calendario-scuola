"""Vista personal: sólo datos ficticios, sin red ni archivos de producción."""
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from edufacil.ediciones import ConfigNube
from edufacil.informacion_local import CHILE, base
from edufacil.noticias_liston import aplicar_noticias_y_liston
from edufacil.pagina import a_html


def crear_fixture(carpeta: Path) -> Path:
    """Genera una página completa ficticia para las pruebas Python y Playwright."""
    ahora = datetime.now(CHILE)
    nube = {'url': 'https://ejemplo.supabase.co', 'key': 'sb_publishable_prueba'}
    datos = {'consultado': ahora.isoformat(),
             'lecturas': [dict(base(tipo, ahora), titulo='Título ficticio ' + tipo,
                               resumen='Resumen de prueba.', detalle='Detalle de prueba.')
                          for tipo in ('clima', 'ruta', 'noticias')]}
    noticias = {'nube': dict(nube, revision=1), 'noticias': [{
        'id': 'noticia-prueba', 'fecha': '2026-10-27', 'titulo': 'Noticia de prueba',
        'titulo_es': 'Título de prueba', 'detalle': 'Descripción ficticia.',
        'url': 'https://scuola.scuolaitalianadiconcepcion.cl/2026/10/27/prueba/',
    }]}
    with patch('requests.sessions.Session.request', side_effect=AssertionError('No usar la red')):
        ruta = a_html([{'FECHA': ahora.date().isoformat(), 'ASIGNATURA': 'MATEMÁTICA',
                        'EVALUACION': 'Evaluación ficticia', 'TIPO': 'Evaluación'}],
                      carpeta / 'index.html', nube=ConfigNube(nube['url'], nube['key']))
        html = aplicar_noticias_y_liston(ruta.read_text(encoding='utf-8'), datos, noticias)
        ruta.write_text(html, encoding='utf-8')
    return ruta


class VistaSimpleTest(unittest.TestCase):
    def test_generacion_y_reintegracion(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = crear_fixture(Path(tmp))
            html = ruta.read_text(encoding='utf-8')
            # Reintegrar el listón no borra ni duplica la preferencia personal.
            ahora = datetime.now(CHILE)
            repetida = aplicar_noticias_y_liston(html, {
                'consultado': ahora.isoformat(),
                'lecturas': [base(t, ahora) for t in ('clima', 'ruta', 'noticias')],
            }, {'noticias': []})
            for contenido in (html, repetida):
                for ident in ('vista-fouc', 'control-vista', 'cambiar-vista',
                              'tab-calendario', 'tab-mensajes', 'tab-noticias-scuola',
                              'franja-local', 'nuevo', 'avisos', 'descargar', 'imprimir'):
                    self.assertEqual(contenido.count('id="' + ident + '"'), 1, ident)
                self.assertLess(contenido.index('id="vista-fouc"'), contenido.index('<style>'))
                self.assertIn("getItem('edufacil-vista')", contenido)
                self.assertIn("setItem('edufacil-vista', vista)", contenido)
                self.assertIn('Vista completa', contenido)
                self.assertIn("getAttribute('data-vista') !== 'simple'", contenido)
                self.assertIn('html[data-vista="simple"] #clima-pronostico', contenido)
                self.assertNotIn('html[data-vista="simple"] header .marca', contenido)
                ayuda = contenido.split('<details id="ayuda">')[1].split('</details>')[0]
                self.assertEqual(ayuda.count('<li>'), 10)
                self.assertIn('sin desactivar los avisos', ayuda)


if __name__ == '__main__':
    unittest.main()
