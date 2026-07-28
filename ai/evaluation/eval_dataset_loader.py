"""평가 데이터셋 로더 모듈."""

import json
import os
from typing import Any, Dict, List, Optional


class EvalDatasetLoader:
    """evaluation/datasets/ JSON 데이터셋 읽기 로더"""

    def __init__(self, dataset_dir: Optional[str] = None):
        if dataset_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.dataset_dir = os.path.join(base_dir, "datasets")
        else:
            self.dataset_dir = dataset_dir

    def load_rag_dataset(self) -> List[Dict[str, Any]]:
        """RAG 검색 정답셋 로딩"""
        paths = [
            os.path.join(self.dataset_dir, "retrieval", "rag_eval_dataset.json"),
            os.path.join(self.dataset_dir, "rag_eval_dataset.json")
        ]
        for path in paths:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        return []

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
