---
description: HTML, CSS, JavaScript, PWA, accesibilidad y listón del calendario
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
La interfaz sale de plantillas Python y JavaScript/CSS sin framework; no incorpores
Tailwind ni reescribas index.html a mano como fuente principal.
Revisa pestañas y respuestas tardías, contadores independientes, listeners/timers,
impresión/ICS, PDF, PWA, caché, teclado, móvil/escritorio y modo oscuro.
Conserva el listón sobre la barra del mes, 5 segundos, hasta 10 titulares y sus pausas.
Separa producción y vistas locales; no desconectes edición ni avisos al publicar.
Las revisiones son de sólo lectura. No publiques ni cambies datos remotos.
Implementa únicamente cambios autorizados. Entrega evidencia, pruebas y riesgos;
no te limites al nombre de un archivo. No leas secretos ni vuelvas a delegar.
