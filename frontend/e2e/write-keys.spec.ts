import { test, expect } from "@playwright/test";

test("generate, view once, and revoke a write key", async ({ page, request }) => {
  await page.goto("/settings/write-keys");

  await expect(page.getByTestId("tenant-label")).toBeVisible();

  await page.getByRole("button", { name: "Generate new key" }).click();

  const reveal = page.getByTestId("write-key-reveal");
  await expect(reveal).toBeVisible();
  const revealedKey = await page.getByTestId("revealed-key").innerText();
  expect(revealedKey).toMatch(/^wk_live_/);

  await page.getByRole("button", { name: "I've saved it" }).click();
  await expect(reveal).not.toBeVisible();

  const row = page.getByTestId("write-key-row").first();
  await expect(row).toBeVisible();
  await expect(row).not.toContainText(revealedKey);

  // Confirm the key works against the real API before revoking.
  const preRevokeResponse = await request.post("http://localhost:8000/api/v1/telemetry/event", {
    headers: { Authorization: `Bearer ${revealedKey}` },
    data: {
      anonymous_id: "e2e-test",
      event_name: "e2e_test_event",
      properties: {},
      client_timestamp: new Date().toISOString(),
    },
  });
  expect(preRevokeResponse.status()).toBe(202);

  page.on("dialog", (dialog) => dialog.accept());
  await row.getByRole("button", { name: "Revoke" }).click();
  await expect(row).toContainText("Revoked");

  const postRevokeResponse = await request.post("http://localhost:8000/api/v1/telemetry/event", {
    headers: { Authorization: `Bearer ${revealedKey}` },
    data: {
      anonymous_id: "e2e-test",
      event_name: "e2e_test_event",
      properties: {},
      client_timestamp: new Date().toISOString(),
    },
  });
  expect(postRevokeResponse.status()).toBe(401);
});
