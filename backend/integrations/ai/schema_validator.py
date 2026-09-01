"""JSON Schema Draft 2020-12 기반 AI 계약 검증."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from integrations.ai.exceptions import (
    AIRequestValidationError,
    AIResponseValidationError,
)


DEFAULT_CONTRACT_ROOT = (
    Path(__file__).resolve().parents[3] / "contracts" / "ai"
)


class AIContractValidator:
    """AI 요청·성공·오류 응답을 동일 계약 디렉터리로 검증한다."""

    schema_paths = {
        "request": "requests/SymptomAnalysisRequest.schema.json",
        "success": "responses/SymptomAnalysisResponse.schema.json",
        "internal_success": (
            "internal/AnalysisConsultationEnvelope.schema.json"
        ),
        "error": "common/AIErrorResponse.schema.json",
    }

    def __init__(self, contract_root: Path | str | None = None) -> None:
        self.contract_root = Path(
            contract_root or DEFAULT_CONTRACT_ROOT
        ).resolve()
        if not self.contract_root.is_dir():
            raise AIResponseValidationError(
                "AI 계약 디렉터리를 찾을 수 없습니다.",
            )
        self._registry = self._build_registry()
        self._validators = {
            kind: self._build_validator(relative_path)
            for kind, relative_path in self.schema_paths.items()
        }

    def validate_request(self, payload: dict[str, Any]) -> None:
        errors = self._validation_errors("request", payload)
        if errors:
            raise AIRequestValidationError(
                "AI 요청 계약 검증에 실패했습니다.",
                validation_errors=errors,
            )

    def validate_success_response(self, payload: dict[str, Any]) -> None:
        errors = self._validation_errors("success", payload)
        if errors:
            raise AIResponseValidationError(
                "AI 성공 응답 계약 검증에 실패했습니다.",
                payload=payload,
                validation_errors=errors,
            )

    def validate_internal_success_response(
        self,
        payload: dict[str, Any],
    ) -> None:
        """Validate the private analysis + cause-ledger Envelope."""

        errors = self._validation_errors("internal_success", payload)
        if errors:
            raise AIResponseValidationError(
                "AI 내부 Envelope 계약 검증에 실패했습니다.",
                payload=payload,
                validation_errors=errors,
            )

    def validate_error_response(self, payload: dict[str, Any]) -> None:
        errors = self._validation_errors("error", payload)
        if errors:
            raise AIResponseValidationError(
                "AI 오류 응답 계약 검증에 실패했습니다.",
                payload=payload,
                validation_errors=errors,
            )

    def contract_version(self, kind: str = "request") -> str:
        schema = self._schema_contents(self.schema_paths[kind])
        version = schema.get("x-contract-version")
        return str(version or "unknown")

    def _build_registry(self) -> Registry:
        registry = Registry()
        for path in self.contract_root.rglob("*.json"):
            contents = json.loads(path.read_text(encoding="utf-8"))
            resource = Resource.from_contents(
                contents,
                default_specification=DRAFT202012,
            )
            registry = registry.with_resource(path.resolve().as_uri(), resource)
        return registry

    def _build_validator(self, relative_path: str) -> Draft202012Validator:
        path = (self.contract_root / relative_path).resolve()
        schema = deepcopy(self._schema_contents(relative_path))
        schema["$id"] = path.as_uri()
        return Draft202012Validator(
            schema,
            registry=self._registry,
            format_checker=FormatChecker(),
        )

    def _schema_contents(self, relative_path: str) -> dict[str, Any]:
        path = self.contract_root / relative_path
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AIResponseValidationError(
                f"AI 계약 파일을 읽을 수 없습니다: {relative_path}",
            ) from exc

    def _validation_errors(
        self,
        kind: str,
        payload: dict[str, Any],
    ) -> list[str]:
        errors = sorted(
            self._validators[kind].iter_errors(payload),
            key=lambda error: list(error.absolute_path),
        )
        return [self._format_error(error) for error in errors]

    @staticmethod
    def _format_error(error: Any) -> str:
        location = ".".join(str(item) for item in error.absolute_path)
        return f"{location or '$'}: {error.message}"
