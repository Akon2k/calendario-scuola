-- Sólo infraestructura de traducción. Desactivada hasta configurar Google.
-- No modifica las traducciones existentes ni las tablas de avisos.
begin;
alter table public.noticias_scuola add column if not exists titulo_es_proveedor text not null default 'manual'
  check(titulo_es_proveedor in ('manual','google'));
create table if not exists public.noticias_traduccion_config (
  id boolean primary key default true check(id),
  activo boolean not null default false,
  limite_diario integer not null default 3000 check(limite_diario between 1 and 10000),
  limite_mensual integer not null default 20000 check(limite_mensual between 1 and 100000)
);
insert into public.noticias_traduccion_config(id) values(true) on conflict do nothing;
create table if not exists public.noticias_traduccion_uso (
  periodo text primary key check(periodo ~ '^[dm]:[0-9]{4}-[0-9]{2}(-[0-9]{2})?$'),
  caracteres bigint not null default 0 check(caracteres >= 0)
);
create table if not exists public.noticias_traduccion_cache (
  hash text primary key check(hash ~ '^[0-9a-f]{64}$'),
  titulo text not null check(length(titulo) between 1 and 1000),
  traduccion text check(length(traduccion) between 1 and 1500),
  lease uuid,
  hasta timestamptz,
  proximo timestamptz not null default now(),
  intentos integer not null default 0,
  actualizado timestamptz not null default now()
);
alter table public.noticias_traduccion_config enable row level security;
alter table public.noticias_traduccion_uso enable row level security;
alter table public.noticias_traduccion_cache enable row level security;
revoke all on public.noticias_traduccion_config, public.noticias_traduccion_uso,
  public.noticias_traduccion_cache from public, anon, authenticated;
grant all on public.noticias_traduccion_config, public.noticias_traduccion_uso,
  public.noticias_traduccion_cache to service_role;

create or replace function public.noticias_traduccion_reservar(p_hash text, p_titulo text)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare cfg public.noticias_traduccion_config; trabajo public.noticias_traduccion_cache;
  dia text := 'd:' || to_char(now() at time zone 'UTC','YYYY-MM-DD');
  mes text := 'm:' || to_char(now() at time zone 'UTC','YYYY-MM');
  n integer := length(p_titulo); usado_dia bigint; usado_mes bigint; token uuid;
begin
  if p_hash is null or p_hash !~ '^[0-9a-f]{64}$' or n is null or n < 1 or n > 1000 or btrim(p_titulo) = '' then
    return jsonb_build_object('estado','invalida');
  end if;
  -- Un bloqueo común serializa el presupuesto y evita superar los límites
  -- con varias sincronizaciones simultáneas.
  select * into cfg from public.noticias_traduccion_config where id for update;
  select * into trabajo from public.noticias_traduccion_cache where hash=p_hash;
  if found then
    if trabajo.titulo <> p_titulo then return jsonb_build_object('estado','invalida'); end if;
    if trabajo.traduccion is not null then return jsonb_build_object('estado','cache','traduccion',trabajo.traduccion); end if;
    if trabajo.hasta > now() then return jsonb_build_object('estado','ocupada'); end if;
    if trabajo.proximo > now() then return jsonb_build_object('estado','espera'); end if;
  end if;
  if cfg.id is null or not cfg.activo then return jsonb_build_object('estado','desactivada'); end if;
  insert into public.noticias_traduccion_uso(periodo) values(dia),(mes) on conflict do nothing;
  select caracteres into usado_dia from public.noticias_traduccion_uso where periodo=dia;
  select caracteres into usado_mes from public.noticias_traduccion_uso where periodo=mes;
  if usado_dia + n > cfg.limite_diario or usado_mes + n > cfg.limite_mensual then
    return jsonb_build_object('estado','limite');
  end if;
  -- Se cuenta el intento incluso si se pierde la respuesta del proveedor.
  update public.noticias_traduccion_uso set caracteres=caracteres+n where periodo in (dia,mes);
  token := gen_random_uuid();
  insert into public.noticias_traduccion_cache(hash,titulo,lease,hasta,proximo,intentos)
    values(p_hash,p_titulo,token,now()+interval '90 seconds',now()+interval '24 hours',1)
  on conflict(hash) do update set lease=token,hasta=now()+interval '90 seconds',
    proximo=now()+interval '24 hours',intentos=public.noticias_traduccion_cache.intentos+1,actualizado=now();
  return jsonb_build_object('estado','reservada','lease',token);
end;
$$;

create or replace function public.noticias_traduccion_guardar(p_hash text, p_lease uuid, p_traduccion text)
returns boolean language plpgsql security definer set search_path = '' as $$
begin
  update public.noticias_traduccion_cache set traduccion=p_traduccion,lease=null,hasta=null,actualizado=now()
    where hash=p_hash and lease=p_lease and hasta>now();
  return found;
end;
$$;
revoke all on function public.noticias_traduccion_reservar(text,text),
  public.noticias_traduccion_guardar(text,uuid,text) from public, anon, authenticated;
grant execute on function public.noticias_traduccion_reservar(text,text),
  public.noticias_traduccion_guardar(text,uuid,text) to service_role;
create or replace function public.noticias_scuola_cambiar_revision()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if tg_op <> 'UPDATE' or
    row(new.url,new.fecha,new.titulo,new.titulo_es,new.detalle,new.miniatura,new.titulo_es_proveedor) is distinct from
    row(old.url,old.fecha,old.titulo,old.titulo_es,old.detalle,old.miniatura,old.titulo_es_proveedor) then
    update public.noticias_scuola_revision set version=version+1 where id;
  end if;
  return null;
end;
$$;
commit;
