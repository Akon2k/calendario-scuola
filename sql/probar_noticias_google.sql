-- Prueba transaccional: no llama a Google y no publica noticias.
begin;
do $$
declare a jsonb; b jsonb; n bigint;
  dia text := 'd:' || to_char(now() at time zone 'UTC','YYYY-MM-DD');
begin
  update public.noticias_traduccion_config set activo=false where id;
  a := public.noticias_traduccion_reservar(repeat('a',64),'Nuova notizia');
  if a->>'estado' <> 'desactivada' then raise exception 'No respeta desactivación'; end if;
  update public.noticias_traduccion_config set activo=true, limite_diario=30,limite_mensual=100 where id;
  -- Se usan periodos de la transacción; todo se revierte al terminar.
  update public.noticias_traduccion_uso set caracteres=0 where periodo in
    (dia,'m:'||to_char(now() at time zone 'UTC','YYYY-MM'));
  a := public.noticias_traduccion_reservar(repeat('a',64),'Nuova notizia');
  if a->>'estado' <> 'reservada' then raise exception 'No reserva'; end if;
  b := public.noticias_traduccion_reservar(repeat('a',64),'Nuova notizia');
  if b->>'estado' <> 'ocupada' then raise exception 'Permite consumo duplicado'; end if;
  perform public.noticias_traduccion_guardar(repeat('a',64),(a->>'lease')::uuid,'Nueva noticia');
  b := public.noticias_traduccion_reservar(repeat('a',64),'Nuova notizia');
  if b->>'estado' <> 'cache' then raise exception 'No reutiliza la traducción'; end if;
  select caracteres into n from public.noticias_traduccion_uso where periodo=dia;
  if n <> length('Nuova notizia') then raise exception 'Contabiliza más de una vez'; end if;
  a := public.noticias_traduccion_reservar(repeat('b',64),repeat('x',20));
  if a->>'estado' <> 'limite' then raise exception 'No impone límite diario'; end if;
  a := public.noticias_traduccion_reservar(repeat('c',64),'Novità');
  perform public.noticias_traduccion_guardar(repeat('c',64),(a->>'lease')::uuid,null);
  b := public.noticias_traduccion_reservar(repeat('c',64),'Novità');
  if b->>'estado' <> 'espera' then raise exception 'Reintenta sin espera de 24h'; end if;
  update public.noticias_traduccion_config set limite_mensual=length('Nuova notizia')+length('Novità') where id;
  a := public.noticias_traduccion_reservar(repeat('d',64),'x');
  if a->>'estado' <> 'limite' then raise exception 'No impone límite mensual'; end if;
  if has_table_privilege('anon','public.noticias_traduccion_config','SELECT') or
    has_function_privilege('anon','public.noticias_traduccion_reservar(text,text)','EXECUTE') then
    raise exception 'Control de consumo expuesto';
  end if;
end $$;
rollback;
select activo,limite_diario,limite_mensual,
  (select coalesce(sum(caracteres),0) from public.noticias_traduccion_uso) as caracteres_reservados
from public.noticias_traduccion_config where id;
