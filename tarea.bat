@echo off
rem Ejecucion silenciosa para la Tarea Programada de Windows.
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist logs mkdir logs
rem 1) Baja el calendario, regenera salida/ y sincroniza Outlook (carpeta
rem    Scuola Rafaela) con TODO el calendario, sin tope de fecha: lo que
rem    cambie en el sitio se refleja en Outlook entero, no sólo desde una
rem    fecha. Si no quieres abrir Outlook a las 08:00, borra "--outlook ..."
rem    de esta linea.
python main.py --outlook >> "logs\tarea.log" 2>&1
if errorlevel 1 (
    echo [%date% %time%] main.py fallo: no se publica ni se avisa >> "logs\tarea.log"
    exit /b 1
)
rem 2) Sube la pagina a GitHub Pages (URL fija de la PWA).
python publicar.py >> "logs\tarea.log" 2>&1
rem 3) Envia los avisos (resumen del sabado + cambios del dia), solo de dia:
rem    la corrida de la medianoche actualiza y publica, pero no avisa a nadie.
set /a HORA_AVISOS=%time:~0,2%
if %HORA_AVISOS% GEQ 8 if %HORA_AVISOS% LSS 22 python avisos.py >> "logs\tarea.log" 2>&1
