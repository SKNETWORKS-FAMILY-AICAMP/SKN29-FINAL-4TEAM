from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .kakao_directions import (
    KakaoDirectionsError,
    get_driving_route,
)
from .models import (
    ServiceCall,
    TechnicianLocation,
    VisitRequest,
)
from .serializers import (
    ServiceCallAcceptSerializer,
    ServiceCallCompleteSerializer,
    ServiceCallCustomerActionSerializer,
    ServiceCallLocationUpdateSerializer,
    ServiceCallSerializer,
    ServiceCallTechnicianActionSerializer,
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


class ServiceCallViewSet(viewsets.ModelViewSet):
    """고객 호출 요청과 방문기사 수락·이동을 실제 DB로 동기화한다."""

    queryset = ServiceCall.objects.all()
    serializer_class = ServiceCallSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    http_method_names = (
        "get",
        "post",
        "head",
        "options",
    )

    def get_queryset(self):
        queryset = ServiceCall.objects.all()
        scope = self.request.query_params.get("scope")
        customer_device_id = self.request.query_params.get(
            "customer_device_id"
        )
        technician_device_id = self.request.query_params.get(
            "technician_device_id"
        )

        if scope == "pending":
            queryset = queryset.filter(
                status=ServiceCall.Status.REQUESTED
            )

        if customer_device_id:
            queryset = queryset.filter(
                customer_device_id=customer_device_id
            )

        if technician_device_id:
            queryset = queryset.filter(
                technician_device_id=technician_device_id
            )

        return queryset.order_by("-requested_at")

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        serializer = ServiceCallAcceptSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        accepted_at = timezone.now()
        updated = ServiceCall.objects.filter(
            pk=pk,
            status=ServiceCall.Status.REQUESTED,
        ).update(
            technician_device_id=serializer.validated_data[
                "technician_device_id"
            ],
            technician_name=serializer.validated_data[
                "technician_name"
            ],
            status=ServiceCall.Status.ACCEPTED,
            accepted_at=accepted_at,
            updated_at=accepted_at,
        )

        if updated != 1:
            call = self.get_object()
            return Response(
                {
                    "detail":
                        "이미 다른 기사가 수락했거나 처리 중인 콜입니다.",
                    "status": call.status,
                },
                status=status.HTTP_409_CONFLICT,
            )

        call = ServiceCall.objects.get(pk=pk)
        return Response(
            ServiceCallSerializer(call).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def depart(self, request, pk=None):
        call = self.get_object()
        self._validate_technician(request, call)

        if call.status != ServiceCall.Status.ACCEPTED:
            return self._status_conflict(
                call,
                "기사 수락 상태에서만 출발할 수 있습니다.",
            )

        call.status = ServiceCall.Status.EN_ROUTE
        call.departed_at = timezone.now()
        call.save(
            update_fields=(
                "status",
                "departed_at",
                "updated_at",
            )
        )
        return Response(ServiceCallSerializer(call).data)

    @action(detail=True, methods=["post"])
    def location(self, request, pk=None):
        call = self.get_object()
        serializer = ServiceCallLocationUpdateSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        self._require_technician_device(
            call,
            serializer.validated_data[
                "technician_device_id"
            ],
        )

        if call.status != ServiceCall.Status.EN_ROUTE:
            return self._status_conflict(
                call,
                "이동 중 상태에서만 위치를 전송할 수 있습니다.",
            )

        now = timezone.now()
        if call.technician_location_updated_at:
            elapsed = (
                now - call.technician_location_updated_at
            ).total_seconds()
            if elapsed < 1:
                return Response(
                    {"detail": "위치 전송 간격이 너무 짧습니다."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

        data = serializer.validated_data
        call.technician_latitude = data["latitude"]
        call.technician_longitude = data["longitude"]
        call.technician_accuracy_meters = data.get(
            "accuracy_meters"
        )
        call.technician_speed_mps = data.get("speed_mps")
        call.technician_heading = data.get("heading")
        call.technician_location_updated_at = now
        call.save(
            update_fields=(
                "technician_latitude",
                "technician_longitude",
                "technician_accuracy_meters",
                "technician_speed_mps",
                "technician_heading",
                "technician_location_updated_at",
                "updated_at",
            )
        )
        return Response(
            ServiceCallSerializer(call).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def arrive(self, request, pk=None):
        call = self.get_object()
        self._validate_technician(request, call)

        if call.status != ServiceCall.Status.EN_ROUTE:
            return self._status_conflict(
                call,
                "이동 중 상태에서만 도착 처리할 수 있습니다.",
            )

        call.status = ServiceCall.Status.ARRIVED
        call.arrived_at = timezone.now()
        call.save(
            update_fields=(
                "status",
                "arrived_at",
                "updated_at",
            )
        )
        return Response(ServiceCallSerializer(call).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        call = self.get_object()
        serializer = ServiceCallCompleteSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        self._require_technician_device(
            call,
            serializer.validated_data[
                "technician_device_id"
            ],
        )

        if call.status != ServiceCall.Status.ARRIVED:
            return self._status_conflict(
                call,
                "기사 도착 상태에서만 처리를 완료할 수 있습니다.",
            )

        data = serializer.validated_data
        call.status = ServiceCall.Status.COMPLETED
        call.result_type = data["result_type"]
        call.diagnosis = data["diagnosis"]
        call.action_taken = data["action_taken"]
        call.parts_used = data.get("parts_used", "")
        call.customer_note = data.get("customer_note", "")
        call.follow_up_required = data.get(
            "follow_up_required",
            False,
        )
        call.completed_at = timezone.now()
        call.save(
            update_fields=(
                "status",
                "result_type",
                "diagnosis",
                "action_taken",
                "parts_used",
                "customer_note",
                "follow_up_required",
                "completed_at",
                "updated_at",
            )
        )
        return Response(ServiceCallSerializer(call).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        call = self.get_object()
        serializer = ServiceCallCustomerActionSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        if (
            serializer.validated_data["customer_device_id"]
            != call.customer_device_id
        ):
            raise PermissionDenied(
                "요청을 등록한 고객 기기만 취소할 수 있습니다."
            )

        if call.status not in (
            ServiceCall.Status.REQUESTED,
            ServiceCall.Status.ACCEPTED,
        ):
            return self._status_conflict(
                call,
                "기사 이동이 시작된 뒤에는 앱에서 취소할 수 없습니다.",
            )

        call.status = ServiceCall.Status.CANCELLED
        call.cancelled_at = timezone.now()
        call.save(
            update_fields=(
                "status",
                "cancelled_at",
                "updated_at",
            )
        )
        return Response(ServiceCallSerializer(call).data)

    @staticmethod
    def _validate_technician(request, call):
        serializer = ServiceCallTechnicianActionSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        ServiceCallViewSet._require_technician_device(
            call,
            serializer.validated_data["technician_device_id"],
        )

    @staticmethod
    def _require_technician_device(call, technician_device_id):
        if (
            not call.technician_device_id
            or call.technician_device_id
            != technician_device_id
        ):
            raise PermissionDenied(
                "콜을 수락한 방문기사 기기만 처리할 수 있습니다."
            )

    @staticmethod
    def _status_conflict(call, detail):
        return Response(
            {
                "detail": detail,
                "status": call.status,
            },
            status=status.HTTP_409_CONFLICT,
        )


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
