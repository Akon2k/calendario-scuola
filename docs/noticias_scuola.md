# Noticias Scuola: caché compartida y vista local

La web pública **no se ha actualizado**. La integración se valida en
`salida/vista_previa_liston.html`, fuera de `publicar.py`.

## Qué está preparado

- Tabla `noticias_scuola`: noticias oficiales **sólo de 2026**, títulos,
  traducciones, extractos, URL de miniatura y texto opcional. Los navegadores
  sólo tienen SELECT; no pueden crear, modificar ni borrar noticias.
- Función `noticias-scuola`: GET por UUID conocido obtiene texto, conserva
  párrafos y lo guarda en Supabase. No admite URLs aportadas por el cliente,
  no sigue redirecciones ni descarga fotos o videos. Un lease impide descargas
  simultáneas del mismo artículo; fallos esperan 15 minutos antes de reintentar.
- POST privado revisa la categoría oficial 2026 cada 15 minutos mediante cron.
  No borra noticias por fallos de la fuente y no envía notificaciones push.
  Las correcciones de la fuente invalidan el texto cacheado para volver a leerlo.
- El navegador revisa **un número de versión cada minuto** y al volver a la
  pestaña. Sólo descarga la lista si hay cambios; no descarga las 105 fichas
  en cada revisión. El texto completo se solicita sólo al abrir un artículo.
- Contador de no leídas, independiente de Mensajes. Usa la URL estable de cada
  noticia y `localStorage` por dispositivo. Al entrar en Noticias se marcan
  todas como leídas, igual que en Mensajes; una misma novedad no se acumula.
- Lector dentro de la app: título original, traducción entre paréntesis, fecha,
  párrafos de texto y enlace a la fuente. El HTML remoto nunca se inserta en el
  documento: se usan nodos de texto. Volver/Escape cierra y devuelve el foco.

## Traducciones y costos

`supabase/functions/noticias-scuola/traducciones.json` contiene las 105
traducciones iniciales preparadas en esta implementación. Se guardan en la
tabla y **no hacen llamadas a servicios externos**.

Para un título nuevo, el sincronizador conserva una traducción ya guardada o
busca una coincidencia exacta en ese diccionario. Opcionalmente admite
Google Cloud Translation v2 (NMT) mediante el secreto del servidor
`GOOGLE_TRANSLATE_API_KEY` (máximo cinco intentos por sincronización).
Google otorga un crédito mensual gratuito de US$10 (cubre hasta 500.000
caracteres mensuales sin cobro). Para total seguridad, la base de datos
controla el consumo mediante `sql/noticias_google.sql` con límites estrictos de
**3.000 caracteres diarios y 20.000 mensuales**, manteniéndose desactivada por
defecto (`activo = false`).

**No se ha activado facturación ni credenciales en Google Cloud sin tu
intervención.** Sin la clave configurada, una noticia nueva aparece y
cuenta normalmente, en italiano hasta preparar su traducción. No se inventa
una traducción ni se bloquea la noticia. La traducción no afecta al cuerpo
original: gran parte del contenido ya está en español.

Las miniaturas siguen siendo archivos pequeños del sitio de la Scuola, no
copias de imágenes en Storage. El lector no contiene imágenes. Supabase
almacena textos y metadatos; el consumo depende de las cuotas del proyecto.

## Instalación / administración

1. Aplicar `sql/noticias_scuola.sql` y `sql/noticias_google.sql` al proyecto
   autorizado.
2. Ejecutar `python preparar_noticias_nube.py` para preparar la importación
   del snapshot real, el secreto independiente y el cron. Los archivos
   privados quedan en `logs/noticias-scuola/`, ignorados por git.
3. Aplicar `logs/noticias-scuola/importar.sql` para la carga inicial.
4. Subir **sólo** el secreto de ese directorio con `supabase secrets set
   --env-file .../servidor.env` (y opcionalmente `GOOGLE_TRANSLATE_API_KEY=...`),
   desplegar `noticias-scuola --use-api` y aplicar
   `logs/noticias-scuola/configurar.sql` para Vault y el cron de 15 minutos.
5. Generar `python vista_previa_liston.py`. Lee la tabla con la clave pública
   del HTML del calendario. Si la nube falla, conserva la alternativa de la
   fuente; nunca incrusta una clave privada ni reactiva la edición de tarjetas.

La función usa la clave de servicio **sólo dentro de Supabase**. El HTML sólo
incluye una publishable key, protegida por RLS. El secreto administrativo no
es el de los avisos y no debe copiarse a la web, las pruebas ni GitHub.

Para pausar la revisión automática sin tocar los avisos:

```sql
select cron.alter_job(job_id := jobid, active := false)
from cron.job where jobname = 'noticias-scuola-15min';
```

## Pruebas

`python test_noticias_scuola.py`, `python test_vista_previa_liston.py` y
`node --test test_noticias_backend.mjs`. `sql/probar_noticias_sin_publicar.sql`
valida la revisión y permisos en una transacción con ROLLBACK: no publica
una noticia ficticia ni envía avisos. El diagnóstico de cron y permisos es
`sql/verificar_noticias_scuola.sql`.
