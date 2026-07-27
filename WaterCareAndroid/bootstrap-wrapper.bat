@echo off
powershell -NoProfile -ExecutionPolicy Bypass -Command "New-Item -ItemType Directory -Force -Path 'gradle/wrapper' | Out-Null; Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/gradle/gradle/v9.5.0/gradle/wrapper/gradle-wrapper.jar' -OutFile 'gradle/wrapper/gradle-wrapper.jar'"
if errorlevel 1 exit /b 1
echo Gradle Wrapper 준비 완료
