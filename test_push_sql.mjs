// PostgreSQL real embebido; no HTTP ni conexión con el proyecto Supabase.
// PGLITE_MODULE=ruta absoluta a .../pglite/dist/index.js node test_push_sql.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

if (!process.env.PGLITE_MODULE) throw Error('Configura PGLITE_MODULE (ver docs/avisos_inmediatos.md)');
const { PGlite } = await import(pathToFileURL(process.env.PGLITE_MODULE).href);
const db = new PGlite();
try {
  await db.exec(`
    create role anon; create role authenticated; create role service_role bypassrls;
    create schema extensions; create schema vault; create schema net; create schema cron;
    create table vault.decrypted_secrets (name text, decrypted_secret text);
    insert into vault.decrypted_secrets values
      ('push_ediciones_url','https://project.supabase.co/functions/v1/avisos-ediciones'),
      ('push_ediciones_secret','secreto-falso-para-pruebas');
    create table net.pruebas (url text);
    create function net.http_post(url text, body jsonb, headers jsonb, timeout_milliseconds int)
    returns bigint language plpgsql as $$ begin
      insert into net.pruebas values(url); return 1; end $$;
    create table cron.pruebas (nombre text primary key, horario text, comando text);
    create function cron.schedule(n text, h text, c text) returns bigint language plpgsql as $$
    begin insert into cron.pruebas values (n,h,c) on conflict (nombre)
      do update set horario=excluded.horario,comando=excluded.comando; return 1; end $$;
    create table public.ediciones (id uuid primary key default gen_random_uuid(),
      tipo text not null, clave text not null, campos jsonb not null default '{}',
      previo jsonb not null default '{}', autor text default '', token text default '',
      creado timestamptz default now());
    create table public.suscripciones (id uuid primary key default gen_random_uuid(),
      endpoint text unique not null, p256dh text, auth text, creado timestamptz default now());
    insert into public.suscripciones (endpoint,p256dh,auth) values
      ('https://fcm.googleapis.com/a','p','a'),('https://web.push.apple.com/b','p','a');
  `);
  const sql = readFileSync(new URL('./sql/avisos_inmediatos.sql', import.meta.url), 'utf8')
    .replace(/^create extension[^;]+;/gm, '');
  await db.exec(sql);
  await db.exec(sql); // Reejecutar no reactiva ni duplica cron.
  const q = async (sql, params = []) => (await db.query(sql, params)).rows;
  const count = async (tabla) => Number((await q('select count(*) as n from ' + tabla))[0].n);
  const insertar = async (tipo, campos = {}, previo = {}) => (await q(`
    insert into ediciones (tipo,clave,campos,previo,push_inmediato)
    values ($1,'MATEMÁTICA|1|EVALUACIÓN#1',$2,$3,true) returning *`,
  [tipo, JSON.stringify(campos), JSON.stringify(previo)]))[0];
  const rpc = async (fn, args = [], placeholders = '') =>
    (await q(`select ${fn}(${placeholders}) as valor`, args))[0].valor;

  const historica = await insertar('adjunto', { nombre: 'viejo.pdf' });
  assert.equal(historica.push_inmediato, false, 'cliente no puede forzar la marca');
  assert.equal(await count('push_ediciones_cola'), 0);
  await db.exec('update push_ediciones_config set activo=true');
  assert.equal(await count('push_ediciones_cola'), 0, 'no se notifica la historia');
  assert.equal((await insertar('correccion', { CONTENIDO: 'igual' },
    { CONTENIDO: 'igual' })).push_inmediato, false);
  await db.exec('begin');
  await insertar('adjunto', { nombre: 'no-guardado.pdf' });
  await db.exec('rollback');
  assert.equal(await count('push_ediciones_cola'), 0, 'rollback no deja aviso');
  assert.equal(await count('net.pruebas'), 0);

  const nueva = await insertar('correccion', { FECHA: '2026-11-05' }, { FECHA: '2026-11-02' });
  assert.equal(nueva.push_inmediato, true);
  assert.equal(await count('net.pruebas'), 1);
  let trabajo = await rpc('push_ediciones_tomar');
  assert.equal(trabajo.id, nueva.id);
  assert.equal(trabajo.entregas.length, 2);
  assert.ok(!('token' in trabajo.edicion));
  assert.equal(await rpc('push_ediciones_tomar'), null, 'segundo webhook no toma el lease');
  await assert.rejects(rpc('push_ediciones_resultado',
    [nueva.id, historica.id, trabajo.entregas[0].endpoint, 'enviado'], '$1,$2,$3,$4'), /Lease/);
  const recibo = (t, endpoint, estado) => rpc('push_ediciones_resultado',
    [t.id, t.lease, endpoint, estado], '$1,$2,$3,$4');
  const soltar = (t) => rpc('push_ediciones_soltar', [t.id, t.lease], '$1,$2');
  await recibo(trabajo, trabajo.entregas[0].endpoint, 'enviado');
  await recibo(trabajo, trabajo.entregas[1].endpoint, 'error');
  await soltar(trabajo);
  assert.equal(await rpc('push_ediciones_tomar'), null, 'respeta backoff');
  await db.exec(`update push_ediciones_cola set proximo=now();
    update push_ediciones_entregas set proximo=now() where estado='pendiente'`);
  trabajo = await rpc('push_ediciones_tomar');
  assert.equal(trabajo.entregas.length, 1, 'no reenvía al que ya recibió');
  const leaseViejo = trabajo.lease;
  await db.exec("update push_ediciones_cola set hasta=now()-interval '1 second'");
  trabajo = await rpc('push_ediciones_tomar');
  assert.notEqual(trabajo.lease, leaseViejo, 'recupera lease vencido');
  await recibo(trabajo, trabajo.entregas[0].endpoint, 'caduca');
  await soltar(trabajo);
  assert.equal(await rpc('push_ediciones_tomar'), null);
  assert.equal(await count('push_suscripciones_caducas'), 1);

  for (const tipo of ['nuevo', 'adjunto', 'anula']) {
    const fila = await insertar(tipo, { nombre: 'guia.pdf' });
    const t = await rpc('push_ediciones_tomar');
    assert.equal(t.id, fila.id);
    assert.equal(t.entregas.length, 1, 'excluye endpoint caducado de futuras ediciones');
    await recibo(t, t.entregas[0].endpoint, 'enviado');
    await soltar(t);
  }
  const forzada = (await q(`insert into ediciones (tipo,clave,campos,push_inmediato)
    values ('adjunto','MATEMÁTICA|1|EVALUACIÓN#1','{"nombre":"guia.pdf"}',false)
    returning push_inmediato`))[0];
  assert.equal(forzada.push_inmediato, true, 'cliente no puede desactivar el aviso');
  let t = await rpc('push_ediciones_tomar');
  await recibo(t, t.entregas[0].endpoint, 'caduca');
  await soltar(t);
  const sinSuscriptores = await insertar('adjunto', { nombre: 'sin-suscritos.pdf' });
  t = await rpc('push_ediciones_tomar');
  assert.equal(t.id, sinSuscriptores.id);
  assert.equal(t.entregas.length, 0);
  await soltar(t);
  assert.equal(await rpc('push_ediciones_tomar'), null, 'sin destinatarios no queda en bucle');
  await db.exec('update push_ediciones_config set activo=false');
  assert.equal((await insertar('adjunto')).push_inmediato, false);

  // Permisos de todos los RPC y tablas administrativas.
  for (const rol of ['anon', 'authenticated']) {
    const permisos = (await q(`select
      has_table_privilege($1,'public.push_ediciones_cola','SELECT') as tabla,
      has_function_privilege($1,'public.push_ediciones_tomar()','EXECUTE') as rpc,
      has_function_privilege($1,'public.push_ediciones_despertar()','EXECUTE') as secreto`, [rol]))[0];
    assert.deepEqual(permisos, { tabla: false, rpc: false, secreto: false });
  }
  assert.equal(await count('cron.pruebas'), 1);
  console.log('TODO OK: PostgreSQL, triggers, rollback, cutover, permisos, lease, backoff, PDF y sin reenvíos a entregados');
} finally { await db.close(); }
