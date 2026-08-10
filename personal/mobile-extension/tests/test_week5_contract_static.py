#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


def fail(message: str) -> None:
    raise AssertionError(message)


def read(repo: Path, rel: str) -> str:
    path = repo / rel
    if not path.exists():
        fail(f"missing file: {rel}")
    return path.read_text(encoding="utf-8")


def require(text: str, token: str, label: str) -> None:
    if token not in text:
        fail(f"{label}: missing token: {token}")


def forbid(text: str, token: str, label: str) -> None:
    if token in text:
        fail(f"{label}: forbidden token present: {token}")


def tracked_files(repo: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-files"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()
    repo = Path(args.repo).resolve()

    passed: list[str] = []

    try:
        api = read(repo, "mobile/core/src/main/java/com/skn29/watercare/core/network/WaterCareApi.kt")
        for token in (
            "api/v1/auth/demo-login",
            "api/v1/auth/refresh",
            "api/v1/auth/logout",
            "api/v1/me",
            "api/v1/me/subscriptions",
            "api/v1/me/subscriptions/{subscriptionId}",
            "api/v1/inquiries",
            "api/v1/inquiries/{inquiryId}/submit",
            "api/v1/inquiries/{inquiryId}/cancel",
        ):
            require(api, token, "WaterCareApi")

        for unsupported in (
            "request-consultation",
            "technician/visits",
            "visits/{visitId}/start",
            "visits/{visitId}/complete",
            "guidance",
        ):
            forbid(api.lower(), unsupported.lower(), "WaterCareApi unsupported Runtime")
        passed.append("Mobile Retrofit Runtime boundary")

        error_mapper = read(
            repo,
            "mobile/core/src/main/java/com/skn29/watercare/core/network/ApiErrorMapper.kt",
        )
        for token in (
            "400, 422",
            "401 ->",
            "403 ->",
            "404 ->",
            "409 ->",
            "in 500..599",
        ):
            require(error_mapper, token, "ApiErrorMapper")
        passed.append("400/401/403/404/409/422/5xx mapping")

        network_factory = read(
            repo,
            "mobile/core/src/main/java/com/skn29/watercare/core/network/NetworkFactory.kt",
        )
        for token in (
            ".authenticator(TokenAuthenticator(tokenStore, refreshApi))",
            'redactHeader("Authorization")',
            'redactHeader("Cookie")',
        ):
            require(network_factory, token, "NetworkFactory")
        passed.append("Authenticator wiring and log redaction")

        interceptors = read(
            repo,
            "mobile/core/src/main/java/com/skn29/watercare/core/network/Interceptors.kt",
        )
        for token in (
            "class TokenAuthenticator",
            "synchronized(lock)",
            "refreshApi.refreshSync",
            "tokenStore.clearBlocking()",
            "responseCount(response) >= 2",
            'endsWith("/auth/refresh")',
        ):
            require(interceptors, token, "TokenAuthenticator")
        passed.append("Refresh synchronization and retry boundary")

        remote = read(
            repo,
            "mobile/core/src/main/java/com/skn29/watercare/core/repository/RemoteIntakeCustomerCareRepository.kt",
        )
        require(remote, 'code = "GUIDANCE_ROUTE_UNAVAILABLE"', "Remote Guidance")
        require(remote, "subscriptions.list()", "Remote Home")
        guidance_block = remote.split(
            "override suspend fun getGuidance", 1
        )[1].split(
            "override suspend fun submitIntake", 1
        )[0]
        forbid(
            guidance_block,
            "fallbackRepository.getGuidance",
            "Remote Guidance",
        )
        passed.append("REMOTE Guidance fail-closed")

        tech_repo = read(
            repo,
            "mobile/technician-app/src/main/java/com/skn29/watercare/technician/TechnicianVisitRepository.kt",
        )
        for token in (
            "VISIT_RUNTIME_UNAVAILABLE",
            "BlockedTechnicianVisitRepository",
            "FakeTechnicianVisitRepository",
        ):
            require(tech_repo, token, "Technician Visit repository")
        passed.append("Technician Remote/Fixture repository separation")

        tech_vm = read(
            repo,
            "mobile/technician-app/src/main/java/com/skn29/watercare/technician/TechnicianViewModel.kt",
        )
        for token in (
            "offlinePreview",
            "fixtureVisitRepository",
            "remoteVisitRepository",
        ):
            require(tech_vm, token, "Technician ViewModel")
        passed.append("Technician offline/remote mode separation")

        api_urls = read(repo, "backend/config/api_urls.py")
        for token in (
            "apps.accounts.api.urls",
            "apps.subscriptions.api.urls",
            "apps.inquiries.api.urls",
            "apps.consultations.api.urls",
            "apps.visits.api.urls",
        ):
            require(api_urls, token, "backend api_urls")
        passed.append("Latest Backend domains routed")

        consultations = read(repo, "backend/apps/consultations/api/urls.py")
        for token in (
            "start-consultation",
            "consultation-summary",
            "consultation-summary/confirm",
            "complete-consultation",
        ):
            require(consultations, token, "Consultation Runtime")
        passed.append("Consultant Consultation Runtime present")

        visit_urls = read(repo, "backend/apps/visits/api/urls.py")
        for token in (
            "visit-review",
            'inquiries/<uuid:inquiry_id>/visits',
            'visits/<uuid:visit_id>/schedule',
            'visits/<uuid:visit_id>/confirm',
        ):
            require(visit_urls, token, "Visit scheduling Runtime")
        for token in (
            "technician/visits",
            "/start",
            "/complete",
            "/results",
        ):
            forbid(visit_urls.lower(), token.lower(), "Technician execution Runtime")
        passed.append("Visit scheduling present / technician execution absent")

        workflow = read(repo, "contracts/api/paths/workflow.yaml")
        for operation in ("submitFollowUpAnswers", "requestConsultation"):
            index = workflow.find(f"operationId: {operation}")
            if index < 0:
                fail(f"workflow contract missing: {operation}")
            chunk = workflow[index:index + 1400]
            require(
                chunk,
                "x-runtime-status: NOT_IMPLEMENTED",
                f"{operation} Runtime",
            )
        passed.append("Customer Follow-up/request-consultation contract-only")

        visits_contract = read(repo, "contracts/api/paths/visits.yaml")
        for operation in ("startVisit", "completeVisit"):
            index = visits_contract.find(f"operationId: {operation}")
            if index < 0:
                fail(f"visit contract missing: {operation}")
            chunk = visits_contract[index:index + 1500]
            require(
                chunk,
                "x-runtime-status: NOT_IMPLEMENTED",
                f"{operation} Runtime",
            )
        passed.append("Technician start/complete contract-only")

        inquiry_urls = read(repo, "backend/apps/inquiries/api/urls.py")
        forbid(inquiry_urls.lower(), "guidance", "Customer Guidance Runtime")
        passed.append("Customer Guidance Runtime absent")

        tracked = tracked_files(repo)
        dangerous: list[str] = []
        for rel in tracked:
            lower = rel.lower()
            name = Path(rel).name.lower()
            if name in {".env", "local.properties"}:
                dangerous.append(rel)
            if lower.endswith((".jks", ".keystore", ".p12", ".pfx")):
                dangerous.append(rel)
        if dangerous:
            fail("tracked secret/high-risk files: " + ", ".join(dangerous))
        passed.append("Secret/keystore Git tracking guard")

        private_url = re.compile(
            r"https?://(?!(?:10\.0\.2\.2)(?::|/))"
            r"(?:10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|"
            r"172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)"
        )
        offenders: list[str] = []
        for rel in tracked:
            if not rel.startswith(("mobile/", "personal/mobile-extension/")):
                continue
            if Path(rel).suffix.lower() not in {
                ".kt", ".kts", ".java", ".xml", ".properties", ".py", ".ps1"
            }:
                continue
            try:
                text = (repo / rel).read_text(encoding="utf-8")
            except Exception:
                continue
            if private_url.search(text):
                offenders.append(rel)
        if offenders:
            fail("hard-coded private Backend URL: " + ", ".join(offenders))
        passed.append("Private developer Backend URL guard")

        customer_ui = read(
            repo,
            "mobile/customer-app/src/androidTest/java/com/skn29/watercare/customer/CustomerMinimumFlowTest.kt",
        )
        require(
            customer_ui,
            "runAndroidComposeUiTest<ComposeTestActivity>",
            "Customer functional Compose environment",
        )
        forbid(
            customer_ui,
            "createAndroidComposeRule",
            "Customer functional Compose environment",
        )
        forbid(
            customer_ui,
            "composeRule.",
            "Customer functional Compose environment",
        )
        passed.append("Customer functional Compose UI environment")

        technician_ui = read(
            repo,
            "mobile/technician-app/src/androidTest/java/com/skn29/watercare/technician/TechnicianMinimumFlowTest.kt",
        )
        require(
            technician_ui,
            "runAndroidComposeUiTest<ComposeTestActivity>",
            "Technician functional Compose environment",
        )
        forbid(
            technician_ui,
            "createAndroidComposeRule",
            "Technician functional Compose environment",
        )
        forbid(
            technician_ui,
            "composeRule.",
            "Technician functional Compose environment",
        )
        passed.append("Technician functional Compose UI environment")

        for manifest_rel, host_rel, package_name in (
            (
                "mobile/customer-app/src/debug/AndroidManifest.xml",
                "mobile/customer-app/src/debug/java/com/skn29/watercare/customer/testing/ComposeTestActivity.kt",
                "com.skn29.watercare.customer.testing",
            ),
            (
                "mobile/technician-app/src/debug/AndroidManifest.xml",
                "mobile/technician-app/src/debug/java/com/skn29/watercare/technician/testing/ComposeTestActivity.kt",
                "com.skn29.watercare.technician.testing",
            ),
        ):
            manifest = read(repo, manifest_rel)
            require(manifest, ".testing.ComposeTestActivity", manifest_rel)
            host = read(repo, host_rel)
            require(host, f"package {package_name}", host_rel)
            require(host, "class ComposeTestActivity : ComponentActivity()", host_rel)
        passed.append("Customer/Technician debug Compose hosts")

        customer_remote = read(
            repo,
            "mobile/customer-app/src/androidTest/java/com/skn29/watercare/customer/CustomerRemoteBackendSmokeTest.kt",
        )
        require(
            customer_remote,
            "login_subscriptionDetail_createAndSubmit_realBackend",
            "Customer remote instrumentation",
        )
        require(
            customer_remote,
            "guidanceWithoutCustomerRoute_remoteModeFailsClosed",
            "Customer remote instrumentation",
        )
        passed.append("Customer remote instrumentation coverage")

        tech_remote = read(
            repo,
            "mobile/technician-app/src/androidTest/java/com/skn29/watercare/technician/TechnicianRemoteAuthSmokeTest.kt",
        )
        require(
            tech_remote,
            "technicianLoginAndMe_useRealBackend",
            "Technician remote instrumentation",
        )
        passed.append("Technician remote auth instrumentation coverage")

    except Exception as exc:
        print("W5AUTO_STATIC_CONTRACT=FAIL")
        print(f"W5AUTO_STATIC_ERROR={exc}")
        return 1

    for item in passed:
        print(f"PASS: {item}")
    print(f"W5AUTO_STATIC_CHECK_COUNT={len(passed)}")
    print("W5AUTO_STATIC_CONTRACT=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
