import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const violations = async (page: import("@playwright/test").Page) =>
  (await new AxeBuilder({ page }).withTags(TAGS).analyze()).violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(" | ")}`);

test("loads with one h1, six sections and no console errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto("/");
  await expect(page).toHaveTitle(/GCC Market Report/);
  await expect(page.locator("h1")).toHaveCount(1);
  await expect(page.locator("h1")).toContainText("Sitagliptin");
  for (const id of ["competition", "prices", "reference", "changes", "quality", "method"]) await expect(page.locator(`#${id}`)).toHaveCount(1);
  expect(errors).toEqual([]);
});

test("the country switch changes the competition chart", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#competition h3")).toContainText("Saudi Arabia");
  await expect(page.locator("#competition svg[role=img]")).toHaveAttribute("aria-label", /Sitagliptin, 80 versions, cheapest −52%/);
  await page.getByRole("group", { name: "Country" }).getByRole("button", { name: "Bahrain" }).click();
  await expect(page.locator("#competition h3")).toContainText("Bahrain");
  await expect(page.locator("#competition svg[role=img]")).toHaveAttribute("aria-label", /Sitagliptin, 31 versions, cheapest −26%/);
});

test("every chart has a table behind it with the published counts", async ({ page }) => {
  await page.goto("/");
  await page.locator("#competition").getByRole("button", { name: "Table", exact: true }).click();
  await expect(page.locator("#competition table tbody tr")).toHaveCount(31);
  await page.locator("#prices").getByRole("button", { name: "Table", exact: true }).click();
  await expect(page.locator("#prices table tbody tr")).toHaveCount(26);
  await page.locator("#reference").getByRole("button", { name: "Table", exact: true }).click();
  await expect(page.locator("#reference table tbody tr")).toHaveCount(8);
  await expect(page.locator("#changes table tbody tr")).toHaveCount(20);
  await expect(page.locator("#quality .qrow")).toHaveCount(22);
});

test("the Excel pack downloads", async ({ page, request }) => {
  await page.goto("/");
  const href = await page.getByRole("link", { name: /Download the Excel pack/ }).getAttribute("href");
  const res = await request.get(href!);
  expect(res.status()).toBe(200);
  expect((await res.body()).subarray(0, 2).toString()).toBe("PK");
});

for (const scheme of ["light", "dark"] as const) {
  test(`axe finds no violations (${scheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await page.goto("/");
    expect(await violations(page)).toEqual([]);
  });
}

for (const width of [390, 320]) {
  test(`no sideways scroll at ${width} px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    await page.goto("/");
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
  });
}
