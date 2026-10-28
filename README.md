# Calendario de Evaluaciones — EduFácil

Este proyecto toma las evaluaciones de EduFácil (el sitio del colegio) y las
deja listas en varios lugares a la vez:

1. una **página web de calendario** que se abre en el navegador y también se
   puede instalar en el celular como una app;
2. un **Excel, un CSV y un JSON** con todos los datos;
3. las **citas en Outlook**, en su propia carpeta, con el resumen de cada
   sábado;
4. **avisos por notificación**: el sábado con la semana que viene, y el mismo
   día en que algo cambia.
5. una pestaña **Mensajes** con los comunicados generales del colegio,
   alimentada por BotScuola (Gmail, Google Apps Script y Groq).

Sólo lee tu propio calendario con tus credenciales de EduFácil. Resultado
real del año 2026: 102 evaluaciones de marzo a diciembre, en 10 asignaturas,
con profesor, número (y sub-número cuando corresponde) y coeficiente.

La página publicada está en:

<https://akon2k.github.io/calendario-scuola/>

## Lo que necesitas

- Python 3 y las librerías de `requirements.txt` (`pip install -r requirements.txt`).
- Tu RUT y contraseña de EduFácil, para escribirlos en `config.json`.
- Para Outlook: Outlook de escritorio (versión 16.0) y `pip install pywin32`.
- Para publicar la página: GitHub CLI autenticado una sola vez
  (`gh auth login`).
- Opcional: una base de Supabase para las correcciones de la comunidad, y
  Docker para servir la página en la red local.

## Cómo se corre

```bash
python main.py                      # exporta a xlsx + csv + json + la página
python main.py --probar-login       # sólo prueba si las credenciales sirven
python main.py -v                   # cuenta paso a paso lo que hace
python main.py --sin-nube           # ignora Supabase: sólo lo de EduFácil
python main.py --formatos csv,json  # genera sólo esos formatos
python main.py --sin-detalle        # sin profesor/ponderación (más rápido)
python main.py --sin-resumen        # sin el resumen del sábado
python main.py --guardar-html       # guarda el JSON crudo en debug/ (para investigar)
python publicar.py                  # sube la página a GitHub Pages
python avisos.py                    # envía los avisos pendientes
python avisos.py --probar           # arma los avisos y los imprime, sin enviar
python avisos.py --probar-sabado    # envía el resumen real del próximo sábado (prueba)
python generar_vapid.py             # (re)genera las llaves de los avisos
```

Opciones de Outlook:

```bash
python main.py --outlook                        # todo el año
python main.py --outlook --outlook-desde 2026-10-01   # desde una fecha en adelante
python main.py --outlook --outlook-limite 5     # prueba con las 5 primeras
python main.py --outlook --outlook-carpeta "Otro nombre"   # carpeta destino
python main.py --outlook --sin-recordatorio     # sin aviso de un día antes
python main.py --outlook --outlook-purgar       # borra de Outlook las que ya no existen
```

Doble clic en **`ejecutar.bat`** hace lo mismo sin abrir terminal, y además
publica y envía avisos. **`probar_login.bat`** sólo prueba las credenciales.
**`instalar_tarea.bat`** crea las tareas programadas (más abajo).

## Configuración

Todo se controla desde `config.json`. Ese archivo **nunca se sube a git**: ya
está en el `.gitignore`, que además excluye `salida/`, `logs/`, `debug/` y
las pruebas. Para empezar, copia el de ejemplo y rellénalo:

```bash
copy config.example.json config.json
```

```json
{
  "rut": "12345678-9",
  "password": "TuContraseña",
  "supabase": {
    "url": "https://TU-PROYECTO.supabase.co",
    "anon_key": "sb_publishable_...",
    "tabla": "ediciones"
  },
  "github": { "repo": "calendario-scuola" },
  "avisos": {
    "vapid_publica": "la genera: python generar_vapid.py",
    "vapid_privada": "32 bytes en base64url (sólo en tu config.json real)",
    "sujetos": "https://edufacil.cl"
  }
}
```

- El bloque `supabase` es **opcional**: sin él (o con `--sin-nube`) todo
  funciona igual, sólo que la página queda en modo lectura. La clave que va
  ahí es la *publishable* (pública): viaja dentro de la página y sólo sirve
  para leer y agregar filas.
- El bloque `github` dice en qué repositorio se publica la página.
- El bloque `avisos` guarda las llaves de los avisos: se generan con
  `python generar_vapid.py` y sólo la pública viaja dentro de la página.

Si el login falla con «La contraseña que has ingresado no es válida», revisa
que la contraseña esté bien copiada, completa y con todos sus signos. Ese
mensaje es genérico: también aparece cuando el RUT está mal escrito. El RUT
se prueba solo en varios formatos (sin puntos, con guion y con puntos), así
que con escribirlo de una forma alcanza.

## La página

Al abrirla muestra el mes con las evaluaciones y un panel con el detalle del
día seleccionado. Cada evaluación se muestra con **un dato por línea**
(fecha, asignatura, prueba, profesor, número —y sub-número si es una
sub-evaluación— y coeficiente, sólo los que traiga el registro), igual en el
resumen del sábado, en Outlook, en el `.ics` y en los avisos.

Son los mismos campos que enseñan los diálogos del propio sitio
(«Detalle de evaluación» y «Detalle de sub-evaluación»): la evaluación trae
**Número** y la sub-evaluación trae **Número** y **Sub-número**; el nombre
va sin el `E3:` / `SE2-2:` que trae la lista, y **sin ponderación**, que la
fuente no la muestra en el detalle.

Lo que puede hacer quien la abre:

- **Editar** una evaluación: corrige fecha, profesor o contenido, y lo ven
  todos los que abran la página.
- **Editar resumen** en el sábado: cambia el título o el cuerpo del resumen.
- **Nuevo evento** (arriba): agrega una evaluación que EduFácil no tenga.
  **Asignatura** y **Abreviatura (EFYS)** son combos con las asignaturas del
  colegio y su código (`IDIOMA EXTRANJERO (INGLÉS)` → `IEXIN`): al elegir una
  se completa el código, y al revés. El catálogo sale del propio EduFácil en
  cada corrida, así que una asignatura nueva aparece sola; «Otra…» permite
  escribir una que todavía no esté.
- **Deshacer**: anula una corrección sin borrar nada; queda quién la anuló.
- **Unir con otra tarjeta** (eventos agregados manualmente): permite elegir
  la tarjeta oficial, aunque tenga otro nombre, y qué fecha, título, contenido
  y profesor conservar. Mantiene los PDF de ambas (sin volver a subirlos ni
  duplicar el mismo archivo) y retira sólo el evento manual. Requiere elegir
  un destino y confirmar expresamente. Datos, referencias PDF y anulación se
  guardan juntos en una transacción; no se borra el historial ni el archivo.
  Antes de guardar vuelve a leer Supabase y aborta si cambiaron las tarjetas
  o no hay conexión. No hace una descarga nueva de EduFácil desde el navegador:
  los destinos son los de la última actualización del calendario.
- **Descargar .ics**: baja el calendario para Google Calendar o Outlook web.
- **Instalar app**: la convierte en una app del celular o de la PC.
- **Avisos**: da de alta el navegador para recibir notificaciones.
  El indicador muestra **Avisos ✓** sólo después de confirmar la suscripción;
  en los demás casos dice pendientes, bloqueados, no disponibles o revisar.
  Al pasar el mouse se ve la explicación completa. El punto verde que cuenta
  las correcciones pertenece al estado de Supabase y se mantiene separado.
- **Mensajes**: muestra los comunicados generales desde el 1 de septiembre de
  2026 hasta el presente, del más reciente al más antiguo. La pestaña tiene
  desplazamiento interno y mantiene las dimensiones del calendario.

El alcance es corregir lo existente y agregar: no hay botón de borrar ni
ocultar evaluaciones. El nombre que escribe al corregir queda guardado como
autor, y arriba se ve un indicador de estado («n correcciones»,
«conectando…», «sin conexión»).

La página también incluye una sección de **instrucciones de uso** con los
pasos para instalarla en Android (Chrome) e iPhone (Safari, iOS 16.4 o
superior), que son los que hacen que los avisos lleguen siempre.

Un detalle práctico: si usás Brave en la computadora, los avisos no llegan
—es un bug conocido de Brave—, usá Chrome o Edge. En el celular con Chrome
funcionan sin problemas.

## El resumen de los sábados y los avisos

Vista **sólo local** de una franja de Ruta 160, meteorología y
noticias: `python vista_previa_alertas.py` crea `salida/vista_previa_alertas.html`.
Consulta títulos de BioBioChile (prioriza Coronel), tiempo de Open-Meteo para
Coronel y la lista pública de Transporte Informa Biobío. Muestra fuente,
fecha y hora de consulta, no titulares de ejemplo. La ausencia de reportes
viales recientes no se presenta como ruta despejada. Si una fuente falla o
caduca, lo indica sin inventar datos. Las alertas oficiales DMC/SENAPRED no
están integradas: el pronóstico no se etiqueta como una alerta.
Los datos se consultan al generar la vista (no es monitoreo continuo).
`salida/informacion_local.json` conserva esa lectura. Ambos archivos quedan
fuera del publicador; Supabase se desconecta sólo en la copia de lectura.
No modifica el calendario publicado ni envía avisos. El ancho de la franja
se alinea con los 1180 px del calendario y se adapta a pantallas pequeñas.
Alternativa compacta: `python vista_previa_liston.py` crea
`salida/vista_previa_liston.html` con las mismas lecturas y conserva la franja
anterior. Alterna titulares, tiempo y Ruta 160 cada 8 segundos. Pulsar un
titular abre su noticia original de BioBioChile en otra pestaña, sin desplegable
de noticias. El clima conserva su detalle y Ruta 160 lo muestra sólo cuando
hay un reporte reciente; sin información no tiene desplegable. Tiene anterior,
siguiente y pausa. Se detiene al pasar el mouse, usar el teclado, abrir detalles
o dejar la pestaña oculta. Con movimiento reducido inicia pausado. También es
sólo local y está fuera del publicador.
Para refrescar sus fuentes automáticamente, mantener ejecutándose
`python actualizar_liston_local.py`: consulta noticias, tiempo y Ruta 160 cada
15 minutos y reemplaza sólo `salida/informacion_local.json` de forma atómica.
`--una-vez` hace una única consulta. No instala tareas de Windows ni modifica
los horarios del calendario. El listón lee ese JSON al abrirse, cada minuto
y al volver a la pestaña; incorpora novedades en el siguiente cambio sin
recargar el calendario ni interrumpir detalles abiertos, pausa o lectura.
Requiere el servidor local y el actualizador en ejecución. Al detenerlos no
se inventan nuevas consultas: se conservan las fechas y caducidades reales.
Servidor recomendado para pruebas: `python servidor_vista_local.py` sirve
`salida/` en `127.0.0.1:8765` con cabeceras `no-store`, sin respuestas 304.
Las vistas previas desactivan el registro automático del worker y limpian sólo
la caché `calendario-v*` del origen local; no borran datos, permisos ni estados
guardados, ni afectan al sitio publicado.
La alternativa del listón añade las pestañas «Calendario · Mensajes · Noticias
Scuola». Esta última prefiere la caché de Supabase y conserva la portada
oficial `/noticia/` como alternativa al generar la vista. Filtra sólo 2026, sin fechas
futuras. Muestra miniaturas reales de WordPress (normalmente 150×150), títulos
completos, el extracto publicado por la Scuola y fechas con enlaces al artículo original;
«Ver más noticias» permite recorrer el año sin cargar todas las imágenes de
una vez. No mezcla estas noticias con los comunicados ni con BioBioChile.
Las fotos se solicitan sólo cuando se acercan al área visible de Noticias:
no se descargan mientras la pestaña esté oculta. Si no se puede verificar una
miniatura, se conserva el texto sin recurrir a la imagen grande. Los extractos
se muestran completos tal como los entrega el sitio (algunos ya incluyen «[..]»).
La lectura queda en `salida/noticias_scuola.json`, también fuera del publicador.
Noticias Scuola ahora puede leer la caché compartida de Supabase: títulos
traducidos, lector interno de texto y contador independiente de no leídas.
El servidor revisa novedades cada 15 minutos; el navegador consulta una
versión ligera cada minuto y sólo descarga la lista si cambia. No hay avisos
push por noticias ni publicación de la web. Detalles de permisos, costos,
traducciones nuevas y configuración: [docs/noticias_scuola.md](docs/noticias_scuola.md).
Ambas vistas conservan la pestaña «Mensajes de la Scuola» mediante una copia
de los comunicados reales, consultada por GET al generar el HTML con la
configuración pública del calendario. El navegador sigue sin conexión a
Supabase: no modifica ni elimina mensajes ni tarjetas. Los comunicados de
la copia local no se actualizan en vivo.

**Avisos inmediatos por ediciones y PDF: activados en Supabase el 27/10/2026.**
Las ediciones, fechas, eventos nuevos, PDF y anulaciones disparan el envío
desde el servidor, sin depender del PC. El aviso horario no los repite;
conserva el resumen del sábado y los cambios detectados en EduFácil.
La recepción en teléfono queda por confirmar con una edición real.
Pasos, verificación y pausa: [docs/avisos_inmediatos.md](docs/avisos_inmediatos.md).

La estrategia es sencilla:

- **El sábado a las 7 de la mañana** se envía el resumen de la semana que
  viene (de lunes a viernes), con las fechas separadas por una línea en
  blanco. Si esa semana no hay evaluaciones, no se envía nada.
- **De lunes a viernes** sólo se avisa si algo cambió, y se avisa el mismo
  día: la tarea de avisos corre cada hora de 08:00 a 22:00.
- Si un cambio quedó pendiente (por ejemplo, la red falló), se suma al
  próximo aviso bajo el título «Cambios:».

El formato del resumen es un dato por línea:

```
Sáb 2026-10-10  →  "14, 15 y 16 oct · 3 evaluaciones"
                   Mié 14 oct
                   IDIOMA EXTRANJERO (ITALIANO)
                   Canción
                   Prof. VALENTINA ANDREA PÉREZ DÍAZ
                   Número 4
                   Sub-número 1
                   coef. 1

                   Jue 15 oct
                   ARTES VISUALES
                   …
```

El estado de los avisos queda en `logs/avisos_estado.json` y sólo avanza
cuando el envío sale bien. Para probar todo el circuito sin esperar al
sábado está `python avisos.py --probar-sabado`.

## Comunicados de BotScuola

La integración está en [`botscuola/`](botscuola/README.md). El flujo es Gmail →
remitente/fecha → clasificación de contenido → `public.comunicados` → Mensajes.
Sólo admite el dominio exacto del colegio; tener a un profesor o a Convivencia
en copia **no** evita el control de privacidad. Los personales y dudosos quedan
fuera; la IA puede equivocarse y su confianza no garantiza que un correo sea
público. Se analiza cada mensaje por separado y no se leen adjuntos.

- `previsualizarComunicados`: diagnóstico privado sin publicar ni notificar.
- `sincronizarComunicados`: carga la web sin reenviar avisos históricos.
- `procesarCorreosEscolares`: disparador habitual, sincroniza la web y conserva
  los canales privados de WhatsApp, Telegram y Google Calendar.
- Los IDs evitan duplicados; los fallos se reintentan sin inventar eventos.
  Groq recibe solicitudes espaciadas y se pausa tras límites de cuota.
- La lectura de comunicados es pública. INSERT exige la clave privada del bot;
  no se conceden UPDATE ni DELETE. El SQL generado y la clave quedan ignorados
  por git; sólo se versiona la plantilla SQL sin credenciales.

Publicar GitHub no instala el código ni activa el disparador en Google: se
reemplaza `Código.gs` en el proyecto existente conservando sus Propiedades y
`appsscript.json`. No hace falta una hoja de aprobación manual.
Los push web existentes cubren calendario/correcciones/resúmenes; todavía no
envían avisos por nuevos comunicados.

## Correcciones de la comunidad (Supabase)

La página se puede conectar a Supabase para que cualquiera pueda corregir un
dato y lo vean todos. Las reglas están pensadas para que nadie pueda romper
nada: la tabla es *append-only* (sólo se puede agregar y leer, nunca
actualizar o borrar), así que para deshacer se inserta un registro `anula`
y queda registro de quién anuló qué.

### Crear las tablas (una sola vez)

En la consola de SQL de Supabase:

```sql
create table if not exists public.ediciones (
  id      uuid primary key default gen_random_uuid(),
  tipo    text not null check (tipo in ('correccion','nuevo','anula')),
  clave   text not null,
  campos  jsonb not null default '{}'::jsonb
          check (jsonb_typeof(campos) = 'object'),
  previo  jsonb not null default '{}'::jsonb
          check (jsonb_typeof(previo) = 'object'),
  anula   uuid references public.ediciones(id),
  autor   text not null default '',
  token   text not null default '',
  creado  timestamptz not null default now()
);
create index if not exists ediciones_creado_idx on public.ediciones (creado);
alter table public.ediciones enable row level security;
create policy "lectura publica" on public.ediciones for select using (true);
create policy "solo agregar"    on public.ediciones for insert with check (true);
grant select, insert on public.ediciones to anon, authenticated;
```

Y la tabla de avisos, para que cada navegador pueda darse de alta:

```sql
create table if not exists public.suscripciones (
  id        uuid primary key default gen_random_uuid(),
  endpoint  text not null unique,
  p256dh    text not null,
  auth      text not null,
  agente    text not null default '',
  token     text not null default '',
  creado    timestamptz not null default now()
);
alter table public.suscripciones enable row level security;
create policy "suscripciones: lectura" on public.suscripciones for select using (true);
create policy "suscripciones: alta"    on public.suscripciones for insert with check (true);
grant select, insert on public.suscripciones to anon, authenticated;
```

Si una versión vieja quedó a medias: `drop table if exists public.ediciones;`
y vuelve a pegar el bloque. Para limpiar las filas de prueba (sólo mientras
nadie haya corregido nada): `truncate table public.ediciones;`

### Material de las actividades (PDF)

Cada evaluación puede llevar su PDF («material»). El botón **Elegir PDF** está
dentro de la ventana de edición; al Guardar se sube el archivo y se registra
el enlace en la misma tabla `ediciones` (tipo `adjunto`). El enlace aparece en
el detalle del día. Se pega una sola vez, después de las tablas de arriba:

```sql
-- sql/adjuntos.sql
alter table public.ediciones drop constraint if exists ediciones_tipo_check;
alter table public.ediciones add constraint ediciones_tipo_check
  check (tipo in ('correccion','nuevo','anula','adjunto'));

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('adjuntos', 'adjuntos', true, 8388608, array['application/pdf'])
on conflict (id) do update
  set public = true,
      file_size_limit = 8388608,
      allowed_mime_types = array['application/pdf'];

drop policy if exists "adjuntos: lectura" on storage.objects;
create policy "adjuntos: lectura" on storage.objects
  for select using (bucket_id = 'adjuntos');

drop policy if exists "adjuntos: subida" on storage.objects;
create policy "adjuntos: subida" on storage.objects
  for insert with check (
    bucket_id = 'adjuntos'
    and lower(right(name, 4)) = '.pdf'
  );
```

El bucket es público (cualquiera puede leer los PDF), y sólo admite PDF de
hasta 8 MB. Quitar un material no borra el archivo: agrega un `anula`, como el
resto de la bitácora.

### Cómo se evitan los problemas

- **Identidad con ordinal** (`MATEMÁTICA|1|EVALUACIÓN#2`): el mismo número se
  repite en el año, así que cada repetición lleva su posición según el orden
  del scrapeo, que no cambia cuando alguien corrige una fecha. Mover un dato
  nunca hace que la siguiente corrección apunte al registro equivocado.
  Los eventos manuales conservan además el ID de su alta al generar el HTML;
  retirar uno no renumera los demás ni cambia el destino de sus PDF. Las
  tarjetas retiradas tampoco reaparecen por venir en el HTML de una corrida
  anterior. Estos metadatos no agregan columnas a Excel/CSV/JSON.
- **Caducidad**: cada corrección guarda el valor que reemplazó; si EduFácil
  cambia ese dato por su cuenta, la corrección vieja se ignora sola y queda
  un aviso en `logs/ejecucion.log`.
- **Validación dos veces**: campos permitidos, fechas reales y longitudes
  razonables se revisan en la página y otra vez en Python; lo que llegue de
  la nube no contamina los archivos.
- **Aplicación idempotente**: si la base ya trae el cambio, no se vuelve a
  tocar (por eso el mismo archivo se puede regenerar 10 veces y sale igual).

### El día a día

- La página baja las filas **al abrirla** y las aplica encima de los datos
  embebidos: se ve al instante, incluso lo que corrigió otra persona.
- **Cinco veces al día** (00:00, 08:00, 12:00, 16:00 y 20:00) `tarea.bat` hace
  `scrapeo + filas` y de ahí salen los
  archivos, la página y las citas de Outlook, todos corregidos. Ese orden es
  a propósito: si Supabase no responde, la corrida no se rompe —usa el
  respaldo local `logs/ediciones.json` o sigue sin correcciones— y lo anota
  en el log.
- Sin nube: `python main.py --sin-nube` deja todo como estaba.

Prueba en vivo contra Supabase (escribe una corrección, verifica los
archivos, la anula y comprueba que el dato vuelve):

```bash
python test_nube.py
```

Esa prueba toca la base real, así que no hace falta correrla seguido.

## Outlook

Hecho con la API COM de Outlook 16.0 de escritorio (`pywin32`), que es el
que actualiza las citas en su lugar.

- Todo se crea en su propia carpeta (por defecto `Scuola Rafaela`; el nombre
  cambia con `--outlook-carpeta`), que aparece en Mis Calendarios y se crea
  sola si no existe. Así no se mezcla con tus citas personales.
- Cita de día completo, sin bloquear el horario, con un aviso un día antes
  (quítalo con `--sin-recordatorio`).
- Todo queda con la categoría `EvaScuola`: para deshacer, en Outlook
  `Ver → Cambiar vista → Gestor de categorías`, clic derecho en `EvaScuola`
  → *Eliminar categoría y elementos* (borra lo importado de una sola vez).
- **No se duplican aunque cambien las fechas.** Cada cita se identifica por
  su clave estable (asignatura + número + tipo; el resumen, por su sábado) y
  nunca por la fecha. Si el profesor mueve una prueba, se actualiza la misma
  cita con la nueva fecha.
- **No borra nada sin que lo pidas**: si una evaluación desaparece del sitio,
  la cita queda y aparece un aviso «n sin pareja»; con `--outlook-purgar` se
  eliminan. Los resúmenes de sábado sin actividades sí se borran solos, porque
  son datos derivados.
- El `.ics` para Google Calendar no lo genera este script: se descarga desde
  el botón de la página.

Si no quieres que abra Outlook cada mañana, borra `--outlook ...` de
`tarea.bat`.

## Publicación en GitHub Pages (URL fija)

`python publicar.py` sube lo que genera `main.py` (el HTML como `index.html`,
el manifest, `sw.js` y los iconos) al repositorio público
**`Akon2k/calendario-scuola`**, y la página queda viva en la URL de arriba.

- Primera corrida: crea el repo, sube todo, activa Pages y espera la
  compilación (unos 25 segundos). Las siguientes suben sólo los archivos que
  cambiaron.
- Usa el GitHub CLI (`gh auth login`), de ahí sale el token. El nombre del
  repo se cambia en `config.json → github.repo` (al cambiarlo cambia la URL:
  la PWA instalada tendría que volver a agregarse).
- Desde este commit, el repositorio contiene además **el código fuente** y
  este README. Los archivos de la raíz (`index.html`, `sw.js`, `manifest`,
  iconos) son la página publicada: los actualiza `publicar.py`, no los edites
  a mano.
- Es una URL pública y estable: quien la tenga ve el calendario (asignaturas,
  fechas, contenidos y profesores; **no** van el RUT ni la contraseña). Es el
  enlace para compartir con las familias.
- Si vas a subir cambios desde tu PC, primero `git pull` (la tarea programada
  sube la página sola todos los días y el repo avanza), y después tu commit.

La carpeta Docker (`localhost:8080`, y la URL del túnel de Cloudflare si está
levantado) sigue funcionando igual para la red local:

```bash
docker compose up -d                          # sólo la página
docker compose --profile tunel up -d          # con túnel a internet
docker compose logs -f tunel                  # ver la URL del túnel
docker compose --profile tunel down           # detener todo
```

## Ejecución programada (cinco veces al día)

```bash
instalar_tarea.bat             # 00:00, 08:00, 12:00, 16:00 y 20:00
instalar_tarea.bat /eliminar   # la quita
```

Corre `tarea.bat` en segundo plano y el resultado queda en `logs/tarea.log`.
La tarea principal se llama `CalendarioEvaScuolaTarjetas` (antes `CalendarioEvaScuola`:
al reinstalar, el instalador borra la vieja para que no corra duplicada).
El mismo instalador crea una segunda tarea, `CalendarioEvaScuolaAvisos`, que
cada hora de 08:00 a 22:00 corre sólo `avisos_dia.bat` (sin scrapeo ni
publicación) para anunciar una corrección el mismo día que se hizo; su
salida queda en `logs/avisos_dia.log`.

`tarea.bat` hace tres cosas, en orden y cortando si la primera falla:

1. exporta los archivos **y sincroniza Outlook** con
   `python main.py --outlook`: todo el calendario, sin tope de fecha, para
   que Outlook quede igual que la página pase lo que pase;
2. `python publicar.py` → sube la página a GitHub Pages;
3. `python avisos.py` → envía los avisos pendientes, **sólo entre 08:00 y
   21:59**: la corrida de la medianoche actualiza y publica, pero no manda
   notificaciones de madrugada.

Si `main.py` termina con error no se publica ni se avisa: se conserva la
última versión buena y queda anotado en `logs/tarea.log`.

De `main.py`: agrega las evaluaciones nuevas, mueve las que cambiaron de
fecha y actualiza los resúmenes de sábado. Si Outlook está cerrado, COM lo
abre a esa hora; si pide perfil o está bloqueado, la corrida termina con
código `6` y queda anotado en el log (los archivos de `salida/` igual se
generan antes).

## Estructura del proyecto

```
main.py             programa principal: baja todo y genera todo
avisos.py           los avisos (sábado y cambios)
publicar.py         sube la página a GitHub Pages
generar_vapid.py    genera las llaves de los avisos
botscuola/          bot de Apps Script, instalación y plantilla SQL sin claves
edufacil/
  cliente.py        sesión, menú y llamadas al sitio
  datos.py          el JSON del sitio a filas ordenadas
  semana.py         el resumen semanal (el sábado anterior)
  ediciones.py      correcciones de la comunidad (Supabase) + scrapeo
  exportar.py       Excel / CSV / JSON
  pagina.py         la página HTML y el .ics
  outlook.py        las citas en Outlook
test_pipeline.py    pruebas del pipeline
test_pagina.mjs     pruebas de la página (Node)
test_botscuola.mjs  pruebas simuladas de Gmail, IA, privacidad y carga automática
test_avisos.py      pruebas de los avisos
test_nube.py        prueba en vivo contra Supabase
ejecutar.bat        corro todo y publico (doble clic)
tarea.bat           lo que corre la tarea programada
instalar_tarea.bat  crea o quita las tareas programadas
probar_login.bat    sólo prueba las credenciales
docker-compose.yml  la página en la red local (y túnel opcional)
```

## Pruebas

| Comando | Qué comprueba |
|---|---|
| `python test_pipeline.py` | Que con datos de forma real salgan bien el Excel/CSV/JSON, el resumen del sábado con su línea en blanco, las claves estables, la página y el `.ics`, los recursos PWA y todas las reglas de la nube (corrección, idempotencia, caducidad, `anula`, alta, validación y respaldo) |
| `node test_pagina.mjs` | Ejecuta el JS de la página sobre un DOM simulado: pintado, clics, descarga del `.ics`, que los resúmenes calculados en JavaScript coincidan uno por uno con los de Python, el editor, la sección PWA, las instrucciones de uso y que el pie no nombre la carpeta de Outlook |
| `python test_avisos.py` | Los dos avisos: resumen del sábado (con línea en blanco, deduplicado y «Cambios:» colgando), cambios del sitio, correcciones de la comunidad con su autor, recorte «+N más», instantánea idempotente y suscripciones caducas — sin red |
| `node test_botscuola.mjs` | Remitentes/destinatarios, privacidad con CC/CCO, evidencia literal, carga automática sin duplicados, vista previa sin efectos y reintentos seguros de Groq — sin servicios reales |
| `python test_nube.py` | **En vivo contra Supabase**: escribe una corrección, la verifica en los archivos, la anula y comprueba que el dato vuelve al original |

## Si algo falla

| Código | Significado | Qué hacer |
|---|---|---|
| `2` | Credenciales rechazadas | Revisa `config.json` |
| `3` | No se encontró el menú o cambió el sitio | Ejecuta con `-v`; el error lista los enlaces disponibles |
| `4` | El año no tiene evaluaciones | Revisa con `--guardar-html` |
| `5` | Falló un exportador | Suele ser `openpyxl` ausente: `pip install -r requirements.txt` |
| `6` | No se pudo hablar con Outlook | Abre Outlook y vuelve a ejecutar (o quita `--outlook`) |
| `403` de Cloudflare | Demasiadas corridas seguidas | Espera un minuto y vuelve a ejecutar |

Los detalles de cada corrida quedan en `logs/`: `tarea.log` (la tarea diaria),
`publicar.log` (la subida a Pages), `avisos.log` y `avisos_dia.log` (los
avisos) y `ejecucion.log` (todo lo demás).

## Nota sobre las credenciales

Las credenciales son tuyas y sólo se usan para leer tu propio calendario.
`config.json` está ignorado por git: no lo subas a un repositorio, y no
pegues el RUT ni la contraseña en ningún archivo que sí se suba.
