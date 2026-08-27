import { expect, type Page } from "@playwright/test";

import type { WebConsultationE2EFixture } from "./backendFixture.js";

function readConsultantPassword(): string {
  const password = process.env.E2E_CONSULTANT_PASSWORD;
  if (!password) {
    throw new Error(
      "E2E_LOGIN_BLOCKED: E2E_CONSULTANT_PASSWORD를 안전한 실행 환경에 입력해 주세요.",
    );
  }
  return password;
}

export async function loginToConsultantFixture(
  page: Page,
  fixture: WebConsultationE2EFixture,
): Promise<void> {
  const listPath = `/consultant/inquiries?bucket=NEW&q=${encodeURIComponent(fixture.inquiryCode)}`;
  await page.goto(listPath);
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("사번").fill(fixture.assignedConsultant);
  await page.getByLabel("비밀번호").fill(readConsultantPassword());
  await page
    .getByRole("button", { name: "사번/비밀번호로 로그인" })
    .click();
  await expect(page).toHaveURL((url) => {
    return (
      url.pathname === "/consultant/inquiries" &&
      url.searchParams.get("bucket") === "NEW" &&
      url.searchParams.get("q") === fixture.inquiryCode
    );
  });
}
