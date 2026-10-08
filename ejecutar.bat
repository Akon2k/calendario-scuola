@echo off
chcp 65001 >nul
set PYTHONUTF8=1
title Calendario de Evaluaciones - EduFacil
cd /d "%~dp0"

echo ============================================
echo   Calendario de Evaluaciones - EduFacil
echo ============================================
echo.

python main.py %*

echo.
if errorlevel 1 (
    echo Hubo un problema: revisa el mensaje de arriba o "logs\ejecucion.log".
) else (
    echo Listo. Los archivos quedaron en la carpeta "salida".
    echo.
    echo Publicando la pagina en GitHub Pages...
    python publicar.py
    echo.
    echo Enviando los avisos (resumen del sabado + cambios)...
    python avisos.py
)
pause
