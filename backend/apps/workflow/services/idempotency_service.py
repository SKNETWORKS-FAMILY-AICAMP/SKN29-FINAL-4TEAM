"""Canonical request hashing and stored-response replay rules."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
import hashlib
import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from apps.workflow.models import IdempotencyRecord
from common.exceptions.business import BusinessError
from common.exceptions.error_codes import DUPLICATE_EVENT


class IdempotencyService:
    """Apply the PM actor/operation/key idempotency contract."""

    @classmethod
    def canonical_request_hash(cls, value: Mapping[str, Any]) -> str:
        normalized = cls._json_value(value)
        encoded = json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def _json_value(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                str(key): cls._json_value(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [cls._json_value(item) for item in value]
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        return value

    @staticmethod
    def replay_or_conflict(
        record: IdempotencyRecord,
        *,
        request_hash: str,
        replay_field: str = "idempotent_replay",
    ) -> tuple[int, dict]:
        if record.request_hash != request_hash:
            raise BusinessError(
                DUPLICATE_EVENT,
                "동일 Idempotency-Key가 다른 요청에 재사용되었습니다.",
                details={},
                status_code=409,
            )
        if (
            record.completed_at is None
            or record.response_status is None
            or not record.response_body
        ):
            raise BusinessError(
                DUPLICATE_EVENT,
                "동일 Idempotency-Key 요청이 아직 처리 중입니다.",
                details={},
                status_code=409,
            )

        response_body = deepcopy(record.response_body)
        response_body[replay_field] = True
        return record.response_status, response_body
