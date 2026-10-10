import {
  AlertTriangle,
  Calendar,
  CheckCircle,
  Clock,
  Flame,
  ShieldAlert,
  Sparkles,
  Wrench,
} from "lucide-react";
import type { Equipment, ScoreResult } from "../../domain/types";
import { dateLabel } from "../../domain/rules";
import { DPE_COLORS, getDpeColor } from "../map/ToulouseMap";

interface HeroAgeCardProps {
  equipment: Equipment;
  rank?: number;
  totalRanked: number;
  housingDpe?: string | null;
  snapshotDate: string;
}

export function HeroAgeCard({
  equipment,
  rank,
  totalRanked,
  housingDpe,
  snapshotDate,
}: HeroAgeCardProps) {
  const age = equipment.ageYears;
  const refYears = equipment.referenceLifeYears;
  const isOverdue = age !== null && age > refYears;
  const overdueYears = age !== null && isOverdue ? age - refYears : 0;
  const overduePercent =
    age !== null && refYears > 0 ? Math.round((age / refYears) * 100) : 0;

  // Calcul du pourcentage pour la jauge visuelle (max scale 200% ou ratio)
  const maxScale = Math.max(refYears * 1.6, (age || refYears) * 1.15);
  const normalPercentWidth = Math.min(
    100,
    Math.round((refYears / maxScale) * 100),
  );
  const totalAgeWidth =
    age !== null
      ? Math.min(100, Math.round((age / maxScale) * 100))
      : normalPercentWidth;
  const overdueWidth = Math.max(0, totalAgeWidth - normalPercentWidth);

  const isTop10 = rank && rank <= Math.ceil(totalRanked * 0.1);

  return (
    <div
      className={`hero-age-card ${isOverdue ? "status-critical" : "status-nominal"}`}
    >
      {/* Bandeau d'accentuation supérieur */}
      <div className="hero-card-banner">
        <div className="hero-banner-left">
          <span className="banner-pill-label">
            {isOverdue ? (
              <>
                <AlertTriangle size={15} />
                DURÉE DE RÉFÉRENCE DÉPASSÉE
              </>
            ) : (
              <>
                <CheckCircle size={15} />
                {age === null
                  ? "ÂGE À VÉRIFIER"
                  : "DURÉE DE RÉFÉRENCE NON DÉPASSÉE"}
              </>
            )}
          </span>
          {isTop10 && (
            <span className="top-10-danger-badge">
              <span className="flame-dot" />
              Priorité Top 10% ({rank}ᵉ sur {totalRanked})
            </span>
          )}
        </div>

        {housingDpe && (
          <div className="hero-banner-right">
            <span
              className="housing-dpe-tag"
              style={{ backgroundColor: getDpeColor(housingDpe) }}
            >
              Logement DPE {housingDpe}
            </span>
          </div>
        )}
      </div>

      <div className="hero-card-body">
        {/* Colonne 1 : Âge en chiffres géants */}
        <div className="hero-age-metric-block">
          <span className="metric-super-label">
            ÂGE AU {dateLabel(snapshotDate)}
          </span>
          <div className="giant-age-display">
            <strong>
              {age !== null
                ? age.toLocaleString("fr-FR", {
                    minimumFractionDigits: 1,
                    maximumFractionDigits: 1,
                  })
                : "—"}
            </strong>
            <span className="unit-label">ans</span>
          </div>

          <div className="age-context-caption">
            {isOverdue ? (
              <span className="badge-alert-overdue">
                Dépassement de +
                {overdueYears.toLocaleString("fr-FR", {
                  maximumFractionDigits: 1,
                })}{" "}
                ans (+{overduePercent - 100}%)
              </span>
            ) : (
              <span className="badge-ok-sub">
                Durée de référence : {refYears} ans
              </span>
            )}
          </div>
        </div>

        {/* Colonne 2 : Jauge d'usure bicolore et jalons temporels */}
        <div className="hero-gauge-block">
          <div className="gauge-legend-row">
            <span>
              <strong>Cycle de vie :</strong>{" "}
              {dateLabel(equipment.installedAt, true)} ➔{" "}
              {dateLabel(snapshotDate)}
            </span>
            <span className="ratio-score">
              Ratio de vétusté :{" "}
              <strong>{(overduePercent / 100).toFixed(2)}x</strong> la durée
              normale
            </span>
          </div>

          {/* Barre visuelle bicolore */}
          <div className="life-progress-track">
            {/* Zone normale */}
            <div
              className="track-segment normal"
              style={{ width: `${normalPercentWidth}%` }}
              title={`Durée de vie normale constructeur (${refYears} ans)`}
            >
              <span className="segment-label">
                Durée normale : {refYears} ans
              </span>
            </div>

            {/* Zone de dépassement / risque */}
            {isOverdue && (
              <div
                className="track-segment overdue"
                style={{ width: `${overdueWidth}%` }}
                title={`Zone de dépassement critique (+${overdueYears.toFixed(1)} ans)`}
              >
                <span className="segment-label-overdue">
                  +{overdueYears.toFixed(1)} ans
                </span>
              </div>
            )}

            {/* Curseur actuel */}
            <div
              className="track-cursor"
              style={{ left: `${totalAgeWidth}%` }}
              title={`Âge actuel : ${age?.toFixed(1)} ans`}
            >
              <div className="cursor-pin" />
              <span className="cursor-balloon">{age?.toFixed(1)} ans</span>
            </div>
          </div>

          {/* Marqueurs sous la jauge */}
          <div className="gauge-axis-labels">
            <div>
              <small>Date de mise en service</small>
              <strong>{dateLabel(equipment.installedAt, true)}</strong>
            </div>
            <div>
              <small>Fin de vie théorique</small>
              <strong className={isOverdue ? "text-danger" : ""}>
                {equipment.installedAt
                  ? `${parseInt(equipment.installedAt.slice(0, 4), 10) + refYears}`
                  : `${refYears} ans`}
              </strong>
            </div>
            <div>
              <small>Situation actuelle</small>
              <strong>
                {dateLabel(snapshotDate)} ({age?.toFixed(1) ?? "—"} ans)
              </strong>
            </div>
          </div>
        </div>

        {/* Colonne 3 : Synthèse de décision immédiate */}
        <div className="hero-decision-summary">
          <div className="summary-card-inner">
            <small>Classement du modèle</small>
            <div className="verdict-rank-row">
              <span className="rank-num">#{rank || "—"}</span>
              <span className="rank-denom">sur {totalRanked}</span>
            </div>
            <p className="verdict-sentence">
              {isOverdue
                ? "L’âge dépasse la durée de référence. Un contrôle de l’état permet de préparer la décision."
                : "L’âge seul ne suffit pas à établir l’état de l’appareil. Consultez son historique et son score."}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
