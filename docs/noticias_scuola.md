# Noticias Scuola: caché compartida y vista local

La integración de producción conserva la edición, los PDF, Mensajes, la PWA
y los avisos. `salida/vista_previa_liston.html` continúa como copia local de
sólo lectura y queda fuera de `publicar.py`; nunca se publica ese archivo.

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
El crédito mensual de Google para traducción estándar NMT debe verificarse en
la cuenta elegida. No garantiza una factura total de cero: otros servicios o
usos pueden consumir créditos o generar cargos. La base de datos limita el
consumo de esta integración mediante `sql/noticias_google.sql` a
**3.000 caracteres diarios y 20.000 mensuales**, manteniéndose desactivada por
defecto (`activo = false`).

**No se ha activado facturación ni credenciales en Google Cloud sin tu
intervención.** Sin la clave configurada, una noticia nueva aparece y
cuenta normalmente, en italiano hasta preparar su traducción. No se inventa
una traducción ni se bloquea la noticia. La traducción no afecta al cuerpo
original: gran parte del contenido ya está en español.

La cuota se reserva ANTES de consultar al proveedor, también si se pierde la
respuesta. Se reutilizan traducciones guardadas y los fallos esperan 24 horas.
Las tablas de control y sus RPC son privadas. No hay llamadas a Google desde
el lector ni credenciales en el navegador.

### Lo que falta para activar Google

1. Crear o elegir personalmente un proyecto en Google Cloud, habilitar
   facturación y **Cloud Translation API**. La aplicación no activa cobros.
2. Configurar una cuota baja de caracteres diarios en ese proyecto (por ejemplo,
   5.000). El límite interno permanece en 3.000/día y 20.000/mes. Los avisos de
   presupuesto de Google por sí solos no cortan el consumo; usar cuotas.
3. Crear una API key de Basic v2 y restringirla a **Cloud Translation API**.
4. Ejecutar `python preparar_google_noticias.py`; guardar la clave únicamente
   en `logs/noticias-scuola/google.env`, ignorado por git. No pegarla en el chat.
5. `python preparar_google_noticias.py --comprobar` verifica la credencial
   listando idiomas, sin traducir. Después se sube ese archivo privado con
   `supabase secrets set --env-file logs/noticias-scuola/google.env` al proyecto
   autorizado y, sólo tras confirmar cuotas, se pone `activo=true` en
   `public.noticias_traduccion_config`.

Mientras no se completen estos pasos, la integración está preparada pero no
activada. La clave va en la cabecera `x-goog-api-key`, nunca en una URL.
Las traducciones de Google se identifican como automáticas, con la atribución
oficial, el idioma de traducción y un aviso legal. Las iniciales conservan
origen manual: no se atribuyen a Google. La ayuda del usuario no menciona Supabase.

Las miniaturas siguen siendo archivos pequeños del sitio de la Scuola, no
copias de imágenes en Storage. El texto del artículo no contiene imágenes;
el lector sólo añade la insignia oficial si el título fue traducido por Google. Supabase
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
`node --test test_noticias_backend.mjs test_noticias_google.mjs`.
`sql/probar_noticias_google.sql` verifica presupuestos y permisos con ROLLBACK,
sin llamadas a Google. `sql/probar_noticias_sin_publicar.sql`
valida la revisión y permisos en una transacción con ROLLBACK: no publica
una noticia ficticia ni envía avisos. El diagnóstico de cron y permisos es
`sql/verificar_noticias_scuola.sql`.

## Listón publicado

`edufacil/noticias_liston.py` aplica el diseño aprobado a la página de producción:
tiempo, Ruta 160 y todas las noticias; botones de impresora y descarga ICS
con etiqueta accesible y leyenda. Reemplaza la integración anterior sin duplicarla.
El listón ocupa una fila completa de la cabecera, justo encima de la barra
del mes y sus botones (Hoy, tema, impresión y descarga), tanto en móvil como en PC.
Las noticias del listón priorizan Coronel; si no hay ningún titular reciente
de Coronel en la fuente regional, se utiliza la portada nacional de BioBioChile.
Sólo se muestran titulares fechados y enlazados a publicaciones originales.
Se seleccionan hasta 10 noticias, sin duplicados y sin inventar publicaciones
para completar el cupo. Con 10 titulares, el contador tiene 12 elementos:
tiempo, Ruta 160 y las 10 noticias (96 segundos por vuelta a 8 segundos cada uno).

`sql/liston_publico.sql` crea un único snapshot legible pero no modificable por
los navegadores. `python actualizar_liston_local.py --publicar` consulta las
fuentes cada 15 minutos desde este PC y replica sólo esos datos públicos mediante
la CLI autenticada. La web consulta el snapshot cada minuto, al abrirse y al volver
a la pestaña. Los cambios se aplican sin interrumpir detalles abiertos.
Requiere mantener este PC y el actualizador encendidos; una interrupción conserva
la última fecha y activa las advertencias de caducidad, no simula una actualización.
Noticias Scuola tiene su propio cron en servidor y no depende de este proceso.

`python test_publicacion_liston.py` comprueba la separación entre producción y
vista previa. Google permanece desactivado hasta la configuración explícita.

La regeneración reemplaza los bloques locales anteriores en vez de duplicar
pestañas, lectores, snapshots o controles del listón. Las pruebas cubren también
una segunda generación sobre una copia ya integrada, sin modificar la página base.

Las tres pestañas usan un único controlador del calendario. La llegada tardía o
el refresco de Mensajes no cambia la vista elegida ni deja dos paneles visibles;
Noticias escucha el cambio para sincronizar únicamente sus imágenes y contador.
`node test_pagina.mjs` cubre selección, refrescos y la respuesta sin mensajes.
