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

rem Find adb.exe.
set "ADB_EXE="

if defined ANDROID_HOME if exist "%ANDROID_HOME%\platform-tools\adb.exe" (
    set "ADB_EXE=%ANDROID_HOME%\platform-tools\adb.exe"
)

if not defined ADB_EXE if defined ANDROID_SDK_ROOT if exist "%ANDROID_SDK_ROOT%\platform-tools\adb.exe" (
    set "ADB_EXE=%ANDROID_SDK_ROOT%\platform-tools\adb.exe"
)

if not defined ADB_EXE if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" (
    set "ADB_EXE=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
)

if not defined ADB_EXE if exist "C:\Users\Playdata\AppData\Local\Android\Sdk\platform-tools\adb.exe" (
    set "ADB_EXE=C:\Users\Playdata\AppData\Local\Android\Sdk\platform-tools\adb.exe"
)

if not defined ADB_EXE (
    echo ERROR: adb.exe was not found.
    pause
    exit /b 1
)

rem Select a physical phone and ignore emulators.
set "PHONE_SERIAL="

for /f "skip=1 tokens=1,2" %%A in ('"%ADB_EXE%" devices') do (
    if "%%B"=="device" (
        echo %%A | findstr /b /c:"emulator-" >nul
        if errorlevel 1 (
            if not defined PHONE_SERIAL set "PHONE_SERIAL=%%A"
        )
    )
)

if not defined PHONE_SERIAL (
    echo ERROR: no physical Android phone was found.
    echo Unlock the phone and allow USB debugging.
    "%ADB_EXE%" devices
    pause
    exit /b 1
)

echo Selected phone: %PHONE_SERIAL%

"%ADB_EXE%" -s "%PHONE_SERIAL%" reverse --remove tcp:8000 >nul 2>&1
"%ADB_EXE%" -s "%PHONE_SERIAL%" reverse tcp:8000 tcp:8000

if errorlevel 1 (
    echo ERROR: adb reverse failed.
    pause
    exit /b 1
)

echo Reverse mapping:
"%ADB_EXE%" -s "%PHONE_SERIAL%" reverse --list
echo.

cd /d "%BACKEND_DIR%"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv was not found.
    echo Run the package installation BAT first.
    pause
    exit /b 1
)

set "PYTHON_EXE=%BACKEND_DIR%\.venv\Scripts\python.exe"

rem Ensure migration packages exist.
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

echo Creating accounts migration...
"%PYTHON_EXE%" manage.py makemigrations accounts
if errorlevel 1 (
    echo ERROR: accounts migration creation failed.
    pause
    exit /b 1
)

echo Creating remaining migrations...
"%PYTHON_EXE%" manage.py makemigrations
if errorlevel 1 (
    echo ERROR: migration creation failed.
    pause
    exit /b 1
)

echo Applying migrations...
"%PYTHON_EXE%" manage.py migrate
if errorlevel 1 (
    echo ERROR: migration apply failed.
    pause
    exit /b 1
)

echo.
echo Starting Django at http://127.0.0.1:8000
echo Keep this window open while using the Android app.
echo.

"%PYTHON_EXE%" manage.py runserver 127.0.0.1:8000
pause
