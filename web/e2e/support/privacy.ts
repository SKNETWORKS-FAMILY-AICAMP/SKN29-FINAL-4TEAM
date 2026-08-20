import type { Page, TestInfo } from "@playwright/test";

const PRIVACY_STYLE = `
  [data-e2e-sensitive="true"],
  [data-e2e-sensitive="true"] *,
  input,
  textarea {
    color: transparent !important;
    text-shadow: none !important;
  }
  [data-e2e-sensitive="true"],
  input,
  textarea {
    filter: blur(9px) !important;
  }
  input,
  textarea {
    caret-color: transparent !important;
  }
`;

export async function installArtifactPrivacyMask(page: Page): Promise<void> {
  await page.addInitScript((styleText) => {
    const install = () => {
      if (!document.head || document.getElementById("e2e-privacy-mask")) return;
      const style = document.createElement("style");
      style.id = "e2e-privacy-mask";
      style.textContent = styleText;
      document.head.append(style);
    };
    const observer = new MutationObserver(() => {
      install();
      if (document.getElementById("e2e-privacy-mask")) observer.disconnect();
    });
    observer.observe(document, { childList: true, subtree: true });
    install();
    document.addEventListener("DOMContentLoaded", install, { once: true });
  }, PRIVACY_STYLE);
}

export async function attachMaskedFailureScreenshot(
  page: Page,
  testInfo: TestInfo,
): Promise<void> {
  if (testInfo.status === testInfo.expectedStatus || page.isClosed()) return;
  const screenshotPath = testInfo.outputPath("failure-screenshot.png");
  await page.screenshot({
    path: screenshotPath,
    fullPage: true,
    mask: [
      page.locator(
        '[data-e2e-sensitive="true"], input, textarea, .consultant-user-menu',
      ),
    ],
  });
  await testInfo.attach("failure-screenshot", {
    path: screenshotPath,
    contentType: "image/png",
  });
}
