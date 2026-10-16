-- Ejecutar la copia generada en salida/comunicados.sql, no esta plantilla.
-- La clave privada queda sólo en logs/ y Propiedades del script.
begin;

do $$
begin
  if '{{SHA256_CLAVE}}' !~ '^[0-9a-f]{64}$' then
    raise exception 'Genera primero el SQL: python botscuola/preparar_sql.py';
  end if;
end $$;

create table if not exists public.comunicados (
  id text primary key,
  asunto text not null check (length(asunto) between 1 and 1000),
  remitente text not null default '',
  fecha timestamptz not null,
  puntos jsonb not null default '[]'::jsonb check (jsonb_typeof(puntos) = 'array'),
  accion text not null default '',
  eventos jsonb not null default '[]'::jsonb check (jsonb_typeof(eventos) = 'array'),
  creado timestamptz not null default now()
);

alter table public.comunicados enable row level security;
revoke all on public.comunicados from public, anon, authenticated;
grant select, insert on public.comunicados to anon, authenticated;

drop policy if exists "botscuola: lectura" on public.comunicados;
create policy "botscuola: lectura" on public.comunicados
  for select to anon, authenticated using (true);

drop policy if exists "botscuola: insercion privada" on public.comunicados;
create policy "botscuola: insercion privada" on public.comunicados
  for insert to anon, authenticated with check (
    encode(sha256(convert_to(coalesce(
      current_setting('request.headers', true)::jsonb ->> 'x-botscuola-clave', ''
    ), 'UTF8')), 'hex') = '{{SHA256_CLAVE}}'
  );

create index if not exists comunicados_fecha_idx on public.comunicados (fecha desc);
notify pgrst, 'reload schema';
commit;
