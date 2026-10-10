import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { Page } from "@playwright/test";

const catalog = JSON.parse(
  readFileSync(resolve("tests/fixtures/catalog.json"), "utf8"),
);
const history = JSON.parse(
  readFileSync(resolve("tests/fixtures/history.json"), "utf8"),
);
export async function sharedApi(page: Page, role = "admin") {
  let actions: any[] = [];
  let feedback: any[] = [];
  let unavailable = false;
  let budget = {
    year: 2026,
    version: 0,
    renovationBudget: 1500000,
    maintenanceBudget: null as number | null,
    operationIds: [] as string[],
    isDefault: true,
  };
  const economicEquipment = ["EQP-01533", "EQP-00001"].map((id, index) => ({
    equipmentId: id,
    label: "Chaudière gaz individuelle",
    family: "chaudiere_gaz_individuelle",
    residenceId: "RES-A",
    buildingId: "BAT-A1",
    housingId: "LGT-A1-001",
    providerId: "PRE01",
    collective: false,
    buildingHousingCount: 40,
    underContract: true,
    rank: index + 1,
    priority: true,
    cycleKnown: true,
    repairCount12m: 3,
    pricedRepairCount12m: 3,
    simulatedRepairCost12m: 900,
    replacementMin: 2600,
    replacementMax: 3900,
    repairReplacementRatioMin: 0.23,
    repairReplacementRatioMax: 0.35,
    firstFailureCost: 300,
    weightedFirstFailureCost: 200,
    financeScope: "logement",
    financeContext: {
      billed12m: 400,
      invoiceCount12m: 2,
      outstanding: 100,
      orderCount: 3,
    },
    operationIds: ["OPE-QA"],
  }));
  const economicOperations = [
    {
      id: "OPE-QA",
      residenceId: "RES-A",
      label: "Remplacement chaudières individuelles",
      perimeter: "Résidence",
      desiredYear: 2026,
      cost: 800000,
      energyGain: 15,
      housingCount: 160,
      costPerHousing: 5000,
      reason: "Pannes répétées",
      status: "Proposé (hypothétique)",
      priorityEquipmentCount: 2,
      families: ["chaudiere_gaz_individuelle"],
      buildingIds: null,
      chronologicalRank: 1,
    },
    {
      id: "OPE-BIG",
      residenceId: "RES-A",
      label: "Isolation thermique",
      perimeter: "Résidence",
      desiredYear: 2026,
      cost: 2400000,
      energyGain: 120,
      housingCount: 160,
      costPerHousing: 15000,
      reason: "Performance énergétique",
      status: "Proposé (hypothétique)",
      priorityEquipmentCount: 2,
      families: [],
      buildingIds: null,
      chronologicalRank: 2,
    },
  ];
  const visitGroups = [
    {
      residenceId: "RES-A",
      providerId: "PRE01",
      equipmentIds: ["EQP-01533", "EQP-00001"],
      potentialVisitsCombined: 1,
    },
  ];
  const scores = Object.fromEntries(
    Object.entries(catalog.baselineScores).map(([id, score]) => [
      id,
      Number(score) / 10,
    ]),
  );
  await page.route(
    "https://batia-test.supabase.co/auth/v1/**",
    async (route) => {
      if (route.request().url().includes("logout"))
        return route.fulfill({ status: 204 });
      await route.fulfill({
        json: {
          access_token: "test-token",
          refresh_token: "test-refresh",
          token_type: "bearer",
          expires_in: 3600,
          user: {
            id: "00000000-0000-0000-0000-000000000001",
            email: "qa@example.invalid",
            aud: "authenticated",
            role: "authenticated",
          },
        },
      });
    },
  );
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path === "/api/config")
      return route.fulfill({
        json: {
          url: "https://batia-test.supabase.co",
          publishableKey: "test-public-key",
        },
      });
    if (!request.headers().authorization)
      return route.fulfill({
        status: 401,
        json: { detail: "Connexion requise" },
      });
    if (path === "/api/workspace") {
      if (unavailable)
        return route.fulfill({
          status: 503,
          json: { detail: "API indisponible" },
        });
      const horizon = Number(url.searchParams.get("horizon") || 90);
      const day = url.searchParams.get("as_of_date") || "2026-01-01";
      return route.fulfill({
        json: {
          catalog: { ...catalog, revision: 2 },
          user: { id: "qa", role, email: "qa@example.invalid", name: "QA" },
          actions,
          feedback,
          jobs: [],
          result: {
            scores,
            revision: 2,
            metadata: {
              label: `CatBoost · ${horizon} jours`,
              modelVersion: "qa-trained-model",
              referenceDate: day,
              horizonStart: day,
              horizonEndExclusive: new Date(
                Date.parse(day) + horizon * 86400000,
              )
                .toISOString()
                .slice(0, 10),
              kind: "ranking_score",
              importedAt: "2026-01-01T00:00:00Z",
            },
          },
        },
      });
    }
    if (path === "/api/predict")
      return route.fulfill({
        json: Object.fromEntries(
          [90, 180, 365, 730].map((h) => [
            `failure_types_${h}d`,
            {
              status: "unavailable",
              predictions: [],
              other_conditional_probability: 0,
              expected_price_if_failure: null,
              expected_cost_within_horizon: null,
            },
          ]),
        ),
      });
    if (path === "/api/economies") {
      return route.fulfill({
        json: {
          revision: 2,
          referenceDate: "2026-01-01",
          periodStart: "2025-01-01",
          result: {
            stale: false,
            metadata: { modelVersion: "qa-trained-model" },
          },
          equipment: economicEquipment,
          operations: economicOperations,
          groups: visitGroups,
          residenceFinance: { "RES-A": economicEquipment[0].financeContext },
          plan: budget,
        },
      });
    }
    if (path.endsWith("/economie")) {
      const id = path.split("/").at(-2);
      return route.fulfill({
        json: {
          equipment: economicEquipment.find((e) => e.equipmentId === id) || {
            ...economicEquipment[0],
            equipmentId: id,
          },
          referenceDate: "2026-01-01",
          periodStart: "2025-01-01",
          revision: 2,
          stale: false,
          operations: economicOperations.slice(0, 1),
          groups: visitGroups,
        },
      });
    }
    if (path.startsWith("/api/budgets/")) {
      const next = request.postDataJSON();
      if (next.version !== budget.version)
        return route.fulfill({
          status: 409,
          json: {
            detail:
              "Ce budget a été modifié par un autre membre. Rechargez les arbitrages.",
          },
        });
      const total = economicOperations
        .filter((o) => next.operationIds.includes(o.id))
        .reduce((s, o) => s + o.cost, 0);
      if (total > next.renovationBudget)
        return route.fulfill({
          status: 422,
          json: { detail: "La sélection dépasse l’enveloppe de rénovation." },
        });
      budget = {
        ...budget,
        ...next,
        version: budget.version + 1,
        isDefault: false,
      };
      return route.fulfill({ json: budget });
    }
    if (path.endsWith("/historique")) return route.fulfill({ json: history });
    if (path.startsWith("/api/inspections/")) {
      const id = decodeURIComponent(path.split("/").at(-1)!);
      if (request.method() === "DELETE")
        actions = actions.filter((a) => a.id !== id);
      else {
        const next = request.postDataJSON();
        const old = actions.find((a) => a.id === id);
        actions = actions.filter((a) => a.id !== id);
        actions.push({
          ...next,
          version: (old?.version || 0) + 1,
          history: [
            ...(old?.history || []),
            {
              date: new Date().toISOString(),
              label: old ? "Décision enregistrée" : "Dossier créé",
              note: next.note || next.objective,
              status: next.status,
              outcome: next.outcome,
            },
          ],
        });
      }
      return route.fulfill({ json: { actions, feedback } });
    }
    if (path === "/api/signalements") {
      feedback.push(request.postDataJSON());
      return route.fulfill({ json: { actions, feedback } });
    }
    if (path === "/api/workspace/recovery/preview") {
      const body = request.postDataJSON();
      return route.fulfill({
        json: {
          actions: body.actions.length,
          feedback: body.feedback?.length || 0,
          skipped: 0,
        },
      });
    }
    if (path === "/api/workspace/recovery") {
      const body = request.postDataJSON();
      actions = [
        ...actions,
        ...body.actions.filter((a: any) => !actions.some((x) => x.id === a.id)),
      ];
      feedback = [
        ...feedback,
        ...(body.feedback || []).filter(
          (a: any) => !feedback.some((x) => x.id === a.id),
        ),
      ];
      return route.fulfill({ json: { actions, feedback } });
    }
    if (path === "/api/imports/preview") {
      const invalid = request.postData()?.includes("invalide.csv");
      return route.fulfill({
        json: {
          token: "preview-qa",
          revision: 2,
          files: [
            {
              file: invalid ? "invalide.csv" : "equipements.csv",
              table: "equipements",
              rows: 1,
              added: 0,
              updated: 1,
              unchanged: 0,
            },
          ],
          tables: { equipements: { added: 0, updated: 1, unchanged: 0 } },
          errors: invalid
            ? [{ file: "invalide.csv", line: 2, message: "référence absente" }]
            : [],
        },
      });
    }
    if (path.includes("/confirm"))
      return route.fulfill({ json: { revision: 3, modelChanged: true } });
    if (path === "/api/calculs")
      return route.fulfill({ json: { id: "calculation-qa" } });
    return route.fulfill({
      status: 404,
      json: { detail: "Route simulée inconnue " + path },
    });
  });
  return {
    setUnavailable(value: boolean) {
      unavailable = value;
    },
    changeBudget() {
      budget = {
        ...budget,
        version: budget.version + 1,
        renovationBudget: 2000000,
        isDefault: false,
      };
    },
  };
}

export async function login(page: Page) {
  await page.goto("/");
  await page.getByLabel("Courriel", { exact: true }).fill("qa@example.invalid");
  await page
    .getByLabel("Mot de passe", { exact: true })
    .fill("mot-de-passe-test");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await page.getByRole("button", { name: "Données", exact: true }).waitFor();
}
