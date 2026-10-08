@echo off
rem Avisos a media jornada: corre SOLO avisos.py (sin scrapeo ni publicacion)
rem para anunciar una correccion el mismo dia que se hizo. Lo crea la tarea
rem programada "CalendarioEvaScuolaAvisos" (ver instalar_tarea.ps1).
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist logs mkdir logs
python avisos.py >> "logs\avisos_dia.log" 2>&1
