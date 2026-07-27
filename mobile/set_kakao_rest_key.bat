@echo off
cd /d "%~dp0"
set /p REST_KEY=Paste Kakao REST API key: 

if "%REST_KEY%"=="" (
  echo REST API key is empty.
  pause
  exit /b 1
)

if not exist "local.properties" (
  echo local.properties not found.
  pause
  exit /b 1
)

findstr /v /b "KAKAO_REST_API_KEY=" "local.properties" > "local.properties.tmp"
echo KAKAO_REST_API_KEY=%REST_KEY%>>"local.properties.tmp"
move /y "local.properties.tmp" "local.properties" >nul

echo Kakao REST API key saved.
echo Do not commit local.properties to GitHub.
pause
