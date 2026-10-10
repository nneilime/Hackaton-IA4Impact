import { useEffect, useState } from "react";
import { Link } from "react-router";
import {
  CalendarDays,
  Wrench,
  Layers,
  ArrowRight,
  RefreshCw,
} from "lucide-react";
import { api } from "../../data/api";
import { useAppData } from "../../data/store";
import { dateLabel } from "../../domain/rules";
import {
  euros,
  replacementRange,
  type Economics,
} from "../../domain/economics";
import { Metric } from "../../ui/components";
import { PreventionScenario } from "./PreventionScenario";
import { ResidenceGroupedReplacement } from "./ResidenceGroupedReplacement";
import { ReplacementPriorityList } from "./ReplacementPriorityList";

export function EconomicsPage() {
  const { catalog, horizon, setHorizon, asOfDate, result } =
    useAppData();
  const [year] = useState(Number(asOfDate.slice(0, 4)));
  const [data, setData] = useState<Economics | null>(null);
  const [residence, setResidence] = useState("");
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [repairLimit, setRepairLimit] = useState(12);

  useEffect(() => {
    let alive = true;
    setError("");
    api<Economics>(
      `/economies?year=${year}&horizon=${horizon}&as_of_date=${asOfDate}`,
    )
      .then((next) => {
        if (!alive) return;
        setData(next);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [
    year,
    horizon,
    asOfDate,
    catalog.revision,
    result.metadata.modelVersion,
    retry,
  ]);

  const relevant =
    data?.equipment.filter((e) => !residence || e.residenceId === residence) ||
    [];
  const repeated = relevant.filter(
    (e) => e.repairCount12m !== null && e.repairCount12m >= 2,
  );
  const groups =
    data?.groups.filter((g) => !residence || g.residenceId === residence) || [];
  const coordination = relevant.filter(
    (e) =>
      e.operationIds.length && (e.priority || (e.repairCount12m || 0) >= 2),
  );
  const context = Object.entries(data?.residenceFinance || {}).filter(
    ([id]) => !residence || id === residence,
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">ARBITRAGES BUDGÉTAIRES</span>
          <h1>Préparer les dépenses, comparer les options.</h1>
          <p>
            Prioriser les contrôles, coordonner les travaux et proposer une
            sélection compatible avec l’enveloppe annuelle.
          </p>
        </div>
      </div>
      <div className="economic-toolbar">
        <label>
          Résidence
          <select
            value={residence}
            onChange={(e) => {
              setResidence(e.target.value);
              setRepairLimit(12);
            }}
          >
            <option value="">Toutes les résidences</option>
            {catalog.residences.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Horizon des contrôles
          <select
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
          >
            {[90, 180, 365, 730].map((h) => (
              <option key={h} value={h}>
                {h} jours
              </option>
            ))}
          </select>
        </label>
        <span>
          Historique :{" "}
          {data
            ? `${dateLabel(data.periodStart)} au ${dateLabel(data.referenceDate)} (fin exclue)`
            : "Chargement…"}
        </span>
        <button
          className="button secondary"
          onClick={() => setRetry((v) => v + 1)}
        >
          <RefreshCw size={16} />
          Actualiser les indicateurs
        </button>
      </div>
      {error && (
        <div className="inline-error" role="alert">
          <p>{error}</p>
          <button
            className="button secondary"
            onClick={() => setRetry((v) => v + 1)}
          >
            Réessayer
          </button>
        </div>
      )}
      {!data ? (
        <div className="boot-state">
          <p>
            {error
              ? "Les indicateurs ne sont pas disponibles."
              : "Analyse des interventions et du plan d’investissement…"}
          </p>
        </div>
      ) : (
        <>
          {data.result.stale && (
            <p className="storage-notice" role="status">
              Le classement utilisé est dépassé. Les coûts documentés restent
              consultables ; relancez le calcul avant de préparer une tournée.
            </p>
          )}
          <div className="metrics economic-metrics">
            <Metric
              label="Réparations répétées"
              value={String(repeated.length)}
              detail="Équipements avec au moins 2 dépannages sur 12 mois"
              icon={<Wrench size={23} />}
            />
            <Metric
              label="Contrôles à regrouper"
              value={String(groups.length)}
              detail="Groupes par résidence et prestataire, parmi les 10 % prioritaires"
              icon={<CalendarDays size={23} />}
              tone="mint"
            />
            <Metric
              label="Travaux à coordonner"
              value={String(coordination.length)}
              detail="Rapprochements à confirmer avec le plan d’investissement"
              icon={<Layers size={23} />}
              tone="rose"
            />
          </div>
          <ResidenceGroupedReplacement
            equipmentList={data.equipment}
            currentYear={year}
            renovationBudget={1500000}
          />
          <ReplacementPriorityList
            equipmentList={data.equipment}
            residenceFilter={residence}
          />
          <div className="economic-two-columns">
            <section className="surface economic-section">
              <div className="card-heading">
                <h2>Préparer une tournée commune</h2>
              </div>
              <p>
                Proposer un passage pour plusieurs équipements prioritaires
                d’une même résidence, avec le même prestataire. Disponibilité,
                périmètre contractuel et tarifs sont à confirmer.
              </p>
              {groups.map((g) => (
                <details
                  className="economic-opportunity"
                  key={g.residenceId + g.providerId}
                >
                  <summary>
                    {g.residenceId} ·{" "}
                    {catalog.providers.find((p) => p.id === g.providerId)
                      ?.name || g.providerId}
                    <strong>{g.equipmentIds.length} contrôles</strong>
                  </summary>
                  <p>
                    Jusqu’à {g.potentialVisitsCombined} déplacements distincts à
                    regrouper si les contrôles sont compatibles. Aucun montant
                    d’économie n’est supposé.
                  </p>
                  <div className="economic-links">
                    {g.equipmentIds.map((id) => (
                      <Link key={id} to={`/equipements/${id}`}>
                        {id}
                      </Link>
                    ))}
                  </div>
                </details>
              ))}
              {!groups.length && (
                <p>
                  Aucun groupe de plusieurs équipements prioritaires dans ce
                  filtre.
                </p>
              )}
            </section>
            <section className="surface economic-section">
              <div className="card-heading">
                <h2>Coordonner réparation et rénovation</h2>
              </div>
              <p>
                Vérifier le calendrier des travaux avant d’engager une
                réparation importante. Un rapprochement de famille et de
                localisation doit être confirmé par l’équipe.
              </p>
              {data.operations
                .filter((o) =>
                  coordination.some((e) => e.operationIds.includes(o.id)),
                )
                .map((o) => (
                  <details className="economic-opportunity" key={o.id}>
                    <summary>
                      {o.label}
                      <strong>
                        {o.residenceId} · {o.desiredYear}
                      </strong>
                    </summary>
                    <p>
                      {o.perimeter} · {euros(o.cost)} estimés. Statut source :{" "}
                      {o.status}.
                    </p>
                    <div className="economic-links">
                      {coordination
                        .filter((e) => e.operationIds.includes(o.id))
                        .map((e) => (
                          <Link
                            key={e.equipmentId}
                            to={`/equipements/${e.equipmentId}`}
                          >
                            {e.equipmentId}
                          </Link>
                        ))}
                    </div>
                  </details>
                ))}
              {!coordination.length && (
                <p>Aucun rapprochement dans ce filtre.</p>
              )}
            </section>
          </div>
          <section className="surface economic-section">
            <div className="card-heading">
              <h2>Dépenses documentées par résidence</h2>
            </div>
            <p>
              Montants facturés sur les 12 derniers mois et solde des commandes
              connues à la date de référence. Ces données couvrent partiellement
              la maintenance et ne constituent pas le coût complet du parc.
            </p>
            <div className="economic-table-wrap">
              <table className="economic-table">
                <thead>
                  <tr>
                    <th>Résidence</th>
                    <th>Facturé · 12 mois</th>
                    <th>Factures</th>
                    <th>Commandé, non facturé à la référence</th>
                  </tr>
                </thead>
                <tbody>
                  {context.map(([id, f]) => (
                    <tr key={id}>
                      <td>
                        {catalog.residences.find((r) => r.id === id)?.name ||
                          id}
                      </td>
                      <td>{euros(f.billed12m)}</td>
                      <td>{f.invoiceCount12m}</td>
                      <td>{euros(f.outstanding)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="fine-print">
              Une commande et sa facture ne sont jamais additionnées comme deux
              dépenses. Les prestations sous contrat peuvent ne pas avoir de
              commande individuelle.
            </p>
          </section>
          <PreventionScenario key={horizon} horizon={horizon} />
        </>
      )}
    </>
  );
}
