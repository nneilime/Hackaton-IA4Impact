import { useState, useMemo } from "react";
import { Link } from "react-router";
import {
  AlertTriangle,
  ArrowRight,
  Clock,
  Coins,
  Flame,
  Search,
  SlidersHorizontal,
  Wrench,
} from "lucide-react";
import { useAppData } from "../../data/store";
import { euros, replacementRange, type EconomicEquipment } from "../../domain/economics";

interface Props {
  equipmentList: EconomicEquipment[];
  residenceFilter?: string;
}

export function ReplacementPriorityList({
  equipmentList = [],
  residenceFilter = "",
}: Props) {
  const { catalog } = useAppData();
  const [filterType, setFilterType] = useState<"all" | "ratio50" | "expired" | "repeated">("all");
  const [search, setSearch] = useState("");
  const [limit, setLimit] = useState(15);

  // Équipements scorés selon la corrélation durée de vie / pannes / prix de remplacement
  const scoredItems = useMemo(() => {
    return equipmentList
      .filter((e) => !residenceFilter || e.residenceId === residenceFilter)
      .map((eq) => {
        const catalogItem = catalog.equipment.find((c) => c.id === eq.equipmentId);
        const ageYears = catalogItem?.ageYears ?? null;
        const referenceLifeYears = catalogItem?.referenceLifeYears ?? 15;
        const lifeRatio = ageYears && referenceLifeYears ? ageYears / referenceLifeYears : 0;
        const repairs = eq.repairCount12m ?? 0;
        const simulatedCost = eq.simulatedRepairCost12m ?? 0;
        const replacementMin = eq.replacementMin ?? 1500;
        const costRatio =
          eq.repairReplacementRatioMin ??
          (replacementMin > 0 ? simulatedCost / replacementMin : 0);

        // 1. Usure par rapport à la durée de vie (0 à 40 pts)
        const lifeScore = Math.min(40, Math.round(lifeRatio * 40));

        // 2. Fréquence des pannes récentes (0 à 35 pts)
        const repairScore = Math.min(35, repairs * 12);

        // 3. Poids financier des réparations face au prix du neuf (0 à 25 pts)
        const financialScore = Math.min(25, Math.round(costRatio * 50));

        // Score global de pertinence de remplacement (0 à 100)
        const priorityScore = Math.min(100, lifeScore + repairScore + financialScore);

        // Niveau d'urgence et motif
        let urgency: "critical" | "high" | "moderate";
        let reason: string;

        if (costRatio >= 0.5) {
          urgency = "critical";
          reason = `Réparations à ${Math.round(costRatio * 100)} % du prix neuf (seuil critique atteint)`;
        } else if (lifeRatio >= 1.0 && repairs >= 2) {
          urgency = "critical";
          reason = `Fin de vie dépassée (${Math.round(lifeRatio * 100)} %) avec ${repairs} pannes subies`;
        } else if (priorityScore >= 60 || repairs >= 3) {
          urgency = "high";
          reason = `Forte récurrence de pannes et usure avancée (${Math.round(lifeRatio * 100)} % de vie)`;
        } else {
          urgency = "moderate";
          reason = `Équipement vieillissant à surveiller avant renouvellement`;
        }

        return {
          ...eq,
          catalogItem,
          ageYears,
          referenceLifeYears,
          lifeRatio,
          repairs,
          simulatedCost,
          costRatio,
          priorityScore,
          urgency,
          reason,
        };
      })
      // On conserve les équipements qui ont un signal d'usure ou de panne
      .filter((item) => item.repairs >= 1 || item.lifeRatio >= 0.6 || item.costRatio >= 0.25)
      .sort((a, b) => b.priorityScore - a.priorityScore);
  }, [equipmentList, residenceFilter, catalog.equipment]);

  // Filtrage selon onglet et recherche
  const filteredItems = useMemo(() => {
    return scoredItems.filter((item) => {
      if (filterType === "ratio50" && item.costRatio < 0.5) return false;
      if (filterType === "expired" && item.lifeRatio < 1.0) return false;
      if (filterType === "repeated" && item.repairs < 2) return false;
      if (search) {
        const query = search.toLowerCase();
        const text = `${item.equipmentId} ${item.label} ${item.residenceId} ${item.housingId || ""}`.toLowerCase();
        if (!text.includes(query)) return false;
      }
      return true;
    });
  }, [scoredItems, filterType, search]);

  const countRatio50 = scoredItems.filter((i) => i.costRatio >= 0.5).length;
  const countExpired = scoredItems.filter((i) => i.lifeRatio >= 1.0).length;
  const countRepeated = scoredItems.filter((i) => i.repairs >= 2).length;

  return (
    <section className="surface economic-section replacement-priority-section">
      <div className="card-heading">
        <div>
          <h2>
            <Flame size={20} className="section-title-icon text-red" />
            Priorisation des remplacements à l’unité
          </h2>
          <p className="card-subheading">
            Classement croisant la <strong>durée de vie</strong>, la <strong>récurrence des dépannages</strong> et le <strong>coût cumulé face au prix du neuf</strong>.
          </p>
        </div>
        <span className="count-tag">{filteredItems.length} équipements analysés</span>
      </div>

      {/* Onglets de filtres rapides d'alerte */}
      <div className="replacement-filters-bar">
        <div className="scope-tabs" aria-label="Filtres de priorisation">
          <button
            className={filterType === "all" ? "active" : ""}
            onClick={() => setFilterType("all")}
          >
            Tous les prioritaires ({scoredItems.length})
          </button>
          <button
            className={filterType === "ratio50" ? "active" : ""}
            onClick={() => setFilterType("ratio50")}
          >
            Alerte : Réparations ≥ 50 % du neuf ({countRatio50})
          </button>
          <button
            className={filterType === "expired" ? "active" : ""}
            onClick={() => setFilterType("expired")}
          >
            Durée de vie dépassée ({countExpired})
          </button>
          <button
            className={filterType === "repeated" ? "active" : ""}
            onClick={() => setFilterType("repeated")}
          >
            Pannes répétées ≥ 2 ({countRepeated})
          </button>
        </div>

        <div className="search-field">
          <Search size={16} />
          <input
            placeholder="Filtrer par équipement, logement…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="economic-table-wrap">
        <table className="economic-table priority-replacement-table">
          <thead>
            <tr>
              <th>Équipement</th>
              <th>Durée de vie & Usure</th>
              <th>Pannes 12 mois</th>
              <th>Réparations cumulées vs Prix neuf</th>
              <th>Diagnostic & Priorité</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredItems.slice(0, limit).map((e) => (
              <tr key={e.equipmentId} className={`priority-row priority-${e.urgency}`}>
                <td>
                  <Link to={`/equipements/${e.equipmentId}`}>
                    <strong>{e.label}</strong>
                    <small>
                      {e.equipmentId} · {e.residenceId.replace("RES-", "Résidence ")} ·{" "}
                      {e.housingId || e.buildingId}
                    </small>
                  </Link>
                </td>

                {/* Usure et durée de vie */}
                <td>
                  <div className="life-progress-cell">
                    <strong>
                      {e.ageYears ? `${Math.round(e.ageYears * 10) / 10} ans` : "Inconnu"}
                      <span className="text-muted"> / {e.referenceLifeYears} ans</span>
                    </strong>
                    <div className="life-bar-wrap">
                      <div
                        className={`life-bar-fill ${e.lifeRatio >= 1.0 ? "life-bar-expired" : e.lifeRatio >= 0.75 ? "life-bar-critical" : ""}`}
                        style={{ width: `${Math.min(100, Math.round(e.lifeRatio * 100))}%` }}
                      />
                    </div>
                    <small className={e.lifeRatio >= 1.0 ? "text-red font-semibold" : ""}>
                      {e.lifeRatio >= 1.0
                        ? `Fin de vie dépassée (${Math.round(e.lifeRatio * 100)} %)`
                        : `${Math.round(e.lifeRatio * 100)} % de vie consommée`}
                    </small>
                  </div>
                </td>

                {/* Dépannages */}
                <td>
                  <span className={`repairs-count-badge ${e.repairs >= 2 ? "repairs-high" : ""}`}>
                    {e.repairs} passage{e.repairs > 1 ? "s" : ""}
                  </span>
                  {e.repairs >= 2 && <small className="text-red d-block mt-1">Pannes récurrentes</small>}
                </td>

                {/* Réparations vs Prix Neuf */}
                <td>
                  <div className="cost-ratio-cell">
                    <strong>{euros(e.simulatedCost)}</strong>
                    <small>sur {replacementRange(e)} neuf</small>
                    <span className={`cost-ratio-pill ${e.costRatio >= 0.5 ? "ratio-pill-danger" : e.costRatio >= 0.35 ? "ratio-pill-warning" : ""}`}>
                      {Math.round(e.costRatio * 100)} % du neuf
                    </span>
                  </div>
                </td>

                {/* Indice & Verdict */}
                <td>
                  <div className="verdict-cell">
                    <span
                      className={`urgency-badge ${
                        e.urgency === "critical"
                          ? "badge-critical"
                          : e.urgency === "high"
                            ? "badge-high"
                            : "badge-moderate"
                      }`}
                    >
                      {e.urgency === "critical"
                        ? "Remplacement prioritaire"
                        : e.urgency === "high"
                          ? "Remplacement à planifier"
                          : "À surveiller"}
                    </span>
                    <small className="verdict-reason">{e.reason}</small>
                  </div>
                </td>

                {/* Action */}
                <td>
                  <Link
                    className="button secondary compact open-file-btn"
                    to={`/equipements/${e.equipmentId}`}
                  >
                    Examiner <ArrowRight size={13} />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!filteredItems.length && (
        <p className="empty-filter-note">
          Aucun équipement ne correspond à ces critères dans la résidence sélectionnée.
        </p>
      )}

      {filteredItems.length > limit && (
        <div className="see-more-wrap">
          <button
            className="button secondary"
            onClick={() => setLimit((n) => n + 20)}
          >
            Afficher plus d’équipements ({filteredItems.length - limit} restants)
          </button>
        </div>
      )}

      <p className="fine-print">
        Le score de priorité combine la part de durée de vie consommée (40 %), la fréquence des pannes récentes (35 %) et le ratio de réparation face au prix du neuf (25 %). Un ratio supérieur à 50 % déclenche automatiquement une alerte prioritaire de remplacement.
      </p>
    </section>
  );
}
