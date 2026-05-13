@echo off
setlocal

:: ---------------------------------------------------------------
:: Fountain-TNH Scene Compiler — drag-and-drop entry point.
:: Drop .scene files onto this script, or double-click to compile
:: every scene in the project.
:: ---------------------------------------------------------------

set "SCRIPT_DIR=%~dp0"
set "TOOL_ROOT=%SCRIPT_DIR%.."

:: Discover Python
where python >nul 2>&1 && (set "PY=python") || (
    where py >nul 2>&1 && (set "PY=py") || (
        echo ERROR: Python not found. Install Python 3.10+ and add it to PATH.
        pause
        exit /b 1
    )
)

:: Ensure the package is importable
set "PYTHONPATH=%TOOL_ROOT%;%PYTHONPATH%"

:: Compile dropped files or the full project
if "%~1"=="" (
    %PY% -m tnh_scene_compiler compile --verbose
) else (
    %PY% -m tnh_scene_compiler compile --verbose %*
)

echo.
if %ERRORLEVEL% EQU 0 (
    echo Compilation successful.
) else (
    echo Compilation finished with errors. See above.
)
pause
