-- Material de las actividades (PDF pequeños).
-- Pegar UNA vez en la consola SQL del proyecto Supabase.
--
-- Qué hace:
--   1) La tabla public.ediciones acepta un tipo más, «adjunto»: cada PDF
--      queda registrado como una fila de la misma bitácora (append-only).
--   2) Crea el bucket público «adjuntos», con tope de 8 MB y sólo PDF.
--   3) Permite leer a cualquiera y subir desde la página (es pública).

begin;

-- 1) tipo «adjunto» en la bitácora
alter table public.ediciones drop constraint if exists ediciones_tipo_check;
alter table public.ediciones add constraint ediciones_tipo_check
  check (tipo in ('correccion', 'nuevo', 'anula', 'adjunto'));

-- 2) bucket público con límites del lado del servidor
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('adjuntos', 'adjuntos', true, 8388608, array['application/pdf'])
on conflict (id) do update
  set public = true,
      file_size_limit = 8388608,
      allowed_mime_types = array['application/pdf'];

-- 3) políticas del bucket
drop policy if exists "adjuntos: lectura" on storage.objects;
create policy "adjuntos: lectura" on storage.objects
  for select using (bucket_id = 'adjuntos');

drop policy if exists "adjuntos: subida" on storage.objects;
create policy "adjuntos: subida" on storage.objects
  for insert with check (
    bucket_id = 'adjuntos'
    and lower(right(name, 4)) = '.pdf'
  );

commit;
