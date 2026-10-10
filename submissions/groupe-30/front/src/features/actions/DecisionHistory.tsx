import type { Inspection } from "../../domain/types";
import { dateLabel } from "../../domain/rules";

export function DecisionHistory({ action }: { action: Inspection }) {
  return (
    <details className="decision-history">
      <summary>Historique des décisions ({action.history.length})</summary>
      <ol>
        {[...action.history].reverse().map((event, index) => (
          <li key={`${event.date}-${index}`}>
            <strong>{event.label}</strong>
            <time>
              {dateLabel(event.date)} ·{" "}
              {new Date(event.date).toLocaleTimeString("fr-FR", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </time>
            <p>{event.note}</p>
            {event.outcome && <small>Retour terrain : {event.outcome}</small>}
          </li>
        ))}
      </ol>
    </details>
  );
}
