# Generated for the isolated AI reference-scenario catalogue.

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ReferenceScenario",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.BigAutoField(primary_key=True, serialize=False),
                ),
                (
                    "public_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                    ),
                ),
                ("scenario_id", models.CharField(max_length=64)),
                ("catalog_version", models.CharField(max_length=40)),
                ("exact_model_code", models.CharField(max_length=40)),
                ("model_family", models.CharField(max_length=40)),
                (
                    "risk_level",
                    models.CharField(
                        choices=[
                            ("general", "General"),
                            ("caution", "Caution"),
                            ("danger", "Danger"),
                        ],
                        max_length=20,
                    ),
                ),
                ("title", models.CharField(max_length=180)),
                ("customer_utterance", models.TextField()),
                ("topic_code", models.CharField(max_length=80)),
                ("context_facts", models.JSONField(default=list)),
                ("source_document_id", models.CharField(max_length=100)),
                (
                    "source_policy",
                    models.CharField(
                        choices=[
                            (
                                "MVP_SOURCE_REFERENCE",
                                "MVP source reference",
                            ),
                            (
                                "EXPANSION_REFERENCE_ONLY",
                                "Expansion reference only",
                            ),
                        ],
                        max_length=30,
                    ),
                ),
                ("manual_page_refs", models.JSONField(default=list)),
                (
                    "evidence_group_ids",
                    models.JSONField(blank=True, default=list),
                ),
                (
                    "evidence_readiness",
                    models.CharField(
                        choices=[
                            (
                                "SCENARIO_GROUP_VERIFIED",
                                "Scenario evidence group verified",
                            ),
                            (
                                "TOPIC_GROUP_SELECTION_PENDING",
                                "Topic group needs scenario selection",
                            ),
                            (
                                "SOURCE_PAGE_ONLY",
                                "Verified source page only",
                            ),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "expected_route",
                    models.CharField(
                        choices=[
                            ("AI_GUIDANCE", "AI guidance"),
                            ("HUMAN_REVIEW", "Human review"),
                            (
                                "EMERGENCY_ESCALATION",
                                "Emergency escalation",
                            ),
                        ],
                        max_length=30,
                    ),
                ),
                ("expected_requires_consultation", models.BooleanField()),
                (
                    "expected_publication_gate",
                    models.CharField(
                        choices=[
                            (
                                "AUTO_GUIDANCE_ELIGIBLE",
                                "Auto guidance eligible",
                            ),
                            (
                                "HUMAN_APPROVAL_REQUIRED",
                                "Human approval required",
                            ),
                            (
                                "SAFETY_ESCALATION_ONLY",
                                "Safety escalation only",
                            ),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "expected_usage_guidance_status",
                    models.CharField(
                        choices=[
                            ("NORMAL", "Normal"),
                            ("PARTIAL_STOP", "Partial stop"),
                            ("TOTAL_STOP", "Total stop"),
                        ],
                        max_length=30,
                    ),
                ),
                ("expected_reason", models.TextField()),
                ("response_outline", models.JSONField(default=list)),
                (
                    "runtime_use",
                    models.CharField(
                        choices=[("REFERENCE_ONLY", "Reference only")],
                        default="REFERENCE_ONLY",
                        max_length=20,
                    ),
                ),
                (
                    "training_use",
                    models.CharField(
                        choices=[("PROHIBITED", "Prohibited")],
                        default="PROHIBITED",
                        max_length=20,
                    ),
                ),
                (
                    "curation_status",
                    models.CharField(
                        choices=[("CANDIDATE", "Candidate")],
                        default="CANDIDATE",
                        max_length=20,
                    ),
                ),
                ("is_runtime_enabled", models.BooleanField(default=False)),
                (
                    "data_classification",
                    models.CharField(default="synthetic", max_length=20),
                ),
                ("source_record_sha256", models.CharField(max_length=64)),
                ("source_catalog_sha256", models.CharField(max_length=64)),
            ],
            options={
                "db_table": "ai_reference_scenario",
                "indexes": [
                    models.Index(
                        fields=[
                            "catalog_version",
                            "exact_model_code",
                            "risk_level",
                        ],
                        name="ix_ref_scenario_matrix",
                    ),
                    models.Index(
                        fields=["runtime_use", "is_runtime_enabled"],
                        name="ix_ref_scenario_runtime",
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            exact_model_code__in=[
                                "WPUJAC104DWH",
                                "WPUIAC425SNW",
                                "WPUIAC606SNW",
                            ]
                        ),
                        name="ck_ref_scenario_model_code",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            risk_level__in=["general", "caution", "danger"]
                        ),
                        name="ck_ref_scenario_risk",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            curation_status="CANDIDATE",
                            data_classification="synthetic",
                            is_runtime_enabled=False,
                            runtime_use="REFERENCE_ONLY",
                            training_use="PROHIBITED",
                        ),
                        name="ck_ref_scenario_nonruntime",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(
                                expected_publication_gate=(
                                    "AUTO_GUIDANCE_ELIGIBLE"
                                ),
                                expected_requires_consultation=False,
                                expected_route="AI_GUIDANCE",
                                expected_usage_guidance_status="NORMAL",
                                risk_level="general",
                            )
                            | models.Q(
                                expected_publication_gate=(
                                    "HUMAN_APPROVAL_REQUIRED"
                                ),
                                expected_route="HUMAN_REVIEW",
                                expected_usage_guidance_status="PARTIAL_STOP",
                                risk_level="caution",
                            )
                            | models.Q(
                                expected_publication_gate=(
                                    "SAFETY_ESCALATION_ONLY"
                                ),
                                expected_requires_consultation=True,
                                expected_route="EMERGENCY_ESCALATION",
                                expected_usage_guidance_status="TOTAL_STOP",
                                risk_level="danger",
                            )
                        ),
                        name="ck_ref_scenario_release_oracle",
                    ),
                    models.UniqueConstraint(
                        fields=("catalog_version", "scenario_id"),
                        name="uq_ref_scenario_version_id",
                    ),
                ],
            },
        ),
    ]
