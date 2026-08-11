#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

CUSTOMER_PKG = "com.skn29.watercare.customer"
TECH_PKG = "com.skn29.watercare.technician"


def merged_env(extra=None):
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["GIT_PAGER"] = "cat"
    env["GIT_TERMINAL_PROMPT"] = "0"
    if extra:
        env.update(extra)
    return env


def run(cmd, cwd=None, check=True, capture=True, env=None):
    print("+", " ".join(map(str, cmd)))
    proc = subprocess.run(
        [str(x) for x in cmd],
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        encoding="utf-8",
        errors="replace",
        env=merged_env(env),
    )
    if capture:
        if proc.stdout:
            print(proc.stdout.rstrip())
        if proc.stderr:
            print(proc.stderr.rstrip())
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"command failed({proc.returncode}): {' '.join(map(str, cmd))}"
        )
    return proc


def git(repo: Path, *args, check=True):
    return run(["git", "-C", repo, *args], check=check).stdout.rstrip()


def python_version(executable: Path):
    p = run(
        [executable, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"],
        check=False,
    )
    return p.stdout.strip() if p.returncode == 0 else ""


def py313_executable():
    launcher = shutil.which("py")
    if not launcher:
        return None
    p = run(
        [launcher, "-3.13", "-c", "import sys; print(sys.executable)"],
        check=False,
    )
    if p.returncode == 0 and p.stdout.strip():
        candidate = Path(p.stdout.strip())
        if candidate.exists():
            return candidate
    return None


def find_backend_python(repo: Path, config_source: Path, repo_source: Path) -> Path:
    candidates = [
        repo / "backend" / ".venv" / "Scripts" / "python.exe",
        config_source / "backend" / ".venv" / "Scripts" / "python.exe",
        repo_source / "backend" / ".venv" / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    py313 = py313_executable()
    if py313:
        return py313

    current = shutil.which("python")
    if current:
        return Path(current)

    raise RuntimeError("Backend Python executable not found")


def ensure_backend_imports(executable: Path):
    p = run(
        [
            executable,
            "-c",
            "import django, pytest, rest_framework; print('BACKEND_IMPORTS_OK')",
        ],
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError(
            "선택된 Python에 Backend 의존성이 없습니다. "
            "backend .venv 또는 Python 3.13 환경이 필요합니다."
        )


def find_adb() -> Path:
    direct = shutil.which("adb")
    if direct:
        return Path(direct)

    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidate = (
            Path(local)
            / "Android"
            / "Sdk"
            / "platform-tools"
            / "adb.exe"
        )
        if candidate.exists():
            return candidate

    raise RuntimeError("adb.exe not found")


def one_device(adb: Path) -> str:
    run([adb, "start-server"])
    output = run([adb, "devices"]).stdout
    devices = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == "device":
            devices.append(parts[0])
    if len(devices) != 1:
        raise RuntimeError(
            f"Exactly one authorized adb device required; found={len(devices)}"
        )
    return devices[0]


def free_port():
    for port in range(8011, 8031):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port 8011..8030")


def http(method, url, body=None, headers=None):
    data = None
    hdr = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdr["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=data,
        headers=hdr,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read().decode("utf-8")
            return (
                response.status,
                json.loads(raw) if raw else None,
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            payload = json.loads(raw) if raw else None
        except Exception:
            payload = None
        return exc.code, payload


def wait_health(base):
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            status, _ = http("GET", base + "/health")
            if status == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def find_test_apk(root: Path):
    apks = list(root.rglob("*.apk"))
    if not apks:
        raise RuntimeError(f"No APK under {root}")
    return max(apks, key=lambda p: p.stat().st_mtime)


def instrumentation_component(adb, serial, target):
    output = run(
        [
            adb,
            "-s",
            serial,
            "shell",
            "pm",
            "list",
            "instrumentation",
        ]
    ).stdout
    for line in output.splitlines():
        match = re.match(
            r"instrumentation:([^\s]+)\s+\(target=([^)]+)\)",
            line,
        )
        if match and match.group(2) == target:
            return match.group(1)
    raise RuntimeError(f"No instrumentation for {target}")


def instrument(adb, serial, component, class_name, remote=False):
    command = [
        adb,
        "-s",
        serial,
        "shell",
        "am",
        "instrument",
        "-w",
        "-r",
    ]
    if remote:
        command += ["-e", "runRemoteSmoke", "true"]
    command += [
        "-e",
        "class",
        class_name,
        component,
    ]
    proc = run(command, check=False)
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if (
        proc.returncode != 0
        or "FAILURES!!!" in combined
        or "INSTRUMENTATION_FAILED" in combined
        or "OK (" not in combined
    ):
        raise RuntimeError(f"Instrumentation failed: {class_name}")


def copy_if_exists(src: Path, dst: Path):
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"COPIED_LOCAL_CONFIG={dst}")
    return True


def fresh_worktree_path():
    base = Path(f"C:/w88r5_{time.strftime('%H%M%S')}")
    candidate = base
    counter = 1
    while candidate.exists():
        candidate = Path(str(base) + f"_{counter}")
        counter += 1
    return candidate



CUSTOMER_UI_TEST = (
    "mobile/customer-app/src/androidTest/java/"
    "com/skn29/watercare/customer/CustomerMinimumFlowTest.kt"
)
TECHNICIAN_UI_TEST = (
    "mobile/technician-app/src/androidTest/java/"
    "com/skn29/watercare/technician/TechnicianMinimumFlowTest.kt"
)
TECHNICIAN_DEBUG_MANIFEST = "mobile/technician-app/src/debug/AndroidManifest.xml"
TECHNICIAN_DEBUG_HOST = (
    "mobile/technician-app/src/debug/java/"
    "com/skn29/watercare/technician/testing/ComposeTestActivity.kt"
)


def ensure_debug_compose_host(
    repo: Path,
    manifest_rel: str,
    host_rel: str,
    package_name: str,
):
    manifest = repo / manifest_rel
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application>
        <activity
            android:name=".testing.ComposeTestActivity"
            android:exported="false" />
    </application>
</manifest>
""",
        encoding="utf-8",
    )

    host = repo / host_rel
    host.parent.mkdir(parents=True, exist_ok=True)
    host.write_text(
        f"""package {package_name}

import androidx.activity.ComponentActivity

/**
 * Compose 계측 테스트용 debug-only Activity host.
 * 실제 애플리케이션 진입점에는 포함되지 않는다.
 */
class ComposeTestActivity : ComponentActivity()
""",
        encoding="utf-8",
    )


def convert_to_functional_compose_ui_test(
    repo: Path,
    rel: str,
    host_import: str,
):
    import re

    path = repo / rel
    if not path.exists():
        raise RuntimeError(f"UI test file missing: {rel}")

    text = path.read_text(encoding="utf-8")

    # Remove Rule-based environment imports.
    text = text.replace("import androidx.activity.ComponentActivity\n", "")
    text = text.replace(
        "import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule\n",
        "",
    )
    text = text.replace(
        "import androidx.compose.ui.test.junit4.createAndroidComposeRule\n",
        "",
    )
    text = text.replace("import org.junit.Rule\n", "")

    # Add current official v2 functional environment.
    if "import androidx.compose.ui.test.ExperimentalTestApi\n" not in text:
        anchor = "import androidx.compose.ui.test.assertIsDisplayed\n"
        if anchor not in text:
            raise RuntimeError(f"Compose import anchor missing: {rel}")
        text = text.replace(
            anchor,
            "import androidx.compose.ui.test.ExperimentalTestApi\n" + anchor,
            1,
        )

    if "import androidx.compose.ui.test.v2.runAndroidComposeUiTest\n" not in text:
        anchor = "import androidx.compose.ui.test.performScrollTo\n"
        if anchor not in text:
            raise RuntimeError(f"performScrollTo import anchor missing: {rel}")
        text = text.replace(
            anchor,
            anchor + "import androidx.compose.ui.test.v2.runAndroidComposeUiTest\n",
            1,
        )

    if f"import {host_import}\n" not in text:
        anchor = "import org.junit.Test\n"
        if anchor not in text:
            raise RuntimeError(f"JUnit Test import anchor missing: {rel}")
        text = text.replace(
            anchor,
            f"import {host_import}\n" + anchor,
            1,
        )

    # Remove the Rule property, regardless of ComponentActivity/ComposeTestActivity.
    text = re.sub(
        r"\n\s*@get:Rule\s*\n\s*val composeRule\s*=\s*"
        r"createAndroidComposeRule<[^>]+>\(\)\s*\n",
        "\n",
        text,
        count=1,
    )

    # Convert each @Test function to official v2 functional test environment.
    pattern = re.compile(
        r"(?m)^    @Test\n"
        r"    fun ([A-Za-z0-9_]+)\(\) \{"
    )
    names = pattern.findall(text)
    if len(names) < 1:
        # Idempotency: already converted is fine.
        already = re.findall(
            r"runAndroidComposeUiTest<ComposeTestActivity>",
            text,
        )
        if not already:
            raise RuntimeError(f"No test functions converted: {rel}")
    else:
        text = pattern.sub(
            lambda m: (
                "    @Test\n"
                "    @OptIn(ExperimentalTestApi::class)\n"
                f"    fun {m.group(1)}() = "
                "runAndroidComposeUiTest<ComposeTestActivity> {"
            ),
            text,
        )

    text = text.replace("composeRule.", "")

    # Strong final assertions.
    if "createAndroidComposeRule" in text:
        raise RuntimeError(f"Rule API remains: {rel}")
    if "composeRule." in text:
        raise RuntimeError(f"composeRule receiver remains: {rel}")
    if "runAndroidComposeUiTest<ComposeTestActivity>" not in text:
        raise RuntimeError(f"Functional v2 API missing: {rel}")

    path.write_text(text, encoding="utf-8")
    print(f"T088R5_FUNCTIONAL_UI_TEST_CONVERTED={rel}")


def append_readme(readme: Path):
    marker = "## Week5 Autonomous Completion Gate"
    text = readme.read_text(encoding="utf-8")
    if marker in text:
        return

    addition = """
## Week5 Autonomous Completion Gate

5주차 업무지침서에서 Mobile 담당자가 독자적으로 수행 가능한 회귀·실단말·보안·Runtime 판정을 자동화한다.

반복 실행:

```powershell
python personal/mobile-extension/scripts/run_week5_autonomous_gate.py --repo-source <repo> --config-source <config-worktree> --bundle-dir <bundle>
```

판정 원칙:

- 고객 Subscription / Inquiry create / symptom submit: 실제 Runtime 사용
- 상담사 Consultation / Visit scheduling: Backend Runtime 존재 여부와 회귀 검증
- 고객 Follow-up / request-consultation: Runtime 미구현이면 Blocked
- 기사 assigned Visit list/detail / start / complete: Runtime 미구현이면 Blocked
- Guidance/Evidence: 고객 Runtime 미구현이면 Remote fail-closed
- 미구현 Runtime을 Mobile Fake 성공으로 대체하지 않음
"""
    readme.write_text(
        text.rstrip() + "\n\n" + addition.strip() + "\n",
        encoding="utf-8",
    )


def write_report(repo: Path, values: dict):
    report = (
        repo
        / "personal"
        / "mobile-extension"
        / "docs"
        / "week5-autonomous-completion.md"
    )
    lines = [
        "# Week5 Autonomous Mobile Completion",
        "",
        f"- Integrated base: `{values['integrated_head']}`",
        f"- Latest main: `{values['main']}`",
        f"- Backend Python: `{values['python_version']}`",
        f"- Device: {values['device_model']} / Android {values['device_android']}",
        "",
        "## Independently verified",
        "",
        "- Latest main → jeonghyun local merge candidate: **PASS**",
        "- Static API/Runtime/Fake/security boundary: **PASS**",
        "- Official v2 `runAndroidComposeUiTest` UI environment: **PASS**",
        "- Core / Customer / Technician Unit + Debug APK: **PASS**",
        "- Customer / Technician androidTest APK build: **PASS**",
        "- T-018 Subscription backend regression: **PASS**",
        "- T-022 Inquiry submit / Idempotency / 401 / 403 / 404 / 409 / 422 regression: **PASS**",
        "- Consultation / Visit scheduling backend regression: **PASS**",
        "- Week5 action contract regression: **PASS**",
        "- Model / migration consistency (`makemigrations --check --dry-run`): **PASS**",
        "- Live anonymous `/me` 401: **PASS**",
        "- Live customer login / refresh / `/me`: **PASS**",
        "- Live ACTIVE `WPUJAC104DWH` subscription list/detail: **PASS**",
        "- Live unknown subscription 404: **PASS**",
        "- Live Consultation route registration anonymous 401: **PASS**",
        "- Live Visit-review route registration anonymous 401: **PASS**",
        "- Customer Galaxy UI instrumentation: **PASS**",
        "- Customer Galaxy Remote Backend smoke: **PASS**",
        "- Technician Galaxy UI instrumentation: **PASS**",
        "- Technician Galaxy Remote Auth smoke: **PASS**",
        f"- Customer APK SHA-256: `{values['customer_hash']}`",
        f"- Technician APK SHA-256: `{values['technician_hash']}`",
        "",
        "## 업무지침서 3.1 ~ 3.7",
        "",
        "| 항목 | 판정 |",
        "| --- | --- |",
        "| 3.1 기준선·Runtime·Build Gate | DONE |",
        "| 3.2 고객 Subscription Remote | DONE / REAL_DEVICE |",
        "| 3.3 Inquiry create·symptom·Idempotency·Conflict | DONE 범위 PASS / Follow-up Runtime 대기 |",
        "| 3.4 Guidance·Evidence | MOBILE FAIL-CLOSED PASS / Backend 고객 Runtime 대기 |",
        "| 3.5 Technician Visit | UI·Fail-closed PASS / 기사 실행 Runtime 대기 |",
        "| 3.6 대표 Full E2E | BLOCKED_BY_BACKEND |",
        "| 3.7 회귀·APK·실단말·Hash | DONE |",
        "",
        "## Latest Runtime distinction",
        "",
        "- Consultation start/summary/confirm/complete: **IMPLEMENTED, 상담사 업무 Runtime**",
        "- Visit review/create/schedule/confirm: **IMPLEMENTED, 상담사 업무 Runtime**",
        "- Customer Follow-up answers: **NOT_IMPLEMENTED**",
        "- Customer request-consultation: **NOT_IMPLEMENTED**",
        "- Customer Guidance/Evidence: **NOT_IMPLEMENTED**",
        "- Technician assigned Visit list/detail: **NOT_IMPLEMENTED**",
        "- Technician Visit start/complete: **NOT_IMPLEMENTED**",
        "",
        "## Remaining external blockers",
        "",
    ]
    for blocker in values["blocked"]:
        lines.append(f"- {blocker}")

    lines += [
        "",
        "위 Blocker는 Mobile에서 임의 Endpoint 또는 Fake 성공으로 대체하지 않는다.",
        "",
        "**INDEPENDENT_MOBILE_WEEK5 = PASS**",
        "",
        "**FULL_P0_FEATURE_COMPLETE = BLOCKED_BY_BACKEND**",
        "",
    ]

    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-source", required=True)
    parser.add_argument("--config-source", required=True)
    parser.add_argument("--bundle-dir", required=True)
    args = parser.parse_args()

    source = Path(args.repo_source).resolve()
    config_source = Path(args.config_source).resolve()
    bundle = Path(args.bundle_dir).resolve()

    print("T088R5_SCOPE=WEEK5_AUTONOMOUS_LATEST_MAIN")
    print("T088R5_ENCODING=UTF8_WITH_REPLACEMENT")

    run(
        [
            "git",
            "-C",
            source,
            "fetch",
            "origin",
            "main",
            "jeonghyun",
            "--prune",
        ]
    )
    main_sha = git(source, "rev-parse", "origin/main")
    jeong_sha = git(source, "rev-parse", "origin/jeonghyun")
    print(f"T088R5_REMOTE_MAIN={main_sha}")
    print(f"T088R5_REMOTE_JEONGHYUN={jeong_sha}")

    work = fresh_worktree_path()
    run(
        [
            "git",
            "-C",
            source,
            "worktree",
            "add",
            "--detach",
            work,
            jeong_sha,
        ]
    )
    print(f"T088R5_WORKTREE={work}")

    copy_if_exists(
        config_source / "mobile" / "local.properties",
        work / "mobile" / "local.properties",
    )
    copy_if_exists(
        config_source / "backend" / ".env",
        work / "backend" / ".env",
    )

    merge_message = (
        "2026-08-10 | 최신 main 상담·방문 Runtime 반영 완룡 >.<"
    )
    run(
        [
            "git",
            "-C",
            work,
            "merge",
            "--no-ff",
            main_sha,
            "-m",
            merge_message,
        ]
    )
    integrated_head = git(work, "rev-parse", "HEAD")
    print("T088R5_MAIN_MERGE_LOCAL=PASS")
    print(f"T088R5_INTEGRATED_HEAD={integrated_head}")

    extension = work / "personal" / "mobile-extension"
    if not extension.exists():
        raise RuntimeError(
            "personal/mobile-extension scaffold missing after merge"
        )

    scripts = extension / "scripts"
    tests = extension / "tests"
    scripts.mkdir(parents=True, exist_ok=True)
    tests.mkdir(parents=True, exist_ok=True)

    shutil.copy2(
        bundle / "run_week5_autonomous_gate.py",
        scripts / "run_week5_autonomous_gate.py",
    )
    shutil.copy2(
        bundle / "test_week5_contract_static.py",
        tests / "test_week5_contract_static.py",
    )
    append_readme(extension / "README.md")

    # Ensure explicit debug-only Activity hosts for functional v2 UI tests.
    ensure_debug_compose_host(
        work,
        "mobile/customer-app/src/debug/AndroidManifest.xml",
        "mobile/customer-app/src/debug/java/com/skn29/watercare/customer/testing/ComposeTestActivity.kt",
        "com.skn29.watercare.customer.testing",
    )
    ensure_debug_compose_host(
        work,
        TECHNICIAN_DEBUG_MANIFEST,
        TECHNICIAN_DEBUG_HOST,
        "com.skn29.watercare.technician.testing",
    )

    convert_to_functional_compose_ui_test(
        work,
        CUSTOMER_UI_TEST,
        "com.skn29.watercare.customer.testing.ComposeTestActivity",
    )
    convert_to_functional_compose_ui_test(
        work,
        TECHNICIAN_UI_TEST,
        "com.skn29.watercare.technician.testing.ComposeTestActivity",
    )
    print("T088R5_FUNCTIONAL_COMPOSE_ENVIRONMENT=PASS")

    backend_python = find_backend_python(
        work,
        config_source,
        source,
    )
    version = python_version(backend_python)
    print(f"T088R5_BACKEND_PYTHON={backend_python}")
    print(f"T088R5_BACKEND_PYTHON_VERSION={version}")

    if version.startswith("3.14"):
        print(
            "T088R5_PYTHON_NOTE=3.14_UNVERIFIED_FALLBACK_"
            "OFFICIAL_LOCK_VALIDATED_ON_3.13.13"
        )

    ensure_backend_imports(backend_python)
    print("T088R5_BACKEND_PYTHON_IMPORTS=PASS")

    run(
        [
            backend_python,
            tests / "test_week5_contract_static.py",
            "--repo",
            work,
        ],
        cwd=work,
    )
    print("W5AUTO_STATIC_CONTRACT=PASS")

    run(
        ["cmd.exe", "/d", "/c", "verify-build.bat"],
        cwd=work / "mobile",
    )
    print("W5AUTO_VERIFY_BUILD=PASS")

    run(
        [
            "cmd.exe",
            "/d",
            "/c",
            (
                "gradlew.bat --no-daemon "
                ":customer-app:assembleDebugAndroidTest "
                ":technician-app:assembleDebugAndroidTest"
            ),
        ],
        cwd=work / "mobile",
    )
    print("W5AUTO_ANDROID_TEST_APKS=PASS")

    run(
        [
            backend_python,
            "-m",
            "pytest",
            "-q",
            "tests/api/test_t018_subscription_runtime.py",
            "tests/api/test_t022_submit_symptom.py",
            "tests/api/test_consultation_visit_runtime.py",
        ],
        cwd=work / "backend",
    )
    print("W5AUTO_BACKEND_RUNTIME_REGRESSION=PASS")

    run(
        [
            backend_python,
            "-m",
            "pytest",
            "-q",
            "tests/contract/api/test_week5_e2e_action_contract.py",
        ],
        cwd=work,
    )
    print("W5AUTO_WEEK5_ACTION_CONTRACT=PASS")

    run(
        [
            backend_python,
            "manage.py",
            "makemigrations",
            "--check",
            "--dry-run",
        ],
        cwd=work / "backend",
    )
    print("W5AUTO_MIGRATION_MODEL_CONSISTENCY=PASS")

    port = free_port()
    base = f"http://127.0.0.1:{port}"

    log_dir = (
        work
        / "mobile"
        / "build"
        / "reports"
        / "week5-autonomous"
    )
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_handle = open(
        log_dir / "backend.stdout.log",
        "w",
        encoding="utf-8",
    )
    stderr_handle = open(
        log_dir / "backend.stderr.log",
        "w",
        encoding="utf-8",
    )

    server = subprocess.Popen(
        [
            str(backend_python),
            "manage.py",
            "runserver",
            f"127.0.0.1:{port}",
            "--noreload",
        ],
        cwd=str(work / "backend"),
        stdout=stdout_handle,
        stderr=stderr_handle,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=merged_env(),
    )

    try:
        if not wait_health(base):
            raise RuntimeError("Backend health timeout")
        print("W5AUTO_BACKEND_HEALTH=PASS")

        status, _ = http("GET", base + "/api/v1/me")
        if status != 401:
            raise RuntimeError(
                f"anonymous /me expected 401, got {status}"
            )
        print("W5AUTO_LIVE_401=PASS")

        status, login = http(
            "POST",
            base + "/api/v1/auth/demo-login",
            {"demo_user_code": "SYN-CUSTOMER-001"},
        )
        if (
            status != 200
            or not login
            or not login.get("data", {}).get("access_token")
        ):
            raise RuntimeError(
                f"SYN-CUSTOMER-001 login failed status={status}"
            )

        access = login["data"]["access_token"]
        refresh = login["data"]["refresh_token"]
        headers = {
            "Authorization": f"Bearer {access}",
        }
        print("W5AUTO_LIVE_CUSTOMER_LOGIN=PASS")

        status, refreshed = http(
            "POST",
            base + "/api/v1/auth/refresh",
            {"refresh_token": refresh},
        )
        if (
            status != 200
            or not refreshed
            or not refreshed.get("data", {}).get("access_token")
        ):
            raise RuntimeError(
                f"refresh failed status={status}"
            )

        headers = {
            "Authorization": (
                f"Bearer {refreshed['data']['access_token']}"
            )
        }
        status, me = http(
            "GET",
            base + "/api/v1/me",
            headers=headers,
        )
        if (
            status != 200
            or me.get("data", {}).get("role_code") != "CUSTOMER"
        ):
            raise RuntimeError(
                "refreshed /me validation failed"
            )
        print("W5AUTO_LIVE_REFRESH=PASS")

        status, subscriptions = http(
            "GET",
            base + "/api/v1/me/subscriptions?page=1&size=20",
            headers=headers,
        )
        if status != 200:
            raise RuntimeError(
                f"subscription list failed status={status}"
            )

        items = subscriptions.get("data", {}).get("items", [])
        target = next(
            (
                item
                for item in items
                if item.get("status_code") == "ACTIVE"
                and item.get("product", {}).get("model_code")
                == "WPUJAC104DWH"
            ),
            None,
        )
        if not target:
            raise RuntimeError(
                "ACTIVE WPUJAC104DWH subscription not found"
            )

        subscription_id = target["subscription_id"]
        status, detail = http(
            "GET",
            base
            + f"/api/v1/me/subscriptions/{subscription_id}",
            headers=headers,
        )
        if (
            status != 200
            or detail.get("data", {}).get("subscription_id")
            != subscription_id
        ):
            raise RuntimeError("subscription detail failed")
        print("W5AUTO_LIVE_SUBSCRIPTION=PASS")

        status, _ = http(
            "GET",
            base
            + f"/api/v1/me/subscriptions/{uuid.uuid4()}",
            headers=headers,
        )
        if status != 404:
            raise RuntimeError(
                f"unknown subscription expected 404, got {status}"
            )
        print("W5AUTO_LIVE_404=PASS")

        random_id = str(uuid.uuid4())
        status, _ = http(
            "POST",
            base
            + f"/api/v1/inquiries/{random_id}/start-consultation",
            {},
        )
        if status != 401:
            raise RuntimeError(
                "start-consultation route expected "
                f"anonymous 401, got {status}"
            )
        print(
            "W5AUTO_CONSULTATION_ROUTE_REGISTERED=PASS"
        )

        status, _ = http(
            "POST",
            base
            + f"/api/v1/inquiries/{random_id}/visit-review",
            {},
        )
        if status != 401:
            raise RuntimeError(
                "visit-review route expected "
                f"anonymous 401, got {status}"
            )
        print(
            "W5AUTO_VISIT_SCHEDULING_ROUTE_REGISTERED=PASS"
        )

        customer_apk = (
            work
            / "mobile"
            / "customer-app"
            / "build"
            / "outputs"
            / "apk"
            / "debug"
            / "customer-app-debug.apk"
        )
        technician_apk = (
            work
            / "mobile"
            / "technician-app"
            / "build"
            / "outputs"
            / "apk"
            / "debug"
            / "technician-app-debug.apk"
        )
        if not customer_apk.exists():
            raise RuntimeError("Customer debug APK missing")
        if not technician_apk.exists():
            raise RuntimeError("Technician debug APK missing")

        customer_hash = sha256(customer_apk)
        technician_hash = sha256(technician_apk)
        print(
            f"W5AUTO_CUSTOMER_APK_SHA256={customer_hash}"
        )
        print(
            f"W5AUTO_TECHNICIAN_APK_SHA256={technician_hash}"
        )
        print("W5AUTO_APK_HASH=PASS")

        adb = find_adb()
        serial = one_device(adb)
        device_model = run(
            [
                adb,
                "-s",
                serial,
                "shell",
                "getprop",
                "ro.product.model",
            ]
        ).stdout.strip()
        device_android = run(
            [
                adb,
                "-s",
                serial,
                "shell",
                "getprop",
                "ro.build.version.release",
            ]
        ).stdout.strip()

        print(f"W5AUTO_DEVICE_SERIAL={serial}")
        print(f"W5AUTO_DEVICE_MODEL={device_model}")
        print(f"W5AUTO_DEVICE_ANDROID={device_android}")

        customer_test_apk = find_test_apk(
            work
            / "mobile"
            / "customer-app"
            / "build"
            / "outputs"
            / "apk"
            / "androidTest"
        )
        technician_test_apk = find_test_apk(
            work
            / "mobile"
            / "technician-app"
            / "build"
            / "outputs"
            / "apk"
            / "androidTest"
        )

        for apk in (
            customer_apk,
            customer_test_apk,
            technician_apk,
            technician_test_apk,
        ):
            run(
                [
                    adb,
                    "-s",
                    serial,
                    "install",
                    "-r",
                    "-t",
                    apk,
                ]
            )
        print("W5AUTO_DEVICE_INSTALL=PASS")

        run(
            [
                adb,
                "-s",
                serial,
                "reverse",
                "tcp:8000",
                f"tcp:{port}",
            ]
        )
        print("W5AUTO_ADB_REVERSE=PASS")

        customer_component = instrumentation_component(
            adb,
            serial,
            CUSTOMER_PKG,
        )
        technician_component = instrumentation_component(
            adb,
            serial,
            TECH_PKG,
        )

        instrument(
            adb,
            serial,
            customer_component,
            (
                "com.skn29.watercare.customer."
                "CustomerMinimumFlowTest"
            ),
        )
        print("W5AUTO_CUSTOMER_UI_DEVICE=PASS")

        instrument(
            adb,
            serial,
            customer_component,
            (
                "com.skn29.watercare.customer."
                "CustomerRemoteBackendSmokeTest"
            ),
            remote=True,
        )
        print("W5AUTO_CUSTOMER_REMOTE_DEVICE=PASS")

        instrument(
            adb,
            serial,
            technician_component,
            (
                "com.skn29.watercare.technician."
                "TechnicianMinimumFlowTest"
            ),
        )
        print("W5AUTO_TECHNICIAN_UI_DEVICE=PASS")

        instrument(
            adb,
            serial,
            technician_component,
            (
                "com.skn29.watercare.technician."
                "TechnicianRemoteAuthSmokeTest"
            ),
            remote=True,
        )
        print("W5AUTO_TECHNICIAN_REMOTE_DEVICE=PASS")

        blocked = [
            "CUSTOMER_FOLLOWUP_RUNTIME",
            "CUSTOMER_GUIDANCE_EVIDENCE_RUNTIME",
            "CUSTOMER_REQUEST_CONSULTATION_RUNTIME",
            "TECHNICIAN_ASSIGNED_VISIT_LIST_DETAIL_RUNTIME",
            "TECHNICIAN_VISIT_START_COMPLETE_RUNTIME",
            (
                "FULL_CUSTOMER_AI_CONSULTATION_VISIT_"
                "TECHNICIAN_E2E"
            ),
        ]

        report = write_report(
            work,
            {
                "integrated_head": integrated_head,
                "main": main_sha,
                "python_version": version,
                "device_model": device_model,
                "device_android": device_android,
                "customer_hash": customer_hash,
                "technician_hash": technician_hash,
                "blocked": blocked,
            },
        )

        print(f"W5AUTO_REPORT={report}")
        print(
            "W5AUTO_BLOCKED_AREAS="
            + ",".join(blocked)
        )
        print("W5AUTO_INDEPENDENT_WEEK5=PASS")
        print(
            "W5AUTO_FULL_P0_FEATURE_COMPLETE="
            "BLOCKED_BY_BACKEND"
        )
        print("W5AUTO_COMPLETE")

    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except Exception:
            server.kill()
        stdout_handle.close()
        stderr_handle.close()

    status = git(work, "status", "--porcelain")
    changed = []
    for line in status.splitlines():
        if not line.strip():
            continue
        path = line[3:].replace("\\", "/")
        changed.append(path)
        approved_mobile_test_files = {
            CUSTOMER_UI_TEST,
            TECHNICIAN_UI_TEST,
            "mobile/customer-app/src/debug/AndroidManifest.xml",
            "mobile/customer-app/src/debug/java/com/skn29/watercare/customer/testing/ComposeTestActivity.kt",
            TECHNICIAN_DEBUG_MANIFEST,
            TECHNICIAN_DEBUG_HOST,
        }
        if (
            not path.startswith("personal/mobile-extension/")
            and path not in approved_mobile_test_files
        ):
            raise RuntimeError(
                "uncommitted change outside approved test/extension scope: "
                + path
            )
    print("T088R5_EXTENSION_SCOPE_GUARD=PASS")

    run(
        [
            "git",
            "-C",
            work,
            "add",
            "--",
            "personal/mobile-extension",
            CUSTOMER_UI_TEST,
            TECHNICIAN_UI_TEST,
            "mobile/customer-app/src/debug/AndroidManifest.xml",
            "mobile/customer-app/src/debug/java/com/skn29/watercare/customer/testing/ComposeTestActivity.kt",
            TECHNICIAN_DEBUG_MANIFEST,
            TECHNICIAN_DEBUG_HOST,
        ]
    )

    staged = git(
        work,
        "diff",
        "--cached",
        "--name-only",
    ).splitlines()

    print("T088R5_STAGED_FILES_BEGIN")
    for path in staged:
        print(path)
        approved_mobile_test_files = {
            CUSTOMER_UI_TEST,
            TECHNICIAN_UI_TEST,
            "mobile/customer-app/src/debug/AndroidManifest.xml",
            "mobile/customer-app/src/debug/java/com/skn29/watercare/customer/testing/ComposeTestActivity.kt",
            TECHNICIAN_DEBUG_MANIFEST,
            TECHNICIAN_DEBUG_HOST,
        }
        if (
            not path.startswith("personal/mobile-extension/")
            and path not in approved_mobile_test_files
        ):
            raise RuntimeError(
                "staged outside approved test/extension scope: "
                + path
            )
    print("T088R5_STAGED_FILES_END")

    if len(staged) < 8:
        raise RuntimeError(
            "Expected extension evidence plus functional UI test/debug host changes; "
            f"staged={len(staged)}"
        )

    tested_tree = git(work, "write-tree")
    print(f"T088R5_TESTED_TREE={tested_tree}")

    run(
        [
            "git",
            "-C",
            source,
            "fetch",
            "origin",
            "main",
            "jeonghyun",
            "--quiet",
        ]
    )

    current_main = git(
        source,
        "rev-parse",
        "origin/main",
    )
    current_jeong = git(
        source,
        "rev-parse",
        "origin/jeonghyun",
    )

    if current_main != main_sha:
        raise RuntimeError(
            "origin/main moved during verification; "
            "commit/push aborted"
        )
    if current_jeong != jeong_sha:
        raise RuntimeError(
            "origin/jeonghyun moved during verification; "
            "commit/push aborted"
        )

    commit_message = (
        "2026-08-10 | 5주차 독자 수행 및 Compose v2 실단말 검증 완룡 >.<"
    )

    run(
        [
            "git",
            "-C",
            work,
            "commit",
            "--no-gpg-sign",
            "-m",
            commit_message,
        ]
    )

    commit = git(work, "rev-parse", "HEAD")
    commit_tree = git(
        work,
        "rev-parse",
        "HEAD^{tree}",
    )

    if commit_tree != tested_tree:
        raise RuntimeError(
            "tested tree != commit tree"
        )

    print(f"T088R5_COMMIT_CREATED={commit}")
    print(
        "T088R5_TESTED_TREE_EQUALS_COMMIT_TREE=True"
    )

    run(
        [
            "git",
            "-C",
            work,
            "push",
            "origin",
            "HEAD:refs/heads/jeonghyun",
        ]
    )

    run(
        [
            "git",
            "-C",
            source,
            "fetch",
            "origin",
            "jeonghyun",
            "--quiet",
        ]
    )

    remote = git(
        source,
        "rev-parse",
        "origin/jeonghyun",
    )
    if remote != commit:
        raise RuntimeError(
            "origin/jeonghyun mismatch after push"
        )

    print("T088R5_PUSH_PASS")
    print(
        f"T088R5_REMOTE_JEONGHYUN_HEAD={remote}"
    )
    print("T088R5_INDEPENDENT_WEEK5=PASS")
    print(
        "T088R5_FULL_P0_FEATURE_COMPLETE="
        "BLOCKED_BY_BACKEND"
    )
    print("T088R5_MOBILE_RUNTIME_SOURCE_EDIT=False")
    print("T088R5_MOBILE_TEST_DEBUG_EDIT=True")
    print("T088R5_FORCE_PUSH=False")
    print("T088R5_MAIN_TO_JEONGHYUN_MERGE=True")
    print("T088R5_COMPLETE")


if __name__ == "__main__":
    main()
