@echo off
rem Ejecucion silenciosa para la Tarea Programada de Windows.
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist logs mkdir logs
rem 1) Baja el calendario, regenera salida/ y sincroniza Outlook (carpeta
rem    Scuola Rafaela). Si no quieres abrir Outlook a las 07:00, borra
rem    "--outlook ..." de esta linea.
python main.py --outlook --outlook-desde 2026-10-01 >> "logs\tarea.log" 2>&1
if errorlevel 1 (
    echo [%date% %time%] main.py fallo: no se publica ni se avisa >> "logs\tarea.log"
    exit /b 1
)
rem 2) Sube la pagina a GitHub Pages (URL fija de la PWA).
python publicar.py >> "logs\tarea.log" 2>&1
rem 3) Envia los avisos (resumen del sabado + cambios del dia).
python avisos.py >> "logs\tarea.log" 2>&1
