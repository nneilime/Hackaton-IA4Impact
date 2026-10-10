import { test, expect } from "@playwright/test";
import { sharedApi, login } from "./shared-api";

test("arbitrage direction : comparaison marché groupé vs au fil de l'eau et seuil de rentabilité", async ({
  page,
}) => {
  await sharedApi(page);
  await login(page);
  await page.goto("/economies");
  await expect(
    page.getByRole("heading", {
      name: "Préparer les dépenses, comparer les options.",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Remplacement à l’unité ou Rénovation globale groupée ?",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Au fil de l’eau (Cas par cas)" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Remplacement groupé (Marché unique)" }),
  ).toBeVisible();
  await expect(page.getByText("Gain financier net")).toBeVisible();
  await expect(page.getByText("Seuil de bascule atteint")).toBeVisible();
  await expect(page.getByText("Programmer en 2026")).toBeVisible();
  await page.screenshot({
    path: "../.cache/qa/economics-desktop.png",
    animations: "disabled",
  });
});

test("scénario explicite et repères économiques sur mobile", async ({
  page,
}) => {
  await sharedApi(page);
  await login(page);
  await page.goto("/economies");
  await expect(
    page.getByText(
      "Renseignez les quatre hypothèses pour comparer le scénario.",
    ),
  ).toBeVisible();
  await page.getByLabel("Coût supplémentaire du contrôle (€ TTC)").fill("100");
  await page.getByLabel("Probabilité de panne supposée (%)").fill("20");
  await page
    .getByLabel("Part des pannes évitables par ce contrôle (%)")
    .fill("50");
  await page
    .getByLabel("Dépense réellement évitable par panne (€ TTC)")
    .fill("2000");
  await expect(page.locator(".economic-scenario-result > strong")).toHaveText(
    /100/,
  );
  await page
    .getByLabel("Part des pannes évitables par ce contrôle (%)")
    .fill("0");
  await expect(page.locator(".economic-scenario-result > strong")).toHaveText(
    /-100/,
  );
  await page.getByLabel("Horizon des contrôles").selectOption("180");
  await expect(
    page.getByRole("heading", {
      name: "Tester un scénario de prévention · 180 jours",
    }),
  ).toBeVisible();
  await expect(
    page.getByLabel("Coût supplémentaire du contrôle (€ TTC)"),
  ).toHaveValue("");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({
    path: "../.cache/qa/economics-mobile.png",
    animations: "disabled",
  });
  await page.goto("/equipements/EQP-01533");
  await expect(
    page.getByRole("heading", { name: "Réparer ou remplacer : les repères" }),
  ).not.toBeVisible();
  await expect(page.getByRole("heading", { name: "Carte d’identité" })).toBeVisible();
});
