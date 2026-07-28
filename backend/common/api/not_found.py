"""등록되지 않은 /api/v1 경로의 공통 404 응답."""

from django.http import JsonResponse

from common.api.response import build_error_payload
from common.exceptions.error_codes import RESOURCE_NOT_FOUND


def api_not_found(request, unmatched_path=None):
    return JsonResponse(
        build_error_payload(
            RESOURCE_NOT_FOUND,
            "요청한 대상을 찾을 수 없습니다.",
        ),
        status=404,
    )
