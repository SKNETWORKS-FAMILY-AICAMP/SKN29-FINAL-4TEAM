"""공통 성공·오류 Wrapper 검증."""

import pytest

from common.api.pagination import (
    MAX_PAGE_SIZE,
    MIN_PAGE,
    MIN_PAGE_SIZE,
    MIN_TOTAL,
    build_page_data,
)
from common.api.response import (
    build_error_payload,
    build_success_payload,
    error_response,
    success_response,
)


def test_success_payload_uses_common_wrapper():
    assert build_success_payload({"id": "sample-id"}) == {
        "success": True,
        "data": {"id": "sample-id"},
        "error": None,
    }


def test_error_payload_uses_common_wrapper():
    assert build_error_payload(
        "INVALID_REQUEST",
        "요청 형식을 확인해 주세요.",
        {"field": ["필수 항목입니다."]},
    ) == {
        "success": False,
        "data": None,
        "error": {
            "code": "INVALID_REQUEST",
            "message": "요청 형식을 확인해 주세요.",
            "details": {"field": ["필수 항목입니다."]},
        },
    }


def test_page_data_uses_page_size_total_contract():
    assert build_page_data(
        [{"id": "DEMO-INQ-002"}],
        page=2,
        size=10,
        total=11,
    ) == {
        "items": [{"id": "DEMO-INQ-002"}],
        "page": 2,
        "size": 10,
        "total": 11,
    }


def test_page_data_accepts_confirmed_boundary_values():
    assert build_page_data(
        [],
        page=MIN_PAGE,
        size=MAX_PAGE_SIZE,
        total=MIN_TOTAL,
    ) == {
        "items": [],
        "page": 1,
        "size": 100,
        "total": 0,
    }


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {"page": MIN_PAGE - 1, "size": MIN_PAGE_SIZE, "total": 0},
            "page must be at least 1",
        ),
        (
            {"page": MIN_PAGE, "size": MIN_PAGE_SIZE - 1, "total": 0},
            "size must be between 1 and 100",
        ),
        (
            {"page": MIN_PAGE, "size": MAX_PAGE_SIZE + 1, "total": 0},
            "size must be between 1 and 100",
        ),
        (
            {"page": MIN_PAGE, "size": MIN_PAGE_SIZE, "total": -1},
            "total must be at least 0",
        ),
    ],
)
def test_page_data_rejects_values_outside_confirmed_contract(
    kwargs,
    message,
):
    with pytest.raises(ValueError, match=message):
        build_page_data([], **kwargs)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("page", 1.5),
        ("page", True),
        ("page", "1"),
        ("size", 10.5),
        ("size", False),
        ("size", "10"),
        ("total", 0.5),
        ("total", True),
        ("total", "0"),
    ],
)
def test_page_data_rejects_non_integer_contract_values(field, value):
    kwargs = {
        "page": MIN_PAGE,
        "size": MIN_PAGE_SIZE,
        "total": MIN_TOTAL,
    }
    kwargs[field] = value

    with pytest.raises(ValueError, match=rf"{field} must be an integer"):
        build_page_data([], **kwargs)


def test_success_response_preserves_status_payload_and_neutral_header():
    response = success_response(
        {"id": "DEMO-INQ-002"},
        status_code=201,
        headers={"X-Contract-Test": "confirmed"},
    )

    assert response.status_code == 201
    assert response.data == {
        "success": True,
        "data": {"id": "DEMO-INQ-002"},
        "error": None,
    }
    assert response["X-Contract-Test"] == "confirmed"


def test_error_response_normalizes_missing_details_to_empty_object():
    response = error_response(
        "INVALID_REQUEST",
        "요청 형식을 확인해 주세요.",
        status_code=400,
    )

    assert response.status_code == 400
    assert response.data == {
        "success": False,
        "data": None,
        "error": {
            "code": "INVALID_REQUEST",
            "message": "요청 형식을 확인해 주세요.",
            "details": {},
        },
    }
