// Navegador real, sin producción: genera en TEMP y simula TODAS las peticiones.
// node test_vista_simple.mjs (Playwright instalado, o PLAYWRIGHT_MODULE indicando su ruta).
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, readFileSync, rmSync } from 'node:fs';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const temporal = join(tmpdir(), 'opencode');
mkdirSync(temporal, { recursive: true });
const carpeta = mkdtempSync(join(temporal, 'scuola-vista-simple-'));
let browser;
const errores = [];
const origen = 'http://calendario.test';
try {
  execFileSync('python', ['-X', 'utf8', '-c',
    'from pathlib import Path; import sys; from test_vista_simple import crear_fixture; crear_fixture(Path(sys.argv[1]))',
    carpeta], { cwd: import.meta.dirname, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
  const html = readFileSync(join(carpeta, 'index.html'), 'utf8');
  browser = await chromium.launch({ headless: true });
  async function contexto(opciones = {}) {
    const ctx = await browser.newContext({ serviceWorkers: 'block', ...opciones });
    ctx.on('page', p => p.on('pageerror', e => errores.push(e.stack)));
    await ctx.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.origin === origen) {
        return route.fulfill({ status: url.pathname === '/' ? 200 : 404,
          contentType: 'text/html', body: url.pathname === '/' ? html : '' });
      }
      let datos = [];
      if (url.pathname === '/rest/v1/comunicados') datos = [{
        id: 'mensaje-prueba', fecha: '2026-10-27T12:00:00Z', asunto: 'Comunicado de prueba',
        puntos: ['Texto ficticio.'], accion: '', eventos: [],
      }];
      if (url.pathname.includes('noticias_scuola_revision')) datos = [{ version: 1 }];
      if (url.pathname === '/functions/v1/noticias-scuola') {
        datos = { id: 'noticia-prueba', texto: 'Texto ficticio del lector de noticias.' };
      }
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify(datos) });
    });
    return ctx;
  }
  async function visible(p, selector, valor = true) {
    assert.equal(await p.locator(selector).isVisible(), valor, selector);
  }
  async function simple(p) {
    assert.equal(await p.locator('html').getAttribute('data-vista'), 'simple');
    for (const s of ['#franja-local', '#clima-ubicacion', '#clima .actual',
                     '#clima-pronostico', '#nuevo', '#descargar',
                     '#imprimir', '#avisos-estado', '#nube-estado']) await visible(p, s, false);
    for (const s of ['header .marca', '#clima .hora', '#anterior', '#mes-actual', '#siguiente', '#hoy', '#cambiar-vista',
                     '#tab-calendario', '#tab-mensajes', '#tab-noticias-scuola']) await visible(p, s);
    assert.equal(await p.locator('#cambiar-vista').innerText(), 'Vista completa');
    assert.equal(await p.locator('#cambiar-vista').getAttribute('aria-expanded'), 'false');
  }
  const escritorio = await contexto({ viewport: { width: 1280, height: 900 } });
  const p = await escritorio.newPage();
  await p.clock.install();
  await p.goto(origen);
  await visible(p, 'header .marca');
  await visible(p, '#franja-local');
  await p.locator('#cambiar-vista').focus();
  await p.keyboard.press('Enter');
  await simple(p);
  assert.equal(await p.evaluate(() => localStorage.getItem('edufacil-vista')), 'simple');
  await p.reload();
  await simple(p);

  // El cambio no altera la pestaña activa ni impide navegar por los meses.
  const mes = await p.locator('#mes-actual').innerText();
  await p.locator('#siguiente').click();
  assert.notEqual(await p.locator('#mes-actual').innerText(), mes);
  await p.locator('#anterior').click();
  assert.equal(await p.locator('#mes-actual').innerText(), mes);
  await p.locator('#tab-mensajes').click();
  await visible(p, '#mensajes');
  await visible(p, '#vista-calendario', false);
  await p.locator('#cambiar-vista').click();
  await visible(p, '#mensajes');
  await visible(p, '#franja-local');
  await visible(p, '#nuevo');
  await p.locator('#tab-noticias-scuola').click();
  await p.locator('#cambiar-vista').click();
  await simple(p);
  await visible(p, '#noticias-scuola');
  await visible(p, '#mensajes', false);
  await p.locator('.noticia-scuola a').first().click();
  await visible(p, '#scuola-lector');
  await p.keyboard.press('Escape');

  // La rotación automática no sigue cambiando un listón oculto.
  const frame = await p.locator('#liston-contador').innerText();
  await p.clock.runFor(11000);
  assert.equal(await p.locator('#liston-contador').innerText(), frame);
  await p.locator('#cambiar-vista').click();
  await p.locator('#tab-calendario').click();
  await p.mouse.move(0, 0);
  await p.clock.runFor(5000);
  assert.notEqual(await p.locator('#liston-contador').innerText(), frame);
  await p.locator('#cambiar-vista').click();

  // Otra pestaña del mismo navegador respeta y actualiza la preferencia.
  const otra = await escritorio.newPage();
  await otra.goto(origen);
  await simple(otra);
  await otra.locator('#cambiar-vista').click();
  await p.waitForFunction(() => document.documentElement.dataset.vista === 'completa');
  await otra.locator('#cambiar-vista').click();
  await p.waitForFunction(() => document.documentElement.dataset.vista === 'simple');
  const estado = await escritorio.storageState();
  const reabierto = await contexto({ storageState: estado });
  const r = await reabierto.newPage();
  await r.goto(origen);
  await simple(r);

  // Navegador/teléfono independiente: empieza completo y conserva su elección.
  const movil = await contexto({ viewport: { width: 390, height: 844 },
    isMobile: true, hasTouch: true, deviceScaleFactor: 3, colorScheme: 'dark' });
  const m = await movil.newPage();
  await m.goto(origen);
  await visible(m, '#franja-local');
  await m.locator('#cambiar-vista').tap();
  await simple(m);
  for (const [width, height] of [[320, 740], [390, 844], [430, 932], [844, 390]]) {
    await m.setViewportSize({ width, height });
    await simple(m);
    assert.ok(await m.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      `Sin desbordamiento a ${width}px`);
    const boton = await m.locator('#cambiar-vista').boundingBox();
    assert.ok(boton.height >= 44 && boton.x + boton.width <= width);
  }
  await m.reload();
  await simple(m);
  await m.locator('#cambiar-vista').tap();
  await visible(m, '#franja-local');
  await simple(r); // El teléfono no modifica la preferencia del otro contexto.

  // Imprimir desde vista simple conserva el título y el calendario.
  await r.emulateMedia({ media: 'print' });
  await visible(r, 'header .marca');
  await visible(r, '#vista-calendario');
  await visible(r, '#cambiar-vista', false);
  await visible(r, '#franja-local', false);

  // Si el navegador bloquea el almacenamiento, el selector aún funciona.
  const sinStorage = await contexto();
  await sinStorage.addInitScript(() => Object.defineProperty(window, 'localStorage', {
    get() { throw new DOMException('Almacenamiento bloqueado', 'SecurityError'); },
  }));
  const s = await sinStorage.newPage();
  await s.goto(origen);
  await s.locator('#cambiar-vista').click();
  await simple(s);
  await s.locator('#cambiar-vista').click();
  await visible(s, '#franja-local');
  assert.deepEqual(errores, [], 'Sin errores JavaScript');
  console.log('OK: escritorio, móvil 320–844px, teclado/tacto, recarga/reapertura, aislamiento, pestañas, lector, rotación, impresión y almacenamiento bloqueado. Todo con datos ficticios.');
} finally {
  if (browser) await browser.close();
  // Sólo se elimina la carpeta temporal única creada por esta prueba.
  rmSync(carpeta, { recursive: true, force: true });
}
