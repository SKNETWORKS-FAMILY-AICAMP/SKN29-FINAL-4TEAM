import math

from django.utils import timezone
from rest_framework import serializers

from .models import (
    ServiceCall,
    TechnicianLocation,
    VisitRequest,
)


class TechnicianLocationSerializer(serializers.ModelSerializer):
    recorded_at_epoch_millis = serializers.SerializerMethodField()

    class Meta:
        model = TechnicianLocation
        fields = (
            "latitude",
            "longitude",
            "accuracy_meters",
            "speed_mps",
            "heading",
            "recorded_at",
            "recorded_at_epoch_millis",
        )
        read_only_fields = (
            "recorded_at",
            "recorded_at_epoch_millis",
        )

    def get_recorded_at_epoch_millis(self, obj):
        return int(obj.recorded_at.timestamp() * 1000)

    def validate_accuracy_meters(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "GPS 정확도는 0 이상이어야 합니다."
            )
        if value is not None and value > 200:
            raise serializers.ValidationError(
                "GPS 정확도가 너무 낮아 위치를 저장할 수 없습니다."
            )
        return value

    def validate_heading(self, value):
        if value is None:
            return value
        return value % 360


class VisitRequestSerializer(serializers.ModelSerializer):
    latest_location = serializers.SerializerMethodField()
    location_age_seconds = serializers.SerializerMethodField()
    tracking_connection_state = serializers.SerializerMethodField()

    class Meta:
        model = VisitRequest
        fields = (
            "id",
            "inquiry",
            "technician",
            "customer_address",
            "customer_latitude",
            "customer_longitude",
            "scheduled_at",
            "status",
            "departed_at",
            "started_at",
            "completed_at",
            "latest_location",
            "location_age_seconds",
            "tracking_connection_state",
        )
        read_only_fields = (
            "status",
            "departed_at",
            "started_at",
            "completed_at",
            "latest_location",
            "location_age_seconds",
            "tracking_connection_state",
        )

    def get_latest_location(self, obj):
        item = obj.locations.order_by("-recorded_at").first()
        return (
            TechnicianLocationSerializer(item).data
            if item
            else None
        )

    def get_location_age_seconds(self, obj):
        item = obj.locations.order_by("-recorded_at").first()
        if not item:
            return None

        age = timezone.now() - item.recorded_at
        return max(0, int(age.total_seconds()))

    def get_tracking_connection_state(self, obj):
        age_seconds = self.get_location_age_seconds(obj)

        if age_seconds is None:
            return "CONNECTING"
        if age_seconds >= 60:
            return "OFFLINE"
        if age_seconds >= 15:
            return "STALE"
        return "LIVE"


class ServiceCallSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )
    result_type_label = serializers.CharField(
        source="get_result_type_display",
        read_only=True,
    )
    location_age_seconds = serializers.SerializerMethodField()
    tracking_connection_state = serializers.SerializerMethodField()
    distance_meters = serializers.SerializerMethodField()
    eta_minutes = serializers.SerializerMethodField()

    class Meta:
        model = ServiceCall
        fields = (
            "id",
            "customer_device_id",
            "customer_name",
            "customer_phone",
            "customer_address",
            "customer_latitude",
            "customer_longitude",
            "product_name",
            "product_model",
            "symptom",
            "status",
            "status_label",
            "technician_device_id",
            "technician_name",
            "technician_latitude",
            "technician_longitude",
            "technician_accuracy_meters",
            "technician_speed_mps",
            "technician_heading",
            "technician_location_updated_at",
            "tracking_connection_state",
            "location_age_seconds",
            "distance_meters",
            "eta_minutes",
            "result_type",
            "result_type_label",
            "diagnosis",
            "action_taken",
            "parts_used",
            "customer_note",
            "follow_up_required",
            "requested_at",
            "accepted_at",
            "departed_at",
            "arrived_at",
            "completed_at",
            "cancelled_at",
            "updated_at",
        )
        read_only_fields = (
            "status",
            "status_label",
            "technician_device_id",
            "technician_name",
            "technician_latitude",
            "technician_longitude",
            "technician_accuracy_meters",
            "technician_speed_mps",
            "technician_heading",
            "technician_location_updated_at",
            "tracking_connection_state",
            "location_age_seconds",
            "distance_meters",
            "eta_minutes",
            "result_type",
            "result_type_label",
            "diagnosis",
            "action_taken",
            "parts_used",
            "customer_note",
            "follow_up_required",
            "requested_at",
            "accepted_at",
            "departed_at",
            "arrived_at",
            "completed_at",
            "cancelled_at",
            "updated_at",
        )

    def validate_customer_latitude(self, value):
        if not -90 <= float(value) <= 90:
            raise serializers.ValidationError(
                "위도는 -90부터 90 사이여야 합니다."
            )
        return value

    def validate_customer_longitude(self, value):
        if not -180 <= float(value) <= 180:
            raise serializers.ValidationError(
                "경도는 -180부터 180 사이여야 합니다."
            )
        return value

    def get_location_age_seconds(self, obj):
        if not obj.technician_location_updated_at:
            return None
        age = timezone.now() - obj.technician_location_updated_at
        return max(0, int(age.total_seconds()))

    def get_tracking_connection_state(self, obj):
        age = self.get_location_age_seconds(obj)
        if age is None:
            return "CONNECTING"
        if age >= 60:
            return "OFFLINE"
        if age >= 15:
            return "STALE"
        return "LIVE"

    def get_distance_meters(self, obj):
        if (
            obj.technician_latitude is None
            or obj.technician_longitude is None
        ):
            return None

        return round(
            _haversine_meters(
                float(obj.technician_latitude),
                float(obj.technician_longitude),
                float(obj.customer_latitude),
                float(obj.customer_longitude),
            )
        )

    def get_eta_minutes(self, obj):
        distance = self.get_distance_meters(obj)
        if distance is None:
            return None

        reported_speed = obj.technician_speed_mps or 0
        practical_speed = max(float(reported_speed), 8.33)
        return max(1, math.ceil(distance / practical_speed / 60))


class ServiceCallAcceptSerializer(serializers.Serializer):
    technician_device_id = serializers.CharField(max_length=80)
    technician_name = serializers.CharField(max_length=80)


class ServiceCallTechnicianActionSerializer(serializers.Serializer):
    technician_device_id = serializers.CharField(max_length=80)


class ServiceCallCustomerActionSerializer(serializers.Serializer):
    customer_device_id = serializers.CharField(max_length=80)


class ServiceCallLocationUpdateSerializer(serializers.Serializer):
    technician_device_id = serializers.CharField(max_length=80)
    latitude = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
    )
    longitude = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
    )
    accuracy_meters = serializers.FloatField(
        required=False,
        allow_null=True,
        min_value=0,
        max_value=200,
    )
    speed_mps = serializers.FloatField(
        required=False,
        allow_null=True,
        min_value=0,
    )
    heading = serializers.FloatField(
        required=False,
        allow_null=True,
    )

    def validate_latitude(self, value):
        if not -90 <= float(value) <= 90:
            raise serializers.ValidationError(
                "위도는 -90부터 90 사이여야 합니다."
            )
        return value

    def validate_longitude(self, value):
        if not -180 <= float(value) <= 180:
            raise serializers.ValidationError(
                "경도는 -180부터 180 사이여야 합니다."
            )
        return value

    def validate_heading(self, value):
        if value is None:
            return value
        return value % 360


class ServiceCallCompleteSerializer(
    ServiceCallTechnicianActionSerializer
):
    result_type = serializers.ChoiceField(
        choices=ServiceCall.ResultType.choices
    )
    diagnosis = serializers.CharField()
    action_taken = serializers.CharField()
    parts_used = serializers.CharField(
        required=False,
        allow_blank=True,
    )
    customer_note = serializers.CharField(
        required=False,
        allow_blank=True,
    )
    follow_up_required = serializers.BooleanField(
        required=False,
        default=False,
    )


def _haversine_meters(
    start_lat,
    start_lng,
    end_lat,
    end_lng,
):
    earth_radius = 6_371_000.0
    lat_delta = math.radians(end_lat - start_lat)
    lng_delta = math.radians(end_lng - start_lng)
    start_latitude = math.radians(start_lat)
    end_latitude = math.radians(end_lat)

    value = (
        math.sin(lat_delta / 2) ** 2
        + math.cos(start_latitude)
        * math.cos(end_latitude)
        * math.sin(lng_delta / 2) ** 2
    )
    return earth_radius * 2 * math.asin(
        math.sqrt(min(1.0, max(0.0, value)))
    )
