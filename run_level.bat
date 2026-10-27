@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "LEVEL=%~1"
if not defined LEVEL (
    wscript.exe "%~dp0启动声呐助手.vbs"
    exit /b 0
)

for /f "delims=0123456789" %%A in ("%LEVEL%") do goto invalid_level
if %LEVEL% LSS 1 goto invalid_level
if %LEVEL% GTR 50 goto invalid_level

echo ========================================
echo Boom Beach Sonar - Level %LEVEL%
echo ========================================
echo Make sure the emulator is running and the game is on its home screen.
echo.

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -u "%~dp0run_level.py" --level %LEVEL%
    goto finished
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3 -u "%~dp0run_level.py" --level %LEVEL%
    goto finished
)

where python >nul 2>nul
if not errorlevel 1 (
    python -u "%~dp0run_level.py" --level %LEVEL%
    goto finished
)

echo [ERROR] Python was not found. Create .venv or install Python 3.
set "RUN_EXIT=9009"
goto done

:finished
set "RUN_EXIT=%ERRORLEVEL%"
if "%RUN_EXIT%"=="0" (
    echo.
    echo Run completed.
) else (
    echo.
    echo [ERROR] Process exit code: %RUN_EXIT%
    echo See _debug\logs\bbma.log for details.
)
goto done

:invalid_level
echo [ERROR] Level must be an integer from 1 to 50.
set "RUN_EXIT=2"

:done
echo.
exit /b %RUN_EXIT%
