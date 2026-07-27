"""외부 세부 정보를 노출하지 않는 최소 Liveness Endpoint."""

from django.http import HttpResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request):
    """HealthDTO 계약 확정 전 임시 liveness로 200과 빈 본문만 반환한다."""

    return HttpResponse(status=200)
