"""평가 데이터셋 로더 모듈."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class EvalDatasetLoader:
    """evaluation/datasets/ JSON 데이터셋 읽기 로더"""

    def __init__(self, dataset_dir: Optional[str] = None, rag_config_path: Optional[str] = None):
        if dataset_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.dataset_dir = os.path.join(base_dir, "datasets")
        else:
            self.dataset_dir = dataset_dir
        repository_root = Path(__file__).resolve().parents[2]
        self.rag_config_path = Path(rag_config_path) if rag_config_path else (
            repository_root / "data" / "config" / "rag" / "jac104_retrieval_cases.json"
        )

    def load_rag_dataset(self) -> List[Dict[str, Any]]:
        """Data Owner의 JAC104 검색 평가 기준본을 직접 로딩한다."""
        if not self.rag_config_path.is_file():
            raise FileNotFoundError(f"RAG 평가 기준본이 없습니다: {self.rag_config_path}")
        config = json.loads(self.rag_config_path.read_text(encoding="utf-8"))
        cases = config.get("cases")
        if not isinstance(cases, list):
            raise ValueError("RAG 평가 기준본의 cases는 배열이어야 합니다.")
        return cases

    def load_safety_dataset(self) -> List[Dict[str, Any]]:
        """안전 규칙 평가셋 로딩"""
        paths = [
            os.path.join(self.dataset_dir, "safety", "safety_eval_dataset.json"),
            os.path.join(self.dataset_dir, "safety_eval_dataset.json")
        ]
        for path in paths:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        return []

    def load_structuring_dataset(self) -> Dict[str, Any]:
        """T-026 구조화·누락 필드·추가 질문 평가 기준본을 로딩한다."""
        path = Path(self.dataset_dir) / "structuring" / "symptom_eval_dataset.json"
        if not path.is_file():
            raise FileNotFoundError(f"구조화 평가 기준본이 없습니다: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("구조화 평가 기준본은 Metadata와 cases를 가진 객체여야 합니다.")
        cases = payload.get("cases")
        if not isinstance(cases, list) or not cases:
            raise ValueError("구조화 평가 기준본의 cases는 비어 있지 않은 배열이어야 합니다.")
        case_ids = [case.get("case_id") for case in cases if isinstance(case, dict)]
        if len(case_ids) != len(cases) or any(not case_id for case_id in case_ids):
            raise ValueError("모든 구조화 평가 Case에는 case_id가 필요합니다.")
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("구조화 평가 case_id는 중복될 수 없습니다.")
        return payload
