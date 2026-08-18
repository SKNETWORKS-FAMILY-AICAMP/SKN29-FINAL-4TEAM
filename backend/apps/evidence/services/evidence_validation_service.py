"""Fail-closed validation for non-public T-028B projection candidates."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID


PREPARATION_STATUS = "PREPARATION_ONLY"
SUPPORTED_CONSUMER_ROLES = frozenset(
    {"CUSTOMER", "CONSULTANT", "TECHNICIAN"}
)
SAFE_TOP_LEVEL_FIELDS = frozenset(
    {
        "projection_status",
        "consumer_role",
        "evidence_id",
        "document",
        "location",
        "evidence_summary",
        "product_model_codes",
        "verification",
    }
)
SAFE_DOCUMENT_FIELDS = frozenset(
    {
        "document_code",
        "title",
        "revision",
        "source_org",
        "landing_url",
    }
)
SAFE_LOCATION_FIELDS = frozenset({"page_no", "section"})
SAFE_VERIFICATION_FIELDS = frozenset({"is_verified"})
PROHIBITED_FIELDS = frozenset(
    {
        "ai_run_id",
        "chunk_id",
        "cited_text_snapshot",
        "document_sha256_snapshot",
        "manual_page_text",
        "original_file_uri",
        "prompt",
        "query_text",
        "raw_text",
        "retrieval_hit_id",
        "retrieval_run_id",
        "retrieval_text",
        "search_score",
        "similarity_score",
        "source_path",
        "source_storage_path",
        "vector_score",
        "verified_by",
    }
)


class UnsafeEvidenceProjection(ValueError):
    """Raised before an unsafe or unapproved field can leave the service."""


class EvidenceValidationService:
    """Validate the minimal internal candidate without approving a public DTO."""

    @classmethod
    def validate_preparation_candidate(
        cls,
        payload: Mapping[str, Any],
    ) -> None:
        if not isinstance(payload, Mapping):
            raise UnsafeEvidenceProjection("projection must be an object")
        keys = cls._collect_keys(payload)
        if keys & PROHIBITED_FIELDS:
            raise UnsafeEvidenceProjection("projection contains prohibited fields")
        if set(payload) != SAFE_TOP_LEVEL_FIELDS:
            raise UnsafeEvidenceProjection("projection fields are not approved")
        if payload["projection_status"] != PREPARATION_STATUS:
            raise UnsafeEvidenceProjection("public projection is not approved")
        if payload["consumer_role"] not in SUPPORTED_CONSUMER_ROLES:
            raise UnsafeEvidenceProjection("unsupported consumer role")
        try:
            UUID(str(payload["evidence_id"]))
        except (TypeError, ValueError, AttributeError) as exc:
            raise UnsafeEvidenceProjection("invalid evidence identifier") from exc

        document = cls._exact_mapping(
            payload["document"],
            SAFE_DOCUMENT_FIELDS,
            "document",
        )
        location = cls._exact_mapping(
            payload["location"],
            SAFE_LOCATION_FIELDS,
            "location",
        )
        verification = cls._exact_mapping(
            payload["verification"],
            SAFE_VERIFICATION_FIELDS,
            "verification",
        )
        for field in ("document_code", "title", "source_org"):
            cls._required_text(document[field], f"document.{field}")
        for field in ("revision",):
            cls._optional_text(document[field], f"document.{field}")
        cls._https_url(document["landing_url"])

        page_no = location["page_no"]
        if not isinstance(page_no, int) or isinstance(page_no, bool) or page_no < 1:
            raise UnsafeEvidenceProjection("location.page_no is invalid")
        cls._optional_text(location["section"], "location.section")
        cls._required_text(payload["evidence_summary"], "evidence_summary")
        cls._model_codes(payload["product_model_codes"])
        if verification["is_verified"] is not True:
            raise UnsafeEvidenceProjection("unverified evidence is prohibited")

    @staticmethod
    def _collect_keys(value: Any) -> set[str]:
        if isinstance(value, Mapping):
            return set(value) | {
                key
                for nested in value.values()
                for key in EvidenceValidationService._collect_keys(nested)
            }
        if isinstance(value, list):
            return {
                key
                for nested in value
                for key in EvidenceValidationService._collect_keys(nested)
            }
        return set()

    @staticmethod
    def _exact_mapping(
        value: Any,
        fields: frozenset[str],
        name: str,
    ) -> Mapping[str, Any]:
        if not isinstance(value, Mapping) or set(value) != fields:
            raise UnsafeEvidenceProjection(f"{name} fields are not approved")
        return value

    @staticmethod
    def _required_text(value: Any, name: str) -> None:
        if (
            not isinstance(value, str)
            or not value.strip()
            or value != value.strip()
            or len(value) > 1000
        ):
            raise UnsafeEvidenceProjection(f"{name} is invalid")

    @classmethod
    def _optional_text(cls, value: Any, name: str) -> None:
        if value is not None:
            cls._required_text(value, name)

    @staticmethod
    def _https_url(value: Any) -> None:
        if not isinstance(value, str) or len(value) > 1000:
            raise UnsafeEvidenceProjection("document.landing_url is invalid")
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise UnsafeEvidenceProjection("document.landing_url is unsafe")

    @classmethod
    def _model_codes(cls, value: Any) -> None:
        if not isinstance(value, list) or not value or len(value) > 20:
            raise UnsafeEvidenceProjection("product_model_codes are invalid")
        if len(value) != len(set(value)):
            raise UnsafeEvidenceProjection("product_model_codes are duplicated")
        for item in value:
            cls._required_text(item, "product_model_codes")
