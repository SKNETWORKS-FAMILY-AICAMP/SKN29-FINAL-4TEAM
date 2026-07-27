#!/usr/bin/env python
"""Django 관리 명령 실행 진입점."""

import os
import sys

from config.env import load_backend_env, requested_settings_module


def main() -> None:
    load_backend_env(
        settings_module=requested_settings_module(sys.argv),
    )
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django를 불러올 수 없습니다. requirements/local.txt 설치 여부를 확인하세요."
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
