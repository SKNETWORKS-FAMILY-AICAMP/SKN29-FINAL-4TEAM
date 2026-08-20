"""Build a privacy-minimized, read-only Inquiry Context for AI."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from rest_framework.exceptions import NotFound

from apps.inquiries.repositories.internal_ai_context_repository import (
    InternalAIContextRepository,
)
from integrations.ai.request_mapper import build_request_from_inquiry


PRODUCT_FAMILY_BY_MODEL_CODE = {
    "WPUJAC104DWH": "DIRECT_WATER_PURIFIER",
    "WPUIAC425SNW": "ICE_WATER_PURIFIER",
    "WPUIAC606SNW": "ICE_WATER_PURIFIER",
}


class InternalAIContextService:
    """Project only the product and inquiry fields required by AI Tools."""

    @classmethod
    def retrieve(
        cls,
        *,
        inquiry_public_id: UUID,
        correlation_id: UUID,
    ) -> dict[str, Any]:
        inquiry = InternalAIContextRepository.find(inquiry_public_id)
        if inquiry is None:
            raise NotFound()

        ai_request = build_request_from_inquiry(
            inquiry,
            correlation_id=correlation_id,
            ai_request_id=f"context-read-{correlation_id}",
        )
        product = inquiry.subscription.product_model
        selected_symptoms = ai_request["selected_symptoms"]
        return {
            "inquiry_id": ai_request["inquiry_id"],
            "inquiry_code": inquiry.inquiry_code,
            "status_code": inquiry.status_code,
            "state_version": ai_request["state_version"],
            "correlation_id": ai_request["correlation_id"],
            "product_context": {
                "subscription_id": str(inquiry.subscription.public_id),
                "subscription_status_code": inquiry.subscription.status_code,
                "management_type_code": (
                    inquiry.subscription.management_type_code
                ),
                "product_model_id": str(product.public_id),
                "model_code": ai_request["model_code"],
                "model_name": product.model_name,
                "product_family": PRODUCT_FAMILY_BY_MODEL_CODE.get(
                    product.model_code,
                    "UNKNOWN",
                ),
                "generation_code": product.generation_code,
                "manufacturer": product.manufacturer,
                "features": cls._features(product.features),
            },
            "inquiry_context": {
                "customer_query": ai_request["raw_symptom"],
                "symptom_type": (
                    selected_symptoms[0] if selected_symptoms else None
                ),
                "selected_symptoms": selected_symptoms,
                "previous_answers": ai_request["previous_answers"],
            },
        }

    @classmethod
    def _features(cls, raw_value: Any) -> dict[str, Any]:
        raw = raw_value if isinstance(raw_value, dict) else {}
        model_family = raw.get("model_family")
        return {
            "model_family": (
                model_family.strip()[:100]
                if isinstance(model_family, str) and model_family.strip()
                else None
            ),
            "water_modes": cls._string_list(
                raw.get("water_modes"),
                max_items=20,
            ),
            "supported_functions": cls._string_list(
                raw.get("supported_functions"),
                max_items=40,
            ),
        }

    @staticmethod
    def _string_list(raw_value: Any, *, max_items: int) -> list[str]:
        if not isinstance(raw_value, list):
            return []
        result: list[str] = []
        for item in raw_value:
            if not isinstance(item, str):
                continue
            value = item.strip()[:100]
            if value and value not in result:
                result.append(value)
            if len(result) >= max_items:
                break
        return result
