@echo off
setlocal EnableExtensions EnableDelayedExpansion
title WaterCare Connection Setup V3

cd /d "%~dp0"
set "ROOT=%CD%"

echo ============================================
echo WaterCare Connection Setup V3
echo ASCII-only, no PowerShell script required
echo ============================================
echo.

rem --------------------------------------------------
rem 1. Find adb.exe
rem --------------------------------------------------
set "ADB="

if defined ANDROID_HOME if exist "%ANDROID_HOME%\platform-tools\adb.exe" (
    set "ADB=%ANDROID_HOME%\platform-tools\adb.exe"
)

if not defined ADB if defined ANDROID_SDK_ROOT if exist "%ANDROID_SDK_ROOT%\platform-tools\adb.exe" (
    set "ADB=%ANDROID_SDK_ROOT%\platform-tools\adb.exe"
)

if not defined ADB if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" (
    set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
)

if not defined ADB if exist "C:\Users\Playdata\AppData\Local\Android\Sdk\platform-tools\adb.exe" (
    set "ADB=C:\Users\Playdata\AppData\Local\Android\Sdk\platform-tools\adb.exe"
)

if not defined ADB (
    echo ERROR: adb.exe was not found.
    echo Check Android SDK installation.
    goto :FAIL
)

echo ADB:
echo %ADB%
echo.

rem --------------------------------------------------
rem 2. Select a physical Android phone
rem --------------------------------------------------
set "PHONE_SERIAL="

for /f "skip=1 tokens=1,2" %%A in ('"%ADB%" devices') do (
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
    echo.
    "%ADB%" devices
    goto :FAIL
)

echo Selected phone:
echo %PHONE_SERIAL%
echo.

rem --------------------------------------------------
rem 3. Apply adb reverse
rem --------------------------------------------------
"%ADB%" -s "%PHONE_SERIAL%" reverse --remove tcp:8000 >nul 2>&1
"%ADB%" -s "%PHONE_SERIAL%" reverse tcp:8000 tcp:8000

if errorlevel 1 (
    echo ERROR: adb reverse failed.
    goto :FAIL
)

echo Reverse mappings:
"%ADB%" -s "%PHONE_SERIAL%" reverse --list
echo.

rem --------------------------------------------------
rem 4. Find Android project and update local.properties
rem --------------------------------------------------
set "ANDROID_DIR="

if exist "%ROOT%\mobile\settings.gradle.kts" set "ANDROID_DIR=%ROOT%\mobile"
if not defined ANDROID_DIR if exist "%ROOT%\mobile\settings.gradle" set "ANDROID_DIR=%ROOT%\mobile"
if not defined ANDROID_DIR if exist "%ROOT%\WaterCareAndroid\settings.gradle.kts" set "ANDROID_DIR=%ROOT%\WaterCareAndroid"
if not defined ANDROID_DIR if exist "%ROOT%\WaterCareAndroid\settings.gradle" set "ANDROID_DIR=%ROOT%\WaterCareAndroid"

if defined ANDROID_DIR (
    set "LOCAL_PROPERTIES=%ANDROID_DIR%\local.properties"

    if exist "!LOCAL_PROPERTIES!" (
        findstr /v /b /c:"BACKEND_BASE_URL=" "!LOCAL_PROPERTIES!" > "!LOCAL_PROPERTIES!.tmp"
        echo BACKEND_BASE_URL=http://127.0.0.1:8000/>>"!LOCAL_PROPERTIES!.tmp"
        move /y "!LOCAL_PROPERTIES!.tmp" "!LOCAL_PROPERTIES!" >nul
        echo BACKEND_BASE_URL updated:
        echo !LOCAL_PROPERTIES!
        echo.
    ) else (
        echo WARNING: local.properties was not found.
        echo Create it in:
        echo %ANDROID_DIR%
        echo.
    )
) else (
    echo WARNING: Android project folder was not found.
    echo.
)

rem --------------------------------------------------
rem 5. Find Django backend
rem --------------------------------------------------
set "BACKEND="

if exist "%ROOT%\WaterCareBackend\manage.py" (
    set "BACKEND=%ROOT%\WaterCareBackend"
)

if not defined BACKEND if exist "%ROOT%\backend\manage.py" (
    set "BACKEND=%ROOT%\backend"
)

if not defined BACKEND if exist "%ROOT%\backend\mobile_tracking_server\manage.py" (
    set "BACKEND=%ROOT%\backend\mobile_tracking_server"
)

if not defined BACKEND (
    for /r "%ROOT%" %%F in (manage.py) do (
        if not defined BACKEND (
            echo %%~fF | findstr /i /c:"\.venv\" /c:"\venv\" /c:"\site-packages\" >nul
            if errorlevel 1 set "BACKEND=%%~dpF"
        )
    )
)

if not defined BACKEND (
    echo ERROR: Django manage.py was not found.
    goto :FAIL
)

if "%BACKEND:~-1%"=="\" set "BACKEND=%BACKEND:~0,-1%"

echo Backend:
echo %BACKEND%
echo.

rem --------------------------------------------------
rem 6. Find Python
rem --------------------------------------------------
set "PYTHON_EXE="

if exist "%BACKEND%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%BACKEND%\.venv\Scripts\python.exe"
)

if not defined PYTHON_EXE if exist "%BACKEND%\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%BACKEND%\venv\Scripts\python.exe"
)

if not defined PYTHON_EXE (
    where python >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=python"
)

if not defined PYTHON_EXE (
    echo ERROR: Python was not found.
    goto :FAIL
)

echo Python:
echo %PYTHON_EXE%
echo.

rem --------------------------------------------------
rem 7. Check Django and migrate
rem --------------------------------------------------
pushd "%BACKEND%"

"%PYTHON_EXE%" manage.py check
if errorlevel 1 (
    popd
    echo ERROR: Django check failed.
    goto :FAIL
)

"%PYTHON_EXE%" manage.py migrate
if errorlevel 1 (
    popd
    echo ERROR: Django migration failed.
    goto :FAIL
)

popd

rem --------------------------------------------------
rem 8. Start Django in a separate window
rem --------------------------------------------------
echo Starting Django server...
start "WaterCare Django Server" cmd /k "cd /d ""%BACKEND%"" && ""%PYTHON_EXE%"" manage.py runserver 127.0.0.1:8000"

echo.
echo ============================================
echo SUCCESS
echo ============================================
echo Android phone: %PHONE_SERIAL%
echo Backend URL : http://127.0.0.1:8000
echo.
echo Keep the new Django server window open.
echo Rebuild the Android app and reload the road route.
echo.
pause
exit /b 0

:FAIL
echo.
echo ============================================
echo SETUP FAILED
echo ============================================
echo The window will stay open.
echo Check the error above.
echo.
pause
exit /b 1
