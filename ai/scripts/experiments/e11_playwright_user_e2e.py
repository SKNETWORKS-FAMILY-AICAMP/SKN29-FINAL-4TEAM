"""E11 - Playwright Browser User E2E experiment runner.

This runner orchestrates the repository's existing Playwright E2E tests instead of
duplicating them.

Validated scope
---------------
- Real Chromium browser
- Real local WaterBridge Web application
- Real local Backend API
- Real local PostgreSQL
- Mock API / Mock Auth disabled by the repository Playwright config

Conceptual E11 cases
--------------------
E11-01 CONSULTATION_HAPPY_PATH
E11-02 STALE_STATE_CONFLICT
E11-03 ACCESS_BOUNDARY
E11-04 VISIT_TECHNICIAN_WORKFLOW

Important boundary
------------------
This is Consultant Web <-> Backend browser E2E.
It does NOT claim Mobile -> AI -> Backend -> Web full-service E2E.

Run from repository root:

    python ai/scripts/experiments/e11_playwright_user_e2e.py

The runner automatically prefers backend/.venv for Django management
commands and performs a PostgreSQL TCP preflight before Migration checks.

The runner requires the repository-native Playwright fixture parser to accept
the current Workflow Action contract. It validates that boundary before native
Playwright execution and never patches or rewrites repository source files.

If E2E_CONSULTANT_PASSWORD is not already set, the runner generates an
ephemeral policy-compliant password in memory, applies it to the synthetic
consultant with the repository's official management command, verifies one real
HTTP login, and never prints or persists the password.

Artifacts:

    ai/experiment_results/e11/
    ├─ summary.json
    ├─ report.md
    ├─ playwright.log
    └─ backend_server.log   # only when this runner starts Backend
"""

from __future__ import annotations

import getpass
import json
from contextlib import contextmanager
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[3]
WEB_ROOT = REPO_ROOT / "web"
BACKEND_ROOT = REPO_ROOT / "backend"
OUTPUT_DIR = (
    REPO_ROOT
    / "ai"
    / "experiment_results"
    / "e11"
)

PLAYWRIGHT_LOG = OUTPUT_DIR / "playwright.log"
BACKEND_LOG = OUTPUT_DIR / "backend_server.log"

BACKEND_BASE_URL = (
    os.environ.get("E2E_BACKEND_BASE_URL", "").strip()
    or "http://127.0.0.1:8000"
)

CONSULTATION_SPEC = "e2e/specs/consultation-workflow.spec.ts"
TECHNICIAN_SPEC = "e2e/specs/technician-selection.spec.ts"

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


@dataclass(slots=True)
class CaseResult:
    case_id: str
    scenario: str
    passed: bool
    source_spec: str
    evidence: dict[str, Any]
    notes: str


class ExperimentBlocked(RuntimeError):
    """Expected fail-closed precondition failure."""


def git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_loopback_url(raw_url: str) -> bool:
    try:
        host = (urlparse(raw_url).hostname or "").lower()
    except ValueError:
        return False
    return host in LOOPBACK_HOSTS


def read_env_value(path: Path, key: str) -> str | None:
    if not path.exists():
        return None

    prefix = f"{key}="
    for raw_line in path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith(prefix):
            continue

        value = line[len(prefix):].strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1].strip()
        return value

    return None


def backend_database_host() -> str:
    inherited = os.environ.get("POSTGRES_HOST", "").strip()
    if inherited:
        return inherited

    value = read_env_value(BACKEND_ROOT / ".env", "POSTGRES_HOST")
    if value:
        return value

    raise ExperimentBlocked(
        "Backend POSTGRES_HOST를 확인할 수 없습니다. "
        "backend/.env 또는 현재 환경변수를 확인해 주세요."
    )


def assert_local_boundary() -> None:
    if not is_loopback_url(BACKEND_BASE_URL):
        raise ExperimentBlocked(
            "E11은 로컬 Backend에서만 실행합니다. "
            f"현재 E2E_BACKEND_BASE_URL={BACKEND_BASE_URL!r}"
        )

    database_host = backend_database_host().lower()
    if database_host not in LOOPBACK_HOSTS:
        raise ExperimentBlocked(
            "E11은 로컬 PostgreSQL에서만 Fixture를 생성합니다. "
            f"현재 POSTGRES_HOST={database_host!r}"
        )


def backend_python_path() -> str:
    inherited = os.environ.get("E2E_BACKEND_PYTHON", "").strip()
    if inherited:
        candidate = Path(inherited)
        if candidate.exists():
            return str(candidate.resolve())

    if os.name == "nt":
        candidate = BACKEND_ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = BACKEND_ROOT / ".venv" / "bin" / "python"

    if candidate.exists():
        return str(candidate.resolve())

    return sys.executable


def postgres_connection_target() -> tuple[str, int]:
    host = os.environ.get("POSTGRES_HOST", "").strip()
    if not host:
        host = (
            read_env_value(BACKEND_ROOT / ".env", "POSTGRES_HOST")
            or "127.0.0.1"
        ).strip()

    raw_port = os.environ.get("POSTGRES_PORT", "").strip()
    if not raw_port:
        raw_port = (
            read_env_value(BACKEND_ROOT / ".env", "POSTGRES_PORT")
            or "5432"
        ).strip()

    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ExperimentBlocked(
            f"POSTGRES_PORT가 정수가 아닙니다: {raw_port!r}"
        ) from exc

    return host, port


def assert_postgres_tcp_reachable() -> dict[str, Any]:
    host, port = postgres_connection_target()

    try:
        with socket.create_connection((host, port), timeout=2.5):
            pass
    except OSError as exc:
        raise ExperimentBlocked(
            "로컬 PostgreSQL TCP 연결이 열려 있지 않습니다. "
            f"target={host}:{port}. "
            "PostgreSQL 서비스를 먼저 시작한 뒤 E11을 다시 실행해 주세요. "
            "이 상태에서는 Django Migration/Fixture/Playwright를 실행하지 않습니다."
        ) from exc

    return {
        "host": host,
        "port": port,
        "tcp_reachable": True,
    }


def backend_command(
    args: list[str],
    *,
    timeout: float = 60.0,
    require_stdout: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        backend_python_path(),
        "manage.py",
        *args,
        "--settings=config.settings.local",
    ]
    result = subprocess.run(
        command,
        cwd=BACKEND_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        env=os.environ.copy(),
    )

    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        raise ExperimentBlocked(
            "Backend 관리 명령이 실패했습니다.\n"
            f"command={' '.join(args)}\n"
            f"{message[-4000:]}"
        )

    if require_stdout and not result.stdout.strip():
        raise ExperimentBlocked(
            "Backend 관리 명령이 성공했지만 출력 JSON이 없습니다. "
            f"command={' '.join(args)}"
        )

    return result


def assert_migration_gate() -> dict[str, Any]:
    result = backend_command(
        ["showmigrations"],
        timeout=60.0,
        require_stdout=True,
    )

    states: dict[str, str] = {}
    current_app = ""

    for raw_line in result.stdout.splitlines():
        line = raw_line.rstrip()
        app_match = re.match(r"^([A-Za-z0-9_]+)\s*$", line)
        if app_match:
            current_app = app_match.group(1)
            continue

        migration_match = re.match(
            r"^\s*\[([ X])\]\s+([^\s]+)",
            line,
        )
        if not migration_match or not current_app:
            continue

        states[
            f"{current_app}.{migration_match.group(2)}"
        ] = (
            "APPLIED"
            if migration_match.group(1) == "X"
            else "PENDING"
        )

    required_applied = (
        "operations.0002_consultant_dashboard_projection"
    )
    expected_hold = (
        "visits.0005_replace_visit_result_assignment_fk"
    )

    unexpected_pending = sorted(
        key
        for key, state in states.items()
        if state == "PENDING" and key != expected_hold
    )

    checks = {
        "operations_0002_applied": (
            states.get(required_applied) == "APPLIED"
        ),
        "visits_0005_hold_preserved": (
            states.get(expected_hold) == "PENDING"
        ),
        "unexpected_pending_zero": (
            len(unexpected_pending) == 0
        ),
    }

    if not all(checks.values()):
        raise ExperimentBlocked(
            "Playwright Migration Gate가 맞지 않습니다. "
            "operations.0002 적용, visits.0005 단독 HOLD, "
            "예상 외 pending 0건이 필요합니다. "
            f"checks={checks}, "
            f"unexpected_pending={unexpected_pending}"
        )

    return {
        "checks": checks,
        "unexpected_pending": unexpected_pending,
    }


def run_demo_seeds() -> list[str]:
    commands = [
        "seed_demo_accounts",
        "seed_demo_products",
        "seed_demo_subscriptions",
    ]

    for command in commands:
        backend_command(
            [command],
            timeout=60.0,
        )

    return commands


def create_concealed_fixture(run_id: str) -> dict[str, Any]:
    result = backend_command(
        [
            "create_web_concealed_e2e_fixture",
            "--run-id",
            run_id,
            "--json",
        ],
        timeout=60.0,
        require_stdout=True,
    )

    try:
        payload = json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise ExperimentBlocked(
            "create_web_concealed_e2e_fixture가 "
            "공개 JSON만 반환하지 않았습니다."
        ) from exc

    required = {
        "inquiry_id",
        "assigned_consultant",
        "concealed_from",
        "expected_http_status",
        "expected_error_code",
        "fixture_readiness",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise ExperimentBlocked(
            "Concealed Fixture JSON 계약이 예상과 다릅니다. "
            f"missing={missing}"
        )

    if (
        payload["fixture_readiness"] != "READY"
        or payload["expected_http_status"] != 404
        or payload["expected_error_code"]
        != "RESOURCE_NOT_FOUND"
    ):
        raise ExperimentBlocked(
            "Concealed Fixture가 E11 Access Boundary "
            f"검증 준비 상태가 아닙니다: {payload}"
        )

    return payload


def backend_health_ok(timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(
            f"{BACKEND_BASE_URL.rstrip('/')}/health",
            timeout=timeout,
        ) as response:
            return response.status == 200
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
    ):
        return False


def wait_for_backend(
    process: subprocess.Popen[Any] | None,
    *,
    timeout: float = 45.0,
) -> None:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if backend_health_ok(timeout=1.0):
            return

        if process is not None and process.poll() is not None:
            tail = ""
            if BACKEND_LOG.exists():
                tail = "\n".join(
                    BACKEND_LOG.read_text(
                        encoding="utf-8",
                        errors="replace",
                    ).splitlines()[-80:]
                )
            raise ExperimentBlocked(
                "Runner가 시작한 Backend가 Health 준비 전에 "
                "종료되었습니다.\n"
                + tail
            )

        time.sleep(0.25)

    raise ExperimentBlocked(
        "Backend Health 준비 시간이 초과되었습니다. "
        f"url={BACKEND_BASE_URL}/health"
    )


def ensure_backend_running() -> tuple[
    subprocess.Popen[Any] | None,
    Any | None,
    bool,
]:
    if backend_health_ok():
        return None, None, False

    if not is_loopback_url(BACKEND_BASE_URL):
        raise ExperimentBlocked(
            "원격 Backend는 Runner가 시작하지 않습니다."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log_handle = BACKEND_LOG.open(
        "w",
        encoding="utf-8",
    )

    parsed_backend = urlparse(BACKEND_BASE_URL)
    backend_host = parsed_backend.hostname or "127.0.0.1"
    backend_port = parsed_backend.port or 8000
    if backend_host not in LOOPBACK_HOSTS:
        raise ExperimentBlocked(
            "Runner는 loopback Backend만 자동 시작합니다."
        )

    process = subprocess.Popen(
        [
            backend_python_path(),
            "manage.py",
            "runserver",
            f"{backend_host}:{backend_port}",
            "--settings=config.settings.local",
            "--noreload",
        ],
        cwd=BACKEND_ROOT,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=os.environ.copy(),
    )

    wait_for_backend(process)
    return process, log_handle, True


def stop_backend(
    process: subprocess.Popen[Any] | None,
    log_handle: Any | None,
) -> None:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    if log_handle is not None:
        log_handle.flush()
        log_handle.close()


def prepare_and_verify_consultant_login(
    env: dict[str, str],
) -> dict[str, Any]:
    """Prepare the synthetic consultant credential and verify real HTTP login.

    seed_demo_accounts deliberately creates DEMO-CONSULTANT-001 with an
    unusable password.  Therefore E2E_CONSULTANT_PASSWORD must be applied to
    that synthetic account before the browser attempts a password login.

    This function uses the repository's official
    set_synthetic_consultant_password management command and then performs one
    real POST /api/v1/auth/login request against the running isolated Backend.
    Tokens from the response are never logged or persisted.
    """

    password = env.get(
        "E2E_CONSULTANT_PASSWORD",
        "",
    )
    if not password:
        raise ExperimentBlocked(
            "E2E_CONSULTANT_PASSWORD가 준비되지 않았습니다."
        )

    command = [
        backend_python_path(),
        "manage.py",
        "set_synthetic_consultant_password",
        "--username",
        "DEMO-CONSULTANT-001",
        "--password-env",
        "E2E_CONSULTANT_PASSWORD",
        "--json",
        "--settings=config.settings.local",
    ]
    result = subprocess.run(
        command,
        cwd=BACKEND_ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=60.0,
    )

    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        raise ExperimentBlocked(
            "합성 상담사 비밀번호 준비 명령이 실패했습니다. "
            + message[-2000:]
        )

    try:
        command_payload = json.loads(
            result.stdout.strip()
        )
    except json.JSONDecodeError as exc:
        raise ExperimentBlocked(
            "합성 상담사 비밀번호 준비 명령이 "
            "공개 JSON을 반환하지 않았습니다."
        ) from exc

    command_ok = (
        command_payload.get("status") == "APPLIED"
        and command_payload.get("username")
        == "DEMO-CONSULTANT-001"
        and command_payload.get("role_code")
        == "CONSULTANT"
        and command_payload.get("password_source")
        == "ENVIRONMENT"
        and command_payload.get("secret_exposed") is False
    )
    if not command_ok:
        raise ExperimentBlocked(
            "합성 상담사 비밀번호 준비 계약이 예상과 다릅니다."
        )

    request_body = json.dumps(
        {
            "username": "DEMO-CONSULTANT-001",
            "password": password,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"{BACKEND_BASE_URL.rstrip('/')}/api/v1/auth/login",
        data=request_body,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=10.0,
        ) as response:
            http_status = response.status
            response_body = response.read()
    except urllib.error.HTTPError as exc:
        error_code = None
        try:
            payload = json.loads(
                exc.read().decode(
                    "utf-8",
                    errors="replace",
                )
            )
            error_code = (
                payload.get("error", {}).get("code")
                if isinstance(payload, dict)
                else None
            )
        except Exception:
            error_code = None
        raise ExperimentBlocked(
            "Playwright 실행 전 실제 Backend 로그인 "
            f"선검증이 실패했습니다: HTTP {exc.code}, "
            f"error_code={error_code or 'UNKNOWN'}"
        ) from None
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
    ) as exc:
        raise ExperimentBlocked(
            "Playwright 실행 전 Backend 로그인 API에 "
            "연결할 수 없습니다."
        ) from exc

    if http_status != 200:
        raise ExperimentBlocked(
            "Playwright 실행 전 Backend 로그인 선검증이 "
            f"HTTP {http_status}를 반환했습니다."
        )

    try:
        payload = json.loads(
            response_body.decode(
                "utf-8",
                errors="strict",
            )
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExperimentBlocked(
            "Backend 로그인 200 응답 JSON을 검증할 수 없습니다."
        ) from exc

    role_code = (
        payload.get("data", {})
        .get("user", {})
        .get("role_code")
        if isinstance(payload, dict)
        else None
    )
    if role_code != "CONSULTANT":
        raise ExperimentBlocked(
            "Backend 로그인은 성공했지만 사용자 Role이 "
            f"CONSULTANT가 아닙니다: {role_code!r}"
        )

    # Never retain tokens or response payload in experiment artifacts.
    response_body = b""
    payload = {}

    print(
        "[E11] 합성 상담사 Credential 준비: PASS "
        "(official management command)"
    )
    print(
        "[E11] Backend 실제 로그인 선검증: "
        "HTTP 200 / CONSULTANT / PASS"
    )

    return {
        "credential_command_status": (
            command_payload["status"]
        ),
        "credential_changed": bool(
            command_payload.get("changed")
        ),
        "password_source": (
            "EPHEMERAL_RUNTIME"
            if env.get(
                "E11_EPHEMERAL_PASSWORD_GENERATED"
            )
            == "true"
            else "EXTERNAL_ENVIRONMENT"
        ),
        "secret_exposed": False,
        "http_login_status": 200,
        "http_login_role_code": "CONSULTANT",
        "tokens_logged": False,
        "tokens_persisted": False,
    }


@contextmanager
def native_backend_fixture_contract_check():
    """Fail closed unless the repository parser matches the current contract."""

    path = WEB_ROOT / "e2e" / "support" / "backendFixture.ts"
    if not path.exists():
        raise ExperimentBlocked(
            f"Playwright Backend Fixture parser가 없습니다: {path}"
        )

    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ExperimentBlocked(
            "backendFixture.ts를 UTF-8로 읽을 수 없습니다."
        ) from exc

    checks = {
        "official_action_registry": "WORKFLOW_ACTION_CODES" in source,
        "start_action_required": (
            'actions.includes("START_CONSULTATION")' in source
        ),
        "valid_actions_preserved": (
            "allowed_actions: [...fixture.allowedActions]" in source
        ),
        "legacy_exact_length_absent": (
            "raw.allowed_actions.length !== 1" not in source
        ),
    }
    if not all(checks.values()):
        raise ExperimentBlocked(
            "Repository-native Playwright Fixture Parser가 현행 계약과 "
            f"다릅니다. checks={checks}"
        )

    info = {
        "applied": False,
        "reason": "REPOSITORY_NATIVE_CONTRACT",
        "runtime_patch": False,
        "product_code_modified": False,
        "backend_contract_modified": False,
        "checks": checks,
    }
    print(
        "[E11] Repository-native Fixture Parser 계약 검증: PASS "
        "(Runtime Patch 없음)"
    )
    yield info


def npm_executable() -> str:
    candidates = (
        ["npm.cmd", "npm"]
        if os.name == "nt"
        else ["npm"]
    )

    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    raise ExperimentBlocked(
        "npm 실행 파일을 찾을 수 없습니다."
    )


def stream_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_path: Path | None = None,
    timeout: float | None = None,
) -> tuple[int, str, float]:
    started = time.perf_counter()
    collected: list[str] = []

    log_handle = (
        log_path.open("w", encoding="utf-8")
        if log_path is not None
        else None
    )

    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        deadline = (
            time.monotonic() + timeout
            if timeout is not None
            else None
        )

        assert process.stdout is not None

        def console_safe(value: str) -> str:
            encoding = sys.stdout.encoding or "utf-8"
            return value.encode(
                encoding,
                errors="replace",
            ).decode(
                encoding,
                errors="replace",
            )

        while True:
            line = process.stdout.readline()
            if line:
                print(console_safe(line), end="")
                collected.append(line)
                if log_handle is not None:
                    log_handle.write(line)
                    log_handle.flush()

            if process.poll() is not None:
                remainder = process.stdout.read()
                if remainder:
                    print(console_safe(remainder), end="")
                    collected.append(remainder)
                    if log_handle is not None:
                        log_handle.write(remainder)
                break

            if deadline is not None and time.monotonic() > deadline:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                collected.append(
                    "\n[E11 RUNNER] command timeout\n"
                )
                return (
                    124,
                    "".join(collected),
                    time.perf_counter() - started,
                )

        return (
            int(process.returncode or 0),
            "".join(collected),
            time.perf_counter() - started,
        )

    finally:
        if log_handle is not None:
            log_handle.close()


def ensure_node_dependencies(
    npm: str,
    env: dict[str, str],
) -> dict[str, Any]:
    timings: dict[str, Any] = {}

    if not (WEB_ROOT / "node_modules").exists():
        print(
            "[E11] web/node_modules가 없어 npm ci를 실행합니다."
        )
        code, _, seconds = stream_command(
            [npm, "ci"],
            cwd=WEB_ROOT,
            env=env,
            timeout=300.0,
        )
        timings["npm_ci_seconds"] = round(seconds, 3)
        if code != 0:
            raise ExperimentBlocked(
                "npm ci가 실패했습니다."
            )
    else:
        timings["npm_ci_seconds"] = None

    print("[E11] Playwright E2E TypeScript를 검사합니다.")
    code, _, seconds = stream_command(
        [npm, "run", "typecheck:e2e"],
        cwd=WEB_ROOT,
        env=env,
        timeout=180.0,
    )
    timings["typecheck_e2e_seconds"] = round(
        seconds,
        3,
    )
    if code != 0:
        raise ExperimentBlocked(
            "npm run typecheck:e2e가 실패했습니다."
        )

    print("[E11] Chromium 실행 환경을 확인/설치합니다.")
    code, _, seconds = stream_command(
        [npm, "run", "test:e2e:install"],
        cwd=WEB_ROOT,
        env=env,
        timeout=300.0,
    )
    timings["playwright_install_seconds"] = round(
        seconds,
        3,
    )
    if code != 0:
        raise ExperimentBlocked(
            "Playwright Chromium 설치/확인이 실패했습니다."
        )

    return timings


def parse_playwright_summary(output: str) -> dict[str, Any]:
    plain = ANSI_ESCAPE.sub("", output)

    passed_counts = [
        int(match)
        for match in re.findall(
            r"(?m)\b(\d+)\s+passed\b",
            plain,
        )
    ]
    failed_counts = [
        int(match)
        for match in re.findall(
            r"(?m)\b(\d+)\s+failed\b",
            plain,
        )
    ]
    skipped_counts = [
        int(match)
        for match in re.findall(
            r"(?m)\b(\d+)\s+skipped\b",
            plain,
        )
    ]

    return {
        "passed_test_count": (
            passed_counts[-1] if passed_counts else 0
        ),
        "failed_test_count": (
            failed_counts[-1] if failed_counts else 0
        ),
        "skipped_test_count": (
            skipped_counts[-1] if skipped_counts else 0
        ),
        "consultation_spec_mentioned": (
            "consultation-workflow.spec.ts" in plain
        ),
        "technician_spec_mentioned": (
            "technician-selection.spec.ts" in plain
        ),
    }


def artifact_inventory_since(
    started_epoch: float,
) -> dict[str, Any]:
    root = WEB_ROOT / ".runtime" / "playwright"
    if not root.exists():
        return {
            "runtime_dir_present": False,
            "recent_file_count": 0,
            "extensions": {},
        }

    recent: list[Path] = []
    for path in root.rglob("*"):
        try:
            if (
                path.is_file()
                and path.stat().st_mtime
                >= started_epoch - 2
            ):
                recent.append(path)
        except OSError:
            continue

    extensions: dict[str, int] = {}
    for path in recent:
        suffix = path.suffix.lower() or "<none>"
        extensions[suffix] = (
            extensions.get(suffix, 0) + 1
        )

    return {
        "runtime_dir_present": True,
        "recent_file_count": len(recent),
        "extensions": dict(
            sorted(extensions.items())
        ),
        # Never copy Browser traces/screenshots here. The repository's
        # privacy support owns those artifacts.
        "artifact_root": (
            "web/.runtime/playwright"
        ),
    }


def build_cases(
    *,
    playwright_passed: bool,
    playwright_summary: dict[str, Any],
) -> list[CaseResult]:
    consultation_ok = (
        playwright_passed
        and playwright_summary["passed_test_count"] >= 2
        and playwright_summary[
            "consultation_spec_mentioned"
        ]
    )
    technician_ok = (
        playwright_passed
        and playwright_summary["passed_test_count"] >= 2
        and playwright_summary[
            "technician_spec_mentioned"
        ]
    )

    consultation_evidence = {
        "playwright_process_passed": playwright_passed,
        "source_test_passed": consultation_ok,
        "passed_test_count": playwright_summary[
            "passed_test_count"
        ],
        "failed_test_count": playwright_summary[
            "failed_test_count"
        ],
        "skipped_test_count": playwright_summary[
            "skipped_test_count"
        ],
    }

    technician_evidence = {
        "playwright_process_passed": playwright_passed,
        "source_test_passed": technician_ok,
        "passed_test_count": playwright_summary[
            "passed_test_count"
        ],
        "failed_test_count": playwright_summary[
            "failed_test_count"
        ],
        "skipped_test_count": playwright_summary[
            "skipped_test_count"
        ],
    }

    return [
        CaseResult(
            case_id="E11-01",
            scenario="CONSULTATION_HAPPY_PATH",
            passed=consultation_ok,
            source_spec=CONSULTATION_SPEC,
            evidence={
                **consultation_evidence,
                "validated_flow": [
                    "consultant_login",
                    "inquiry_detail",
                    "start_consultation",
                    "save_consultation_summary",
                    "confirm_summary",
                    "complete_consultation",
                    "completion_pending",
                    "browser_reload",
                    "persisted_detail_reloaded",
                ],
            },
            notes=(
                "Existing repository Playwright assertions validate "
                "the full consultant happy path and reload persistence."
            ),
        ),
        CaseResult(
            case_id="E11-02",
            scenario="STALE_STATE_CONFLICT",
            passed=consultation_ok,
            source_spec=CONSULTATION_SPEC,
            evidence={
                **consultation_evidence,
                "expected_http_status": 409,
                "expected_error_code": "STATE-CONFLICT-01",
                "draft_preservation_checked": True,
                "server_state_refresh_checked": True,
            },
            notes=(
                "The same consultation Playwright test deliberately "
                "advances state_version in a concurrent request, verifies "
                "409 fail-closed behavior, refreshes server state, and "
                "checks that the counselor's draft fields remain populated."
            ),
        ),
        CaseResult(
            case_id="E11-03",
            scenario="ACCESS_BOUNDARY",
            passed=consultation_ok,
            source_spec=CONSULTATION_SPEC,
            evidence={
                **consultation_evidence,
                "concealed_fixture_used": True,
                "unassigned_list_hidden_checked": True,
                "direct_detail_expected_status": 404,
                "direct_start_expected_status": 404,
                "expected_error_code": "RESOURCE_NOT_FOUND",
                "missing_inquiry_404_checked": True,
            },
            notes=(
                "A dedicated synthetic inquiry assigned to another "
                "consultant is generated with the backend's official "
                "create_web_concealed_e2e_fixture command."
            ),
        ),
        CaseResult(
            case_id="E11-04",
            scenario="VISIT_TECHNICIAN_WORKFLOW",
            passed=technician_ok,
            source_spec=TECHNICIAN_SPEC,
            evidence={
                **technician_evidence,
                "validated_flow": [
                    "consultation_start",
                    "visit_required",
                    "visit_review",
                    "visit_create",
                    "technician_select",
                    "preferred_date_save",
                    "detail_reload",
                    "technician_and_schedule_persisted",
                ],
            },
            notes=(
                "Existing technician-selection Playwright assertions "
                "validate the consultant-to-visit workflow with a real "
                "Backend and local PostgreSQL."
            ),
        ),
    ]


def write_artifacts(
    *,
    git_ref: str | None,
    cases: list[CaseResult],
    migration_gate: dict[str, Any],
    seed_commands: list[str],
    concealed_fixture: dict[str, Any],
    backend_started_by_runner: bool,
    node_timings: dict[str, Any],
    login_preflight: dict[str, Any],
    harness_patch: dict[str, Any],
    playwright_exit_code: int,
    playwright_seconds: float,
    playwright_summary: dict[str, Any],
    browser_artifacts: dict[str, Any],
    experiment_seconds: float,
) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pass_count = sum(case.passed for case in cases)
    status = (
        "E11_COMPLETE"
        if pass_count == 4
        else "E11_FAILED"
    )

    summary = {
        "experiment_id": "E11",
        "experiment_name": "Playwright Browser User E2E",
        "status": status,
        "git_sha": git_ref,
        "executed_at_utc": now_utc(),
        "scope": "CONSULTANT_WEB_BACKEND_LOCAL_POSTGRES_BROWSER_E2E",
        "browser": "chromium",
        "mock_api": False,
        "mock_auth": False,
        "backend_base_url": BACKEND_BASE_URL,
        "backend_python": backend_python_path(),
        "backend_started_by_runner": backend_started_by_runner,
        "postgres_target": {
            "host": postgres_connection_target()[0],
            "port": postgres_connection_target()[1],
            "tcp_reachable": True,
        },
        "database_boundary": "LOCAL_POSTGRESQL_ONLY",
        "migration_gate": migration_gate,
        "demo_seed_commands_run": seed_commands,
        "concealed_fixture": {
            "fixture_scope": concealed_fixture.get(
                "fixture_scope"
            ),
            "fixture_readiness": concealed_fixture.get(
                "fixture_readiness"
            ),
            "assigned_consultant": concealed_fixture.get(
                "assigned_consultant"
            ),
            "concealed_from": concealed_fixture.get(
                "concealed_from"
            ),
            "expected_http_status": concealed_fixture.get(
                "expected_http_status"
            ),
            "expected_error_code": concealed_fixture.get(
                "expected_error_code"
            ),
            # Keep the synthetic ID for reproducibility.
            "inquiry_id": concealed_fixture.get(
                "inquiry_id"
            ),
        },
        "playwright": {
            "exit_code": playwright_exit_code,
            "seconds": round(
                playwright_seconds,
                3,
            ),
            **playwright_summary,
        },
        "node_preflight": node_timings,
        "consultant_login_preflight": login_preflight,
        "repository_fixture_contract": harness_patch,
        "browser_artifacts": browser_artifacts,
        "case_count": len(cases),
        "pass_count": pass_count,
        "all_passed": pass_count == 4,
        "cases": [asdict(case) for case in cases],
        "experiment_total_seconds": round(
            experiment_seconds,
            3,
        ),
        "claim": (
            "Playwright Chromium에서 Mock API/Auth를 사용하지 않고 "
            "실제 로컬 Web·Backend·PostgreSQL을 연결하여 상담사 "
            "핵심 업무를 검증했다. 상담 처리와 새로고침 후 영속성, "
            "stale state_version의 409 fail-closed, 비배정 문의의 "
            "404 concealment, 방문 생성 후 기사 선택·일정 저장을 "
            "실제 Browser Workflow에서 확인했다."
        ),
        "claim_boundary": (
            "본 E11은 Consultant Web <-> Backend의 Browser E2E다. "
            "Mobile -> AI -> Backend -> Web 전체 서비스 E2E나 "
            "실제 고객/RDS 환경 실행을 증명하지 않는다."
        ),
    }

    (OUTPUT_DIR / "summary.json").write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [
        "# E11 — Playwright Browser User E2E",
        "",
        f"- Git SHA: `{git_ref or 'UNKNOWN'}`",
        f"- Result: **{pass_count}/4 PASS**",
        "- Browser: `Chromium`",
        "- Mock API: `false`",
        "- Mock Auth: `false`",
        "- Backend: real local Backend",
        "- Database: local PostgreSQL only",
        f"- Playwright exit code: `{playwright_exit_code}`",
        f"- Playwright test result: "
        f"`{playwright_summary['passed_test_count']} passed / "
        f"{playwright_summary['failed_test_count']} failed / "
        f"{playwright_summary['skipped_test_count']} skipped`",
        "",
        "## 실험 질문",
        "",
        "> 상담사가 실제 브라우저 UI에서 문의 확인부터 상담 완료, "
        "동시성 충돌 처리, 접근 경계, 방문기사 선택까지 주요 업무를 "
        "실제 Backend와 연결해 수행할 수 있는가?",
        "",
        "## 결과 요약",
        "",
        "| Case | Scenario | Source | Result |",
        "|---|---|---|---:|",
    ]

    for case in cases:
        lines.append(
            f"| {case.case_id} | {case.scenario} | "
            f"`{case.source_spec}` | "
            f"{'PASS' if case.passed else 'FAIL'} |"
        )

    lines += [
        "",
        "## Consultant Login Preflight",
        "",
        "Demo Seed는 합성 상담사 계정을 unusable password 상태로 생성한다. "
        "E11 Runner는 Browser 실행 전에 저장소 공식 "
        "`set_synthetic_consultant_password` 명령으로 Runtime 전용 비밀번호를 "
        "적용하고, 실제 `/api/v1/auth/login` HTTP 200과 "
        "`role_code=CONSULTANT`를 확인한다. Token/비밀번호는 Artifact에 "
        "기록하지 않는다.",
        "",
        f"- Credential command: "
        f"`{login_preflight.get('credential_command_status')}`",
        f"- Password source: "
        f"`{login_preflight.get('password_source')}`",
        f"- Real login HTTP: "
        f"`{login_preflight.get('http_login_status')}`",
        f"- Login role: "
        f"`{login_preflight.get('http_login_role_code')}`",
        f"- Secret exposed: "
        f"`{login_preflight.get('secret_exposed')}`",
        "",
        "## Native Fixture Contract",
        "",
        "Repository의 `web/e2e/support/backendFixture.ts`가 공식 Workflow "
        "Action Registry에서 유효 Action을 검증하고, "
        "`START_CONSULTATION` 포함을 강제하며, Backend가 반환한 유효 배열을 "
        "보존하는지 실행 전에 확인한다. Runner는 Source를 수정하지 않는다.",
        "",
        f"- Runtime parser patch: "
        f"`{harness_patch.get('runtime_patch')}`",
        f"- Product code modified: "
        f"`{harness_patch.get('product_code_modified', False)}`",
        f"- Native contract checks: "
        f"`{harness_patch.get('checks')}`",
        "",
        "## Browser Workflow",
        "",
        "```text",
        "Chromium",
        "  ↓",
        "WaterBridge Web (Vite)",
        "  ↓",
        "Real Local Backend",
        "  ↓",
        "Local PostgreSQL",
        "```",
        "",
        "Playwright 설정의 Mock API/Auth는 비활성 상태이며, "
        "Backend Fixture는 로컬 DB에만 생성된다.",
        "",
        "## E11-01 — Consultation Happy Path",
        "",
        "```text",
        "Login",
        "  ↓",
        "Inquiry Detail",
        "  ↓",
        "Start Consultation",
        "  ↓",
        "Save Consultation",
        "  ↓",
        "Confirm Summary",
        "  ↓",
        "Complete Consultation",
        "  ↓",
        "COMPLETION_PENDING",
        "  ↓",
        "Browser Reload",
        "  ↓",
        "Persisted Data Re-loaded",
        "```",
        "",
        "## E11-02 — Stale State Conflict",
        "",
        "```text",
        "Browser state_version = N",
        "          ↓",
        "Concurrent request saves first",
        "          ↓",
        "Server state_version = N+1",
        "          ↓",
        "Browser submits stale state",
        "          ↓",
        "409 STATE-CONFLICT-01",
        "          ↓",
        "Latest server state refresh",
        "          ↓",
        "Counselor draft fields preserved",
        "```",
        "",
        "## E11-03 — Access Boundary",
        "",
        "Runner가 Backend 공식 "
        "`create_web_concealed_e2e_fixture` 명령으로 다른 상담사에게 "
        "배정된 합성 문의를 생성한 뒤, 실제 로그인 Browser Session에서 "
        "목록 미노출과 직접 Detail/Start 접근의 "
        "`404 RESOURCE_NOT_FOUND`를 검증한다.",
        "",
        "## E11-04 — Visit Technician Workflow",
        "",
        "```text",
        "Consultation",
        "  ↓",
        "Visit Required",
        "  ↓",
        "Visit Review",
        "  ↓",
        "Visit Create",
        "  ↓",
        "Technician Select",
        "  ↓",
        "Preferred Date Save",
        "  ↓",
        "Detail Re-open",
        "  ↓",
        "Technician / Schedule persisted",
        "```",
        "",
        "## Artifact Privacy",
        "",
        "Screenshot·Video·Trace의 Privacy 처리는 기존 "
        "`web/e2e/support/privacy.ts`와 Playwright 설정에 맡긴다. "
        "E11 Runner는 해당 원본 Artifact를 별도로 복제하지 않으며 "
        "실행 결과와 비민감 요약만 AI 실험 결과 폴더에 저장한다.",
        "",
        f"- Browser runtime artifact root: "
        f"`{browser_artifacts.get('artifact_root', 'N/A')}`",
        f"- Recent artifact files: "
        f"`{browser_artifacts.get('recent_file_count', 0)}`",
        "",
        "## 핵심 해석",
        "",
        summary["claim"],
        "",
        "## 주장 범위",
        "",
        summary["claim_boundary"],
        "",
        "따라서 발표에서는 **'실제 Chromium Browser에서 상담사 Web과 "
        "Backend 업무 Workflow를 E2E로 검증했다'**고 표현하고, "
        "**'고객 입력부터 AI 추론까지 전체 서비스 E2E'**라고 확대하지 않는다.",
        "",
        "## 재현 Artifact",
        "",
        "```text",
        "ai/scripts/experiments/e11_playwright_user_e2e.py",
        "",
        "ai/experiment_results/e11/",
        "├─ summary.json",
        "├─ report.md",
        "├─ playwright.log",
        "└─ backend_server.log  # Runner가 Backend를 시작한 경우",
        "```",
        "",
    ]

    (OUTPUT_DIR / "report.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    return summary


def main() -> int:
    experiment_started_monotonic = time.perf_counter()
    experiment_started_epoch = time.time()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    backend_process = None
    backend_log_handle = None
    backend_started = False

    print("=== E11: Playwright Browser User E2E ===")
    print(f"git_sha={git_sha() or 'UNKNOWN'}")
    print(
        "scope=Consultant Web <-> Backend <-> "
        "Local PostgreSQL"
    )
    print()

    try:
        print("[E11] 로컬 실행 경계를 확인합니다.")
        assert_local_boundary()

        print(
            f"[E11] Backend Python: {backend_python_path()}"
        )

        print("[E11] PostgreSQL TCP 연결을 확인합니다.")
        postgres_target = assert_postgres_tcp_reachable()
        print(
            "[E11] PostgreSQL: "
            f"{postgres_target['host']}:{postgres_target['port']} reachable"
        )

        print("[E11] Migration Gate를 확인합니다.")
        migration_gate = assert_migration_gate()

        print("[E11] Demo Seed를 로컬 DB에 준비합니다.")
        seed_commands = run_demo_seeds()

        print("[E11] 비배정 404 검증용 Concealed Fixture를 생성합니다.")
        concealed_run_id = (
            "e11-concealed-"
            + uuid4().hex[:16]
        )
        concealed_fixture = create_concealed_fixture(
            concealed_run_id
        )

        print(
            "[E11] Concealed Fixture 준비 완료: "
            f"{concealed_fixture['fixture_scope']} / READY"
        )

        print("[E11] Backend Health를 준비합니다.")
        (
            backend_process,
            backend_log_handle,
            backend_started,
        ) = ensure_backend_running()

        print(
            "[E11] Backend: "
            + (
                "Runner가 로컬 서버 시작"
                if backend_started
                else "기존 로컬 서버 재사용"
            )
        )

        child_env = os.environ.copy()
        child_env["E2E_BACKEND_PYTHON"] = (
            backend_python_path()
        )
        child_env["E2E_BACKEND_BASE_URL"] = (
            BACKEND_BASE_URL
        )
        child_env["E2E_CONCEALED_RUN_ID"] = concealed_run_id

        # One Playwright invocation creates one primary consultation fixture
        # and one separate visit fixture through globalSetup.
        nonce = uuid4().hex[:12]
        child_env["E2E_RUN_ID"] = (
            f"e11-consult-{nonce}"
        )
        child_env["E2E_VISIT_RUN_ID"] = (
            f"e11-visit-{nonce}"
        )

        password = child_env.get(
            "E2E_CONSULTANT_PASSWORD",
            "",
        )
        if not password:
            # Repository policy requires 12-64 ASCII alphanumeric chars with
            # at least one letter and digit.  Prefix E11 guarantees both.
            password = "E11" + secrets.token_hex(16)
            child_env[
                "E11_EPHEMERAL_PASSWORD_GENERATED"
            ] = "true"
            print(
                "[E11] 합성 상담사 비밀번호: "
                "Runtime에서 임시 생성 (화면/파일 미출력)"
            )

        child_env["E2E_CONSULTANT_PASSWORD"] = password

        login_preflight = prepare_and_verify_consultant_login(
            child_env
        )

        npm = npm_executable()

        with native_backend_fixture_contract_check() as harness_patch:
            node_timings = ensure_node_dependencies(
                npm,
                child_env,
            )

            print()
            print(
                "[E11] Chromium에서 상담 + 방문 Workflow를 "
                "한 번에 실행합니다."
            )
            print(
                f"  - {CONSULTATION_SPEC}"
            )
            print(
                f"  - {TECHNICIAN_SPEC}"
            )
            print()

            playwright_command = [
                npm,
                "run",
                "test:e2e",
                "--",
                CONSULTATION_SPEC,
                TECHNICIAN_SPEC,
                "--project=chromium",
            ]

            (
                playwright_exit_code,
                playwright_output,
                playwright_seconds,
            ) = stream_command(
                playwright_command,
                cwd=WEB_ROOT,
                env=child_env,
                log_path=PLAYWRIGHT_LOG,
                timeout=300.0,
            )

        # Remove the password from this mutable child env as soon as the
        # browser process is gone.
        child_env.pop(
            "E2E_CONSULTANT_PASSWORD",
            None,
        )
        child_env.pop(
            "E11_EPHEMERAL_PASSWORD_GENERATED",
            None,
        )
        password = ""

        playwright_summary = parse_playwright_summary(
            playwright_output
        )

        playwright_passed = (
            playwright_exit_code == 0
            and playwright_summary[
                "passed_test_count"
            ] >= 2
            and playwright_summary[
                "failed_test_count"
            ] == 0
            and playwright_summary[
                "skipped_test_count"
            ] == 0
        )

        cases = build_cases(
            playwright_passed=playwright_passed,
            playwright_summary=playwright_summary,
        )

        browser_artifacts = artifact_inventory_since(
            experiment_started_epoch
        )

        summary = write_artifacts(
            git_ref=git_sha(),
            cases=cases,
            migration_gate=migration_gate,
            seed_commands=seed_commands,
            concealed_fixture=concealed_fixture,
            backend_started_by_runner=backend_started,
            node_timings=node_timings,
            login_preflight=login_preflight,
            harness_patch=harness_patch,
            playwright_exit_code=playwright_exit_code,
            playwright_seconds=playwright_seconds,
            playwright_summary=playwright_summary,
            browser_artifacts=browser_artifacts,
            experiment_seconds=(
                time.perf_counter()
                - experiment_started_monotonic
            ),
        )

        print()
        print("=" * 88)
        print("[E11] FINAL")
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "git_sha": summary["git_sha"],
                    "cases_passed": (
                        f"{summary['pass_count']}/"
                        f"{summary['case_count']}"
                    ),
                    "browser": summary["browser"],
                    "mock_api": summary["mock_api"],
                    "mock_auth": summary["mock_auth"],
                    "playwright_tests": (
                        f"{summary['playwright']['passed_test_count']} "
                        "passed / "
                        f"{summary['playwright']['failed_test_count']} "
                        "failed / "
                        f"{summary['playwright']['skipped_test_count']} "
                        "skipped"
                    ),
                    "output_dir": (
                        "ai/experiment_results/"
                        "e11"
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        return (
            0
            if summary["status"] == "E11_COMPLETE"
            else 1
        )

    except ExperimentBlocked as exc:
        blocked = {
            "experiment_id": "E11",
            "experiment_name": (
                "Playwright Browser User E2E"
            ),
            "status": "E11_ENVIRONMENT_BLOCKED",
            "git_sha": git_sha(),
            "executed_at_utc": now_utc(),
            "reason": str(exc),
            "claim_boundary": (
                "환경 사전조건이 충족되지 않아 Browser "
                "E2E 결과로 간주하지 않는다."
            ),
        }
        (OUTPUT_DIR / "summary.json").write_text(
            json.dumps(
                blocked,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print()
        print("=" * 88)
        print("[E11] ENVIRONMENT_BLOCKED")
        print(str(exc))
        return 2

    finally:
        stop_backend(
            backend_process,
            backend_log_handle,
        )


if __name__ == "__main__":
    raise SystemExit(main())
