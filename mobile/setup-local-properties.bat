@echo off
setlocal
cd /d "%~dp0"

set "SDK_DIR=%LOCALAPPDATA%\Android\Sdk"

if not exist "%SDK_DIR%\platforms" (
  echo [ERROR] Android SDK not found: %SDK_DIR%
  exit /b 1
)

set "SDK_FORWARD=%SDK_DIR:\=/%"

if exist local.properties (
  echo [INFO] local.properties already exists. It was not overwritten.
  type local.properties
  exit /b 0
)

(
  echo sdk.dir=%SDK_FORWARD%
  echo KAKAO_NATIVE_APP_KEY=
  echo BACKEND_BASE_URL=http://10.0.2.2:8000/
) > local.properties

echo [DONE] local.properties created.
type local.properties
