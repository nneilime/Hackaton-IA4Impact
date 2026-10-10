import { useRef, useState } from "react";
import { Link } from "react-router";
import {
  CalendarDays,
  ClipboardList,
  Download,
  ArrowRight,
  Search,
  Trash2,
  Pencil,
  Clock3,
  CircleCheck,
} from "lucide-react";
import Papa from "papaparse";
import { useAppData } from "../../data/store";
import {
  actionSchedule,
  dateLabel,
  download,
  normalize,
  numberLabel,
} from "../../domain/rules";
import { STATUS_LABELS, type Inspection, type ActionStatus } from "../../domain/types";
import { EmptyState, Metric, Modal, StatusBadge } from "../../ui/components";
import { InspectionForm } from "./InspectionForm";

export function ActionsPage() {
  const { actions, feedback, catalog, deleteAction, importBackup, notify } =
    useAppData();
  const [status, setStatus] = useState("all");
  const [query, setQuery] = useState("");
  const backupInput = useRef<HTMLInputElement>(null);
  const [restoreError, setRestoreError] = useState("");
  const [editing, setEditing] = useState<Inspection | null>(null);
  const [targetStatus, setTargetStatus] = useState<ActionStatus | undefined>();
  const [deleting, setDeleting] = useState<Inspection | null>(null);

  function openEditWithStatus(action: Inspection, target?: ActionStatus) {
    setTargetStatus(target);
    setEditing(action);
  }

  const items = actions
    .filter(
      (a) =>
        (status === "all" || a.status === status) &&
        (!query ||
          normalize(`${a.equipmentId} ${a.owner} ${a.objective}`).includes(
            normalize(query),
          )),
    )
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  function exportActions() {
    download(
      "inspections-preventives.csv",
      Papa.unparse(
        actions.map((a) => {
          const equipment = catalog.equipment.find(
            (e) => e.id === a.equipmentId,
          )!;
          return {
            dossier: a.id,
            equipement_id: a.equipmentId,
            famille: equipment.label,
            residence_id: equipment.residenceId,
            batiment_id: equipment.buildingId,
            logement_id: equipment.housingId || "",
            prestataire_id: a.providerId,
            statut: STATUS_LABELS[a.status],
            responsable: a.owner,
            objectif: a.objective,
            date_souhaitee: a.desiredDate,
            date_confirmee: a.confirmedDate,
            date_visite: a.visitedDate,
            resultat: a.outcome,
            date_reexamen: a.reviewDate,
            reference_externe: a.externalReference,
            conclusion: a.conclusion,
            commentaire: a.note,
            derniere_observation: equipment.latestObservation?.text || "",
            source_observation: equipment.latestObservation?.id || "",
            date_observation: equipment.latestObservation?.date || "",
            version_classement: a.scoreVersion,
          };
        }),
        { escapeFormulae: true },
      ),
      "text/csv;charset=utf-8",
    );
    notify("Les dossiers de préparation ont été exportés.");
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            <span />
            PILOTAGE PRESTATAIRES & SUIVI OPÉRATIONNEL
          </span>
          <h1>Suivi des interventions prestataires.</h1>
          <p>
            Pilotez chaque dossier du devis jusqu’au retour terrain : commandez
            l'intervention, planifiez la date de passage et archivez le constat.
          </p>
        </div>
        <button
          className="button secondary"
          disabled={!actions.length}
          onClick={exportActions}
        >
          <Download size={17} />
          Exporter les inspections
        </button>
      </div>

      {/* Guide visuel du cycle de vie */}
      <div className="action-workflow-guide" aria-label="Cycle de traitement d’une intervention">
        <div className="workflow-step-card">
          <span className="workflow-step-num">1</span>
          <div>
            <strong>1. Commande créée</strong>
            <p>Dossier préventif initié avec l'objectif et le prestataire sous contrat.</p>
          </div>
        </div>
        <span className="workflow-arrow" aria-hidden="true">→</span>
        <div className="workflow-step-card">
          <span className="workflow-step-num">2</span>
          <div>
            <strong>2. Visite planifiée</strong>
            <p>Date d’intervention convenue et confirmée avec le prestataire.</p>
          </div>
        </div>
        <span className="workflow-arrow" aria-hidden="true">→</span>
        <div className="workflow-step-card">
          <span className="workflow-step-num">3</span>
          <div>
            <strong>3. Constat terrain & Clôture</strong>
            <p>Compte-rendu du passage (RAS, réparation, devis) et archivage.</p>
          </div>
        </div>
      </div>

      <div className="metrics">
        <Metric
          label="Dossiers ouverts"
          value={numberLabel(
            actions.filter((a) => a.status !== "closed").length,
          )}
          detail="En attente de passage ou de retour"
          icon={<ClipboardList size={23} />}
        />
        <Metric
          label="Passages planifiés"
          value={numberLabel(
            actions.filter((a) => a.status === "planned").length,
          )}
          detail="Dates de visite confirmées"
          icon={<CalendarDays size={23} />}
          tone="mint"
        />
        <Metric
          label="Constats enregistrés"
          value={numberLabel(
            actions.filter(
              (a) => a.status === "completed" || a.status === "closed",
            ).length,
          )}
          detail="Retours terrain disponibles"
          icon={<CircleCheck size={23} />}
          tone="rose"
        />
      </div>
      <section className="list-section">
        <div className="section-heading">
          <div>
            <h2>
              Dossiers d’intervention
              <span className="count-tag">{actions.length}</span>
            </h2>
            <p>Faites avancer chaque action étape par étape avec le bouton dédié.</p>
          </div>
          <span className="quiet-label">Partagé avec l’équipe</span>
        </div>
        <div className="scope-tabs" aria-label="États des dossiers">
          {[["all", "Tous"], ...Object.entries(STATUS_LABELS)].map(
            ([key, label]) => {
              const count =
                key === "all"
                  ? actions.length
                  : actions.filter((a) => a.status === key).length;
              return (
                <button
                  key={key}
                  className={key === status ? "active" : ""}
                  aria-pressed={key === status}
                  onClick={() => setStatus(key)}
                >
                  {label}
                  <span className="tab-pill-count">{count}</span>
                </button>
              );
            },
          )}
        </div>
        <div className="filter-bar">
          <div className="search-field wide-search">
            <Search size={18} />
            <input
              aria-label="Rechercher un dossier d’inspection"
              placeholder="Rechercher un équipement, un responsable…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <button
            className="button subtle"
            disabled={!actions.length && !feedback.length}
            onClick={() =>
              download(
                "sauvegarde-inspections.json",
                JSON.stringify(
                  {
                    version: 1,
                    exportedAt: new Date().toISOString(),
                    actions,
                    feedback,
                  },
                  null,
                  2,
                ),
                "application/json",
              )
            }
          >
            <Download size={16} />
            Sauvegarder les dossiers
          </button>
          <button
            className="button subtle"
            onClick={() => backupInput.current?.click()}
          >
            Restaurer une sauvegarde
          </button>
          <input
            ref={backupInput}
            type="file"
            accept=".json,application/json"
            hidden
            aria-label="Sauvegarde de dossiers à restaurer"
            onChange={async (event) => {
              const file = event.target.files?.[0];
              if (!file) return;
              try {
                await importBackup(await file.text());
                setRestoreError("");
              } catch (error) {
                setRestoreError((error as Error).message);
              }
              event.target.value = "";
            }}
          />
        </div>
        {restoreError && (
          <p className="form-error restore-error" role="alert">
            {restoreError}
          </p>
        )}
        {!items.length ? (
          <EmptyState
            title={
              actions.length
                ? "Aucun dossier dans cette vue"
                : "Votre prochaine inspection commence ici"
            }
            description={
              actions.length
                ? "Changez de filtre ou recherchez une autre référence."
                : "Ouvrez une fiche équipement pour préparer un contrôle. Les dossiers que vous créez apparaîtront dans cet espace."
            }
            action={
              <Link className="button primary" to="/examiner">
                Examiner les équipements
                <ArrowRight size={16} />
              </Link>
            }
          />
        ) : (
          <div className="action-list">
            {items.map((action) => {
              const equipment = catalog.equipment.find(
                (e) => e.id === action.equipmentId,
              );
              if (!equipment) return null;
              const provider = catalog.providers.find(
                (p) => p.id === action.providerId,
              );
              const schedule = actionSchedule(action);

              const isStep1Done = true;
              const isStep2Done =
                action.status === "completed" || action.status === "closed";
              const isStep2Active = action.status === "planned";
              const isStep3Done = action.status === "closed";
              const isStep3Active = action.status === "completed";

              return (
                <article className="action-row" key={action.id}>
                  <span className="action-row-icon">
                    <ClipboardList size={21} />
                  </span>
                  <div className="action-row-main">
                    <div className="action-row-header-line">
                      <Link
                        to={`/equipements/${equipment.id}`}
                        state={{ backTo: "/actions" }}
                      >
                        <strong>{equipment.label}</strong>
                        <ArrowRight size={14} />
                      </Link>
                      <span className="action-ref-badge">{equipment.id}</span>
                      {provider && (
                        <span className="action-provider-badge">
                          Prestataire : {provider.name.replace(" (fictif)", "")}
                        </span>
                      )}
                    </div>
                    <span className="action-loc-detail">
                      {equipment.residenceId.replace("RES-", "Résidence ")} ·{" "}
                      {equipment.buildingId} ·{" "}
                      {equipment.housingId || "Parties communes"}
                    </span>
                    <p className="action-obj-text">{action.objective}</p>

                    {/* Mini-stepper visuel de cycle de vie */}
                    <div className="action-stepper-track" aria-label="Progression du dossier">
                      <div className="stepper-node done">
                        <span className="node-dot">✓</span>
                        <span className="node-text">1. Commande</span>
                      </div>
                      <span className={`stepper-connector ${isStep2Done || isStep2Active ? "active" : ""}`} />
                      <div
                        className={`stepper-node ${
                          isStep2Done
                            ? "done"
                            : isStep2Active
                              ? "current"
                              : "todo"
                        }`}
                      >
                        <span className="node-dot">
                          {isStep2Done ? "✓" : "2"}
                        </span>
                        <span className="node-text">
                          {action.confirmedDate
                            ? `2. Visite (${dateLabel(action.confirmedDate)})`
                            : "2. Planification"}
                        </span>
                      </div>
                      <span className={`stepper-connector ${isStep3Done || isStep3Active ? "active" : ""}`} />
                      <div
                        className={`stepper-node ${
                          isStep3Done
                            ? "done"
                            : isStep3Active
                              ? "current"
                              : "todo"
                        }`}
                      >
                        <span className="node-dot">
                          {isStep3Done ? "✓" : "3"}
                        </span>
                        <span className="node-text">
                          {action.status === "closed"
                            ? "3. Clôturé"
                            : action.outcome
                              ? `3. Constat (${action.outcome})`
                              : "3. Constat & Clôture"}
                        </span>
                      </div>
                    </div>

                    {action.externalReference && (
                      <small className="action-ext-note">
                        Réf. dossier métier : {action.externalReference}
                      </small>
                    )}
                  </div>

                  {/* Bouton d'action directe pour avancer le dossier */}
                  <div className="action-row-cta">
                    {action.status === "preparing" && (
                      <button
                        className="button primary compact action-advance-btn"
                        onClick={() => openEditWithStatus(action, "planned")}
                      >
                        Planifier la visite →
                      </button>
                    )}
                    {action.status === "planned" && (
                      <button
                        className="button primary compact action-advance-btn"
                        onClick={() => openEditWithStatus(action, "completed")}
                      >
                        Saisir le constat →
                      </button>
                    )}
                    {action.status === "completed" && (
                      <button
                        className="button primary compact action-advance-btn"
                        onClick={() => openEditWithStatus(action, "closed")}
                      >
                        Clôturer le dossier ✓
                      </button>
                    )}
                    {action.status === "review" && (
                      <button
                        className="button secondary compact action-advance-btn"
                        onClick={() => openEditWithStatus(action, "review")}
                      >
                        Gérer le réexamen →
                      </button>
                    )}
                    {action.status === "closed" && (
                      <span className="action-closed-indicator">
                        <CircleCheck size={14} /> Dossier clôturé
                      </span>
                    )}
                  </div>

                  <div className="action-row-meta">
                    <StatusBadge status={action.status} />
                    <strong>{action.owner || "Non assigné"}</strong>
                    <span>
                      <Clock3 size={13} />
                      {schedule.date
                        ? `${schedule.label} : ${dateLabel(schedule.date)}`
                        : "Date à définir"}
                    </span>
                  </div>

                  <div className="action-row-buttons">
                    <button
                      className="icon-button"
                      title="Modifier tous les champs"
                      aria-label={`Mettre à jour le dossier de ${equipment.id}`}
                      onClick={() => openEditWithStatus(action)}
                    >
                      <Pencil size={16} />
                    </button>
                    <button
                      className="icon-button danger"
                      title="Supprimer le dossier"
                      aria-label={`Supprimer le dossier de ${equipment.id}`}
                      onClick={() => setDeleting(action)}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
      <p className="page-footnote">
        <span>
          Les constats de visite ne mesurent pas à eux seuls le nombre de pannes
          évitées.
        </span>
      </p>
      {editing && (
        <InspectionForm
          equipment={catalog.equipment.find(
            (e) => e.id === editing.equipmentId,
          )!}
          existing={editing}
          targetStatus={targetStatus}
          onClose={() => {
            setEditing(null);
            setTargetStatus(undefined);
          }}
        />
      )}
      {deleting && (
        <Modal
          title="Supprimer ce dossier ?"
          description="Cette opération retire le dossier partagé et ses décisions. L’historique technique et les scores sont conservés."
          onClose={() => setDeleting(null)}
        >
          <div className="modal-body">
            <p>
              <strong>{deleting.equipmentId}</strong> · {deleting.objective}
            </p>
          </div>
          <div className="modal-footer">
            <button
              className="button secondary"
              onClick={() => setDeleting(null)}
            >
              Conserver le dossier
            </button>
            <button
              className="button destructive"
              onClick={async () => {
                try {
                  await deleteAction(deleting.id);
                  setDeleting(null);
                } catch (e) {
                  notify((e as Error).message);
                }
              }}
            >
              Supprimer le dossier
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
