@echo off
setlocal
title INNOVA - Crear Usuario Administrador

echo ================================================================
echo   Crear o Actualizar Usuario Administrador de INNOVA
echo ================================================================

python --version >nul 2>nul
if not errorlevel 1 (
    set PY_CMD=python
    goto run_admin
)

py --version >nul 2>nul
if not errorlevel 1 (
    set PY_CMD=py
    goto run_admin
)

for %%P in ("%USERPROFILE%\.local\bin\python*.exe") do (
    if exist "%%~P" (
        "%%~P" --version >nul 2>nul
        if not errorlevel 1 (
            set "PY_CMD=%%~P"
            goto run_admin
        )
    )
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
