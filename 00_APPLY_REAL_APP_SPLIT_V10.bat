@echo off
setlocal EnableExtensions
title WaterCare Real App Split V10

cd /d "%~dp0"

echo ============================================
echo WaterCare Customer / Technician Split V10
echo ============================================
echo.

if not exist "mobile\settings.gradle.kts" (
    echo ERROR: Put this file in C:\skn29\WaterCare
    goto :FAIL
)

echo Removing the old product-flavor split files...

if exist "mobile\app\src\customer" (
    rmdir /s /q "mobile\app\src\customer"
)

if exist "mobile\app\src\technician" (
    rmdir /s /q "mobile\app\src\technician"
)

if exist "mobile\app\src\main\java\com\skn29\watercare\ui\technician\TechnicianApp.kt" (
    del /q "mobile\app\src\main\java\com\skn29\watercare\ui\technician\TechnicianApp.kt"
)

if exist "mobile\app\src\main\res\drawable-nodpi\customer_home_hero.png" (
    del /q "mobile\app\src\main\res\drawable-nodpi\customer_home_hero.png"
)

if exist "mobile\app\src\main\res\drawable-nodpi\technician_home_hero.png" (
    del /q "mobile\app\src\main\res\drawable-nodpi\technician_home_hero.png"
)

echo.
echo Old V8/V9 flavor files were removed.
echo.
echo Android Studio:
echo   1. Open C:\skn29\WaterCare\mobile
echo   2. File ^> Sync Project with Gradle Files
echo   3. Run customerApp or technicianApp
echo.
echo Customer app icon:
echo   original app_icon_mascot.png
echo.
echo Technician app:
echo   separate application module technicianApp
echo.
pause
exit /b 0

:FAIL
echo.
echo App split setup failed.
pause
exit /b 1
