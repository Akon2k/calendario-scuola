# Avisos inmediatos por cambios de tarjetas

**Estado:** código preparado y probado localmente. No queda activo por hacer
commit o publicar en GitHub: requiere desplegar la función y activar Supabase.

## Qué cambia

- Guardar una edición, mover una fecha, crear una actividad, adjuntar un PDF
  o deshacer un cambio encola un aviso **después de confirmar el guardado**.
- Supabase dispara una Edge Function; no depende del PC ni de GitHub Pages.
- Llegan a los navegadores que ya activaron **🔔 Avisos**, usando las MISMAS
  claves VAPID. No necesitan suscribirse otra vez.
- Salen al guardar, también fuera del horario 08–22. Se elimina la espera de
  hasta una hora para estas acciones; el dispositivo/proveedor puede demorar
  la recepción (no existe entrega instantánea garantizada).
- El resumen del sábado y los cambios detectados al descargar EduFácil siguen
  con la tarea de Windows. Nuevos comunicados no forman parte de este cambio.
- Guardar PDF y texto juntos produce dos registros y puede producir dos avisos.
  Un evento nuevo con PDF también. Sólo se notifica lo que realmente se guardó.

## Diseño y seguridad

`ediciones` → trigger → cola persistente → webhook autenticado → Web Push.
No hay claves privadas ni service-role en la página. La función no acepta
filas ni endpoints suministrados por una llamada: los obtiene de la base.
La cola y los RPC están restringidos a `service_role`/administrador. La anon
key no puede invocar el worker. Los destinos de push tienen lista permitida
para impedir peticiones a localhost/redes internas usando una suscripción falsa.

Cada edición tiene una cola única, lease de dos minutos y entregas por
destinatario. Sólo reintenta los que fallan; HTTP 404/410 retira ese endpoint
de envíos futuros sin borrar la suscripción original. Cron recupera fallos
cada minuto, con espera exponencial hasta una hora. El envío es *al menos
una vez*: una caída entre enviar y registrar OK puede repetir un push; el
`tag` estable evita apilarlo en el mismo dispositivo. No se promete exactly-once.

La marca `push_inmediato` la calcula el servidor, no la web. `avisos.py`
omite esas filas, incluidas las pendientes de reintento, para no repetirlas
cada hora. Sin activar el servidor, el modo anterior sigue funcionando y
ahora también reconoce los PDF.

## Activación (administrador de Supabase)

No pegar tokens, claves privadas ni los archivos de `logs/` en el chat o GitHub.
No se necesita cambiar el HTML para activar los avisos del servidor.

1. Ejecutar `sql/avisos_inmediatos.sql` en el SQL Editor del proyecto.
   Instala tablas, triggers y cron, pero deja `activo = false`. Requiere las
   tablas `ediciones`, `suscripciones`, y Supabase Vault (ya incluido en Supabase).
2. En este PC: `python preparar_push.py`. Genera dos archivos **privados** en
   `logs/push-inmediato/`, ignorados por git. Reutiliza las claves VAPID de
   `config.json`; no las muestra. No sobrescribe secretos preexistentes.
3. Autenticar la CLI con tu cuenta administradora y desplegar desde la raíz:

   ```powershell
   npx supabase login
   npx supabase secrets set --project-ref icblrmookmpmzpnjeeeh --env-file logs/push-inmediato/servidor.env
   npx supabase functions deploy avisos-ediciones --project-ref icblrmookmpmzpnjeeeh
   ```

   `supabase/config.toml` desactiva la verificación JWT **sólo** para esta
   función: su autenticación obligatoria es `PUSH_WEBHOOK_SECRET`.
   `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` los inyecta Supabase; no copiar
   la service key a la web o a `config.json`.
4. Ejecutar el archivo **privado** `logs/push-inmediato/configurar_webhook.sql`
   en el SQL Editor. Guarda URL/secreto en Vault; todavía no activa nada.
5. Confirmar que la función desplegada está sana y que se está usando la
   versión nueva de `avisos.py`. Después activar:

   ```sql
   update public.push_ediciones_config set activo = true where id;
   ```

   No encola ni reenvía las ediciones históricas. Sólo las guardadas desde
   este punto quedan a cargo del servidor.
6. Prueba acordada con el grupo: editar una actividad o subir un PDF pequeño
   y confirmar recepción en un teléfono suscrito. **Esa prueba sí enviará un
   aviso real a los suscritos**. Verificar el registro sin mostrar endpoints:

   ```sql
   select c.id, c.creado, c.terminada,
          count(*) filter (where e.estado = 'enviado') as enviados,
          count(*) filter (where e.estado = 'pendiente') as pendientes,
          count(*) filter (where e.estado = 'caduca') as caducas
   from public.push_ediciones_cola c
   left join public.push_ediciones_entregas e on e.edicion = c.id
   group by c.id order by c.creado desc limit 10;
   ```

## Pausar sin perder avisos

```sql
update public.push_ediciones_config set activo = false where id;
```

Los cambios nuevos vuelven al aviso horario (necesita el PC encendido).
La cola ya existente termina sus pendientes; no se borra ninguna edición.
Para suspender también los reintentos, se puede desactivar el job de Cron
`push-ediciones-reintentos` y la función, sabiendo que quedan pendientes.

## Pruebas locales sin enviar a personas

```powershell
python -X utf8 test_avisos.py
node --test test_push_inmediato.mjs
python -X utf8 test_preparar_push.py
python -X utf8 test_pipeline.py
node test_pagina.mjs
```

Opcional: `test_push_sql.mjs` valida la migración en PostgreSQL embebido
(PGlite, sin Supabase real). Se simulan exclusivamente Vault/pg_net/cron;
tablas, PL/pgSQL, permisos, triggers, leases y reintentos sí se ejecutan.
Instalar `@electric-sql/pglite@0.3.14` en una carpeta temporal y pasar su ruta
absoluta en `PGLITE_MODULE` al ejecutar `node test_push_sql.mjs`.
