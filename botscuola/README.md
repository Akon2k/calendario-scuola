# BotScuola automático

`BotScuola.gs` es el código completo para el proyecto de Google Apps Script.
Cambiar la copia de la PC no cambia el proyecto de Google ni publica GitHub.

## Regla solicitada, sin revisión manual

- Sólo correos con remitente del dominio exacto `scuolaitalianadiconcepcion.cl`.
- Para, CC y CCO visible sólo contienen a `ivancarmonavidal@gmail.com`,
  `franciscaverasalazar@gmail.com` o ambos: **se clasifica por contenido**, porque
  podría ser un comunicado masivo con los demás destinatarios en CCO.
- Si hay otras direcciones, **también se comprueba el contenido**. Una copia a
  Convivencia o a profesores no autoriza a publicar información individual.
- Se ignoran mayúsculas y repeticiones. Los nombres no cuentan como direcciones.
- Sin destinatarios visibles: también se clasifica por contenido. Un encabezado
  malformado no se admite.
- La web se alimenta desde el **01/09/2026, 00:00 de Chile** (UTC-4 ese día),
  hasta el momento de cada ejecución. La fecha final avanza con los días.

**CCO:** Gmail normalmente oculta las direcciones de los demás destinatarios.
No se puede demostrar que hubo envío masivo. Para esos casos, Groq evalúa el
asunto y el cuerpo del mensaje como `general`, `personal` o `dudoso`. Sólo se
publica un `general` con confianza numérica de al menos 0,90 y una cita literal
de 12 a 400 caracteres que exista en el cuerpo. Faltando alguno de esos datos,
queda fuera. **La confianza del modelo no es una garantía de acierto.**

La cita no se le pide a la IA: el script divide el cuerpo en fragmentos de
hasta 300 caracteres (`F1`, `F2`, etc.). El modelo elige `evidencia_id` y el
script extrae la evidencia del original. Una cita inventada que venga en el JSON
se ignora; un ID inexistente se rechaza. Esto evita que una paráfrasis de un
aviso general provoque un descarte por falta de coincidencia literal.

Avisos de horarios, materiales, tareas, rúbricas y actividades generales pueden
admitirse. Casos de alumnos, notas o salud individuales, incidentes privados y
respuestas personales de encuestas no. Si hay información personal dentro de un
aviso aparentemente general o de su texto citado, se pide `personal` o `dudoso`.
No se filtra por curso ni siglas: **«GIORNATA DEI COLORI 3MS» no se descarta por
su título**. Ningún título garantiza por sí solo que el contenido sea general.

El control de contenido tiene prioridad para **todos** los mensajes, incluso
con muchos destinatarios. Ya no existe el atajo que publicaba por tener copias.
Una referencia explícita como «su hija, Nombre Apellido» se bloquea antes de
enviarla a Groq; tampoco una clasificación `general` del modelo puede salvarla.
Es una protección adicional conservadora, no una garantía de detectar todo
caso individual: los demás casos siguen requiriendo clasificación general,
confianza y evidencia. El saludo «Estimados apoderados» no demuestra envío masivo.

No hay casillas ni autorización por correo. Se quitaron las funciones de Sheets.
La hoja privada anterior y sus decisiones no se modifican ni se borran; ya no
se consultan. La propiedad antigua `BOTSCUOLA_REVISION_HOJA` tampoco se necesita,
pero no hace falta borrarla para que funcione.

## Instalar y dejar funcionando

1. Guarda copia del código anterior de Google. Reemplaza el contenido de
   `Código.gs` por `BotScuola.gs` y guarda. No reemplaces `appsscript.json` ni
   las Propiedades del script. No dejes funciones duplicadas en otros `.gs`.
2. Conserva `GROQ_API_KEY`, `BOTSCUOLA_CLAVE`, `TELEGRAM_TOKEN`,
   `TELEGRAM_CHATID` y `WA_IVAN_KEY` en Propiedades del script.
   Antes de cargar los nuevos casos por contenido, se puede ejecutar
   **`previsualizarComunicados`**: muestra APTO/OMITIDO/YA GUARDADO sin insertar,
   enviar avisos, cambiar etiquetas ni escribir caché. Esta prueba **sí lee
   los cuerpos de correos nuevos y los envía a Groq** para clasificarlos.
   El registro detalla tipo, confianza, motivo de rechazo, tamaño del texto y
   si la cita coincide literalmente; no imprime el cuerpo ni la cita privada.
   Así se distingue un descarte por contenido de uno por evidencia inválida.
3. Ejecuta **`sincronizarComunicados` una vez**: recupera los comunicados desde
   septiembre, incluso de hilos ya etiquetados por el bot antiguo. Publica en la
   tabla sin reenviar los avisos antiguos de WhatsApp, Telegram ni Calendar.
4. Para los correos futuros, el disparador debe ejecutar
   **`procesarCorreosEscolares`**. Esa función sincroniza la web y mantiene
   los canales privados anteriores. Si ya existe ese disparador, no lo dupliques.
   Si no existe: **Desencadenadores (reloj) → Añadir → procesarCorreosEscolares
   → Según tiempo → Temporizador por minutos → Cada 15 minutos**.

Guardar el código por sí solo no crea un disparador. No hace falta desplegar
una aplicación web. La tabla y la clave ya configuradas sirven sin repetir SQL.
Los comunicados insertados son de lectura pública.

## Cómo evita duplicados y correos personales

- Revisa cada mensaje individual, no sólo el último correo de un hilo.
- Antes de leer cuerpos, consulta los IDs ya guardados en Supabase: no vuelve
  a llamar a la IA para los mensajes existentes.
- La sincronización web ignora `Scuola_Procesado` para no perder mensajes nuevos
  en hilos viejos. No modifica etiquetas ni borra datos de Gmail o Supabase.
- La rutina privada mantiene su consulta anterior de últimos 30 días y exclusión
  de hilos etiquetados, para no volver a enviar avisos históricos.
- Usa sólo el cuerpo del mensaje elegido; nunca concatena respuestas personales.
- Si falla Groq o la inserción, se reintenta en una ejecución posterior. Nunca
  se agenda una reunión ficticia de respaldo.
- Los descartes por contenido se recuerdan temporalmente para no reenviar
  cuerpos personales a la IA cada 15 minutos: 7 días para personal claro y
  1 día para dudoso. La caché usa propiedades `BOTSCUOLA_OMITIDO_V2_*` y sólo
  contiene ID, tipo y caducidad, no texto, asuntos ni nombres.
  La versión V2 no reutiliza descartes antiguos V1 por evidencia parafraseada;
  no hace falta borrar propiedades ni modificar la tabla.
- Usa bloqueo para no solapar corridas e ID de Gmail como clave única.
- No guarda Para, CC, CCO ni el cuerpo completo: guarda asunto, remitente escolar,
  fecha, puntos del resumen, acción y eventos extraídos por Groq.

## Ver todos los correos del mes, incluidos los personales

Ejecutar **`revisarFiltroCorreos`**. Busca cualquier remitente del dominio, por
ejemplo Inspectoría, Tamara o Valentina, desde el 01/09/2026 hasta la hora de la
consulta, sin excluir etiquetas de procesado. Muestra cada mensaje una vez,
ordenado del más reciente al más antiguo, con fecha de Chile, remitente,
asunto, señal de destinatarios y motivo. Los casos con CCO aparecen como
`POR CONTENIDO`, no como personales confirmados. No confunde una respuesta de los padres en el
mismo hilo con un correo proveniente de la Scuola.

**El listado privado incluye los personales, la tabla pública no.** Por eso el
total del registro puede ser mayor que el número de mensajes de la página.
No imprime las direcciones de otros apoderados ni lee cuerpos, usa IA, pide
aprobaciones o modifica Gmail/Supabase. Es sólo un diagnóstico opcional.

Pruebas sin Gmail, Groq ni Supabase reales:

```text
node test_botscuola.mjs
```

## Revisar los pendientes por fallos

Ejecutar **`previsualizarComunicados`** con el código actualizado. Cada fallo
produce una línea **`PENDIENTE`** con asunto, fecha ISO (UTC), enlace privado a
Gmail y diagnóstico de cada modelo: estado HTTP (por ejemplo, 429 indica límite
o cuota), JSON inválido, evidencia/esquema inválido o error de conexión.
El enlace usa la primera cuenta abierta de Gmail; abrirlo con la cuenta del bot.

No imprime el cuerpo, las citas, las respuestas completas del proveedor ni sus
excepciones sin filtrar, que podrían contener información privada. Estos datos
son sólo para el registro privado de Apps Script, no se guardan en la tabla.
No hace falta aprobar nada: la siguiente ejecución reintenta los fallos y sólo
admite los que superen los filtros. La vista previa no publica ni notifica ni
escribe caché; al repetirla, los pendientes pueden cambiar si la IA responde.

Se usan `openai/gpt-oss-20b` y `openai/gpt-oss-120b`, que respondieron en las
pruebas reales. Los otros tres modelos devolvían 404 y fueron retirados de la
lista, sin asumir que estén disponibles para esa cuenta. Las solicitudes se
separan al menos 7 segundos, también al pasar al respaldo. Esto reduce las
ráfagas, pero no garantiza evitar una cuota por tokens o una cuota diaria.
Tras un 429 se pausa ese modelo durante la ejecución, usando `Retry-After`
o 60 segundos si falta; mientras tanto los mensajes quedan pendientes sin
volver a solicitarlo. La pausa sólo vive en memoria; no escribe propiedades.
El límite de seguridad incluye las esperas. No repetir vistas previas seguidas
si continúa el 429: consultar los límites/uso de la cuenta de Groq antes de
reintentar. Un resultado personal que cambie a general en otra prueba no
constituye por sí solo una comprobación de privacidad.

## Tabla y clave de escritura (sólo para una instalación nueva)

```text
python botscuola/preparar_sql.py
```

- Copiar `salida/comunicados.sql` en el SQL Editor de Supabase y ejecutar.
- Guardar el contenido de `logs/botscuola_clave.txt` como propiedad
  `BOTSCUOLA_CLAVE` en Apps Script. No compartir ni pegar esa clave en el código.

Ambos archivos están ignorados por git. La plantilla `botscuola/comunicados.sql`
no se ejecuta directamente: contiene un marcador. La tabla permite lectura
pública, pero exige una cabecera con esa clave privada para insertar. No concede
UPDATE ni DELETE; el SQL almacena sólo la huella SHA-256 de la clave.

## Historial visible

Apps Script y la página usan el mismo inicio fijo de septiembre. Cuenta la fecha del
correo, no la del evento mencionado. La página carga todos los comunicados del
período por lotes de 500, del más reciente al más antiguo, con desplazamiento
interno en la pestaña Mensajes. Los registros anteriores ya guardados se conservan
en Supabase, pero no se muestran. La página publicada se actualiza con
`python publicar.py`, después de comprobar los cambios en local.
