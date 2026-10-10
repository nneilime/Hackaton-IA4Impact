import { CaseRow, fmtDate, User } from "../api";
import { ErrorBox, Loading, go, useFetch } from "../components/ui";

const TRI: Record<string, string> = { identification: "Identifiants du dossier", ghs: "Numéro GHS", code: "Code différent entre les deux documents",
  montant: "Écart de total expliqué par une ligne", ocr: "Lectures OCR incertaines", structure: "Structure du fichier TXT" };
const ACTIVE = ["En analyse", "Anomalie à vérifier", "Revue complémentaire nécessaire", "Écart confirmé"];

export default function Investigations({ user }: { user: User }) {
  const { data, error } = useFetch<CaseRow[]>("/api/cases");
  const ov = useFetch<any>("/api/overview");
  const tri = useFetch<any>("/api/triage");
  if (error) return <ErrorBox e={error} />;
  if (!data) return <Loading />;
  const groups = ACTIVE.map(s => ({ s, rows: data.filter(c => c.status === s) }));
  const closed = data.filter(c => ["Faux positif reconnu", "Contrôle terminé", "Clôturé"].includes(c.status));
  return <>
    <div className="page-head"><div><h1>Investigations</h1>
      <p>Dossiers en cours d'instruction, regroupés par statut. L'escalade vers le superviseur, la décision motivée et la clôture se font depuis l'écran de contrôle du dossier.
        {user.role === "agent" ? " La clôture est réservée au gestionnaire de caisse." : ""}</p></div></div>
    <div className="grid cols-2">
      {groups.map(g => <section key={g.s} className="panel">
        <div className="pane-head"><h3>{g.s}</h3><span className="tag">{g.rows.length}</span></div>
        {g.rows.length === 0 ? <p className="empty small">Aucun dossier.</p> :
          <table className="data"><tbody>{g.rows.map(c => <tr key={c.id} className="clickable" onClick={() => go(`/controle/${c.id}`)}>
            <td className="mono">{c.id}</td><td>{c.establishment}</td><td>{c.anomaly_rules.join(", ") || "—"}</td><td>{c.assigned_name || "non affecté"}</td></tr>)}</tbody></table>}
      </section>)}
      <section className="panel">
        <div className="pane-head"><h3>Terminés ou clôturés</h3><span className="tag">{closed.length}</span></div>
        {closed.length === 0 ? <p className="empty small">Aucun dossier.</p> :
          <table className="data"><tbody>{closed.map(c => <tr key={c.id} className="clickable" onClick={() => go(`/controle/${c.id}`)}>
            <td className="mono">{c.id}</td><td>{c.status}</td><td>{c.assigned_name || "—"}</td></tr>)}</tbody></table>}
      </section>
      <section className="panel" style={{ gridColumn: "1 / -1" }}>
        <div className="pane-head"><h3>Regroupements d'alertes</h3><span className="hint">hypothèses d'aide au tri — chaque règle reste décidée individuellement, sans score de fraude</span></div>
        <div className="panel-pad">{!tri.data ? <Loading /> : Object.keys(tri.data).length === 0 ? <p className="muted">Aucun regroupement.</p> :
          Object.entries(tri.data).map(([type, gs]: any) => <div key={type} style={{ marginBottom: 12 }}>
            <h3>{TRI[type] || type} <span className="tag">{gs.length} dossier(s)</span></h3>
            <table className="data small"><tbody>{gs.slice(0, 12).map((g: any, k: number) => <tr key={k} className="clickable" onClick={() => go(`/controle/${g.case_id}`)}>
              <td className="mono nowrap">{g.case_id}</td><td>{g.hypothesis}</td><td className="nowrap">{g.rules.join(", ")}</td></tr>)}</tbody></table>
            {gs.length > 12 && <p className="hint">… et {gs.length - 12} autre(s).</p>}</div>)}</div>
      </section>
      <section className="panel">
        <div className="pane-head"><h3>Dernières remarques</h3></div>
        <div className="panel-pad">
          {!ov.data ? <Loading /> : ov.data.decisions_recentes.filter((d: any) => d.comment).length === 0 ? <p className="muted">Aucune remarque enregistrée.</p> :
            <ul className="timeline">{ov.data.decisions_recentes.filter((d: any) => d.comment).map((d: any) => <li key={d.id}>
              <a className="mono" href={`#/controle/${d.case_id}`}>{d.case_id}</a> — {d.display_name} : « {d.comment} »<div className="hint">{fmtDate(d.created_at)}</div></li>)}</ul>}
        </div>
      </section>
    </div>
  </>;
}
