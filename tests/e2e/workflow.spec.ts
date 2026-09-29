import { expect, test } from "../../apps/web/node_modules/@playwright/test";
import { readFileSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";
import AxeBuilder from "../../apps/web/node_modules/@axe-core/playwright";
const root = resolve(process.cwd(), "../..");
test("computed dashboard, evidence review, no default model, export, and audit", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Better data. Better decisions." }),
  ).toBeVisible();
  await expect(page.getByText("1,200", { exact: false })).toBeVisible();
  const summary = await (await page.request.get("/api/v1/overview")).json();
  await expect(
    page.getByText(summary.metrics.quality_score.toFixed(1), { exact: false }),
  ).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    accessibility.violations.map((item) => ({
      id: item.id,
      impact: item.impact,
      nodes: item.nodes.map((node) => node.target),
    })),
  ).toEqual([]);
  mkdirSync(resolve(root, "docs/assets"), { recursive: true });
  await page.screenshot({
    path: resolve(root, "docs/assets/dashboard.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: /Local AI models/ }).click();
  await expect(
    page.getByRole("combobox", { name: "Explanation model" }),
  ).toHaveValue("");
  await page.screenshot({
    path: resolve(root, "docs/assets/local-models.png"),
    fullPage: false,
  });
  await page.getByRole("button", { name: "Close model settings" }).click();
  await page.getByRole("button", { name: "View review queue" }).click();
  await page
    .getByRole("combobox", { name: "Finding category" })
    .selectOption("duplicate");
  await expect(
    page.getByRole("button", { name: "Potential duplicate material" }).first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Potential duplicate material" })
    .first()
    .click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", { name: "Potential duplicate material" }),
  ).toBeVisible();
  await dialog.getByRole("tab", { name: "Raw records" }).click();
  await expect(dialog.getByText("Raw source", { exact: true })).toHaveCount(2);
  await dialog.getByRole("tab", { name: "Detection evidence" }).click();
  await expect(
    dialog.getByRole("combobox", { name: "Explanation model" }),
  ).toHaveValue("");
  await expect(
    dialog.getByRole("button", { name: "Generate explanation" }),
  ).toBeDisabled();
  await page.setViewportSize({ width: 1512, height: 1500 });
  await page.screenshot({
    path: resolve(root, "docs/assets/evidence.png"),
    fullPage: false,
  });
  await page.setViewportSize({ width: 1512, height: 1150 });
  await dialog
    .getByLabel("Review note", { exact: false })
    .fill("Verified supplier specification and source identifiers.");
  await dialog.getByRole("button", { name: "Accept finding" }).click();
  await expect(dialog.getByText("accepted", { exact: true })).toBeVisible();
  await dialog.getByRole("tab", { name: "Review history" }).click();
  await expect(
    dialog
      .locator(".review-history")
      .getByText("Verified supplier specification and source identifiers."),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export", exact: true }).click();
  expect((await downloadPromise).suggestedFilename()).toBe(
    "materialmaster-findings.csv",
  );
  await page
    .getByRole("button", { name: "Activity & audit", exact: true })
    .click();
  await expect(
    page.getByText("finding · reviewed", { exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
test("material search, responsive layout and architecture", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByText("1,200", { exact: false })).toBeVisible();
  await page
    .getByRole("button", { name: "Material explorer", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "Search materials" })
    .fill("MAT-0000010");
  await expect(page.getByText("1–1 of 1", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Architecture & about", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "AI with a clearly defined job." }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await expect(page.getByText("1,200", { exact: false })).toBeVisible();
  await page.screenshot({
    path: resolve(root, "docs/assets/mobile.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
test("import quarantines malformed rows, then scan produces real output", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByText("1,200", { exact: false })).toBeVisible();
  await page
    .getByRole("button", { name: "Import dataset", exact: true })
    .click();
  const sample =
    readFileSync(resolve(root, "data/sample/materials.jsonl"), "utf8")
      .trim()
      .split("\n")
      .slice(0, 80)
      .join("\n") + "\nnot-json\n";
  await page.getByLabel("Material data file").setInputFiles({
    name: "browser-import.jsonl",
    mimeType: "application/x-ndjson",
    buffer: Buffer.from(sample),
  });
  await page.getByRole("button", { name: "Validate & import" }).click();
  await expect(page.getByText("quarantined", { exact: true })).toBeVisible();
  await page.getByText("Inspect rejected rows (first 30)").click();
  await expect(page.getByText(/_invalid_json_line/)).toBeVisible();
  await page.getByRole("button", { name: "Open imported dataset" }).click();
  await page.getByRole("button", { name: "Run quality scan" }).click();
  await expect(page.locator(".kpi-value").first()).toBeVisible();
  await expect(
    page.getByText(
      "Quality scan complete. Evidence and trend snapshot updated.",
    ),
  ).toBeVisible();
});

test("local model selection is explicit, session-only, and sent with the explanation", async ({
  page,
}) => {
  let installed = ["workstation-model:7b"];
  let inventoryStatus = "ready";
  let holdNext = false;
  let release: (() => void) | undefined;
  const requests: { runtime: string; model: string }[] = [];
  await page.route("**/api/v1/ai/models", (route) =>
    route.fulfill({
      json: {
        runtime: "ollama",
        status: inventoryStatus,
        models: installed.map((id) => ({
          id,
          parameter_size: "7B",
          quantization: "Q4_K_M",
        })),
        message:
          inventoryStatus === "unavailable"
            ? "Could not read the local runtime."
            : "Choose a model explicitly.",
      },
    }),
  );
  await page.route("**/api/v1/commands/findings/*/explain", async (route) => {
    const choice = route.request().postDataJSON();
    requests.push(choice);
    const id = route.request().url().split("/").at(-2);
    const finding = await (
      await page.request.get(`/api/v1/findings/${id}`)
    ).json();
    if (holdNext)
      await new Promise<void>((resolve) => {
        release = resolve;
      });
    await route.fulfill({
      json: {
        result: {
          explanation: {
            status: "explained",
            summary: "Fixture explanation with supplied evidence.",
            evidence_ids: finding.material_ids,
            normalization_suggestions: [],
            limitations: [],
          },
          telemetry: { model: choice.model },
        },
      },
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: /Local AI models/ }).click();
  const settings = page.getByRole("dialog");
  const picker = settings.getByRole("combobox", { name: "Explanation model" });
  await expect(picker).toBeEnabled();
  await expect(picker).toHaveValue(""); // Even one installed model has no default.
  await picker.selectOption("workstation-model:7b");
  await expect(
    settings.getByText("Selected for this session.", { exact: false }),
  ).toBeVisible();
  expect(requests).toEqual([]); // Selecting a model does not perform inference.
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
  await settings.getByRole("button", { name: "Close model settings" }).click();
  await page.getByRole("button", { name: "View review queue" }).click();
  await page
    .getByRole("button", { name: "Potential duplicate material" })
    .first()
    .click();
  const evidence = page.getByRole("dialog");
  await expect(
    evidence.getByRole("combobox", { name: "Explanation model" }),
  ).toHaveValue("workstation-model:7b");
  await evidence.getByRole("button", { name: "Generate explanation" }).click();
  await expect(
    evidence.getByText("Fixture explanation with supplied evidence."),
  ).toBeVisible();
  expect(requests).toEqual([
    { runtime: "ollama", model: "workstation-model:7b" },
  ]);
  await expect(
    evidence.getByText("Generated by", { exact: false }),
  ).toContainText("workstation-model:7b");
  installed = ["another-local-model:8b"];
  await evidence.getByRole("button", { name: "Refresh local models" }).click();
  await expect(
    evidence.getByRole("combobox", { name: "Explanation model" }),
  ).toHaveValue("");
  await expect(
    evidence.getByRole("button", { name: "Generate explanation" }),
  ).toBeDisabled();
  await evidence
    .getByRole("combobox", { name: "Explanation model" })
    .selectOption("another-local-model:8b");
  await evidence.getByRole("button", { name: "Generate explanation" }).click();
  await expect(
    evidence.getByText("Generated by", { exact: false }),
  ).toContainText("another-local-model:8b");
  expect(requests[1].model).toBe("another-local-model:8b");
  holdNext = true;
  await evidence.getByRole("button", { name: "Generate explanation" }).click();
  await expect.poll(() => Boolean(release)).toBe(true);
  await page.keyboard.press("Escape");
  await page
    .getByRole("button", { name: "Potential duplicate material" })
    .nth(1)
    .click();
  await expect(
    evidence.getByText("Fixture explanation with supplied evidence."),
  ).toHaveCount(0);
  release?.();
  await expect(
    evidence.getByRole("button", { name: "Generate explanation" }),
  ).toBeEnabled();
  await expect(
    evidence.getByText("Fixture explanation with supplied evidence."),
  ).toHaveCount(0);
  await page.reload();
  await page.getByRole("button", { name: /Local AI models/ }).click();
  await expect(
    page.getByRole("combobox", { name: "Explanation model" }),
  ).toHaveValue("");
  inventoryStatus = "unavailable";
  installed = [];
  await page.getByRole("button", { name: "Refresh local models" }).click();
  await expect(
    page.getByRole("combobox", { name: "Explanation model" }),
  ).toBeDisabled();
  await expect(
    page.getByText("Could not read the local runtime."),
  ).toBeVisible();
});

test("workplace source guidance is accessible from import", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Import dataset", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByText("data/sample/import-template.csv", { exact: false }),
  ).toBeVisible();
  await dialog
    .getByRole("button", { name: "Where does workplace data come from?" })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Start with the records you already own.",
    }),
  ).toBeVisible();
  await expect(
    page.getByText("This version has no direct ERP connectors or writeback.", {
      exact: false,
    }),
  ).toBeVisible();
});
