@echo off
cd /d "%~dp0"

echo Cleaning old WaterCare files...

if exist "app\src\main\java\com\skn29\watercare\tracking\VisitTrackingService.kt" (
    del /f /q "app\src\main\java\com\skn29\watercare\tracking\VisitTrackingService.kt"
    echo Deleted VisitTrackingService.kt
) else (
    echo Skip VisitTrackingService.kt - not found
)

if exist "app\src\main\java\com\skn29\watercare\ui\map\NaverTrackingMap.kt" (
    del /f /q "app\src\main\java\com\skn29\watercare\ui\map\NaverTrackingMap.kt"
    echo Deleted NaverTrackingMap.kt
) else (
    echo Skip NaverTrackingMap.kt - not found
)

if exist "app\src\main\java\com\skn29\watercare\ui\shared\RoleSelectionScreen.kt" (
    del /f /q "app\src\main\java\com\skn29\watercare\ui\shared\RoleSelectionScreen.kt"
    echo Deleted RoleSelectionScreen.kt
) else (
    echo Skip RoleSelectionScreen.kt - not found
)

if exist "app\src\main\java\com\skn29\watercare\ui\technician\TechnicianScreens.kt" (
    del /f /q "app\src\main\java\com\skn29\watercare\ui\technician\TechnicianScreens.kt"
    echo Deleted TechnicianScreens.kt
) else (
    echo Skip TechnicianScreens.kt - not found
)

echo.
echo Cleanup finished.
echo Return to Android Studio and run:
echo Build ^> Clean Project
echo Build ^> Rebuild Project
pause
