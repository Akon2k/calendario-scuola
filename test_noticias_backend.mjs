import test from 'node:test';
import assert from 'node:assert/strict';
import {crearHandler, descargar, validarUrl} from './supabase/functions/noticias-scuola/core.mjs';
import {hashTitulo, traducirGoogle, traducirPendiente} from './supabase/functions/noticias-scuola/google.mjs';

const id = '11111111-1111-4111-8111-111111111111';
const url = 'https://scuola.scuolaitalianadiconcepcion.cl/2026/10/27/noticia/';
const noticia = {id, url, titulo: 'Titolo', titulo_es: 'Título', fecha: '2026-10-27', texto: null};
const req = (query = '?id=' + id, opciones = {}) => new Request('https://ejemplo.supabase.co/functions/v1/noticias-scuola' + query, opciones);
const base = () => ({secreto: 'secreto-de-prueba', leer: async () => ({...noticia}),
  reservar: async () => 'reserva', guardar: async () => true,
  extraer: async () => 'Un texto completo con párrafos que no contiene fotografías ni código HTML.',
  sincronizar: async () => ({ok: true})});

test('sólo URLs oficiales de 2026, sin credenciales, redirecciones ni fechas imposibles', () => {
  assert.ok(validarUrl(url));
  for (const u of [url.replace('/2026/', '/2025/'), url.replace('/10/27/', '/02/31/'),
    url.replace('https:', 'http:'), url + '?destino=http://localhost', url + '#foto',
    url.replace('.cl/', '.cl.evil.example/'), url.replace('https://', 'https://clave@'),
    url.replace('.cl/', '.cl:8443/'), 'http://127.0.0.1/']) assert.equal(validarUrl(u), false);
});

test('lecturas públicas sólo por id conocido; administración privada', async () => {
  const handler = crearHandler(base());
  assert.equal((await handler(req('', {method: 'POST'}))).status, 401);
  assert.equal((await handler(req('?url=http://127.0.0.1'))).status, 400);
  assert.equal((await handler(req('', {method: 'DELETE'}))).status, 405);
  assert.equal((await handler(req('?id=' + id, {headers: {Origin: 'https://evil.example'}}))).status, 403);
  const r = await handler(req('', {method: 'POST', headers: {'x-noticias-secret': 'secreto-de-prueba'}}));
  assert.equal(r.status, 200);
});

test('el texto se obtiene una vez y se guarda; lecturas cacheadas no consultan la fuente', async () => {
  let extracciones = 0, guardados = 0;
  const deps = base(); let texto = null;
  deps.leer = async () => ({...noticia, texto});
  deps.extraer = async () => { extracciones++; return 'Texto de la noticia, extraído de la fuente oficial y conservado en la caché.'; };
  deps.guardar = async (_id, _lease, t) => { guardados++; texto = t; return true; };
  const handler = crearHandler(deps);
  const primero = await handler(req()); const segundo = await handler(req());
  assert.equal(primero.status, 200); assert.equal(segundo.status, 200);
  assert.equal(extracciones, 1); assert.equal(guardados, 1);
  assert.equal((await primero.json()).texto, (await segundo.json()).texto);
});

test('reserva evita descargas duplicadas; un fallo conserva pendiente y no inventa texto', async () => {
  const deps = base(); let fallido = false;
  deps.reservar = async () => null;
  assert.equal((await crearHandler(deps)(req())).status, 202);
  deps.reservar = async () => 'reserva';
  deps.extraer = async () => { throw new Error('secreto que nunca debe devolverse'); };
  deps.guardar = async (_id, _lease, t) => { fallido = t === null; return true; };
  const r = await crearHandler(deps)(req());
  assert.equal(r.status, 503); assert.ok(fallido); assert.ok(!(await r.text()).includes('secreto'));
});

test('descarga acotada y sin seguir redirecciones', async () => {
  const t = await descargar(url, async (_u, opciones) => {
    assert.equal(opciones.redirect, 'error'); assert.ok(opciones.signal);
    return new Response('Contenido');
  });
  assert.equal(t, 'Contenido');
  await assert.rejects(descargar(url, async () => new Response('x'.repeat(2_000_001))), /demasiado grande/);
});

test('hashTitulo genera resumen SHA-256 determinista para la caché', async () => {
  const h1 = await hashTitulo('Festa di Primavera');
  const h2 = await hashTitulo('Festa di Primavera');
  const h3 = await hashTitulo('Altra festa');
  assert.equal(h1.length, 64);
  assert.match(h1, /^[0-9a-f]{64}$/);
  assert.equal(h1, h2);
  assert.notEqual(h1, h3);
});

test('traducirGoogle descarta entradas inválidas sin invocar el proveedor', async () => {
  let llamado = false;
  const f = async () => { llamado = true; return new Response('{}'); };
  assert.equal(await traducirGoogle('', 'key-123', f), null);
  assert.equal(await traducirGoogle('   ', 'key-123', f), null);
  assert.equal(await traducirGoogle('Título', '', f), null);
  assert.equal(await traducirGoogle('Título', null, f), null);
  assert.equal(await traducirGoogle('x'.repeat(1001), 'key-123', f), null);
  assert.equal(llamado, false);
});

test('traducirGoogle envía petición NMT, valida cabeceras y decodifica entidades', async () => {
  let urlLlamada, cabeceras, cuerpo;
  const f = async (u, opt) => {
    urlLlamada = u;
    cabeceras = opt.headers;
    cuerpo = JSON.parse(opt.body);
    return new Response(JSON.stringify({
      data: {
        translations: [{translatedText: 'D&iacute;a de los &quot;colores&quot; &amp; m&aacute;s'}]
      }
    }), {status: 200, headers: {'Content-Type': 'application/json'}});
  };
  const res = await traducirGoogle('Giornata dei colori', 'google-key-abc', f);
  assert.equal(urlLlamada, 'https://translation.googleapis.com/language/translate/v2');
  assert.equal(cabeceras['x-goog-api-key'], 'google-key-abc');
  assert.equal(cabeceras['Content-Type'], 'application/json; charset=utf-8');
  assert.deepEqual(cuerpo, {q: ['Giornata dei colori'], source: 'it', target: 'es', format: 'text', model: 'nmt'});
  assert.equal(res, 'Día de los "colores" & más');
});

test('traducirGoogle nunca lanza errores ni expone secretos si Google falla', async () => {
  const fError = async () => new Response('{"error":{"message":"clave privada o interna"}}', {status: 403});
  const res = await traducirGoogle('Giornata', 'google-key-abc', fError);
  assert.equal(res, null);

  const fRed = async () => { throw new Error('fallo de red que contiene secreto-123'); };
  const resRed = await traducirGoogle('Giornata', 'google-key-abc', fRed);
  assert.equal(resRed, null);
});

test('traducirPendiente reutiliza la caché y no gasta cuota si ya está traducido', async () => {
  let consultasGoogle = 0;
  const deps = {
    key: 'google-key-xyz',
    fetcher: async () => { consultasGoogle++; return new Response('{}'); },
    reservar: async () => ({estado: 'cache', traduccion: 'Título guardado en español'}),
    guardar: async () => true,
  };
  const res = await traducirPendiente('Titolo gia tradotto', deps);
  assert.equal(res, 'Título guardado en español');
  assert.equal(consultasGoogle, 0);
});

test('traducirPendiente reserva, traduce y guarda con lease; respeta límites y fallos', async () => {
  let guardadoCon = null;
  const deps = {
    key: 'google-key-xyz',
    fetcher: async () => new Response(JSON.stringify({
      data: {translations: [{translatedText: 'Título traducido'}]}
    }), {status: 200, headers: {'Content-Type': 'application/json'}}),
    reservar: async () => ({estado: 'reservada', lease: 'lease-uuid-789'}),
    guardar: async (hash, lease, texto) => { guardadoCon = {hash, lease, texto}; return true; },
  };
  const res = await traducirPendiente('Nuovo titolo', deps);
  assert.equal(res, 'Título traducido');
  assert.equal(guardadoCon?.lease, 'lease-uuid-789');
  assert.equal(guardadoCon?.texto, 'Título traducido');

  // Si se alcanzó el límite diario/mensual en la base de datos
  deps.reservar = async () => ({estado: 'limite'});
  let llamadaGoogle = false;
  deps.fetcher = async () => { llamadaGoogle = true; return new Response('{}'); };
  const resLimite = await traducirPendiente('Nuovo titolo', deps);
  assert.equal(resLimite, null);
  assert.equal(llamadaGoogle, false);

  // Si Google falla, libera la reserva con texto nulo
  let leaseLiberado = null;
  deps.reservar = async () => ({estado: 'reservada', lease: 'lease-uuid-999'});
  deps.fetcher = async () => new Response('Error', {status: 500});
  deps.guardar = async (hash, lease, texto) => { leaseLiberado = {lease, texto}; return true; };
  const resFallo = await traducirPendiente('Nuovo titolo', deps);
  assert.equal(resFallo, null);
  assert.equal(leaseLiberado?.lease, 'lease-uuid-999');
  assert.equal(leaseLiberado?.texto, null);
});

