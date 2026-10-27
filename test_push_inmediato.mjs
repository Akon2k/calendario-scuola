// Sin red: node --test test_push_inmediato.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { crearMensaje, crearHandler, endpointPermitido, procesarTrabajo }
  from './supabase/functions/avisos-ediciones/core.mjs';

const pagina = 'https://akon2k.github.io/calendario-scuola/';
const base = { id: 'edicion-1', tipo: 'correccion', clave: 'MATEMÁTICA|3|EVALUACIÓN#1',
  autor: 'Ana', campos: { CONTENIDO: 'Nuevo contenido' }, previo: { CONTENIDO: 'Anterior' } };

test('texto, fecha, nuevo evento, PDF y deshacer tienen notificación', () => {
  const texto = crearMensaje(base, pagina);
  assert.match(texto.titulo, /actualizada/);
  assert.match(texto.cuerpo, /MATEMÁTICA.*contenido.*Ana/);
  const fecha = crearMensaje({ ...base, campos: { FECHA: '2026-11-05' },
    previo: { FECHA: '2026-11-02' } }, pagina);
  assert.match(fecha.titulo, /fecha/);
  assert.match(fecha.cuerpo, /02\/11\/2026 → 05\/11\/2026/);
  const nuevo = crearMensaje({ ...base, tipo: 'nuevo', campos: {
    ASIGNATURA: 'INGLÉS', FECHA: '2026-11-10', EVALUACION: 'Quiz' } }, pagina);
  assert.match(nuevo.cuerpo, /INGLÉS.*10\/11\/2026.*Quiz/);
  const pdf = crearMensaje({ ...base, tipo: 'adjunto', campos: { nombre: 'guia.pdf' } }, pagina);
  assert.match(pdf.titulo, /PDF/);
  assert.match(pdf.cuerpo, /guia.pdf/);
  assert.match(crearMensaje({ ...base, tipo: 'anula' }, pagina).titulo, /deshecho/);
  for (const mensaje of [texto, fecha, nuevo, pdf]) {
    assert.equal(mensaje.url, pagina);
    assert.equal(mensaje.tag, 'edicion-edicion-1');
  }
});

test('sin cambios o tipos desconocidos no inventa un aviso; textos acotados', () => {
  assert.equal(crearMensaje({ ...base, campos: base.previo }, pagina), null);
  assert.equal(crearMensaje({ ...base, tipo: 'cualquiera' }, pagina), null);
  const m = crearMensaje({ ...base, autor: 'X\n'.repeat(400),
    campos: { CONTENIDO: 'a'.repeat(9000) } }, pagina);
  assert.ok(m.cuerpo.length <= 300);
  assert.ok(!m.cuerpo.includes('\n'));
});

test('endpoints permitidos: Chrome, Firefox, iPhone y Windows; nunca red interna', () => {
  for (const url of ['https://fcm.googleapis.com/fcm/send/a',
    'https://updates.push.services.mozilla.com/wpush/v2/a',
    'https://web.push.apple.com/Q/a', 'https://wns2-x.notify.windows.com/w/?a']) {
    assert.equal(endpointPermitido(url), true, url);
  }
  for (const url of ['http://fcm.googleapis.com/a', 'https://127.0.0.1/a',
    'https://169.254.169.254/', 'https://ejemplo.com/',
    'https://fcm.googleapis.com.evil.example/', 'https://fcm.googleapis.com:8080/',
    'https://x:y@fcm.googleapis.com/', 'archivo cualquiera']) {
    assert.equal(endpointPermitido(url), false, url);
  }
});

test('cada destinatario guarda su resultado; 404/410 caduca, 429/500 reintenta', async () => {
  const guardados = [], enviados = [];
  const trabajo = { id: base.id, lease: 'lease-1', edicion: base,
    entregas: ['ok', '404', '410', '429', '500'].map((id) => ({
      endpoint: 'https://fcm.googleapis.com/' + id, p256dh: 'publica', auth: 'oculta' })) };
  trabajo.entregas.push({ endpoint: 'https://localhost/privado' });
  const resultados = await procesarTrabajo(trabajo, { pagina,
    enviar: async (s) => {
      enviados.push(s.endpoint);
      const codigo = s.endpoint.split('/').at(-1);
      if (codigo !== 'ok') throw { statusCode: Number(codigo) };
    },
    resultado: async (...args) => guardados.push(args),
  });
  assert.deepEqual(resultados, { enviados: 1, caducas: 3, errores: 2, omitidos: 0 });
  assert.equal(enviados.length, 5, 'no se contacta localhost');
  assert.equal(guardados.length, 6);
  assert.ok(guardados.every(([id, lease]) => id === base.id && lease === 'lease-1'));
});

test('un registro inválido se omite, nunca retira suscripciones válidas', async () => {
  const estados = [];
  await procesarTrabajo({ id: base.id, lease: 'l',
    edicion: { ...base, campos: base.previo },
    entregas: [{ endpoint: 'https://fcm.googleapis.com/a' }] }, { pagina,
    enviar: async () => assert.fail('no debe enviar'),
    resultado: async (_id, _lease, _endpoint, estado) => estados.push(estado),
  });
  assert.deepEqual(estados, ['omitido']);
});

test('máximo cinco conexiones simultáneas', async () => {
  let actuales = 0, maximo = 0;
  await procesarTrabajo({ id: base.id, lease: 'l', edicion: base,
    entregas: Array.from({ length: 25 }, (_, n) => ({
      endpoint: 'https://fcm.googleapis.com/' + n })) }, { pagina,
    enviar: async () => {
      maximo = Math.max(maximo, ++actuales);
      await new Promise((r) => setTimeout(r, 1));
      actuales--;
    }, resultado: async () => {},
  });
  assert.equal(maximo, 5);
});

test('el webhook exige POST y secreto; ignora los datos del cliente', async () => {
  let reclamados = 0, procesados = 0, soltados = 0, despertados = 0;
  const trabajo = { id: 'desde-la-base', lease: 'l', edicion: base };
  const handler = crearHandler({ secreto: 'secreto-de-prueba',
    tomar: async () => { reclamados++; return trabajo; },
    procesar: async (real) => { assert.equal(real, trabajo); procesados++; return { enviados: 1 }; },
    soltar: async () => { soltados++; }, despertar: async () => { despertados++; },
  });
  assert.equal((await handler(new Request('https://local/'))).status, 405);
  assert.equal((await handler(new Request('https://local/', { method: 'POST' }))).status, 401);
  assert.equal(reclamados, 0);
  const respuesta = await handler(new Request('https://local/', { method: 'POST',
    headers: { 'x-webhook-secret': 'secreto-de-prueba' },
    body: JSON.stringify({ edicion: 'falsa', endpoint: 'https://localhost/' }),
  }));
  assert.equal(respuesta.status, 200);
  assert.equal(reclamados, 1);
  assert.equal(procesados, 1);
  assert.equal(soltados, 1);
  assert.equal(despertados, 1);
});

test('fallo deja el trabajo pendiente y nunca expone secretos', async () => {
  let soltado = false;
  const handler = crearHandler({ secreto: 's', tomar: async () => ({ id: '1' }),
    procesar: async () => { throw Error('CLAVE-PRIVADA-ENDPOINT'); },
    soltar: async () => { soltado = true; }, despertar: async () => {},
  });
  const r = await handler(new Request('https://local/', { method: 'POST',
    headers: { 'x-webhook-secret': 's' } }));
  assert.equal(r.status, 500);
  assert.equal(soltado, false);
  assert.ok(!(await r.text()).includes('CLAVE-PRIVADA'));
});
