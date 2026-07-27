"""Load and validate declarative WaterCare pipeline configuration."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import data_path, read_json


@dataclass(frozen=True)
class PipelineConfig:
    data_root: Path
    values: dict[str, Any]

    @property
    def generated_at(self) -> str:
        return self.values["generated_at"]

    @property
    def dataset_version(self) -> str:
        return self.values["dataset_version"]

    def path(self, key: str) -> Path:
        return data_path(self.data_root, self.values["paths"][key])

    def config(self, key: str) -> Any:
        return read_json(self.path(key))


def load_pipeline(data_root: Path) -> PipelineConfig:
    data_root = data_root.resolve()
    path = data_path(data_root, "config/pipeline.json")
    values = read_json(path)
    required = {
        "config_version",
        "dataset_version",
        "generated_at",
        "mvp_product_code",
        "mvp_document_id",
        "expected_counts",
        "paths",
    }
    missing = sorted(required - values.keys())
    if missing:
        raise ValueError(f"pipeline config missing keys: {missing}")
    for relative in values["paths"].values():
        data_path(data_root, relative)
    if not values["mvp_product_code"] or not values["mvp_document_id"]:
        raise ValueError("MVP product and document identifiers are required")
    if not re.fullmatch(r"\d+\.\d+\.\d+", values["dataset_version"]):
        raise ValueError("dataset_version must use semantic version format")
    return PipelineConfig(data_root=data_root, values=values)
