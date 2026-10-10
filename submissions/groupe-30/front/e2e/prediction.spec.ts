import { test, expect } from "@playwright/test";
import { sharedApi, login } from "./shared-api";

test("fiche : appel API, symptômes, coûts et changement d’horizon", async ({
  page,
}) => {
  await sharedApi(page);
  const bodies: unknown[] = [];
  await page.route("**/api/predict", async (route) => {
    expect(route.request().headers().authorization).toBe("Bearer test-token");
    bodies.push(route.request().postDataJSON());
    await route.fulfill({
      json: Object.fromEntries(
        [90, 180, 365, 730].map((h) => [
          `failure_types_${h}d`,
          {
            status: "available",
            predictions: [
              {
                type_intervention: "Dépannage",
                type_panne: `Fuite à ${h} jours`,
                conditional_probability: 0.5,
                joint_probability: 0.2,
                prix: 100,
              },
              {
                type_intervention: "Dépannage",
                type_panne: `Anomalie à ${h} jours`,
                conditional_probability: 0.3,
                joint_probability: 0.12,
                prix: 300,
              },
              {
                type_intervention: "Dépannage",
                type_panne: `Arrêt à ${h} jours`,
                conditional_probability: 0.1,
                joint_probability: 0.04,
                prix: 400,
              },
            ],
            other_conditional_probability: 0.1,
            expected_price_if_failure: 200,
            expected_cost_within_horizon: h,
          },
        ]),
      ),
    });
  });
  await login(page);
  await page.goto("/equipements/EQP-01533");
  await expect(
    page
      .locator(".prediction-candidates")
      .getByText("Fuite à 90 jours", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Score conditionnel : 50 %")).not.toBeVisible();
  await page
    .getByText("Comprendre le résultat du modèle", { exact: true })
    .click();
  await expect(page.getByText("Score conditionnel : 50 %")).toBeVisible();
  expect(bodies).toContainEqual({
    equipment_id: "EQP-01533",
    as_of_date: "2026-01-01",
  });
  await expect(
    page.getByText(/Scores non calibrés. Prix fictifs/),
  ).toBeVisible();
  await page
    .locator(".prediction-card")
    .screenshot({
      path: "../.cache/qa/prediction-card.png",
      animations: "disabled",
    });
  await page.getByRole("button", { name: "Données", exact: true }).click();
  await page.getByLabel("Horizon", { exact: true }).selectOption("730");
  await page
    .getByRole("button", { name: "Fermer", exact: true })
    .last()
    .click();
  await expect(
    page
      .locator(".prediction-candidates")
      .getByText("Fuite à 730 jours", { exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("fiche : panne de prédiction et relance explicite", async ({ page }) => {
  await sharedApi(page);
  let fail = true;
  await page.route("**/api/predict", async (route) => {
    if (fail)
      return route.fulfill({
        status: 503,
        json: { detail: "Modèles indisponibles" },
      });
    await route.fallback();
  });
  await login(page);
  await page.goto("/equipements/EQP-01533");
  await expect(
    page.getByRole("alert").filter({ hasText: "Modèles indisponibles" }),
  ).toBeVisible();
  fail = false;
  await page.getByRole("button", { name: "Réessayer la prédiction" }).click();
  await expect(
    page.getByText(
      "Le modèle de symptômes n’est pas disponible pour cette famille et cet horizon.",
    ),
  ).toBeVisible();
});
