import { useState, useMemo } from "react";
import { Link } from "react-router";
import {
  Building2,
  TrendingUp,
  Scale,
  CalendarCheck,
  CheckCircle2,
  AlertTriangle,
  Coins,
  ArrowRight,
  Info,
} from "lucide-react";
import { useAppData } from "../../data/store";
import { euros } from "../../domain/economics";
import type { EconomicEquipment } from "../../domain/economics";

interface Props {
  equipmentList?: EconomicEquipment[];
  currentYear: number;
  renovationBudget: number;
}

export function ResidenceGroupedReplacement({
  equipmentList = [],
  currentYear,
  renovationBudget,
}: Props) {
  const { catalog } = useAppData();

  // Résidence sélectionnée (Résidence A par défaut comme recommandé par le client)
  const defaultResidenceId =
    catalog.residences.find((r) => r.id === "RES-A")?.id ||
    catalog.residences[0]?.id ||
    "";
  const [selectedResidenceId, setSelectedResidenceId] = useState(defaultResidenceId);

  // Hypothèses de marché (avec valeurs par défaut réalistes et justifiables)
  const [discountPercent, setDiscountPercent] = useState(25); // -25% en marché groupé
  const [unitReplacementPrice, setUnitReplacementPrice] = useState(2400); // Prix au cas par cas
  const [unitRepairPrice, setUnitRepairPrice] = useState(480); // Dépannage moyen d'urgence
  const [projectedYears, setProjectedYears] = useState(3); // Horizon de projection

  const residence = catalog.residences.find((r) => r.id === selectedResidenceId);

  // Équipements de cette résidence
  const residenceEquipment = useMemo(() => {
    return catalog.equipment.filter((e) => e.residenceId === selectedResidenceId);
  }, [catalog.equipment, selectedResidenceId]);

  // Famille dominante d'équipements de chauffage / production (ex: Chaudière gaz)
  const mainFamily = useMemo(() => {
    const counts = new Map<string, number>();
    for (const eq of residenceEquipment) {
      counts.set(eq.family, (counts.get(eq.family) || 0) + 1);
    }
    let top = "chaudiere_gaz_individuelle";
    let max = 0;
    for (const [fam, count] of counts.entries()) {
      if (count > max) {
        max = count;
        top = fam;
      }
    }
    return top;
  }, [residenceEquipment]);

  // Équipements ciblés par la rénovation (équipements inScope ou de la famille principale)
  const targetEquipment = useMemo(() => {
    const inScope = residenceEquipment.filter((e) => e.inScope);
    if (inScope.length) return inScope;
    return residenceEquipment.filter((e) => e.family === mainFamily);
  }, [residenceEquipment, mainFamily]);

  // Nombre de logements de la résidence
  const housingCount = residence?.housingCount || targetEquipment.length || 100;

  // Dépannages constatés sur l'équipement cible sur les 12 derniers mois
  const recentRepairsCount = useMemo(() => {
    return targetEquipment.reduce((acc, eq) => acc + (eq.recentRepairCount || 0), 0);
  }, [targetEquipment]);

  // Équipements ayant déjà 2 pannes ou plus
  const repeatedRepairsCount = useMemo(() => {
    return targetEquipment.filter((e) => (e.recentRepairCount || 0) >= 2).length;
  }, [targetEquipment]);

  // Âge moyen de l'équipement ciblé (chaudières posées en 2016 pour Résidence A = ~9.7 ans)
  const avgAge = useMemo(() => {
    const validAges = targetEquipment
      .map((e) => e.ageYears)
      .filter((a): a is number => a !== null && a !== undefined);
    if (!validAges.length) return 10;
    return Math.round((validAges.reduce((a, b) => a + b, 0) / validAges.length) * 10) / 10;
  }, [targetEquipment]);

  // Label lisible de la famille
  const mainFamilyLabel = targetEquipment[0]?.label || "Chaudière gaz individuelle";

  // --- CALCULS COMPARATIFS RIGOUREUX ENTRE LES DEUX OPTIONS STRATÉGIQUES ---

  // 1. SCÉNARIO 2 : MARCHÉ GROUPÉ NÉGOCIÉ (remplacement des N équipements d'un coup avec remise)
  const groupedUnitPrice = Math.round(unitReplacementPrice * (1 - discountPercent / 100));
  const groupedTotalCost = housingCount * groupedUnitPrice; // Ex: 160 x 1800 € = 288 000 €

  // 2. SCÉNARIO 1 : AU FIL DE L'EAU (remplacements au cas par cas au prix fort + dépannages d'urgence)
  // Remplacer les N équipements un par un en urgence au tarif fort :
  const individualReplacementsTotalCost = housingCount * unitReplacementPrice; // Ex: 160 x 2400 € = 384 000 €

  // Surcoût des dépannages d'urgence et astreintes répétés subis en attendant le remplacement de chaque appareil :
  const estimatedAnnualRepairs = Math.max(
    recentRepairsCount,
    Math.round(housingCount * 0.15)
  );
  const urgentRepairsTotalCost = estimatedAnnualRepairs * unitRepairPrice * projectedYears; // Ex: ~36 000 €

  // Coût total réel de l'option Au fil de l'eau :
  const totalFilDeLEauCost = individualReplacementsTotalCost + urgentRepairsTotalCost; // Ex: 384 000 + 36 000 = 420 000 €

  // ÉCONOMIES RÉELLES POUR IN'LI SUD-OUEST :
  // Remise d'échelle immédiate sur les équipements :
  const immediateDiscountSavings = individualReplacementsTotalCost - groupedTotalCost; // +96 000 €
  // Bilan net global (équipements négociés + dépannages évités) :
  const netSavings = totalFilDeLEauCost - groupedTotalCost; // +132 000 €

  // Seuil de bascule en volume de pannes :
  // En dessous de 12 % du parc en panne par an, l'usure reste dans la normale de fonctionnement.
  // Dès que les pannes dépassent 12 % du parc par an (ou dès 9 ans d'âge), le maintien au fil de l'eau devient déficitaire.
  const breakEvenFailuresPerYear = Math.max(
    10,
    Math.round(housingCount * 0.12)
  );

  const isAgeThresholdReached = avgAge >= 9;
  const isFailureThresholdReached =
    recentRepairsCount >= breakEvenFailuresPerYear || repeatedRepairsCount >= 5;
  const isThresholdReached = isAgeThresholdReached || isFailureThresholdReached;

  // Recommandation d'année budgétaire
  const recommendedYear = isThresholdReached ? currentYear : currentYear + 1;
  const budgetSharePercent = Math.round((groupedTotalCost / (renovationBudget || 1500000)) * 100);

  return (
    <section className="surface residence-grouped-section">
      <div className="card-heading">
        <div>
          <span className="eyebrow">ARBITRAGE STRATÉGIQUE DIRECTION</span>
          <h2>Remplacement à l’unité ou Rénovation globale groupée ?</h2>
        </div>
        <span className="quiet-label">Aide à la décision pluriannuelle</span>
      </div>

      <p className="residence-grouped-intro">
        Sur une résidence de logements homogènes, BâtIA compare le coût des dépannages
        au fil de l’eau face à un marché de remplacement groupé négocié pour l’ensemble du bâtiment.
      </p>

      {/* Sélecteur de Résidence et Paramètres */}
      <div className="residence-grouped-controls">
        <label>
          Résidence analysée
          <select
            value={selectedResidenceId}
            onChange={(e) => setSelectedResidenceId(e.target.value)}
          >
            {catalog.residences.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} ({r.housingCount} logements · {r.energyHeating || "Gaz"})
              </option>
            ))}
          </select>
        </label>

        <label>
          Hypothèse remise marché groupé (%)
          <input
            type="number"
            min="5"
            max="50"
            step="5"
            value={discountPercent}
            onChange={(e) => setDiscountPercent(Math.max(5, Math.min(50, Number(e.target.value))))}
          />
        </label>

        <label>
          Prix remplacement unitaire (€ TTC)
          <input
            type="number"
            min="500"
            step="100"
            value={unitReplacementPrice}
            onChange={(e) => setUnitReplacementPrice(Math.max(500, Number(e.target.value)))}
          />
        </label>

        <label>
          Coût moyen dépannage d’urgence (€ TTC)
          <input
            type="number"
            min="100"
            step="50"
            value={unitRepairPrice}
            onChange={(e) => setUnitRepairPrice(Math.max(100, Number(e.target.value)))}
          />
        </label>

        <label>
          Horizon de projection
          <select
            value={projectedYears}
            onChange={(e) => setProjectedYears(Number(e.target.value))}
          >
            <option value={2}>2 ans</option>
            <option value={3}>3 ans (recommandé)</option>
            <option value={5}>5 ans</option>
          </select>
        </label>
      </div>

      {/* État de la résidence sélectionnée */}
      <div className="residence-context-banner">
        <div className="residence-context-item">
          <span className="context-label">Patrimoine homogène</span>
          <strong>{residence?.name || selectedResidenceId}</strong>
          <span>{housingCount} logements · {mainFamilyLabel}</span>
        </div>
        <div className="residence-context-item">
          <span className="context-label">Âge du parc</span>
          <strong>~{avgAge} ans d'ancienneté</strong>
          <span>{avgAge >= 9 ? "Période d'usure critique (posé en 2016)" : "Parc en fonctionnement"}</span>
        </div>
        <div className="residence-context-item">
          <span className="context-label">Historique 12 mois</span>
          <strong>{recentRepairsCount} dépannages constatés</strong>
          <span>{repeatedRepairsCount} équipements avec pannes répétées</span>
        </div>
        <div className="residence-context-item">
          <span className="context-label">Prix négocié groupé</span>
          <strong className="text-blue">{euros(groupedUnitPrice)} / logt</strong>
          <span>Remise groupée de {discountPercent} %</span>
        </div>
      </div>

      {/* Comparaison des deux scénarios côte à côte */}
      <div className="scenarios-comparison-grid">
        {/* Scénario 1 : Au fil de l'eau */}
        <div className="scenario-card scenario-fil-de-leau">
          <div className="scenario-header">
            <span className="scenario-badge">Scénario 1</span>
            <h3>Au fil de l’eau (Cas par cas)</h3>
            <p className="scenario-subtitle">
              Remplacements un par un au tarif fort + dépannages d'urgence répétés
            </p>
          </div>

          <div className="scenario-pricing">
            <span className="scenario-cost-label">Coût projeté sur {projectedYears} ans</span>
            <strong className="scenario-cost-value">{euros(totalFilDeLEauCost)}</strong>
            <span className="scenario-cost-sub">
              Remplacements au tarif fort ({euros(individualReplacementsTotalCost)}) + astreintes
            </span>
          </div>

          <ul className="scenario-points">
            <li>
              <strong>Remplacements d'urgence :</strong> {housingCount} logements × {euros(unitReplacementPrice)} = {euros(individualReplacementsTotalCost)}
            </li>
            <li>
              <strong>Dépannages d'urgence subis :</strong> ~{estimatedAnnualRepairs} pannes/an × {euros(unitRepairPrice)} × {projectedYears} ans = {euros(urgentRepairsTotalCost)} (déplacements, astreintes et pièces d’usure)
            </li>
            <li>
              <strong>Impact locataire :</strong> Pannes hivernales à répétition, manque d'eau chaude et gestion de crise
            </li>
          </ul>
        </div>

        {/* Scénario 2 : Remplacement groupé */}
        <div className="scenario-card scenario-grouped">
          <div className="scenario-header">
            <span className="scenario-badge badge-primary">Scénario 2 (Recommandé)</span>
            <h3>Remplacement groupé (Marché unique)</h3>
            <p className="scenario-subtitle">
              Remplacement planifié des {housingCount} équipements en une seule opération
            </p>
          </div>

          <div className="scenario-pricing">
            <span className="scenario-cost-label">Budget total négocié (-{discountPercent} %)</span>
            <strong className="scenario-cost-value text-blue">{euros(groupedTotalCost)}</strong>
            <span className="scenario-cost-sub">
              {euros(groupedUnitPrice)} TTC par logement tout compris
            </span>
          </div>

          <ul className="scenario-points">
            <li>
              <strong>Remise sur volume :</strong> Économie immédiate de +{euros(immediateDiscountSavings)} sur le marché global
            </li>
            <li>
              <strong>Garantie constructeur :</strong> 0 € de dépannages d'urgence sur les {projectedYears} prochaines années
            </li>
            <li>
              <strong>Confort locataire :</strong> Rénovation concertée, continuité de chauffe sans coupure imprévue
            </li>
          </ul>
        </div>
      </div>

      {/* Bilan financier et Seuil de bascule */}
      <div className="threshold-decision-box">
        <div className="threshold-header">
          <Scale size={22} className="threshold-icon" />
          <div>
            <h4>Seuil de bascule et Rentabilité</h4>
            <p>
              Le remplacement groupé devient l'arbitrage prioritaire dès que le parc dépasse{" "}
              <strong>9 ans d'âge</strong> (usure critique) ou dès que la résidence subit au moins{" "}
              <strong>{breakEvenFailuresPerYear} pannes par an</strong> (surcoût récurrent de maintenance).
            </p>
            <ul className="threshold-reasons-list">
              <li>
                <strong>Âge du parc ({avgAge} ans / seuil 9 ans) :</strong> À 60 % de la durée de vie de référence (15 ans), les pièces maîtresses (corps de chauffe, échangeur, cartes) entrent en obsolescence rapide.
              </li>
              <li>
                <strong>Volume de pannes ({recentRepairsCount} pannes constatées / seuil {breakEvenFailuresPerYear} pannes/an) :</strong> Au-delà de 12 % du parc en panne par an, réparer au fil de l'eau détruit de la valeur financière face à un marché négocié.
              </li>
            </ul>
          </div>
        </div>

        <div className="threshold-kpis">
          <div className="threshold-kpi">
            <span>Gain financier net sur {projectedYears} ans</span>
            <strong className="text-success">
              + {euros(netSavings)} d'économie
            </strong>
            <small>Dont +{euros(immediateDiscountSavings)} d'économie immédiate sur les équipements</small>
          </div>

          <div className="threshold-kpi">
            <span>Diagnostic BâtIA</span>
            <strong>
              {isThresholdReached ? (
                <span className="status-badge-critical">Seuil de bascule atteint</span>
              ) : (
                <span className="status-badge-moderate">Surveillance recommandée</span>
              )}
            </strong>
            <small>
              {isThresholdReached
                ? `Parc à ~${avgAge} ans · Rénovation prioritaire`
                : "Pannes modérées à date"}
            </small>
          </div>

          <div className="threshold-kpi">
            <span>Recommandation Direction</span>
            <strong className="text-blue">Programmer en {recommendedYear}</strong>
            <small>
              {euros(groupedTotalCost)} ({budgetSharePercent} % de l'enveloppe de 1,5 M€)
            </small>
          </div>
        </div>
      </div>
    </section>
  );
}
