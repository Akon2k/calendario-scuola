@echo off
chcp 65001 >nul
title Instalar / quitar tarea programada
cd /d "%~dp0"

set "ARG1=%~1"
set "HORA=%~1"
if "%HORA%"=="" set "HORA=07:00"

if /I "%ARG1%"=="/eliminar" goto eliminar

echo Creando tarea diaria a las %HORA% ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar_tarea.ps1" -Hora "%HORA%"
if errorlevel 1 (
    echo.
    echo No se pudo crear la tarea. Ejecuta este archivo como Administrador.
) else (
    echo.
    echo Lista. Se ejecutara cada dia a las %HORA% y guardara el Excel en "salida".
    echo Para quitarla: instalar_tarea.bat /eliminar
)
pause
exit /b 0

:eliminar
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar_tarea.ps1" -Eliminar
pause
