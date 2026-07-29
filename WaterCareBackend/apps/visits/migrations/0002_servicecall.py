import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("visits", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceCall",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "customer_device_id",
                    models.CharField(
                        db_index=True,
                        max_length=80,
                    ),
                ),
                (
                    "customer_name",
                    models.CharField(max_length=80),
                ),
                (
                    "customer_phone",
                    models.CharField(max_length=30),
                ),
                (
                    "customer_address",
                    models.CharField(max_length=255),
                ),
                (
                    "customer_latitude",
                    models.DecimalField(
                        decimal_places=7,
                        max_digits=10,
                    ),
                ),
                (
                    "customer_longitude",
                    models.DecimalField(
                        decimal_places=7,
                        max_digits=10,
                    ),
                ),
                (
                    "product_name",
                    models.CharField(max_length=120),
                ),
                (
                    "product_model",
                    models.CharField(max_length=120),
                ),
                ("symptom", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            (
                                "REQUESTED",
                                "기사 수락 대기",
                            ),
                            ("ACCEPTED", "기사 수락"),
                            ("EN_ROUTE", "기사 이동 중"),
                            ("ARRIVED", "기사 도착"),
                            ("COMPLETED", "처리 완료"),
                            ("CANCELLED", "요청 취소"),
                        ],
                        db_index=True,
                        default="REQUESTED",
                        max_length=20,
                    ),
                ),
                (
                    "technician_device_id",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        max_length=80,
                        null=True,
                    ),
                ),
                (
                    "technician_name",
                    models.CharField(
                        blank=True,
                        max_length=80,
                        null=True,
                    ),
                ),
                (
                    "technician_latitude",
                    models.DecimalField(
                        blank=True,
                        decimal_places=7,
                        max_digits=10,
                        null=True,
                    ),
                ),
                (
                    "technician_longitude",
                    models.DecimalField(
                        blank=True,
                        decimal_places=7,
                        max_digits=10,
                        null=True,
                    ),
                ),
                (
                    "technician_accuracy_meters",
                    models.FloatField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "technician_speed_mps",
                    models.FloatField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "technician_heading",
                    models.FloatField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "technician_location_updated_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "result_type",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("NORMAL", "정상 처리"),
                            ("PART_REPLACED", "부품 교체"),
                            ("REVISIT", "재방문 필요"),
                        ],
                        max_length=30,
                        null=True,
                    ),
                ),
                ("diagnosis", models.TextField(blank=True)),
                ("action_taken", models.TextField(blank=True)),
                ("parts_used", models.TextField(blank=True)),
                ("customer_note", models.TextField(blank=True)),
                (
                    "follow_up_required",
                    models.BooleanField(default=False),
                ),
                (
                    "requested_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "accepted_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "departed_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "arrived_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "completed_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "cancelled_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
            ],
            options={
                "ordering": ("-requested_at",),
                "indexes": [
                    models.Index(
                        fields=[
                            "status",
                            "requested_at",
                        ],
                        name="svc_call_status_time_idx",
                    ),
                    models.Index(
                        fields=[
                            "technician_device_id",
                            "status",
                        ],
                        name="svc_call_tech_status_idx",
                    ),
                ],
            },
        ),
    ]
