import { resolve } from "node:path";

import { expect, test, type Page, type Response } from "@playwright/test";

import {
  readBackendFixture,
  type WebConsultationE2EFixture,
} from "../support/backendFixture.js";
import {
  attachMaskedFailureScreenshot,
  installArtifactPrivacyMask,
} from "../support/privacy.js";

const missingInquiryId = "00000000-0000-4000-8000-000000000000";
let fixture: WebConsultationE2EFixture;

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

function isNewInquiryListResponse(
  response: Response,
  activeFixture: WebConsultationE2EFixture,
): boolean {
  const url = new URL(response.url());
  const statuses = url.searchParams.getAll("status");
  return (
    response.request().method() === "GET" &&
    url.pathname.endsWith("/api/v1/inquiries") &&
    url.searchParams.get("q") === activeFixture.inquiryCode &&
    statuses.length === 2 &&
    statuses.includes("CONSULTATION_REQUIRED") &&
    statuses.includes("REOPENED")
  );
}

async function expectFixtureInNewInquiryList(
  response: Response,
  activeFixture: WebConsultationE2EFixture,
): Promise<void> {
  expect(response.status()).toBe(200);
  const payload: unknown = await response.json();
  if (
    !isRecord(payload) ||
    !isRecord(payload.data) ||
    !Array.isArray(payload.data.items)
  ) {
    throw new Error("상담사 신규 문의 목록 응답이 공통 API 구조와 다릅니다.");
  }
  const fixtureItem = payload.data.items.find(
    (item: unknown) =>
      isRecord(item) && item.inquiry_id === activeFixture.inquiryId,
  );
  if (!isRecord(fixtureItem)) {
    throw new Error("Backend Fixture가 상담사 신규 문의 목록에 없습니다.");
  }
  expect(fixtureItem.inquiry_code).toBe(activeFixture.inquiryCode);
  expect(fixtureItem.status).toBe(activeFixture.status);
}

async function expectInitialDetailContract(
  response: Response,
  activeFixture: WebConsultationE2EFixture,
): Promise<void> {
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
}

async function loginToFixture(
  page: Page,
  activeFixture: WebConsultationE2EFixture,
): Promise<Response> {
  const listPath = `/consultant/inquiries?bucket=NEW&q=${encodeURIComponent(activeFixture.inquiryCode)}`;
  await page.goto(listPath);
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("역할").selectOption("CONSULTANT");
  const listResponse = page.waitForResponse((response) =>
    isNewInquiryListResponse(response, activeFixture),
  );
  await page
    .getByRole("button", { name: "API 데모 계정으로 로그인" })
    .click();
  return listResponse;
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

test("Backend Fixture로 상담 처리와 404·409 경계를 검증한다", async ({
  page,
}) => {
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
  const detailPath = `/consultant/inquiries/${encodeURIComponent(fixture.inquiryId)}`;
  const consultationNote = `E2E 상담 기록 ${fixture.runId}`;
  const customerGuidance = `E2E 고객 안내 ${fixture.runId}`;
  const confirmedSummary = `E2E 확정 요약 ${fixture.runId}`;
  const newInquiryListResponse = await loginToFixture(page, fixture);
  await expectFixtureInNewInquiryList(await newInquiryListResponse, fixture);
  const fixtureCard = page.getByTestId(
    `consultant-inquiry-${fixture.inquiryId}`,
  );
  await expect(fixtureCard).toBeVisible();
  const initialDetailResponse = page.waitForResponse((response) =>
    isDetailResponse(response, fixture.inquiryId),
  );
  await fixtureCard.click();
  await expect(page).toHaveURL(detailPath);
  await expectInitialDetailContract(await initialDetailResponse, fixture);
  await expect(
    page.locator('[data-action-code="START_CONSULTATION"]'),
  ).toBeVisible();

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

  await page.goto(`/consultant/inquiries/${missingInquiryId}`);
  await expect(
    page.getByRole("heading", { name: "문의 정보를 찾을 수 없습니다." }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "문의가 없거나 현재 상담사에게 배정되지 않은 경우 동일하게 안내됩니다.",
    ),
  ).toBeVisible();

  const fixtureDetailResponse = page.waitForResponse((response) =>
    isDetailResponse(response, fixture.inquiryId),
  );
  await page.goto(detailPath);
  await fixtureDetailResponse;

  const startResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(
        `/api/v1/inquiries/${fixture.inquiryId}/start-consultation`,
      ),
  );
  await page.locator('[data-action-code="START_CONSULTATION"]').click();
  expect((await startResponse).status()).toBe(200);
  await expect(
    page.locator('[data-action-code="UPDATE_CONSULTATION_SUMMARY"]'),
  ).toBeVisible();

  await page.getByLabel("상담 기록", { exact: true }).fill(consultationNote);
  await page
    .getByLabel("고객 안내", { exact: true })
    .fill(customerGuidance);
  await page.getByLabel("확정 요약", { exact: true }).fill(confirmedSummary);
  await page.getByLabel("방문 필요 여부").selectOption("NOT_REQUIRED");
  await page.getByLabel("사용 안내 상태").selectOption("NORMAL");
  await page.getByRole("checkbox", { name: "상담 요약 검토·확정" }).check();

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
  await page
    .locator('[data-action-code="UPDATE_CONSULTATION_SUMMARY"]')
    .click();
  const stalePayload: unknown = await (await staleResponse).json();
  expect(updateRequestCount).toBe(1);
  expect(
    isRecord(stalePayload) &&
      isRecord(stalePayload.error) &&
      stalePayload.error.code,
  ).toBe("STATE-CONFLICT-01");
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(
    page.getByTestId("consultation-current-status"),
  ).toHaveAttribute("data-workflow-status", "CONSULTATION_IN_PROGRESS");
  await expect(
    page.getByTestId("consultation-current-status"),
  ).toHaveAttribute(
    "data-state-version",
    String(fixture.stateVersion + 2),
  );
  await expect(page.getByLabel("상담 기록", { exact: true })).toHaveValue(
    consultationNote,
  );
  page.off("request", countUpdateRequest);

  const saveResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().endsWith(
        `/api/v1/inquiries/${fixture.inquiryId}/consultation-summary`,
      ) &&
      response.status() === 200,
  );
  await page
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
  await page
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
  await page
    .locator('[data-action-code="CONSULTATION_COMPLETED"]')
    .click();
  expect((await completeResponse).status()).toBe(200);
  await expect(
    page.getByTestId("consultation-current-status"),
  ).toHaveAttribute("data-workflow-status", "COMPLETION_PENDING");

  const refreshedDetailResponse = page.waitForResponse((response) =>
    isDetailResponse(response, fixture.inquiryId),
  );
  await page.reload();
  expect((await refreshedDetailResponse).status()).toBe(200);
  await expect(
    page.getByTestId("consultation-current-status"),
  ).toHaveAttribute("data-workflow-status", "COMPLETION_PENDING");

  const consultationSection = page
    .locator("section")
    .filter({ has: page.getByRole("heading", { name: "상담·방문 정보" }) });
  await expect(consultationSection.getByText(consultationNote)).toBeVisible();
  await expect(consultationSection.getByText(customerGuidance)).toBeVisible();
  await expect(consultationSection.getByText(confirmedSummary)).toBeVisible();

  const recoveredPage = await page.context().newPage();
  await installArtifactPrivacyMask(recoveredPage);
  const newTabDetailResponse = recoveredPage.waitForResponse((response) =>
    isDetailResponse(response, fixture.inquiryId),
  );
  await recoveredPage.goto(detailPath);
  expect((await newTabDetailResponse).status()).toBe(200);
  await expect(
    recoveredPage.getByTestId("consultation-current-status"),
  ).toHaveAttribute("data-workflow-status", "COMPLETION_PENDING");
  const recoveredConsultationSection = recoveredPage
    .locator("section")
    .filter({
      has: recoveredPage.getByRole("heading", { name: "상담·방문 정보" }),
    });
  await expect(
    recoveredConsultationSection.getByText(consultationNote),
  ).toBeVisible();
  await expect(
    recoveredConsultationSection.getByText(customerGuidance),
  ).toBeVisible();
  await expect(
    recoveredConsultationSection.getByText(confirmedSummary),
  ).toBeVisible();
  await recoveredPage.close();
});
