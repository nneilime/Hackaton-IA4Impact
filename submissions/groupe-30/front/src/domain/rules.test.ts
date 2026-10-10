import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import {
  actionSchedule,
  BASELINE_METADATA,
  currentEvents,
  latestActions,
  mergeActions,
  parseActionBackup,
  parseScores,
  ranksFor,
  scoreCsv,
  validateInspection,
} from "./rules";
import type { Catalog, HistoryData, Inspection } from "./types";

const catalog = JSON.parse(
  readFileSync(
    new URL("../../tests/fixtures/catalog.json", import.meta.url),
    "utf8",
  ),
) as Catalog;
const history = JSON.parse(
  readFileSync(
    new URL("../../tests/fixtures/history.json", import.meta.url),
    "utf8",
  ),
) as HistoryData;
const sample = catalog.equipment.filter((e) => e.inScope).slice(0, 2);
const makeAction = (overrides: Partial<Inspection> = {}): Inspection => ({
  id: "test-case",
  equipmentId: sample[0].id,
  status: "preparing",
  owner: "Équipe technique",
  providerId: "PRE01",
  objective: "Contrôle ciblé",
  desiredDate: "",
  confirmedDate: "",
  reviewDate: "",
  visitedDate: "",
  outcome: "",
  note: "",
  conclusion: "",
  externalReference: "",
  cycleStartedAt: sample[0].cycleStartedAt,
  scoreVersion: "v1",
  createdAt: "2026-10-10T10:00:00Z",
  updatedAt: "2026-10-10T10:00:00Z",
  history: [],
  ...overrides,
});

describe("Import du modèle", () => {
  it("accepte un résultat partiel sans attribuer zéro aux absents", () => {
    const value = parseScores(
      `equipement_id,score_risque\n${sample[0].id},-3.5`,
      catalog.equipment,
      BASELINE_METADATA,
    );
    expect(value.scores[sample[0].id]).toBe(-3.5);
    expect(Object.hasOwn(value.scores, sample[1].id)).toBe(false);
  });
  it("accepte BOM et fichier à séparateur point-virgule", () => {
    expect(
      parseScores(
        `\uFEFFequipement_id;score_risque\r\n${sample[0].id};0.75`,
        catalog.equipment,
        BASELINE_METADATA,
      ).scores[sample[0].id],
    ).toBe(0.75);
  });
  it.each(["", "NaN", "Infinity", "texte"])(
    "refuse un score invalide : %s",
    (raw) => {
      expect(() =>
        parseScores(
          `equipement_id,score_risque\n${sample[0].id},${raw}`,
          catalog.equipment,
          BASELINE_METADATA,
        ),
      ).toThrow(/score/);
    },
  );
  it("refuse les doublons plutôt que conserver la dernière ligne", () => {
    expect(() =>
      parseScores(
        `equipement_id,score_risque\n${sample[0].id},1\n${sample[0].id},2`,
        catalog.equipment,
        BASELINE_METADATA,
      ),
    ).toThrow(/plusieurs/);
  });
  it("refuse les références inconnues et hors périmètre", () => {
    for (const id of [
      "EQP-INCONNU",
      catalog.equipment.find((e) => !e.inScope)!.id,
    ])
      expect(() =>
        parseScores(
          `equipement_id,score_risque\n${id},1`,
          catalog.equipment,
          BASELINE_METADATA,
        ),
      ).toThrow(/périmètre/);
  });
  it("refuse une autre date de référence pour cet inventaire", () => {
    expect(() =>
      parseScores(
        `equipement_id,score_risque\n${sample[0].id},1`,
        catalog.equipment,
        { ...BASELINE_METADATA, referenceDate: "2024-12-31" },
      ),
    ).toThrow(/dates/);
  });
  it("ne traite une valeur hors 0-1 comme erreur que pour une probabilité déclarée", () => {
    const csv = `equipement_id,score_risque\n${sample[0].id},1.8`;
    expect(() =>
      parseScores(csv, catalog.equipment, BASELINE_METADATA),
    ).not.toThrow();
    expect(() =>
      parseScores(csv, catalog.equipment, {
        ...BASELINE_METADATA,
        kind: "calibrated_probability",
      }),
    ).toThrow(/probabilité/);
  });
  it("ne permet pas l’export complet d’un classement partiel", () => {
    expect(() => scoreCsv({ [sample[0].id]: 1 }, catalog.equipment)).toThrow(
      /chaque équipement/,
    );
  });
  it("exporte exactement les 1 285 équipements sans les colonnes du suivi métier", () => {
    const csv = scoreCsv(catalog.baselineScores, catalog.equipment);
    expect(csv.split("\r\n")).toHaveLength(1286);
    expect(csv.split("\r\n")[0]).toBe("equipement_id,score_risque");
  });
});
describe("Classement et vies d’appareil", () => {
  it("départage les ex æquo et conserve le rang global dans une sélection", () => {
    const ranks = ranksFor({ "EQP-003": 0.2, "EQP-002": 0.7, "EQP-001": 0.7 });
    expect(ranks.get("EQP-001")).toBe(1);
    expect(ranks.get("EQP-003")).toBe(3);
    const filtered = ["EQP-003"].map((id) => ranks.get(id));
    expect(filtered).toEqual([3]);
  });
  it("ne rattache pas les anciens incidents au nouvel appareil EQP-01533", () => {
    const e = catalog.equipment.find((e) => e.id === "EQP-01533")!;
    const all = history.events[e.id];
    const current = currentEvents(e, all);
    expect(current.length).toBeLessThan(all.length);
    expect(current.every((e) => e.date >= "2025-07-22T17:17")).toBe(true);
    expect(current.some((e) => e.type === "Remplacement")).toBe(true);
  });
  it("ne transforme pas une date de pose inconnue en histoire complète", () => {
    expect(
      currentEvents(
        { ...sample[0], cycleStartedAt: null },
        history.events[sample[0].id],
      ),
    ).toEqual([]);
  });
  it("conserve 42 observations sourcées, les collectifs et la borne temporelle", () => {
    expect(Object.values(history.reports).flat()).toHaveLength(42);
    expect(
      catalog.equipment.filter((e) => e.inScope && e.collective),
    ).toHaveLength(45);
    expect(
      Object.values(history.events)
        .flat()
        .every((e) => e.date < "2026-01-01"),
    ).toBe(true);
  });
});
describe("Décisions et suivi des inspections", () => {
  it("affiche la date de réexamen après un report malgré une ancienne date confirmée", () => {
    expect(
      actionSchedule(
        makeAction({
          status: "review",
          confirmedDate: "2026-11-01",
          reviewDate: "2026-12-01",
        }),
      ),
    ).toEqual({ label: "Réexamen", date: "2026-12-01" });
  });
  it("affiche le passage réel pour un dossier réalisé", () => {
    expect(
      actionSchedule(
        makeAction({
          status: "completed",
          confirmedDate: "2025-12-01",
          visitedDate: "2025-12-02",
        }),
      ),
    ).toEqual({ label: "Passage", date: "2025-12-02" });
  });
  it("une date souhaitée ne suffit pas à confirmer un rendez-vous", () => {
    expect(() =>
      validateInspection(
        makeAction({ status: "planned", desiredDate: "2026-11-01" }),
        [],
      ),
    ).toThrow(/confirmée/);
  });
  it("refuse deux dossiers ouverts pour le même équipement", () => {
    expect(() =>
      validateInspection(makeAction(), [makeAction({ id: "other" })]),
    ).toThrow(/déjà ouvert/);
  });
  it("autorise la mise à jour du dossier existant et un nouveau dossier après clôture", () => {
    expect(() =>
      validateInspection(makeAction(), [makeAction()]),
    ).not.toThrow();
    expect(() =>
      validateInspection(makeAction(), [
        makeAction({ id: "previous", status: "closed" }),
      ]),
    ).not.toThrow();
  });
  it("exige une date de réexamen pour un report", () => {
    expect(() =>
      validateInspection(makeAction({ status: "review" }), []),
    ).toThrow(/réexamen/);
  });
  it("exige un constat et une conclusion pour la clôture", () => {
    expect(() =>
      validateInspection(
        makeAction({
          status: "closed",
          visitedDate: "2025-12-01",
          outcome: "RAS",
        }),
        [],
      ),
    ).toThrow(/conclusion/);
  });
});
describe("Sauvegarde et continuité du suivi", () => {
  const backup = (actions: Inspection[]) =>
    JSON.stringify({ version: 1, actions });
  it("restaure des dossiers valides avec leur historique", () => {
    const action = makeAction({
      history: [
        { date: "2026-10-10T10:00:00Z", label: "Création", note: "Contrôle" },
      ],
    });
    expect(
      parseActionBackup(backup([action]), catalog.equipment).actions,
    ).toEqual([action]);
  });
  it("refuse une référence inconnue et un format ancien inconnu", () => {
    expect(() =>
      parseActionBackup(
        backup([makeAction({ equipmentId: "UNKNOWN" })]),
        catalog.equipment,
      ),
    ).toThrow(/invalide/);
    expect(() =>
      parseActionBackup('{"version":2,"actions":[]}', catalog.equipment),
    ).toThrow(/format/);
  });
  it("refuse une date et un état illisibles avant toute restauration", () => {
    expect(() =>
      parseActionBackup(
        backup([makeAction({ createdAt: "pas une date" })]),
        catalog.equipment,
      ),
    ).toThrow(/date/);
    expect(() =>
      parseActionBackup(
        backup([makeAction({ status: "inconnu" as Inspection["status"] })]),
        catalog.equipment,
      ),
    ).toThrow(/État/);
  });
  it("préserve un dossier déjà présent même si la sauvegarde contient une ancienne version", () => {
    const current = makeAction({ note: "Décision récente" });
    const old = makeAction({ note: "Ancienne décision" });
    expect(mergeActions([current], [old])).toEqual([current]);
  });
  it("refuse la fusion de deux dossiers ouverts sur un équipement", () => {
    expect(() =>
      mergeActions([makeAction()], [makeAction({ id: "other" })]),
    ).toThrow(/déjà ouvert/);
  });
  it("un dossier clôturé reste clôturé dans la liste, sans réouverture automatique", () => {
    const closed = makeAction({
      status: "closed",
      visitedDate: "2025-12-01",
      outcome: "RAS",
      conclusion: "Contrôle terminé",
    });
    expect(latestActions([closed]).get(closed.equipmentId)?.status).toBe(
      "closed",
    );
    const newCase = makeAction({
      id: "new",
      updatedAt: "2026-10-11T10:00:00Z",
    });
    expect(latestActions([closed, newCase]).get(closed.equipmentId)?.id).toBe(
      "new",
    );
  });
  it("conserve un signalement séparé des scores et valide son auteur", () => {
    const value = {
      version: 1,
      actions: [],
      feedback: [
        {
          id: "feedback-1",
          equipmentId: sample[0].id,
          subject: "Pose",
          comment: "À vérifier",
          author: "Technique",
          createdAt: "2026-10-10T10:00:00Z",
        },
      ],
    };
    expect(
      parseActionBackup(JSON.stringify(value), catalog.equipment).feedback,
    ).toHaveLength(1);
    value.feedback[0].author = "";
    expect(() =>
      parseActionBackup(JSON.stringify(value), catalog.equipment),
    ).toThrow(/signalement/);
  });
});
