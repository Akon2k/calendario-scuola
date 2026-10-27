-- Infraestructura de avisos inmediatos. Ejecutar en el SQL Editor de Supabase.
-- NO activa los envíos ni reenvía la historia. Ver docs/avisos_inmediatos.md.
begin;
create extension if not exists pg_net with schema extensions;
create extension if not exists pg_cron;

alter table public.ediciones add column if not exists push_inmediato boolean
  not null default false;

create table if not exists public.push_ediciones_config (
  id boolean primary key default true check (id),
  activo boolean not null default false
);
insert into public.push_ediciones_config (id) values (true) on conflict do nothing;

create table if not exists public.push_ediciones_cola (
  id uuid primary key references public.ediciones(id),
  creado timestamptz not null default clock_timestamp(),
  proximo timestamptz not null default now(),
  lease uuid,
  hasta timestamptz,
  preparada boolean not null default false,
  terminada boolean not null default false
);
create index if not exists push_ediciones_pendientes_idx
  on public.push_ediciones_cola (proximo) where not terminada;

create table if not exists public.push_ediciones_entregas (
  edicion uuid not null references public.push_ediciones_cola(id),
  endpoint text not null,
  estado text not null default 'pendiente'
    check (estado in ('pendiente', 'enviado', 'caduca', 'omitido')),
  intentos integer not null default 0,
  proximo timestamptz not null default now(),
  primary key (edicion, endpoint)
);
create table if not exists public.push_suscripciones_caducas (
  endpoint text primary key,
  creado timestamptz not null default now()
);

-- Ni la cola ni los endpoints ni el interruptor se exponen a los navegadores.
alter table public.push_ediciones_config enable row level security;
alter table public.push_ediciones_cola enable row level security;
alter table public.push_ediciones_entregas enable row level security;
alter table public.push_suscripciones_caducas enable row level security;
revoke all on public.push_ediciones_config, public.push_ediciones_cola,
  public.push_ediciones_entregas, public.push_suscripciones_caducas
  from public, anon, authenticated;
grant all on public.push_ediciones_config, public.push_ediciones_cola,
  public.push_ediciones_entregas, public.push_suscripciones_caducas to service_role;

-- Sólo avisa al worker de que hay trabajo: no envía datos del usuario ni
-- confía en payloads del navegador. pg_net sale DESPUÉS del COMMIT.
create or replace function public.push_ediciones_despertar()
returns void language plpgsql security definer set search_path = '' as $$
declare destino text; secreto text;
begin
  if not exists (select 1 from public.push_ediciones_cola
      where not terminada and proximo <= now()
        and (hasta is null or hasta < now())) then return; end if;
  select decrypted_secret into destino from vault.decrypted_secrets
    where name = 'push_ediciones_url' limit 1;
  select decrypted_secret into secreto from vault.decrypted_secrets
    where name = 'push_ediciones_secret' limit 1;
  if destino is null or secreto is null then return; end if;
  perform net.http_post(url := destino, body := '{}'::jsonb,
    headers := jsonb_build_object('Content-Type', 'application/json',
      'x-webhook-secret', secreto), timeout_milliseconds := 30000);
exception when others then
  -- Una caída del webhook no debe impedir guardar la tarjeta. La cola es
  -- persistente; cron reintentará aunque falle pg_net o reinicie Postgres.
  raise warning 'Aviso pendiente: no se pudo despertar el worker';
end;
$$;

create or replace function public.push_ediciones_marcar()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  -- No se permite que el cliente elija si un cambio ya está notificado.
  new.push_inmediato := coalesce((select activo
    from public.push_ediciones_config where id), false)
    and new.tipo in ('nuevo', 'correccion', 'adjunto', 'anula');
  if new.tipo = 'correccion' and not exists (
    select 1 from jsonb_each(new.campos) as c
    where c.key in ('FECHA', 'ASIGNATURA', 'ABREVIATURA', 'EVALUACION', 'CONTENIDO',
      'PROFESOR', 'NUMERO', 'COEFICIENTE', 'PONDERACION', 'TIPO')
      and c.value is distinct from new.previo -> c.key
  ) then new.push_inmediato := false; end if;
  return new;
end;
$$;

create or replace function public.push_ediciones_encolar()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if new.push_inmediato then
    insert into public.push_ediciones_cola (id) values (new.id) on conflict do nothing;
    perform public.push_ediciones_despertar();
  end if;
  return new;
end;
$$;
drop trigger if exists push_ediciones_marcar on public.ediciones;
create trigger push_ediciones_marcar before insert on public.ediciones
  for each row execute function public.push_ediciones_marcar();
drop trigger if exists push_ediciones_encolar on public.ediciones;
create trigger push_ediciones_encolar after insert on public.ediciones
  for each row execute function public.push_ediciones_encolar();

-- Lease por tarjeta + resultados por destinatario. Dos webhooks simultáneos
-- no reclaman el mismo trabajo; reintentar no vuelve a enviar a los que ya
-- respondieron OK. Una interrupción libera el trabajo al vencer el lease.
create or replace function public.push_ediciones_tomar()
returns jsonb language plpgsql security definer set search_path = '' as $$
declare trabajo public.push_ediciones_cola; recibos jsonb;
begin
  select * into trabajo from public.push_ediciones_cola
    where not terminada and proximo <= now() and (hasta is null or hasta < now())
    order by creado for update skip locked limit 1;
  if not found then return null; end if;
  update public.push_ediciones_cola set lease = gen_random_uuid(),
    hasta = now() + interval '2 minutes' where id = trabajo.id returning * into trabajo;
  if not trabajo.preparada then
    insert into public.push_ediciones_entregas (edicion, endpoint)
      select trabajo.id, s.endpoint from public.suscripciones s
      where s.creado <= trabajo.creado and not exists (
        select 1 from public.push_suscripciones_caducas c where c.endpoint = s.endpoint)
      on conflict do nothing;
    update public.push_ediciones_cola set preparada = true where id = trabajo.id;
  end if;
  -- Una suscripción retirada/caducada no bloquea una tarjeta indefinidamente.
  update public.push_ediciones_entregas e set estado = 'caduca'
    where e.edicion = trabajo.id and e.estado = 'pendiente' and (
      not exists (select 1 from public.suscripciones s where s.endpoint = e.endpoint)
      or exists (select 1 from public.push_suscripciones_caducas c where c.endpoint = e.endpoint));
  select coalesce(jsonb_agg(to_jsonb(s)), '[]'::jsonb) into recibos from (
    select s.endpoint, s.p256dh, s.auth from public.push_ediciones_entregas e
      join public.suscripciones s on s.endpoint = e.endpoint
      where e.edicion = trabajo.id and e.estado = 'pendiente' and e.proximo <= now()
      order by e.endpoint limit 25
  ) s;
  return jsonb_build_object('id', trabajo.id, 'lease', trabajo.lease,
    'edicion', (select to_jsonb(e) - 'token' from public.ediciones e where e.id = trabajo.id),
    'entregas', recibos);
end;
$$;

create or replace function public.push_ediciones_resultado(
  p_id uuid, p_lease uuid, p_endpoint text, p_estado text)
returns void language plpgsql security definer set search_path = '' as $$
begin
  perform 1 from public.push_ediciones_cola where id = p_id and lease = p_lease
    and hasta > now() for update;
  if not found then raise exception 'Lease inválido'; end if;
  if p_estado not in ('enviado', 'caduca', 'error', 'omitido') then
    raise exception 'Resultado inválido'; end if;
  update public.push_ediciones_entregas set
    estado = case when p_estado = 'error' then 'pendiente' else p_estado end,
    intentos = intentos + 1,
    proximo = now() + make_interval(secs => least(3600, 30 * power(2, least(intentos, 7)))::int)
    where edicion = p_id and endpoint = p_endpoint and estado = 'pendiente';
  if found and p_estado = 'caduca' then
    insert into public.push_suscripciones_caducas (endpoint) values (p_endpoint)
      on conflict do nothing;
  end if;
end;
$$;

create or replace function public.push_ediciones_soltar(p_id uuid, p_lease uuid)
returns void language plpgsql security definer set search_path = '' as $$
declare siguiente timestamptz;
begin
  perform 1 from public.push_ediciones_cola where id = p_id and lease = p_lease for update;
  if not found then raise exception 'Lease inválido'; end if;
  select min(proximo) into siguiente from public.push_ediciones_entregas
    where edicion = p_id and estado = 'pendiente';
  update public.push_ediciones_cola set terminada = siguiente is null,
    proximo = coalesce(siguiente, now()), lease = null, hasta = null where id = p_id;
end;
$$;

-- Los SECURITY DEFINER nunca se ejecutan con anon ni con authenticated.
revoke all on function public.push_ediciones_despertar(), public.push_ediciones_marcar(),
  public.push_ediciones_encolar(), public.push_ediciones_tomar(),
  public.push_ediciones_resultado(uuid, uuid, text, text),
  public.push_ediciones_soltar(uuid, uuid) from public, anon, authenticated;
grant execute on function public.push_ediciones_despertar(), public.push_ediciones_tomar(),
  public.push_ediciones_resultado(uuid, uuid, text, text),
  public.push_ediciones_soltar(uuid, uuid) to service_role;

-- No pide HTTP cada minuto si no hay trabajo; también recupera leases vencidos.
select cron.schedule('push-ediciones-reintentos', '* * * * *',
  'select public.push_ediciones_despertar()');
commit;
