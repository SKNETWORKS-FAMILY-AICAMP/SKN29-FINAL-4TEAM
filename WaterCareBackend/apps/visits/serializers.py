from django.utils import timezone
from rest_framework import serializers

from .models import TechnicianLocation, VisitRequest


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
