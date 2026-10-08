@echo off
chcp 65001 >nul
set PYTHONUTF8=1
title Probar credenciales - EduFacil
cd /d "%~dp0"

echo Comprobando credenciales contra edufacil.cl ...
echo.
python main.py --probar-login -v
echo.
if errorlevel 1 (
    echo [FALLO] Revisa el archivo config.json y vuelve a intentar.
) else (
    echo [OK] Credenciales correctas.
)
pause
