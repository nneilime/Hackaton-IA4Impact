import { test, expect, type Page } from "@playwright/test";
import { mkdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { sharedApi, login } from "./shared-api";
test.beforeEach(async ({ page }) => {
  await sharedApi(page);
  await login(page);
});

const equipment = "EQP-01533";
const snapshotDir = resolve("qa");
mkdirSync(snapshotDir, { recursive: true });
async function openEquipment(page: Page) {
  await page.goto(`/equipements/${equipment}`);
  await expect(
    page.getByRole("heading", { name: "Carte d’identité" }),
  ).toBeVisible();
}
async function saveForm(page: Page) {
  await page
    .getByRole("button", { name: "Vérifier le dossier", exact: true })
    .click();
  await expect(
    page.getByText("Vérifiez le dossier avant de l’enregistrer"),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Enregistrer le dossier", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
}
test("classement, filtres, sources et navigation conservée", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/examiner");
  await expect(
    page.getByRole("heading", { name: "Votre liste de prévention" }),
  ).toBeVisible();
  await expect(page.getByRole("table").locator("tbody tr")).toHaveCount(15);
  await expect(page.getByText("1–15 sur 129 équipements")).toBeVisible();
  await expect(page.locator("body")).not.toContainText("hackathon mode");
  await page.screenshot({
    path: resolve(snapshotDir, "liste-desktop.png"),
    animations: "disabled",
  });
  await page.getByRole("button", { name: "Page suivante" }).click();
  await expect(page.getByText("Page 2 sur 9")).toBeVisible();
  await page
    .getByRole("link", { name: /Ouvrir EQP-/ })
    .first()
    .click();
  await page.getByRole("link", { name: "Revenir à la liste" }).click();
  await expect(page.getByText("Page 2 sur 9")).toBeVisible();
  await page.getByRole("button", { name: "Page précédente" }).click();
  await expect(page.getByText("Page 1 sur 9")).toBeVisible();
  await page.getByRole("button", { name: "Collectifs", exact: true }).click();
  await expect(page.getByText("1–15 sur 45 équipements")).toBeVisible();
  await page.getByRole("button", { name: "Tous", exact: true }).click();
  await page
    .getByRole("textbox", {
      name: "Rechercher un équipement, un logement ou un bâtiment",
    })
    .fill(equipment);
  await expect(page.getByRole("table").locator("tbody tr")).toHaveCount(1);
  await page.getByRole("link", { name: `Ouvrir ${equipment}` }).click();
  await expect(
    page
      .locator(".identity-grid")
      .getByText("22 juillet 2025", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: /Inclure l.appareil précédent/,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: /Consulter le PDF original/ }).first(),
  ).toHaveAttribute("href", /^\/sources\/.+\.pdf#page=/);
  await page
    .getByRole("button", {
      name: /Inclure l.appareil précédent/,
    })
    .click();
  await expect(
    page.getByRole("button", {
      name: /Masquer les données de l.appareil précédent/,
    }),
  ).toBeVisible();
  await page.screenshot({
    path: resolve(snapshotDir, "fiche-desktop.png"),
    animations: "disabled",
  });
  await page.getByRole("link", { name: "Revenir à la liste" }).click();
  await expect(
    page.getByRole("textbox", {
      name: "Rechercher un équipement, un logement ou un bâtiment",
    }),
  ).toHaveValue(equipment);
  await page
    .getByRole("textbox", {
      name: "Rechercher un équipement, un logement ou un bâtiment",
    })
    .fill("AUCUNE-REFERENCE");
  await expect(
    page.getByRole("heading", { name: "Aucun équipement dans cette vue" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("signalement, inspection, constat, clôture et récupération partagés", async ({
  page,
}, testInfo) => {
  await openEquipment(page);
  await page
    .getByRole("button", { name: "Signaler une information incorrecte" })
    .click();
  await page.getByLabel("Votre nom ou équipe *").fill("Équipe QA");
  await page
    .getByLabel("Observation et référence concernée *")
    .fill("Vérifier le rattachement du rapport au matériel remplacé.");
  await page
    .getByRole("button", { name: "Enregistrer le signalement" })
    .click();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Signalements de l’équipe" }),
  ).toBeVisible();
  await expect(
    page
      .locator(".identity-grid")
      .getByText("22 juillet 2025", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Préparer une inspection", exact: true })
    .first()
    .click();
  await page.getByLabel("Responsable *", { exact: true }).fill("Équipe QA");
  await page.getByLabel("État du dossier").selectOption("planned");
  await page.getByLabel("Date souhaitée", { exact: false }).fill("2026-11-01");
  await page
    .getByRole("button", { name: "Vérifier le dossier", exact: true })
    .click();
  await expect(
    page.getByText("Vérifiez le dossier avant de l’enregistrer"),
  ).toHaveCount(0);
  await page.getByLabel("Date confirmée", { exact: false }).fill("2026-11-03");
  await saveForm(page);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Suivre l’inspection" }),
  ).toBeVisible();
  await expect(page.getByText("Planifiée", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Suivre l’inspection" }).click();
  await page.getByLabel("État du dossier").selectOption("completed");
  await page.getByLabel("Date du passage *").fill("2025-12-01");
  await page.getByLabel("Résultat *").selectOption("RAS");
  await saveForm(page);
  await expect(page.getByText("Réalisée", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Suivre l’inspection" }).click();
  await page.getByLabel("État du dossier").selectOption("closed");
  await page
    .getByLabel("Conclusion du dossier *")
    .fill("Contrôle terminé, surveillance habituelle.");
  await saveForm(page);
  await expect(
    page.locator(".past-action").getByText("Clôturée", { exact: true }),
  ).toBeVisible();
  await page.getByText("Historique des décisions (3)", { exact: true }).click();
  await expect(page.getByText("Retour terrain : RAS").first()).toBeVisible();
  await page.goto(`/equipements?q=${equipment}`);
  await expect(
    page.getByRole("table").getByText("Clôturée", { exact: true }),
  ).toBeVisible();
  await page.goto(`/examiner?scope=all&q=${equipment}`);
  await expect(
    page.getByRole("heading", { name: "Aucun équipement dans cette vue" }),
  ).toBeVisible();
  await page.goto("/actions");
  const backupDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Sauvegarder les dossiers" }).click();
  const backupPath = testInfo.outputPath("dossiers.json");
  await (await backupDownload).saveAs(backupPath);
  expect(JSON.parse(readFileSync(backupPath, "utf8")).feedback).toHaveLength(1);
  await page
    .getByRole("button", { name: `Supprimer le dossier de ${equipment}` })
    .click();
  await page
    .getByRole("button", { name: "Supprimer le dossier", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Votre prochaine inspection commence ici",
    }),
  ).toBeVisible();
  await page
    .getByLabel("Sauvegarde de dossiers à restaurer")
    .setInputFiles(backupPath);
  await expect(
    page.locator(".action-list").getByText("Clôturée", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.locator(".action-list").getByText("Clôturée", { exact: true }),
  ).toBeVisible();
});

test("clavier, menu mobile, largeur intermédiaire et équipement hors périmètre", async ({
  page,
}) => {
  await page.goto("/examiner");
  await expect(
    page.getByRole("heading", { name: "Votre liste de prévention" }),
  ).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Aller au contenu" }),
  ).toBeFocused();
  await page.getByRole("button", { name: "Données", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Données", exact: true }),
  ).toBeFocused();
  await page.setViewportSize({ width: 1024, height: 900 });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(1024);
  await page.screenshot({
    path: resolve(snapshotDir, "liste-tablette.png"),
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Ouvrir la navigation" }).focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("link", { name: "À examiner", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Ouvrir la navigation" }),
  ).toBeFocused();
  await expect(
    page.getByRole("button", { name: "Ouvrir la navigation" }),
  ).toHaveAttribute("aria-expanded", "false");
  const catalog = JSON.parse(
    readFileSync(resolve("tests/fixtures/catalog.json"), "utf8"),
  );
  const excluded = catalog.equipment.find(
    (item: { inScope: boolean }) => !item.inScope,
  );
  await page.goto(`/equipements/${excluded.id}`);
  await expect(
    page.getByRole("heading", { name: "Hors périmètre de prédiction" }),
  ).toBeVisible();
});

test("fiche, navigation et formulaire utilisables sur mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/examiner");
  await expect(
    page.getByRole("heading", { name: "Votre liste de prévention" }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.screenshot({
    path: resolve(snapshotDir, "liste-mobile.png"),
    animations: "disabled",
  });
  await page.getByRole("button", { name: "Ouvrir la navigation" }).click();
  await page.getByRole("link", { name: "Actions", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "Votre prochaine inspection commence ici",
    }),
  ).toBeVisible();
  await openEquipment(page);
  await expect(
    page.getByRole("button", { name: "Réexaminer plus tard" }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.getByRole("button", { name: "Réexaminer plus tard" }).click();
  await page.getByLabel("Responsable *", { exact: true }).fill("Équipe QA");
  await page.getByLabel("Date de réexamen *").fill("2026-11-01");
  await page.screenshot({
    path: resolve(snapshotDir, "formulaire-mobile.png"),
    animations: "disabled",
  });
  await saveForm(page);
  await expect(page.getByText("À réexaminer", { exact: true })).toBeVisible();
});

test("aperçu CSV, annulation, confirmation et changement d’horizon", async ({
  page,
}) => {
  await page.goto("/examiner");
  await page.getByRole("button", { name: "Données", exact: true }).click();
  await page
    .getByRole("button", { name: "Importer des CSV", exact: true })
    .click();
  await page.getByLabel("Fichiers CSV à importer").setInputFiles({
    name: "invalide.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("equipement_id\nINCONNU"),
  });
  await page.getByRole("button", { name: "Vérifier les fichiers" }).click();
  await expect(page.getByRole("alert")).toContainText("ligne 2");
  await expect(
    page.getByRole("button", { name: "Confirmer l’import" }),
  ).toBeDisabled();
  await page.getByLabel("Fichiers CSV à importer").setInputFiles({
    name: "equipements.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("CSV valide simulé"),
  });
  await page.getByRole("button", { name: "Vérifier les fichiers" }).click();
  await expect(
    page.getByRole("button", { name: "Confirmer l’import" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Confirmer l’import" }).click();
  await page.getByLabel("Horizon", { exact: true }).selectOption("730");
  await expect(
    page.getByRole("heading", { name: "CatBoost · 730 jours" }),
  ).toBeVisible();
  await expect(
    page.getByText("Score de risque non calibré", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Recalculer le classement" }).click();
  await expect(
    page.getByText("Le calcul des quatre horizons a démarré.", { exact: true }),
  ).toBeVisible();
});
