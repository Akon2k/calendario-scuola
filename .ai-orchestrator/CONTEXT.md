# Contexto técnico: CalendarioEvaScuola

## Identidad y alcance
- Ruta: `E:\Proyectos Antigravity\CalendarioEvaScuola`.
- Aplicación: calendario escolar, documentos, comunicados, noticias y listón informativo.
- Stack: Python, HTML/CSS y JavaScript sin framework; Supabase/PostgreSQL y Edge Functions TypeScript/JavaScript.
- Publicación: GitHub Pages. No crear un backend ASP.NET, login, JWT, EF Core ni Tailwind por herencia de otra plantilla.
- Los agentes no fijan un modelo: heredan el modelo seleccionado en la sesión. No se garantiza gratuidad.
  Los alias de proveedores conservados en opencode.json son opcionales y no deben activarse sin elección del usuario.

## Mapa de archivos para lectura dirigida
- `main.py`, `edufacil/cliente.py`, `datos.py`, `exportar.py`, `semana.py`: obtención y exportación del calendario.
- `edufacil/ediciones.py`, `ics.py`, `outlook.py`: correcciones, identidades estables, ICS y Outlook.
- `edufacil/pagina.py`, `pwa.py`: plantilla, JavaScript, PWA, edición, PDF, pestañas y avisos.
- `edufacil/noticias_liston.py`: integra el diseño en producción sin desconectar sus funciones.
- `edufacil/informacion_local.py`, `actualizar_liston_local.py`, `vista_previa_liston.py`: fuentes y carrusel.
- `vista_noticias_scuola.py`, `supabase/functions/noticias-scuola/`, SQL de noticias: caché, lector y traducciones.
- `avisos.py`, `supabase/functions/avisos-ediciones/`, SQL de avisos: Web Push y sus reintentos.
- `botscuola/BotScuola.gs`: comunicados mediante Apps Script; no acceder a correos reales durante una auditoría.
- `publicar.py`, `tarea.bat`, `instalar_tarea.ps1`: publicación y automatización de Windows.
- `docs/noticias_scuola.md`, `docs/avisos_inmediatos.md`: operación; contrastar la documentación con el código.

## Requisitos que deben conservarse
- Calendario, tarjetas, correcciones, unión de tarjetas, PDF de hasta 8 MB, WhatsApp, Telegram, impresión e ICS.
- Exportación compatible con Google Calendar/Outlook y logo verde #008837.
- Horarios del calendario: 00:00, 08:00, 12:00, 16:00 y 20:00; zona horaria de Chile.
- Una sola pestaña/panel activo entre Calendario, Mensajes y Noticias Scuola, incluso tras respuestas tardías.
- Vista simple/completa opcional, recordada por navegador (`edufacil-vista`), también en móvil.
  La simple oculta el encabezado, clima, listón y controles secundarios, pero conserva pestañas,
  navegación del mes y el selector para restaurar todo. No desactiva avisos ni cambia otros dispositivos.
- Contadores independientes por navegador/dispositivo; entrar marca el contenido como leído.
- Noticias Scuola oficiales sólo de 2026, traducciones guardadas, miniaturas pequeñas y lector del texto sin fotos/videos.
- Listón sobre la barra del mes: tiempo, Ruta 160 y hasta 10 noticias; cambio cada 5 segundos.
- Prioridad a Coronel; sin titulares locales recientes, respaldo nacional de BioBioChile.
- Pausa al leer detalles, usar teclado, pasar el mouse o esconder la pestaña; movimiento reducido inicia pausado.
- Sin reportes de tránsito no significa ruta despejada. No inventar titulares, fechas, clima ni alertas.
- Impresora y descarga ICS con iconos accesibles y leyenda; ayuda pública de 10 puntos, sin iconos ni mención a Supabase.
- No hay push por Noticias Scuola. Una suscripción confirmada no demuestra recepción real en el dispositivo.

## Operación y precauciones
- El listón replica su snapshot público desde este PC cada 15 minutos con `--publicar`; el navegador revisa cada minuto.
  Depende de que el PC, la CLI autenticada y el actualizador estén activos. Ha sido detenido por reinicios del servidor.
  Investigar supervisión/recuperación sin instalar nada automáticamente ni reiniciar procesos durante una auditoría.
- Noticias Scuola tiene un cron independiente en el servidor; comprobar su estado antes de afirmar que funciona.
- Google Translation está preparado pero no debe activarse sin autorización, credencial y cuotas confirmadas.
  Preservar caché, reservas y límites documentados; no retraducir títulos ya guardados ni hacer llamadas pagadas de prueba.
- Brave puede necesitar habilitar los servicios de Google para mensajes push; no asumir que es incompatible.
- `test_nube.py` modifica producción. `test_pipeline.py` genera archivos y debe aislarse en una carpeta temporal.
- `ejecutar.bat`, `tarea.bat`, `publicar.py` y algunas opciones de `avisos.py` tienen efectos reales: no usarlos para verificar sin permiso.
- Revisa pruebas Python/Node específicas antes de ejecutarlas. Los mocks no verifican entregas push, facturación ni producción.
- No asumir cantidades fijas de noticias o comunicados: comprobar los datos sin exponer información privada.
