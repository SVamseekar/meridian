import { test, expect } from "@playwright/test";

const DEV_TENANT_ID = "00000000-0000-0000-0000-000000000001";

test.beforeEach(async ({ page, request }) => {
  const response = await request.post("http://localhost:8000/api/v1/session", {
    data: {
      tenant_id: DEV_TENANT_ID,
      dev_secret: process.env.SESSION_DEV_SECRET ?? "dev-bootstrap-secret-change-me",
    },
  });
  expect(response.status()).toBe(204);
  const cookies = response.headers()["set-cookie"];
  const sessionCookie = cookies?.match(/meridian_session=[^;]+/)?.[0];
  if (sessionCookie) {
    const [name, value] = sessionCookie.split("=");
    await page.context().addCookies([
      {
        name,
        value,
        domain: "localhost",
        path: "/",
      },
    ]);
  }
});

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
