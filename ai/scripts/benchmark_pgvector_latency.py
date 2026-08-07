"""개인 격리 pgvector에서 bge-m3 검색 지연시간 기준선을 측정한다."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import psycopg

from ai.app.integrations.embedding.embedding_client import BgeM3EmbeddingClient
from ai.app.integrations.vector_store.vector_store import PgVectorStore


DEFAULT_COLD_RUNS = 3
DEFAULT_WARM_RUNS = 30


def _percentile(values: Sequence[float], percentile: float) -> float:
    """선형 보간 방식으로 Percentile을 계산한다."""
    if not values:
        raise ValueError("Percentile 계산에는 한 개 이상의 값이 필요합니다.")
    if not 0 <= percentile <= 100:
        raise ValueError("Percentile은 0~100 범위여야 합니다.")

    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * (percentile / 100)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _summary(values: Sequence[float]) -> dict[str, float | int]:
    if not values:
        raise ValueError("지연시간 요약에는 한 개 이상의 값이 필요합니다.")
    return {
        "sample_count": len(values),
        "mean_ms": round(sum(values) / len(values), 3),
        "p50_ms": round(_percentile(values, 50), 3),
        "p95_ms": round(_percentile(values, 95), 3),
        "min_ms": round(min(values), 3),
        "max_ms": round(max(values), 3),
    }


def _total_memory_bytes() -> int | None:
    if platform.system() != "Windows":
        return None

    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong),
            ("memory_load", ctypes.c_ulong),
            ("total_physical", ctypes.c_ulonglong),
            ("available_physical", ctypes.c_ulonglong),
            ("total_page_file", ctypes.c_ulonglong),
            ("available_page_file", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("available_virtual", ctypes.c_ulonglong),
            ("available_extended_virtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatusEx()
    status.length = ctypes.sizeof(MemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int(status.total_physical)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _load_positive_cases(config_path: Path) -> list[dict]:
    contract = json.loads(config_path.read_text(encoding="utf-8"))
    cases = [case for case in contract["cases"] if case["case_type"] == "POSITIVE"]
    if not cases:
        raise RuntimeError("Warm/Cold 측정에 사용할 양성 검색 Case가 없습니다.")
    return cases


def _database_facts(dsn: str) -> dict:
    with psycopg.connect(dsn, connect_timeout=5) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        database_name = str(cursor.fetchone()[0])
        cursor.execute("SHOW server_version")
        postgres_version = str(cursor.fetchone()[0])
        cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        pgvector_version = str(cursor.fetchone()[0])
        cursor.execute(
            "SELECT COUNT(*), MIN(vector_dims(embedding)), MAX(vector_dims(embedding)) "
            "FROM ai_rag_chunks"
        )
        row_count, minimum_dimension, maximum_dimension = cursor.fetchone()
    return {
        "database_name": database_name,
        "postgres_version": postgres_version,
        "pgvector_version": pgvector_version,
        "row_count": int(row_count),
        "minimum_dimension": int(minimum_dimension),
        "maximum_dimension": int(maximum_dimension),
        "host_port": 55432,
    }


def _assert_disposable_database(dsn: str) -> dict:
    if os.getenv("AI_VECTOR_DISPOSABLE_CONFIRM") != "DISPOSABLE_ONLY":
        raise RuntimeError("간이 성능 측정은 DISPOSABLE_ONLY 격리 DB에서만 허용됩니다.")
    facts = _database_facts(dsn)
    if not re.search(r"(verify|test|tmp|disposable)", facts["database_name"], re.IGNORECASE):
        raise RuntimeError("공유 DB 성능 측정을 거부했습니다.")
    if facts["row_count"] != 7 or facts["minimum_dimension"] != 1024 or facts["maximum_dimension"] != 1024:
        raise RuntimeError("승인 청크 7개·1024차원 격리 기준선과 DB 상태가 다릅니다.")
    return facts


def _measure_once(
    embedding_client: BgeM3EmbeddingClient,
    vector_store: PgVectorStore,
    case: dict,
) -> dict:
    total_started = time.perf_counter()
    embedding_started = time.perf_counter()
    vector = embedding_client.embed_query(case["query"])
    embedding_ms = (time.perf_counter() - embedding_started) * 1000

    search_started = time.perf_counter()
    chunks = vector_store.search(
        vector,
        model_code=case["product_model_code"],
        product_generation="D",
        top_k=case["top_k"],
    )
    search_ms = (time.perf_counter() - search_started) * 1000
    retrieval_total_ms = (time.perf_counter() - total_started) * 1000
    return {
        "case_id": case["case_id"],
        "embedding_ms": embedding_ms,
        "pgvector_search_ms": search_ms,
        "retrieval_total_ms": retrieval_total_ms,
        "hit_count": len(chunks),
    }


def _cold_child(config_path: Path, case_index: int, model_revision: str, dsn: str) -> None:
    cases = _load_positive_cases(config_path)
    case = cases[case_index % len(cases)]
    result = _measure_once(
        BgeM3EmbeddingClient(model_revision=model_revision),
        PgVectorStore(dsn),
        case,
    )
    print(json.dumps(result, ensure_ascii=False))


def _run_cold_samples(
    repository_root: Path,
    config_path: Path,
    cold_runs: int,
) -> list[dict]:
    results = []
    for case_index in range(cold_runs):
        process_started = time.perf_counter()
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "ai.scripts.benchmark_pgvector_latency",
                "--cold-child",
                "--config",
                str(config_path),
                "--case-index",
                str(case_index),
            ],
            cwd=repository_root,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=True,
        )
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        if not lines:
            raise RuntimeError("Cold 측정 하위 프로세스가 결과를 반환하지 않았습니다.")
        result = json.loads(lines[-1])
        result["process_total_ms"] = (time.perf_counter() - process_started) * 1000
        results.append(result)
    return results


def _metric_summaries(samples: Sequence[dict], *, include_process: bool = False) -> dict:
    keys = ["embedding_ms", "pgvector_search_ms", "retrieval_total_ms"]
    if include_process:
        keys.append("process_total_ms")
    return {key: _summary([float(sample[key]) for sample in samples]) for key in keys}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cold-runs", type=int, default=DEFAULT_COLD_RUNS)
    parser.add_argument("--warm-runs", type=int, default=DEFAULT_WARM_RUNS)
    parser.add_argument("--cold-child", action="store_true")
    parser.add_argument("--case-index", type=int, default=0)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    dsn = os.getenv("AI_VECTOR_DSN")
    model_revision = os.getenv("AI_EMBEDDING_REVISION")
    if not dsn or not model_revision:
        raise RuntimeError("AI_VECTOR_DSN과 AI_EMBEDDING_REVISION이 필요합니다.")
    if args.cold_runs < 1 or args.warm_runs < 1:
        raise ValueError("Cold/Warm 실행 횟수는 1 이상이어야 합니다.")

    repository_root = Path(__file__).resolve().parents[2]
    config_path = args.config or repository_root / "data" / "config" / "rag" / "jac104_retrieval_cases.json"
    output_path = args.output or repository_root / "ai" / "evaluation" / "reports" / "pgvector_latency_baseline_20260806.json"

    if args.cold_child:
        _cold_child(config_path, args.case_index, model_revision, dsn)
        return

    database = _assert_disposable_database(dsn)
    positive_cases = _load_positive_cases(config_path)
    cold_samples = _run_cold_samples(repository_root, config_path, args.cold_runs)

    embedding_client = BgeM3EmbeddingClient(model_revision=model_revision)
    vector_store = PgVectorStore(dsn)
    _measure_once(embedding_client, vector_store, positive_cases[0])
    warm_samples = [
        _measure_once(embedding_client, vector_store, positive_cases[index % len(positive_cases)])
        for index in range(args.warm_runs)
    ]

    all_samples = [*cold_samples, *warm_samples]
    failed_samples = [sample for sample in all_samples if sample["hit_count"] == 0]
    report = {
        "benchmark_status": "PASS" if not failed_samples else "PARTIAL",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "PERSONAL_ISOLATED_SINGLE_USER_BASELINE",
        "limitations": [
            "개인 PC의 127.0.0.1:55432 격리 PostgreSQL/pgvector 측정이다.",
            "동시 사용자, 네트워크 구간, FastAPI HTTP와 Backend E2E는 포함하지 않는다.",
            "승인 청크 7개 Exact Search 기준이므로 운영 데이터 규모 성능으로 일반화하지 않는다.",
        ],
        "methodology": {
            "cold_runs": args.cold_runs,
            "cold_definition": "매회 독립 Python 프로세스에서 bge-m3 로드·질의 임베딩·pgvector 검색 수행",
            "warmup_runs": 1,
            "warm_runs": args.warm_runs,
            "warm_definition": "모델 1회 예열 후 단일 프로세스에서 양성 7 Case를 순환 측정",
            "concurrency": 1,
            "database_connection": "현재 PgVectorStore 구현처럼 검색마다 새 psycopg 연결 포함",
            "percentile_method": "정렬 표본의 (n-1)*p 위치 선형 보간",
        },
        "runtime": {
            "python_version": platform.python_version(),
            "os": platform.platform(),
            "machine": platform.machine(),
            "cpu": os.getenv("PROCESSOR_IDENTIFIER") or platform.processor(),
            "logical_cpu_count": os.cpu_count(),
            "total_memory_bytes": _total_memory_bytes(),
            "cuda_used": False,
        },
        "embedding": {
            "model": BgeM3EmbeddingClient.model_name,
            "revision": model_revision,
            "dimension": BgeM3EmbeddingClient.dimension,
            "device": "cpu",
        },
        "database": database,
        "dataset": {
            "config_path": str(config_path.relative_to(repository_root)).replace("\\", "/"),
            "config_sha256": _sha256(config_path),
            "positive_case_count": len(positive_cases),
        },
        "cold": _metric_summaries(cold_samples, include_process=True),
        "warm": _metric_summaries(warm_samples),
        "validation": {
            "measured_request_count": len(all_samples),
            "nonempty_result_count": sum(sample["hit_count"] > 0 for sample in all_samples),
            "failed_request_count": len(failed_samples),
            "failed_case_ids": [sample["case_id"] for sample in failed_samples],
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "benchmark_status": report["benchmark_status"],
        "output_path": str(output_path.relative_to(repository_root)).replace("\\", "/"),
        "cold_retrieval_total_ms": report["cold"]["retrieval_total_ms"],
        "warm_retrieval_total_ms": report["warm"]["retrieval_total_ms"],
        "validation": report["validation"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
