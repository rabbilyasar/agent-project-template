import { test, expect } from "@playwright/test";

// Hidden Playwright spec for bench/tasks/browser-ui.md. Not shown to the
// agent during the trial; copied in only by harness/lib/06_validate.sh.
test("submit button is disabled while the request is in flight", async ({ page }) => {
  await page.goto("/");
  await page.fill("#client-id", "client-a");
  const button = page.locator("#submit-button");
  await button.click();
  await expect(button).toBeDisabled();
  await expect(button).toBeEnabled({ timeout: 5000 });
});
