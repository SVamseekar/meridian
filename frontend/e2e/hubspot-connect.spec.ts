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

test("display hubspot settings page status and connect button", async ({ page }) => {
  await page.goto("/settings/hubspot");

  await expect(page.getByTestId("connection-status")).toBeVisible();

  const connectButton = page.getByTestId("connect-button");
  if (await connectButton.isVisible()) {
    await expect(connectButton).toBeEnabled();
    await expect(connectButton).toHaveText("Connect HubSpot");
  } else {
    const disconnectButton = page.getByTestId("disconnect-button");
    await expect(disconnectButton).toBeVisible();
  }
});
