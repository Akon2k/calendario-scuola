-- La noticia de prueba y su revisión se revierten íntegramente. Sin push.
begin;
do $$
declare prueba uuid; antes bigint; despues bigint;
begin
  select version into antes from public.noticias_scuola_revision where id;
  insert into public.noticias_scuola(url,fecha,titulo) values(
    'https://scuola.scuolaitalianadiconcepcion.cl/2026/10/27/prueba-transaccion-lector/',
    date '2026-10-27','Prueba transaccional no publicada') returning id into prueba;
  select version into despues from public.noticias_scuola_revision where id;
  if despues <> antes + 1 then raise exception 'No detecta publicación nueva'; end if;
  update public.noticias_scuola set consultado=now(), texto=repeat('Texto válido de prueba. ',4) where id=prueba;
  select version into antes from public.noticias_scuola_revision where id;
  if antes <> despues then raise exception 'Repite novedades al consultar o cachear texto'; end if;
  update public.noticias_scuola set titulo_es='Traducción de prueba' where id=prueba;
  select version into despues from public.noticias_scuola_revision where id;
  if despues <> antes + 1 then raise exception 'No detecta traducción actualizada'; end if;
  if has_table_privilege('anon','public.noticias_scuola','UPDATE') or
     has_table_privilege('anon','public.noticias_scuola','INSERT') or
     has_table_privilege('anon','public.noticias_scuola_control','SELECT') or
     has_function_privilege('anon','public.noticias_scuola_reservar(uuid)','EXECUTE') then
    raise exception 'Permisos de escritura o control expuestos';
  end if;
end $$;
rollback;
select count(*) as noticias_reales, count(titulo_es) as traducidas, count(texto) as textos_cacheados,
  has_table_privilege('anon','public.noticias_scuola','SELECT') as lectura_publica,
  has_table_privilege('anon','public.noticias_scuola','UPDATE') as escritura_publica
from public.noticias_scuola;
