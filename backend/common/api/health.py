"""외부 세부 정보를 노출하지 않는 최소 Liveness Endpoint."""

from django.http import HttpResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny


@extend_schema(
    operation_id="getHealth",
    summary="서비스 생존 상태 확인",
    description=(
        "인증 없이 호출할 수 있는 liveness endpoint입니다. "
        "정상이면 빈 본문과 HTTP 200을 반환하며, 응답 헤더에 "
        "X-Correlation-ID가 포함됩니다."
    ),
    tags=["Health"],
    auth=[],
    responses={
        200: OpenApiResponse(
            description="서비스가 요청을 처리할 수 있는 상태입니다.",
        ),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """HealthDTO 계약 확정 전 임시 liveness로 200과 빈 본문만 반환한다."""

    return HttpResponse(status=200)
