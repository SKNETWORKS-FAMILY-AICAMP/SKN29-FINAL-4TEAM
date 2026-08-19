"""Official transactional importer for the canonical synthetic handoff."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from django.db import transaction

from apps.accounts.models import CustomerProfile, User
from apps.audit.models import AuditEvent
from apps.care.models import CareRecord
from apps.consultations.models import Consultation
from apps.inquiries.models import (
    FollowupConfirmation,
    Inquiry,
    SymptomEntry,
)
from apps.operations.models import SyntheticImportItem
from apps.operations.repositories import (
    LedgerItem,
    PersistResult,
    SyntheticImportConflict,
    SyntheticImportRepository,
)
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.visits.models import Visit
from apps.workflow.models import TransitionHistory


DATASET_ORDER = (
    "users",
    "customer_profiles",
    "products",
    "customer_products",
    "subscriptions",
    "inquiries",
    "consultations",
    "visits",
    "followup_confirmations",
    "care_histories",
    "inquiry_status_histories",
    "audit_events",
)
EXPECTED_FULL_COUNTS = {
    "users": 16,
    "customer_profiles": 12,
    "products": 1,
    "customer_products": 12,
    "subscriptions": 12,
    "inquiries": 22,
    "consultations": 12,
    "visits": 4,
    "followup_confirmations": 1,
    "care_histories": 25,
    "inquiry_status_histories": 125,
    "audit_events": 125,
}
# The physical fixture package also carries two contract-blocked products for
# Data/RAG lineage. Database handoff profiles still select only the product
# referenced by their CustomerProduct closure.
EXPECTED_FIXTURE_COUNTS = {
    **EXPECTED_FULL_COUNTS,
    "products": 3,
}
EXPECTED_SMOKE_COUNTS = {
    "users": 8,
    "customer_profiles": 6,
    "products": 1,
    "customer_products": 6,
    "subscriptions": 6,
    "inquiries": 6,
    "consultations": 3,
    "visits": 1,
    "followup_confirmations": 0,
    "care_histories": 0,
    "inquiry_status_histories": 0,
    "audit_events": 0,
}
EXPECTED_SOURCE_COUNTS = {"db-smoke": 37, "db-full": 367}
SMOKE_SCENARIOS = {
    f"SYN-JAC104-{sequence:03d}" for sequence in range(1, 7)
}
PLAN_CODE_MAP = {"SYNTHETIC_REGULAR_CARE": "VISIT_CARE"}
CARE_TYPE_MAP = {
    "REGULAR_INSPECTION": "PERIODIC_CHECK",
    "FILTER_REPLACEMENT": "FILTER_REPLACEMENT",
    "VISIT_SERVICE": "VISIT_SERVICE",
}
BUSINESS_KEY_FIELDS = {
    "users": "user_number",
    "customer_profiles": "customer_profile_number",
    "products": "product_code",
    "customer_products": "serial_number",
    "subscriptions": "subscription_number",
    "inquiries": "inquiry_number",
    "consultations": "consultation_number",
    "visits": "visit_number",
    "followup_confirmations": "followup_number",
    "care_histories": "care_history_number",
    "inquiry_status_histories": "status_history_number",
    "audit_events": "audit_record_number",
}


@dataclass(frozen=True)
class SyntheticImportResult:
    """Serializable result from one smoke, full, or dry-run execution."""

    profile: str
    dry_run: bool
    dataset_version: str
    mapping_version: str
    fixture_set_sha256: str
    source_count: int
    created_count: int
    updated_count: int
    unchanged_count: int
    projected_count: int
    ledger_item_count: int
    batch_public_id: str | None
    batch_code: str | None
    verification: dict[str, int]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _ImportContext:
    rows: dict[str, list[dict[str, Any]]]
    outcomes: list[LedgerItem] = field(default_factory=list)
    users: dict[int, User] = field(default_factory=dict)
    profiles: dict[int, CustomerProfile] = field(default_factory=dict)
    products: dict[int, ProductModel] = field(default_factory=dict)
    customer_products: dict[int, dict[str, Any]] = field(
        default_factory=dict
    )
    subscriptions: dict[int, CustomerSubscription] = field(
        default_factory=dict
    )
    inquiries: dict[int, Inquiry] = field(default_factory=dict)
    consultations: dict[int, Consultation] = field(default_factory=dict)
    visits: dict[int, Visit] = field(default_factory=dict)
    followups: dict[int, FollowupConfirmation] = field(
        default_factory=dict
    )
    care_records: dict[int, CareRecord] = field(default_factory=dict)
    histories: dict[
        tuple[str, int, int], TransitionHistory
    ] = field(default_factory=dict)
    audits: dict[int, AuditEvent] = field(default_factory=dict)


class SyntheticHandoffImportService:
    """Import canonical fixtures without persisting their integer IDs."""

    def __init__(
        self,
        *,
        fixture_root: Path | None = None,
        repository: SyntheticImportRepository | None = None,
    ) -> None:
        self.repo_root = Path(__file__).resolve().parents[4]
        self.fixture_root = (
            fixture_root
            if fixture_root is not None
            else self.repo_root / "data" / "synthetic" / "fixtures"
        )
        self.repository = repository or SyntheticImportRepository()

    def run(
        self,
        *,
        profile: str,
        dry_run: bool = False,
    ) -> SyntheticImportResult:
        """Execute a fully atomic import and its verification gates."""

        normalized_profile = self._normalize_profile(profile)
        all_rows = self._load_fixture_set()
        selected_rows = self._select_rows(
            normalized_profile,
            all_rows,
        )
        dataset_version, mapping_version = self._source_versions()
        fixture_set_sha256 = self._fixture_set_sha256(all_rows)

        with transaction.atomic():
            context = _ImportContext(rows=selected_rows)
            self._import_users(context)
            self._import_profiles(context)
            self._import_products(context)
            self._project_customer_products(context)
            self._import_subscriptions(context)
            self._import_inquiries_and_symptoms(context)
            self._import_consultations(context)
            self._import_visits(context)
            self._import_followups(context)
            self._import_care_records(context)
            self._import_histories(context)
            self._import_audits(context)
            verification = self._verify(
                profile=normalized_profile,
                context=context,
            )

            batch = self.repository.record_ledger(
                profile=normalized_profile,
                dataset_version=dataset_version,
                mapping_version=mapping_version,
                fixture_set_sha256=fixture_set_sha256,
                items=context.outcomes,
            )
            counts = self._action_counts(context.outcomes)
            result = SyntheticImportResult(
                profile=normalized_profile,
                dry_run=dry_run,
                dataset_version=dataset_version,
                mapping_version=mapping_version,
                fixture_set_sha256=fixture_set_sha256,
                source_count=len(context.outcomes),
                created_count=counts[
                    SyntheticImportItem.Action.CREATED
                ],
                updated_count=counts[
                    SyntheticImportItem.Action.UPDATED
                ],
                unchanged_count=counts[
                    SyntheticImportItem.Action.UNCHANGED
                ],
                projected_count=counts[
                    SyntheticImportItem.Action.PROJECTED
                ],
                ledger_item_count=len(context.outcomes),
                batch_public_id=(
                    None if dry_run else str(batch.public_id)
                ),
                batch_code=None if dry_run else batch.batch_code,
                verification=verification,
            )
            if dry_run:
                transaction.set_rollback(True)
        return result

    def _import_users(self, context: _ImportContext) -> None:
        for row in context.rows["users"]:
            employee_no = (
                None
                if row["role"] == "CUSTOMER"
                else row["user_number"]
            )

            def prepare_new(instance: User) -> None:
                instance.set_unusable_password()

            result = self.repository.persist(
                User,
                public_id=self._uuid(row["public_id"]),
                business_lookup={"username": row["user_number"]},
                immutable_values={
                    "role_code": row["role"],
                    "employee_no": employee_no,
                },
                values={
                    "full_name": row["display_name"],
                    "is_active": bool(row["active"]),
                    "is_synthetic": (
                        row.get("data_classification") == "synthetic"
                    ),
                    "date_joined": self._datetime(row["created_at"]),
                },
                prepare_new=prepare_new,
                source_created_at=self._datetime(row["created_at"]),
            )
            instance = result.instance
            context.users[row["id"]] = instance
            self._append_outcome(
                context,
                dataset="users",
                row=row,
                result=result,
                target=instance,
                target_business_key=instance.username,
            )

    def _import_profiles(self, context: _ImportContext) -> None:
        for row in context.rows["customer_profiles"]:
            user = self._map_get(
                context.users,
                row["user_id"],
                "customer profile user",
            )
            result = self.repository.persist(
                CustomerProfile,
                public_id=self._uuid(row["public_id"]),
                business_lookup={
                    "customer_no": row["customer_profile_number"]
                },
                immutable_values={"user": user},
                values={
                    "customer_name": row["customer_name"],
                    "is_synthetic": bool(row["is_synthetic"]),
                },
                source_created_at=self._datetime(row["created_at"]),
            )
            instance = result.instance
            context.profiles[row["id"]] = instance
            self._append_outcome(
                context,
                dataset="customer_profiles",
                row=row,
                result=result,
                target=instance,
                target_business_key=instance.customer_no,
            )

    def _import_products(self, context: _ImportContext) -> None:
        for row in context.rows["products"]:
            result = self.repository.persist(
                ProductModel,
                public_id=self._uuid(row["public_id"]),
                business_lookup={"model_code": row["product_code"]},
                values={
                    "model_name": row["product_model"],
                    "generation_code": row["product_generation"],
                    "features": {
                        "model_family": row["model_family"],
                        "manual_revision": row["manual_revision"],
                        "support_scope": row["support_scope"],
                        "data_classification": row[
                            "data_classification"
                        ],
                    },
                    "is_supported_mvp": (
                        row["support_scope"] == "MVP"
                    ),
                    "is_active": True,
                },
            )
            instance = result.instance
            context.products[row["id"]] = instance
            self._append_outcome(
                context,
                dataset="products",
                row=row,
                result=result,
                target=instance,
                target_business_key=instance.model_code,
            )

    def _project_customer_products(
        self,
        context: _ImportContext,
    ) -> None:
        subscriptions_by_customer_product = {
            row["customer_product_id"]: row
            for row in context.rows["subscriptions"]
        }
        if len(subscriptions_by_customer_product) != len(
            context.rows["subscriptions"]
        ):
            raise SyntheticImportConflict(
                "Multiple subscriptions reference one customer product."
            )

        for row in context.rows["customer_products"]:
            context.customer_products[row["id"]] = row
            subscription_row = subscriptions_by_customer_product.get(
                row["id"]
            )
            if subscription_row is None:
                raise SyntheticImportConflict(
                    "Customer product has no selected subscription: "
                    f"public_id={row['public_id']}"
                )
            self._append_projection_outcome(
                context,
                row=row,
                target_public_id=self._uuid(
                    subscription_row["public_id"]
                ),
                target_business_key=subscription_row[
                    "subscription_number"
                ],
            )

    def _import_subscriptions(self, context: _ImportContext) -> None:
        for row in context.rows["subscriptions"]:
            customer_product = self._map_get(
                context.customer_products,
                row["customer_product_id"],
                "subscription customer product",
            )
            if (
                customer_product["customer_id"]
                != row["customer_profile_id"]
            ):
                raise SyntheticImportConflict(
                    "Subscription customer projection mismatch: "
                    f"source_public_id={row['public_id']}"
                )
            customer = self._map_get(
                context.profiles,
                row["customer_profile_id"],
                "subscription customer",
            )
            product = self._map_get(
                context.products,
                customer_product["product_id"],
                "subscription product",
            )
            management_type = PLAN_CODE_MAP.get(row["plan_code"])
            if management_type is None:
                raise SyntheticImportConflict(
                    f"Unsupported plan_code: {row['plan_code']}"
                )
            customer_product_public_id = self._uuid(
                customer_product["public_id"]
            )
            result = self.repository.persist(
                CustomerSubscription,
                public_id=self._uuid(row["public_id"]),
                business_lookup={
                    "contract_no": row["subscription_number"]
                },
                immutable_values={
                    "customer": customer,
                    "product_model": product,
                    "source_customer_product_public_id": (
                        customer_product_public_id
                    ),
                },
                values={
                    "serial_no": customer_product["serial_number"],
                    "management_type_code": management_type,
                    "status_code": row["status"],
                    "started_on": self._date(row["started_on"]),
                    "ended_on": None,
                    "installed_at": None,
                    "installed_on": self._date(
                        customer_product["installation_date"]
                    ),
                    "installation_address": customer_product[
                        "installation_location"
                    ],
                    "next_care_on": self._date(row["next_care_on"]),
                },
            )
            instance = result.instance
            context.subscriptions[row["id"]] = instance
            self._append_outcome(
                context,
                dataset="subscriptions",
                row=row,
                result=result,
                target=instance,
                target_business_key=instance.contract_no,
            )

    def _import_inquiries_and_symptoms(
        self,
        context: _ImportContext,
    ) -> None:
        for row in context.rows["inquiries"]:
            subscription = self._map_get(
                context.subscriptions,
                row["subscription_id"],
                "inquiry subscription",
            )
            customer = self._map_get(
                context.profiles,
                row["customer_id"],
                "inquiry customer",
            )
            if subscription.customer_id != customer.pk:
                raise SyntheticImportConflict(
                    "Inquiry customer does not own subscription: "
                    f"scenario={row['scenario_id']}"
                )
            assigned_user = (
                None
                if row["assigned_user_id"] is None
                else self._map_get(
                    context.users,
                    row["assigned_user_id"],
                    "inquiry assignee",
                )
            )
            result = self.repository.persist(
                Inquiry,
                public_id=self._uuid(row["public_id"]),
                business_lookup={
                    "inquiry_code": row["inquiry_number"]
                },
                immutable_values={
                    "scenario_code": row["scenario_id"],
                    "subscription": subscription,
                    "initiated_by": customer.user,
                },
                values={
                    "assigned_user": assigned_user,
                    "assigned_role_code": row["assigned_role"],
                    "channel_code": None,
                    "raw_text": row["original_text"],
                    "risk_level_code": row["risk_level"],
                    "usage_guidance_status": row[
                        "usage_guidance_status"
                    ],
                    "evidence_ids": row["evidence_ids"],
                    "evidence_mode": row["evidence_mode"],
                    "requires_fallback": bool(
                        row["requires_fallback"]
                    ),
                    "source_idempotency_key": row[
                        "idempotency_key"
                    ],
                    "source_correlation_id": self._uuid(
                        row["correlation_id"]
                    ),
                    "questionnaire_session_public_id": None,
                    "status_code": row["status"],
                    "state_version": row["state_version"],
                    "cancelled_at": None,
                    "cancellation_reason_code": None,
                    "cancellation_reason_detail": None,
                },
                source_created_at=self._datetime(row["created_at"]),
                source_updated_at=self._datetime(row["updated_at"]),
            )
            inquiry = result.instance
            context.inquiries[row["id"]] = inquiry

            symptom_result = self.repository.persist(
                SymptomEntry,
                public_id=uuid5(
                    self._uuid(row["public_id"]),
                    "representative-symptom",
                ),
                business_lookup={"inquiry": inquiry},
                values={
                    "symptom_type_code": row["topic_code"],
                    "structured_payload": {
                        "scenario_id": row["scenario_id"],
                        "variant": row["variant"],
                        "risk_level": row["risk_level"],
                        "usage_guidance_status": row[
                            "usage_guidance_status"
                        ],
                        "assigned_role": row["assigned_role"],
                        "assigned_user_public_id": (
                            str(assigned_user.public_id)
                            if assigned_user is not None
                            else None
                        ),
                        "evidence_ids": row["evidence_ids"],
                        "evidence_mode": row["evidence_mode"],
                        "requires_fallback": bool(
                            row["requires_fallback"]
                        ),
                        "data_classification": row[
                            "data_classification"
                        ],
                    },
                    "schema_version": "synthetic-handoff-1.0",
                    "is_customer_confirmed": True,
                },
            )
            combined = PersistResult(
                instance=inquiry,
                action=self._combine_actions(
                    result.action,
                    symptom_result.action,
                ),
            )
            self._append_outcome(
                context,
                dataset="inquiries",
                row=row,
                result=combined,
                target=inquiry,
                target_business_key=inquiry.inquiry_code,
            )

    def _import_consultations(self, context: _ImportContext) -> None:
        for row in context.rows["consultations"]:
            inquiry = self._map_get(
                context.inquiries,
                row["inquiry_id"],
                "consultation inquiry",
            )
            consultant = (
                None
                if row["consultant_id"] is None
                else self._map_get(
                    context.users,
                    row["consultant_id"],
                    "consultation consultant",
                )
            )
            result = self.repository.persist(
                Consultation,
                public_id=self._uuid(row["public_id"]),
                business_lookup={
                    "consultation_code": row[
                        "consultation_number"
                    ]
                },
                immutable_values={
                    "inquiry": inquiry,
                    "sequence": row["sequence"],
                },
                values={
                    "consultant": consultant,
                    "status": row["status"],
                    "outcome": row["outcome"],
                    "summary": row["summary"],
                    "state_version": row["state_version"],
                    "idempotency_key": row["idempotency_key"],
                    "correlation_id": self._uuid(
                        row["correlation_id"]
                    ),
                    "started_at": self._datetime(row["started_at"]),
                    "completed_at": self._datetime(
                        row["completed_at"]
                    ),
                    "data_classification": row[
                        "data_classification"
                    ],
                    "created_at": self._datetime(row["created_at"]),
                },
            )
            instance = result.instance
            context.consultations[row["id"]] = instance
            self._append_outcome(
                context,
                dataset="consultations",
                row=row,
                result=result,
                target=instance,
                target_business_key=instance.consultation_code,
            )

    def _import_visits(self, context: _ImportContext) -> None:
        for row in context.rows["visits"]:
            inquiry = self._map_get(
                context.inquiries,
                row["inquiry_id"],
                "visit inquiry",
            )
            technician = (
                None
                if row["technician_id"] is None
                else self._map_get(
                    context.users,
                    row["technician_id"],
                    "visit technician",
                )
            )
            result = self.repository.persist(
                Visit,
                public_id=self._uuid(row["public_id"]),
                business_lookup={"visit_code": row["visit_number"]},
                immutable_values={"inquiry": inquiry},
                values={
                    "technician": technician,
                    "status": row["status"],
                    "requested_at": self._datetime(
                        row["requested_at"]
                    ),
                    "scheduled_at": self._datetime(
                        row["scheduled_at"]
                    ),
                    "started_at": self._datetime(row["started_at"]),
                    "completed_at": self._datetime(
                        row["completed_at"]
                    ),
                    "confirmed_cause": row["confirmed_cause"],
                    "action_taken": row["action_taken"],
                    "state_version": row["state_version"],
                    "idempotency_key": row["idempotency_key"],
                    "correlation_id": self._uuid(
                        row["correlation_id"]
                    ),
                    "data_classification": row[
                        "data_classification"
                    ],
                },
            )
            instance = result.instance
            context.visits[row["id"]] = instance
            self._append_outcome(
                context,
                dataset="visits",
                row=row,
                result=result,
                target=instance,
                target_business_key=instance.visit_code,
            )

    def _import_followups(self, context: _ImportContext) -> None:
        for row in context.rows["followup_confirmations"]:
            if row["guidance_id"] is not None:
                raise SyntheticImportConflict(
                    "Canonical guidance fixture lookup is unavailable."
                )
            inquiry = self._map_get(
                context.inquiries,
                row["inquiry_id"],
                "follow-up inquiry",
            )
            consultation = (
                None
                if row["consultation_id"] is None
                else self._map_get(
                    context.consultations,
                    row["consultation_id"],
                    "follow-up consultation",
                )
            )
            visit = (
                None
                if row["visit_id"] is None
                else self._map_get(
                    context.visits,
                    row["visit_id"],
                    "follow-up visit",
                )
            )
            result = self.repository.persist(
                FollowupConfirmation,
                public_id=self._uuid(row["public_id"]),
                business_lookup={
                    "followup_code": row["followup_number"]
                },
                immutable_values={
                    "inquiry": inquiry,
                    "consultation": consultation,
                    "visit": visit,
                    "guidance_public_id": None,
                },
                values={
                    "channel_code": row["channel_code"],
                    "resolution_status_code": row[
                        "resolution_status_code"
                    ],
                    "state_version": row["state_version"],
                    "customer_response": row["customer_response"],
                    "unresolved_reason": row["unresolved_reason"],
                    "next_action": row["next_action"],
                    "requested_at": self._datetime(
                        row["requested_at"]
                    ),
                    "responded_at": self._datetime(
                        row["responded_at"]
                    ),
                    "confirmed_at": self._datetime(
                        row["confirmed_at"]
                    ),
                },
            )
            instance = result.instance
            context.followups[row["id"]] = instance
            self._append_outcome(
                context,
                dataset="followup_confirmations",
                row=row,
                result=result,
                target=instance,
                target_business_key=instance.followup_code,
            )

    def _import_care_records(self, context: _ImportContext) -> None:
        subscription_by_customer_product = {
            row["customer_product_id"]: context.subscriptions[row["id"]]
            for row in context.rows["subscriptions"]
        }
        for row in context.rows["care_histories"]:
            subscription = self._map_get(
                subscription_by_customer_product,
                row["customer_product_id"],
                "care subscription",
            )
            inquiry = (
                None
                if row["inquiry_id"] is None
                else self._map_get(
                    context.inquiries,
                    row["inquiry_id"],
                    "care inquiry",
                )
            )
            visit = (
                None
                if row["visit_id"] is None
                else self._map_get(
                    context.visits,
                    row["visit_id"],
                    "care visit",
                )
            )
            care_type = CARE_TYPE_MAP.get(row["care_type"])
            if care_type is None:
                raise SyntheticImportConflict(
                    f"Unsupported care_type: {row['care_type']}"
                )
            result = self.repository.persist(
                CareRecord,
                public_id=self._uuid(row["public_id"]),
                business_lookup={
                    "care_code": row["care_history_number"]
                },
                immutable_values={
                    "subscription": subscription,
                    "inquiry": inquiry,
                    "visit": visit,
                },
                values={
                    "visit_result_public_id": None,
                    "care_type_code": care_type,
                    "status_code": CareRecord.Status.COMPLETED,
                    "scheduled_on": None,
                    "performed_on": self._date(
                        row["performed_on"]
                    ),
                    "result_code": row["result"],
                    "completed_at": None,
                    "cancelled_at": None,
                    "cancellation_reason": None,
                    "summary": row["note"],
                    "performed_by": None,
                    "source_code": CareRecord.Source.IMPORT,
                },
            )
            instance = result.instance
            context.care_records[row["id"]] = instance
            self._append_outcome(
                context,
                dataset="care_histories",
                row=row,
                result=result,
                target=instance,
                target_business_key=instance.care_code,
            )

    def _import_histories(self, context: _ImportContext) -> None:
        for row in context.rows["inquiry_status_histories"]:
            if row["questionnaire_session_id"] is not None:
                raise SyntheticImportConflict(
                    "Questionnaire session fixture mapping is unavailable."
                )
            target_type = row["target_type_code"]
            inquiry = None
            visit = None
            target_fixture_id: int
            if target_type == TransitionHistory.TargetType.INQUIRY:
                target_fixture_id = row["inquiry_id"]
                inquiry = self._map_get(
                    context.inquiries,
                    target_fixture_id,
                    "history inquiry",
                )
            elif target_type == TransitionHistory.TargetType.VISIT:
                target_fixture_id = row["visit_id"]
                visit = self._map_get(
                    context.visits,
                    target_fixture_id,
                    "history visit",
                )
            else:
                raise SyntheticImportConflict(
                    f"Unsupported history target: {target_type}"
                )
            actor = (
                None
                if row["changed_by_id"] is None
                else self._map_get(
                    context.users,
                    row["changed_by_id"],
                    "history actor",
                )
            )
            result = self.repository.persist(
                TransitionHistory,
                public_id=self._uuid(row["public_id"]),
                business_lookup={
                    "status_history_code": row[
                        "status_history_number"
                    ]
                },
                immutable_values={
                    "target_type_code": target_type,
                    "questionnaire_session": None,
                    "inquiry": inquiry,
                    "consultation": None,
                    "visit": visit,
                    "state_version": row["state_version"],
                },
                values={
                    "actor": actor,
                    "changed_by_type_code": row[
                        "changed_by_type_code"
                    ],
                    "event_code": row["event_code"],
                    "from_state": row["from_status_code"],
                    "to_state": row["to_status_code"],
                    "correlation_id": self._uuid(
                        row["correlation_id"]
                    ),
                    "idempotency_key": row["idempotency_key"],
                    "change_reason": row["change_reason"],
                    "changed_at": self._datetime(row["changed_at"]),
                },
            )
            instance = result.instance
            key = (
                target_type,
                target_fixture_id,
                row["state_version"],
            )
            if key in context.histories:
                raise SyntheticImportConflict(
                    f"Duplicate history aggregate version: {key}"
                )
            context.histories[key] = instance
            self._append_outcome(
                context,
                dataset="inquiry_status_histories",
                row=row,
                result=result,
                target=instance,
                target_business_key=instance.status_history_code,
            )

    def _import_audits(self, context: _ImportContext) -> None:
        history_source = {
            (
                row["target_type_code"],
                row["inquiry_id"]
                if row["target_type_code"] == "INQUIRY"
                else row["visit_id"],
                row["state_version"],
            ): row
            for row in context.rows["inquiry_status_histories"]
        }
        for row in context.rows["audit_events"]:
            key = (
                row["entity_type"],
                row["entity_id"],
                row["state_version"],
            )
            transition = self._map_get(
                context.histories,
                key,
                "audit transition",
            )
            source_history = self._map_get(
                history_source,
                key,
                "audit source history",
            )
            self._assert_audit_source_equal(row, source_history)

            inquiry = None
            visit = None
            if row["entity_type"] == AuditEvent.EntityType.INQUIRY:
                inquiry = self._map_get(
                    context.inquiries,
                    row["entity_id"],
                    "audit inquiry",
                )
            elif row["entity_type"] == AuditEvent.EntityType.VISIT:
                visit = self._map_get(
                    context.visits,
                    row["entity_id"],
                    "audit visit",
                )
            else:
                raise SyntheticImportConflict(
                    f"Unsupported audit entity: {row['entity_type']}"
                )
            actor = (
                None
                if row["actor_id"] is None
                else self._map_get(
                    context.users,
                    row["actor_id"],
                    "audit actor",
                )
            )
            if actor is not None and actor.role_code != row["actor_role"]:
                raise SyntheticImportConflict(
                    "Audit actor role mismatch: "
                    f"audit={row['audit_record_number']}"
                )
            result = self.repository.persist(
                AuditEvent,
                public_id=self._uuid(row["public_id"]),
                business_lookup={
                    "audit_code": row["audit_record_number"]
                },
                immutable_values={
                    "transition": transition,
                    "entity_type": row["entity_type"],
                    "inquiry": inquiry,
                    "visit": visit,
                    "state_version": row["state_version"],
                },
                values={
                    "event_code": row["event_type"],
                    "actor_role": row["actor_role"],
                    "actor": actor,
                    "idempotency_key": row["idempotency_key"],
                    "correlation_id": self._uuid(
                        row["correlation_id"]
                    ),
                    "occurred_at": self._datetime(
                        row["occurred_at"]
                    ),
                    "data_classification": row[
                        "data_classification"
                    ],
                },
            )
            instance = result.instance
            context.audits[row["id"]] = instance
            self._append_outcome(
                context,
                dataset="audit_events",
                row=row,
                result=result,
                target=instance,
                target_business_key=instance.audit_code,
            )

    def _verify(
        self,
        *,
        profile: str,
        context: _ImportContext,
    ) -> dict[str, int]:
        expected = EXPECTED_SOURCE_COUNTS[profile]
        if len(context.outcomes) != expected:
            raise SyntheticImportConflict(
                f"Source ledger count mismatch: "
                f"{len(context.outcomes)} != {expected}"
            )
        source_keys = {
            (item.source_dataset, item.source_public_id)
            for item in context.outcomes
        }
        if len(source_keys) != len(context.outcomes):
            raise SyntheticImportConflict(
                "Source ledger contains duplicate dataset/public UUID."
            )

        projection_checks = 0
        subscriptions_by_customer_product = {
            row["customer_product_id"]: context.subscriptions[row["id"]]
            for row in context.rows["subscriptions"]
        }
        for row in context.rows["customer_products"]:
            subscription = subscriptions_by_customer_product[row["id"]]
            if (
                subscription.source_customer_product_public_id
                != self._uuid(row["public_id"])
                or subscription.serial_no != row["serial_number"]
                or subscription.installed_on
                != self._date(row["installation_date"])
                or subscription.installation_address
                != row["installation_location"]
            ):
                raise SyntheticImportConflict(
                    "Customer product projection verification failed: "
                    f"source_public_id={row['public_id']}"
                )
            projection_checks += 1

        aggregate_checks = 0
        audit_history_checks = 0
        if profile == "db-full":
            histories_by_target: dict[
                tuple[str, int], list[dict[str, Any]]
            ] = {}
            for row in context.rows["inquiry_status_histories"]:
                target_id = (
                    row["inquiry_id"]
                    if row["target_type_code"] == "INQUIRY"
                    else row["visit_id"]
                )
                histories_by_target.setdefault(
                    (row["target_type_code"], target_id),
                    [],
                ).append(row)

            for row in context.rows["inquiries"]:
                latest = max(
                    histories_by_target[("INQUIRY", row["id"])],
                    key=lambda item: item["state_version"],
                )
                instance = context.inquiries[row["id"]]
                if (
                    instance.state_version != latest["state_version"]
                    or instance.status_code
                    != latest["to_status_code"]
                ):
                    raise SyntheticImportConflict(
                        "Inquiry aggregate/history mismatch: "
                        f"inquiry={row['inquiry_number']}"
                    )
                aggregate_checks += 1

            for row in context.rows["visits"]:
                latest = max(
                    histories_by_target[("VISIT", row["id"])],
                    key=lambda item: item["state_version"],
                )
                instance = context.visits[row["id"]]
                if (
                    instance.state_version != latest["state_version"]
                    or instance.status != latest["to_status_code"]
                ):
                    raise SyntheticImportConflict(
                        "Visit aggregate/history mismatch: "
                        f"visit={row['visit_number']}"
                    )
                aggregate_checks += 1

            for row in context.rows["audit_events"]:
                key = (
                    row["entity_type"],
                    row["entity_id"],
                    row["state_version"],
                )
                audit = context.audits[row["id"]]
                history = context.histories[key]
                if (
                    audit.transition_id != history.pk
                    or audit.event_code != history.event_code
                    or audit.state_version != history.state_version
                    or audit.actor_id != history.actor_id
                    or audit.idempotency_key
                    != history.idempotency_key
                    or audit.correlation_id != history.correlation_id
                    or audit.occurred_at != history.changed_at
                ):
                    raise SyntheticImportConflict(
                        "Audit/history persistence mismatch: "
                        f"audit={row['audit_record_number']}"
                    )
                audit_history_checks += 1

        return {
            "source_items": len(context.outcomes),
            "projection_checks": projection_checks,
            "aggregate_checks": aggregate_checks,
            "audit_history_checks": audit_history_checks,
        }

    def _load_fixture_set(self) -> dict[str, list[dict[str, Any]]]:
        if not self.fixture_root.is_dir():
            raise SyntheticImportConflict(
                f"Fixture directory is missing: {self.fixture_root}"
            )
        result: dict[str, list[dict[str, Any]]] = {}
        for dataset in DATASET_ORDER:
            path = self.fixture_root / f"{dataset}.json"
            try:
                rows = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise SyntheticImportConflict(
                    f"Cannot read fixture: {path}"
                ) from exc
            if not isinstance(rows, list):
                raise SyntheticImportConflict(
                    f"Fixture root must be an array: {path}"
                )
            expected_count = EXPECTED_FIXTURE_COUNTS[dataset]
            if len(rows) != expected_count:
                raise SyntheticImportConflict(
                    f"Fixture count mismatch: {dataset} "
                    f"{len(rows)} != {expected_count}"
                )
            ids: set[int] = set()
            public_ids: set[UUID] = set()
            business_keys: set[str] = set()
            key_field = BUSINESS_KEY_FIELDS[dataset]
            for row in rows:
                fixture_id = row.get("id")
                if (
                    not isinstance(fixture_id, int)
                    or fixture_id <= 0
                    or fixture_id in ids
                ):
                    raise SyntheticImportConflict(
                        f"Invalid or duplicate local fixture ID: "
                        f"{dataset}:{fixture_id}"
                    )
                ids.add(fixture_id)
                public_id = self._uuid(row.get("public_id"))
                if public_id in public_ids:
                    raise SyntheticImportConflict(
                        f"Duplicate fixture public UUID: "
                        f"{dataset}:{public_id}"
                    )
                public_ids.add(public_id)
                business_key = str(row.get(key_field) or "")
                if not business_key or business_key in business_keys:
                    raise SyntheticImportConflict(
                        f"Invalid fixture business key: "
                        f"{dataset}:{business_key}"
                    )
                business_keys.add(business_key)
                if row.get("data_classification") != "synthetic":
                    raise SyntheticImportConflict(
                        f"Non-synthetic fixture row: "
                        f"{dataset}:{public_id}"
                    )
            result[dataset] = rows
        expected_total = sum(EXPECTED_FIXTURE_COUNTS.values())
        if sum(map(len, result.values())) != expected_total:
            raise SyntheticImportConflict(
                "Canonical physical fixture set must contain exactly "
                f"{expected_total} rows."
            )
        return result

    def _select_rows(
        self,
        profile: str,
        all_rows: dict[str, list[dict[str, Any]]],
    ) -> dict[str, list[dict[str, Any]]]:
        if profile == "db-full":
            selected = {
                dataset: list(all_rows[dataset])
                for dataset in DATASET_ORDER
            }
            referenced_product_ids = {
                row["product_id"]
                for row in selected["customer_products"]
            }
            selected["products"] = [
                row
                for row in all_rows["products"]
                if row["id"] in referenced_product_ids
            ]
            self._assert_profile_counts(
                profile,
                selected,
                EXPECTED_FULL_COUNTS,
            )
            return selected

        inquiries = [
            row
            for row in all_rows["inquiries"]
            if row["scenario_id"] in SMOKE_SCENARIOS
        ]
        inquiry_ids = {row["id"] for row in inquiries}
        subscription_ids = {
            row["subscription_id"] for row in inquiries
        }
        subscriptions = [
            row
            for row in all_rows["subscriptions"]
            if row["id"] in subscription_ids
        ]
        customer_product_ids = {
            row["customer_product_id"] for row in subscriptions
        }
        customer_products = [
            row
            for row in all_rows["customer_products"]
            if row["id"] in customer_product_ids
        ]
        profile_ids = {
            row["customer_profile_id"] for row in subscriptions
        }
        profiles = [
            row
            for row in all_rows["customer_profiles"]
            if row["id"] in profile_ids
        ]
        product_ids = {
            row["product_id"] for row in customer_products
        }
        products = [
            row
            for row in all_rows["products"]
            if row["id"] in product_ids
        ]
        consultations = [
            row
            for row in all_rows["consultations"]
            if row["inquiry_id"] in inquiry_ids
        ]
        visits = [
            row
            for row in all_rows["visits"]
            if row["inquiry_id"] in inquiry_ids
        ]
        user_ids = {
            row["user_id"] for row in profiles
        } | {
            row["assigned_user_id"]
            for row in inquiries
            if row["assigned_user_id"] is not None
        } | {
            row["consultant_id"]
            for row in consultations
            if row["consultant_id"] is not None
        } | {
            row["technician_id"]
            for row in visits
            if row["technician_id"] is not None
        }
        users = [
            row
            for row in all_rows["users"]
            if row["id"] in user_ids
        ]
        selected = {
            "users": users,
            "customer_profiles": profiles,
            "products": products,
            "customer_products": customer_products,
            "subscriptions": subscriptions,
            "inquiries": inquiries,
            "consultations": consultations,
            "visits": visits,
            "followup_confirmations": [],
            "care_histories": [],
            "inquiry_status_histories": [],
            "audit_events": [],
        }
        self._assert_profile_counts(
            profile,
            selected,
            EXPECTED_SMOKE_COUNTS,
        )
        return selected

    def _assert_profile_counts(
        self,
        profile: str,
        selected: dict[str, list[dict[str, Any]]],
        expected_counts: dict[str, int],
    ) -> None:
        actual_counts = {
            dataset: len(selected[dataset])
            for dataset in DATASET_ORDER
        }
        if actual_counts != expected_counts:
            raise SyntheticImportConflict(
                f"{profile} closure mismatch: {actual_counts}"
            )
        expected_total = EXPECTED_SOURCE_COUNTS[profile]
        if sum(actual_counts.values()) != expected_total:
            raise SyntheticImportConflict(
                f"{profile} source total mismatch."
            )

    def _source_versions(self) -> tuple[str, str]:
        try:
            pipeline = json.loads(
                (
                    self.repo_root / "data" / "config" / "pipeline.json"
                ).read_text(encoding="utf-8-sig")
            )
            crosswalk = json.loads(
                (
                    self.repo_root
                    / "data"
                    / "config"
                    / "handoff"
                    / "backend_import_crosswalk.json"
                ).read_text(encoding="utf-8-sig")
            )
            dataset_version = str(pipeline["dataset_version"])
            mapping_version = str(crosswalk["mapping_version"])
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            raise SyntheticImportConflict(
                "Cannot resolve dataset or mapping version."
            ) from exc
        if not dataset_version or not mapping_version:
            raise SyntheticImportConflict(
                "Dataset and mapping versions must be non-empty."
            )
        return dataset_version, mapping_version

    @staticmethod
    def _fixture_set_sha256(
        rows: dict[str, list[dict[str, Any]]],
    ) -> str:
        manifest = hashlib.sha256()
        for dataset in DATASET_ORDER:
            payload = json.dumps(
                rows[dataset],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            manifest.update(dataset.encode("utf-8"))
            manifest.update(b"\0")
            manifest.update(hashlib.sha256(payload).digest())
            manifest.update(b"\n")
        return manifest.hexdigest().upper()

    def _append_outcome(
        self,
        context: _ImportContext,
        *,
        dataset: str,
        row: dict[str, Any],
        result: PersistResult,
        target: Any,
        target_business_key: str,
    ) -> None:
        context.outcomes.append(
            LedgerItem(
                source_dataset=dataset,
                source_public_id=self._uuid(row["public_id"]),
                source_business_key=str(
                    row[BUSINESS_KEY_FIELDS[dataset]]
                ),
                source_sha256=self._row_sha256(row),
                action=result.action,
                target_model=target._meta.label,
                target_public_id=target.public_id,
                target_business_key=str(target_business_key),
            )
        )

    def _append_projection_outcome(
        self,
        context: _ImportContext,
        *,
        row: dict[str, Any],
        target_public_id: UUID,
        target_business_key: str,
    ) -> None:
        context.outcomes.append(
            LedgerItem(
                source_dataset="customer_products",
                source_public_id=self._uuid(row["public_id"]),
                source_business_key=row["serial_number"],
                source_sha256=self._row_sha256(row),
                action=SyntheticImportItem.Action.PROJECTED,
                target_model=CustomerSubscription._meta.label,
                target_public_id=target_public_id,
                target_business_key=target_business_key,
            )
        )

    @staticmethod
    def _row_sha256(row: dict[str, Any]) -> str:
        payload = json.dumps(
            row,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest().upper()

    @staticmethod
    def _combine_actions(*actions: str) -> str:
        if SyntheticImportItem.Action.CREATED in actions:
            return SyntheticImportItem.Action.CREATED
        if SyntheticImportItem.Action.UPDATED in actions:
            return SyntheticImportItem.Action.UPDATED
        return SyntheticImportItem.Action.UNCHANGED

    @staticmethod
    def _action_counts(items: list[LedgerItem]) -> dict[str, int]:
        return {
            action: sum(item.action == action for item in items)
            for action in SyntheticImportItem.Action.values
        }

    @staticmethod
    def _normalize_profile(profile: str) -> str:
        aliases = {
            "smoke": "db-smoke",
            "db-smoke": "db-smoke",
            "full": "db-full",
            "db-full": "db-full",
        }
        try:
            return aliases[profile]
        except KeyError as exc:
            raise SyntheticImportConflict(
                f"Unsupported import profile: {profile}"
            ) from exc

    @staticmethod
    def _assert_audit_source_equal(
        audit: dict[str, Any],
        history: dict[str, Any],
    ) -> None:
        audit_values = (
            audit["event_type"],
            audit["actor_id"],
            audit["state_version"],
            audit["idempotency_key"],
            audit["correlation_id"],
            audit["occurred_at"],
        )
        history_values = (
            history["event_code"],
            history["changed_by_id"],
            history["state_version"],
            history["idempotency_key"],
            history["correlation_id"],
            history["changed_at"],
        )
        if audit_values != history_values:
            raise SyntheticImportConflict(
                "Audit source does not match transition source: "
                f"audit={audit['audit_record_number']}"
            )

    @staticmethod
    def _map_get(mapping: dict[Any, Any], key: Any, label: str) -> Any:
        try:
            return mapping[key]
        except (KeyError, TypeError) as exc:
            raise SyntheticImportConflict(
                f"Missing {label} relationship: {key}"
            ) from exc

    @staticmethod
    def _uuid(value: Any) -> UUID:
        try:
            return UUID(str(value))
        except (ValueError, TypeError, AttributeError) as exc:
            raise SyntheticImportConflict(
                f"Invalid UUID value: {value}"
            ) from exc

    @staticmethod
    def _date(value: Any) -> date | None:
        if value in (None, ""):
            return None
        try:
            return date.fromisoformat(str(value))
        except ValueError as exc:
            raise SyntheticImportConflict(
                f"Invalid date value: {value}"
            ) from exc

    @staticmethod
    def _datetime(value: Any) -> datetime | None:
        if value in (None, ""):
            return None
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError as exc:
            raise SyntheticImportConflict(
                f"Invalid datetime value: {value}"
            ) from exc
        if parsed.tzinfo is None:
            raise SyntheticImportConflict(
                f"Naive datetime is forbidden: {value}"
            )
        return parsed
