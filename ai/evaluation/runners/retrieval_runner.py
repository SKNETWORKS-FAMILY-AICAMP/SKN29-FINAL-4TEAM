"""검색 원문·근거 본문을 노출하지 않는 Retrieval 품질 평가 실행기."""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import Counter
from pathlib import Path
from typing import Any, Literal, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai.app.retrieval import RetrievalQuery
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk
from ai.evaluation.metrics import calculate_mrr, calculate_recall_at_k


class RetrievalSearchService(Protocol):
    def search(
        self,
        query: RetrievalQuery,
        *,
        cancellation_token: object | None = None,
    ) -> Sequence[RetrievedChunk]: ...


class _EvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RetrievalEvaluationPolicy(_EvaluationModel):
    default_top_k: int = Field(ge=1, le=20)
    positive_min_expected_hits: int = Field(ge=1)
    negative_max_forbidden_hits: int = Field(ge=0)
    required_result_metadata: list[str]


class RetrievalQualityCase(_EvaluationModel):
    case_id: str = Field(min_length=1, max_length=100)
    case_type: Literal["POSITIVE", "NEGATIVE_SCOPE", "NEGATIVE_SOURCE"]
    scenario_id: str | None
    query: str = Field(min_length=1, max_length=4000)
    product_model_code: str = Field(min_length=1, max_length=100)
    expected_chunk_ids: list[str]
    expected_document_id: str | None
    expected_page_numbers: list[int]
    forbidden_model_codes: list[str]
    forbidden_document_ids: list[str]
    top_k: int = Field(ge=1, le=20)
    expected_no_evidence: bool

    @model_validator(mode="after")
    def validate_case_semantics(self) -> "RetrievalQualityCase":
        if self.case_type == "POSITIVE":
            if self.expected_no_evidence or not self.expected_chunk_ids:
                raise ValueError("양성 Retrieval Case에는 기대 청크가 필요합니다.")
        elif not self.expected_no_evidence or self.expected_chunk_ids:
            raise ValueError("음성 Retrieval Case는 빈 기대 청크를 사용해야 합니다.")
        return self


class RetrievalQualityDataset(_EvaluationModel):
    config_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    status: str = Field(min_length=1, max_length=100)
    approved_chunk_count: int = Field(ge=0)
    evaluation_policy: RetrievalEvaluationPolicy
    cases: list[RetrievalQualityCase] = Field(min_length=1)
    ai_execution: dict[str, Any]

    @model_validator(mode="after")
    def validate_unique_case_ids(self) -> "RetrievalQualityDataset":
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("Retrieval 평가 case_id는 중복될 수 없습니다.")
        mismatched_top_k = [
            case.case_id
            for case in self.cases
            if case.top_k != self.evaluation_policy.default_top_k
        ]
        if mismatched_top_k:
            raise ValueError(
                "Retrieval Case top_k는 evaluation_policy.default_top_k와 "
                "일치해야 합니다."
            )
        return self


class RetrievalEvaluationRunner:
    """Recall·음성 차단·제품 오염·지연시간을 분리해 평가한다."""

    DEFAULT_DATASET_PATH = (
        Path(__file__).resolve().parents[3]
        / "data"
        / "config"
        / "rag"
        / "jac104_retrieval_cases.json"
    )

    def __init__(
        self,
        search_service: RetrievalSearchService | None = None,
        dataset_path: str | Path | None = None,
    ) -> None:
        self.search_service = search_service
        self.dataset_path = Path(dataset_path or self.DEFAULT_DATASET_PATH).resolve()

    def load_dataset(self) -> RetrievalQualityDataset:
        if not self.dataset_path.is_file():
            raise FileNotFoundError(
                f"Retrieval 평가 기준본이 없습니다: {self.dataset_path}"
            )
        payload = json.loads(self.dataset_path.read_text(encoding="utf-8"))
        return RetrievalQualityDataset.model_validate(payload)

    def run(self) -> dict[str, object]:
        dataset = self.load_dataset()
        dataset_metadata = self._dataset_metadata(dataset)
        if self.search_service is None:
            return {
                "status": "NOT_RUN",
                "reason": "승인된 Retrieval Search Service가 설정되지 않았습니다.",
                "evaluation_scope": "retrieval_runtime_not_executed",
                "dataset": dataset_metadata,
                "summary": {
                    "case_count": len(dataset.cases),
                    "positive_case_count": self._positive_case_count(dataset),
                    "negative_case_count": self._negative_case_count(dataset),
                    "search_call_count": 0,
                    "mean_recall_at_5": None,
                    "mean_mrr": None,
                    "negative_no_evidence_rate": None,
                    "wrong_model_evidence_rate": None,
                    "product_contamination_rate": None,
                    "latency": None,
                },
                "cases": [],
                "total_cases": len(dataset.cases),
                "mean_recall_at_5": None,
                "mean_mrr": None,
                **self._disclosure_flags(search_service_called=False),
            }

        case_results = [self._evaluate_case(case, dataset) for case in dataset.cases]
        summary = self._summarize(case_results)
        return {
            "status": "PASS" if summary["failed_count"] == 0 else "FAIL",
            "evaluation_scope": "configured_retrieval_search_service",
            "dataset": dataset_metadata,
            "summary": summary,
            "cases": case_results,
            "total_cases": summary["case_count"],
            "mean_recall_at_5": summary["mean_recall_at_5"],
            "mean_mrr": summary["mean_mrr"],
            **self._disclosure_flags(search_service_called=True),
        }

    def _evaluate_case(
        self,
        case: RetrievalQualityCase,
        dataset: RetrievalQualityDataset,
    ) -> dict[str, object]:
        effective_top_k = dataset.evaluation_policy.default_top_k
        query = RetrievalQuery(
            query_text=case.query,
            model_code=case.product_model_code,
            top_k=effective_top_k,
        )
        execution_path = self._execution_path(query)
        started_at = time.perf_counter()
        try:
            chunks = list(self.search_service.search(query))
        except Exception as exc:  # 평가 리포트에는 예외 본문을 기록하지 않는다.
            latency_ms = round((time.perf_counter() - started_at) * 1000.0, 3)
            return {
                "case_id": case.case_id,
                "case_type": case.case_type,
                "execution_path": execution_path,
                "latency_ms": latency_ms,
                "result_count": 0,
                "expected_hit_count": 0,
                "recall_at_k": None,
                "mrr": None,
                "no_evidence_passed": None,
                "wrong_model_hit_count": 0,
                "forbidden_document_hit_count": 0,
                "product_contamination_hit_count": 0,
                "invalid_evidence_hit_count": 0,
                "expected_document_mismatch_count": 0,
                "expected_page_mismatch_count": 0,
                "missing_required_metadata_count": len(
                    dataset.evaluation_policy.required_result_metadata
                ),
                "effective_top_k": dataset.evaluation_policy.default_top_k,
                "top_k_exceeded": False,
                "error_type": type(exc).__name__,
                "passed": False,
            }
        latency_ms = round((time.perf_counter() - started_at) * 1000.0, 3)

        retrieved_ids = [chunk.chunk_id for chunk in chunks]
        expected_ids = set(case.expected_chunk_ids)
        expected_hit_count = len(
            expected_ids.intersection(retrieved_ids[:effective_top_k])
        )
        wrong_model_indexes = {
            index
            for index, chunk in enumerate(chunks)
            if chunk.model_code != case.product_model_code
            or chunk.model_code in case.forbidden_model_codes
        }
        forbidden_document_indexes = {
            index
            for index, chunk in enumerate(chunks)
            if chunk.document_id in case.forbidden_document_ids
        }
        contamination_indexes = wrong_model_indexes | forbidden_document_indexes
        invalid_evidence_indexes = {
            index
            for index, chunk in enumerate(chunks)
            if chunk.verification_status != "official_verified" or not chunk.allowed_use
        }
        expected_document_mismatch_count = sum(
            1
            for chunk in chunks
            if chunk.chunk_id in expected_ids
            and case.expected_document_id is not None
            and chunk.document_id != case.expected_document_id
        )
        expected_hit_chunks = [
            chunk
            for chunk in chunks[:effective_top_k]
            if chunk.chunk_id in expected_ids
        ]
        returned_page_numbers = {
            page_number
            for chunk in expected_hit_chunks
            for page_number in ([chunk.page] if chunk.page is not None else [])
            + list(chunk.page_refs)
        }
        expected_page_mismatch_count = len(
            set(case.expected_page_numbers) - returned_page_numbers
        )
        missing_required_metadata_count = len(
            self._missing_required_metadata(
                chunks=chunks,
                execution_path=execution_path,
                required=dataset.evaluation_policy.required_result_metadata,
            )
        )

        if case.expected_no_evidence:
            recall_at_k = None
            mrr = None
            no_evidence_passed = len(chunks) == 0
            passed = (
                no_evidence_passed
                and len(contamination_indexes)
                <= dataset.evaluation_policy.negative_max_forbidden_hits
                and not invalid_evidence_indexes
                and missing_required_metadata_count == 0
            )
        else:
            recall_at_k = calculate_recall_at_k(
                retrieved_ids,
                case.expected_chunk_ids,
                k=effective_top_k,
            )
            mrr = calculate_mrr(
                retrieved_ids[:effective_top_k], case.expected_chunk_ids
            )
            no_evidence_passed = None
            passed = (
                expected_hit_count
                >= dataset.evaluation_policy.positive_min_expected_hits
                and not contamination_indexes
                and not invalid_evidence_indexes
                and expected_document_mismatch_count == 0
                and expected_page_mismatch_count == 0
                and missing_required_metadata_count == 0
                and len(chunks) <= effective_top_k
            )

        return {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "execution_path": execution_path,
            "latency_ms": latency_ms,
            "result_count": len(chunks),
            "expected_hit_count": expected_hit_count,
            "recall_at_k": round(recall_at_k, 4) if recall_at_k is not None else None,
            "mrr": round(mrr, 4) if mrr is not None else None,
            "no_evidence_passed": no_evidence_passed,
            "wrong_model_hit_count": len(wrong_model_indexes),
            "forbidden_document_hit_count": len(forbidden_document_indexes),
            "product_contamination_hit_count": len(contamination_indexes),
            "invalid_evidence_hit_count": len(invalid_evidence_indexes),
            "expected_document_mismatch_count": expected_document_mismatch_count,
            "expected_page_mismatch_count": expected_page_mismatch_count,
            "missing_required_metadata_count": missing_required_metadata_count,
            "effective_top_k": effective_top_k,
            "top_k_exceeded": len(chunks) > effective_top_k,
            "error_type": None,
            "passed": passed,
        }

    @staticmethod
    def _missing_required_metadata(
        *,
        chunks: Sequence[RetrievedChunk],
        execution_path: str,
        required: Sequence[str],
    ) -> set[str]:
        """필수 Metadata의 값은 노출하지 않고 누락 여부만 계산한다."""

        chunk_attributes = {
            "embedding_model": "embedding_model",
            "embedding_model_version": "embedding_model_revision",
            "chunk_set_sha256": "chunk_set_sha256",
            "index_version": "index_version",
        }
        structurally_available = {"ranked_chunk_ids", "recall_at_k", "mrr"}
        missing: set[str] = set()
        for metadata_name in required:
            attribute_name = chunk_attributes.get(metadata_name)
            if attribute_name is not None:
                if chunks and any(
                    not getattr(chunk, attribute_name, None) for chunk in chunks
                ):
                    missing.add(metadata_name)
                continue
            if metadata_name == "filter":
                if execution_path in {"UNAVAILABLE", "EXECUTION_PATH_ERROR"}:
                    missing.add(metadata_name)
                continue
            if metadata_name not in structurally_available:
                missing.add(metadata_name)
        return missing

    def _execution_path(self, query: RetrievalQuery) -> str:
        resolver = getattr(self.search_service, "execution_path", None)
        if not callable(resolver):
            return "UNAVAILABLE"
        try:
            value = str(resolver(query))
        except Exception:
            return "EXECUTION_PATH_ERROR"
        return value if value else "UNAVAILABLE"

    @staticmethod
    def _summarize(case_results: list[dict[str, object]]) -> dict[str, object]:
        positive = [case for case in case_results if case["case_type"] == "POSITIVE"]
        negative = [case for case in case_results if case["case_type"] != "POSITIVE"]
        latencies = [float(case["latency_ms"]) for case in case_results]
        retrieved_count = sum(int(case["result_count"]) for case in case_results)
        wrong_model_count = sum(
            int(case["wrong_model_hit_count"]) for case in case_results
        )
        contamination_count = sum(
            int(case["product_contamination_hit_count"]) for case in case_results
        )
        positive_recalls = [
            float(case["recall_at_k"])
            for case in positive
            if case["recall_at_k"] is not None
        ]
        positive_mrrs = [
            float(case["mrr"])
            for case in positive
            if case["mrr"] is not None
        ]
        passed_count = sum(case["passed"] is True for case in case_results)
        return {
            "case_count": len(case_results),
            "passed_count": passed_count,
            "failed_count": len(case_results) - passed_count,
            "positive_case_count": len(positive),
            "positive_passed_count": sum(case["passed"] is True for case in positive),
            "negative_case_count": len(negative),
            "negative_passed_count": sum(case["passed"] is True for case in negative),
            "mean_recall_at_5": RetrievalEvaluationRunner._mean(positive_recalls),
            "mean_mrr": RetrievalEvaluationRunner._mean(positive_mrrs),
            "negative_no_evidence_rate": RetrievalEvaluationRunner._rate(
                sum(case["no_evidence_passed"] is True for case in negative),
                len(negative),
            ),
            "retrieved_hit_count": retrieved_count,
            "wrong_model_hit_count": wrong_model_count,
            "wrong_model_evidence_rate": RetrievalEvaluationRunner._rate(
                wrong_model_count,
                retrieved_count,
            ),
            "product_contamination_hit_count": contamination_count,
            "product_contamination_rate": RetrievalEvaluationRunner._rate(
                contamination_count,
                retrieved_count,
            ),
            "invalid_evidence_hit_count": sum(
                int(case["invalid_evidence_hit_count"]) for case in case_results
            ),
            "expected_page_mismatch_count": sum(
                int(case["expected_page_mismatch_count"]) for case in case_results
            ),
            "missing_required_metadata_count": sum(
                int(case["missing_required_metadata_count"])
                for case in case_results
            ),
            "search_error_count": sum(case["error_type"] is not None for case in case_results),
            "search_call_count": len(case_results),
            "execution_path_counts": dict(
                sorted(Counter(str(case["execution_path"]) for case in case_results).items())
            ),
            "latency": RetrievalEvaluationRunner._latency_summary(latencies),
        }

    def _dataset_metadata(self, dataset: RetrievalQualityDataset) -> dict[str, object]:
        approval_scope = dataset.ai_execution.get("approval_scope")
        return {
            "config_version": dataset.config_version,
            "source_status": dataset.status,
            "approval_scope": (
                str(approval_scope) if approval_scope is not None else "UNSPECIFIED"
            ),
            "approved_chunk_count": dataset.approved_chunk_count,
            "path": self._report_path(self.dataset_path),
            "file_sha256": hashlib.sha256(self.dataset_path.read_bytes()).hexdigest().upper(),
        }

    @staticmethod
    def _positive_case_count(dataset: RetrievalQualityDataset) -> int:
        return sum(case.case_type == "POSITIVE" for case in dataset.cases)

    @staticmethod
    def _negative_case_count(dataset: RetrievalQualityDataset) -> int:
        return sum(case.case_type != "POSITIVE" for case in dataset.cases)

    @staticmethod
    def _mean(values: Sequence[float]) -> float | None:
        return round(sum(values) / len(values), 4) if values else None

    @staticmethod
    def _rate(numerator: int, denominator: int) -> float | None:
        return round(numerator / denominator, 4) if denominator else None

    @staticmethod
    def _percentile(values: Sequence[float], percentile: float) -> float:
        ordered = sorted(float(value) for value in values)
        position = (len(ordered) - 1) * (percentile / 100)
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            return ordered[lower]
        weight = position - lower
        return ordered[lower] * (1 - weight) + ordered[upper] * weight

    @staticmethod
    def _latency_summary(values: Sequence[float]) -> dict[str, float | int]:
        return {
            "sample_count": len(values),
            "mean_ms": round(sum(values) / len(values), 3),
            "p50_ms": round(RetrievalEvaluationRunner._percentile(values, 50), 3),
            "p95_ms": round(RetrievalEvaluationRunner._percentile(values, 95), 3),
            "max_ms": round(max(values), 3),
        }

    @staticmethod
    def _disclosure_flags(*, search_service_called: bool) -> dict[str, bool]:
        return {
            "search_service_called": search_service_called,
            "query_text_printed": False,
            "evidence_content_printed": False,
            "vector_values_printed": False,
            "secret_values_printed": False,
        }

    @staticmethod
    def _report_path(path: Path) -> str:
        repository_root = Path(__file__).resolve().parents[3]
        try:
            return path.relative_to(repository_root).as_posix()
        except ValueError:
            return path.name


__all__ = [
    "RetrievalEvaluationRunner",
    "RetrievalEvaluationPolicy",
    "RetrievalQualityCase",
    "RetrievalQualityDataset",
]
