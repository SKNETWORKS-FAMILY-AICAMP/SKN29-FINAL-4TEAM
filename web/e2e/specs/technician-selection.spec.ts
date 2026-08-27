import { resolve } from "node:path";

import {
  expect,
  test,
  type Locator,
  type Response,
} from "@playwright/test";

import {
  readBackendFixture,
  type WebConsultationE2EFixture,
} from "../support/backendFixture.js";
import { loginToConsultantFixture } from "../support/consultantPasswordLogin.js";
import {
  attachMaskedEvidenceScreenshot,
  attachMaskedFailureScreenshot,
  installArtifactPrivacyMask,
} from "../support/privacy.js";

let fixture: WebConsultationE2EFixture;

const VISIT_SCHEDULE_STATUS_LABELS: Readonly<Record<string, string>> = {
  ASSIGNING: "기사 배정 중",
  SCHEDULING: "일정 조율 중",
  CONFIRMED: "방문 일정 확정",
  IN_PROGRESS: "방문 진행 중",
  COMPLETED: "방문 완료",
  FOLLOW_UP_REQUIRED: "추가 방문 필요",
  CANCELLED: "방문 취소",
};

interface VisitDetailPresentation {
  scheduleStatusLabel: string;
  preferredDate: string;
  technicianDisplayName: string;
}

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

function formatContractDate(value: string): string {
  const matched = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!matched) {
    throw new Error("방문 상세의 고객 희망일 형식이 올바르지 않습니다.");
  }
  return `${Number(matched[1])}. ${Number(matched[2])}. ${Number(matched[3])}.`;
}

async function readVisitDetailPresentation(
  response: Response,
  expected: {
    inquiryId: string;
    preferredDate: string;
    technicianId: string;
  },
): Promise<VisitDetailPresentation> {
  expect(response.status()).toBe(200);
  const payload: unknown = await response.json();
  if (
    !isRecord(payload) ||
    !isRecord(payload.data) ||
    !isRecord(payload.data.visit)
  ) {
    throw new Error("방문 생성 후 상담 통합 상세 Projection이 올바르지 않습니다.");
  }

  const visit = payload.data.visit;
  if (!isRecord(visit.schedule) || !isRecord(visit.technician)) {
    throw new Error("방문 생성 후 상담 통합 상세 Projection이 올바르지 않습니다.");
  }
  const schedule = visit.schedule;
  const technician = visit.technician;
  if (
    visit.inquiry_id !== expected.inquiryId ||
    schedule.preferred_date !== expected.preferredDate ||
    schedule.synthetic_technician_id !== expected.technicianId ||
    typeof schedule.schedule_status !== "string" ||
    !(schedule.schedule_status in VISIT_SCHEDULE_STATUS_LABELS) ||
    technician.technician_id !== expected.technicianId ||
    typeof technician.display_name !== "string" ||
    technician.display_name.trim().length === 0
  ) {
    throw new Error("방문 일정·담당 기사 상세가 저장 결과와 일치하지 않습니다.");
  }

  return {
    scheduleStatusLabel:
      VISIT_SCHEDULE_STATUS_LABELS[schedule.schedule_status],
    preferredDate: schedule.preferred_date,
    technicianDisplayName: technician.display_name,
  };
}

async function expectVisitDetailPresentation(
  detailPanel: Locator,
  expected: VisitDetailPresentation,
): Promise<void> {
  const consultationAndVisitSection = detailPanel
    .getByRole("heading", { name: "방문 정보", exact: true })
    .locator("..");
  await expect(
    consultationAndVisitSection.getByText("방문 정보 등록됨", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    consultationAndVisitSection.getByText(expected.scheduleStatusLabel, {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    consultationAndVisitSection.getByText(
      formatContractDate(expected.preferredDate),
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    consultationAndVisitSection.getByText(expected.technicianDisplayName, {
      exact: true,
    }),
  ).toBeVisible();
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

  await loginToConsultantFixture(page, fixture);
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
    .getByLabel("고객 안내 내용", { exact: true })
    .fill(customerGuidance);
  await firstDetailPanel
    .getByLabel("상담 요약 수정본", { exact: true })
    .fill(confirmedSummary);
  await firstDetailPanel
    .getByLabel("방문 필요 여부")
    .selectOption("REQUIRED");
  await firstDetailPanel
    .getByLabel("제품 사용 상태")
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

  await page.goto(
    `/consultant/inquiries?bucket=IN_PROGRESS&q=${encodeURIComponent(fixture.inquiryCode)}`,
  );
  const scheduledFixtureCard = page.getByTestId(
    `consultant-inquiry-${fixture.inquiryId}`,
  );
  await expect(scheduledFixtureCard).toBeVisible();
  const scheduledDetailResponse = page.waitForResponse((response) =>
    isInquiryDetailResponse(response, fixture.inquiryId),
  );
  await scheduledFixtureCard.click();
  const scheduledDetailPanel = page.getByRole("dialog");
  await expect(scheduledDetailPanel).toBeVisible();
  const visitDetailPresentation = await readVisitDetailPresentation(
    await scheduledDetailResponse,
    {
      inquiryId: fixture.inquiryId,
      preferredDate,
      technicianId,
    },
  );
  await expectVisitDetailPresentation(
    scheduledDetailPanel,
    visitDetailPresentation,
  );

  await attachMaskedEvidenceScreenshot(page, testInfo);
});
