"""Execute the actual SSM wire payload through POSIX sh, without AWS access."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/deployment/production/build_ssm_bash_parameters.py"
WORKFLOW = ROOT / ".github/workflows/production-deploy.yml"
SPEC = importlib.util.spec_from_file_location("ssm_bash_parameters", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
BUILDER = "scripts/deployment/production/build_ssm_bash_parameters.py"


class SSMParameterTests(unittest.TestCase):
    def test_payload_is_one_posix_quoted_explicit_bash_invocation(self):
        commands = ["[[ -n ok ]]", "printf '%s' \"quote'and\\nnewline\""]
        payload = MODULE.build_parameters(commands)
        tokens = shlex.split(payload["commands"][0])
        self.assertEqual(tokens[:6], ["exec", "/bin/bash", "-euo", "pipefail", "-c", "\n".join(commands)])
        self.assertEqual(len(payload["commands"]), 1)
        self.assertEqual(json.loads(json.dumps(payload)), payload)

    def test_empty_or_nul_commands_are_rejected(self):
        for commands in ([], [""], [" "], ["bad\x00command"], [None]):
            with self.subTest(commands=commands), self.assertRaises(ValueError):
                MODULE.build_parameters(commands)

    def test_all_four_ssm_paths_use_the_tested_builder(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(text.count('commands_json="$(python3 ' + BUILDER), 4)
        self.assertNotIn('commands_json="$(jq', text)
        self.assertIn("tests.deployment.test_ssm_bash_parameters", text)

    def test_canary_checks_out_helper_from_main_caller_not_old_runtime_sha(self):
        text = WORKFLOW.read_text(encoding="utf-8").split("\n  source-guard:", 1)[0]
        checkout = "Checkout trusted main caller for SSM transport helper"
        self.assertIn("ref: ${{ github.sha }}", text)
        self.assertIn("sparse-checkout: scripts/deployment/production", text)
        self.assertLess(text.index(checkout), text.index(BUILDER))
        self.assertLess(text.index('[[ "$CALLER_REF" == "refs/heads/main" ]]'), text.index(checkout))
        self.assertNotIn("ref: ${{ env.RELEASE_SHA }}", text)


@unittest.skipIf(os.name == "nt", "Run transport regressions on real Linux /bin/sh")
class SSMWireExecutionTests(unittest.TestCase):
    def execute(self, payload, *, env=None):
        return subprocess.run(
            ["/bin/sh", "-c", "\n".join(payload["commands"])],
            capture_output=True, text=True, timeout=10, env=env,
        )

    def test_sh_transport_supports_bash_arrays_and_double_brackets(self):
        payload = MODULE.build_parameters([
            "items=(one two)", '[[ "${items[1]}" == two ]]', "printf BASH_OK",
        ])
        result = self.execute(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "BASH_OK")

    def test_pipe_failure_stops_later_commands(self):
        result = self.execute(MODULE.build_parameters(["false | true", "printf UNSAFE_CONTINUE"]))
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("UNSAFE_CONTINUE", result.stdout)

    def test_unset_variable_stops_later_commands(self):
        result = self.execute(MODULE.build_parameters([
            "unset QA_UNSET_VARIABLE", 'printf "%s" "$QA_UNSET_VARIABLE"', "printf UNSAFE_CONTINUE",
        ]))
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("UNSAFE_CONTINUE", result.stdout)

    def test_exit_code_is_preserved(self):
        result = self.execute(MODULE.build_parameters(["exit 37", "printf UNSAFE_CONTINUE"]))
        self.assertEqual(result.returncode, 37)
        self.assertNotIn("UNSAFE_CONTINUE", result.stdout)

    def test_cli_and_bash_percent_q_survive_posix_transport_without_injection(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "must-not-exist"
            value = f"quote' double\" newline\n$(touch {marker}) `touch {marker}` \\ end"
            quoted = subprocess.run(
                ["/bin/bash", "-c", 'printf "%q" "$1"', "qa", value],
                capture_output=True, text=True, check=True, timeout=10,
            ).stdout
            encoded = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "printf '%s' " + quoted],
                capture_output=True, text=True, check=True, timeout=10,
            )
            result = self.execute(json.loads(encoded.stdout))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, value)
            self.assertFalse(marker.exists())

    def workflow_payload(self, role, state):
        # Execute the commands_json assignment extracted from the real workflow.
        # Only external operation values and the Canary fixture path are replaced.
        text = WORKFLOW.read_text(encoding="utf-8")
        pattern = r'commands_json="\$\((python3 ' + re.escape(BUILDER) + r'[\s\S]*?)\)"'
        calls = re.findall(pattern, text)
        self.assertEqual(len(calls), 4)
        marker = {
            "canary": '"$canary_command"',
            "activation": '"$activation_command"',
            "deploy": '"$deploy_command"',
            "rollback": '"$rollback_command"',
        }[role]
        selected = [call for call in calls if marker in call]
        self.assertEqual(len(selected), 1, role)
        call = selected[0].replace("python3 ", shlex.quote(sys.executable) + " ", 1)
        call = call.replace("/opt/waterbridge/shared/ai-handoff-canary.state", str(state))
        env = os.environ | {
            "canary_command": "printf CANARY_CALLED",
            "activation_command": "printf ACTIVATION_CALLED",
            "copy_command": "aws synthetic-copy",
            "chmod_command": "chmod synthetic-chmod",
            "deploy_command": "printf DEPLOY_CALLED",
            "rollback_command": "printf ROLLBACK_CALLED",
        }
        result = subprocess.run(
            ["/bin/bash", "-euo", "pipefail", "-c", call],
            cwd=ROOT, capture_output=True, text=True, check=True, timeout=10, env=env,
        )
        return json.loads(result.stdout)

    def stub_environment(self, directory, copy_status=0):
        # No real install/chmod/AWS or production path writes in this test.
        for name, body in {
            "install": "printf 'INSTALL_CALLED\\n'",
            "aws": "printf 'COPY_CALLED\\n'; exit \"${COPY_STATUS:-0}\"",
            "chmod": "printf 'CHMOD_CALLED\\n'",
        }.items():
            script = directory / name
            script.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
            script.chmod(0o700)
        return os.environ | {
            # Never fall back to a real host operation if a stub cannot run.
            "PATH": str(directory),
            "COPY_STATUS": str(copy_status),
        }

    def test_actual_deploy_wire_blocks_active_canary_before_any_operation(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            state = directory / "canary.state"
            state.touch()
            result = self.execute(self.workflow_payload("deploy", state), env=self.stub_environment(directory))
            self.assertEqual(result.returncode, 1)
            self.assertIn("DEPLOYMENT_BLOCKED", result.stderr)
            self.assertNotIn("[[: not found", result.stderr)
            self.assertEqual(result.stdout, "")

    def test_actual_deploy_wire_preserves_order_when_canary_is_inactive(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            result = self.execute(
                self.workflow_payload("deploy", directory / "absent.state"),
                env=self.stub_environment(directory),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "INSTALL_CALLED\nCOPY_CALLED\nCHMOD_CALLED\nDEPLOY_CALLED")

    def test_copy_failure_stops_deploy_and_rollback_wire(self):
        for role in ("deploy", "rollback"):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                result = self.execute(
                    self.workflow_payload(role, directory / "absent.state"),
                    env=self.stub_environment(directory, copy_status=23),
                )
                self.assertEqual(result.returncode, 23)
                self.assertIn("COPY_CALLED", result.stdout)
                for marker in ("CHMOD_CALLED", "DEPLOY_CALLED", "ROLLBACK_CALLED"):
                    self.assertNotIn(marker, result.stdout)

    def test_actual_canary_activation_and_rollback_wire_execute_successfully(self):
        expected_outputs = (
            ("canary", "CANARY_CALLED"),
            ("activation", "ACTIVATION_CALLED"),
            ("rollback", "COPY_CALLED\nCHMOD_CALLED\nROLLBACK_CALLED"),
        )
        for role, expected in expected_outputs:
            with self.subTest(role=role), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                result = self.execute(
                    self.workflow_payload(role, directory / "absent.state"),
                    env=self.stub_environment(directory),
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)


if __name__ == "__main__":
    unittest.main()
