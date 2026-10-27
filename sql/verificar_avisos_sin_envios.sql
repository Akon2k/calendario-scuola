-- Verifica los triggers reales SIN dejar ediciones ni enviar notificaciones.
-- pg_net sólo sale después del COMMIT: aquí TODO termina en ROLLBACK.
begin;
set local statement_timeout = '15s';
update public.push_ediciones_config set activo = true where id;
do $$
declare prueba uuid; marcada boolean;
begin
  insert into public.ediciones (tipo, clave, campos, previo, autor)
    values ('correccion', 'PRUEBA_TRANSACCIONAL|0|EVALUACIÓN#1',
      jsonb_build_object('CONTENIDO', 'Prueba que se deshace'),
      '{}'::jsonb, 'Verificación técnica')
    returning id, push_inmediato into prueba, marcada;
  if not marcada or not exists (
      select 1 from public.push_ediciones_cola where id = prueba) then
    raise exception 'El disparador no encola correctamente';
  end if;
end;
$$;
rollback;
select not exists (select 1 from public.ediciones
    where clave = 'PRUEBA_TRANSACCIONAL|0|EVALUACIÓN#1') as prueba_revertida,
  (select activo from public.push_ediciones_config where id) as activo;
