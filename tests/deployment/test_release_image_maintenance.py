"""Synthetic Docker/filesystem regressions; never contact Docker or AWS."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/deployment/production/maintain_release_images.py"
SPEC = importlib.util.spec_from_file_location("release_image_maintenance", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)
REGISTRY = "111111111111.dkr.ecr.ap-northeast-2.amazonaws.com"
REPOS = {service: f"{REGISTRY}/waterbridge/{service}" for service in ("web", "backend", "ai")}


def digest(number: int) -> str:
    return f"sha256:{number:064x}"


def ref(service: str, number: int) -> str:
    return f"{REPOS[service]}@{digest(number)}"


def image(number: int, refs=(), tags=()):
    return digest(number), set(tags), set(refs)


class FakeDocker:
    def __init__(self, images, containers=()):
        self.images = {item[0]: item for item in images}
        self.containers = set(containers)
        self.calls = []
        self.removed = []
        self.refuse = set()

    def __call__(self, *args):
        self.calls.append(args)
        if args == ("image", "ls", "--quiet", "--no-trunc"):
            return "\n".join(self.images)
        if args == ("container", "ls", "--all", "--quiet", "--no-trunc"):
            return "\n".join(self.containers)
        if args[:2] == ("container", "inspect"):
            assert args[2:4] == ("--format", "{{.Image}}")
            return args[-1]
        if args[:2] == ("image", "inspect"):
            assert args[2:4] == ("--format", POLICY.IMAGE_FORMAT)
            for identifier, tags, digests in self.images.values():
                if args[-1] == identifier or args[-1] in tags | digests:
                    return json.dumps([identifier, sorted(tags), sorted(digests)])
            raise POLICY.MaintenanceError("DOCKER_COMMAND_FAILED")
        if args[:2] == ("image", "rm"):
            assert args[2] == "--no-prune" and len(args) == 4
            if args[-1] in self.refuse:
                raise POLICY.MaintenanceError("DOCKER_COMMAND_FAILED")
            self.removed.append(args[-1])
            del self.images[args[-1]]
            return ""
        raise AssertionError(f"Unexpected Docker command: {args}")


class ReleaseImageMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        (self.base / "shared").mkdir()
        (self.base / "releases").mkdir()
        self.incoming = self.make_release(40)

    def make_release(self, number):
        payload = self.base / "releases" / f"{number:040x}" / "payload"
        payload.mkdir(parents=True, exist_ok=True)
        text = "".join(
            f"{service.upper()}_IMAGE={repo}\n{service.upper()}_IMAGE_DIGEST={digest(number + index)}\n"
            for index, (service, repo) in enumerate(REPOS.items())
        )
        (payload / "release.env").write_text(text, encoding="utf-8")
        return payload

    @contextlib.contextmanager
    def pointers(self, **targets):
        # Exercise pointer validation on Windows without requiring symlink admin
        # rights. Actual manifests and containment validation use the filesystem.
        original_symlink = Path.is_symlink
        original_resolve = Path.resolve
        links = {self.base / name: target for name, target in targets.items()}

        def resolve(path, strict=False):
            if path in links:
                if links[path] is None:
                    raise FileNotFoundError
                return links[path]
            return original_resolve(path, strict=strict)

        with patch.object(Path, "is_symlink", lambda path: path in links or original_symlink(path)), patch.object(Path, "resolve", resolve):
            yield

    def run_maintenance(self, fake, protected=(), required=(), known=(), *, apply=True, free=None, before=True):
        free = POLICY.MIN_FREE_BYTES if free is None else free
        output = io.StringIO()
        with (
            patch.object(POLICY, "docker", fake),
            patch.object(POLICY, "release_sets", return_value=(set(protected), set(required), set(known))),
            patch.object(POLICY, "disk_paths", return_value=[("synthetic", self.base)]),
            patch.object(POLICY.shutil, "disk_usage", return_value=types.SimpleNamespace(free=free)),
            contextlib.redirect_stdout(output),
        ):
            POLICY.maintain(self.base, self.incoming, apply=apply, before_pull=before)
        return output.getvalue()

    def test_manifest_reads_only_non_secret_release_image_keys(self):
        expected = {ref(service, 40 + index) for index, service in enumerate(REPOS)}
        self.assertEqual(POLICY.manifest(self.incoming, self.base), expected)

    def test_manifest_rejects_duplicate_mutable_wrong_service_and_other_registry(self):
        path = self.incoming / "release.env"
        good = path.read_text(encoding="utf-8")
        variants = [
            good + f"WEB_IMAGE={REPOS['web']}\n",
            good.replace(digest(40), "latest"),
            good.replace(REPOS["web"], REPOS["ai"]),
            good.replace(REPOS["web"], REPOS["web"].replace("111111111111", "222222222222")),
            good.replace(REPOS["web"], f"{REGISTRY}/other-project/web"),
        ]
        for text in variants:
            with self.subTest(text=text):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(POLICY.MaintenanceError):
                    POLICY.manifest(self.incoming, self.base)

    def test_path_escape_and_symlink_manifest_fail_closed(self):
        with self.assertRaises(POLICY.MaintenanceError):
            POLICY.manifest(self.base, self.base)
        original = Path.is_symlink
        with patch.object(Path, "is_symlink", lambda path: path.name == "release.env" or original(path)):
            with self.assertRaisesRegex(POLICY.MaintenanceError, "MANIFEST_UNAVAILABLE"):
                POLICY.manifest(self.incoming, self.base)

    def test_protects_current_previous_incoming_and_collects_historical_evidence(self):
        current, previous, old = (self.make_release(n) for n in (30, 20, 10))
        with self.pointers(current=current, previous=previous):
            protected, required, known = POLICY.release_sets(self.base, self.incoming)
        self.assertEqual(len(protected), 9)
        self.assertEqual(len(required), 6)
        self.assertEqual(len(known), 12)
        self.assertIn(ref("web", 10), known - protected)

    @unittest.skipIf(os.name == "nt", "Real POSIX release symlinks")
    def test_real_symlink_targets_remain_inside_release_root(self):
        current = self.make_release(30)
        (self.base / "current").symlink_to(current, target_is_directory=True)
        _, required, _ = POLICY.release_sets(self.base, self.incoming)
        self.assertEqual(required, POLICY.manifest(current, self.base))

    def test_first_release_has_no_required_rollback_images(self):
        protected, required, known = POLICY.release_sets(self.base, self.incoming)
        self.assertEqual(required, set())
        self.assertEqual(protected, known)

    def test_broken_pointer_does_not_silently_drop_rollback_protection(self):
        with self.pointers(previous=None), self.assertRaises(FileNotFoundError):
            POLICY.release_sets(self.base, self.incoming)

    def test_non_symlink_pointer_is_rejected(self):
        (self.base / "current").mkdir()
        with self.assertRaisesRegex(POLICY.MaintenanceError, "POINTER_INVALID"):
            POLICY.release_sets(self.base, self.incoming)

    def test_invalid_historical_manifest_does_not_authorize_deletion(self):
        old = self.make_release(10)
        (old / "release.env").write_text("invalid", encoding="utf-8")
        protected, _, known = POLICY.release_sets(self.base, self.incoming)
        self.assertEqual(known, protected)

    def test_removes_only_recorded_obsolete_release_image(self):
        refs = [ref("web", number) for number in range(1, 6)]
        fake = FakeDocker([image(n, [reference]) for n, reference in enumerate(refs, 1)], containers=[digest(4)])
        self.run_maintenance(fake, protected=refs[:3], required=refs[:2], known=refs)
        self.assertEqual(fake.removed, [digest(5)])
        self.assertTrue(any(call[0:4] == ("container", "ls", "--all", "--quiet") for call in fake.calls))

    def test_dangling_unrecorded_tempo_qa_and_mutable_aliases_stay(self):
        old = ref("web", 10)
        unknown = ref("web", 11)
        records = [
            image(1), image(2, [unknown]),
            image(3, [old], ["grafana/tempo:3.0.3"]),
            image(4, [old], ["waterbridge-backend-db-promotion:qa"]),
            image(5, [old], [f"{REPOS['web']}:latest"]),
            image(6, [old, f"{REGISTRY}/unrelated/app@{digest(9)}"]),
        ]
        fake = FakeDocker(records)
        self.run_maintenance(fake, known=[old])
        self.assertEqual(fake.removed, [])

    def test_same_image_id_as_retained_release_is_protected(self):
        old, retained = ref("web", 10), ref("web", 20)
        fake = FakeDocker([image(1, [old, retained])])
        self.run_maintenance(fake, protected=[retained], required=[retained], known=[old, retained])
        self.assertEqual(fake.removed, [])

    def test_containerd_digest_reference_in_repo_tags_is_eligible(self):
        # Shape observed on EC2: RepoTags AND RepoDigests contain repo@sha256.
        old = ref("ai", 10)
        fake = FakeDocker([image(10, [old], [old])])
        output = self.run_maintenance(fake, known=[old])
        self.assertIn("candidates=1 apply=true", output)
        self.assertEqual(fake.removed, [digest(10)])

    def test_containerd_snapshot_shape_keeps_six_apps_and_selects_95(self):
        refs = [ref(("web", "backend", "ai")[n % 3], n) for n in range(1, 102)]
        records = [image(n, [reference], [reference]) for n, reference in enumerate(refs, 1)]
        tempo = f"grafana/tempo@{digest(200)}"
        records.append(image(200, [tempo], [tempo]))
        records.extend(image(n, tags=[f"qa-tool:{n}"]) for n in range(201, 205))
        fake = FakeDocker(records, containers=[digest(n) for n in (1, 2, 3, 200)])
        incoming = [ref(service, n) for service, n in zip(REPOS, (301, 302, 303))]
        output = self.run_maintenance(
            fake, protected=refs[:6] + incoming, required=refs[:6], known=refs + incoming,
        )
        self.assertIn("candidates=95 apply=true", output)
        self.assertEqual(set(fake.removed), {digest(n) for n in range(7, 102)})
        self.assertTrue(all(digest(n) in fake.images for n in (1, 2, 3, 4, 5, 6, 200)))

    def test_digest_alias_must_be_recorded_and_belong_to_same_image(self):
        old, unknown, other_image = ref("web", 10), ref("web", 11), ref("web", 12)
        for alias in (unknown, other_image, old + "extra", old.upper()):
            with self.subTest(alias=alias):
                fake = FakeDocker([image(10, [old], [alias])])
                self.run_maintenance(fake, known=[old, other_image])
                self.assertEqual(fake.removed, [])

    def test_mixed_digest_and_commit_tags_still_protect_retained_releases(self):
        old = ref("web", 10)
        aliases = [old, f"{REPOS['web']}:{10:040x}"]
        for protected in ([], [old]):
            with self.subTest(protected=protected):
                fake = FakeDocker([image(10, [old], aliases)])
                self.run_maintenance(fake, known=[old], protected=protected, required=protected)
                self.assertEqual(fake.removed, [] if protected else [digest(10)])

    def test_unknown_digest_alias_in_same_repository_is_also_protected(self):
        old, unrecorded = ref("web", 10), ref("web", 11)
        fake = FakeDocker([image(1, [old, unrecorded])])
        self.run_maintenance(fake, known=[old])
        self.assertEqual(fake.removed, [])

    def test_digest_protection_handles_containerd_index_id_differences(self):
        retained = ref("web", 20)
        self.assertFalse(POLICY.eligible(image(1, [retained]), {retained}, {retained}, {digest(999)}))

    def test_missing_previous_image_stops_before_any_removal(self):
        fake = FakeDocker([image(1, [ref("web", 10)])])
        with self.assertRaises(POLICY.MaintenanceError):
            self.run_maintenance(fake, required=[ref("web", 20)], known=[ref("web", 10)])
        self.assertEqual(fake.removed, [])

    def test_dry_run_never_removes_images(self):
        old = ref("web", 10)
        fake = FakeDocker([image(1, [old])])
        output = self.run_maintenance(fake, known=[old], apply=False)
        self.assertIn("candidates=1 apply=false", output)
        self.assertEqual(fake.removed, [])

    def test_insufficient_space_blocks_before_pull_even_after_cleanup(self):
        old = ref("web", 10)
        fake = FakeDocker([image(1, [old])])
        with self.assertRaisesRegex(POLICY.MaintenanceError, "INSUFFICIENT_DISK_SPACE"):
            self.run_maintenance(fake, known=[old], free=POLICY.MIN_FREE_BYTES - 1)
        self.assertEqual(fake.removed, [digest(1)])

    def test_space_is_measured_again_after_cleanup(self):
        old = ref("web", 10)
        fake = FakeDocker([image(1, [old])])
        with (
            patch.object(POLICY, "docker", fake),
            patch.object(POLICY, "release_sets", return_value=(set(), set(), {old})),
            patch.object(POLICY, "disk_paths", return_value=[("synthetic", self.base)]),
            patch.object(POLICY.shutil, "disk_usage", side_effect=[types.SimpleNamespace(free=1), types.SimpleNamespace(free=POLICY.MIN_FREE_BYTES)]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            POLICY.maintain(self.base, self.incoming, apply=True, before_pull=True)
        self.assertEqual(fake.removed, [digest(1)])

    def test_refused_removal_is_not_forced(self):
        old = ref("web", 10)
        fake = FakeDocker([image(1, [old])])
        fake.refuse.add(digest(1))
        output = self.run_maintenance(fake, known=[old])
        self.assertIn("refused=1", output)
        self.assertEqual(fake.removed, [])
        self.assertNotIn("--force", [value for call in fake.calls for value in call])

    def test_new_container_reference_after_plan_is_protected(self):
        old = ref("web", 10)
        fake = FakeDocker([image(1, [old])])
        with patch.object(POLICY, "container_images", side_effect=[set(), {digest(1)}]):
            self.run_maintenance(fake, known=[old])
        self.assertEqual(fake.removed, [])

    def test_changed_aliases_after_plan_are_not_removed(self):
        old = ref("web", 10)
        fake = FakeDocker([image(1, [old])])
        with patch.object(POLICY, "image_metadata", side_effect=[image(1, [old]), image(1, [old], ["unrelated:stable"])]):
            self.run_maintenance(fake, known=[old])
        self.assertEqual(fake.removed, [])

    def test_post_success_low_space_does_not_fail_runtime(self):
        self.run_maintenance(FakeDocker([]), free=1, before=False)

    def test_active_canary_blocks_all_docker_commands(self):
        (self.base / "shared/ai-handoff-canary.state").touch()
        fake = FakeDocker([])
        with self.assertRaisesRegex(POLICY.MaintenanceError, "CANARY_ACTIVE"):
            self.run_maintenance(fake)
        self.assertEqual(fake.calls, [])

    def test_active_context_activation_blocks_all_docker_commands(self):
        (self.base / "shared/ai-context-activation.state").touch()
        fake = FakeDocker([])
        with self.assertRaisesRegex(
            POLICY.MaintenanceError,
            "CONTEXT_ACTIVATION_ACTIVE",
        ):
            self.run_maintenance(fake)
        self.assertEqual(fake.calls, [])

    def test_each_filesystem_is_checked_not_only_docker_root(self):
        with patch.object(POLICY.shutil, "disk_usage", side_effect=[types.SimpleNamespace(free=POLICY.MIN_FREE_BYTES), types.SimpleNamespace(free=1)]), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(POLICY.MaintenanceError, "INSUFFICIENT_DISK_SPACE"):
                POLICY.check_space([("docker", self.base), ("containerd", self.base)], enforce=True)

    def test_storage_discovery_includes_host_docker_and_containerd(self):
        root = str(self.base / "docker")
        with patch.object(POLICY, "docker", return_value=root), patch.object(Path, "is_dir", return_value=True):
            self.assertEqual([label for label, _ in POLICY.disk_paths(self.base)], ["host", "release", "docker", "containerd"])

    def test_unknown_containerd_location_fails_closed(self):
        root = self.base / "docker"
        with patch.object(POLICY, "docker", side_effect=[str(root), "overlayfs"]), patch.object(Path, "is_dir", lambda path: path == root):
            with self.assertRaisesRegex(POLICY.MaintenanceError, "CONTAINERD_STORAGE_PATH_UNVERIFIED"):
                POLICY.disk_paths(self.base)

    def test_docker_error_and_timeout_are_sanitized(self):
        with patch.object(POLICY.subprocess, "run", return_value=types.SimpleNamespace(returncode=1, stderr="sensitive-value", stdout="sensitive-value")):
            with self.assertRaisesRegex(POLICY.MaintenanceError, "^DOCKER_COMMAND_FAILED$"):
                POLICY.docker("image", "ls")
        with patch.object(POLICY.subprocess, "run", side_effect=subprocess.TimeoutExpired("docker", 60)):
            with self.assertRaisesRegex(POLICY.MaintenanceError, "^DOCKER_UNAVAILABLE$"):
                POLICY.docker("image", "ls")

    def test_malformed_docker_metadata_fails_closed(self):
        for data in ("not-json", '["bad-id", [], []]', '["' + digest(1) + '", {}, []]'):
            with self.subTest(data=data), patch.object(POLICY, "docker", return_value=data):
                with self.assertRaises(POLICY.MaintenanceError):
                    POLICY.image_metadata(digest(1))

    def test_inherited_lock_must_reference_the_deploy_lock(self):
        fake_fcntl = types.SimpleNamespace(LOCK_EX=2, LOCK_NB=4, flock=lambda *_: None)
        expected = types.SimpleNamespace(st_dev=1, st_ino=10)
        with patch.dict("sys.modules", fcntl=fake_fcntl), patch.object(POLICY.os, "fstat", return_value=expected), patch.object(Path, "stat", return_value=expected):
            POLICY.require_deployment_lock(self.base)
        with patch.dict("sys.modules", fcntl=fake_fcntl), patch.object(POLICY.os, "fstat", side_effect=OSError):
            with self.assertRaisesRegex(POLICY.MaintenanceError, "DEPLOYMENT_LOCK_REQUIRED"):
                POLICY.require_deployment_lock(self.base)
        wrong = types.SimpleNamespace(st_dev=1, st_ino=11)
        with patch.dict("sys.modules", fcntl=fake_fcntl), patch.object(POLICY.os, "fstat", return_value=wrong), patch.object(Path, "stat", return_value=expected):
            with self.assertRaisesRegex(POLICY.MaintenanceError, "DEPLOYMENT_LOCK_INVALID"):
                POLICY.require_deployment_lock(self.base)

    def test_main_requires_lock_and_does_not_expose_failure_input(self):
        output = io.StringIO()
        with patch("sys.argv", [str(SCRIPT), "--release-dir", str(self.incoming), "--phase", "before-pull", "--apply"]), patch.object(POLICY, "require_deployment_lock", side_effect=OSError("sensitive-path")), contextlib.redirect_stderr(output):
            self.assertEqual(POLICY.main(), 1)
        self.assertNotIn("sensitive-path", output.getvalue())


class MaintenanceShellIntegrationTests(unittest.TestCase):
    def bash(self):
        bash = shutil.which("bash")
        if os.name == "nt":
            git = shutil.which("git")
            candidate = Path(git).resolve().parents[1] / "bin/bash.exe" if git else None
            bash = str(candidate) if candidate and candidate.is_file() else None
        if not bash:
            self.skipTest("Bash required for isolated shell regression")
        return bash

    def test_pre_pull_failure_exits_without_runtime_mutation(self):
        deploy = (SCRIPT.parent / "deploy-release.sh").read_text(encoding="utf-8")
        pre = next(line for line in deploy.splitlines() if line.startswith('python3 "$image_maintenance_script"'))
        script = (
            "set -euo pipefail\nimage_maintenance_script=synthetic\npayload_dir=synthetic\n"
            "python3() { return 42; }\n" + pre + "\nprintf 'MUTATION_STARTED\\n'\n"
        )
        result = subprocess.run([self.bash(), "--noprofile", "--norc", "-c", script], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 42)
        self.assertNotIn("MUTATION_STARTED", result.stdout)

    def test_post_success_maintenance_error_does_not_rollback(self):
        deploy = (SCRIPT.parent / "deploy-release.sh").read_text(encoding="utf-8")
        post = deploy[deploy.rindex("trap - ERR\n"):]
        script = (
            "set -euo pipefail\nimage_maintenance_script=synthetic\npayload_dir=synthetic\n"
            "release_sha=synthetic\npython3() { return 42; }\n"
            "trap 'printf ROLLBACK_EXECUTED; exit 1' ERR\n" + post
        )
        result = subprocess.run([self.bash(), "--noprofile", "--norc", "-c", script], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DEPLOYMENT_RUNTIME_PASS", result.stdout)
        self.assertIn("RELEASE_IMAGE_CLEANUP_WARNING", result.stderr)
        self.assertNotIn("ROLLBACK_EXECUTED", result.stdout)

    @unittest.skipIf(os.name == "nt", "Real POSIX inherited flock")
    def test_real_inherited_lock_remains_held_by_deployment_shell(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            (base / "shared").mkdir()
            lock = base / "shared/deploy.lock"
            verify = (
                "import runpy, sys; from pathlib import Path; "
                "module = runpy.run_path(sys.argv[1]); "
                "module['require_deployment_lock'](Path(sys.argv[2]))"
            )
            competitor = (
                "import fcntl, sys\n"
                "with open(sys.argv[1], 'w') as lock:\n"
                " try:\n"
                "  fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
                " except BlockingIOError:\n"
                "  print('LOCK_STILL_HELD')\n"
                " else:\n"
                "  raise SystemExit(1)\n"
            )
            shell = 'set -euo pipefail\nexec 9>"$1"\n"$2" -B -c "$3" "$4" "$5"\n"$2" -B -c "$6" "$1"\n'
            result = subprocess.run(
                [self.bash(), "--noprofile", "--norc", "-c", shell, "qa", str(lock), sys.executable, verify, str(SCRIPT), str(base), competitor],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("LOCK_STILL_HELD", result.stdout)


if __name__ == "__main__":
    unittest.main()
