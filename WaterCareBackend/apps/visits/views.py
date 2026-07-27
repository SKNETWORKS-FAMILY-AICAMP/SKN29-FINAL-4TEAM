from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .kakao_directions import (
    KakaoDirectionsError,
    get_driving_route,
)
from .models import TechnicianLocation, VisitRequest
from .serializers import (
    TechnicianLocationSerializer,
    VisitRequestSerializer,
)


class DrivingRouteView(APIView):
    """Android 앱에 실제 자동차 도로 경로 좌표를 반환한다."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        parameter_names = (
            "origin_lat",
            "origin_lng",
            "destination_lat",
            "destination_lng",
        )
        missing = [
            name
            for name in parameter_names
            if request.query_params.get(name) in (None, "")
        ]

        if missing:
            return Response(
                {
                    "detail": "필수 좌표가 누락되었습니다.",
                    "missing": missing,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            route = get_driving_route(
                origin_lat=float(
                    request.query_params["origin_lat"]
                ),
                origin_lng=float(
                    request.query_params["origin_lng"]
                ),
                destination_lat=float(
                    request.query_params["destination_lat"]
                ),
                destination_lng=float(
                    request.query_params["destination_lng"]
                ),
            )
        except ValueError:
            return Response(
                {
                    "detail": "위도와 경도는 숫자로 입력해야 합니다."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except KakaoDirectionsError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(route, status=status.HTTP_200_OK)


class VisitRequestViewSet(viewsets.ModelViewSet):
    serializer_class = VisitRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.role == "CUSTOMER":
            return VisitRequest.objects.filter(
                inquiry__customer=user
            )
        if user.role == "TECHNICIAN":
            return VisitRequest.objects.filter(
                technician=user
            )
        return VisitRequest.objects.all()

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        visit = self.get_object()
        self._require_assigned_technician(request, visit)

        if visit.status != VisitRequest.Status.CONFIRMED:
            return Response(
                {
                    "detail":
                        "방문 확정 상태에서만 콜을 수락할 수 있습니다."
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "visit_id": str(visit.id),
                "status": visit.status,
                "accepted": True,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def depart(self, request, pk=None):
        visit = self.get_object()
        self._require_assigned_technician(request, visit)

        if visit.status != VisitRequest.Status.CONFIRMED:
            return Response(
                {
                    "detail":
                        "방문 확정 상태에서만 출발할 수 있습니다."
                },
                status=status.HTTP_409_CONFLICT,
            )

        visit.status = VisitRequest.Status.EN_ROUTE
        visit.departed_at = timezone.now()
        visit.save(
            update_fields=("status", "departed_at")
        )
        return Response(self.get_serializer(visit).data)

    @action(detail=True, methods=["post"])
    def location(self, request, pk=None):
        visit = self.get_object()
        self._require_assigned_technician(request, visit)

        if visit.status != VisitRequest.Status.EN_ROUTE:
            return Response(
                {
                    "detail":
                        "이동 중 상태에서만 위치를 전송할 수 있습니다."
                },
                status=status.HTTP_409_CONFLICT,
            )

        serializer = TechnicianLocationSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        latest = visit.locations.order_by(
            "-recorded_at"
        ).first()

        if latest:
            elapsed = (
                timezone.now() - latest.recorded_at
            ).total_seconds()

            if elapsed < 1:
                return Response(
                    {
                        "detail":
                            "위치 전송 간격이 너무 짧습니다."
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

        item = serializer.save(visit=visit)

        # 방문별 최근 위치 이력이 과도하게 쌓이지 않도록
        # 최근 500개를 제외한 오래된 좌표는 정리한다.
        old_location_ids = list(
            visit.locations.order_by(
                "-recorded_at"
            ).values_list("id", flat=True)[500:]
        )
        if old_location_ids:
            TechnicianLocation.objects.filter(
                id__in=old_location_ids
            ).delete()

        return Response(
            TechnicianLocationSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"])
    def tracking(self, request, pk=None):
        visit = self.get_object()
        return Response(
            self.get_serializer(visit).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        visit = self.get_object()
        self._require_assigned_technician(request, visit)

        if visit.status != VisitRequest.Status.EN_ROUTE:
            return Response(
                {
                    "detail":
                        "이동 중 상태에서만 점검을 시작할 수 있습니다."
                },
                status=status.HTTP_409_CONFLICT,
            )

        visit.status = VisitRequest.Status.IN_PROGRESS
        visit.started_at = timezone.now()
        visit.save(
            update_fields=("status", "started_at")
        )
        return Response(self.get_serializer(visit).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        visit = self.get_object()
        self._require_assigned_technician(request, visit)

        if visit.status != VisitRequest.Status.IN_PROGRESS:
            return Response(
                {
                    "detail":
                        "점검 중 상태에서만 완료할 수 있습니다."
                },
                status=status.HTTP_409_CONFLICT,
            )

        visit.status = VisitRequest.Status.COMPLETED
        visit.completed_at = timezone.now()
        visit.save(
            update_fields=("status", "completed_at")
        )

        visit.inquiry.state = "COMPLETION_PENDING"
        visit.inquiry.save(update_fields=("state",))

        return Response(self.get_serializer(visit).data)

    @staticmethod
    def _require_assigned_technician(request, visit):
        user = request.user

        if getattr(user, "role", None) != "TECHNICIAN":
            raise PermissionDenied(
                "방문기사 계정만 수행할 수 있습니다."
            )

        if visit.technician_id != user.id:
            raise PermissionDenied(
                "배정된 방문기사만 수행할 수 있습니다."
            )
