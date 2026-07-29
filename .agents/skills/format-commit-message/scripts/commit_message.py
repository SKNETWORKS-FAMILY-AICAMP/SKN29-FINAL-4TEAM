#!/usr/bin/env python3
"""Generate and validate WaterCare team commit messages."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone


SEOUL_TIMEZONE = timezone(timedelta(hours=9), name="Asia/Seoul")
MESSAGE_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2}) \| (?P<description>[^\r\n|]+)$"
)


def normalize_description(description: str) -> str:
    if "\r" in description or "\n" in description:
        raise ValueError("작업 내용은 한 줄이어야 합니다.")

    normalized = " ".join(description.split()).strip()
    if not normalized:
        raise ValueError("작업 내용이 비어 있습니다.")
    if "|" in normalized:
        raise ValueError("작업 내용에는 '|'를 사용할 수 없습니다.")
    if normalized.endswith("."):
        raise ValueError("작업 내용 끝에 마침표를 붙이지 마세요.")
    return normalized


def build_message(description: str) -> str:
    work_date = datetime.now(SEOUL_TIMEZONE).date().isoformat()
    return f"{work_date} | {normalize_description(description)}"


def validate_message(message: str) -> None:
    match = MESSAGE_PATTERN.fullmatch(message)
    if match is None:
        raise ValueError("형식은 'YYYY-MM-DD | 작업 내용' 한 줄이어야 합니다.")

    try:
        datetime.strptime(match.group("date"), "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("유효하지 않은 작업 일자입니다.") from exc

    normalize_description(match.group("description"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="팀 규칙에 맞는 커밋 메시지를 생성하거나 검증합니다."
    )
    parser.add_argument(
        "description",
        nargs="?",
        help="커밋에 담을 한국어 작업 내용",
    )
    parser.add_argument(
        "--check",
        metavar="MESSAGE",
        help="기존 커밋 메시지의 형식을 검증",
    )
    args = parser.parse_args()
    if (args.description is None) == (args.check is None):
        parser.error("작업 내용 또는 --check 중 하나만 입력하세요.")
    return args


def main() -> int:
    args = parse_args()
    try:
        if args.check is not None:
            validate_message(args.check)
            print(args.check)
        else:
            print(build_message(args.description))
    except ValueError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
