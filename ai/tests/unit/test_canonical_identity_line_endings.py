"""Canonical identity 파일의 Windows 줄끝·바이트 SHA 회귀 테스트."""

from hashlib import sha256
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
IDENTITY_PATH = REPOSITORY_ROOT / "ai/configs/canonical_evidence_identity.json"
EXPECTED_LF_FILE_SHA256 = (
    "925088A352A81180B51E5418EB3152A1244ABA3DA07569712C4D903468220B85"
)


def test_canonical_identity_is_lf_only_with_fixed_file_sha256() -> None:
    raw = IDENTITY_PATH.read_bytes()

    assert b"\r" not in raw
    assert sha256(raw).hexdigest().upper() == EXPECTED_LF_FILE_SHA256


def test_gitattributes_forces_canonical_identity_to_lf() -> None:
    attributes = (REPOSITORY_ROOT / ".gitattributes").read_text(encoding="utf-8")

    assert "ai/configs/canonical_evidence_identity.json text eol=lf" in attributes
