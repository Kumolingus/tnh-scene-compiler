@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "TOOL_ROOT=%SCRIPT_DIR%.."
where python >nul 2>&1 && (set "PY=python") || (
    where py >nul 2>&1 && (set "PY=py") || (
        echo ERROR: Python not found.
        pause & exit /b 1
    )
)
set "PYTHONPATH=%TOOL_ROOT%;%PYTHONPATH%"
%PY% -m tnh_generate_cheatsheet %*
pause
