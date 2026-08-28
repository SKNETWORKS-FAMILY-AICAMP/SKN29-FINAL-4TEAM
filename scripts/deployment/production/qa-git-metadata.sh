#!/bin/sh
set -eu

repository_root=/workspace
system_git=/usr/bin/git

fail_unsupported() {
  printf 'Unsupported QA git metadata query: %s\n' "$*" >&2
  exit 64
}

validate_relative_path() {
  path="$1"
  case "$path" in
    ""|/*|..|../*|*/..|*/../*)
      printf 'Unsafe QA git metadata path.\n' >&2
      exit 64
      ;;
  esac
}

case "${1:-}" in
  rev-parse)
    [ "$#" -eq 2 ] || fail_unsupported "$@"
    case "$2" in
      HEAD)
        printf '%s\n' "${RELEASE_SHA:?RELEASE_SHA is required}"
        ;;
      origin/main)
        # The isolated build context has no remote refs. Match real Git's
        # not-found behavior instead of inventing an origin/main identity.
        exit 1
        ;;
      *)
        fail_unsupported "$@"
        ;;
    esac
    ;;
  branch)
    [ "$#" -eq 2 ] && [ "$2" = "--show-current" ] \
      || fail_unsupported "$@"
    # Release images are detached from a mutable branch name.
    ;;
  status)
    [ "$#" -eq 2 ] && [ "$2" = "--porcelain" ] || fail_unsupported "$@"
    ;;
  check-ignore)
    shift
    quiet=false
    case "${1:-}" in
      --quiet|-q)
        quiet=true
        shift
        ;;
    esac
    if [ "${1:-}" = "--" ]; then
      shift
    fi
    [ "$#" -gt 0 ] || fail_unsupported check-ignore
    [ -x "$system_git" ] && [ -d "$repository_root/.git" ] \
      || fail_unsupported check-ignore "$@"
    for path in "$@"; do
      validate_relative_path "$path"
    done
    if [ "$quiet" = true ]; then
      exec "$system_git" -C "$repository_root" check-ignore --quiet -- "$@"
    fi
    exec "$system_git" -C "$repository_root" check-ignore -- "$@"
    ;;
  *)
    fail_unsupported "$@"
    ;;
esac
