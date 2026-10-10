import { useState } from "react";
import { euros, preventionScenario } from "../../domain/economics";

export function PreventionScenario({ horizon }: { horizon: number }) {
  const [cost, setCost] = useState("");
  const [probability, setProbability] = useState("");
  const [efficacy, setEfficacy] = useState("");
  const [avoidable, setAvoidable] = useState("");
  const complete = [cost, probability, efficacy, avoidable].every(
    (v) => v.trim() !== "",
  );
  const result = complete
    ? preventionScenario(
        Number(cost),
        Number(probability) / 100,
        Number(efficacy) / 100,
        Number(avoidable),
      )
    : null;
  return (
    <section className="surface economic-section">
      <div className="card-heading">
        <h2>Tester un scénario de prévention · {horizon} jours</h2>
      </div>
      <p>
        Comparez le coût d’un contrôle à la dépense qu’il pourrait éviter sur la
        période choisie. Les hypothèses restent à valider sur le terrain.
      </p>
      <div className="economic-form-grid">
        <label>
          Coût supplémentaire du contrôle (€ TTC)
          <input
            type="number"
            min="0"
            step="0.01"
            value={cost}
            onChange={(e) => setCost(e.target.value)}
          />
        </label>
        <label>
          Probabilité de panne supposée (%)
          <input
            type="number"
            min="0"
            max="100"
            step="0.1"
            value={probability}
            onChange={(e) => setProbability(e.target.value)}
          />
        </label>
        <label>
          Part des pannes évitables par ce contrôle (%)
          <input
            type="number"
            min="0"
            max="100"
            step="0.1"
            value={efficacy}
            onChange={(e) => setEfficacy(e.target.value)}
          />
        </label>
        <label>
          Dépense réellement évitable par panne (€ TTC)
          <input
            type="number"
            min="0"
            step="0.01"
            value={avoidable}
            onChange={(e) => setAvoidable(e.target.value)}
          />
        </label>
      </div>
      <div aria-live="polite" className="economic-scenario-result">
        {!complete ? (
          <p>Renseignez les quatre hypothèses pour comparer le scénario.</p>
        ) : !result ? (
          <p role="alert">
            Vérifiez les montants et les pourcentages : valeurs positives,
            pourcentages entre 0 et 100.
          </p>
        ) : (
          <>
            <span>Gain net simulé par équipement</span>
            <strong>{euros(result.net)}</strong>
            <p>
              {result.net > 0
                ? "Le gain estimé dépasse le coût du contrôle avec ces hypothèses."
                : result.net === 0
                  ? "Le scénario est à l’équilibre."
                  : "Le contrôle coûte davantage que la dépense évitée estimée avec ces hypothèses."}
            </p>
            <small>
              {result.breakEvenProbability === null
                ? "Aucune dépense évitable avec cette efficacité."
                : result.breakEvenProbability > 1
                  ? "L’équilibre n’est pas atteignable avec ces montants, même avec une probabilité de panne de 100 %."
                  : `Équilibre à partir d’une probabilité supposée de ${(result.breakEvenProbability * 100).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %.`}
            </small>
          </>
        )}
      </div>
      <p className="fine-print">
        Hypothèses de simulation, sans économie garantie. Le score non calibré
        du modèle n’est pas utilisé comme probabilité. Une dépense couverte par
        un contrat ne constitue pas automatiquement un coût supplémentaire
        évitable.
      </p>
    </section>
  );
}
