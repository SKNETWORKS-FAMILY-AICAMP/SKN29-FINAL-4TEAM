"""Clarification-only retrieval over the isolated synthetic scenario dataset."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from typing import Any

from ..schemas import FollowUpQuestion, StructuredSymptom
from .filters import EvidenceApplicabilityGate


_CANONICAL_QUESTION_IDS = {
    "target_water_type": "followup-target-water-type",
    "occurrence_condition": "followup-occurrence-condition",
    "actions_taken": "followup-actions-taken",
    "occurrence_time": "followup-occurrence-time",
    "taste_odor_applicability": EvidenceApplicabilityGate.QUESTION_ID,
}
_REQUIRED_POLICY = {
    "knowledge_type": "SYNTHETIC_SCENARIO",
    "clarification_only": True,
    "evidence_eligible": False,
    "customer_citation_allowed": False,
    "official_evidence": False,
    "diagnosis_allowed": False,
}


class SyntheticScenarioDatasetError(RuntimeError):
    """The clarification-only dataset cannot be trusted or loaded."""


@dataclass(frozen=True, slots=True)
class SyntheticScenarioCandidate:
    chunk_id: str
    group_id: str
    scenario_id: str
    symptom_type: str
    discriminators: dict[str, str]


@dataclass(frozen=True, slots=True)
class SyntheticQuestionDefinition:
    source_question_id: str
    question_text: str
    target_field: str
    options: tuple[str, ...]

    def to_runtime_question(self) -> FollowUpQuestion:
        question_id = _CANONICAL_QUESTION_IDS.get(self.target_field)
        if question_id is None:
            raise SyntheticScenarioDatasetError(
                f"Unsupported synthetic question target: {self.target_field}"
            )
        return FollowUpQuestion(
            question_id=question_id,
            question_text=self.question_text,
            options=list(self.options),
            target_field=self.target_field,
        )


@dataclass(frozen=True, slots=True)
class SyntheticScenarioGroup:
    group_id: str
    symptom_type: str
    questions: tuple[SyntheticQuestionDefinition, ...]


@dataclass(frozen=True, slots=True)
class SyntheticScenarioSearchResult:
    candidates: tuple[SyntheticScenarioCandidate, ...] = ()
    question: FollowUpQuestion | None = None
    source_question_id: str | None = None
    reason: str = "NO_SYNTHETIC_SCENARIO"


class SyntheticScenarioRetriever:
    """Search a physically separate, clarification-only scenario catalog.

    The result type intentionally cannot be converted to ``EvidenceReference``.
    It contains only identifiers and discriminators needed to choose one
    deterministic question.
    """

    def __init__(
        self,
        *,
        scenario_path: Path | None = None,
        candidate_path: Path | None = None,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[3]
        self.scenario_path = scenario_path or self._first_existing(
            repository_root
            / "data"
            / "synthetic"
            / "scenarios"
            / "synthetic_troubleshooting_scenarios_v1.json",
            repository_root
            / "data"
            / "synthetic"
            / "expected"
            / "synthetic_troubleshooting_scenarios_v1.json",
        )
        self.candidate_path = candidate_path or (
            repository_root
            / "data"
            / "synthetic"
            / "candidates"
            / "synthetic_troubleshooting_chunks_v1.jsonl"
        )
        self.groups, self.candidates = self._load()

    def search(
        self,
        *,
        structured_symptom: StructuredSymptom | None,
        previous_answers: list[dict[str, str]],
    ) -> SyntheticScenarioSearchResult:
        if structured_symptom is None:
            return SyntheticScenarioSearchResult()
        group = next(
            (
                item
                for item in self.groups
                if item.symptom_type == structured_symptom.symptom_type
            ),
            None,
        )
        if group is None:
            return SyntheticScenarioSearchResult()

        known = self._known_discriminators(
            structured_symptom=structured_symptom,
            previous_answers=previous_answers,
        )
        candidates = tuple(
            candidate
            for candidate in self.candidates
            if candidate.group_id == group.group_id
            and all(
                field not in candidate.discriminators
                or candidate.discriminators[field] == value
                for field, value in known.items()
            )
        )
        if not candidates:
            return SyntheticScenarioSearchResult(reason="NO_MATCHING_CANDIDATE")

        if group.symptom_type == "물맛/냄새 이상":
            gate = EvidenceApplicabilityGate()
            question = gate.followup_question(
                symptom_type=group.symptom_type,
                previous_answers=previous_answers,
            )
            if question is not None:
                return SyntheticScenarioSearchResult(
                    candidates=candidates,
                    question=question,
                    source_question_id=self._source_question_id(
                        group,
                        gate.TARGET_FIELD,
                    ),
                    reason="SCENARIO_AMBIGUOUS",
                )

        for definition in group.questions:
            if self._has_known_value(definition.target_field, known):
                continue
            distinct_values = {
                candidate.discriminators[definition.target_field]
                for candidate in candidates
                if definition.target_field in candidate.discriminators
            }
            if len(distinct_values) < 2:
                continue
            return SyntheticScenarioSearchResult(
                candidates=candidates,
                question=definition.to_runtime_question(),
                source_question_id=definition.source_question_id,
                reason="SCENARIO_AMBIGUOUS",
            )

        return SyntheticScenarioSearchResult(
            candidates=candidates,
            reason=(
                "SCENARIO_RESOLVED"
                if len(candidates) == 1
                else "NO_INFORMATION_GAINING_QUESTION"
            ),
        )

    def _load(
        self,
    ) -> tuple[
        tuple[SyntheticScenarioGroup, ...],
        tuple[SyntheticScenarioCandidate, ...],
    ]:
        try:
            dataset = json.loads(self.scenario_path.read_text(encoding="utf-8"))
            candidate_rows = [
                json.loads(line)
                for line in self.candidate_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except (OSError, json.JSONDecodeError) as exc:
            raise SyntheticScenarioDatasetError(
                "Synthetic clarification dataset could not be loaded."
            ) from exc

        global_policy = dataset.get("global_policy")
        if not isinstance(global_policy, dict):
            raise SyntheticScenarioDatasetError("Synthetic global policy is missing.")
        self._validate_policy(global_policy)

        raw_groups = dataset.get("groups")
        if not isinstance(raw_groups, list) or not raw_groups:
            raise SyntheticScenarioDatasetError("Synthetic groups are missing.")
        groups = tuple(self._parse_group(item) for item in raw_groups)

        candidates: list[SyntheticScenarioCandidate] = []
        for row in candidate_rows:
            metadata = row.get("metadata")
            if not isinstance(metadata, dict):
                raise SyntheticScenarioDatasetError(
                    "Synthetic candidate metadata is missing."
                )
            self._validate_policy(metadata)
            discriminators = metadata.get("discriminators")
            if not isinstance(discriminators, dict):
                raise SyntheticScenarioDatasetError(
                    "Synthetic candidate discriminators are invalid."
                )
            candidate = SyntheticScenarioCandidate(
                chunk_id=self._required_text(row, "chunk_id"),
                group_id=self._required_text(metadata, "group_id"),
                scenario_id=self._required_text(metadata, "scenario_id"),
                symptom_type=self._required_text(metadata, "symptom_type"),
                discriminators={
                    str(key): str(value)
                    for key, value in discriminators.items()
                    if str(key).strip() and str(value).strip()
                },
            )
            if not candidate.chunk_id.startswith("syn-scn-"):
                raise SyntheticScenarioDatasetError(
                    "Synthetic candidate chunk identity is invalid."
                )
            candidates.append(candidate)

        expected_count = dataset.get("scenario_count")
        if expected_count != len(candidates):
            raise SyntheticScenarioDatasetError(
                "Synthetic scenario and candidate counts do not match."
            )
        group_ids = {group.group_id for group in groups}
        if any(candidate.group_id not in group_ids for candidate in candidates):
            raise SyntheticScenarioDatasetError(
                "Synthetic candidate references an unknown group."
            )
        return groups, tuple(candidates)

    @classmethod
    def _parse_group(cls, value: Any) -> SyntheticScenarioGroup:
        if not isinstance(value, dict):
            raise SyntheticScenarioDatasetError("Synthetic group is invalid.")
        questions: list[SyntheticQuestionDefinition] = []
        for key in ("primary_question", "secondary_question"):
            question = value.get(key)
            if not question:
                continue
            if not isinstance(question, dict):
                raise SyntheticScenarioDatasetError(
                    "Synthetic question definition is invalid."
                )
            options = question.get("options")
            if not isinstance(options, list) or not options:
                raise SyntheticScenarioDatasetError(
                    "Synthetic question options are invalid."
                )
            questions.append(
                SyntheticQuestionDefinition(
                    source_question_id=cls._required_text(question, "question_id"),
                    question_text=cls._required_text(question, "question_text"),
                    target_field=cls._required_text(question, "target_field"),
                    options=tuple(str(item).strip() for item in options),
                )
            )
        return SyntheticScenarioGroup(
            group_id=cls._required_text(value, "group_id"),
            symptom_type=cls._required_text(value, "symptom_type"),
            questions=tuple(questions),
        )

    @staticmethod
    def _known_discriminators(
        *,
        structured_symptom: StructuredSymptom,
        previous_answers: list[dict[str, str]],
    ) -> dict[str, str]:
        known: dict[str, str] = {}
        for field in (
            "target_water_type",
            "occurrence_condition",
            "occurrence_time",
        ):
            value = getattr(structured_symptom, field, None)
            if value:
                known[field] = str(value)
        if structured_symptom.actions_taken:
            known["actions_taken"] = " / ".join(structured_symptom.actions_taken)
        for answer in previous_answers:
            if not isinstance(answer, dict):
                continue
            question_id = str(answer.get("question_id", ""))
            target_field = next(
                (
                    field
                    for field, canonical_id in _CANONICAL_QUESTION_IDS.items()
                    if canonical_id == question_id
                ),
                None,
            )
            answer_text = str(answer.get("answer_text", "")).strip()
            if target_field and answer_text:
                known[target_field] = answer_text
        return known

    @staticmethod
    def _has_known_value(field: str, known: dict[str, str]) -> bool:
        return bool(known.get(field, "").strip())

    @staticmethod
    def _source_question_id(
        group: SyntheticScenarioGroup,
        target_field: str,
    ) -> str | None:
        return next(
            (
                item.source_question_id
                for item in group.questions
                if item.target_field == target_field
            ),
            None,
        )

    @staticmethod
    def _required_text(value: dict[str, Any], key: str) -> str:
        item = value.get(key)
        if not isinstance(item, str) or not item.strip():
            raise SyntheticScenarioDatasetError(
                f"Synthetic dataset field is invalid: {key}"
            )
        return item.strip()

    @staticmethod
    def _validate_policy(value: dict[str, Any]) -> None:
        for key, expected in _REQUIRED_POLICY.items():
            if value.get(key) != expected:
                raise SyntheticScenarioDatasetError(
                    f"Synthetic policy must keep {key}={expected!r}."
                )

    @staticmethod
    def _first_existing(*paths: Path) -> Path:
        return next((path for path in paths if path.is_file()), paths[0])


@lru_cache(maxsize=1)
def get_synthetic_scenario_retriever() -> SyntheticScenarioRetriever:
    return SyntheticScenarioRetriever()


__all__ = [
    "SyntheticScenarioCandidate",
    "SyntheticScenarioDatasetError",
    "SyntheticScenarioRetriever",
    "SyntheticScenarioSearchResult",
    "get_synthetic_scenario_retriever",
]
