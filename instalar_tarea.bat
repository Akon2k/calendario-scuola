@echo off
chcp 65001 >nul
title Instalar / quitar tarea programada
cd /d "%~dp0"

set "ARG1=%~1"

if /I "%ARG1%"=="/eliminar" goto eliminar

echo Creando tareas a las 00:00, 08:00, 12:00, 16:00 y 20:00 ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar_tarea.ps1"
if errorlevel 1 (
    echo.
    echo No se pudo crear la tarea. Ejecuta este archivo como Administrador.
) else (
    echo.
    echo Lista. Se actualiza cinco veces al dia y guarda el Excel en "salida".
    echo Para quitarla: instalar_tarea.bat /eliminar
)
pause
exit /b 0

:eliminar
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar_tarea.ps1" -Eliminar
pause
