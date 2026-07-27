@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo [WaterCare] 이전 버전 잔여 파일 정리 중...

del /q "app\src\main\java\com\skn29\watercare\tracking\VisitTrackingService.kt" 2>nul
del /q "app\src\main\java\com\skn29\watercare\ui\map\NaverTrackingMap.kt" 2>nul
del /q "app\src\main\java\com\skn29\watercare\ui\shared\RoleSelectionScreen.kt" 2>nul
del /q "app\src\main\java\com\skn29\watercare\ui\technician\TechnicianScreens.kt" 2>nul

echo.
echo 정리 완료:
echo - VisitTrackingService.kt
echo - NaverTrackingMap.kt
echo - RoleSelectionScreen.kt
echo - TechnicianScreens.kt
echo.
echo Android Studio에서 Build ^> Clean Project 후 Rebuild Project를 실행하세요.
pause
