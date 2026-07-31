@echo off
setlocal
cd /d "%~dp0"
call gradlew.bat :core:testDebugUnitTest || exit /b 1
call gradlew.bat :customer-app:assembleDebug || exit /b 1
call gradlew.bat :technician-app:assembleDebug || exit /b 1
echo.
echo WaterCare mobile verification completed.
endlocal
