import { useEffect, useState } from "react";
import { Link } from "react-router";
import { Coins, ArrowRight } from "lucide-react";
import { api } from "../../data/api";
import { useAppData } from "../../data/store";
import {
  euros,
  replacementRange,
  type EquipmentEconomy as Economy,
} from "../../domain/economics";

export function EquipmentEconomy({
  equipmentId,
  onCompare,
}: {
  equipmentId: string;
  onCompare: () => void;
}) {
  const { asOfDate, horizon, catalog, result } = useAppData();
  const [data, setData] = useState<Economy | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let alive = true;
    setData(null);
    setError("");
    api<Economy>(
      `/equipements/${encodeURIComponent(equipmentId)}/economie?horizon=${horizon}&as_of_date=${asOfDate}`,
    )
      .then((next) => {
        if (alive) setData(next);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [
    equipmentId,
    asOfDate,
    horizon,
    catalog.revision,
    result.metadata.modelVersion,
    retry,
  ]);
  const e = data?.equipment;
  return (
    <section className="surface economic-section">
      <div className="card-heading">
        <h2>
          <Coins size={19} />
          Réparer ou remplacer : les repères
        </h2>
      </div>
      {error ? (
        <>
          <p role="alert">{error}</p>
          <button
            className="button secondary"
            onClick={() => setRetry((n) => n + 1)}
          >
            Réessayer les repères économiques
          </button>
        </>
      ) : !e ? (
        <p>Chargement des coûts et travaux prévus…</p>
      ) : (
        <>
          <div className="economic-equipment-metrics">
            <div>
              <span>Dépannages de l’appareil actuel · 12 mois</span>
              <strong>{e.repairCount12m ?? "Cycle inconnu"}</strong>
            </div>
            <div>
              <span>Coût de ces dépannages (barème indicatif)</span>
              <strong>{euros(e.simulatedRepairCost12m)}</strong>
            </div>
            <div>
              <span>Remplacement indicatif de cette famille</span>
              <strong>{replacementRange(e)}</strong>
            </div>
          </div>
          {e.simulatedRepairCost12m === null && (
            <p className="context-note">
              {e.cycleKnown
                ? "Certains dépannages n’ont pas de tarif : le total ne peut pas être estimé."
                : "La date de pose est à confirmer pour séparer les dépenses de l’appareil actuel et du précédent."}
            </p>
          )}
          {e.repairReplacementRatioMin !== null &&
            e.repairReplacementRatioMax !== null && (
              <p>
                Les dépannages simulés représentent{" "}
                {(e.repairReplacementRatioMin * 100).toLocaleString("fr-FR", {
                  maximumFractionDigits: 0,
                })}{" "}
                à{" "}
                {(e.repairReplacementRatioMax * 100).toLocaleString("fr-FR", {
                  maximumFractionDigits: 0,
                })}{" "}
                % du remplacement indicatif. Cette comparaison aide à préparer
                des devis ; les dépenses passées ne constituent pas des
                économies futures.
              </p>
            )}
          {e.underContract && (
            <p className="context-note">
              Sous contrat d’entretien : vérifier la prise en charge avant de
              retenir un coût supplémentaire.
            </p>
          )}
          {e.financeContext ? (
            <details className="economic-opportunity">
              <summary>
                Factures du {e.financeScope} :{" "}
                {euros(e.financeContext.billed12m)} sur 12 mois
              </summary>
              <p>
                {e.financeContext.invoiceCount12m} factures, tous équipements et
                natures confondus. Solde commandé non facturé :{" "}
                {euros(e.financeContext.outstanding)}. Ces montants ne sont pas
                attribués à cet appareil et ne sont pas ajoutés aux coûts
                simulés.
              </p>
            </details>
          ) : (
            <p className="fine-print">
              Aucune commande documentée pour ce {e.financeScope}. Cela ne
              signifie pas une maintenance gratuite.
            </p>
          )}
          {!!data!.operations.length && (
            <div className="economic-coordinate">
              <h3>
                Vérifier les travaux prévus avant une réparation importante
              </h3>
              {data!.operations.map((o) => (
                <p key={o.id}>
                  <strong>{o.label}</strong> · {o.desiredYear} · {o.perimeter} ·{" "}
                  {euros(o.cost)}
                  <small>
                    Rapprochement à confirmer : opération proposée, pas une
                    rénovation engagée.
                  </small>
                </p>
              ))}
            </div>
          )}
          {!!data!.groups.length && (
            <p className="context-note">
              Ce contrôle peut être étudié avec{" "}
              {data!.groups[0].equipmentIds.length - 1} autres équipements
              prioritaires de la résidence, suivis par le même prestataire.
            </p>
          )}
          <p className="fine-print">
            Tarifs fictifs TTC du kit, sans valeur de devis. Les factures ont
            une couverture partielle ; aucune facture n’est reliée directement à
            un équipement.
          </p>
        </>
      )}
      <div className="economic-actions">
        <Link className="text-link" to="/economies">
          Consulter les arbitrages budgétaires <ArrowRight size={14} />
        </Link>
        <button className="button secondary" onClick={onCompare}>
          Préparer la comparaison de devis
        </button>
      </div>
    </section>
  );
}
