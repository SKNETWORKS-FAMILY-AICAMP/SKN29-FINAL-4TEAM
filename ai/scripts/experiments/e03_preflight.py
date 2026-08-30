from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi
from transformers import AutoTokenizer


ROOT = Path(__file__).resolve().parents[3]

E02_PREFLIGHT_PATH = ROOT / ".runtime/e02_v2/preflight.json"
E02_MANIFEST_PATH = ROOT / ".runtime/e02_v2/manifest.json"
E02_RESULT_PATH = ROOT / ".runtime/e02_v2/results/summary.json"
PARENT_CHILD_PATH = ROOT / ".runtime/e02_v2/variants/parent_child_256.jsonl"
E01_CASE_PATH = ROOT / "data/config/rag/three_model_evaluation_cases.json"

OUT_DIR = ROOT / ".runtime/e03_embedding"
OUT_PATH = OUT_DIR / "preflight.json"

TOP_K = 5
EXPECTED_PRIMARY_POSITIVE = 43
EXPECTED_SUPPLEMENTAL_FAQ = 5
EXPECTED_PARENT_CHILD_CHUNKS = 216
EXPECTED_EVIDENCE_GROUPS = 43
EXPECTED_SOURCE_CHILDREN = 53

# E03에서는 "모델 선택"만 바꾼다.
# 모델별 권장 입력 형식은 모델 자체의 사용 계약으로 간주한다.
MODEL_SPECS = [
    {
        "key": "bge_m3",
        "model_id": "BAAI/bge-m3",
        "requested_revision": "5617a9f61b028005a4858fdac845db406aefb181",
        "expected_dimension": 1024,
        "declared_max_tokens": 8192,
        "trust_remote_code": False,
        "query_prefix": "",
        "document_prefix": "",
        "role": "CURRENT_BASELINE",
        "family": "BGE",
    },
    {
        "key": "multilingual_e5_base",
        "model_id": "intfloat/multilingual-e5-base",
        "requested_revision": "main",
        "expected_dimension": 768,
        "declared_max_tokens": 512,
        "trust_remote_code": False,
        "query_prefix": "query: ",
        "document_prefix": "passage: ",
        "role": "MULTILINGUAL_RETRIEVAL_ALTERNATIVE",
        "family": "E5",
    },
    {
        "key": "gte_multilingual_base",
        "model_id": "Alibaba-NLP/gte-multilingual-base",
        "requested_revision": "main",
        "expected_dimension": 768,
        "declared_max_tokens": 8192,
        "trust_remote_code": True,
        "query_prefix": "",
        "document_prefix": "",
        "role": "MULTILINGUAL_RETRIEVAL_ALTERNATIVE",
        "family": "GTE",
    },
]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, raw in enumerate(f, 1):
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception as exc:
                raise RuntimeError(
                    f"{path.relative_to(ROOT)}:{line_no} JSON parse 실패: {exc}"
                ) from exc
            if not isinstance(row, dict):
                raise RuntimeError(
                    f"{path.relative_to(ROOT)}:{line_no} JSON object가 아닙니다."
                )
            rows.append(row)
    return rows


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def git_value(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "NOT_INSTALLED"


def parse_version(value: str) -> tuple[int, ...]:
    if value == "NOT_INSTALLED":
        return ()
    numbers = []
    for part in value.split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        if not digits:
            break
        numbers.append(int(digits))
    return tuple(numbers)


def load_e01_positive_cases() -> list[dict[str, Any]]:
    data = load_json(E01_CASE_PATH)
    if isinstance(data, dict) and isinstance(data.get("cases"), list):
        cases = data["cases"]
    elif isinstance(data, list):
        cases = data
    else:
        raise RuntimeError("E01 Case JSON 구조를 해석하지 못했습니다.")

    positives = [
        row
        for row in cases
        if str(row.get("case_type") or "").upper() == "POSITIVE"
    ]
    return positives


def unique_groups(rows: list[dict[str, Any]]) -> set[str]:
    return {
        str(gid)
        for row in rows
        for gid in (row.get("evidence_group_ids") or [])
        if gid
    }


def unique_source_children(rows: list[dict[str, Any]]) -> set[str]:
    return {
        str(cid)
        for row in rows
        for cid in (row.get("source_child_ids") or [])
        if cid
    }


def resolve_model(
    api: HfApi,
    spec: dict[str, Any],
    *,
    documents: list[str],
    queries: list[str],
) -> dict[str, Any]:
    model_id = spec["model_id"]
    requested_revision = spec["requested_revision"]

    print(f"[E03 Preflight] 모델 확인: {model_id}", flush=True)

    info = api.model_info(
        repo_id=model_id,
        revision=requested_revision,
        files_metadata=True,
    )
    resolved_revision = str(info.sha)

    tokenizer = AutoTokenizer.from_pretrained(
        model_id,
        revision=resolved_revision,
        trust_remote_code=bool(spec["trust_remote_code"]),
        use_fast=True,
    )

    formatted_documents = [
        spec["document_prefix"] + text
        for text in documents
    ]
    formatted_queries = [
        spec["query_prefix"] + text
        for text in queries
    ]

    doc_lengths = [
        len(
            tokenizer(
                text,
                add_special_tokens=False,
                truncation=False,
            )["input_ids"]
        )
        for text in formatted_documents
    ]
    query_lengths = [
        len(
            tokenizer(
                text,
                add_special_tokens=False,
                truncation=False,
            )["input_ids"]
        )
        for text in formatted_queries
    ]

    declared_max = int(spec["declared_max_tokens"])
    overlong_doc_count = sum(length > declared_max for length in doc_lengths)
    overlong_query_count = sum(length > declared_max for length in query_lengths)

    # 다운로드 비용 감을 잡기 위한 safetensors 크기. 여러 shard면 합산.
    safetensor_bytes = 0
    for sibling in info.siblings or []:
        filename = str(getattr(sibling, "rfilename", "") or "")
        size = getattr(sibling, "size", None)
        if filename.endswith(".safetensors") and isinstance(size, int):
            safetensor_bytes += size

    return {
        **spec,
        "resolved_revision": resolved_revision,
        "license": getattr(info, "card_data", None).license
        if getattr(info, "card_data", None)
        else None,
        "safetensors_bytes": safetensor_bytes or None,
        "safetensors_mb": (
            round(safetensor_bytes / 1024 / 1024, 1)
            if safetensor_bytes
            else None
        ),
        "tokenizer_class": tokenizer.__class__.__name__,
        "tokenizer_is_fast": bool(getattr(tokenizer, "is_fast", False)),
        "document_tokens": {
            "min": min(doc_lengths),
            "mean": round(sum(doc_lengths) / len(doc_lengths), 3),
            "max": max(doc_lengths),
            "over_declared_max_count": overlong_doc_count,
        },
        "query_tokens": {
            "min": min(query_lengths),
            "mean": round(sum(query_lengths) / len(query_lengths), 3),
            "max": max(query_lengths),
            "over_declared_max_count": overlong_query_count,
        },
        "truncation_gate": (
            "PASS"
            if overlong_doc_count == 0 and overlong_query_count == 0
            else "FAIL"
        ),
    }


def main() -> int:
    required = [
        E02_PREFLIGHT_PATH,
        E02_MANIFEST_PATH,
        E02_RESULT_PATH,
        PARENT_CHILD_PATH,
        E01_CASE_PATH,
    ]
    missing = [
        str(path.relative_to(ROOT))
        for path in required
        if not path.exists()
    ]
    if missing:
        raise RuntimeError(
            "필수 입력 파일이 없습니다: " + ", ".join(missing)
        )

    errors: list[str] = []
    warnings: list[str] = []

    e02_preflight = load_json(E02_PREFLIGHT_PATH)
    e02_manifest = load_json(E02_MANIFEST_PATH)
    e02_result = load_json(E02_RESULT_PATH)
    parent_child_rows = load_jsonl(PARENT_CHILD_PATH)
    primary_cases = load_e01_positive_cases()

    if e02_preflight.get("status") != "E02_V2_PREFLIGHT_READY":
        errors.append(
            f"E02-v2 Preflight 상태={e02_preflight.get('status')}"
        )
    if e02_manifest.get("status") != "E02_V2_VARIANTS_READY":
        errors.append(
            f"E02-v2 Build 상태={e02_manifest.get('status')}"
        )
    if e02_result.get("status") != "E02_V2_COMPLETE":
        errors.append(
            f"E02-v2 Run 상태={e02_result.get('status')}"
        )

    if len(parent_child_rows) != EXPECTED_PARENT_CHILD_CHUNKS:
        errors.append(
            f"Parent-Child chunks={len(parent_child_rows)}, "
            f"expected={EXPECTED_PARENT_CHILD_CHUNKS}"
        )

    groups = unique_groups(parent_child_rows)
    children = unique_source_children(parent_child_rows)

    if len(groups) != EXPECTED_EVIDENCE_GROUPS:
        errors.append(
            f"Parent-Child Evidence Group={len(groups)}, "
            f"expected={EXPECTED_EVIDENCE_GROUPS}"
        )
    if len(children) != EXPECTED_SOURCE_CHILDREN:
        errors.append(
            f"Parent-Child Source Child={len(children)}, "
            f"expected={EXPECTED_SOURCE_CHILDREN}"
        )
    if len(primary_cases) != EXPECTED_PRIMARY_POSITIVE:
        errors.append(
            f"Primary Positive Case={len(primary_cases)}, "
            f"expected={EXPECTED_PRIMARY_POSITIVE}"
        )

    model_counts: dict[str, int] = {}
    for row in parent_child_rows:
        model = str(row.get("exact_sales_code") or "")
        model_counts[model] = model_counts.get(model, 0) + 1

    if not model_counts or min(model_counts.values()) < 20:
        errors.append(
            f"제품 필터 후 후보 Chunk 난도 부족: {model_counts}"
        )

    faq = e02_preflight.get("faq") or {}
    supplemental_rows = faq.get("compatible_cases") or []
    if len(supplemental_rows) != EXPECTED_SUPPLEMENTAL_FAQ:
        warnings.append(
            f"FAQ supplemental={len(supplemental_rows)}, "
            f"expected={EXPECTED_SUPPLEMENTAL_FAQ}"
        )

    # E03에서는 임베딩 모델마다 cosine score 분포가 다르므로
    # threshold 기반 No-Evidence 평가는 제외하고 positive ranking만 비교한다.
    primary_queries = [
        str(row["query"])
        for row in primary_cases
    ]
    supplemental_queries = [
        str(row["query"])
        for row in supplemental_rows
        if row.get("query")
    ]
    all_queries = primary_queries + supplemental_queries
    documents = [
        str(row["text"])
        for row in parent_child_rows
    ]

    versions = {
        "python": platform.python_version(),
        "sentence_transformers": package_version("sentence-transformers"),
        "transformers": package_version("transformers"),
        "huggingface_hub": package_version("huggingface-hub"),
        "torch": package_version("torch"),
        "numpy": package_version("numpy"),
    }

    if not parse_version(versions["sentence_transformers"]):
        errors.append("sentence-transformers가 설치되어 있지 않습니다.")
    if not parse_version(versions["transformers"]):
        errors.append("transformers가 설치되어 있지 않습니다.")
    if not parse_version(versions["huggingface_hub"]):
        errors.append("huggingface-hub가 설치되어 있지 않습니다.")

    # GTE model card 기준 SentenceTransformers >= 3.0 / Transformers >= 4.36.
    if parse_version(versions["sentence_transformers"]) < (3, 0):
        errors.append(
            "gte-multilingual-base 비교에는 sentence-transformers>=3.0.0이 필요합니다. "
            f"actual={versions['sentence_transformers']}"
        )
    if parse_version(versions["transformers"]) < (4, 36):
        errors.append(
            "gte-multilingual-base 비교에는 transformers>=4.36.0이 필요합니다. "
            f"actual={versions['transformers']}"
        )

    resolved_models: list[dict[str, Any]] = []
    if not errors:
        api = HfApi()
        for spec in MODEL_SPECS:
            try:
                resolved = resolve_model(
                    api,
                    spec,
                    documents=documents,
                    queries=all_queries,
                )
                resolved_models.append(resolved)

                if resolved["truncation_gate"] != "PASS":
                    errors.append(
                        f"{spec['model_id']}: 입력 길이 초과 "
                        f"documents={resolved['document_tokens']['over_declared_max_count']}, "
                        f"queries={resolved['query_tokens']['over_declared_max_count']}"
                    )
            except Exception as exc:
                errors.append(
                    f"{spec['model_id']} metadata/tokenizer 확인 실패: "
                    f"{type(exc).__name__}: {exc}"
                )

    # 모델 SHA가 실제 run 전에 고정되도록 exact resolved revision을 저장한다.
    status = (
        "E03_PREFLIGHT_READY"
        if not errors
        else "E03_PREFLIGHT_BLOCKED"
    )

    input_hashes = {
        str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
        for path in required
    }

    result = {
        "status": status,
        "experiment_id": "E03",
        "git": {
            "branch": git_value("branch", "--show-current"),
            "head_sha": git_value("rev-parse", "HEAD"),
        },
        "purpose": (
            "E02-v2 우승 Parent-Child-256 Corpus를 고정하고 "
            "Dense Embedding 모델만 변경하여 retrieval ranking 품질과 "
            "CPU 추론 비용을 비교"
        ),
        "fixed_contract": {
            "corpus": "E02-v2 parent_child_256",
            "corpus_chunk_count": len(parent_child_rows),
            "candidate_counts_after_product_filter": dict(
                sorted(model_counts.items())
            ),
            "evidence_group_count": len(groups),
            "source_child_count": len(children),
            "primary_query_set": "E01 positive 43 cases",
            "primary_case_count": len(primary_cases),
            "supplemental_query_set": "FAQ-origin compatible UNREVIEWED_DRAFT",
            "supplemental_case_count": len(supplemental_rows),
            "top_k": TOP_K,
            "exact_sales_code_pre_filter": True,
            "cross_model_fallback": False,
            "retrieval_text": "CHILD_TEXT_ONLY",
            "parent_context_scored": False,
            "query_expansion": "SAME_RUNTIME_POLICY_FOR_ALL_MODELS",
            "normalization": "L2_NORMALIZED",
            "similarity": "COSINE_VIA_NORMALIZED_DOT_PRODUCT",
            "score_threshold": None,
            "no_evidence_metric": "EXCLUDED_FROM_E03_PRIMARY",
            "reason_threshold_excluded": (
                "Embedding 모델별 cosine score 분포가 달라 "
                "동일 threshold=0.4 적용이 불공정하므로 E03은 순위 지표만 비교. "
                "Threshold/No-Evidence는 E09에서 별도 평가."
            ),
            "metrics": [
                "Hit@1",
                "Hit@3",
                "Hit@5",
                "MRR@5",
                "nDCG@5",
                "document_embedding_time",
                "query_embedding_time",
                "ranking_latency",
                "embedding_dimension",
            ],
        },
        "models": resolved_models,
        "environment": versions,
        "input_hashes": input_hashes,
        "publication_guardrail": {
            "result_label": "DRAFT_DIAGNOSTIC",
            "primary": "E01 positive 43 case ranking metric",
            "supplemental": (
                "FAQ-origin 5 case는 UNREVIEWED_DRAFT이며 "
                "공식 Metric에 합산하지 않음"
            ),
        },
        "warnings": warnings,
        "errors": errors,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    compact_models = {
        row["key"]: {
            "model_id": row["model_id"],
            "revision": row["resolved_revision"],
            "dimension": row["expected_dimension"],
            "declared_max_tokens": row["declared_max_tokens"],
            "document_max_tokens": row["document_tokens"]["max"],
            "query_max_tokens": row["query_tokens"]["max"],
            "truncation_gate": row["truncation_gate"],
            "safetensors_mb": row["safetensors_mb"],
            "query_prefix": row["query_prefix"],
            "document_prefix": row["document_prefix"],
        }
        for row in resolved_models
    }

    compact = {
        "status": status,
        "git_sha": result["git"]["head_sha"],
        "fixed_corpus": {
            "variant": "parent_child_256",
            "chunks": len(parent_child_rows),
            "candidate_counts_by_model": dict(sorted(model_counts.items())),
            "evidence_groups": len(groups),
            "source_children": len(children),
        },
        "query_sets": {
            "primary_positive": len(primary_cases),
            "supplemental_faq_draft": len(supplemental_rows),
        },
        "models": compact_models,
        "threshold_policy": "DISABLED_FOR_E03_RANKING_COMPARISON",
        "output": str(OUT_PATH.relative_to(ROOT)).replace("\\", "/"),
        "warnings": warnings,
        "errors": errors,
    }

    print(
        json.dumps(
            compact,
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
