"""page·size·total 페이지네이션 응답 조립."""

from typing import Any


MIN_PAGE = 1
MIN_PAGE_SIZE = 1
MAX_PAGE_SIZE = 100
MIN_TOTAL = 0


def build_page_data(
    items: list[Any],
    *,
    page: int,
    size: int,
    total: int,
) -> dict[str, Any]:
    for name, value in (
        ("page", page),
        ("size", size),
        ("total", total),
    ):
        if type(value) is not int:
            raise ValueError(f"{name} must be an integer")

    if page < MIN_PAGE:
        raise ValueError(f"page must be at least {MIN_PAGE}")
    if not MIN_PAGE_SIZE <= size <= MAX_PAGE_SIZE:
        raise ValueError(
            f"size must be between {MIN_PAGE_SIZE} and {MAX_PAGE_SIZE}"
        )
    if total < MIN_TOTAL:
        raise ValueError(f"total must be at least {MIN_TOTAL}")

    return {
        "items": items,
        "page": page,
        "size": size,
        "total": total,
    }
