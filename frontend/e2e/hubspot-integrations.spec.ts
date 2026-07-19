import { test, expect } from "@playwright/test";

const DEV_TENANT_ID = "00000000-0000-0000-0000-000000000002";

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
    await page.context().addCookies([{ name, value, domain: "localhost", path: "/" }]);
  }
});

test("integrations page shows not connected and links to the real authorize endpoint", async ({
  page,
  request,
}) => {
  await page.goto("/settings/integrations");

  await expect(page.getByTestId("hubspot-status")).toHaveText("Not connected");

  const connectButton = page.getByTestId("hubspot-connect-button");
  await expect(connectButton).toBeVisible();
  await expect(connectButton).toHaveAttribute(
    "href",
    "http://localhost:8000/api/v1/oauth/hubspot/authorize"
  );

  // Confirm the authorize endpoint itself, when hit directly with this
  // tenant's session cookie, issues a real redirect to HubSpot — proves
  // the browser -> FastAPI -> HubSpot leg works without needing live
  // HubSpot credentials or completing the consent screen.
  const cookies = await page.context().cookies();
  const sessionCookie = cookies.find((c) => c.name === "meridian_session");
  const authorizeResponse = await request.get(
    "http://localhost:8000/api/v1/oauth/hubspot/authorize",
    {
      headers: { Cookie: `meridian_session=${sessionCookie?.value}` },
      maxRedirects: 0,
    }
  );
  expect(authorizeResponse.status()).toBe(307);
  expect(authorizeResponse.headers()["location"]).toContain("https://app.hubspot.com/oauth/authorize");
});

test("callback banner shows an error for an invalid state param", async ({ page }) => {
  await page.goto("/settings/integrations?error=invalid_state");

  await expect(page.getByTestId("hubspot-callback-banner")).toBeVisible();
  await expect(page.getByTestId("hubspot-callback-banner")).toContainText("Connection failed");
});

test("callback banner shows success for a connected param", async ({ page }) => {
  await page.goto("/settings/integrations?connected=1");

  await expect(page.getByTestId("hubspot-callback-banner")).toBeVisible();
  await expect(page.getByTestId("hubspot-callback-banner")).toContainText("connected successfully");
});
