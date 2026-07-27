@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

set "PROJECT_ROOT=%CD%"
set "BACKEND_DIR=%PROJECT_ROOT%\WaterCareBackend"

if not exist "%BACKEND_DIR%\manage.py" (
    echo ERROR: WaterCareBackend\manage.py was not found.
    echo Put this BAT file in C:\skn29\WaterCare
    pause
    exit /b 1
)

cd /d "%BACKEND_DIR%"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv was not found.
    echo Run RUN_WATERCARE_INSTALL_AND_START.bat first.
    pause
    exit /b 1
)

set "PYTHON_EXE=%BACKEND_DIR%\.venv\Scripts\python.exe"

echo ==============================================
echo WaterCare migration repair
echo ==============================================
echo.

rem Ensure Django migration packages exist.
for %%A in (accounts inquiries visits) do (
    if exist "apps\%%A" (
        if not exist "apps\%%A\migrations" (
            mkdir "apps\%%A\migrations"
        )
        if not exist "apps\%%A\migrations\__init__.py" (
            type nul > "apps\%%A\migrations\__init__.py"
        )
    )
)

echo [1/5] Django project check
"%PYTHON_EXE%" manage.py check
if errorlevel 1 (
    echo ERROR: Django project check failed.
    pause
    exit /b 1
)

echo.
echo [2/5] Creating the initial accounts migration
"%PYTHON_EXE%" manage.py makemigrations accounts
if errorlevel 1 (
    echo ERROR: accounts migration creation failed.
    pause
    exit /b 1
)

echo.
echo [3/5] Creating migrations for the remaining apps
"%PYTHON_EXE%" manage.py makemigrations
if errorlevel 1 (
    echo ERROR: migration creation failed.
    pause
    exit /b 1
)

echo.
echo [4/5] Applying migrations
"%PYTHON_EXE%" manage.py migrate
if errorlevel 1 (
    echo ERROR: migration apply failed.
    pause
    exit /b 1
)

echo.
echo [5/5] Showing migration status
"%PYTHON_EXE%" manage.py showmigrations

echo.
echo SUCCESS: migrations were created and applied.
echo Starting Django at http://127.0.0.1:8000
echo Keep this window open while using the Android app.
echo.

"%PYTHON_EXE%" manage.py runserver 127.0.0.1:8000
pause
