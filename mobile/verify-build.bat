@echo off
setlocal
cd /d "%~dp0"

call gradlew.bat :core:test :customer-app:testDebugUnitTest :technician-app:testDebugUnitTest :customer-app:assembleDebug :technician-app:assembleDebug --no-daemon
if errorlevel 1 (
  echo.
  echo [FAIL] Gradle test or APK build failed.
  endlocal & exit /b 1
)

set CUSTOMER_APK=%CD%\customer-app\build\outputs\apk\debug\customer-app-debug.apk
set TECHNICIAN_APK=%CD%\technician-app\build\outputs\apk\debug\technician-app-debug.apk

if not exist "%CUSTOMER_APK%" (
  echo [FAIL] Customer APK not found: %CUSTOMER_APK%
  endlocal & exit /b 1
)

if not exist "%TECHNICIAN_APK%" (
  echo [FAIL] Technician APK not found: %TECHNICIAN_APK%
  endlocal & exit /b 1
)

echo.
echo [PASS] Core tests
echo [PASS] Customer unit tests
echo [PASS] Technician unit tests
echo [PASS] Customer Debug APK
echo [PASS] Technician Debug APK
echo WaterCare mobile verification completed.
endlocal & exit /b 0