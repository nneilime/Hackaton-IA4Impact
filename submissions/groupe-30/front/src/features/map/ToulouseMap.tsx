import { useEffect, useRef, useState, useMemo } from "react";
import { Link } from "react-router";
import L from "leaflet";
import {
  Building2,
  Calendar,
  Flame,
  Gauge,
  Home,
  Info,
  MapPin,
  Search,
  ShieldAlert,
  SlidersHorizontal,
  Sparkles,
  Wind,
  X,
  Zap,
  ArrowRight,
  ExternalLink,
  Activity,
  Layers,
} from "lucide-react";
import { useAppData } from "../../data/store";
import type { Housing, Residence, Equipment } from "../../domain/types";
import { numberLabel } from "../../domain/rules";
import { Badge } from "../../ui/components";

// Couleurs officielles DPE ADEME (gardées pour export et HeroAgeCard)
export const DPE_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  A: { bg: "#009944", text: "#ffffff", label: "A (≤ 70)" },
  B: { bg: "#33b347", text: "#ffffff", label: "B (71 - 110)" },
  C: { bg: "#99cc33", text: "#1a3800", label: "C (111 - 180)" },
  D: { bg: "#ffcc00", text: "#3d3000", label: "D (181 - 250)" },
  E: { bg: "#ff9900", text: "#ffffff", label: "E (251 - 330)" },
  F: { bg: "#ff3300", text: "#ffffff", label: "F (331 - 420)" },
  G: { bg: "#cc0000", text: "#ffffff", label: "G (> 420)" },
};

export function getDpeColor(dpe?: string | null): string {
  if (!dpe) return "#8c9ba5";
  return DPE_COLORS[dpe.toUpperCase()]?.bg || "#8c9ba5";
}

// Modèle unifié : DPE + Âge + Urgence de prévention
export interface CompositeScore {
  score: number; // 0 (sain / vert) à 100 (critique / rouge)
  dpeScore: number;
  ageScore: number;
  equipScore: number;
  color: string;
  level: "critical" | "high" | "moderate" | "low";
  label: string;
}

export function computeCompositeScore(
  dpeTag: string | null | undefined,
  constructionYear: number | undefined,
  equipRiskRatio: number // de 0 à 1 (taux d'équipements critiques ou présence d'équipement Top 10%)
): CompositeScore {
  // 1. Pilier DPE (0 à 100) : A=0, B=15, C=35, D=55, E=75, F=90, G=100
  const dpeValues: Record<string, number> = {
    A: 5, B: 18, C: 38, D: 58, E: 78, F: 92, G: 100,
  };
  const dpeScore = dpeValues[(dpeTag || "D").toUpperCase()] ?? 58;

  // 2. Pilier Âge (0 à 100) : 1968 (le plus ancien, 58 ans) = 96, 2016 (récent, 10 ans) = 15
  const year = constructionYear || 1985;
  const ageYears = Math.max(0, 2026 - year);
  const ageScore = Math.min(100, Math.max(10, Math.round((ageYears / 58) * 100)));

  // 3. Pilier Équipements & Pannes (0 à 100)
  const equipScore = Math.min(100, Math.max(0, Math.round(equipRiskRatio * 100)));

  // Score pondéré unifié : 35% DPE + 35% Âge + 30% Équipements
  const score = Math.min(100, Math.round(0.35 * dpeScore + 0.35 * ageScore + 0.30 * equipScore));

  // Plus c'est vieux, mauvais en DPE et en urgence, plus c'est ROUGE !
  let color = "#10b981"; // Vert émeraude
  let level: "critical" | "high" | "moderate" | "low" = "low";
  let label = "Faible risque";

  if (score >= 75) {
    color = "#e92549"; // Rouge vif Action Logement (Urgence maximale)
    level = "critical";
    label = "Urgence critique";
  } else if (score >= 58) {
    color = "#f97316"; // Orange soutenu (Risque élevé)
    level = "high";
    label = "Risque élevé";
  } else if (score >= 40) {
    color = "#f59e0b"; // Jaune / Ambre (Vigilance)
    level = "moderate";
    label = "Vigilance";
  }

  return {
    score,
    dpeScore,
    ageScore,
    equipScore,
    color,
    level,
    label,
  };
}

export function ToulouseMap() {
  const { catalog, ranks, result } = useAppData();
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);

  const [selectedResidenceId, setSelectedResidenceId] = useState<string | null>("RES-F");
  const [levelFilter, setLevelFilter] = useState<string>("all");
  const [housingSearch, setHousingSearch] = useState("");
  const [housingLevelFilter, setHousingLevelFilter] = useState("all");

  const residences = catalog.residences || [];
  const housings = catalog.housings || [];

  // Calcul du score unifié pour chaque résidence
  const residenceScores = useMemo(() => {
    const totalScores = Object.keys(result.scores).length;
    const cut = Math.ceil(totalScores * 0.1);
    const map: Record<string, { composite: CompositeScore; totalEquip: number; highRiskCount: number }> = {};

    residences.forEach((r) => {
      const equips = catalog.equipment.filter((e) => e.residenceId === r.id && e.inScope);
      const highRisk = equips.filter((e) => {
        const rank = ranks.get(e.id);
        return rank && rank <= cut;
      });

      // Ratio d'équipements sous pression (normalisé sur la base de la métropole)
      const ratio = equips.length > 0 ? Math.min(1, (highRisk.length / equips.length) * 3) : 0;
      const composite = computeCompositeScore(r.dpeTag, r.constructionYear, ratio);

      map[r.id] = {
        composite,
        totalEquip: equips.length,
        highRiskCount: highRisk.length,
      };
    });
    return map;
  }, [catalog.equipment, residences, ranks, result.scores]);

  // Initialisation de la carte Leaflet SANS AUCUNE CLÉ API (OpenStreetMap standard / France)
  useEffect(() => {
    if (!mapContainerRef.current) return;
    if (mapInstanceRef.current) return;

    // Toulouse coordinates
    const map = L.map(mapContainerRef.current, {
      center: [43.595, 1.425],
      zoom: 12,
      zoomControl: true,
      scrollWheelZoom: true,
    });

    // 100% GRATUIT, AUCUNE CLÉ API REQUISE : OpenStreetMap officiel
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);

    markersLayerRef.current = L.layerGroup().addTo(map);
    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Affichage des marqueurs avec le code couleur unifié (Vert -> Rouge)
  useEffect(() => {
    const map = mapInstanceRef.current;
    const layer = markersLayerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();

    residences.forEach((res) => {
      if (!res.lat || !res.lng) return;

      const data = residenceScores[res.id];
      if (!data) return;

      const { composite, highRiskCount } = data;
      if (levelFilter !== "all" && composite.level !== levelFilter) return;

      const isSelected = res.id === selectedResidenceId;
      const isCritical = composite.level === "critical";

      const iconHtml = `
        <div class="custom-map-marker unified ${isSelected ? "selected" : ""} ${isCritical ? "critical-halo" : ""}" style="--marker-color: ${composite.color};">
          <div class="marker-pin">
            <span class="marker-badge">${composite.score}</span>
          </div>
          <div class="marker-tooltip">
            <strong>${res.name}</strong>
            <small>${composite.label} · ${highRiskCount} pannes prévues</small>
          </div>
        </div>
      `;

      const customIcon = L.divIcon({
        className: "leaflet-div-marker-wrapper",
        html: iconHtml,
        iconSize: [44, 44],
        iconAnchor: [22, 42],
        popupAnchor: [0, -44],
      });

      const marker = L.marker([res.lat, res.lng], { icon: customIcon });

      marker.on("click", () => {
        setSelectedResidenceId(res.id);
        map.flyTo([res.lat!, res.lng!], 14, { duration: 0.8 });
      });

      marker.addTo(layer);
    });
  }, [residences, residenceScores, levelFilter, selectedResidenceId]);

  const selectedResidence = useMemo(() => {
    return residences.find((r) => r.id === selectedResidenceId) || residences[0];
  }, [residences, selectedResidenceId]);

  const selectedScoreData = useMemo(() => {
    if (!selectedResidence) return null;
    return residenceScores[selectedResidence.id];
  }, [selectedResidence, residenceScores]);

  const selectedResidenceHousings = useMemo(() => {
    if (!selectedResidence) return [];
    return housings.filter((h) => h.residenceId === selectedResidence.id);
  }, [housings, selectedResidence]);

  // Équipements de la résidence
  const selectedResidenceEquipments = useMemo(() => {
    if (!selectedResidence) return [];
    return catalog.equipment.filter((e) => e.residenceId === selectedResidence.id);
  }, [catalog.equipment, selectedResidence]);

  // Calcul du score unifié pour chaque logement individuel
  const housingsWithScore = useMemo(() => {
    const totalScores = Object.keys(result.scores).length;
    const cut = Math.ceil(totalScores * 0.1);

    return selectedResidenceHousings.map((h) => {
      const equips = selectedResidenceEquipments.filter((e) => e.housingId === h.id);
      const hasTop10Equip = equips.some((e) => {
        const r = ranks.get(e.id);
        return r && r <= cut;
      });
      const hasOverdueEquip = equips.some((e) => e.ageYears !== null && e.ageYears > e.referenceLifeYears);

      // Risque équipement logement : 90 si Top 10%, 65 si vétuste, sinon 15
      const equipRatio = hasTop10Equip ? 0.95 : hasOverdueEquip ? 0.65 : 0.15;
      const composite = computeCompositeScore(h.dpeGlobal, selectedResidence?.constructionYear, equipRatio);

      return {
        housing: h,
        equips,
        hasTop10Equip,
        composite,
      };
    });
  }, [selectedResidenceHousings, selectedResidenceEquipments, selectedResidence, ranks, result.scores]);

  // Filtrage des logements
  const filteredHousings = useMemo(() => {
    return housingsWithScore.filter(({ housing, composite }) => {
      const matchSearch =
        !housingSearch ||
        housing.id.toLowerCase().includes(housingSearch.toLowerCase()) ||
        housing.buildingId.toLowerCase().includes(housingSearch.toLowerCase()) ||
        housing.typology.toLowerCase().includes(housingSearch.toLowerCase());

      const matchLevel = housingLevelFilter === "all" || composite.level === housingLevelFilter;
      return matchSearch && matchLevel;
    }).sort((a, b) => b.composite.score - a.composite.score); // Les plus rouges en premier !
  }, [housingsWithScore, housingSearch, housingLevelFilter]);

  return (
    <div className="toulouse-map-view">
      {/* En-tête de la carte avec explication du score unifié */}
      <div className="map-page-header">
        <div>
          <div className="header-tag-group">
            <span className="eyebrow-red">
              <span className="pulse-dot" />
              MÉTROPOLE TOULOUSAINE
            </span>
            <Badge tone="blue">8 résidences · 1 100 logements</Badge>
          </div>
          <h1>Indice Global de Vulnérabilité & Prévention</h1>
          <p>
            Un <strong>code couleur unifié</strong> combinant <strong>l'âge du bâti</strong>, la{" "}
            <strong>performance énergétique DPE</strong> et l'<strong>urgence de panne des équipements</strong>.  
            Plus un logement est ancien, énergivore et à risque de rupture, plus il s'affiche en <strong>rouge vif</strong>.
          </p>
        </div>

        {/* Jauge / Échelle visuelle globale unifiée */}
        <div className="unified-legend-card">
          <span className="legend-title">Échelle unifiée de vulnérabilité :</span>
          <div className="gradient-scale-bar">
            <span className="gradient-tick tick-low">0 (Sain)</span>
            <span className="gradient-tick tick-mid">50</span>
            <span className="gradient-tick tick-high">100 (Critique)</span>
          </div>
          <div className="scale-levels-row">
            <span style={{ color: "#10b981" }}>● Faible risque</span>
            <span style={{ color: "#f59e0b" }}>● Vigilance</span>
            <span style={{ color: "#f97316" }}>● Risque élevé</span>
            <span style={{ color: "#e92549" }}>● Urgence critique</span>
          </div>
        </div>
      </div>

      {/* Barre de filtres par niveau unifié */}
      <div className="map-controls-bar">
        <div className="dpe-legend-filter">
          <span className="control-label">
            <Activity size={16} />
            Filtrer les résidences :
          </span>

          <div className="dpe-pill-group">
            <button
              className={`dpe-pill-btn ${levelFilter === "all" ? "selected" : ""}`}
              onClick={() => setLevelFilter("all")}
            >
              Toutes (8)
            </button>
            <button
              className={`dpe-pill-btn ${levelFilter === "critical" ? "selected" : ""}`}
              style={{
                backgroundColor: levelFilter === "critical" ? "#e92549" : "#fee2e2",
                color: levelFilter === "critical" ? "#ffffff" : "#b91c1c",
                borderColor: "#e92549",
              }}
              onClick={() => setLevelFilter(levelFilter === "critical" ? "all" : "critical")}
            >
              🔴 Urgence critique (3)
            </button>
            <button
              className={`dpe-pill-btn ${levelFilter === "high" ? "selected" : ""}`}
              style={{
                backgroundColor: levelFilter === "high" ? "#f97316" : "#ffedd5",
                color: levelFilter === "high" ? "#ffffff" : "#c2410c",
                borderColor: "#f97316",
              }}
              onClick={() => setLevelFilter(levelFilter === "high" ? "all" : "high")}
            >
              🟠 Risque élevé (2)
            </button>
            <button
              className={`dpe-pill-btn ${levelFilter === "moderate" ? "selected" : ""}`}
              style={{
                backgroundColor: levelFilter === "moderate" ? "#f59e0b" : "#fef3c7",
                color: levelFilter === "moderate" ? "#ffffff" : "#b45309",
                borderColor: "#f59e0b",
              }}
              onClick={() => setLevelFilter(levelFilter === "moderate" ? "all" : "moderate")}
            >
              🟡 Vigilance (1)
            </button>
            <button
              className={`dpe-pill-btn ${levelFilter === "low" ? "selected" : ""}`}
              style={{
                backgroundColor: levelFilter === "low" ? "#10b981" : "#d1fae5",
                color: levelFilter === "low" ? "#ffffff" : "#047857",
                borderColor: "#10b981",
              }}
              onClick={() => setLevelFilter(levelFilter === "low" ? "all" : "low")}
            >
              🟢 Faible risque (2)
            </button>
          </div>
        </div>

        <div className="map-stats-summary">
          <span>Carte OpenStreetMap officielle · <strong>Sans clé API</strong></span>
        </div>
      </div>

      {/* Grille Carte + Tiroir de détail */}
      <div className="map-layout-grid">
        <div className="leaflet-outer-container">
          <div ref={mapContainerRef} className="leaflet-map-canvas" />

          <div className="map-floating-hint">
            <MapPin size={15} />
            <span>Chiffre sur le repère = Score global de vulnérabilité (0 à 100). Cliquez pour explorer.</span>
          </div>
        </div>

        {/* Tiroir d'exploration de la résidence */}
        {selectedResidence && selectedScoreData && (
          <aside className="residence-drawer">
            <div className="drawer-header">
              <div>
                <div className="drawer-eyebrow">
                  <span>{selectedResidence.district || "Toulouse"}</span>
                  <Badge tone={selectedScoreData.composite.level === "critical" ? "rose" : "blue"}>
                    {selectedResidence.id}
                  </Badge>
                </div>
                <h2>{selectedResidence.name}</h2>
              </div>
              <button
                className="icon-button"
                aria-label="Fermer le panneau"
                onClick={() => setSelectedResidenceId(null)}
              >
                <X size={18} />
              </button>
            </div>

            {/* Score global unifié de la résidence */}
            <div
              className="unified-score-banner"
              style={{
                borderLeftColor: selectedScoreData.composite.color,
                background: `linear-gradient(90deg, ${selectedScoreData.composite.color}15 0%, #ffffff 100%)`,
              }}
            >
              <div
                className="score-circle-badge"
                style={{ backgroundColor: selectedScoreData.composite.color }}
              >
                <strong>{selectedScoreData.composite.score}</strong>
                <small>/ 100</small>
              </div>

              <div className="score-summary-details">
                <span
                  className="score-level-tag"
                  style={{ color: selectedScoreData.composite.color }}
                >
                  {selectedScoreData.composite.label.toUpperCase()}
                </span>
                <p>
                  Combinaison : Bâti de <strong>{selectedResidence.constructionYear}</strong> ({2026 - (selectedResidence.constructionYear || 1985)} ans) ·{" "}
                  Classe <strong>DPE {selectedResidence.dpeTag}</strong> · <strong>{selectedScoreData.highRiskCount}</strong> équipements Top 10%.
                </p>
              </div>
            </div>

            {/* Décomposition des 3 piliers */}
            <div className="score-pillars-breakdown">
              <div className="pillar-row">
                <div className="pillar-label">
                  <span>🔋 Performance DPE ({selectedResidence.dpeTag})</span>
                  <strong>{selectedScoreData.composite.dpeScore}/100</strong>
                </div>
                <div className="pillar-bar-track">
                  <div
                    className="pillar-bar-fill"
                    style={{ width: `${selectedScoreData.composite.dpeScore}%`, backgroundColor: getDpeColor(selectedResidence.dpeTag) }}
                  />
                </div>
              </div>

              <div className="pillar-row">
                <div className="pillar-label">
                  <span>⏳ Âge du bâti ({selectedResidence.constructionYear})</span>
                  <strong>{selectedScoreData.composite.ageScore}/100</strong>
                </div>
                <div className="pillar-bar-track">
                  <div
                    className="pillar-bar-fill"
                    style={{ width: `${selectedScoreData.composite.ageScore}%`, backgroundColor: "#f59e0b" }}
                  />
                </div>
              </div>

              <div className="pillar-row">
                <div className="pillar-label">
                  <span>🚨 Urgence équipements (Top 10%)</span>
                  <strong>{selectedScoreData.composite.equipScore}/100</strong>
                </div>
                <div className="pillar-bar-track">
                  <div
                    className="pillar-bar-fill"
                    style={{ width: `${selectedScoreData.composite.equipScore}%`, backgroundColor: "#e92549" }}
                  />
                </div>
              </div>
            </div>

            {/* Exploration des logements avec le score unifié individuel */}
            <div className="housings-section">
              <div className="housings-heading">
                <div>
                  <h3>Logements ({filteredHousings.length})</h3>
                  <p>Classés du plus critique (rouge) au plus sain (vert)</p>
                </div>

                <select
                  aria-label="Filtrer les logements par niveau de criticité"
                  value={housingLevelFilter}
                  onChange={(e) => setHousingLevelFilter(e.target.value)}
                  className="housing-dpe-select"
                >
                  <option value="all">Tous les niveaux</option>
                  <option value="critical">🔴 Urgence critique</option>
                  <option value="high">🟠 Risque élevé</option>
                  <option value="moderate">🟡 Vigilance</option>
                  <option value="low">🟢 Faible risque</option>
                </select>
              </div>

              <div className="housing-search-input">
                <Search size={15} />
                <input
                  placeholder="Rechercher un logement (ex: LGT-F4-022, T3...)"
                  value={housingSearch}
                  onChange={(e) => setHousingSearch(e.target.value)}
                />
                {housingSearch && (
                  <button onClick={() => setHousingSearch("")}>
                    <X size={14} />
                  </button>
                )}
              </div>

              <div className="housings-scroll-list">
                {filteredHousings.slice(0, 30).map(({ housing: h, equips, hasTop10Equip, composite }) => (
                  <div
                    key={h.id}
                    className={`housing-item-card unified ${composite.level === "critical" ? "alert" : ""}`}
                    style={{ borderLeftColor: composite.color, borderLeftWidth: "4px" }}
                  >
                    <div className="housing-top-row">
                      <div className="housing-ref">
                        <strong>{h.id}</strong>
                        <span>· Bât {h.buildingId.replace("BAT-", "")} · Étage {h.floor}</span>
                      </div>

                      {/* Badge du score unifié du logement */}
                      <span
                        className="unified-housing-pill"
                        style={{
                          backgroundColor: `${composite.color}18`,
                          color: composite.color,
                          borderColor: composite.color,
                        }}
                      >
                        <strong>Score {composite.score}</strong>
                        <small>DPE {h.dpeGlobal}</small>
                      </span>
                    </div>

                    <div className="housing-specs-row">
                      <span>Typologie: <strong>{h.typology}</strong> ({h.area} m²)</span>
                      <span>Statut: <strong>{h.occupancyStatus}</strong></span>
                    </div>

                    {equips.length > 0 && (
                      <div className="housing-equips-block">
                        {equips.map((eq) => {
                          const eqRank = ranks.get(eq.id);
                          const isHighRisk =
                            eqRank &&
                            eqRank <= Math.ceil(Object.keys(result.scores).length * 0.1);

                          return (
                            <Link
                              key={eq.id}
                              to={`/equipements/${eq.id}`}
                              className={`housing-equip-link ${isHighRisk ? "critical" : ""}`}
                              title={`Voir la fiche détaillée de ${eq.label}`}
                            >
                              <span className="equip-link-name">
                                {isHighRisk && <span className="red-dot-ping" />}
                                {eq.label}
                              </span>
                              <span className="equip-link-age">
                                {eq.ageYears !== null
                                  ? `${eq.ageYears.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} ans`
                                  : "Âge —"}
                              </span>
                              <ArrowRight size={13} />
                            </Link>
                          );
                        })}
                      </div>
                    )}
                  </div>
                ))}

                {filteredHousings.length > 30 && (
                  <p className="housings-more-hint">
                    + {filteredHousings.length - 30} autres logements dans cette résidence
                  </p>
                )}

                {filteredHousings.length === 0 && (
                  <div className="housings-empty">
                    <p>Aucun logement ne correspond aux filtres sélectionnés.</p>
                  </div>
                )}
              </div>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
