import { fmtDate, User } from "../api";
import { ErrorBox, Loading, go, useFetch } from "../components/ui";

/** Accueil de l'agent (version 3.0) : une action principale — contrôler le dossier suivant — et la liste
 *  des dossiers à traiter, dans l'ordre proposé. Les indicateurs détaillés sont dans le pilotage. */
export default function Overview({ user }: { user: User }) {
  const { data: o, error } = useFetch<any>("/api/overview");
  if (error) return <ErrorBox e={error} />;
  if (!o) return <Loading />;
  const next = o.queue[0];
  const result = (c: any) => c.n_anomalies ? `${c.n_anomalies} écart${c.n_anomalies > 1 ? "s" : ""}${c.n_nv ? ` · ${c.n_nv} à vérifier` : ""}`
    : c.n_nv ? `${c.n_nv} point${c.n_nv > 1 ? "s" : ""} à vérifier` : "Aucun écart";
  return <>
    <div className="page-head">
      <div>
        <h1>Bonjour {user.display_name}</h1>
        <p>{o.a_controler + o.en_cours} dossier(s) à traiter · {o.verifies} déjà vérifié(s) sur {o.accessible}.</p>
      </div>
      {next && <button className="btn primary big" onClick={() => go(`/controle/${next.id}`)}>Contrôler le dossier suivant → <span className="mono">{next.id}</span></button>}
    </div>
    <section className="panel">
      <div className="pane-head"><h3>À traiter</h3><span className="hint">dans l'ordre proposé (score paramétrable, pas une norme MSA)</span>
        <span className="spacer" /><a className="btn small" href="#/dossiers?status=verifies">Retrouver un dossier traité</a></div>
      <div className="table-wrap"><table className="data">
        <thead><tr><th>Dossier</th><th>Établissement</th><th>Résultat</th><th>Statut</th></tr></thead>
        <tbody>{o.queue.map((c: any) => <tr key={c.id} className="clickable" onClick={() => go(`/controle/${c.id}`)}>
          <td className="mono">{c.id}{c.priority_override === "haute" && <span className="tag" style={{ marginLeft: 6 }}>priorité haute</span>}</td>
          <td>{c.establishment}</td>
          <td><span className={`s-pill ${c.n_anomalies ? "bad" : c.n_nv ? "warn" : "ok"}`}>{result(c)}</span></td>
          <td><span className="case-status">{c.status}</span></td></tr>)}</tbody>
      </table></div>
    </section>
    <details className="panel panel-pad" style={{ marginTop: 12 }}>
      <summary><b>Mes dernières décisions</b></summary>
      {o.decisions_recentes.length === 0 ? <p className="muted">Aucune décision enregistrée pour l'instant.</p> :
        <ul className="timeline">{o.decisions_recentes.map((d: any) => <li key={d.id}>
          <a href={`#/controle/${d.case_id}`} className="mono">{d.case_id}</a> — {d.display_name} : {d.kind.replace("_", " ")}{d.rule_id ? ` (${d.rule_id})` : ""}{d.value ? ` → ${d.value}` : ""}
          <div className="hint">{fmtDate(d.created_at)}</div></li>)}</ul>}
    </details>
  </>;
}
