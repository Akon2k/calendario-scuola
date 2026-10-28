import test from 'node:test';
import assert from 'node:assert/strict';
import {hashTitulo, traducirGoogle, traducirPendiente} from './supabase/functions/noticias-scuola/google.mjs';

test('Google usa NMT, sólo un título, italiano a español y clave fuera de la URL', async () => {
  const texto = await traducirGoogle('Novità della Scuola', 'clave-de-prueba', async (url, opciones) => {
    assert.equal(url, 'https://translation.googleapis.com/language/translate/v2');
    assert.ok(!url.includes('clave-de-prueba'));
    assert.equal(opciones.headers['x-goog-api-key'], 'clave-de-prueba');
    assert.equal(opciones.redirect, 'error');
    assert.deepEqual(JSON.parse(opciones.body), {q: ['Novità della Scuola'], source: 'it', target: 'es', format: 'text', model: 'nmt'});
    return Response.json({data: {translations: [{translatedText: 'Novedades &amp; noticias de la Scuola'}]}});
  });
  assert.equal(texto, 'Novedades & noticias de la Scuola');
});

test('sin clave, vacío o demasiado largo no llama al proveedor', async () => {
  const fallar = async () => { throw Error('No debe llamar'); };
  assert.equal(await traducirGoogle('Titolo', '', fallar), null);
  assert.equal(await traducirGoogle('', 'prueba', fallar), null);
  assert.equal(await traducirGoogle('a'.repeat(1001), 'prueba', fallar), null);
  assert.equal(await traducirPendiente('Titolo', {key: '', reservar: fallar}), null);
});

test('errores, cuotas y respuestas inválidas no se convierten en traducciones', async () => {
  for (const codigo of [400, 401, 403, 429, 500]) {
    assert.equal(await traducirGoogle('Titolo', 'prueba', async () => new Response('error privado', {status: codigo})), null);
  }
  for (const j of [{}, {data: {translations: []}}, {data: {translations: [{translatedText: ' '}]}}]) {
    assert.equal(await traducirGoogle('Titolo', 'prueba', async () => Response.json(j)), null);
  }
});

test('una reserva previa es obligatoria; caché y límites evitan llamadas pagadas', async () => {
  let llamadas = 0;
  const fetcher = async () => { llamadas++; return Response.json({data: {translations: [{translatedText: 'Título'}]}}); };
  for (const estado of ['desactivada', 'limite', 'ocupada', 'espera']) {
    assert.equal(await traducirPendiente('Titolo', {key: 'prueba', reservar: async () => ({estado}), fetcher}), null);
  }
  assert.equal(await traducirPendiente('Titolo', {key: 'prueba', reservar: async () => ({estado: 'cache', traduccion: 'Título guardado'}), fetcher}), 'Título guardado');
  assert.equal(llamadas, 0);
  let guardado;
  const t = await traducirPendiente('Titolo', {key: 'prueba', fetcher,
    reservar: async (hash, titulo) => {
      assert.equal(hash, await hashTitulo(titulo));
      return {estado: 'reservada', lease: 'reserva'};
    }, guardar: async (hash, lease, texto) => { guardado = {hash, lease, texto}; return true; }});
  assert.equal(t, 'Título'); assert.equal(llamadas, 1); assert.equal(guardado.texto, 'Título');
});

test('un fallo se registra sin reintentar el proveedor en bucle', async () => {
  let intentos = 0, guardado = 'sin registrar';
  const t = await traducirPendiente('Titolo', {key: 'prueba',
    reservar: async () => ({estado: 'reservada', lease: 'reserva'}),
    fetcher: async () => { intentos++; throw Error('No disponible'); },
    guardar: async (_h, _l, texto) => { guardado = texto; return true; }});
  assert.equal(t, null); assert.equal(intentos, 1); assert.equal(guardado, null);
});
