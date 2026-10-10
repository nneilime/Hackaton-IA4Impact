import { useMemo, useState } from "react";
import { euro } from "../api";
import { ErrorBox, Loading, StatusPill, go, useFetch } from "../components/ui";
import { DECISION_LABEL, issueTitle } from "../labels";

export default function Anomalies({ params }: { params: URLSearchParams }) {
  const { data, error } = useFetch<any[]>("/api/anomalies");
  const [rule, setRule] = useState(params.get("regle") || "");
  const [st, setSt] = useState(params.get("statut") || "ANOMALIE");
  const [est, setEst] = useState("");
  const rows = useMemo(() => (data || []).filter(r => (!rule || r.rule_id === rule) && (!st || r.status === st) && (!est || r.establishment === est)), [data, rule, st, est]);
  if (error) return <ErrorBox e={error} />;
  if (!data) return <Loading />;
  const rules = [...new Set(data.map(r => r.rule_id))].sort();
  const ests = [...new Set(data.map(r => r.establishment))].sort();
  return <>
    <div className="page-head"><div><h1>Écarts à examiner</h1>
      <p>{rows.length} résultat(s). Un écart est une différence entre le bordereau et le fichier ; ce n'est pas une fraude. Les n° d'assurés sont masqués dans cette liste : ouvrez le dossier pour les voir.</p></div></div>
    <div className="panel">
      <div className="pane-head">
        <select className="input" value={st} onChange={e => setSt(e.target.value)} aria-label="Statut"><option value="ANOMALIE">Écarts</option><option value="NON_VERIFIABLE">À vérifier manuellement</option><option value="">Les deux</option></select>
        <select className="input" value={rule} onChange={e => setRule(e.target.value)} aria-label="Règle"><option value="">Toutes les règles</option>{rules.map(r => <option key={r}>{r}</option>)}</select>
        <select className="input" value={est} onChange={e => setEst(e.target.value)} aria-label="Établissement"><option value="">Tous les établissements</option>{ests.map(r => <option key={r}>{r}</option>)}</select>
      </div>
      <div className="table-wrap" style={{ maxHeight: "calc(100vh - 230px)" }}><table className="data">
        <thead><tr><th>Dossier</th><th>Écart</th><th>Statut</th><th>Bordereau</th><th>Fichier</th><th className="num">Différence</th><th>Décision</th></tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i} className="clickable" onClick={() => go(`/controle/${r.case_id}?regle=${r.rule_id}`)}>
          <td className="mono nowrap">{r.case_id}<div className="hint">{r.establishment}</div></td>
          <td>{issueTitle(r)}<div className="hint">{r.rule_id} · {(r.zones || []).join(", ")}</div></td>
          <td><StatusPill s={r.status} /></td>
          <td className="mono small">{r.jpg_value ?? "—"}</td><td className="mono small">{r.txt_value ?? "—"}</td>
          <td className="num nowrap">{r.gap_cents ? euro(r.gap_cents) : "—"}</td>
          <td className="small">{r.effective_decision ? DECISION_LABEL[r.effective_decision] || r.effective_decision : <span className="muted">à décider</span>}</td>
        </tr>)}</tbody></table></div>
    </div>
  </>;
}
