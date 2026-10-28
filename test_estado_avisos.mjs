// Estados reales de permisos/suscripción con APIs simuladas, sin red.
// Ejecutar después de generar el HTML: node --test test_estado_avisos.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const html = readFileSync('salida/calendario_evaluaciones.html', 'utf8');
const inicio = html.indexOf('  var nav = (typeof navigator');
const fin = html.indexOf('  // ---- comunicados generales', inicio);
assert.ok(inicio > 0 && fin > inicio);
const js = html.slice(inicio, fin) + '\nthis.apiAvisos = {msgAvisos, pedirAvisos, restaurarAvisos};';

async function escenario({ permiso = 'default', respuesta = 'granted', compatible = true,
  errorRegistro = false, errorGuardado = false, configurado = true,
  ios = false, instalada = false, existente = true, pausarGuardado = false } = {}) {
  const elementos = Object.fromEntries(['instalar', 'avisos', 'avisos-estado', 'avisos-ayuda', 'probar'].map(id => [id, {
    textContent: '', title: '', className: '', hidden: false, disabled: false,
    attributes: {}, listeners: {},
    setAttribute(k, v) { this.attributes[k] = v; },
    addEventListener(k, f) { this.listeners[k] = f; },
  }]));
  const contadores = { permisos: 0, consultas: 0, altas: 0, suscripciones: 0 };
  let guardada = existente;
  let liberar;
  const pausa = pausarGuardado ? new Promise(r => { liberar = r; }) : Promise.resolve();
  const sub = { toJSON: () => ({ endpoint: 'https://fcm.googleapis.com/ficticio',
    keys: { p256dh: 'publica-ficticia', auth: 'auth-ficticio' } }) };
  const w = { matchMedia: () => ({ matches: instalada }), addEventListener() {} };
  if (compatible) w.Notification = {
    permission: permiso,
    requestPermission: async () => { contadores.permisos++; return respuesta; },
  };
  const contexto = {
    window: w, document: { getElementById: id => elementos[id] },
    navigator: { userAgent: ios ? 'iPhone' : 'Chrome', serviceWorker: {
      register: async () => {
        if (errorRegistro) throw Error('sin conexión');
        return { pushManager: { getSubscription: async () => existente ? sub : null,
          subscribe: async () => { contadores.suscripciones++; return sub; } } };
      },
    } },
    NUBE: configurado ? { url: 'https://prueba.supabase.co', vapid: 'A'.repeat(87) } : null,
    almacenar: () => null, encabezado: () => ({}),
    atob: b64 => Buffer.from(b64, 'base64').toString('binary'),
    fetch: async (_url, opts = {}) => {
      contadores.consultas++;
      await pausa;
      if (opts.method === 'POST') {
        contadores.altas++;
        if (!errorGuardado) guardada = true;
        return { ok: !errorGuardado, status: errorGuardado ? 503 : 201 };
      }
      return { json: async () => errorGuardado || !guardada ? [] : [{ endpoint: 'registrado' }] };
    },
    Uint8Array, Promise,
  };
  vm.runInNewContext(js, contexto);
  const tick = () => new Promise(r => setImmediate(r));
  await tick(); await tick();
  return { estado: elementos['avisos-estado'], boton: elementos.avisos,
    ayuda: elementos['avisos-ayuda'], contadores, api: contexto.apiAvisos, tick, liberar };
}

test('pendiente: texto visible y ayuda; nunca un check sin permiso', async () => {
  const e = await escenario();
  assert.equal(e.estado.textContent, 'Avisos pendientes');
  assert.match(e.estado.title, /Pulsa Avisos/);
  assert.match(e.estado.attributes['aria-label'], /pendientes/);
  assert.ok(!e.estado.className.includes('nube'));
  assert.equal(e.contadores.permisos, 0, 'no pedir permiso al abrir');
  assert.equal(e.contadores.consultas, 0);
  assert.equal(e.ayuda.hidden, true);
});

test('permiso y suscripción confirmados: Avisos check y explicación en tooltip', async () => {
  const e = await escenario({ permiso: 'granted' });
  assert.equal(e.estado.textContent, 'Avisos ✓');
  assert.match(e.estado.title, /PDF.*sábado/);
  assert.equal(e.boton.disabled, true);
  assert.equal(e.contadores.permisos, 0);
  e.api.msgAvisos('Elige Instalar aplicación en el navegador.');
  assert.equal(e.estado.textContent, 'Avisos ✓', 'instalar no altera el estado de la suscripción');
  assert.match(e.estado.title, /Instalar/);
  assert.equal(e.ayuda.hidden, false);
  assert.match(e.ayuda.textContent, /Instalar/);
});

test('mientras la nube no confirma, indica verificando y no muestra check', async () => {
  const e = await escenario({ permiso: 'granted', pausarGuardado: true });
  assert.equal(e.estado.textContent, 'Avisos: verificando…');
  assert.equal(e.boton.disabled, false);
  e.liberar();
  await e.tick(); await e.tick();
  assert.equal(e.estado.textContent, 'Avisos ✓');
});

test('bloqueados y no disponibles se distinguen sin mostrar un check', async () => {
  const bloqueado = await escenario({ permiso: 'denied' });
  assert.equal(bloqueado.estado.textContent, 'Avisos bloqueados');
  assert.match(bloqueado.estado.title, /configuración/);
  const no = await escenario({ compatible: false });
  assert.equal(no.estado.textContent, 'Avisos no disponibles');
  assert.equal(no.boton.hidden, true);
  assert.match(no.estado.title, /no admite/);
});

test('errores de registro o guardado nunca se presentan como activos', async () => {
  for (const opciones of [{ errorRegistro: true }, { errorGuardado: true }]) {
    const e = await escenario({ permiso: 'granted', ...opciones });
    assert.equal(e.estado.textContent, 'Avisos: revisar');
    assert.equal(e.boton.disabled, false);
    assert.ok(!e.estado.textContent.includes('✓'));
  }
});

test('iPhone sin instalar y configuración ausente no marcan activos', async () => {
  const ios = await escenario({ permiso: 'granted', ios: true });
  assert.equal(ios.estado.textContent, 'Avisos pendientes');
  assert.match(ios.estado.title, /pantalla de inicio/);
  assert.equal(ios.contadores.consultas, 0);
  const no = await escenario({ permiso: 'granted', configurado: false });
  assert.equal(no.estado.textContent, 'Avisos no configurados');
});

test('activar: sólo muestra check tras permiso y guardado; rechazar no lo activa', async () => {
  const si = await escenario({ existente: false });
  si.api.pedirAvisos();
  await si.tick(); await si.tick();
  assert.equal(si.estado.textContent, 'Avisos ✓');
  assert.equal(si.contadores.suscripciones, 1);
  assert.equal(si.contadores.altas, 1);
  const no = await escenario({ respuesta: 'denied' });
  no.api.pedirAvisos();
  await no.tick();
  assert.equal(no.estado.textContent, 'Avisos bloqueados');
  assert.equal(no.contadores.suscripciones, 0);
});
