"""Sin red: la franja de ejemplo nunca debe tocar la página publicable."""
import json
import re
import tempfile
from pathlib import Path

from publicar import ARCHIVOS
from vista_previa_alertas import crear_vista_previa, generar


def main():
    html = ('<html><head><style>body{color:black}</style></head><body><header>Calendario</header>'
            '<script type="application/json" id="nube">{"url":"https://prueba.supabase.co","key":"publica"}</script>'
            '<main id="vista-calendario">Datos</main></body></html>')
    vista = crear_vista_previa(html)
    assert '<script type="application/json" id="nube">null</script>' in vista
    assert vista.index('id="franja-local"') > vista.index('</header>')
    assert vista.index('id="franja-local"') < vista.index('<main')
    datos = json.loads(re.search(r'id="franja-datos">(.*?)</script>', vista, re.S)[1])
    assert [d['id'] for d in datos] == ['ruta', 'clima', 'noticias']
    assert all('Ejemplo' in d['titulo'] and 'DISEÑO' in d['detalle'] for d in datos)
    assert 'no reportes en vivo' in vista
    assert not any(origen == 'vista_previa_alertas.html' for origen, destino in ARCHIVOS)
    with tempfile.TemporaryDirectory() as tmp:
        salida = Path(tmp)
        base = salida / 'calendario_evaluaciones.html'
        base.write_text(html, encoding='utf-8')
        destino = generar(salida)
        assert destino.name == 'vista_previa_alertas.html'
        assert base.read_text(encoding='utf-8') == html
        assert destino.read_text(encoding='utf-8') == vista
    try:
        crear_vista_previa('<html>incompleto</html>')
    except ValueError:
        pass
    else:
        raise AssertionError('No debe generar una vista sin poder desactivar la nube')
    print('TODO OK: copia local, ejemplos claros, sin Supabase y fuera del publicador')


if __name__ == '__main__':
    main()
