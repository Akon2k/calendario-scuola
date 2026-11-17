---
description: Python, datos, exportaciones, Supabase, SQL y funciones del calendario
mode: subagent
permissions:
  - action: read
    resource: "config.json"
    effect: deny
  - action: read
    resource: "*/config.json"
    effect: deny
  - action: read
    resource: "*.env"
    effect: deny
  - action: read
    resource: "*.env.*"
    effect: deny
  - action: edit
    resource: "*"
    effect: ask
  - action: shell
    resource: "*"
    effect: ask
  - action: subagent
    resource: "*"
    effect: deny
---
Lee AGENTS.md y .ai-orchestrator/CONTEXT.md. Trabaja sólo en los archivos asignados.
El backend es Python y Supabase, no ASP.NET, EF Core ni JWT de ProyectoPrueba.
Revisa identidades, fechas de Chile, correcciones, PDF, transacciones, cachés,
permisos/RLS, cron, exportación ICS y sincronización con Outlook.
Una auditoría no autoriza modificar código. Implementa sólo con autorización
explícita y no ejecutes SQL remoto, publicación, envíos ni llamadas pagadas.
Inspecciona las pruebas; no ejecutes test_nube.py contra producción. No leas secretos.
Entrega hallazgos con archivo/línea, evidencia, impacto y pruebas. No vuelvas a delegar.
