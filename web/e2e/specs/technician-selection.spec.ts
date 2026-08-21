import { resolve } from "node:path";

import { expect, test, type Page, type Response } from "@playwright/test";

import {
  readBackendFixture,
  type WebConsultationE2EFixture,
} from "../support/backendFixture.js";
import {
  attachMaskedEvidenceScreenshot,
  attachMaskedFailureScreenshot,
  installArtifactPrivacyMask,
} from "../support/privacy.js";

let fixture: WebConsultationE2EFixture;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isInquiryDetailResponse(
  response: Response,
  inquiryId: string,
): boolean {
  return (
    response.request().method() === "GET" &&
    response.url().includes(
      `/api/v1/inquiries/${encodeURIComponent(inquiryId)}`,
    )
  );
}

function isApiResponse(
  response: Response,
  method: "GET" | "PATCH" | "POST",
  path: string,
): boolean {
  return response.request().method() === method && response.url().endsWith(path);
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

async function readDashboardTechnicianId(response: Response): Promise<string> {
  expect(response.status()).toBe(200);
  const payload: unknown = await response.json();
  if (
    !isRecord(payload) ||
    !isRecord(payload.data) ||
    !Array.isArray(payload.data.technicians)
  ) {
    throw new Error("Dashboard 기사 목록 응답이 공통 API 구조와 다릅니다.");
  }
  const technician = payload.data.technicians.find(
    (candidate) =>
      isRecord(candidate) && typeof candidate.user_id === "string",
  );
  if (!isRecord(technician) || typeof technician.user_id !== "string") {
    throw new Error("Dashboard에 선택 가능한 합성 방문기사가 없습니다.");
  }
  return technician.user_id;
}

async function readTransitionResult(response: Response): Promise<{
  stateVersion: number;
  visitId: string | null;
}> {
  expect(response.status()).toBe(200);
  const payload: unknown = await response.json();
  if (
    !isRecord(payload) ||
    !isRecord(payload.data) ||
    typeof payload.data.state_version !== "number"
  ) {
    throw new Error("방문 상태 변경 응답이 공통 API 구조와 다릅니다.");
  }
  const resource = isRecord(payload.data.resource)
    ? payload.data.resource
    : null;
  return {
    stateVersion: payload.data.state_version,
    visitId:
      resource && typeof resource.visit_id === "string"
        ? resource.visit_id
        : null,
  };
}

async function assertScheduledTechnician(
  response: Response,
  expectedTechnicianId: string,
): Promise<void> {
  expect(response.status()).toBe(200);
  const payload: unknown = await response.json();
  if (!isRecord(payload) || !isRecord(payload.data)) {
    throw new Error("방문 일정 저장 응답이 공통 API 구조와 다릅니다.");
  }
  const resource = payload.data.resource;
  if (!isRecord(resource)) {
    throw new Error("방문 일정 저장 응답에 resource가 없습니다.");
  }
  const schedule = resource.schedule;
  const technician = resource.technician;
  if (!isRecord(schedule) || !isRecord(technician)) {
    throw new Error("방문 일정 저장 응답에 일정 또는 기사 정보가 없습니다.");
  }
  expect(schedule.synthetic_technician_id).toBe(expectedTechnicianId);
  expect(technician.technician_id).toBe(expectedTechnicianId);
}

function futureLocalDate(daysFromToday: number): string {
  const today = new Date();
  const future = new Date(
    today.getFullYear(),
    today.getMonth(),
    today.getDate() + daysFromToday,
  );
  const year = future.getFullYear();
  const month = String(future.getMonth() + 1).padStart(2, "0");
  const day = String(future.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  const visitFixturePath = process.env.E2E_VISIT_FIXTURE_JSON_PATH?.trim();
  if (!visitFixturePath) {
    throw new Error(
      "기사 선택 Smoke에는 별도 E2E_VISIT_FIXTURE_JSON_PATH가 필요합니다.",
    );
  }
  fixture = readBackendFixture(resolve(visitFixturePath));
});

test.beforeEach(async ({ page }) => {
  await installArtifactPrivacyMask(page);
});

test.afterEach(async ({ page }, testInfo) => {
  await attachMaskedFailureScreenshot(page, testInfo);
});

test("별도 공식 Fixture로 Dashboard 합성 기사를 선택해 방문 일정에 저장한다", async (
  { page },
  testInfo,
) => {
  const consultationNote = `E2E 방문 상담 기록 ${fixture.runId}`;
  const customerGuidance = `E2E 방문 안전 안내 ${fixture.runId}`;
  const confirmedSummary = `E2E 방문 필요 확정 ${fixture.runId}`;
  const preferredDate = futureLocalDate(7);

  await loginToFixture(page, fixture);
  const fixtureCard = page.getByTestId(
    `consultant-inquiry-${fixture.inquiryId}`,
  );
  await expect(fixtureCard).toBeVisible();

  const initialDetailResponse = page.waitForResponse((response) =>
    isInquiryDetailResponse(response, fixture.inquiryId),
  );
  await fixtureCard.click();
  expect((await initialDetailResponse).status()).toBe(200);

  const firstDetailPanel = page.getByRole("dialog");
  await expect(firstDetailPanel).toBeVisible();

  const startResponse = page.waitForResponse((response) =>
    isApiResponse(
      response,
      "POST",
      `/api/v1/inquiries/${fixture.inquiryId}/start-consultation`,
    ),
  );
  await firstDetailPanel
    .locator('[data-action-code="START_CONSULTATION"]')
    .click();
  expect((await startResponse).status()).toBe(200);

  await firstDetailPanel
    .getByLabel("상담 기록", { exact: true })
    .fill(consultationNote);
  await firstDetailPanel
    .getByLabel("고객 안내", { exact: true })
    .fill(customerGuidance);
  await firstDetailPanel
    .getByLabel("확정 요약", { exact: true })
    .fill(confirmedSummary);
  await firstDetailPanel
    .getByLabel("방문 필요 여부")
    .selectOption("REQUIRED");
  await firstDetailPanel
    .getByLabel("사용 안내 상태")
    .selectOption("PARTIAL_STOP");
  await firstDetailPanel
    .getByRole("checkbox", { name: "상담 요약 검토·확정" })
    .check();

  const saveResponse = page.waitForResponse((response) =>
    isApiResponse(
      response,
      "PATCH",
      `/api/v1/inquiries/${fixture.inquiryId}/consultation-summary`,
    ),
  );
  await firstDetailPanel
    .locator('[data-action-code="UPDATE_CONSULTATION_SUMMARY"]')
    .click();
  expect((await saveResponse).status()).toBe(200);

  const confirmResponse = page.waitForResponse((response) =>
    isApiResponse(
      response,
      "POST",
      `/api/v1/inquiries/${fixture.inquiryId}/consultation-summary/confirm`,
    ),
  );
  page.once("dialog", (dialog) => void dialog.accept());
  await firstDetailPanel
    .locator('[data-action-code="CONFIRM_CONSULTATION_SUMMARY"]')
    .click();
  expect((await confirmResponse).status()).toBe(200);

  const dashboardResponse = page.waitForResponse((response) =>
    isApiResponse(response, "GET", "/api/v1/consultant/dashboard"),
  );
  await firstDetailPanel
    .locator('[data-action-code="VISIT_REVIEW_REQUIRED"]')
    .click();
  await expect(page).toHaveURL(
    new RegExp(
      `/consultant/inquiries/${fixture.inquiryId}/visit-transition$`,
    ),
  );
  const technicianId = await readDashboardTechnicianId(
    await dashboardResponse,
  );

  await page.getByLabel("방문 사유").fill("현장 누수 점검이 필요합니다.");
  await page
    .getByLabel("기사 전달사항")
    .fill("급수 연결부를 우선 확인해 주세요.");
  await page
    .getByLabel("안전 유의사항")
    .fill("점검 전 급수 밸브를 잠가 주세요.");

  const reviewResponse = page.waitForResponse((response) =>
    isApiResponse(
      response,
      "POST",
      `/api/v1/inquiries/${fixture.inquiryId}/visit-review`,
    ),
  );
  await page
    .getByRole("button", { name: "방문 필요 검토 요청" })
    .click();
  expect((await reviewResponse).status()).toBe(200);

  const createResponse = page.waitForResponse((response) =>
    isApiResponse(
      response,
      "POST",
      `/api/v1/inquiries/${fixture.inquiryId}/visits`,
    ),
  );
  await page.getByRole("button", { name: "방문 생성" }).click();
  const createResult = await readTransitionResult(await createResponse);
  expect(createResult.visitId).not.toBeNull();
  const visitId = createResult.visitId;
  if (!visitId) throw new Error("방문 생성 응답에 visit_id가 없습니다.");

  const technicianSelect = page.getByLabel("방문기사");
  await expect(technicianSelect).toBeEnabled();
  await technicianSelect.selectOption(technicianId);
  await expect(technicianSelect).toHaveValue(technicianId);
  await page.getByLabel("고객 희망일").fill(preferredDate);

  const scheduleRequest = page.waitForRequest((request) =>
    request.method() === "PATCH" &&
    request.url().endsWith(`/api/v1/visits/${visitId}/schedule`),
  );
  const scheduleResponse = page.waitForResponse((response) =>
    isApiResponse(
      response,
      "PATCH",
      `/api/v1/visits/${visitId}/schedule`,
    ),
  );
  await page
    .locator('[data-action-code="UPDATE_VISIT_SCHEDULE"]')
    .click();

  const request = await scheduleRequest;
  const body: unknown = request.postDataJSON();
  expect(body).toEqual({
    state_version: createResult.stateVersion,
    synthetic_technician_id: technicianId,
    preferred_date: preferredDate,
    confirmed_date: null,
  });
  await assertScheduledTechnician(await scheduleResponse, technicianId);

  await attachMaskedEvidenceScreenshot(page, testInfo);
});
