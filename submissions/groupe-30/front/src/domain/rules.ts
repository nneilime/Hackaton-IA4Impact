import Papa from "papaparse";
import {
  STATUS_LABELS,
  type ActionBackup,
  type DataFeedback,
  type Equipment,
  type Inspection,
  type Intervention,
  type ScoreMetadata,
  type ScoreResult,
} from "./types";

export const BASELINE_METADATA: ScoreMetadata = {
  label: "Référence par âge relatif",
  modelVersion: "age-relatif-v1",
  referenceDate: "2025-12-31",
  horizonStart: "2026-01-01",
  horizonEndExclusive: "2026-10-01",
  kind: "ranking_score",
  importedAt: null,
};
export function ranksFor(scores: Record<string, number>) {
  return new Map(
    Object.entries(scores)
      .sort(([a, av], [b, bv]) => bv - av || a.localeCompare(b))
      .map(([id], index) => [id, index + 1]),
  );
}
export function currentEvents(equipment: Equipment, events: Intervention[]) {
  return equipment.cycleStartedAt
    ? events.filter((e) => e.date >= equipment.cycleStartedAt!)
    : [];
}
export function normalize(text: string) {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}
export function parseScores(
  csv: string,
  equipment: Equipment[],
  metadata: ScoreMetadata,
): ScoreResult {
  if (
    !metadata ||
    !["ranking_score", "calibrated_probability"].includes(metadata.kind)
  )
    throw new Error("La nature du score doit être précisée.");
  const parsed = Papa.parse<Record<string, string>>(
    csv.replace(/^\uFEFF/, ""),
    {
      header: true,
      skipEmptyLines: "greedy",
      transformHeader: (h) => h.trim(),
    },
  );
  if (parsed.errors.length)
    throw new Error(`CSV illisible : ${parsed.errors[0].message}`);
  if (
    !parsed.meta.fields?.includes("equipement_id") ||
    !parsed.meta.fields.includes("score_risque")
  )
    throw new Error(
      "Le fichier doit contenir les colonnes equipement_id et score_risque.",
    );
  const eligible = new Set(equipment.filter((e) => e.inScope).map((e) => e.id));
  const scores: Record<string, number> = {};
  for (const [index, row] of parsed.data.entries()) {
    const id = row.equipement_id?.trim();
    if (!id || !eligible.has(id))
      throw new Error(
        `Ligne ${index + 2} : équipement inconnu ou hors périmètre (${id || "vide"}).`,
      );
    if (Object.hasOwn(scores, id))
      throw new Error(`Ligne ${index + 2} : ${id} apparaît plusieurs fois.`);
    const raw = row.score_risque?.trim();
    const value = Number(raw);
    if (!raw || !Number.isFinite(value))
      throw new Error(`Ligne ${index + 2} : score non numérique ou non fini.`);
    if (metadata.kind === "calibrated_probability" && (value < 0 || value > 1))
      throw new Error(
        `Ligne ${index + 2} : la probabilité doit être comprise entre 0 et 1.`,
      );
    scores[id] = value;
  }
  if (!Object.keys(scores).length)
    throw new Error("Le fichier ne contient aucun score.");
  if (!metadata.label.trim() || !metadata.modelVersion.trim())
    throw new Error("Renseignez le nom du résultat et sa version.");
  if (
    metadata.referenceDate !== "2025-12-31" ||
    metadata.horizonStart !== "2026-01-01" ||
    metadata.horizonEndExclusive !== "2026-10-01"
  )
    throw new Error(
      "Les dates doivent correspondre au patrimoine chargé : référence au 31/12/2025, horizon du 01/01/2026 au 30/09/2026.",
    );
  return { scores, metadata };
}
export function validateInspection(action: Inspection, existing: Inspection[]) {
  if (!Object.hasOwn(STATUS_LABELS, action.status))
    throw new Error("État de dossier inconnu.");
  if (!action.owner.trim() || !action.objective.trim())
    throw new Error("Renseignez le responsable et l’objectif du contrôle.");
  if (
    action.status !== "closed" &&
    existing.some(
      (a) =>
        a.id !== action.id &&
        a.equipmentId === action.equipmentId &&
        a.status !== "closed",
    )
  )
    throw new Error(
      "Un dossier est déjà ouvert pour cet équipement. Consultez-le pour ajouter votre décision.",
    );
  if (action.status === "planned" && !action.confirmedDate)
    throw new Error(
      "Une date confirmée est nécessaire pour une inspection planifiée.",
    );
  if (
    (action.status === "completed" || action.status === "closed") &&
    (!action.visitedDate || !action.outcome)
  )
    throw new Error("Renseignez la date de visite et son résultat.");
  if (action.status === "closed" && !action.conclusion.trim())
    throw new Error("Ajoutez une conclusion avant de clôturer le dossier.");
  if (action.status === "review" && !action.reviewDate)
    throw new Error("Choisissez une date de réexamen.");
  if (
    action.visitedDate &&
    action.visitedDate > new Date().toISOString().slice(0, 10)
  )
    throw new Error(
      "Une visite réalisée ne peut pas être datée dans le futur.",
    );
}
export function latestActions(actions: Inspection[]) {
  const latest = new Map<string, Inspection>();
  for (const action of [...actions].sort((a, b) =>
    a.updatedAt.localeCompare(b.updatedAt),
  )) {
    const previous = latest.get(action.equipmentId);
    if (!previous || previous.status === "closed" || action.status !== "closed")
      latest.set(action.equipmentId, action);
  }
  return latest;
}
export function actionSchedule(action: Inspection) {
  if (action.status === "completed" || action.status === "closed")
    return { label: "Passage", date: action.visitedDate };
  if (action.status === "review")
    return { label: "Réexamen", date: action.reviewDate };
  if (action.status === "planned")
    return { label: "Confirmée", date: action.confirmedDate };
  return { label: "Souhaitée", date: action.desiredDate };
}
export function parseActionBackup(
  raw: string,
  equipment: Equipment[],
): ActionBackup {
  let value: ActionBackup;
  try {
    value = JSON.parse(raw);
  } catch {
    throw new Error("La sauvegarde JSON est illisible.");
  }
  if (!value || value.version !== 1 || !Array.isArray(value.actions))
    throw new Error("Le format de cette sauvegarde n’est pas reconnu.");
  const known = new Set(equipment.map((e) => e.id));
  const ids = new Set<string>();
  const fields = [
    "id",
    "equipmentId",
    "status",
    "owner",
    "providerId",
    "objective",
    "desiredDate",
    "confirmedDate",
    "reviewDate",
    "visitedDate",
    "outcome",
    "note",
    "conclusion",
    "externalReference",
    "scoreVersion",
    "createdAt",
    "updatedAt",
  ] as const;
  const dateValid = (date: unknown) =>
    typeof date === "string" &&
    /^\d{4}-\d{2}-\d{2}/.test(date) &&
    Number.isFinite(Date.parse(date));
  for (const action of value.actions) {
    if (
      !action ||
      fields.some((field) => typeof action[field] !== "string") ||
      !action.id.trim() ||
      !known.has(action.equipmentId) ||
      ids.has(action.id) ||
      !Array.isArray(action.history)
    )
      throw new Error(
        "Un dossier de la sauvegarde est invalide, inconnu ou dupliqué.",
      );
    if (
      ![action.createdAt, action.updatedAt].every(dateValid) ||
      ![
        action.desiredDate,
        action.confirmedDate,
        action.reviewDate,
        action.visitedDate,
      ].every((date) => !date || dateValid(date)) ||
      !(action.cycleStartedAt === null || dateValid(action.cycleStartedAt))
    )
      throw new Error("Une date de la sauvegarde est invalide.");
    if (
      action.history.some(
        (event) =>
          !event ||
          !dateValid(event.date) ||
          typeof event.label !== "string" ||
          typeof event.note !== "string" ||
          (event.status !== undefined &&
            !Object.hasOwn(STATUS_LABELS, event.status)),
      )
    )
      throw new Error("L’historique d’un dossier est invalide.");
    ids.add(action.id);
    validateInspection(action, value.actions);
  }
  if (value.feedback !== undefined) {
    if (!Array.isArray(value.feedback))
      throw new Error("Les signalements de la sauvegarde sont illisibles.");
    const feedbackIds = new Set<string>();
    for (const item of value.feedback) {
      if (
        !item ||
        ["id", "equipmentId", "subject", "comment", "author", "createdAt"].some(
          (field) => typeof item[field as keyof DataFeedback] !== "string",
        ) ||
        !item.id ||
        !known.has(item.equipmentId) ||
        !item.subject.trim() ||
        !item.comment.trim() ||
        !item.author.trim() ||
        !dateValid(item.createdAt) ||
        feedbackIds.has(item.id)
      )
        throw new Error("Un signalement de la sauvegarde est invalide.");
      feedbackIds.add(item.id);
    }
  }
  return value;
}
export function mergeActions(existing: Inspection[], incoming: Inspection[]) {
  const ids = new Set(existing.map((a) => a.id));
  const merged = [...existing, ...incoming.filter((a) => !ids.has(a.id))];
  merged.forEach((action) => validateInspection(action, merged));
  return merged;
}
export function scoreCsv(
  scores: Record<string, number>,
  equipment: Equipment[],
) {
  const scope = equipment.filter((e) => e.inScope);
  if (
    scope.some(
      (e) => !Object.hasOwn(scores, e.id) || !Number.isFinite(scores[e.id]),
    ) ||
    Object.keys(scores).length !== scope.length
  )
    throw new Error(
      "L’export complet exige un score valide pour chaque équipement du périmètre.",
    );
  return Papa.unparse(
    scope.map((e) => ({ equipement_id: e.id, score_risque: scores[e.id] })),
  );
}
export function dateLabel(value: string | null | undefined, long = false) {
  if (!value) return "Non renseignée";
  const date = new Date(value.slice(0, 10) + "T12:00:00");
  return new Intl.DateTimeFormat("fr-FR", {
    day: "numeric",
    month: long ? "long" : "short",
    year: "numeric",
  }).format(date);
}
export const numberLabel = (value: number) =>
  new Intl.NumberFormat("fr-FR").format(value);
export function download(
  name: string,
  content: string,
  mime = "text/csv;charset=utf-8",
) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
