"""OpenAPI operation과 실제 Django Runtime route의 지원 상태를 검증한다."""

from pathlib import Path
from typing import Any

import yaml
from django.urls import resolve


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
OPENAPI_PATH = REPOSITORY_ROOT / "contracts" / "api" / "openapi.yaml"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
INQUIRY_ID = "00000000-0000-4000-8000-000000000001"
VISIT_ID = "00000000-0000-4000-8000-000000000002"
SUBSCRIPTION_ID = "00000000-0000-4000-8000-000000000003"
CARE_RECORD_ID = "00000000-0000-4000-8000-000000000004"
QUESTIONNAIRE_SESSION_ID = "00000000-0000-4000-8000-000000000005"

EXPECTED_OPERATIONS = {
    ("/health", "get"): {
        "operation_id": "getProvisionalHealth",
        "contract_status": "IN_PROGRESS",
        "runtime_path": "/health",
        "url_name": "health",
        "view_name": "health",
    },
    ("/auth/demo-login", "post"): {
        "operation_id": "demoLogin",
        "contract_status": "CONFIRMED",
        "runtime_path": "/api/v1/auth/demo-login",
        "url_name": "demo-login",
        "view_name": "DemoLoginView",
    },
    ("/auth/refresh", "post"): {
        "operation_id": "refreshAuthToken",
        "contract_status": "CONFIRMED",
        "runtime_path": "/api/v1/auth/refresh",
        "url_name": "token-refresh",
        "view_name": "TokenRefreshView",
    },
    ("/auth/logout", "post"): {
        "operation_id": "logout",
        "contract_status": "CONFIRMED",
        "runtime_path": "/api/v1/auth/logout",
        "url_name": "logout",
        "view_name": "LogoutView",
    },
    ("/me", "get"): {
        "operation_id": "getCurrentUser",
        "contract_status": "CONFIRMED",
        "runtime_path": "/api/v1/me",
        "url_name": "me",
        "view_name": "MeView",
    },
    ("/me/subscriptions", "get"): {
        "operation_id": "listMySubscriptions",
        "contract_status": "CONFIRMED",
        "runtime_path": "/api/v1/me/subscriptions",
        "url_name": "my-subscription-list",
        "view_name": "MySubscriptionListView",
    },
    ("/me/subscriptions", "post"): {
        "operation_id": "createMySubscription",
        "contract_status": "CONFIRMED",
        "runtime_path": "/api/v1/me/subscriptions",
        "url_name": "my-subscription-list",
        "view_name": "MySubscriptionListView",
    },
    ("/me/subscriptions/{subscription_id}", "get"): {
        "operation_id": "getMySubscription",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/me/subscriptions/{SUBSCRIPTION_ID}"
        ),
        "url_name": "my-subscription-detail",
        "view_name": "MySubscriptionDetailView",
    },
    ("/me/subscriptions/{subscription_id}", "patch"): {
        "operation_id": "updateMySubscription",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/me/subscriptions/{SUBSCRIPTION_ID}"
        ),
        "url_name": "my-subscription-detail",
        "view_name": "MySubscriptionDetailView",
    },
    ("/me/subscriptions/{subscription_id}/care-records", "get"): {
        "operation_id": "listMyCareRecords",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/me/subscriptions/{SUBSCRIPTION_ID}/care-records"
        ),
        "url_name": "my-care-record-list-create",
        "view_name": "MyCareRecordListCreateView",
    },
    ("/me/subscriptions/{subscription_id}/care-records", "post"): {
        "operation_id": "createMyCareRecord",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/me/subscriptions/{SUBSCRIPTION_ID}/care-records"
        ),
        "url_name": "my-care-record-list-create",
        "view_name": "MyCareRecordListCreateView",
    },
    (
        "/me/subscriptions/{subscription_id}/care-records/"
        "{care_record_id}",
        "get",
    ): {
        "operation_id": "getMyCareRecord",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/me/subscriptions/{SUBSCRIPTION_ID}/care-records/"
            f"{CARE_RECORD_ID}"
        ),
        "url_name": "my-care-record-detail",
        "view_name": "MyCareRecordDetailView",
    },
    ("/me/inquiries/active", "get"): {
        "operation_id": "getMyActiveInquiry",
        "contract_status": "CONFIRMED",
        "runtime_path": "/api/v1/me/inquiries/active",
        "url_name": "customer-active-inquiry",
        "view_name": "CustomerActiveInquiryView",
    },
    ("/me/inquiries/{inquiry_id}", "get"): {
        "operation_id": "getMyInquiry",
        "contract_status": "CONFIRMED",
        "runtime_path": f"/api/v1/me/inquiries/{INQUIRY_ID}",
        "url_name": "customer-inquiry-snapshot",
        "view_name": "CustomerInquirySnapshotView",
    },
    ("/me/inquiries/{inquiry_id}/questions", "get"): {
        "operation_id": "listMyInquiryQuestions",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/me/inquiries/{INQUIRY_ID}/questions"
        ),
        "url_name": "customer-inquiry-questions",
        "view_name": "CustomerInquiryQuestionsView",
    },
    ("/me/inquiries/{inquiry_id}/guidance", "get"): {
        "operation_id": "getMyInquiryGuidance",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/me/inquiries/{INQUIRY_ID}/guidance"
        ),
        "url_name": "customer-inquiry-guidance",
        "view_name": "CustomerInquiryGuidanceView",
    },
    ("/me/questionnaire-sessions", "post"): {
        "operation_id": "startCarePrecheck",
        "contract_status": "CONFIRMED",
        "runtime_path": "/api/v1/me/questionnaire-sessions",
        "url_name": "care-precheck-start",
        "view_name": "CarePrecheckCollectionView",
    },
    ("/me/questionnaire-sessions/{questionnaire_session_id}", "get"): {
        "operation_id": "getCarePrecheck",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            "/api/v1/me/questionnaire-sessions/"
            f"{QUESTIONNAIRE_SESSION_ID}"
        ),
        "url_name": "care-precheck-detail",
        "view_name": "CarePrecheckDetailView",
    },
    ("/me/questionnaire-sessions/{questionnaire_session_id}", "patch"): {
        "operation_id": "saveCarePrecheck",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            "/api/v1/me/questionnaire-sessions/"
            f"{QUESTIONNAIRE_SESSION_ID}"
        ),
        "url_name": "care-precheck-detail",
        "view_name": "CarePrecheckDetailView",
    },
    (
        "/me/questionnaire-sessions/{questionnaire_session_id}/submit",
        "post",
    ): {
        "operation_id": "submitCarePrecheck",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            "/api/v1/me/questionnaire-sessions/"
            f"{QUESTIONNAIRE_SESSION_ID}/submit"
        ),
        "url_name": "care-precheck-submit",
        "view_name": "CarePrecheckSubmitView",
    },
    ("/consultant/customer-subscriptions/search", "post"): {
        "operation_id": "searchConsultantCustomerSubscriptions",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            "/api/v1/consultant/customer-subscriptions/search"
        ),
        "url_name": "consultant-customer-subscription-search",
        "view_name": "ConsultantCustomerSubscriptionSearchView",
    },
    ("/consultant/phone-inquiries", "post"): {
        "operation_id": "registerConsultantPhoneInquiry",
        "contract_status": "CONFIRMED",
        "runtime_path": "/api/v1/consultant/phone-inquiries",
        "url_name": "consultant-phone-inquiry-register",
        "view_name": "RegisterConsultantPhoneInquiryView",
    },
    ("/consultant/dashboard", "get"): {
        "operation_id": "getConsultantDashboard",
        "contract_status": "CONFIRMED",
        "runtime_path": "/api/v1/consultant/dashboard",
        "url_name": "consultant-dashboard",
        "view_name": "ConsultantDashboardView",
    },
    ("/inquiries/unassigned-consultations", "get"): {
        "operation_id": "listUnassignedConsultationInquiries",
        "contract_status": "CONFIRMED",
        "runtime_path": "/api/v1/inquiries/unassigned-consultations",
        "url_name": "unassigned-consultation-queue",
        "view_name": "UnassignedConsultationQueueView",
    },
    ("/inquiries", "post"): {
        "operation_id": "startInquiry",
        "contract_status": "CONFIRMED",
        "runtime_path": "/api/v1/inquiries",
        "url_name": "inquiry-create",
        "view_name": "CreateInquiryView",
    },
    ("/inquiries", "get"): {
        "operation_id": "listConsultantInquiries",
        "contract_status": "CONFIRMED",
        "runtime_path": "/api/v1/inquiries",
        "url_name": "inquiry-create",
        "view_name": "CreateInquiryView",
    },
    ("/inquiries/{id}", "get"): {
        "operation_id": "getConsultantInquiryDetail",
        "contract_status": "CONFIRMED",
        "runtime_path": f"/api/v1/inquiries/{INQUIRY_ID}",
        "url_name": "consultant-inquiry-detail",
        "view_name": "ConsultantInquiryDetailView",
    },
    ("/inquiries/{id}/cancel", "post"): {
        "operation_id": "cancelInquiry",
        "contract_status": "CONFIRMED",
        "runtime_path": f"/api/v1/inquiries/{INQUIRY_ID}/cancel",
        "url_name": "inquiry-cancel",
        "view_name": "CancelInquiryView",
    },
    ("/inquiries/{id}/submit", "post"): {
        "operation_id": "submitSymptom",
        "contract_status": "CONFIRMED",
        "runtime_path": f"/api/v1/inquiries/{INQUIRY_ID}/submit",
        "url_name": "inquiry-submit",
        "view_name": "SubmitSymptomView",
    },
    ("/inquiries/{id}/questionnaire", "patch"): {
        "operation_id": "accumulateInquiryQuestionnaire",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/inquiries/{INQUIRY_ID}/questionnaire"
        ),
        "url_name": None,
        "view_name": None,
    },
    ("/inquiries/{id}/answers", "post"): {
        "operation_id": "submitFollowUpAnswers",
        "contract_status": "CONFIRMED",
        "runtime_path": f"/api/v1/inquiries/{INQUIRY_ID}/answers",
        "url_name": "inquiry-submit-followup-answers",
        "view_name": "SubmitFollowUpAnswersView",
    },
    ("/inquiries/{id}/request-consultation", "post"): {
        "operation_id": "requestConsultation",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/inquiries/{INQUIRY_ID}/request-consultation"
        ),
        "url_name": "inquiry-request-consultation",
        "view_name": "RequestConsultationView",
    },
    ("/inquiries/{id}/claim-consultation", "post"): {
        "operation_id": "claimConsultation",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/inquiries/{INQUIRY_ID}/claim-consultation"
        ),
        "url_name": "inquiry-claim-consultation",
        "view_name": "ClaimConsultationView",
    },
    ("/inquiries/{id}/resolution-feedback", "post"): {
        "operation_id": "submitResolutionFeedback",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/inquiries/{INQUIRY_ID}/resolution-feedback"
        ),
        "url_name": "inquiry-resolution-feedback",
        "view_name": "SubmitResolutionFeedbackView",
    },
    ("/inquiries/{id}/finalize", "post"): {
        "operation_id": "finalizeInquiry",
        "contract_status": "CONFIRMED",
        "runtime_path": f"/api/v1/inquiries/{INQUIRY_ID}/finalize",
        "url_name": "inquiry-finalize",
        "view_name": "FinalizeInquiryView",
    },
    ("/inquiries/{id}/report-unresolved", "post"): {
        "operation_id": "reportUnresolved",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/inquiries/{INQUIRY_ID}/report-unresolved"
        ),
        "url_name": "inquiry-report-unresolved",
        "view_name": "ReportUnresolvedView",
    },
    ("/inquiries/{id}/resume-consultation", "post"): {
        "operation_id": "resumeConsultation",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/inquiries/{INQUIRY_ID}/resume-consultation"
        ),
        "url_name": "inquiry-resume-consultation",
        "view_name": "ResumeConsultationView",
    },
    ("/inquiries/{id}/action-results", "post"): {
        "operation_id": "createInquiryActionResult",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/inquiries/{INQUIRY_ID}/action-results"
        ),
        "url_name": "inquiry-create-action-result",
        "view_name": "CreateActionResultView",
    },
    ("/inquiries/{id}/start-consultation", "post"): {
        "operation_id": "startConsultation",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/inquiries/{INQUIRY_ID}/start-consultation"
        ),
        "url_name": "consultation-start",
        "view_name": "StartConsultationView",
    },
    ("/inquiries/{id}/consultation-summary", "patch"): {
        "operation_id": "updateConsultationSummary",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/inquiries/{INQUIRY_ID}/consultation-summary"
        ),
        "url_name": "consultation-summary-update",
        "view_name": "UpdateConsultationSummaryView",
    },
    ("/inquiries/{id}/consultation-summary/confirm", "post"): {
        "operation_id": "confirmConsultationSummary",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/inquiries/{INQUIRY_ID}/consultation-summary/confirm"
        ),
        "url_name": "consultation-summary-confirm",
        "view_name": "ConfirmConsultationSummaryView",
    },
    ("/inquiries/{id}/complete-consultation", "post"): {
        "operation_id": "completeConsultation",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/inquiries/{INQUIRY_ID}/complete-consultation"
        ),
        "url_name": "consultation-complete",
        "view_name": "CompleteConsultationView",
    },
    ("/inquiries/{id}/visit-review", "post"): {
        "operation_id": "requestVisitReview",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/inquiries/{INQUIRY_ID}/visit-review"
        ),
        "url_name": "visit-review",
        "view_name": "RequestVisitReviewView",
    },
    ("/inquiries/{id}/visits", "post"): {
        "operation_id": "createVisitRequest",
        "contract_status": "CONFIRMED",
        "runtime_path": f"/api/v1/inquiries/{INQUIRY_ID}/visits",
        "url_name": "visit-create",
        "view_name": "CreateVisitRequestView",
    },
    ("/inquiries/{id}/visit-not-needed", "post"): {
        "operation_id": "markVisitNotNeeded",
        "contract_status": "CONFIRMED",
        "runtime_path": (
            f"/api/v1/inquiries/{INQUIRY_ID}/visit-not-needed"
        ),
        "url_name": "visit-not-needed",
        "view_name": "MarkVisitNotNeededView",
    },
    ("/visits/{visit_id}/schedule", "patch"): {
        "operation_id": "updateVisitSchedule",
        "contract_status": "CONFIRMED",
        "runtime_path": f"/api/v1/visits/{VISIT_ID}/schedule",
        "url_name": "visit-schedule-update",
        "view_name": "UpdateVisitScheduleView",
    },
    ("/visits/{visit_id}/confirm", "post"): {
        "operation_id": "confirmVisit",
        "contract_status": "CONFIRMED",
        "runtime_path": f"/api/v1/visits/{VISIT_ID}/confirm",
        "url_name": "visit-confirm",
        "view_name": "ConfirmVisitView",
    },
    ("/visits/{visit_id}/start", "post"): {
        "operation_id": "startVisit",
        "contract_status": "CONFIRMED",
        "runtime_path": f"/api/v1/visits/{VISIT_ID}/start",
        "url_name": None,
        "view_name": None,
    },
    ("/visits/{visit_id}/complete", "post"): {
        "operation_id": "completeVisit",
        "contract_status": "CONFIRMED",
        "runtime_path": f"/api/v1/visits/{VISIT_ID}/complete",
        "url_name": None,
        "view_name": None,
    },
}


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def resolve_json_pointer(document: Any, fragment: str) -> Any:
    current = document
    pointer = fragment.removeprefix("/")
    if not pointer:
        return current
    for token in pointer.split("/"):
        decoded = token.replace("~1", "/").replace("~0", "~")
        current = current[decoded]
    return current


def load_path_item(path_item: dict[str, Any]) -> dict[str, Any]:
    reference = path_item.get("$ref")
    if reference is None:
        return path_item

    external_path, _, fragment = reference.partition("#")
    target_path = (OPENAPI_PATH.parent / external_path).resolve()
    target_document = load_yaml(target_path)
    return resolve_json_pointer(target_document, fragment)


def collect_operations() -> dict[tuple[str, str], dict[str, Any]]:
    specification = load_yaml(OPENAPI_PATH)
    operations = {}
    for api_path, raw_path_item in specification["paths"].items():
        path_item = load_path_item(raw_path_item)
        for method, operation in path_item.items():
            if method in HTTP_METHODS:
                operations[(api_path, method)] = operation
    return operations


def runtime_view_name(match) -> str:
    view_class = getattr(match.func, "view_class", None)
    if view_class is not None:
        return view_class.__name__
    return match.func.__name__


def test_openapi_operation_inventory_is_exactly_forty_nine():
    operations = collect_operations()

    assert set(operations) == set(EXPECTED_OPERATIONS)
    assert len(operations) == 49
    assert {
        operation["operationId"] for operation in operations.values()
    } == {
        expected["operation_id"]
        for expected in EXPECTED_OPERATIONS.values()
    }

    for key, expected in EXPECTED_OPERATIONS.items():
        operation = operations[key]
        assert operation["operationId"] == expected["operation_id"]
        assert operation["x-contract-status"] == (
            expected["contract_status"]
        )


def test_forty_six_operations_resolve_to_expected_runtime_views():
    implemented = [
        (key, expected)
        for key, expected in EXPECTED_OPERATIONS.items()
        if expected.get(
            "runtime_method", expected["url_name"] is not None
        )
    ]

    assert len(implemented) == 46
    for (_, method), expected in implemented:
        match = resolve(expected["runtime_path"])
        assert match.url_name == expected["url_name"]
        assert runtime_view_name(match) == expected["view_name"]
        view_class = getattr(match.func, "view_class", None)
        if view_class is not None:
            assert callable(getattr(view_class, method, None))


def test_three_openapi_only_operations_have_no_runtime_method():
    openapi_only = [
        (key, expected)
        for key, expected in EXPECTED_OPERATIONS.items()
        if not expected.get(
            "runtime_method", expected["url_name"] is not None
        )
    ]

    assert len(openapi_only) == 3
    for (_, method), expected in openapi_only:
        match = resolve(expected["runtime_path"])
        if expected["url_name"] is None:
            assert match.url_name == "api-not-found"
            assert runtime_view_name(match) == "api_not_found"
            continue

        assert match.url_name == expected["url_name"]
        assert runtime_view_name(match) == expected["view_name"]
        view_class = getattr(match.func, "view_class", None)
        assert view_class is not None
        assert getattr(view_class, method, None) is None
