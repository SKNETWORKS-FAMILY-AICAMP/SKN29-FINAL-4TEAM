"""Backend-owned durable consultation-cause ledger."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.common_codes.db_expressions import IsJSONArray, IsJSONObject
from common.json_integrity import canonical_json_sha256
from common.models.base import TimestampedModel


class ConsultationCauseLedger(TimestampedModel):
    """Persist one validated internal cause Ledger for one AI analysis run."""

    id = models.BigAutoField(primary_key=True)
    ledger_id = models.UUIDField(unique=True, editable=False)
    inquiry = models.ForeignKey(
        "inquiries.Inquiry",
        on_delete=models.PROTECT,
        related_name="consultation_cause_ledgers",
        db_column="inquiry_id",
        db_index=False,
    )
    ai_run = models.OneToOneField(
        "audit.AIRun",
        on_delete=models.PROTECT,
        related_name="consultation_cause_ledger",
        db_column="ai_run_id",
    )
    contract_version = models.CharField(max_length=20)
    correlation_id = models.UUIDField()
    ai_request_id = models.CharField(max_length=100)
    source_inquiry_state_version = models.PositiveIntegerField()
    model_code = models.CharField(max_length=100)
    producer = models.CharField(max_length=40)
    policy_version = models.CharField(max_length=100)
    execution_identity = models.JSONField(default=dict)
    analysis_result_sha256 = models.CharField(max_length=64)
    causes = models.JSONField(default=list, blank=True)
    ledger_sha256 = models.CharField(max_length=64)

    class Meta:
        db_table = "support_consultation_cause_ledger"
        constraints = [
            models.UniqueConstraint(
                fields=["inquiry", "ai_request_id"],
                name="ux_ccledger_inquiry_request",
            ),
            models.CheckConstraint(
                condition=Q(contract_version="1.0.0"),
                name="ck_ccledger_contract_v1",
            ),
            models.CheckConstraint(
                condition=Q(producer="AI_HARNESS"),
                name="ck_ccledger_producer",
            ),
            models.CheckConstraint(
                condition=Q(source_inquiry_state_version__gt=0),
                name="ck_ccledger_state_version",
            ),
            models.CheckConstraint(
                condition=IsJSONObject(F("execution_identity")),
                name="ck_ccledger_execution_object",
            ),
            models.CheckConstraint(
                condition=IsJSONArray(F("causes")),
                name="ck_ccledger_causes_array",
            ),
            models.CheckConstraint(
                condition=Q(
                    analysis_result_sha256__regex=r"^[0-9a-f]{64}$"
                ),
                name="ck_ccledger_analysis_hash",
            ),
            models.CheckConstraint(
                condition=Q(ledger_sha256__regex=r"^[0-9a-f]{64}$"),
                name="ck_ccledger_ledger_hash",
            ),
        ]
        indexes = [
            models.Index(
                fields=["inquiry", "-created_at"],
                name="ix_ccledger_inquiry_created",
            ),
            models.Index(
                fields=["model_code", "-created_at"],
                name="ix_ccledger_model_created",
            ),
        ]

    def clean(self) -> None:
        """Validate cross-row identity and canonical hashes before storage."""

        super().clean()
        errors: dict[str, str] = {}
        if not isinstance(self.execution_identity, dict):
            errors["execution_identity"] = "execution_identity must be an object."
        if not isinstance(self.causes, list) or any(
            not isinstance(cause, dict) for cause in self.causes
        ):
            errors["causes"] = "causes must be an array of objects."

        run = self.ai_run if self.ai_run_id is not None else None
        if run is not None:
            if self.inquiry_id != run.inquiry_id:
                errors["inquiry"] = "Ledger and AI run must belong to one inquiry."
            if str(self.correlation_id) != str(run.correlation_id):
                errors["correlation_id"] = "Ledger correlation ID differs from the AI run."
            if self.ai_request_id != run.idempotency_key:
                errors["ai_request_id"] = "Ledger request ID differs from the AI run."

            request_payload = run.input_payload
            if not isinstance(request_payload, dict):
                errors["ai_run"] = "AI run request payload is unavailable."
            else:
                if self.source_inquiry_state_version != request_payload.get(
                    "state_version"
                ):
                    errors["source_inquiry_state_version"] = (
                        "Ledger state version differs from the AI request."
                    )
                if self.model_code != request_payload.get("model_code"):
                    errors["model_code"] = "Ledger model differs from the AI request."

            analysis = run.validated_output_payload
            if not isinstance(analysis, dict):
                errors["ai_run"] = "Validated analysis result is unavailable."
            else:
                expected_analysis_hash = canonical_json_sha256(analysis)
                if self.analysis_result_sha256 != expected_analysis_hash:
                    errors["analysis_result_sha256"] = (
                        "Analysis result hash differs from the stored AI result."
                    )
                requires_consultation = bool(
                    analysis.get("safety_assessment", {}).get(
                        "requires_consultation"
                    )
                )
                if requires_consultation != bool(self.causes):
                    errors["causes"] = (
                        "Ledger causes differ from consultation authority."
                    )

        if not errors and self.inquiry_id is not None:
            ledger_payload = {
                "contract_version": self.contract_version,
                "ledger_id": str(self.ledger_id),
                "inquiry_id": str(self.inquiry.public_id),
                "correlation_id": str(self.correlation_id),
                "ai_request_id": self.ai_request_id,
                "state_version": self.source_inquiry_state_version,
                "model_code": self.model_code,
                "producer": self.producer,
                "policy_version": self.policy_version,
                "execution_identity": self.execution_identity,
                "analysis_result_sha256": self.analysis_result_sha256,
                "causes": self.causes,
            }
            if self.ledger_sha256 != canonical_json_sha256(ledger_payload):
                errors["ledger_sha256"] = (
                    "Ledger hash differs from the canonical stored fields."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.ledger_id} ({self.model_code})"
