-- Caché de noticias públicas de 2026. No toca ediciones, mensajes ni avisos.
begin;
create table if not exists public.noticias_scuola (
  id uuid primary key default gen_random_uuid(),
  url text not null unique check (url ~ '^https://scuola[.]scuolaitalianadiconcepcion[.]cl/2026/[0-9]{2}/[0-9]{2}/[a-z0-9-]+/$'),
  fecha date not null check (fecha >= date '2026-01-01' and fecha < date '2027-01-01'),
  titulo text not null check (length(titulo) between 1 and 1000),
  titulo_es text check (length(titulo_es) between 1 and 1500),
  detalle text not null default '' check (length(detalle) <= 10000),
  miniatura text not null default '' check (miniatura = '' or miniatura like 'https://scuola.scuolaitalianadiconcepcion.cl/wp-content/uploads/%'),
  texto text check (length(texto) between 40 and 100000),
  texto_actualizado timestamptz,
  fuente_modificada text,
  consultado timestamptz not null default now()
);
create index if not exists noticias_scuola_fecha_idx on public.noticias_scuola (fecha desc, url);
alter table public.noticias_scuola enable row level security;
revoke all on public.noticias_scuola from public, anon, authenticated;
grant select on public.noticias_scuola to anon, authenticated;
grant all on public.noticias_scuola to service_role;
drop policy if exists noticias_scuola_lectura on public.noticias_scuola;
create policy noticias_scuola_lectura on public.noticias_scuola for select to anon, authenticated using (true);

-- El navegador consulta sólo este número cada minuto. Descarga la lista
-- completa únicamente cuando cambia, no 105 noticias en cada revisión.
create table if not exists public.noticias_scuola_revision (
  id boolean primary key default true check(id),
  version bigint not null default 1
);
insert into public.noticias_scuola_revision(id) values(true) on conflict do nothing;
alter table public.noticias_scuola_revision enable row level security;
revoke all on public.noticias_scuola_revision from public, anon, authenticated;
grant select on public.noticias_scuola_revision to anon, authenticated;
grant all on public.noticias_scuola_revision to service_role;
drop policy if exists noticias_scuola_revision_lectura on public.noticias_scuola_revision;
create policy noticias_scuola_revision_lectura on public.noticias_scuola_revision for select to anon, authenticated using(true);
create or replace function public.noticias_scuola_cambiar_revision()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if tg_op <> 'UPDATE' or
    row(new.url,new.fecha,new.titulo,new.titulo_es,new.detalle,new.miniatura) is distinct from
    row(old.url,old.fecha,old.titulo,old.titulo_es,old.detalle,old.miniatura) then
    update public.noticias_scuola_revision set version = version + 1 where id;
  end if;
  return null;
end;
$$;
revoke all on function public.noticias_scuola_cambiar_revision() from public, anon, authenticated;
drop trigger if exists noticias_scuola_revision on public.noticias_scuola;
create trigger noticias_scuola_revision after insert or update or delete on public.noticias_scuola
for each row execute function public.noticias_scuola_cambiar_revision();

create table if not exists public.noticias_scuola_control (
  id uuid primary key references public.noticias_scuola(id) on delete cascade,
  lease uuid,
  hasta timestamptz,
  proximo timestamptz not null default now()
);
alter table public.noticias_scuola_control enable row level security;
revoke all on public.noticias_scuola_control from public, anon, authenticated;
grant all on public.noticias_scuola_control to service_role;

create or replace function public.noticias_scuola_invalidar()
returns trigger language plpgsql set search_path = '' as $$
begin
  if new.titulo is distinct from old.titulo then
    if new.titulo_es is not distinct from old.titulo_es then new.titulo_es := null; end if;
  end if;
  if new.titulo is distinct from old.titulo or
    (old.fuente_modificada is not null and new.fuente_modificada is distinct from old.fuente_modificada) then
    new.texto := null; new.texto_actualizado := null;
  end if;
  return new;
end;
$$;
drop trigger if exists noticias_scuola_invalidar on public.noticias_scuola;
create trigger noticias_scuola_invalidar before update on public.noticias_scuola
for each row execute function public.noticias_scuola_invalidar();

create or replace function public.noticias_scuola_reservar(p_id uuid)
returns uuid language plpgsql security definer set search_path = '' as $$
declare resultado uuid;
begin
  if not exists (select 1 from public.noticias_scuola where id = p_id and texto is null) then return null; end if;
  insert into public.noticias_scuola_control (id) values (p_id) on conflict do nothing;
  update public.noticias_scuola_control set lease = gen_random_uuid(), hasta = now() + interval '60 seconds'
  where id = p_id and proximo <= now() and (hasta is null or hasta < now())
  returning lease into resultado;
  return resultado;
end;
$$;
create or replace function public.noticias_scuola_guardar(p_id uuid, p_lease uuid, p_texto text)
returns boolean language plpgsql security definer set search_path = '' as $$
begin
  perform 1 from public.noticias_scuola_control where id = p_id and lease = p_lease and hasta > now() for update;
  if not found then return false; end if;
  if p_texto is not null then
    update public.noticias_scuola set texto = p_texto, texto_actualizado = now() where id = p_id;
  end if;
  update public.noticias_scuola_control set lease = null, hasta = null,
    proximo = case when p_texto is null then now() + interval '15 minutes' else now() end where id = p_id;
  return true;
end;
$$;
revoke all on function public.noticias_scuola_reservar(uuid), public.noticias_scuola_guardar(uuid, uuid, text)
  from public, anon, authenticated;
grant execute on function public.noticias_scuola_reservar(uuid), public.noticias_scuola_guardar(uuid, uuid, text)
  to service_role;
commit;
