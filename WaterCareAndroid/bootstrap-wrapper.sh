#!/usr/bin/env sh
set -eu
URL="https://raw.githubusercontent.com/gradle/gradle/v9.5.0/gradle/wrapper/gradle-wrapper.jar"
DEST="gradle/wrapper/gradle-wrapper.jar"
mkdir -p "$(dirname "$DEST")"
if command -v curl >/dev/null 2>&1; then
  curl -L --fail "$URL" -o "$DEST"
elif command -v wget >/dev/null 2>&1; then
  wget -O "$DEST" "$URL"
else
  echo "curl 또는 wget이 필요합니다." >&2
  exit 1
fi
echo "Gradle Wrapper 준비 완료: $DEST"
