import { resolve } from "node:path";

import {
  expect,
  test,
  type Locator,
  type Page,
  type Response,
} from "@playwright/test";

import {
  readBackendFixture,
  type WebConsultationE2EFixture,
} from "../support/backendFixture.js";
import {
  attachMaskedEvidenceScreenshot,
  attachMaskedFailureScreenshot,
  installArtifactPrivacyMask,
} from "../support/privacy.js";

const missingInquiryId = "00000000-0000-4000-8000-000000000000";
let fixture: WebConsultationE2EFixture;

const USAGE_GUIDANCE_DISPLAY_LABELS = {
  NORMAL: "정상 사용 가능",
  PARTIAL_STOP: "일부 기능 사용 중단",
  TOTAL_STOP: "제품 사용 중단",
  PENDING_CONSULTATION: "상담 확인 필요",
} as const;

const EXPECTED_CUSTOMER_DISPLAY_NAME = "제갈지용";
const EXPECTED_CUSTOMER_PHONE_MASKED = "010-****-5678";
const EXPECTED_QUESTIONNAIRE = [
  {
    questionCode: "followup-occurrence-time",
    questionText: "증상은 언제부터 시작됐나요?",
    answer: "오늘",
  },
  {
    questionCode: "followup-target-water-type",
    questionText: "어떤 출수에서 증상이 발생하나요?",
    answer: "정수",
  },
  {
    questionCode: "followup-occurrence-condition",
    questionText: "증상은 언제 또는 어떤 조건에서 발생하나요?",
    answer: "출수 버튼을 누를 때",
  },
  {
    questionCode: "followup-actions-taken",
    questionText: "이미 확인하거나 조치해 본 내용이 있나요?",
    answer: "필터 상태 확인",
  },
] as const;

interface InitialDetailPresentation {
  productModel: string;
  productModelName: string;
  usageGuidanceStatus: keyof typeof USAGE_GUIDANCE_DISPLAY_LABELS;
  usageGuidanceDisplayLabel: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isDetailResponse(response: Response, inquiryId: string): boolean {
  return (
    response.request().method() === "GET" &&
    response.url().includes(
      `/api/v1/inquiries/${encodeURIComponent(inquiryId)}`,
    )
  );
}

async function expectInitialDetailContract(
  response: Response,
  activeFixture: WebConsultationE2EFixture,
  recordMissingFieldFailures = true,
): Promise<InitialDetailPresentation> {
  expect(response.status()).toBe(200);
  const payload: unknown = await response.json();
  if (!isRecord(payload) || !isRecord(payload.data)) {
    throw new Error("상담사 문의 상세 응답이 공통 API 구조와 다릅니다.");
  }
  const data = payload.data;
  if (
    !isRecord(data.inquiry) ||
    !isRecord(data.workflow) ||
    !isRecord(data.customer)
  ) {
    throw new Error("상담사 문의 상세 공개 Projection이 올바르지 않습니다.");
  }
  expect(data.customer.is_synthetic).toBe(true);
  expect(data.inquiry.inquiry_id).toBe(activeFixture.inquiryId);
  expect(data.inquiry.status).toBe(activeFixture.status);
  expect(data.inquiry.state_version).toBe(activeFixture.stateVersion);
  expect(data.workflow.status).toBe(activeFixture.status);
  expect(data.workflow.state_version).toBe(activeFixture.stateVersion);
  const actionCodes = Array.isArray(data.workflow.allowed_actions)
    ? data.workflow.allowed_actions.flatMap((action) =>
        isRecord(action) && typeof action.code === "string"
          ? [action.code]
          : [],
      )
    : [];
  expect(actionCodes).toEqual([...activeFixture.allowedActions]);

  if (
    !isRecord(data.product_and_care) ||
    typeof data.product_and_care.product_model !== "string" ||
    data.product_and_care.product_model.trim().length === 0 ||
    typeof data.product_and_care.product_model_name !== "string" ||
    data.product_and_care.product_model_name.trim().length === 0 ||
    !isRecord(data.guidance_and_actions)
  ) {
    throw new Error(
      "상담 통합 상세의 제품·AI 안내 Projection이 올바르지 않습니다.",
    );
  }

  const customerDisplayName =
    typeof data.customer.display_name === "string"
      ? data.customer.display_name
      : null;
  const phoneMasked =
    typeof data.customer.phone_masked === "string"
      ? data.customer.phone_masked
      : null;
  if (recordMissingFieldFailures) {
    expect.soft(
      customerDisplayName,
      "상담 상세 API의 합성 고객 이름이 예상값과 달라서는 안 됩니다.",
    ).toBe(EXPECTED_CUSTOMER_DISPLAY_NAME);
    expect.soft(
      phoneMasked,
      "상담 상세 API의 마스킹 연락처가 예상값과 달라서는 안 됩니다.",
    ).toBe(EXPECTED_CUSTOMER_PHONE_MASKED);
  }

  const answers =
    isRecord(data.symptom_and_questionnaire) &&
    Array.isArray(data.symptom_and_questionnaire.answers)
      ? data.symptom_and_questionnaire.answers
      : [];
  const questionnaire = answers.flatMap((answer) =>
    isRecord(answer) &&
    typeof answer.question_code === "string" &&
    typeof answer.question_text === "string" &&
    typeof answer.answer === "string"
      ? [
          {
            questionCode: answer.question_code,
            questionText: answer.question_text,
            answer: answer.answer,
          },
        ]
      : [],
  );
  if (recordMissingFieldFailures) {
    expect.soft(
      questionnaire,
      "상담 상세 API의 문진 질문·답변 4건이 예상값과 일치해야 합니다.",
    ).toEqual(EXPECTED_QUESTIONNAIRE);
  }

  const usageGuidanceStatus = data.guidance_and_actions
    .usage_guidance_status;
  if (
    typeof usageGuidanceStatus !== "string" ||
    !(usageGuidanceStatus in USAGE_GUIDANCE_DISPLAY_LABELS) ||
    typeof data.guidance_and_actions.usage_guidance_display_label !==
      "string" ||
    data.guidance_and_actions.usage_guidance_display_label !==
      USAGE_GUIDANCE_DISPLAY_LABELS[
        usageGuidanceStatus as keyof typeof USAGE_GUIDANCE_DISPLAY_LABELS
      ]
  ) {
    throw new Error("AI 안내 상태 코드와 한글 표시명이 일치하지 않습니다.");
  }
  if (data.visit !== null) {
    throw new Error("상담 완료 Fixture의 최초 상세에 방문 정보가 없어야 합니다.");
  }

  for (const key of ["evidence", "official_evidence", "public_evidence"]) {
    if (key in data || key in data.guidance_and_actions) {
      throw new Error(
        "계약에 없는 공식 Evidence가 상담 상세 응답에 포함되었습니다.",
      );
    }
  }

  return {
    productModel: data.product_and_care.product_model,
    productModelName: data.product_and_care.product_model_name,
    usageGuidanceStatus:
      usageGuidanceStatus as keyof typeof USAGE_GUIDANCE_DISPLAY_LABELS,
    usageGuidanceDisplayLabel:
      data.guidance_and_actions.usage_guidance_display_label,
  };
}

async function expectInitialDetailPresentation(
  detailPanel: Locator,
  expected: InitialDetailPresentation,
): Promise<void> {
  const customerSection = detailPanel
    .getByRole("heading", {
      name: EXPECTED_CUSTOMER_DISPLAY_NAME,
      exact: true,
    })
    .locator("..");
  await expect(
    customerSection.getByText(EXPECTED_CUSTOMER_DISPLAY_NAME, { exact: true }),
  ).toBeVisible();
  await expect(
    customerSection.getByText(EXPECTED_CUSTOMER_PHONE_MASKED, { exact: true }),
  ).toBeVisible();

  const productSection = detailPanel
    .getByRole("heading", { name: "제품·관리 정보", exact: true })
    .locator("..");
  await expect(
    detailPanel.getByText(expected.productModelName, { exact: true }),
  ).toBeVisible();
  await expect(
    productSection.getByText(expected.productModel, { exact: true }),
  ).toBeVisible();

  const questionnaireSection = detailPanel
    .getByRole("heading", { name: "고객 증상과 답변", exact: true })
    .locator("..");
  for (const item of EXPECTED_QUESTIONNAIRE) {
    await expect(
      questionnaireSection.getByText(item.questionText, { exact: true }),
    ).toBeVisible();
    await expect(
      questionnaireSection.getByText(item.answer, { exact: true }),
    ).toBeVisible();
  }

  const guidanceSection = detailPanel
    .getByRole("heading", { name: "고객에게 안내할 내용", exact: true })
    .locator("..");
  await expect(
    guidanceSection.getByText(expected.usageGuidanceDisplayLabel, {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    guidanceSection.getByText(expected.usageGuidanceStatus, { exact: true }),
  ).toHaveCount(0);
  await expect(
    guidanceSection.getByText("공식 근거는 아직 제공되지 않았습니다.", {
      exact: true,
    }),
  ).toBeVisible();

  await expect(
    detailPanel.getByRole("heading", { name: "방문 정보", exact: true }),
  ).toHaveCount(0);
}

async function expectCompletedDetailContract(
  response: Response,
  activeFixture: WebConsultationE2EFixture,
  expected: {
    consultationNote: string;
    customerGuidance: string;
    confirmedSummary: string;
  },
): Promise<void> {
  expect(response.status()).toBe(200);
  const payload: unknown = await response.json();
  if (!isRecord(payload) || !isRecord(payload.data)) {
    throw new Error("완료된 상담사 문의 상세 응답이 공통 API 구조와 다릅니다.");
  }
  const data = payload.data;
  if (
    !isRecord(data.inquiry) ||
    !isRecord(data.workflow) ||
    !isRecord(data.consultation) ||
    !isRecord(data.consultation.summary)
  ) {
    throw new Error("완료된 상담사 문의 상세 Projection이 올바르지 않습니다.");
  }

  expect(data.inquiry.inquiry_id).toBe(activeFixture.inquiryId);
  expect(data.inquiry.status).toBe("COMPLETION_PENDING");
  expect(data.workflow.status).toBe("COMPLETION_PENDING");
  expect(data.inquiry.state_version).toBe(data.workflow.state_version);
  expect(data.workflow.state_version).toEqual(expect.any(Number));
  expect(data.workflow.state_version).toBeGreaterThan(activeFixture.stateVersion);
  expect(data.consultation.consultation_note).toBe(expected.consultationNote);
  expect(data.consultation.customer_guidance).toBe(expected.customerGuidance);
  expect(data.consultation.summary.confirmed_summary).toBe(
    expected.confirmedSummary,
  );
}

async function loginToFixture(
  page: Page,
  activeFixture: WebConsultationE2EFixture,
): Promise<void> {
  const listPath = `/consultant/inquiries?bucket=NEW&q=${encodeURIComponent(activeFixture.inquiryCode)}`;
  await page.goto(listPath);
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("역할").selectOption("CONSULTANT");
  await page
    .getByRole("button", { name: "API 데모 계정으로 로그인" })
    .click();
  await expect(page).toHaveURL((url) => {
    return (
      url.pathname === "/consultant/inquiries" &&
      url.searchParams.get("bucket") === "NEW" &&
      url.searchParams.get("q") === activeFixture.inquiryCode
    );
  });
}

async function authenticatedBrowserRequest(
  page: Page,
  input: {
    method: "GET" | "PATCH" | "POST";
    path: string;
    body?: Record<string, unknown>;
    idempotencyKey?: string;
  },
): Promise<{
  status: number;
  code: string | null;
  stateVersion: number | null;
}> {
  return page.evaluate(async (request) => {
    const serialized = window.localStorage.getItem(
      "waterbridge.auth.session.v1",
    );
    if (!serialized) throw new Error("상담사 로그인 세션이 없습니다.");
    const session: unknown = JSON.parse(serialized);
    if (
      typeof session !== "object" ||
      session === null ||
      !("accessToken" in session) ||
      typeof session.accessToken !== "string"
    ) {
      throw new Error("상담사 로그인 세션 형식이 올바르지 않습니다.");
    }

    const headers = new Headers({
      Accept: "application/json",
      Authorization: `Bearer ${session.accessToken}`,
      "X-Correlation-ID": crypto.randomUUID(),
    });
    if (request.body !== undefined) {
      headers.set("Content-Type", "application/json");
    }
    if (request.idempotencyKey) {
      headers.set("Idempotency-Key", request.idempotencyKey);
    }
    const response = await fetch(request.path, {
      method: request.method,
      headers,
      body:
        request.body === undefined
          ? undefined
          : JSON.stringify(request.body),
    });
    const payload: unknown = await response.json();
    const error =
      typeof payload === "object" &&
      payload !== null &&
      "error" in payload &&
      typeof payload.error === "object" &&
      payload.error !== null
        ? payload.error
        : null;
    const data =
      typeof payload === "object" &&
      payload !== null &&
      "data" in payload &&
      typeof payload.data === "object" &&
      payload.data !== null
        ? payload.data
        : null;
    const details =
      error &&
      "details" in error &&
      typeof error.details === "object" &&
      error.details !== null
        ? error.details
        : null;
    return {
      status: response.status,
      code:
        error && "code" in error && typeof error.code === "string"
          ? error.code
          : null,
      stateVersion:
        data &&
        "state_version" in data &&
        typeof data.state_version === "number"
          ? data.state_version
          : details &&
              "current_state_version" in details &&
              typeof details.current_state_version === "number"
            ? details.current_state_version
            : null,
    };
  }, input);
}

async function authenticatedInquiryListIds(page: Page): Promise<{
  status: number;
  inquiryIds: string[];
}> {
  return page.evaluate(async () => {
    const serialized = window.localStorage.getItem(
      "waterbridge.auth.session.v1",
    );
    if (!serialized) throw new Error("상담사 로그인 세션이 없습니다.");
    const session: unknown = JSON.parse(serialized);
    if (
      typeof session !== "object" ||
      session === null ||
      !("accessToken" in session) ||
      typeof session.accessToken !== "string"
    ) {
      throw new Error("상담사 로그인 세션 형식이 올바르지 않습니다.");
    }

    const inquiryIds: string[] = [];
    const size = 100;
    let page = 1;
    let total: number;
    let lastStatus: number;

    do {
      const params = new URLSearchParams({
        sort: "UPDATED_DESC",
        page: String(page),
        size: String(size),
      });
      const response = await fetch(`/api/v1/inquiries?${params.toString()}`, {
        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${session.accessToken}`,
          "X-Correlation-ID": crypto.randomUUID(),
        },
      });
      lastStatus = response.status;
      const payload: unknown = await response.json();
      const data =
        typeof payload === "object" &&
        payload !== null &&
        "data" in payload &&
        typeof payload.data === "object" &&
        payload.data !== null
          ? payload.data
          : null;
      const items =
        data && "items" in data && Array.isArray(data.items) ? data.items : [];
      inquiryIds.push(
        ...items.flatMap((item) =>
          typeof item === "object" &&
          item !== null &&
          "inquiry_id" in item &&
          typeof item.inquiry_id === "string"
            ? [item.inquiry_id]
            : [],
        ),
      );
      const pageInfo =
        data &&
        "page_info" in data &&
        typeof data.page_info === "object" &&
        data.page_info !== null
          ? data.page_info
          : null;
      total =
        pageInfo &&
        "total" in pageInfo &&
        typeof pageInfo.total === "number"
          ? pageInfo.total
          : inquiryIds.length;
      if (!response.ok || items.length === 0) break;
      page += 1;
    } while (inquiryIds.length < total && page <= 100);

    return { status: lastStatus, inquiryIds };
  });
}

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  fixture = readBackendFixture(
    resolve(
      process.env.E2E_FIXTURE_JSON_PATH ||
        ".runtime/playwright/backend-fixture.json",
    ),
  );
});

test.beforeEach(async ({ page }) => {
  await installArtifactPrivacyMask(page);
});

test.afterEach(async ({ page }, testInfo) => {
  await attachMaskedFailureScreenshot(page, testInfo);
});

test("Backend Fixture로 상담 처리와 404·409 경계를 검증한다", async (
  { page },
  testInfo,
) => {
  const unassignedInquiryId = process.env.E2E_UNASSIGNED_INQUIRY_ID?.trim();
  if (!unassignedInquiryId) {
    throw new Error(
      "BACKEND_FIXTURE_BLOCKED: 비배정 404 검증용 합성 inquiry_id가 필요합니다.",
    );
  }
  if (
    unassignedInquiryId === fixture.inquiryId ||
    unassignedInquiryId === missingInquiryId
  ) {
    throw new Error(
      "BACKEND_FIXTURE_BLOCKED: 비배정 문의 ID가 양성 또는 미존재 테스트 ID와 같습니다.",
    );
  }
  const consultationNote = `E2E 상담 기록 ${fixture.runId}`;
  const customerGuidance = `E2E 고객 안내 ${fixture.runId}`;
  const confirmedSummary = `E2E 확정 요약 ${fixture.runId}`;
  await loginToFixture(page, fixture);
  const fixtureCard = page.getByTestId(
    `consultant-inquiry-${fixture.inquiryId}`,
  );
  await expect(fixtureCard).toBeVisible();
  const initialDetailResponse = page.waitForResponse((response) =>
    isDetailResponse(response, fixture.inquiryId),
  );
  await fixtureCard.click();
  const listFirstDetailPanel = page.getByRole("dialog");
  await expect(listFirstDetailPanel).toBeVisible();
  const initialDetailPresentation = await expectInitialDetailContract(
    await initialDetailResponse,
    fixture,
  );
  await expectInitialDetailPresentation(
    listFirstDetailPanel,
    initialDetailPresentation,
  );
  await expect(
    listFirstDetailPanel.locator('[data-action-code="START_CONSULTATION"]'),
  ).toBeVisible();
  await expect(
    listFirstDetailPanel.getByRole("button", { name: "전체 기록 보기" }),
  ).toHaveCount(0);
  await expect(page).toHaveURL((url) => {
    return (
      url.pathname === "/consultant/inquiries" &&
      url.searchParams.get("bucket") === "NEW" &&
      url.searchParams.get("q") === fixture.inquiryCode
    );
  });
  await listFirstDetailPanel
    .getByRole("button", { name: "문의 상세 닫기" })
    .click();
  await expect(listFirstDetailPanel).not.toBeVisible();

  await page.goto("/consultant/dashboard");
  await expect(page).toHaveURL((url) => url.pathname === "/consultant/dashboard");
  const recentInquiry = page.getByTestId(
    `consultant-recent-inquiry-${fixture.inquiryId}`,
  );
  await expect(recentInquiry).toBeVisible();
  const dashboardDetailResponse = page.waitForResponse((response) =>
    isDetailResponse(response, fixture.inquiryId),
  );
  await recentInquiry.click();
  const firstDetailPanel = page.getByRole("dialog");
  await expect(firstDetailPanel).toBeVisible();
  await expectInitialDetailContract(
    await dashboardDetailResponse,
    fixture,
    false,
  );
  await expect(
    firstDetailPanel.locator('[data-action-code="START_CONSULTATION"]'),
  ).toBeVisible();
  await expect(page).toHaveURL((url) => url.pathname === "/consultant/dashboard");

  const visibleInquiryList = await authenticatedInquiryListIds(page);
  expect(visibleInquiryList.status).toBe(200);
  expect(visibleInquiryList.inquiryIds).toContain(fixture.inquiryId);
  expect(visibleInquiryList.inquiryIds).not.toContain(unassignedInquiryId);

  const concealedDetail = await authenticatedBrowserRequest(page, {
    method: "GET",
    path: `/api/v1/inquiries/${encodeURIComponent(unassignedInquiryId)}`,
  });
  expect(concealedDetail).toEqual({
    status: 404,
    code: "RESOURCE_NOT_FOUND",
    stateVersion: null,
  });
  const concealedStart = await authenticatedBrowserRequest(page, {
    method: "POST",
    path: `/api/v1/inquiries/${encodeURIComponent(unassignedInquiryId)}/start-consultation`,
    idempotencyKey: `e2e-unassigned-start-${fixture.runId}`,
    body: { state_version: Number.MAX_SAFE_INTEGER },
  });
  expect(concealedStart).toEqual({
    status: 404,
    code: "RESOURCE_NOT_FOUND",
    stateVersion: null,
  });

  const missingDetail = await authenticatedBrowserRequest(page, {
    method: "GET",
    path: `/api/v1/inquiries/${missingInquiryId}`,
  });
  expect(missingDetail).toEqual({
    status: 404,
    code: "RESOURCE_NOT_FOUND",
    stateVersion: null,
  });
  const missingStart = await authenticatedBrowserRequest(page, {
    method: "POST",
    path: `/api/v1/inquiries/${missingInquiryId}/start-consultation`,
    idempotencyKey: `e2e-missing-${fixture.runId}`,
    body: { state_version: Number.MAX_SAFE_INTEGER },
  });
  expect(missingStart).toEqual({
    status: 404,
    code: "RESOURCE_NOT_FOUND",
    stateVersion: null,
  });

  const startResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(
        `/api/v1/inquiries/${fixture.inquiryId}/start-consultation`,
      ),
  );
  await firstDetailPanel
    .locator('[data-action-code="START_CONSULTATION"]')
    .click();
  expect((await startResponse).status()).toBe(200);
  await expect(
    firstDetailPanel.locator(
      '[data-action-code="UPDATE_CONSULTATION_SUMMARY"]',
    ),
  ).toBeVisible();

  await firstDetailPanel
    .getByLabel("상담 기록", { exact: true })
    .fill(consultationNote);
  await firstDetailPanel
    .getByLabel("고객 안내 내용", { exact: true })
    .fill(customerGuidance);
  await firstDetailPanel
    .getByLabel("상담 요약 수정본", { exact: true })
    .fill(confirmedSummary);
  await firstDetailPanel
    .getByLabel("방문 필요 여부")
    .selectOption("NOT_REQUIRED");
  await firstDetailPanel
    .getByLabel("제품 사용 상태")
    .selectOption("NORMAL");
  await firstDetailPanel
    .getByRole("checkbox", { name: "상담 요약 검토·확정" })
    .check();

  const concurrentSave = await authenticatedBrowserRequest(page, {
    method: "PATCH",
    path: `/api/v1/inquiries/${fixture.inquiryId}/consultation-summary`,
    idempotencyKey: `e2e-concurrent-${fixture.runId}`,
    body: {
      state_version: fixture.stateVersion + 1,
      summary: `E2E 동시 저장 ${fixture.runId}`,
      consultation_note: `E2E 동시 기록 ${fixture.runId}`,
      customer_guidance: `E2E 동시 안내 ${fixture.runId}`,
      result_code: "COMPLETED_NO_VISIT",
      usage_guidance_status: "NORMAL",
    },
  });
  expect(concurrentSave.status).toBe(200);
  expect(concurrentSave.stateVersion).toBe(fixture.stateVersion + 2);

  let updateRequestCount = 0;
  const countUpdateRequest = (request: { method(): string; url(): string }) => {
    if (
      request.method() === "PATCH" &&
      request.url().endsWith(
        `/api/v1/inquiries/${fixture.inquiryId}/consultation-summary`,
      )
    ) {
      updateRequestCount += 1;
    }
  };
  page.on("request", countUpdateRequest);
  const staleResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().endsWith(
        `/api/v1/inquiries/${fixture.inquiryId}/consultation-summary`,
      ) &&
      response.status() === 409,
  );
  const conflictRefreshResponse = page.waitForResponse(
    (response) =>
      isDetailResponse(response, fixture.inquiryId) &&
      response.status() === 200,
  );
  await firstDetailPanel
    .locator('[data-action-code="UPDATE_CONSULTATION_SUMMARY"]')
    .click();
  const stalePayload: unknown = await (await staleResponse).json();
  expect(updateRequestCount).toBe(1);
  expect(
    isRecord(stalePayload) &&
      isRecord(stalePayload.error) &&
      stalePayload.error.code,
  ).toBe("STATE-CONFLICT-01");
  expect((await conflictRefreshResponse).status()).toBe(200);
  await expect(firstDetailPanel.getByRole("alert")).toBeVisible();
  await expect(
    firstDetailPanel.getByTestId("consultation-current-status"),
  ).toHaveAttribute("data-workflow-status", "CONSULTATION_IN_PROGRESS");
  await expect(
    firstDetailPanel.getByTestId("consultation-current-status"),
  ).toHaveAttribute(
    "data-state-version",
    String(fixture.stateVersion + 2),
  );
  await expect(
    firstDetailPanel.getByTestId("consultation-field-consultationNote"),
  ).toHaveValue(consultationNote);
  await expect(
    firstDetailPanel.getByTestId("consultation-field-customerGuidance"),
  ).toHaveValue(customerGuidance);
  await expect(
    firstDetailPanel.getByTestId("consultation-field-summaryRevision"),
  ).toHaveValue(confirmedSummary);
  await expect(
    firstDetailPanel.getByLabel("방문 필요 여부"),
  ).toHaveValue("NOT_REQUIRED");
  await expect(
    firstDetailPanel.getByLabel("제품 사용 상태"),
  ).toHaveValue("NORMAL");
  await expect(
    firstDetailPanel.getByRole("checkbox", {
      name: "상담 요약 검토·확정",
    }),
  ).toBeChecked();
  page.off("request", countUpdateRequest);

  const saveResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().endsWith(
        `/api/v1/inquiries/${fixture.inquiryId}/consultation-summary`,
      ) &&
      response.status() === 200,
  );
  await firstDetailPanel
    .locator('[data-action-code="UPDATE_CONSULTATION_SUMMARY"]')
    .click();
  expect((await saveResponse).status()).toBe(200);

  const confirmResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(
        `/api/v1/inquiries/${fixture.inquiryId}/consultation-summary/confirm`,
      ),
  );
  page.once("dialog", (dialog) => void dialog.accept());
  await firstDetailPanel
    .locator('[data-action-code="CONFIRM_CONSULTATION_SUMMARY"]')
    .click();
  expect((await confirmResponse).status()).toBe(200);

  const completeResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(
        `/api/v1/inquiries/${fixture.inquiryId}/complete-consultation`,
      ),
  );
  page.once("dialog", (dialog) => void dialog.accept());
  await firstDetailPanel
    .locator('[data-action-code="CONSULTATION_COMPLETED"]')
    .click();
  expect((await completeResponse).status()).toBe(200);
  await expect(
    firstDetailPanel.getByTestId("consultation-current-status"),
  ).toHaveAttribute("data-workflow-status", "COMPLETION_PENDING");
  await expect(page).toHaveURL((url) => url.pathname === "/consultant/dashboard");
  await expect(
    firstDetailPanel.getByTestId("consultation-detail-note"),
  ).toHaveText(
    consultationNote,
  );
  await expect(
    firstDetailPanel.getByTestId("consultation-detail-customer-guidance"),
  ).toHaveText(customerGuidance);
  await expect(
    firstDetailPanel.getByTestId("consultation-detail-confirmed-summary"),
  ).toHaveText(confirmedSummary);

  await page.reload();
  await expect(page).toHaveURL((url) => url.pathname === "/consultant/dashboard");
  const recoveredRecentInquiry = page.getByTestId(
    `consultant-recent-inquiry-${fixture.inquiryId}`,
  );
  await expect(recoveredRecentInquiry).toBeVisible();
  const recoveredDetailResponse = page.waitForResponse((response) =>
    isDetailResponse(response, fixture.inquiryId),
  );
  await recoveredRecentInquiry.click();
  const recoveredFirstDetailPanel = page.getByRole("dialog");
  await expect(recoveredFirstDetailPanel).toBeVisible();
  await expectCompletedDetailContract(await recoveredDetailResponse, fixture, {
    consultationNote,
    customerGuidance,
    confirmedSummary,
  });
  await expect(
    recoveredFirstDetailPanel.getByTestId("consultation-current-status"),
  ).toHaveAttribute("data-workflow-status", "COMPLETION_PENDING");
  await expect(
    recoveredFirstDetailPanel.getByTestId("consultation-detail-note"),
  ).toHaveText(consultationNote);
  await expect(
    recoveredFirstDetailPanel.getByTestId(
      "consultation-detail-customer-guidance",
    ),
  ).toHaveText(customerGuidance);
  await expect(
    recoveredFirstDetailPanel.getByTestId(
      "consultation-detail-confirmed-summary",
    ),
  ).toHaveText(confirmedSummary);
  await expect(page).toHaveURL((url) => url.pathname === "/consultant/dashboard");
  await attachMaskedEvidenceScreenshot(page, testInfo);
});
