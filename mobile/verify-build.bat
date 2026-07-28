@echo off
setlocal
cd /d "%~dp0"

if not exist local.properties (
  call setup-local-properties.bat
  if errorlevel 1 exit /b 1
)

if not exist gradle\wrapper\gradle-wrapper.jar (
  call bootstrap-wrapper.bat
  if errorlevel 1 exit /b 1
)

call gradlew.bat :core:build
if errorlevel 1 exit /b 1

call gradlew.bat :customer-app:assembleDebug
if errorlevel 1 exit /b 1

call gradlew.bat :technician-app:assembleDebug
if errorlevel 1 exit /b 1

echo.
echo [DONE] All modules built successfully.
echo Customer APK:
echo   customer-app\build\outputs\apk\debug
echo Technician APK:
echo   technician-app\build\outputs\apk\debug
