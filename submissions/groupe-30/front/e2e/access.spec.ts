import { test, expect } from "@playwright/test";
import { sharedApi, login } from "./shared-api";

test("connexion obligatoire, imports masqués aux membres et déconnexion", async ({
  page,
}) => {
  await sharedApi(page, "membre");
  await page.goto("/examiner");
  await expect(
    page.getByRole("heading", { name: "Votre espace BâtIA" }),
  ).toBeVisible();
  await login(page);
  await page.getByRole("button", { name: "Données", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Importer des CSV", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Fermer", exact: true })
    .last()
    .click();
  await page
    .getByRole("button", { name: "Se déconnecter", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Votre espace BâtIA" }),
  ).toBeVisible();
});

test("panne API visible, récupération après nouvelle tentative", async ({
  page,
}) => {
  const server = await sharedApi(page);
  server.setUnavailable(true);
  await page.goto("/");
  await page.getByLabel("Courriel", { exact: true }).fill("qa@example.invalid");
  await page.getByLabel("Mot de passe", { exact: true }).fill("test");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Le patrimoine n’est pas disponible" }),
  ).toBeVisible();
  server.setUnavailable(false);
  await page.getByRole("button", { name: "Réessayer", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Données", exact: true }),
  ).toBeVisible();
});
