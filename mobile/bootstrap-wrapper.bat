@echo off
setlocal
cd /d "%~dp0"
if not exist "gradle\wrapper" mkdir "gradle\wrapper"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/gradle/gradle/v9.5.0/gradle/wrapper/gradle-wrapper.jar' -OutFile 'gradle/wrapper/gradle-wrapper.jar'"
if errorlevel 1 exit /b 1
if not exist "gradle\wrapper\gradle-wrapper.jar" exit /b 1
echo Gradle Wrapper ready.
endlocal
