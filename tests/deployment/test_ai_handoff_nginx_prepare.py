"""Runtime tests for the protected Canary Nginx include preparation."""

from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/deployment/production/prepare_ai_handoff_nginx.py"
SPEC = importlib.util.spec_from_file_location("ai_handoff_nginx_prepare", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeRunner:
    def __init__(self, dump: str, *, fail_test_once: bool = False):
        self.dump = dump
        self.fail_test_once = fail_test_once
        self.commands: list[list[str]] = []

    def __call__(self, command, *, check, capture_output, text):
        self.commands.append(command)
        if command == ["nginx", "-T"]:
            return subprocess.CompletedProcess(command, 0, self.dump, "")
        if command == ["nginx", "-t"] and self.fail_test_once:
            self.fail_test_once = False
            raise subprocess.CalledProcessError(1, command)
        return subprocess.CompletedProcess(command, 0, "", "")


class AIHandoffNginxPrepareTests(unittest.TestCase):
    def _fixture(self, directory: Path, *, duplicate: bool = False):
        allowed = directory / "etc" / "nginx"
        allowed.mkdir(parents=True)
        site = allowed / "waterbridge.conf"
        block = (
            "server {\n"
            "    listen 443 ssl;\n"
            "    server_name waterbridge.site;\n"
            "    location / { proxy_pass http://127.0.0.1:18080; }\n"
            "}\n"
        )
        site.write_text(block + (block if duplicate else ""), encoding="utf-8")
        dump = f"# configuration file {site.as_posix()}:\n" + site.read_text(
            encoding="utf-8"
        )
        return allowed, site, dump

    def test_installs_include_with_backup_and_reload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            allowed, site, dump = self._fixture(root)
            runner = FakeRunner(dump)

            checksum = MODULE.prepare_nginx(
                domain="waterbridge.site",
                upstream="127.0.0.1:18080",
                dropin_dir=allowed / "waterbridge-server.d",
                backup_dir=root / "backup",
                allowed_root=allowed,
                require_root=False,
                runner=runner,
            )

            self.assertRegex(checksum, r"^[0-9a-f]{64}$")
            self.assertEqual(site.read_text().count(MODULE.INCLUDE_DIRECTIVE), 1)
            self.assertTrue((root / "backup" / f"{checksum}.conf").is_file())
            self.assertIn(["nginx", "-t"], runner.commands)
            self.assertIn(["systemctl", "reload", "nginx"], runner.commands)

    def test_ambiguous_server_blocks_fail_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            allowed, site, dump = self._fixture(root, duplicate=True)
            original = site.read_bytes()
            with self.assertRaises(MODULE.NginxPreparationError):
                MODULE.prepare_nginx(
                    domain="waterbridge.site",
                    upstream="127.0.0.1:18080",
                    dropin_dir=allowed / "waterbridge-server.d",
                    backup_dir=root / "backup",
                    allowed_root=allowed,
                    require_root=False,
                    runner=FakeRunner(dump),
                )
            self.assertEqual(site.read_bytes(), original)

    def test_failed_nginx_validation_restores_original(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            allowed, site, dump = self._fixture(root)
            original = site.read_bytes()
            with self.assertRaises(MODULE.NginxPreparationError):
                MODULE.prepare_nginx(
                    domain="waterbridge.site",
                    upstream="127.0.0.1:18080",
                    dropin_dir=allowed / "waterbridge-server.d",
                    backup_dir=root / "backup",
                    allowed_root=allowed,
                    require_root=False,
                    runner=FakeRunner(dump, fail_test_once=True),
                )
            self.assertEqual(site.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
