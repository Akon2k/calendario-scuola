# CalendarioEvaScuola: reglas del proyecto

1. Comienza por `.ai-orchestrator/CONTEXT.md` y `.ai-orchestrator/TASKS.md`.
   Este proyecto es Python + JavaScript + Supabase; no es ProyectoPrueba ni un backend .NET.
2. Lee después únicamente los archivos y dependencias pertinentes a la solicitud.
   Usa búsquedas acotadas; evita escaneos completos, listados masivos y abrir el HTML generado si basta la plantilla.
3. La solicitud actual del usuario define el trabajo autorizado. El tablero es una ayuda,
   no una orden para ejecutar tareas antiguas. Si no hay una tarea [ACTUAL], no inventes trabajo:
   atiende la consulta o acuerda qué tarea activar. Marca completado sólo lo realmente verificado.
4. Las revisiones son de sólo lectura por defecto. Antes de corregir código, instalar dependencias,
   ejecutar pruebas con efectos secundarios o cambiar infraestructura, obtén autorización.
5. No leas ni muestres `config.json`, archivos `.env`, claves privadas, tokens o endpoints de suscripción.
   Los archivos de `logs/`, `salida/` y `debug/` pueden contener información privada; pide permiso si son necesarios.
   Usa `config.example.json` y datos ficticios. No incluyas secretos en informes, git o HTML.
6. No hagas commit, push, publicación, migraciones remotas, purgas de Outlook ni envíos de avisos
   sin autorización explícita para esa acción. No ejecutes `test_nube.py` como prueba inocua.
7. Conserva cambios ajenos. No uses reset, checkout destructivo ni borrados amplios.
   Inspecciona cada prueba antes de ejecutarla; usa mocks y carpetas temporales para artefactos.
8. Mantén separadas la página de producción y las vistas previas locales de sólo lectura.
   Preserva las funciones y requisitos descritos en CONTEXT.md.
9. Al delegar, entrega objetivo, archivos acotados, restricciones y pruebas permitidas.
   No asignes el mismo archivo a dos agentes que escriban en paralelo. Los subagentes no vuelven a delegar.
10. Responde en español. Distingue evidencia, hipótesis y aspectos no comprobados.
    Informa archivos/líneas, impacto, pruebas y pendientes; no declares éxito real basándote sólo en mocks.
