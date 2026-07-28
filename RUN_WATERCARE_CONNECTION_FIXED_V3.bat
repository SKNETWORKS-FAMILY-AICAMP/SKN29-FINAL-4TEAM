@echo off
setlocal EnableExtensions EnableDelayedExpansion
title WaterCare Connection and Route Setup V6

cd /d "%~dp0"
set "ROOT=%CD%"
set "BACKEND=%ROOT%\WaterCareBackend"
set "ANDROID=%ROOT%\mobile"
set "ROUTE_RESULT=%ROOT%\watercare_route_test.json"

echo ============================================
echo WaterCare Connection and Route Setup V6
echo ============================================
echo.

rem The repository contains both backend and WaterCareBackend.
rem The Kakao driving route API is implemented in WaterCareBackend.
if not exist "%BACKEND%\manage.py" (
    echo ERROR: WaterCareBackend\manage.py was not found.
    echo Put this file directly in C:\skn29\WaterCare
    goto :FAIL
)

if not exist "%BACKEND%\apps\visits\kakao_directions.py" (
    echo ERROR: Kakao route implementation was not found.
    echo Expected:
    echo %BACKEND%\apps\visits\kakao_directions.py
    goto :FAIL
)

if not exist "%BACKEND%\apps\visits\urls.py" (
    echo ERROR: route URL configuration was not found.
    goto :FAIL
)

rem --------------------------------------------------
rem Find adb.exe and select a physical Android phone.
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
    goto :FAIL
)

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
rem Apply USB port forwarding.
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
rem Keep Android backend URL consistent.
rem --------------------------------------------------
if exist "%ANDROID%\local.properties" (
    findstr /v /b /c:"BACKEND_BASE_URL=" "%ANDROID%\local.properties" > "%ANDROID%\local.properties.tmp"
    echo BACKEND_BASE_URL=http://127.0.0.1:8000/>>"%ANDROID%\local.properties.tmp"
    move /y "%ANDROID%\local.properties.tmp" "%ANDROID%\local.properties" >nul

    echo BACKEND_BASE_URL updated:
    echo %ANDROID%\local.properties
    echo.
) else (
    echo WARNING: mobile\local.properties was not found.
    echo.
)

rem --------------------------------------------------
rem Check whether the correct route API is already running.
rem --------------------------------------------------
set "HTTP_CODE=000"

for /f %%H in ('curl.exe -s -o "%ROUTE_RESULT%" -w "%%{http_code}" "http://127.0.0.1:8000/api/routes/driving/?origin_lat=37.55860^&origin_lng=126.98600^&destination_lat=37.56650^&destination_lng=126.97800"') do (
    set "HTTP_CODE=%%H"
)

if "!HTTP_CODE!"=="200" (
    echo The correct route backend is already running.
    goto :SUCCESS
)

rem --------------------------------------------------
rem Stop a different server already occupying port 8000.
rem --------------------------------------------------
set "OLD_PID="

for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":8000 .*LISTENING"') do (
    if not defined OLD_PID set "OLD_PID=%%P"
)

if defined OLD_PID (
    echo Port 8000 is used by PID !OLD_PID!.
    echo The active server did not return the route API.
    choice /c YN /n /m "Stop PID !OLD_PID! and start WaterCareBackend? [Y/N]: "

    if errorlevel 2 (
        echo Existing process was not stopped.
        goto :FAIL
    )

    taskkill /PID !OLD_PID! /F >nul 2>&1
    timeout /t 2 /nobreak >nul
)

rem --------------------------------------------------
rem Prepare the WaterCareBackend Python environment.
rem --------------------------------------------------
set "PYTHON_EXE=%BACKEND%\.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Creating WaterCareBackend virtual environment...

    where py >nul 2>&1
    if not errorlevel 1 (
        pushd "%BACKEND%"
        py -3.13 -m venv .venv
        if errorlevel 1 py -m venv .venv
        popd
    ) else (
        where python >nul 2>&1
        if errorlevel 1 (
            echo ERROR: Python was not found.
            goto :FAIL
        )

        pushd "%BACKEND%"
        python -m venv .venv
        popd
    )
)

if not exist "%PYTHON_EXE%" (
    echo ERROR: virtual environment creation failed.
    goto :FAIL
)

pushd "%BACKEND%"

"%PYTHON_EXE%" -c "import django, rest_framework, requests" >nul 2>&1

if errorlevel 1 (
    echo Installing WaterCareBackend packages...
    "%PYTHON_EXE%" -m pip install -r requirements.txt

    if errorlevel 1 (
        popd
        echo ERROR: package installation failed.
        goto :FAIL
    )
)

echo Checking WaterCareBackend...
"%PYTHON_EXE%" manage.py check

if errorlevel 1 (
    popd
    echo ERROR: Django check failed.
    goto :FAIL
)

echo Applying migrations...
"%PYTHON_EXE%" manage.py migrate

if errorlevel 1 (
    popd
    echo ERROR: migration failed.
    goto :FAIL
)

popd

rem --------------------------------------------------
rem Start only the backend that contains the Kakao route API.
rem --------------------------------------------------
start "WaterCare Route Backend" cmd /k "cd /d ""%BACKEND%"" && ""%PYTHON_EXE%"" manage.py runserver 127.0.0.1:8000"

echo Waiting for the route API...
set "HTTP_CODE=000"

for /L %%I in (1,1,30) do (
    timeout /t 1 /nobreak >nul

    for /f %%H in ('curl.exe -s -o "%ROUTE_RESULT%" -w "%%{http_code}" "http://127.0.0.1:8000/api/routes/driving/?origin_lat=37.55860^&origin_lng=126.98600^&destination_lat=37.56650^&destination_lng=126.97800"') do (
        set "HTTP_CODE=%%H"
    )

    if "!HTTP_CODE!"=="200" goto :SUCCESS
    if "!HTTP_CODE!"=="502" goto :KAKAO_ERROR
)

echo ERROR: route API did not return HTTP 200.
echo HTTP code: !HTTP_CODE!
echo Response:
type "%ROUTE_RESULT%"
goto :FAIL

:KAKAO_ERROR
echo.
echo ERROR: Django is running, but Kakao Directions returned HTTP 502.
echo Check KAKAO_REST_API_KEY in WaterCareBackend\.env.
echo Response:
type "%ROUTE_RESULT%"
goto :FAIL

:SUCCESS
echo.
echo ============================================
echo SUCCESS: Android route connection is ready
echo ============================================
echo Backend : %BACKEND%
echo Phone   : %PHONE_SERIAL%
echo API     : http://127.0.0.1:8000/api/routes/driving/
echo.
echo Keep the WaterCare Route Backend window open.
echo Rebuild the Android app and reload the route.
echo.
pause
exit /b 0

:FAIL
echo.
echo ============================================
echo ROUTE SETUP FAILED
echo ============================================
echo Check the message above.
echo.
pause
exit /b 1
