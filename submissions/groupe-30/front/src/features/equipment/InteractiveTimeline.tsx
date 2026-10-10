import { useState, useMemo } from "react";
import {
  AlertTriangle,
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  ExternalLink,
  FileText,
  Filter,
  MessageSquare,
  RefreshCw,
  Search,
  ShieldCheck,
  User,
  Wrench,
} from "lucide-react";
import type {
  Equipment,
  Intervention,
  RequestEvidence,
  ReportEvidence,
} from "../../domain/types";
import { dateLabel } from "../../domain/rules";
import { Badge } from "../../ui/components";

export type TimelineEventType =
  | "pose"
  | "incident"
  | "maintenance"
  | "tenant_request"
  | "report"
  | "replacement";

export interface TimelineItem {
  id: string;
  type: TimelineEventType;
  date: string;
  title: string;
  subtitle?: string;
  badgeTone?: "rose" | "amber" | "green" | "blue" | "neutral";
  badgeLabel?: string;
  severity?: string;
  comment?: string;
  authorOrRef?: string;
  isPriorToCurrentAppliance?: boolean;
  rawEvent?: Intervention;
  rawRequest?: RequestEvidence;
  rawReport?: ReportEvidence;
}

interface InteractiveTimelineProps {
  equipment: Equipment;
  interventions: Intervention[];
  currentInterventions: Intervention[];
  linkedRequests: RequestEvidence[];
  contextRequests: RequestEvidence[];
  reports: ReportEvidence[];
}

export function InteractiveTimeline({
  equipment,
  interventions,
  currentInterventions,
  linkedRequests,
  contextRequests,
  reports,
}: InteractiveTimelineProps) {
  const [filterType, setFilterType] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [showOldAppliances, setShowOldAppliances] = useState<boolean>(false);
  const [expandedItems, setExpandedItems] = useState<Record<string, boolean>>(
    {},
  );

  const toggleExpand = (id: string) => {
    setExpandedItems((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  // Construction de tous les événements chronologiques de la vie de l'appareil
  const allTimelineItems = useMemo<TimelineItem[]>(() => {
    const items: TimelineItem[] = [];

    // 1. Événement de pose initiale de l'appareil actuel
    if (equipment.installedAt) {
      items.push({
        id: `pose-${equipment.id}`,
        type: "pose",
        date: equipment.installedAt,
        title: "Mise en service de l'appareil actuel",
        subtitle: `Pose initiale constatée · ${equipment.installationOrigin}`,
        badgeTone: "blue",
        badgeLabel: "Mise en service",
        comment: `Durée de vie de référence du kit : ${equipment.referenceLifeYears} ans. Début du cycle de fonctionnement suivi.`,
        authorOrRef: equipment.installationOrigin,
      });
    }

    // 2. Interventions techniques (Dépannages, Entretiens, Remplacements)
    interventions.forEach((evt) => {
      const isPrior =
        !!equipment.cycleStartedAt && !currentInterventions.includes(evt);
      const isReplacement = evt.type === "Remplacement";
      const isRepair = evt.type === "Dépannage";
      const isPreventive = evt.type === "Entretien préventif";

      let itemType: TimelineEventType = "incident";
      let tone: "rose" | "amber" | "green" | "blue" | "neutral" = "neutral";

      if (isReplacement) {
        itemType = "replacement";
        tone = "blue";
      } else if (isRepair) {
        itemType = "incident";
        tone = evt.severity === "Arrêt total" ? "rose" : "amber";
      } else if (isPreventive) {
        itemType = "maintenance";
        tone = evt.result.includes("RAS") ? "green" : "amber";
      }

      items.push({
        id: evt.id,
        type: itemType,
        date: evt.date,
        title: isReplacement ? "Remplacement de l'équipement" : evt.type,
        subtitle:
          evt.symptom ||
          (isReplacement ? "Nouvel appareil installé" : evt.result),
        badgeTone: tone,
        badgeLabel: evt.severity
          ? `${evt.result} · ${evt.severity}`
          : evt.result,
        severity: evt.severity,
        comment: evt.comment,
        authorOrRef: `Intervention ${evt.id}${evt.requestId ? ` (Demande ${evt.requestId})` : ""}`,
        isPriorToCurrentAppliance: isPrior,
        rawEvent: evt,
      });
    });

    // 3. Commentaires & Demandes locataires liées
    linkedRequests.forEach((req) => {
      items.push({
        id: `req-${req.id}`,
        type: "tenant_request",
        date: req.date,
        title: `Commentaire / Signalement locataire : ${req.subject}`,
        subtitle: `Motif : ${req.motif} · Parties ${req.parts.toLowerCase()}`,
        badgeTone: "amber",
        badgeLabel: "Signalement locataire",
        comment: req.text,
        authorOrRef: `Demande locataire ${req.id} (Logement ${req.housingId})`,
        rawRequest: req,
      });
    });

    // 4. Demandes locataires du même logement (contexte)
    contextRequests.forEach((req) => {
      items.push({
        id: `ctx-req-${req.id}`,
        type: "tenant_request",
        date: req.date,
        title: `Avis locataire logement : ${req.subject}`,
        subtitle: `Signalement connexe · ${req.motif}`,
        badgeTone: "neutral",
        badgeLabel: "Avis à rapprocher",
        comment: req.text,
        authorOrRef: `Demande ${req.id}`,
        rawRequest: req,
      });
    });

    // 5. Rapports prestataires trimestriels
    reports.forEach((rep) => {
      const approxDate = `${rep.year ?? 2025}-${String(rep.quarter * 3).padStart(2, "0")}-28T00:00:00`;
      items.push({
        id: rep.id,
        type: "report",
        date: approxDate,
        title: `Rapport de suivi prestataire · T${rep.quarter} ${rep.year ?? 2025}`,
        subtitle: `Extrait d'audit trimestriel${rep.page ? ` (page ${rep.page})` : ""}`,
        badgeTone: "blue",
        badgeLabel: `Audit T${rep.quarter}`,
        comment: rep.text,
        authorOrRef: rep.url,
        rawReport: rep,
      });
    });

    // Tri anti-chronologique (le plus récent en haut)
    return items.sort((a, b) => b.date.localeCompare(a.date));
  }, [
    equipment,
    interventions,
    currentInterventions,
    linkedRequests,
    contextRequests,
    reports,
  ]);

  // Filtrage selon onglet et texte
  const filteredItems = useMemo(() => {
    return allTimelineItems.filter((item) => {
      // Masquage éventuel des événements de l'appareil précédent
      if (!showOldAppliances && item.isPriorToCurrentAppliance) {
        return false;
      }

      // Filtre par catégorie
      if (filterType === "incident" && item.type !== "incident") return false;
      if (filterType === "maintenance" && item.type !== "maintenance")
        return false;
      if (filterType === "tenant" && item.type !== "tenant_request")
        return false;
      if (filterType === "report" && item.type !== "report") return false;

      // Recherche texte dans titre, commentaire, sous-titre
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const inTitle = item.title.toLowerCase().includes(query);
        const inComment = item.comment?.toLowerCase().includes(query) ?? false;
        const inSubtitle =
          item.subtitle?.toLowerCase().includes(query) ?? false;
        const inRef = item.authorOrRef?.toLowerCase().includes(query) ?? false;
        return inTitle || inComment || inSubtitle || inRef;
      }

      return true;
    });
  }, [allTimelineItems, filterType, searchQuery, showOldAppliances]);

  // Compteurs pour les onglets
  const counts = useMemo(() => {
    const list = showOldAppliances
      ? allTimelineItems
      : allTimelineItems.filter((i) => !i.isPriorToCurrentAppliance);

    return {
      all: list.length,
      incident: list.filter((i) => i.type === "incident").length,
      tenant: list.filter((i) => i.type === "tenant_request").length,
      maintenance: list.filter((i) => i.type === "maintenance").length,
      report: list.filter((i) => i.type === "report").length,
      priorCount: allTimelineItems.filter((i) => i.isPriorToCurrentAppliance)
        .length,
    };
  }, [allTimelineItems, showOldAppliances]);

  return (
    <div className="interactive-timeline-module">
      <div className="timeline-header-controls">
        <div className="timeline-title-row">
          <div>
            <h3>Frise Interactive de la Vie de l'Équipement</h3>
            <p>
              Parcourez l'historique de l'appareil depuis sa pose, les pannes
              déclarées, les retours locataires et les visites de maintenance.
            </p>
          </div>
          {counts.priorCount > 0 && (
            <button
              className="toggle-prior-btn"
              onClick={() => setShowOldAppliances(!showOldAppliances)}
            >
              {showOldAppliances ? (
                <ChevronUp size={15} />
              ) : (
                <ChevronDown size={15} />
              )}
              {showOldAppliances
                ? "Masquer les données de l'appareil précédent"
                : `Inclure l'appareil précédent (${counts.priorCount})`}
            </button>
          )}
        </div>

        {/* Barre d'onglets de filtres interactifs */}
        <div className="timeline-filter-tabs">
          <button
            className={`tab-btn ${filterType === "all" ? "active" : ""}`}
            onClick={() => setFilterType("all")}
          >
            <span>Tous les jalons</span>
            <strong>{counts.all}</strong>
          </button>
          <button
            className={`tab-btn ${filterType === "incident" ? "active incident" : ""}`}
            onClick={() => setFilterType("incident")}
          >
            <AlertTriangle size={15} />
            <span>Incidents & Pannes</span>
            <strong>{counts.incident}</strong>
          </button>
          <button
            className={`tab-btn ${filterType === "tenant" ? "active tenant" : ""}`}
            onClick={() => setFilterType("tenant")}
          >
            <MessageSquare size={15} />
            <span>Avis & Retours locataires</span>
            <strong>{counts.tenant}</strong>
          </button>
          <button
            className={`tab-btn ${filterType === "maintenance" ? "active maintenance" : ""}`}
            onClick={() => setFilterType("maintenance")}
          >
            <Wrench size={15} />
            <span>Entretiens préventifs</span>
            <strong>{counts.maintenance}</strong>
          </button>
          <button
            className={`tab-btn ${filterType === "report" ? "active report" : ""}`}
            onClick={() => setFilterType("report")}
          >
            <FileText size={15} />
            <span>Rapports prestataires</span>
            <strong>{counts.report}</strong>
          </button>
        </div>

        {/* Barre de recherche dans l'historique */}
        <div className="timeline-search-bar">
          <Search size={15} />
          <input
            placeholder="Rechercher dans les commentaires, pièces, symptômes…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button className="clear-search" onClick={() => setSearchQuery("")}>
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Frise chronologique visuelle */}
      <div className="timeline-vertical-flow">
        {filteredItems.map((item, index) => {
          const isExpanded = !!expandedItems[item.id];
          const hasExpandableContent =
            !!item.comment && item.comment.length > 100;

          return (
            <div
              key={item.id}
              className={`timeline-node ${item.type} ${item.isPriorToCurrentAppliance ? "prior-appliance" : ""}`}
            >
              {/* Point jalon sur la ligne temporelle */}
              <div className="timeline-dot-pin">
                {item.type === "pose" && <Calendar size={15} />}
                {item.type === "incident" && <AlertTriangle size={15} />}
                {item.type === "maintenance" && <ShieldCheck size={15} />}
                {item.type === "tenant_request" && <MessageSquare size={15} />}
                {item.type === "report" && <FileText size={15} />}
                {item.type === "replacement" && <RefreshCw size={15} />}
              </div>

              {/* Carte de contenu de l'événement */}
              <div className="timeline-card-content">
                <div className="card-top-meta">
                  <div className="item-date">
                    <Clock size={13} />
                    <time dateTime={item.date}>
                      {dateLabel(item.date, true)}
                    </time>
                  </div>
                  <div className="tags-cluster">
                    {item.badgeLabel && (
                      <Badge tone={item.badgeTone}>{item.badgeLabel}</Badge>
                    )}
                    {item.isPriorToCurrentAppliance && (
                      <span className="prior-badge">Appareil antérieur</span>
                    )}
                  </div>
                </div>

                <div className="item-main-title">
                  <h4>{item.title}</h4>
                  {item.subtitle && (
                    <p className="item-subtitle">{item.subtitle}</p>
                  )}
                </div>

                {/* Commentaire technicien ou texte de la réclamation locataire */}
                {item.comment && (
                  <div className={`item-comment-box ${item.type}`}>
                    {item.type === "tenant_request" && (
                      <div className="comment-author-badge">
                        <User size={13} />
                        <span>Signalement du locataire</span>
                      </div>
                    )}
                    {item.type === "incident" && (
                      <div className="comment-author-badge warning">
                        <Wrench size={13} />
                        <span>Compte-rendu d'intervention prestataire</span>
                      </div>
                    )}
                    <p
                      className={`comment-text ${!isExpanded && hasExpandableContent ? "clamped" : ""}`}
                    >
                      « {item.comment} »
                    </p>

                    {hasExpandableContent && (
                      <button
                        className="expand-comment-toggle"
                        onClick={() => toggleExpand(item.id)}
                      >
                        {isExpanded
                          ? "Réduire le texte"
                          : "Lire tout le compte-rendu…"}
                      </button>
                    )}
                  </div>
                )}

                {/* Métadonnées en pied de carte */}
                <div className="item-footer-ref">
                  <small>{item.authorOrRef}</small>
                  {item.rawReport && (
                    <a
                      href={
                        item.rawReport.url +
                        (item.rawReport.page
                          ? "#page=" + item.rawReport.page
                          : "")
                      }
                      target="_blank"
                      rel="noreferrer"
                      className="report-download-link"
                    >
                      <ExternalLink size={13} />
                      Consulter le PDF original
                    </a>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {filteredItems.length === 0 && (
          <div className="timeline-empty-notice">
            <Filter size={24} />
            <p>
              Aucun événement ne correspond à ce filtre ou à votre recherche.
            </p>
            <button
              className="button subtle"
              onClick={() => {
                setFilterType("all");
                setSearchQuery("");
              }}
            >
              Réinitialiser les filtres
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
