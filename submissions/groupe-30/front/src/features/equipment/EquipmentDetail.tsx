import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  CalendarDays,
  ClipboardList,
  Clock3,
  FileText,
  History,
  Info,
  ShieldCheck,
  Wrench,
  MessageSquare,
  ChevronDown,
  ChevronUp,
  RefreshCw,
} from "lucide-react";
import { loadHistory, useAppData } from "../../data/store";
import type { HistoryData } from "../../domain/types";
import {
  actionSchedule,
  currentEvents,
  dateLabel,
  numberLabel,
} from "../../domain/rules";
import {
  Badge,
  EmptyState,
  ExternalEvidenceLink,
  StatusBadge,
} from "../../ui/components";
import { InspectionForm } from "../actions/InspectionForm";
import { DecisionHistory } from "../actions/DecisionHistory";
import { FeedbackForm } from "./FeedbackForm";
import { HeroAgeCard } from "./HeroAgeCard";
import { InteractiveTimeline } from "./InteractiveTimeline";
import { FailurePrediction } from "./FailurePrediction";

export function EquipmentDetail() {
  const { id } = useParams();
  const location = useLocation();
  const {
    catalog,
    ranks,
    result,
    actions,
    feedback,
    lastListQuery,
    asOfDate,
    horizon,
  } = useAppData();
  const equipment = catalog.equipment.find((e) => e.id === id);
  const [history, setHistory] = useState<HistoryData | null>(null);
  const [error, setError] = useState("");
  const [showOld, setShowOld] = useState(false);
  const [limit, setLimit] = useState(10);
  const [modal, setModal] = useState<
    "inspection" | "review" | "feedback" | null
  >(null);
  const [retry, setRetry] = useState(0);
  const [inspectionObjective, setInspectionObjective] = useState<string>();
  useEffect(() => {
    let alive = true;
    if (!id) return;
    loadHistory(id, asOfDate)
      .then((data) => {
        if (alive) {
          setHistory(data);
          setError("");
        }
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [retry, id, asOfDate, catalog.revision]);
  useEffect(() => {
    setShowOld(false);
    setLimit(10);
    setInspectionObjective(undefined);
    window.scrollTo(0, 0);
  }, [id]);
  if (!equipment)
    return (
      <EmptyState
        title="Équipement introuvable"
        description="Cette référence n’est pas présente dans le patrimoine chargé."
        action={
          <Link className="button primary" to="/equipements">
            Consulter le patrimoine
          </Link>
        }
      />
    );
  const rank = ranks.get(equipment.id);
  const count = Object.keys(result.scores).length;
  const active = actions.find(
    (a) => a.equipmentId === equipment.id && a.status !== "closed",
  );
  const schedule = active ? actionSchedule(active) : null;
  const pastActions = actions.filter(
    (a) => a.equipmentId === equipment.id && a.status === "closed",
  );
  const provider = catalog.providers.find((p) => p.id === equipment.providerId);
  const events = [...(history?.events[equipment.id] || [])].sort((a, b) =>
    b.date.localeCompare(a.date),
  );
  const current = currentEvents(equipment, events);
  const previous = equipment.cycleStartedAt
    ? events.filter((e) => !current.includes(e))
    : [];
  const timeline = showOld || !equipment.cycleStartedAt ? events : current;
  const recentStart = new Date(
    new Date(asOfDate + "T00:00:00Z").getTime() - 365 * 86400000,
  )
    .toISOString()
    .slice(0, 10);
  const linkedIds = new Set(events.map((e) => e.requestId).filter(Boolean));
  const linkedRequests =
    history?.requests.filter((r) => linkedIds.has(r.id)) || [];
  const contextRequests =
    history?.requests
      .filter(
        (r) =>
          !linkedIds.has(r.id) &&
          r.date >= recentStart &&
          (equipment.collective
            ? r.parts === "Communes" && r.buildingId === equipment.buildingId
            : r.parts === "Privatives" && r.housingId === equipment.housingId),
      )
      .sort((a, b) => b.date.localeCompare(a.date))
      .slice(0, 3) || [];
  const reports = history?.reports[equipment.id] || [];
  const backTo = location.state?.backTo || "/examiner" + lastListQuery;
  const baseline = result.metadata.modelVersion === "age-relatif-v1";
  return (
    <>
      <Link className="back-link" to={backTo}>
        <ArrowLeft size={16} />
        Revenir à la liste
      </Link>
      <div className="detail-heading">
        <div className="detail-title">
          <span className="detail-symbol">
            <Building2 size={29} />
          </span>
          <div>
            <div className="inline-tags">
              <span className="eyebrow">FICHE ÉQUIPEMENT</span>
              <Badge tone={equipment.collective ? "blue" : "neutral"}>
                {equipment.collective ? "Collectif" : "Privatif"}
              </Badge>
              {!equipment.inScope && (
                <Badge>Hors périmètre de prédiction</Badge>
              )}
            </div>
            <h1>{equipment.label}</h1>
            <p>
              {equipment.id}
              <span>·</span>
              {equipment.residenceId.replace("RES-", "Résidence ")}
              <span>·</span>
              {equipment.housingId || equipment.buildingId}
            </p>
          </div>
        </div>
        <button
          className="button primary"
          onClick={() => setModal("inspection")}
        >
          <ClipboardList size={17} />
          {active ? "Suivre l’inspection" : "Préparer une inspection"}
        </button>
      </div>
      <div className="detail-decision">
        <section className="surface decision-summary">
          <span className="eyebrow">DIAGNOSTIC ET CONTRÔLE PRÉVENTIF</span>
          <h2>
            {rank && rank <= Math.ceil(count * 0.1)
              ? "Contrôle sur site recommandé en priorité"
              : rank
                ? "Équipement sous surveillance standard"
                : "Vérification des données et constats"}
          </h2>
          <p>
            {active
              ? "Un dossier d’intervention est déjà ouvert : complétez-le avec le rapport de visite et les devis."
              : rank && rank <= Math.ceil(count * 0.1)
                ? "Cet équipement figure parmi les plus à risque du parc. Une visite préventive est conseillée pour contrôler les organes d’usure avant une panne bloquante."
                : "Le niveau d’incident actuel est modéré. Consultez l’historique ci-dessous pour planifier le prochain entretien réglementaire."}
          </p>
          <div className="decision-facts">
            <div className="decision-fact-card">
              <span className="decision-fact-label">Niveau de risque</span>
              <span className="decision-fact-value">
                {rank
                  ? `Rang ${rank} sur ${numberLabel(count)}`
                  : "Non scoré"}
              </span>
              <span className="decision-fact-sub">
                {rank && rank <= Math.ceil(count * 0.1)
                  ? `Top 10 % critique · horizon ${horizon}j`
                  : rank
                    ? `Horizon prédictif ${horizon}j`
                    : "Décision d’après les constats"}
              </span>
            </div>
            <div className="decision-fact-card">
              <span className="decision-fact-label">Historique d’interventions</span>
              <span className="decision-fact-value">
                {equipment.recentRepairCount > 0
                  ? `${equipment.recentRepairCount} dépannages`
                  : "Aucun dépannage récent"}
              </span>
              <span className="decision-fact-sub">
                {equipment.cycleStartedAt
                  ? "sur les 12 derniers mois"
                  : "Cycle de l’appareil à confirmer"}
              </span>
            </div>
            <div className="decision-fact-card">
              <span className="decision-fact-label">Périmètre d’impact</span>
              <span className="decision-fact-value">
                {equipment.collective
                  ? `${equipment.buildingHousingCount || "Plusieurs"} logements`
                  : "Équipement privatif"}
              </span>
              <span className="decision-fact-sub">
                {equipment.collective
                  ? `Parties communes · ${equipment.buildingId || "Bâtiment"}`
                  : "Continuité de service du logement"}
              </span>
            </div>
          </div>
        </section>
        {equipment.inScope && (
          <FailurePrediction
            equipmentId={equipment.id}
            asOfDate={asOfDate}
            horizon={horizon}
            revision={catalog.revision}
            modelVersion={result.metadata.modelVersion}
          />
        )}
      </div>
      <div className="detail-layout">
        <div className="detail-main">
          <HeroAgeCard
            equipment={equipment}
            rank={rank}
            totalRanked={count}
            housingDpe={equipment.housingDpe}
            snapshotDate={catalog.snapshotDate}
          />
          <section className="surface identity-card">
            <div className="card-heading">
              <h2>
                <Building2 size={18} />
                Carte d’identité
              </h2>
              {equipment.needsVerification && (
                <Badge tone="amber">À vérifier</Badge>
              )}
            </div>
            <div className="identity-grid">
              <div>
                <small>Localisation</small>
                <strong>
                  {equipment.residenceId.replace("RES-", "Résidence ")} ·{" "}
                  {equipment.buildingId}
                </strong>
                <span>{equipment.housingId || "Parties communes"}</span>
              </div>
              <div>
                <small>Pose de l’appareil actuel</small>
                <strong>{dateLabel(equipment.installedAt, true)}</strong>
                <span>
                  {equipment.ageYears !== null
                    ? `${equipment.ageYears.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} ans au ${dateLabel(catalog.snapshotDate)}`
                    : "Âge non disponible"}
                </span>
              </div>
              <div>
                <small>Prestataire</small>
                <strong>
                  {provider?.name.replace(" (fictif)", "") ||
                    equipment.providerId}
                </strong>
                <span>
                  {equipment.underContract
                    ? "Sous contrat d’entretien"
                    : "Hors contrat d’entretien"}
                </span>
              </div>
              <div>
                <small>Entretien</small>
                <strong>
                  {equipment.annualVisit
                    ? "Visite annuelle prévue"
                    : "Pas de visite annuelle prévue"}
                </strong>
                <span>
                  Durée de référence : {equipment.referenceLifeYears} ans
                </span>
              </div>
            </div>
            <button
              className="text-link feedback-link"
              onClick={() => setModal("feedback")}
            >
              <MessageSquare size={15} />
              Signaler une information incorrecte
            </button>
            <div className="origin-note">
              <Info size={15} />
              <span>Origine de la pose : {equipment.installationOrigin}</span>
            </div>
            {equipment.collective && (
              <div className="context-note">
                Bâtiment de {equipment.buildingHousingCount} logements. Le
                nombre réellement desservi par cette installation reste à
                confirmer.
              </div>
            )}
          </section>
          <section className="surface">
            <div className="card-heading">
              <h2>
                <Wrench size={18} />
                Historique disponible
              </h2>
              <span className="quiet-label">Appareil actuel · 12 mois</span>
            </div>
            <div className="fact-cards">
              <div>
                <strong>
                  {equipment.cycleStartedAt ? equipment.recentRepairCount : "—"}
                </strong>
                <span>
                  Dépannage{equipment.recentRepairCount > 1 ? "s" : ""}
                </span>
              </div>
              <div>
                <strong>
                  {equipment.cycleStartedAt
                    ? equipment.recentAnomalyCount
                    : "—"}
                </strong>
                <span>
                  Anomalie{equipment.recentAnomalyCount > 1 ? "s" : ""}{" "}
                  constatée{equipment.recentAnomalyCount > 1 ? "s" : ""}
                </span>
              </div>
              <div>
                <strong>
                  {!equipment.cycleStartedAt
                    ? "—"
                    : current.filter(
                        (e) =>
                          e.type === "Entretien préventif" &&
                          e.date >= recentStart &&
                          e.result.includes("RAS"),
                      ).length}
                </strong>
                <span>Entretien réalisé avec RAS</span>
              </div>
            </div>
            {equipment.latestObservation && (
              <blockquote className="observation-quote">
                <MessageSquare size={19} />
                <div>
                  <p>« {equipment.latestObservation.text} »</p>
                  <span>
                    Compte-rendu prestataire ·{" "}
                    {dateLabel(equipment.latestObservation.date)} ·{" "}
                    {equipment.latestObservation.id}
                  </span>
                </div>
              </blockquote>
            )}
            <p className="fine-print">
              Ces faits décrivent l’historique observé. Ils ne constituent pas,
              à eux seuls, une explication du calcul du modèle.
            </p>
          </section>
          {error ? (
            <div className="inline-error" role="alert">
              <p>{error}</p>
              <button
                className="button secondary"
                onClick={() => setRetry(retry + 1)}
              >
                <RefreshCw size={15} />
                Réessayer
              </button>
            </div>
          ) : !history ? (
            <div
              className="skeleton-block"
              aria-label="Chargement de la chronologie"
            />
          ) : (
            <InteractiveTimeline
              equipment={equipment}
              interventions={events}
              currentInterventions={current}
              linkedRequests={linkedRequests}
              contextRequests={contextRequests}
              reports={reports}
            />
          )}
        </div>
        <aside className="detail-aside">
          <section className="surface risk-card">
            <div className="card-heading">
              <h2>Priorité de contrôle</h2>
              <span className="risk-icon">
                <ShieldCheck size={19} />
              </span>
            </div>
            {rank ? (
              <>
                <div className="detail-rank">
                  <strong>{rank}</strong>
                  <span>
                    sur {numberLabel(count)}
                    <small>équipements classés</small>
                  </span>
                </div>
                <Badge tone={rank <= Math.ceil(count * 0.1) ? "rose" : "blue"}>
                  {rank <= Math.ceil(count * 0.1)
                    ? "Parmi les 10 % les plus à risque"
                    : "Classé dans le périmètre"}
                </Badge>
              </>
            ) : (
              <h3>
                {equipment.inScope
                  ? "Score non disponible"
                  : "Hors périmètre de prédiction"}
              </h3>
            )}
            <div className="risk-dates">
              <div>
                <small>État des données</small>
                <strong>{dateLabel(result.metadata.referenceDate)}</strong>
              </div>
              <div>
                <small>Horizon étudié</small>
                <strong>
                  {horizon} jours · {dateLabel(result.metadata.horizonStart)} –{" "}
                  {dateLabel(result.metadata.horizonEndExclusive)} (fin exclue)
                </strong>
              </div>
            </div>
            {rank && result.metadata.kind === "calibrated_probability" && (
              <p className="probability">
                Probabilité fournie :{" "}
                {(result.scores[equipment.id] * 100).toLocaleString("fr-FR", {
                  maximumFractionDigits: 1,
                })}{" "}
                %
              </p>
            )}
            <div className="risk-explanation">
              <h3>
                {baseline
                  ? "Ce qui détermine ce classement"
                  : "Explication du modèle"}
              </h3>
              {baseline ? (
                <>
                  <p>
                    Le classement de référence compare l’âge de l’appareil à la
                    durée de vie de sa famille.
                  </p>
                  <div className="factor-row">
                    <span>Âge / durée de référence</span>
                    <strong>
                      {result.scores[equipment.id]?.toLocaleString("fr-FR", {
                        maximumFractionDigits: 2,
                      }) || "—"}
                    </strong>
                  </div>
                </>
              ) : (
                <p>
                  Les facteurs du modèle n’ont pas été fournis avec ce résultat.
                  Les preuves disponibles restent consultables dans le dossier.
                </p>
              )}
            </div>
            <p className="fine-print">
              Un rang exprime une priorité relative. Il ne donne pas une date
              certaine de panne.
            </p>
          </section>
          <section className="surface action-card">
            <div className="card-heading">
              <h2>Prochaine étape</h2>
              <ClipboardList size={18} />
            </div>
            {active ? (
              <>
                <StatusBadge status={active.status} />
                <strong className="action-owner">{active.owner}</strong>
                <p>{active.objective}</p>
                {schedule?.date && (
                  <span className="action-date">
                    <CalendarDays size={15} />
                    {schedule.label} : {dateLabel(schedule.date)}
                  </span>
                )}
                {active.cycleStartedAt !== equipment.cycleStartedAt && (
                  <p className="form-error">
                    L’appareil a changé depuis la préparation du dossier. La
                    décision doit être revue.
                  </p>
                )}
                <button
                  className="button primary full-width"
                  onClick={() => setModal("inspection")}
                >
                  Mettre à jour le dossier
                  <ArrowRight size={16} />
                </button>
              </>
            ) : (
              <>
                <p>
                  Préparez un contrôle ciblé à partir des observations du
                  dossier.
                </p>
                <button
                  className="button primary full-width"
                  onClick={() => setModal("inspection")}
                >
                  <ClipboardList size={16} />
                  Préparer une inspection
                </button>
                <button
                  className="button secondary full-width"
                  onClick={() => setModal("review")}
                >
                  <Clock3 size={16} />
                  Réexaminer plus tard
                </button>
              </>
            )}
            {active && <DecisionHistory action={active} />}
            <Link className="text-link" to="/actions">
              Consulter le suivi des actions
              <ArrowRight size={14} />
            </Link>
          </section>
          {pastActions.length > 0 && (
            <section className="surface">
              <div className="card-heading">
                <h2>Dossiers précédents</h2>
              </div>
              {pastActions.map((a) => (
                <div className="past-action" key={a.id}>
                  <StatusBadge status={a.status} />
                  <p>{a.conclusion}</p>
                  <small>
                    {a.owner} · {dateLabel(a.updatedAt)}
                  </small>
                  <DecisionHistory action={a} />
                </div>
              ))}
            </section>
          )}
          {feedback.some((item) => item.equipmentId === equipment.id) && (
            <section className="surface">
              <div className="card-heading">
                <h2>
                  <MessageSquare size={17} />
                  Signalements de l’équipe
                </h2>
              </div>
              {feedback
                .filter((item) => item.equipmentId === equipment.id)
                .map((item) => (
                  <article className="feedback-item" key={item.id}>
                    <Badge tone="amber">À vérifier</Badge>
                    <strong>{item.subject}</strong>
                    <p>{item.comment}</p>
                    <small>
                      {item.author} · {dateLabel(item.createdAt)}
                    </small>
                  </article>
                ))}
            </section>
          )}
        </aside>
      </div>
      {modal === "feedback" && (
        <FeedbackForm equipment={equipment} onClose={() => setModal(null)} />
      )}
      {(modal === "inspection" || modal === "review") && (
        <InspectionForm
          equipment={equipment}
          existing={active}
          initialStatus={modal === "review" ? "review" : undefined}
          initialObjective={inspectionObjective}
          onClose={() => {
            setModal(null);
            setInspectionObjective(undefined);
          }}
        />
      )}
    </>
  );
}
