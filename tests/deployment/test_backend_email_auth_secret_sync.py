"""Synthetic-only tests for the Backend email auth Secret synchronizer."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts"
    / "deployment"
    / "production"
    / "sync_backend_email_auth_secret.py"
)
SPEC = importlib.util.spec_from_file_location("email_auth_secret_sync", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)


def approved_hmacs() -> list[str]:
    return [character * 64 for character in "abcdef"]


def complete_secret() -> dict[str, str]:
    values = {
        key: f"synthetic-{index}"
        for index, key in enumerate(
            sorted(SYNC.EXISTING_EMAIL_AUTH_KEYS),
            start=1,
        )
    }
    values[SYNC.ALLOWLIST_KEY] = ",".join(approved_hmacs())
    return values


class BackendEmailAuthSecretSyncTests(unittest.TestCase):
    def assert_reason(self, reason: str, callback) -> None:
        with self.assertRaises(SYNC.SafeSyncError) as captured:
            callback()
        self.assertEqual(captured.exception.reason, reason)

    def test_single_and_two_document_secret_strings_are_supported(self) -> None:
        values = complete_secret()
        decoded, count = SYNC.decode_json_documents(json.dumps(values))
        self.assertEqual(decoded, values)
        self.assertEqual(count, 1)

        first = {
            key: value
            for key, value in values.items()
            if key != SYNC.ALLOWLIST_KEY
        }
        second = {SYNC.ALLOWLIST_KEY: values[SYNC.ALLOWLIST_KEY]}
        decoded, count = SYNC.decode_json_documents(
            f"{json.dumps(first)}\n{json.dumps(second)}"
        )
        self.assertEqual(decoded, values)
        self.assertEqual(count, 2)

        decoded, count = SYNC.decode_json_documents(
            f"{json.dumps(values)}\n{{}}"
        )
        self.assertEqual(decoded, values)
        self.assertEqual(count, 2)

        decoded, count = SYNC.decode_json_documents(
            f'{json.dumps(values)}\n{{"": ""}}'
        )
        self.assertEqual(decoded, values)
        self.assertEqual(count, 2)

    def test_secret_document_and_key_boundaries_fail_closed(self) -> None:
        values = complete_secret()
        self.assert_reason(
            "SECRET_DOCUMENT_COUNT_INVALID",
            lambda: SYNC.decode_json_documents("{}\n{}\n{}"),
        )
        self.assert_reason(
            "SECRET_DOCUMENT_NOT_OBJECT",
            lambda: SYNC.decode_json_documents("[]"),
        )
        self.assert_reason(
            "SECRET_KEY_UNKNOWN",
            lambda: SYNC.decode_json_documents(
                json.dumps({**values, "UNAPPROVED_KEY": "synthetic"})
            ),
        )
        self.assert_reason(
            "SECRET_KEY_UNKNOWN",
            lambda: SYNC.decode_json_documents(
                f'{json.dumps(values)}\n{{"": "unexpected"}}'
            ),
        )
        self.assert_reason(
            "SECRET_KEY_DUPLICATED",
            lambda: SYNC.decode_json_documents(
                f"{json.dumps(values)}\n"
                f"{json.dumps({SYNC.ALLOWLIST_KEY: values[SYNC.ALLOWLIST_KEY]})}"
            ),
        )
        missing = dict(values)
        missing.pop("DJANGO_EMAIL_HOST_USER")
        self.assert_reason(
            "SECRET_REQUIRED_KEY_MISSING",
            lambda: SYNC.decode_json_documents(json.dumps(missing)),
        )
        empty = dict(values)
        empty["DJANGO_EMAIL_HOST_USER"] = ""
        self.assert_reason(
            "SECRET_VALUE_EMPTY_OR_INVALID",
            lambda: SYNC.decode_json_documents(json.dumps(empty)),
        )

    def test_allowlist_requires_six_unique_lowercase_sha256_values(self) -> None:
        canonical = ",".join(approved_hmacs())
        self.assertEqual(SYNC.canonicalize_allowlist(canonical), canonical)
        self.assert_reason(
            "ALLOWLIST_COUNT_INVALID",
            lambda: SYNC.canonicalize_allowlist(",".join(approved_hmacs()[:5])),
        )
        duplicated = approved_hmacs()
        duplicated[-1] = duplicated[0]
        self.assert_reason(
            "ALLOWLIST_DUPLICATED",
            lambda: SYNC.canonicalize_allowlist(",".join(duplicated)),
        )
        uppercase = approved_hmacs()
        uppercase[0] = "A" * 64
        self.assert_reason(
            "ALLOWLIST_FORMAT_INVALID",
            lambda: SYNC.canonicalize_allowlist(",".join(uppercase)),
        )

    def test_env_update_preserves_existing_secret_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "backend.env"
            existing = {
                key: f"preserve-{index}"
                for index, key in enumerate(
                    sorted(SYNC.EXISTING_EMAIL_AUTH_KEYS),
                    start=1,
                )
            }
            original_lines = [
                *(f"{key}={value}" for key, value in existing.items()),
                "UNRELATED_SETTING=preserve-unrelated",
            ]
            path.write_text("\n".join(original_lines) + "\n", encoding="utf-8")
            canonical = ",".join(approved_hmacs())

            SYNC.update_backend_env(
                path,
                canonical_allowlist=canonical,
                enforce_root=False,
            )
            SYNC.update_backend_env(
                path,
                canonical_allowlist=canonical,
                enforce_root=False,
            )

            updated = path.read_text(encoding="utf-8")
            for key, value in existing.items():
                self.assertIn(f"{key}={value}\n", updated)
            self.assertIn("UNRELATED_SETTING=preserve-unrelated\n", updated)
            self.assertEqual(updated.count(f"{SYNC.RUNTIME_ENV_KEY}="), 1)
            self.assertEqual(updated.count(f"{SYNC.DELIVERY_ENABLED_KEY}="), 1)
            self.assertEqual(updated.count(f"{SYNC.ALLOWLIST_KEY}="), 1)
            self.assertIn(f"{SYNC.RUNTIME_ENV_KEY}=AWS_NONPROD\n", updated)
            self.assertIn(f"{SYNC.DELIVERY_ENABLED_KEY}=true\n", updated)
            self.assertIn(f"{SYNC.ALLOWLIST_KEY}={canonical}\n", updated)

    def test_duplicate_target_env_definition_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "backend.env"
            lines = [
                *(f"{key}=synthetic" for key in SYNC.EXISTING_EMAIL_AUTH_KEYS),
                f"{SYNC.RUNTIME_ENV_KEY}=AWS_NONPROD",
                f"{SYNC.RUNTIME_ENV_KEY}=AWS_NONPROD",
            ]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.assert_reason(
                "BACKEND_ENV_KEY_DUPLICATED",
                lambda: SYNC.update_backend_env(
                    path,
                    canonical_allowlist=",".join(approved_hmacs()),
                    enforce_root=False,
                ),
            )

    def test_source_never_prints_secret_payloads(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("print(secret_string", source)
        self.assertNotIn("print(completed.stdout", source)
        self.assertNotIn("print(values", source)
        self.assertIn("secret_values_printed=false", source)


if __name__ == "__main__":
    unittest.main()
