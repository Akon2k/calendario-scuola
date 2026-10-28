-- Snapshot de fuentes públicas del listón. Ningún navegador puede escribir.
begin;
create table if not exists public.liston_publico (
  id boolean primary key default true check(id),
  datos jsonb not null check(jsonb_typeof(datos)='object'
    and datos ? 'consultado' and jsonb_typeof(datos->'lecturas')='array'
    and jsonb_array_length(datos->'lecturas')=3),
  actualizado timestamptz not null default now()
);
alter table public.liston_publico enable row level security;
revoke all on public.liston_publico from public,anon,authenticated;
grant select on public.liston_publico to anon,authenticated;
grant all on public.liston_publico to service_role;
drop policy if exists liston_publico_lectura on public.liston_publico;
create policy liston_publico_lectura on public.liston_publico for select to anon,authenticated using(true);
commit;
