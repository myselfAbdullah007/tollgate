import { test, expect } from "@playwright/test";

let loginCookies: Awaited<
  ReturnType<import("@playwright/test").BrowserContext["cookies"]>
> = [];
test.beforeAll(async ({ browser, baseURL }) => {
  const page = await browser.newPage({ baseURL });
  await page.goto("/login");
  await page.getByRole("button", { name: "Use demo credentials" }).click();
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Connecting to your workspace…")).toBeHidden();
  loginCookies = await page.context().cookies();
  await page.close();
});
test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "ignoreErrors" });
});

test.beforeEach(async ({ page, context }) => {
  await context.addCookies(loginCookies);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Connecting to your workspace…")).toBeHidden();
});

test("sidebar footer stays reachable at short desktop and mobile heights", async ({
  page,
}) => {
  for (const size of [
    { width: 1280, height: 720 },
    { width: 1024, height: 600 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(size);
    if (size.width < 760)
      await page.getByRole("button", { name: "Open navigation" }).click();
    const bounds = await page
      .getByRole("button", { name: "Sign out", exact: true })
      .boundingBox();
    expect(bounds).not.toBeNull();
    expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(size.height);
    if (size.width < 760) {
      await page.keyboard.press("Escape");
      await expect(page.locator(".sidebar")).not.toHaveClass(/is-open/);
    }
  }
});

test("plan editor round trip preserves all privacy categories and degradation steps", async ({
  page,
}) => {
  let original: Record<string, unknown> = {},
    submitted: Record<string, unknown> = {};
  await page.route("**/api/admin/v1/tenants/default/plans", async (route) => {
    const response = await route.fetch();
    const rows = await response.json();
    const p = rows.find((r: { name: string }) => r.name === "Pro");
    p.pii_block_categories = ["CARD", "EMAIL", "SECRET"];
    p.degradation = [
      { at: 0.6, tier: 1 },
      { at: 0.8, tier: 2 },
      { at: 0.95, tier: 3 },
    ];
    original = structuredClone(p);
    await route.fulfill({ response, json: rows });
  });
  await page.route("**/api/admin/v1/tenants/default/plans/*", async (route) => {
    if (route.request().method() === "PATCH") {
      submitted = route.request().postDataJSON();
      await route.fulfill({ json: { ...original, ...submitted } });
    } else await route.continue();
  });
  await page.goto("/plans");
  await expect(page.getByText("Connecting to your workspace…")).toBeHidden();
  await page
    .locator(".plan-card")
    .filter({ has: page.getByRole("heading", { name: "Pro", exact: true }) })
    .getByRole("button", { name: "Edit plan" })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Save changes" })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(submitted.pii_block_categories).toEqual(original.pii_block_categories);
  expect(submitted.degradation).toEqual(original.degradation);
  expect(submitted.revision).toEqual(original.revision);
});

test("switching workspaces resets the settings form and preserves navigation scope", async ({
  page,
}) => {
  await page.route("**/api/admin/v1/tenants", async (route) => {
    const response = await route.fetch();
    const rows = await response.json();
    rows.push({
      id: "fixture",
      name: "other",
      display_name: "Other workspace",
      rpm: 321,
      default_plan: "Free",
    });
    await route.fulfill({ response, json: rows });
  });
  await page.route("**/api/admin/v1/tenants/other/**", async (route) => {
    expect(route.request().method()).toBe("GET");
    const response = await route.fetch({
      url: route
        .request()
        .url()
        .replace("/tenants/other/", "/tenants/default/"),
    });
    await route.fulfill({ response });
  });
  await page.goto("/settings");
  await expect(page.getByText("Connecting to your workspace…")).toBeHidden();
  await page.locator(".workspace-switch").click();
  await page
    .locator(".workspace-menu")
    .getByRole("button", { name: "Other workspace" })
    .click();
  await expect(
    page.getByRole("textbox", { name: "Workspace name", exact: true }),
  ).toHaveValue("Other workspace");
  await expect(
    page.getByRole("spinbutton", { name: "Workspace requests per minute" }),
  ).toHaveValue("321");
  const link = page
    .getByRole("navigation")
    .getByRole("link", { name: "Customers" });
  await expect(link).toHaveAttribute("href", /workspace=other/);
});

test("request date range reaches the API and customer context is retained", async ({
  page,
}) => {
  await page.goto("/logs");
  await expect(page.getByText("Connecting to your workspace…")).toBeHidden();
  const promise = page.waitForRequest(
    (r) =>
      r.url().includes("/tenants/default/logs?") && r.url().includes("days=7"),
  );
  await page.getByRole("combobox", { name: "Date range" }).selectOption("7");
  await promise;
  const response = await page.request.get(
    "/api/admin/v1/tenants/default/customers",
  );
  const customer = (await response.json())[0];
  await page.goto(`/customers/${customer.id}`);
  await expect(page.getByText("Connecting to your workspace…")).toBeHidden();
  await expect(
    page.getByRole("link", { name: "Open request logs" }),
  ).toHaveAttribute("href", new RegExp(`customer=${customer.name}`));
});

test("insights exposes actual routing and feature cost, settings expose secure operations", async ({
  page,
}) => {
  await page.goto("/insights");
  await expect(
    page.getByRole("heading", { name: "Cost by feature" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Budget and routing events" }),
  ).toBeVisible();
  await page.goto("/settings");
  await expect(
    page.getByRole("heading", { name: "Signed budget webhooks" }),
  ).toBeVisible();
  await expect(
    page.getByRole("checkbox", { name: "Enable signed event delivery" }),
  ).not.toBeChecked();
  await expect(
    page.getByRole("heading", { name: "Your sessions" }),
  ).toBeVisible();
});

test("a superseding refresh does not turn a persisted customer save into an error", async ({
  page,
}) => {
  await page.goto("/customers");
  await expect(page.getByText("Connecting to your workspace…")).toBeHidden();
  await page.getByRole("button", { name: "Edit Acme Inc." }).click();
  const budget = page.getByRole("spinbutton", {
    name: "Custom monthly budget (USD)",
  });
  const original = await budget.inputValue();
  await budget.fill("81");
  let holdReads = false;
  await page.route(
    "**/api/admin/v1/tenants/default/customers",
    async (route) => {
      if (holdReads && route.request().method() === "GET") {
        await new Promise((resolve) => setTimeout(resolve, 700));
      }
      await route.continue();
    },
  );
  holdReads = true;
  const written = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().includes("/customers/"),
  );
  await page.getByRole("button", { name: "Save changes" }).click();
  expect((await written).ok()).toBeTruthy();
  // Refresh is a distinct read. It can supersede the save's read after the write commits.
  await page.locator(".table-search input").fill("Acme", { force: true });
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("status")).toContainText("Changes saved");
  await expect(page.locator("tbody")).toContainText("$81");
  holdReads = false;
  await page.getByRole("button", { name: "Edit Acme Inc." }).click();
  await page
    .getByRole("spinbutton", { name: "Custom monthly budget (USD)" })
    .fill(original);
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("a failed refresh reports a warning without replaying a successful save", async ({ page }) => {
  await page.goto("/customers");
  await expect(page.getByText("Connecting to your workspace…")).toBeHidden();
  const endpoint = "/api/admin/v1/tenants/default/customers";
  const original = (await (await page.request.get(endpoint)).json()).find(
    (customer: { name: string }) => customer.name === "cus_acme",
  );
  let writes = 0;
  page.on("request", (request) => {
    if (request.method() === "PATCH" && request.url().includes("/customers/")) writes++;
  });
  try {
    await page.getByRole("button", { name: "Edit Acme Inc." }).click();
    await page.getByRole("spinbutton", { name: "Custom monthly budget (USD)" }).fill("82");
    await page.route("**/api/admin/v1/tenants/default/keys", (route) =>
      route.fulfill({ status: 500, contentType: "text/plain", body: "Internal Server Error" }),
    );
    await page.getByRole("button", { name: "Save changes" }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page.getByRole("status")).toContainText("Changes saved");
    await expect(page.locator(".error-banner")).toContainText("Changes were saved, but the workspace could not refresh");
    const persisted = (await (await page.request.get(endpoint)).json()).find(
      (customer: { name: string }) => customer.name === "cus_acme",
    );
    expect(persisted.budget_override).toBe(82_000_000);
    expect(writes).toBe(1);
  } finally {
    await page.unrouteAll({ behavior: "ignoreErrors" });
    const current = (await (await page.request.get(endpoint)).json()).find(
      (customer: { name: string }) => customer.name === "cus_acme",
    );
    const restored = await page.request.patch(`${endpoint}/${original.id}`, {
      headers: { "X-Tollgate-Admin": "1" },
      data: { ...original, revision: current.revision },
    });
    expect(restored.ok()).toBeTruthy();
  }
});

test("a non-JSON write failure remains a readable form error", async ({ page }) => {
  await page.goto("/customers");
  await expect(page.getByText("Connecting to your workspace…")).toBeHidden();
  await page.getByRole("button", { name: "Edit Acme Inc." }).click();
  await page.route("**/api/admin/v1/tenants/default/customers/*", async (route) => {
    if (route.request().method() === "PATCH") {
      await route.fulfill({ status: 500, contentType: "text/plain", body: "Internal Server Error" });
    } else await route.continue();
  });
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(1);
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText("HTTP 500");
  await expect(page.getByRole("dialog").getByRole("alert")).not.toContainText("Unexpected token");
});
