"""T-019 care history request and safe response serializers."""

from collections.abc import Mapping

from django.utils import timezone
from rest_framework import serializers

from apps.care.models import CareRecord


class RejectUnknownFieldsMixin:
    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown = sorted(set(data) - set(self.fields))
            if unknown:
                raise serializers.ValidationError(
                    {
                        field: ["지원하지 않는 필드입니다."]
                        for field in unknown
                    }
                )
        return super().to_internal_value(data)


class CareHistoryListQuerySerializer(serializers.Serializer):
    page = serializers.IntegerField(default=1, min_value=1)
    size = serializers.IntegerField(default=20, min_value=1, max_value=100)


class CareHistoryCreateSerializer(
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    care_type_code = serializers.ChoiceField(
        choices=(
            CareRecord.CareType.FILTER_REPLACEMENT,
            CareRecord.CareType.CLEANING,
        )
    )
    performed_on = serializers.DateField()

    def validate_performed_on(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError(
                "미래 날짜는 사용할 수 없습니다."
            )
        return value


class CareHistoryItemSerializer(serializers.Serializer):
    care_record_id = serializers.UUIDField()
    subscription_id = serializers.UUIDField()
    care_type_code = serializers.ChoiceField(
        choices=CareRecord.CareType.values
    )
    status_code = serializers.ChoiceField(
        choices=(CareRecord.Status.COMPLETED,)
    )
    performed_on = serializers.DateField()
    result_code = serializers.ChoiceField(
        choices=CareRecord.Result.values,
        allow_null=True,
    )
    source_code = serializers.ChoiceField(
        choices=CareRecord.Source.values
    )


class CareHistoryMutationResultSerializer(CareHistoryItemSerializer):
    idempotent_replay = serializers.BooleanField()


class CareHistoryListDataSerializer(serializers.Serializer):
    items = CareHistoryItemSerializer(many=True)
    page = serializers.IntegerField(min_value=1)
    size = serializers.IntegerField(min_value=1, max_value=100)
    total = serializers.IntegerField(min_value=0)
