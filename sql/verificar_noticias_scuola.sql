-- Sólo diagnóstico. No genera noticias ni envía avisos al curso.
select count(*) as noticias, count(titulo_es) as traducidas, count(texto) as textos_cacheados,
  bool_and(fecha >= '2026-01-01' and fecha < '2027-01-01') as solo_2026
from public.noticias_scuola;
select has_table_privilege('anon','public.noticias_scuola','SELECT') as lectura_publica,
  has_table_privilege('anon','public.noticias_scuola','INSERT') as permite_insertar,
  has_table_privilege('anon','public.noticias_scuola','UPDATE') as permite_editar,
  has_table_privilege('anon','public.noticias_scuola_control','SELECT') as expone_control,
  has_function_privilege('anon','public.noticias_scuola_reservar(uuid)','EXECUTE') as reserva_publica;
select jobname, schedule, active from cron.job where jobname='noticias-scuola-15min';
