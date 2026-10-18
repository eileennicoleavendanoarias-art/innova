@echo off
setlocal
title INNOVA Server - Web & Panel de Administracion

echo ================================================================
echo   Iniciando Servidor Web y Panel Administrativo de INNOVA
echo ================================================================

:: Check for python in system PATH
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set PY_CMD=python
    goto run_server
)

:: Check for py launcher
where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set PY_CMD=py
    goto run_server
)

:: Check for JetBrains Python
if exist "C:\Program Files\JetBrains\CLion 2026.2.3\bin\lldb\win\x64\bin\python.exe" (
    set "PY_CMD=C:\Program Files\JetBrains\CLion 2026.2.3\bin\lldb\win\x64\bin\python.exe"
    goto run_server
)

echo [ERROR] No se encontro una instalacion de Python en el sistema.
echo Por favor instala Python o configuralo en la variable PATH.
pause
exit /b 1

:run_server
echo [OK] Utilizando ejecutable: "%PY_CMD%"
echo [INFO] Servidor iniciando en http://127.0.0.1:8000/ ...
"%PY_CMD%" server.py
pause

