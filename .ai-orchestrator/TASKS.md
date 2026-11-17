# Tablero: CalendarioEvaScuola

Las tareas antiguas de ProyectoPrueba no pertenecen a este proyecto. Se conservó
su copia en el respaldo privado de configuración antes de sustituir este tablero.

- [COMPLETADO] CFG-001: Configurar y validar Orchestrator y sus especialistas para este proyecto, sin llamadas a modelos ni cambios en la aplicación.
- [COMPLETADO] UI-001: Vista simple/completa con preferencia por navegador. Ajustada para conservar visible el logo de la Scuola, el reloj/hora, la barra del mes y las pestañas (Calendario, Mensajes y Noticias Scuola), ocultando el ruido visual (listón externo, pronóstico/temperatura y botones secundarios). Verificado con pruebas unitarias y DOM simulado en verde. Código comiteado, pusheado y publicado en producción en GitHub Pages.
- [PENDIENTE] REV-001: Auditoría de sólo lectura: datos, calendario, interfaz/PWA, noticias, seguridad, publicación y continuidad del actualizador. Iniciar sólo cuando el usuario pida la revisión.
- [PENDIENTE] REV-002: Consolidar hallazgos de REV-001 por severidad, con archivo/línea, evidencia, reproducción, impacto y propuesta de corrección.
- [PENDIENTE] FIX-001: Acordar con el usuario qué correcciones implementar; no ejecutar automáticamente.

No se ha ejecutado todavía la auditoría REV-001. No marcarla completada por configurar agentes.
El estado del tablero no autoriza commits, publicación, envíos, migraciones ni activación de servicios.

Validación de CFG-001: OpenCode 2.2.2 descubrió Orchestrator como agente primario
y coder-backend, coder-frontend, reviewer y debugger como subagentes, todos sin
modelo forzado. Se conservó la configuración original en logs/orchestrator-backup-20261030-005447/.
Se comprobó la carga por API; no se lanzaron subagentes ni se consumieron consultas a modelos para validar.
