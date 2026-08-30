@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr"
set "PATH=%JAVA_HOME%\bin;%PATH%"
set "GRADLE_OPTS=-Dorg.gradle.java.home=%JAVA_HOME%"

echo JAVA_HOME=%JAVA_HOME%
java -version

echo ========================================
echo WaterBridge Local Runtime
echo ========================================
echo.

echo [1/5] PostgreSQL starting...

docker compose --env-file backend\.env up -d postgres
if errorlevel 1 (
    echo.
    echo [ERROR] PostgreSQL start failed.
    pause
    exit /b 1
)

echo Waiting for PostgreSQL...

:WAIT_DB
for /f "delims=" %%H in ('docker inspect -f "{{.State.Health.Status}}" watercare-local-postgres-1 2^>nul') do (
    if "%%H"=="healthy" goto DB_READY
)

timeout /t 1 /nobreak >nul
goto WAIT_DB

:DB_READY
echo PostgreSQL OK.
echo.

echo [2/5] Backend starting...
start "WaterBridge Backend" cmd /k "cd /d ""%CD%"" && backend\.venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8000"

timeout /t 2 /nobreak >nul

echo [3/5] AI starting...
start "WaterBridge AI" cmd /k "cd /d ""%CD%"" && ai\.venv\Scripts\python.exe -m uvicorn ai.app.main:app --host 127.0.0.1 --port 8001 --env-file backend\.env"

timeout /t 2 /nobreak >nul

echo [4/5] Web starting...
start "WaterBridge Web" cmd /k "cd /d ""%CD%\web"" && npm run dev"

timeout /t 3 /nobreak >nul

echo [5/5] Mobile...

where adb >nul 2>&1
if errorlevel 1 (
    echo [WARN] adb not found. Mobile skipped.
    goto DONE
)

adb get-state >nul 2>&1
if errorlevel 1 (
    echo [WARN] Android device not connected. Mobile skipped.
    goto DONE
)

echo Setting adb reverse...
adb reverse tcp:8000 tcp:8000

echo Installing customer app...
pushd mobile
call gradlew.bat :customer-app:installLocalDebug
if errorlevel 1 (
    echo [WARN] Mobile install failed.
    popd
    goto DONE
)
popd

echo Opening customer app...
adb shell am start -n com.skn29.watercare.customer.local/com.skn29.watercare.customer.MainActivity

:DONE
echo.
echo ========================================
echo WaterBridge runtime started
echo ========================================
echo Backend : http://127.0.0.1:8000
echo AI      : http://127.0.0.1:8001
echo Web     : http://localhost:5173
echo Mobile  : Android customer-app
echo ========================================
echo.

pause