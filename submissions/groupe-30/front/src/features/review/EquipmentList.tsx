import { useEffect, useRef } from "react";
import { Link, useSearchParams } from "react-router";
import {
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Search,
  SlidersHorizontal,
  Building2,
  ClipboardList,
  CircleCheck,
  X,
  MapPin,
  Download,
} from "lucide-react";
import Papa from "papaparse";
import { useAppData } from "../../data/store";
import {
  normalize,
  numberLabel,
  dateLabel,
  latestActions,
  download,
} from "../../domain/rules";
import { Badge, EmptyState, Metric, StatusBadge } from "../../ui/components";

export function EquipmentList({ inventory = false }: { inventory?: boolean }) {
  const { catalog, ranks, result, actions, setLastListQuery } = useAppData();
  const [params, setParams] = useSearchParams();
  // Conserve aussi la dernière navigation demandée pendant le rendu différé du routeur.
  const pendingParams = useRef(params);
  useEffect(() => {
    pendingParams.current = params;
  }, [params]);
  function changeParams(
    next: URLSearchParams | Record<string, string>,
    replace = false,
  ) {
    pendingParams.current = new URLSearchParams(next);
    setParams(pendingParams.current, { replace });
  }
  const query = params.get("q") || "";
  const residence = params.get("residence") || "";
  const family = params.get("family") || "";
  const provider = params.get("provider") || "";
  const scope = params.get("scope") || (inventory ? "all" : "priority");
  const status = params.get("status") || (inventory ? "all" : "unassigned");
  const page = Math.max(1, Number(params.get("page")) || 1);
  const [eligible, totalScores] = [
    catalog.equipment.filter((e) => e.inScope),
    Object.keys(result.scores).length,
  ];
  const cut = Math.ceil(totalScores * 0.1);
  const active = latestActions(actions);
  useEffect(() => {
    if (!inventory)
      setLastListQuery(params.toString() ? "?" + params.toString() : "");
  }, [params, inventory, setLastListQuery]);
  function filter(key: string, value: string) {
    const next = new URLSearchParams(pendingParams.current);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.delete("page");
    changeParams(next, true);
  }
  const items = (inventory ? catalog.equipment : eligible)
    .filter((e) => {
      const rank = ranks.get(e.id);
      const action = active.get(e.id);
      return (
        (!query ||
          normalize(
            `${e.id} ${e.label} ${e.residenceId} ${e.buildingId} ${e.housingId || ""}`,
          ).includes(normalize(query))) &&
        (!residence || e.residenceId === residence) &&
        (!family || e.family === family) &&
        (!provider || e.providerId === provider) &&
        (status === "all" ||
          (status === "unassigned" ? !action : action?.status === status)) &&
        (scope === "all" ||
          (scope === "week10" && !!rank && rank <= 10) ||
          (scope === "priority" && !!rank && rank <= cut) ||
          (scope === "collective" && e.collective) ||
          (scope === "private" && !e.collective) ||
          (scope === "verify" && e.needsVerification) ||
          (scope === "unscored" && e.inScope && !rank))
      );
    })
    .sort(
      (a, b) =>
        (ranks.get(a.id) || Infinity) - (ranks.get(b.id) || Infinity) ||
        a.id.localeCompare(b.id),
    );
  const isWeek10 = scope === "week10";
  const pageSize = isWeek10 ? 10 : 15;
  const maxPage = Math.max(1, Math.ceil(items.length / pageSize));
  const currentPage = Math.min(page, maxPage);
  const visible = items.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize,
  );

  function exportWeek10() {
    const top10 = items.slice(0, 10);
    const csvData = top10.map((e, idx) => {
      const p = catalog.providers.find((prov) => prov.id === e.providerId);
      const rk = ranks.get(e.id);
      return {
        priorite: idx + 1,
        equipement_id: e.id,
        famille: e.label,
        residence: e.residenceId,
        batiment: e.buildingId,
        logement_ou_parties: e.housingId || "Parties communes",
        rang_risque: rk ? `${rk}/${totalScores}` : "Non scoré",
        depannages_recents_12m: e.recentRepairCount,
        prestataire_en_contrat: p?.name.replace(" (fictif)", "") || e.providerId,
        statut_contrat: e.underContract ? "Sous contrat" : "Hors contrat",
        mission_a_commander: "Contrôle préventif et vérification des organes d'usure",
      };
    });
    download("tournee-prestataires-top10-semaine.csv", Papa.unparse(csvData));
  }
  const families = [
    ...new Map(
      (inventory ? catalog.equipment : eligible).map((e) => [
        e.family,
        e.label,
      ]),
    ).entries(),
  ].sort((a, b) => a[1].localeCompare(b[1]));
  const route = inventory ? "/equipements" : "/examiner";
  const backTo = route + (params.toString() ? "?" + params.toString() : "");
  const hasFilter = !!(
    query ||
    residence ||
    family ||
    provider ||
    status !== (inventory ? "all" : "unassigned")
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            <span />
            MAINTENANCE PRÉVENTIVE
          </span>
          <h1>
            {inventory
              ? "Votre patrimoine, en un seul endroit."
              : "Les contrôles à traiter en priorité."}
          </h1>
          <p>
            {inventory
              ? "Retrouvez les équipements et consultez leur historique technique."
              : "Préserver le service aux locataires, examiner les preuves et préparer les dépenses."}
          </p>
        </div>
        <div className="heading-note">
          <Building2 size={18} />
          <span>
            <strong>{catalog.residences.length} résidences</strong>
            <small>
              {numberLabel(
                catalog.residences.reduce((sum, r) => sum + r.housingCount, 0),
              )}{" "}
              logements suivis
            </small>
          </span>
        </div>
      </div>
      {!inventory && (
        <div className="economic-entry">
          <div>
            <strong>Préparer les dépenses avec les contrôles</strong>
            <p>
              Réparations répétées, tournées communes et rénovation sous
              enveloppe.
            </p>
          </div>
          <Link className="button secondary" to="/economies">
            Arbitrages budgétaires <ArrowRight size={16} />
          </Link>
        </div>
      )}
      <div className="metrics">
        <Metric
          label={
            inventory ? "Équipements référencés" : "Équipements du périmètre"
          }
          value={numberLabel(
            inventory ? catalog.equipment.length : eligible.length,
          )}
          detail={
            inventory
              ? "Inventaire privatif et collectif"
              : `${numberLabel(totalScores)} résultats disponibles`
          }
          icon={<Building2 size={23} />}
        />
        <Metric
          label="Actions à suivre"
          value={numberLabel(
            actions.filter((a) => a.status !== "closed").length,
          )}
          detail="Inspections et réexamens ouverts"
          icon={<ClipboardList size={23} />}
          tone="mint"
        />
        <Metric
          label="Informations à vérifier"
          value={numberLabel(
            eligible.filter((e) => e.needsVerification).length,
          )}
          detail="Origine ou date de pose à confirmer"
          icon={<CircleCheck size={23} />}
          tone="rose"
        />
      </div>
      <section className="list-section">
        <div className="section-heading">
          <div>
            <h2>
              {inventory
                ? "Répertoire des équipements"
                : "Votre liste de prévention"}
              <span className="count-tag">{numberLabel(items.length)}</span>
            </h2>
            <p>
              {scope === "priority"
                ? "Les 10 % les mieux classés sur le périmètre du résultat."
                : "Une vue de votre patrimoine, avec le classement et la prise en charge."}
            </p>
          </div>
          <div className="section-actions-group">
            <Link
              to="/carte"
              className="map-shortcut-btn"
              title="Voir les résidences et logements sur la carte de Toulouse"
            >
              <MapPin size={15} />
              Carte de Toulouse
            </Link>
            <span className="quiet-label">
              <SlidersHorizontal size={15} />
              Vue personnalisée
            </span>
          </div>
        </div>
        <div className="scope-tabs" aria-label="Vue des équipements">
          {[
            ["week10", "⚡ 10 de la semaine"],
            ["priority", "Top 10 %"],
            ["all", "Tous"],
            ["collective", "Collectifs"],
            ["private", "Privatifs"],
            ["verify", "À vérifier"],
            ["unscored", "Non scorés"],
          ].map(([value, label]) => (
            <button
              key={value}
              className={scope === value ? "active" : ""}
              aria-pressed={scope === value}
              onClick={() => filter("scope", value)}
            >
              {label}
              {value === "week10" && <span>10</span>}
              {value === "priority" && <span>{cut}</span>}
            </button>
          ))}
        </div>
        <div className="filter-bar">
          <div className="search-field">
            <Search size={18} />
            <input
              aria-label="Rechercher un équipement, un logement ou un bâtiment"
              placeholder="Rechercher un équipement, un logement…"
              value={query}
              onChange={(e) => filter("q", e.target.value)}
            />
            {query && (
              <button
                aria-label="Effacer la recherche"
                onClick={() => filter("q", "")}
              >
                <X size={15} />
              </button>
            )}
          </div>
          <select
            aria-label="Filtrer par résidence"
            value={residence}
            onChange={(e) => filter("residence", e.target.value)}
          >
            <option value="">Toutes les résidences</option>
            {catalog.residences.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
          <select
            aria-label="Filtrer par famille"
            value={family}
            onChange={(e) => filter("family", e.target.value)}
          >
            <option value="">Tous les équipements</option>
            {families.map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
          <select
            aria-label="Filtrer par prestataire"
            value={provider}
            onChange={(e) => filter("provider", e.target.value)}
          >
            <option value="">Tous les prestataires</option>
            {catalog.providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name.replace(" (fictif)", "")}
              </option>
            ))}
          </select>
          <select
            aria-label="Filtrer par prise en charge"
            value={status}
            onChange={(e) => filter("status", e.target.value)}
          >
            <option value="all">Tout le suivi</option>
            <option value="unassigned">À examiner</option>
            <option value="preparing">À préparer</option>
            <option value="planned">Planifiée</option>
            <option value="review">À réexaminer</option>
            <option value="completed">Réalisée</option>
            <option value="closed">Clôturée</option>
          </select>
        </div>
        {hasFilter && (
          <div className="active-filters">
            <span>
              Vue filtrée · {numberLabel(items.length)} résultat
              {items.length > 1 ? "s" : ""}
            </span>
            <button
              onClick={() =>
                changeParams(
                  scope === (inventory ? "all" : "priority") ? {} : { scope },
                )
              }
            >
              Réinitialiser les filtres
              <X size={13} />
            </button>
          </div>
        )}
        {isWeek10 && (
          <div className="week-dispatch-banner">
            <div className="week-dispatch-header">
              <div>
                <span className="eyebrow">FEUILLE DE ROUTE GESTIONNAIRE</span>
                <h3>10 équipements de la semaine à confier à vos prestataires</h3>
                <p>
                  Sélection des équipements au risque de panne le plus critique. Transmettez cette feuille de route aux prestataires sous contrat pour programmer les contrôles avant rupture de service pour les occupants.
                </p>
              </div>
              <button
                className="button primary"
                onClick={exportWeek10}
              >
                <Download size={16} />
                Exporter la feuille de tournée (CSV)
              </button>
            </div>
            <div className="week-dispatch-stats">
              <div className="dispatch-stat">
                <span>Équipements ciblés</span>
                <strong>{items.slice(0, 10).length}</strong>
                <small>Top criticité du patrimoine</small>
              </div>
              <div className="dispatch-stat">
                <span>Dépannages récents cumulés</span>
                <strong>
                  {items.slice(0, 10).reduce((sum, e) => sum + (e.recentRepairCount || 0), 0)}
                </strong>
                <small>Sur les 12 derniers mois</small>
              </div>
              <div className="dispatch-stat">
                <span>Logements concernés</span>
                <strong>
                  {items.slice(0, 10).reduce((sum, e) => sum + (e.buildingHousingCount || 1), 0)}
                </strong>
                <small>Continuité de service locatif</small>
              </div>
            </div>
          </div>
        )}
        {!visible.length ? (
          <EmptyState
            title="Aucun équipement dans cette vue"
            description="Essayez une autre recherche ou retirez les filtres pour élargir votre sélection."
            action={
              <button
                className="button secondary"
                onClick={() => changeParams({ scope: "all" })}
              >
                Voir tous les équipements
              </button>
            }
          />
        ) : (
          <div className="table-scroll">
            <table className="equipment-table">
              <thead>
                <tr>
                  <th>Équipement</th>
                  <th>Localisation</th>
                  <th>Rang de risque</th>
                  <th>Dernier élément observé</th>
                  <th>Prise en charge</th>
                  <th>
                    <span className="sr-only">Ouvrir la fiche</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {visible.map((e) => {
                  const rank = ranks.get(e.id);
                  const a = active.get(e.id);
                  return (
                    <tr key={e.id}>
                      <td>
                        <Link
                          className="equipment-link"
                          to={`/equipements/${e.id}`}
                          state={{ backTo }}
                        >
                          <span
                            className={`equipment-symbol ${e.collective ? "collective" : ""}`}
                          >
                            <Building2 size={19} />
                          </span>
                          <span>
                            <strong>{e.label}</strong>
                            <small>
                              {e.id}
                              {e.collective && " · Collectif"}
                              {e.ageYears !== null && (
                                <span
                                  className={`table-age-pill ${e.ageYears > e.referenceLifeYears ? "alert" : ""}`}
                                >
                                  {e.ageYears.toFixed(1)} ans
                                </span>
                              )}
                            </small>
                          </span>
                        </Link>
                      </td>
                      <td data-label="Localisation">
                        <strong className="cell-title">
                          {e.residenceId.replace("RES-", "Résidence ")}
                        </strong>
                        <small>
                          {e.housingId || e.buildingId + " · Parties communes"}
                        </small>
                      </td>
                      <td data-label="Rang de risque">
                        {rank ? (
                          <span className={`rank ${rank <= cut ? "high" : ""}`}>
                            <span>{rank}</span>
                            <small>/ {numberLabel(totalScores)}</small>
                          </span>
                        ) : (
                          <Badge>
                            {e.inScope ? "Non scoré" : "Hors périmètre"}
                          </Badge>
                        )}
                      </td>
                      <td className="observation-cell" data-label="Observation">
                        {e.latestObservation ? (
                          <>
                            <span className="observation-text">
                              {e.latestObservation.text}
                            </span>
                            <small>{dateLabel(e.latestObservation.date)}</small>
                          </>
                        ) : (
                          <span className="muted">
                            Aucun constat récent disponible
                          </span>
                        )}
                      </td>
                      <td data-label="Suivi">
                        <StatusBadge status={a?.status} />
                      </td>
                      <td className="row-open">
                        <Link
                          aria-label={`Ouvrir ${e.id}`}
                          className="icon-button"
                          to={`/equipements/${e.id}`}
                          state={{ backTo }}
                        >
                          <ChevronRight size={18} />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <div className="pagination">
          <span>
            {items.length
              ? `${(currentPage - 1) * pageSize + 1}–${Math.min(currentPage * pageSize, items.length)} sur ${numberLabel(items.length)} équipements`
              : "0 équipement"}
          </span>
          <div>
            <button
              className="icon-button"
              aria-label="Page précédente"
              disabled={currentPage === 1}
              onClick={() => filter("page", String(currentPage - 1))}
            >
              <ChevronLeft size={17} />
            </button>
            <span>
              Page {currentPage} sur {maxPage}
            </span>
            <button
              className="icon-button"
              aria-label="Page suivante"
              disabled={currentPage === maxPage}
              onClick={() => {
                const next = new URLSearchParams(pendingParams.current);
                next.set("page", String(currentPage + 1));
                changeParams(next);
              }}
            >
              <ChevronRight size={17} />
            </button>
          </div>
        </div>
      </section>
      <div className="page-footnote">
        <span>
          <CircleCheck size={15} />
          Les décisions restent entre les mains de votre équipe.
        </span>
        <Link to="/actions">
          Consulter les actions
          <ArrowRight size={14} />
        </Link>
      </div>
    </>
  );
}
