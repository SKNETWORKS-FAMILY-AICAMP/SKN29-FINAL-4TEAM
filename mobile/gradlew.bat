@echo off
set APP_HOME=%~dp0
set JAR=%APP_HOME%gradle\wrapper\gradle-wrapper.jar
if not exist "%JAR%" (
  echo gradle-wrapper.jar가 없습니다. bootstrap-wrapper.bat를 먼저 실행하세요.
  exit /b 1
)
if defined JAVA_HOME (
  set JAVA_EXE=%JAVA_HOME%\bin\java.exe
) else (
  set JAVA_EXE=java.exe
)
"%JAVA_EXE%" -classpath "%JAR%" org.gradle.wrapper.GradleWrapperMain %*
