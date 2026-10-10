import { useEffect, useState } from "react";
import { api } from "../../data/api";
import { Link } from "react-router";
import { euros } from "../../domain/economics";

interface FailureTypes {
  status: "available" | "unavailable";
  predictions: {
    type_intervention: string;
    type_panne: string;
    conditional_probability: number;
    joint_probability: number;
    prix: number | null;
  }[];
  other_conditional_probability: number;
  expected_price_if_failure: number | null;
  expected_cost_within_horizon: number | null;
}
type Prediction = Record<`failure_types_${number}d`, FailureTypes>;
const percent = (value: number) =>
  (value * 100).toLocaleString("fr-FR", { maximumFractionDigits: 1 }) + " %";
const money = (value: number | null) =>
  value === null
    ? "Non estimé"
    : value.toLocaleString("fr-FR", { style: "currency", currency: "EUR" });

export function FailurePrediction({
  equipmentId,
  asOfDate,
  horizon,
  revision,
  modelVersion,
}: {
  equipmentId: string;
  asOfDate: string;
  horizon: number;
  revision?: number;
  modelVersion: string;
}) {
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let alive = true;
    setPrediction(null);
    setError("");
    api<Prediction>("/predict", {
      method: "POST",
      body: JSON.stringify({ equipment_id: equipmentId, as_of_date: asOfDate }),
    })
      .then((value) => {
        if (alive) setPrediction(value);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [equipmentId, asOfDate, revision, modelVersion, retry]);
  const types = prediction?.[`failure_types_${horizon}d`];
  return (
    <section className="surface prediction-card">
      <div className="card-heading">
        <h2>Points de contrôle ciblés · {horizon} jours</h2>
        <span className="quiet-label">Diagnostic prédictif</span>
      </div>
      {error ? (
        <>
          <p role="alert">{error}</p>
          <button
            className="button secondary"
            onClick={() => setRetry((v) => v + 1)}
          >
            Réessayer la prédiction
          </button>
        </>
      ) : !prediction ? (
        <p>Calcul des prévisions en cours…</p>
      ) : types?.status !== "available" ? (
        <p>
          Le modèle de symptômes n’est pas disponible pour cette famille et cet
          horizon.
        </p>
      ) : (
        <>
          <p className="prediction-intro">
            Points de vigilance à examiner en priorité lors du contrôle :
          </p>
          <div className="prediction-table-header">
            <span>Symptôme suspecté & intervention</span>
            <span>Probabilité sur {horizon} jours</span>
          </div>
          <ol className="prediction-candidates">
            {types.predictions.map((p) => (
              <li
                className="failure-candidate"
                key={p.type_intervention + ":" + p.type_panne}
              >
                <div>
                  <strong>{p.type_panne}</strong>
                  <span>
                    {p.type_intervention} · Barème contractuel : {euros(p.prix)} TTC
                  </span>
                </div>
                <div className="prediction-share">
                  <strong>{percent(p.joint_probability)}</strong>
                  <span>sous {horizon} jours</span>
                </div>
              </li>
            ))}
          </ol>
          <div className="prediction-cost-summary">
            <div>
              <span>
                Coût moyen estimé par dépannage d’urgence (repère indicatif)
              </span>
              <strong>{euros(types.expected_price_if_failure)}</strong>
            </div>
            <p>
              Moyenne constatée sur les interventions de ce type d’équipement. Ce montant sert de repère financier pour évaluer l’intérêt d’une visite préventive face au coût d’un dépannage en urgence.
            </p>
          </div>
          <details className="prediction-method">
            <summary>Comprendre le résultat du modèle</summary>
            <p>
              Le pourcentage affiché pour chaque symptôme correspond au <strong>score sur l’horizon ({horizon} jours)</strong> : il mesure le risque combiné que l’équipement tombe en panne et que ce soit pour cette cause précise d’ici {horizon} jours.
            </p>
            {types.predictions.map((p) => (
              <div
                className="prediction-score-row"
                key={p.type_intervention + ":" + p.type_panne}
              >
                <strong>{p.type_panne}</strong>
                <span>
                  Score sur l’horizon : {percent(p.joint_probability)}
                </span>
                <span>
                  Score conditionnel : {percent(p.conditional_probability)}
                </span>
              </div>
            ))}
            <p>
              Autres possibilités :{" "}
              {percent(types.other_conditional_probability)} du score
              conditionnel.
            </p>
            <p>
              Coût pondéré sur {horizon} jours :{" "}
              <strong>{money(types.expected_cost_within_horizon)}</strong>. Il
              combine le score de panne et le coût moyen de toutes les classes,
              y compris celles non affichées. Il ne représente ni une facture,
              ni un budget annuel, ni une économie garantie.
            </p>
          </details>
          <p className="fine-print">
            Scores non calibrés. Prix fictifs en euros TTC ; symptômes à
            confirmer, sans valeur de diagnostic ou de devis.
          </p>
          <Link className="text-link" to="/economies">
            Comparer les options et préparer le budget
          </Link>
        </>
      )}
    </section>
  );
}
