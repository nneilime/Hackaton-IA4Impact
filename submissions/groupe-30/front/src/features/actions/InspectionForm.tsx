import { useState, type FormEvent } from "react";
import { CalendarDays, Check, ClipboardCheck } from "lucide-react";
import { useAppData } from "../../data/store";
import type { Equipment, Inspection, ActionStatus } from "../../domain/types";
import { STATUS_LABELS } from "../../domain/types";
import { dateLabel } from "../../domain/rules";
import { Field, Modal } from "../../ui/components";
import { DecisionHistory } from "./DecisionHistory";

export function InspectionForm({
  equipment,
  existing,
  onClose,
  initialStatus,
  initialObjective,
  targetStatus,
}: {
  equipment: Equipment;
  existing?: Inspection;
  onClose: () => void;
  initialStatus?: ActionStatus;
  initialObjective?: string;
  targetStatus?: ActionStatus;
}) {
  const { catalog, result, saveAction } = useAppData();
  const effectiveInitialStatus = targetStatus || initialStatus;
  const [form, setForm] = useState<Inspection>(
    () =>
      existing
        ? targetStatus
          ? { ...existing, status: targetStatus }
          : existing
        : {
            id: crypto.randomUUID(),
            equipmentId: equipment.id,
            status: effectiveInitialStatus || "preparing",
            owner: "",
            providerId: equipment.providerId,
            objective:
              initialObjective ||
              "Contrôler l’état de l’équipement et vérifier les signes observés.",
            desiredDate: "",
            confirmedDate: "",
            reviewDate: "",
            visitedDate: "",
            outcome: "",
            note: "",
            conclusion: "",
            externalReference: "",
            cycleStartedAt: equipment.cycleStartedAt,
            scoreVersion: result.metadata.modelVersion,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            history: [],
          },
  );
  const [error, setError] = useState("");
  const [step, setStep] = useState<"edit" | "confirm">("edit");
  function patch(key: keyof Inspection, value: string) {
    setForm({ ...form, [key]: value });
    setError("");
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (step === "edit") {
      setStep("confirm");
      return;
    }
    try {
      await saveAction(form);
      onClose();
    } catch (error) {
      setError((error as Error).message);
      setStep("edit");
    }
  }
  return (
    <Modal
      title={
        existing
          ? "Suivre l’inspection"
          : initialStatus === "review"
            ? "Prévoir un réexamen"
            : "Préparer une inspection"
      }
      description={`${equipment.label} · ${equipment.id}`}
      onClose={onClose}
    >
      <form onSubmit={submit} className="inspection-form">
        <div className="modal-body">
          <div className="equipment-summary">
            <span className="small-icon">
              <ClipboardCheck size={20} />
            </span>
            <div>
              <strong>
                {equipment.residenceId.replace("RES-", "Résidence ")} ·{" "}
                {equipment.buildingId}
              </strong>
              <p>
                {equipment.housingId || "Parties communes"} ·{" "}
                {equipment.underContract
                  ? "Sous contrat d’entretien"
                  : "Hors contrat d’entretien"}
              </p>
            </div>
          </div>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          {step === "confirm" ? (
            <div className="confirmation">
              <h3>Vérifiez le dossier avant de l’enregistrer</h3>
              <dl>
                <dt>Responsable</dt>
                <dd>{form.owner || "À renseigner"}</dd>
                <dt>État du dossier</dt>
                <dd>{STATUS_LABELS[form.status]}</dd>
                <dt>Objectif</dt>
                <dd>{form.objective}</dd>
                <dt>Date souhaitée</dt>
                <dd>
                  {form.desiredDate
                    ? dateLabel(form.desiredDate, true)
                    : "À définir"}
                </dd>
                {form.confirmedDate && (
                  <>
                    <dt>Date confirmée</dt>
                    <dd>{dateLabel(form.confirmedDate, true)}</dd>
                  </>
                )}
                {form.reviewDate && (
                  <>
                    <dt>Réexamen</dt>
                    <dd>{dateLabel(form.reviewDate, true)}</dd>
                  </>
                )}
                {form.outcome && (
                  <>
                    <dt>Constat</dt>
                    <dd>{form.outcome}</dd>
                  </>
                )}
              </dl>
            </div>
          ) : (
            <>
              <div className="form-step-tip">
                <strong>
                  {form.status === "preparing" && "Étape 1 · Commande prestataire"}
                  {form.status === "planned" && "Étape 2 · Date d’intervention confirmée"}
                  {form.status === "completed" && "Étape 3 · Retour de visite et constat"}
                  {form.status === "closed" && "Étape 3 · Clôture définitive du dossier"}
                  {form.status === "review" && "Dossier en réexamen ultérieur"}
                </strong>
                <p>
                  {form.status === "preparing" && "Définissez le responsable et transmettez la demande au prestataire sous contrat."}
                  {form.status === "planned" && "Renseignez la date confirmée avec le prestataire pour planifier le passage."}
                  {form.status === "completed" && "Saisissez la date réelle du passage et le résultat constaté (RAS, anomalie, devis...)."}
                  {form.status === "closed" && "Renseignez la conclusion pour archiver ce dossier dans l’historique des décisions."}
                  {form.status === "review" && "Indiquez la date de réexamen pour surveiller l’équipement."}
                </p>
              </div>
              <div className="field-grid">
                <Field label="Responsable *">
                  <input
                    autoComplete="name"
                    value={form.owner}
                    required
                    placeholder="Nom ou équipe responsable"
                    onChange={(e) => patch("owner", e.target.value)}
                  />
                </Field>
                <Field label="État du dossier">
                  <select
                    value={form.status}
                    onChange={(e) => patch("status", e.target.value)}
                  >
                    {Object.entries(STATUS_LABELS).map(([key, label]) => (
                      <option key={key} value={key}>
                        {label}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>
              <Field label="Objectif du contrôle *">
                <textarea
                  value={form.objective}
                  rows={3}
                  required
                  onChange={(e) => patch("objective", e.target.value)}
                />
              </Field>
              <Field
                label="Préparer une décision"
                hint="Une proposition d’objectif, à adapter avec les observations et les devis."
              >
                <select
                  value=""
                  onChange={(e) => {
                    if (e.target.value) patch("objective", e.target.value);
                  }}
                >
                  <option value="">Choisir un objectif de travail</option>
                  {[
                    [
                      "Contrôle préventif",
                      "Contrôler l’état de l’équipement et vérifier les signes observés.",
                    ],
                    [
                      "Comparer réparation et remplacement",
                      "Comparer des devis de réparation et de remplacement, en tenant compte de la prise en charge du contrat et des travaux proposés.",
                    ],
                    [
                      "Demander un devis",
                      "Obtenir un devis détaillé et confirmer le besoin technique avant toute dépense.",
                    ],
                    [
                      "Coordonner avec une rénovation",
                      "Confirmer le périmètre et le calendrier de la rénovation avant d’engager une réparation importante.",
                    ],
                    [
                      "Surveiller et réexaminer",
                      "Surveiller les symptômes observés et définir une date de réexamen avec l’équipe.",
                    ],
                  ].map(([label, objective]) => (
                    <option key={label} value={objective}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Prestataire proposé">
                <select
                  value={form.providerId}
                  onChange={(e) => patch("providerId", e.target.value)}
                >
                  {catalog.providers.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name.replace(" (fictif)", "")}
                    </option>
                  ))}
                </select>
              </Field>
              <div className="field-grid">
                <Field
                  label="Date souhaitée"
                  hint="Une demande de passage, pas un rendez-vous confirmé."
                >
                  <input
                    type="date"
                    value={form.desiredDate}
                    onChange={(e) => patch("desiredDate", e.target.value)}
                  />
                </Field>
                <Field
                  label="Date confirmée"
                  hint="À compléter après confirmation du passage."
                >
                  <input
                    type="date"
                    required={form.status === "planned"}
                    value={form.confirmedDate}
                    onChange={(e) => patch("confirmedDate", e.target.value)}
                  />
                </Field>
              </div>
              {form.status === "review" && (
                <Field label="Date de réexamen *">
                  <input
                    type="date"
                    required
                    value={form.reviewDate}
                    onChange={(e) => patch("reviewDate", e.target.value)}
                  />
                </Field>
              )}
              <Field
                label="Référence d’une action existante"
                hint="Si ce contrôle est déjà suivi dans votre outil métier."
              >
                <input
                  value={form.externalReference}
                  placeholder="Référence du dossier ou de l’intervention"
                  onChange={(e) => patch("externalReference", e.target.value)}
                />
              </Field>
              {(form.status === "completed" || form.status === "closed") && (
                <div className="form-section">
                  <h3>
                    <CalendarDays size={17} />
                    Retour de visite
                  </h3>
                  <div className="field-grid">
                    <Field label="Date du passage *">
                      <input
                        type="date"
                        required
                        value={form.visitedDate}
                        onChange={(e) => patch("visitedDate", e.target.value)}
                      />
                    </Field>
                    <Field label="Résultat *">
                      <select
                        required
                        value={form.outcome}
                        onChange={(e) => patch("outcome", e.target.value)}
                      >
                        <option value="">Choisir un constat</option>
                        {[
                          "RAS",
                          "Anomalie constatée",
                          "Réparation réalisée",
                          "Second passage nécessaire",
                          "Remplacement à étudier",
                          "Visite non réalisée",
                        ].map((o) => (
                          <option key={o}>{o}</option>
                        ))}
                      </select>
                    </Field>
                  </div>
                  {form.status === "closed" && (
                    <Field label="Conclusion du dossier *">
                      <textarea
                        rows={3}
                        required
                        value={form.conclusion}
                        onChange={(e) => patch("conclusion", e.target.value)}
                      />
                    </Field>
                  )}
                </div>
              )}
              <Field label="Précisions et compte rendu">
                <textarea
                  rows={3}
                  value={form.note}
                  placeholder="Points à vérifier, modalités d’accès connues ou constat du passage…"
                  onChange={(e) => patch("note", e.target.value)}
                />
              </Field>
              {existing && <DecisionHistory action={existing} />}
            </>
          )}
        </div>
        <div className="modal-footer">
          <button
            type="button"
            className="button secondary"
            onClick={() => (step === "confirm" ? setStep("edit") : onClose())}
          >
            {step === "confirm" ? "Modifier" : "Annuler"}
          </button>
          <button className="button primary" type="submit">
            <Check size={17} />
            {step === "confirm"
              ? "Enregistrer le dossier"
              : "Vérifier le dossier"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
