@echo off
setlocal
title INNOVA - Crear Usuario Administrador

echo ================================================================
echo   Crear o Actualizar Usuario Administrador de INNOVA
echo ================================================================

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set PY_CMD=python
    goto run_admin
)

where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set PY_CMD=py
    goto run_admin
)

if exist "C:\Program Files\JetBrains\CLion 2026.2.3\bin\lldb\win\x64\bin\python.exe" (
    set "PY_CMD=C:\Program Files\JetBrains\CLion 2026.2.3\bin\lldb\win\x64\bin\python.exe"
    goto run_admin
)

echo [ERROR] No se encontro Python en el sistema.
pause
exit /b 1

:run_admin
"%PY_CMD%" create_admin.py %*
pause

