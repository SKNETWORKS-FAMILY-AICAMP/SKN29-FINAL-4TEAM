"""Source-based selection regressions; the 45-case judgment Oracle is not used."""

from collections import Counter
from hashlib import sha256
import json

import pytest

from ai.app.retrieval.filters import canonical_topics, evidence_topic_filter
from ai.app.retrieval.filters.canonical_topics import canonical_v2_topic
from ai.app.retrieval.filters.evidence_applicability_gate import EvidenceApplicability
from ai.app.retrieval.filters.evidence_topic_filter import EvidenceTopicFilter
from ai.app.retrieval.filters.scenario_evidence_selector import ScenarioEvidenceSelector
from ai.app.retrieval.indexing.chunk_loader import ChunkLoader
from ai.app.retrieval.runtime_profile import REPOSITORY_ROOT, resolve_rag_runtime_profile
from ai.app.schemas import StructuredSymptom


@pytest.fixture(scope="module")
def view_chunks():
    """Simulated readonly View metadata; does not import candidates into a DB."""
    profile = resolve_rag_runtime_profile("three_model_integration")
    return [chunk.model_copy(update={
        "index_version": profile.expected_index_version,
        "chunk_set_sha256": profile.expected_chunk_set_sha256,
        "runtime_eligible": True, "record_type": None, "topic_code": None,
    }) for chunk in ChunkLoader.from_handoff_profile("rag-expansion").load_verified_chunks()]


def select(chunks, raw, *, symptom="온도 이상", applicability=None):
    return ScenarioEvidenceSelector().select_chunks(
        chunks, raw_symptom=raw, applicability=applicability,
        structured_symptom=StructuredSymptom(symptom_type=symptom, target_water_type="온수"),
    )


def test_derived_topic_catalog_matches_verified_source_registry(view_chunks):
    registry = REPOSITORY_ROOT / "data/processed/structured/evidence/rag_evidence_groups_3model_v1.jsonl"
    groups = {row["evidence_group_id"]: row for row in
              (json.loads(line) for line in registry.read_text(encoding="utf-8").splitlines() if line.strip())}
    catalog = json.loads((REPOSITORY_ROOT / "ai/configs/canonical_evidence_topics_3model.json").read_bytes())
    normalized_registry = registry.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    assert sha256(normalized_registry).hexdigest() == catalog["source_registry_sha256"]
    assert len(catalog["chunks"]) == len(view_chunks) == 53
    assert Counter(c.model_code for c in view_chunks) == {
        "WPUJAC104DWH": 15, "WPUIAC425SNW": 19, "WPUIAC606SNW": 19,
    }
    for chunk in view_chunks:
        assert canonical_v2_topic(chunk) == groups[chunk.evidence_group_id]["topic_code"]


def test_v2_filter_does_not_require_unshipped_mvp_source(monkeypatch, view_chunks):
    def missing_mvp():
        raise FileNotFoundError("MVP dataset is not in the deployment image")
    monkeypatch.setattr(evidence_topic_filter, "_canonical_topic_by_chunk_id", missing_mvp)
    actual = EvidenceTopicFilter().filter_chunks(
        view_chunks, symptom_type="온도 이상", target_water_type="온수",
    )
    assert actual
    assert all("HOT" in chunk.chunk_id for chunk in actual)


@pytest.mark.parametrize("field,value", [
    ("chunk_id", "UNKNOWN"), ("model_code", "OTHER"), ("product_generation", "OTHER"),
    ("document_id", "OTHER"), ("page_refs", [999]), ("content", "changed source"),
    ("source_hash", "0" * 64), ("chunk_set_sha256", "0" * 64),
    ("verification_status", "unverified"), ("allowed_use", False), ("runtime_eligible", False),
    ("record_type", "PARENT"), ("retrieval_role", "CONTEXT_ONLY"), ("evidence_group_id", "OTHER"),
])
def test_topic_identity_rejects_tampered_or_non_child_rows(view_chunks, field, value):
    assert canonical_v2_topic(view_chunks[0].model_copy(update={field: value})) is None


@pytest.mark.parametrize("model", ["WPUJAC104DWH", "WPUIAC425SNW", "WPUIAC606SNW"])
@pytest.mark.parametrize("raw,fragment", [
    ("온수에서 스팀이 분사돼요", "STEAM"),
    ("온수를 받을 때 물이 끊겨요", "INTERRUPTION"),
    ("온수가 나오다가 중단됐어요", "CHECK-PROCESS|STOPPED"),
])
def test_hot_scenarios_select_corresponding_verified_child(view_chunks, model, raw, fragment):
    candidates = [chunk for chunk in view_chunks if chunk.model_code == model and "HOT" in chunk.chunk_id]
    result = select(candidates, raw)
    assert len(result.chunks) == 1
    assert any(part in result.chunks[0].chunk_id for part in fragment.split("|"))
    assert all("잠금" not in chunk.content and "1L" not in chunk.content for chunk in result.chunks)


def test_lukewarm_does_not_inherit_fault_consultation_but_keeps_hot_water_warning(view_chunks):
    chunks = [c for c in view_chunks if c.model_code == "WPUJAC104DWH" and "HOT" in c.chunk_id]
    result = select(chunks, "온수가 미지근합니다")
    assert [c.chunk_id for c in result.chunks] == ["CHILD-WPUJAC104DWH-P039-HOT-LUKEWARM-001"]
    text = result.chunks[0].content
    assert "두번째 잔" in text and "10초" in text and "조심하세요" in text
    assert "히터의 고장" not in text and "고객상담센터" not in text
    assert "스팀" not in text and "잠금" not in text and "음용하지" not in text


def test_module_warning_keeps_consultation_and_no_drinking_in_source_order(view_chunks):
    chunks = [c for c in view_chunks if c.model_code == "WPUJAC104DWH" and "HOT" in c.chunk_id]
    result = select(chunks, "LCD에 순간온수 모듈 점검이라는 문구가 표시돼요")
    assert [c.chunk_id for c in result.chunks] == ["CHILD-WPUJAC104DWH-P039-HOT-MODULE-CHECK-001"]
    text = " ".join(c.content for c in result.chunks)
    assert "음용하지" in text and "고객상담센터" in text
    assert "두번째 잔" not in text and "10초" not in text


@pytest.mark.parametrize("raw", [
    "스팀은 없지만 온수에서 물 끊김이 있어요",
    "온수에서 증기는 나지 않는데 물이 끊겨요",
])
def test_negated_hot_scenario_does_not_override_asserted_one(view_chunks, raw):
    result = select([c for c in view_chunks if c.model_code == "WPUJAC104DWH"], raw)
    assert result.chunks
    assert all("INTERRUPTION" in chunk.chunk_id for chunk in result.chunks)


def test_unconfirmed_hot_condition_has_no_scenario_evidence(view_chunks):
    assert not select(view_chunks, "온수가 이상해요").chunks
    assert not select(view_chunks, "온수가 안 나오는 건 아니에요").chunks


@pytest.mark.parametrize("model", ["WPUJAC104DWH", "WPUIAC425SNW", "WPUIAC606SNW"])
def test_hot_no_output_keeps_unlock_condition_and_following_consultation(view_chunks, model):
    result = select([c for c in view_chunks if c.model_code == model], "온수가 전혀 안 나와요")
    assert len(result.chunks) == 1
    text = result.chunks[0].content
    assert "잠금" in text and "고객상담센터" in text
    assert "히터의 고장" not in text and "두번째 잔" not in text and "스팀" not in text


def test_hot_low_flow_keeps_generic_verified_flow_evidence(view_chunks):
    source = [c for c in view_chunks if c.model_code == "WPUJAC104DWH"]
    candidates = EvidenceTopicFilter().filter_chunks(source, raw_symptom="온수가 졸졸 나와요",
                        symptom_type="출수량 저하", target_water_type="온수")
    result = select(candidates, "온수가 졸졸 나와요", symptom="출수량 저하")
    assert [c.chunk_id for c in result.chunks] == ["CHILD-WPUJAC104DWH-P038-LOW-FLOW-001"]


@pytest.mark.parametrize("applicability,required,excluded", [
    (EvidenceApplicability.ABSENCE_WITHIN_10_DAYS, "1L", "점검을 요구"),
    (EvidenceApplicability.ABSENCE_OVER_10_DAYS, "점검을 요구", "1L"),
    (EvidenceApplicability.LONG_UNUSED, "필터를 모두 교체", "1L"),
    (EvidenceApplicability.UNSUITABLE_INSTALLATION, "필터를 모두 교체", "1L"),
])
def test_taste_selection_keeps_only_verified_applicable_action(view_chunks, applicability, required, excluded):
    source = next(c for c in view_chunks if c.chunk_id == "CHILD-WPUJAC104DWH-P038-TASTE-ODOR-001")
    result = select([source], "물맛이 이상해요", symptom="물맛/냄새 이상", applicability=applicability)
    assert len(result.chunks) == 1
    assert required in result.chunks[0].content and excluded not in result.chunks[0].content


def test_taste_source_without_matching_condition_is_not_used(view_chunks):
    source = next(c for c in view_chunks if c.chunk_id == "CHILD-WPUJAC104DWH-P038-TASTE-ODOR-001")
    source = source.model_copy(update={"content": "장기(10일 이상) : 필요 시 고객상담센터에 점검을 요구해 주세요."})
    assert not select([source], "물맛이 이상해요", symptom="물맛/냄새 이상",
                      applicability=EvidenceApplicability.ABSENCE_WITHIN_10_DAYS).chunks
