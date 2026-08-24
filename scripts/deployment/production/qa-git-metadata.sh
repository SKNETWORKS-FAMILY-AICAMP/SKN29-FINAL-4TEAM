#!/bin/sh
set -eu

case "$*" in
  "rev-parse HEAD")
    printf '%s\n' "${RELEASE_SHA:?RELEASE_SHA is required}"
    ;;
  "status --porcelain")
    ;;
  *)
    printf 'Unsupported QA git metadata query: %s\n' "$*" >&2
    exit 64
    ;;
esac
