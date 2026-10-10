import { useState } from "react";
import { api, User } from "../api";
import { StatusPill, ErrorBox, Loading, useFetch, go, useToast } from "../components/ui";

export default function Rules({ user }: { user?: User }) {
  const { data, error } = useFetch<any>("/api/rules");
  const conv = useFetch<any>("/api/conventions");
  if (error) return <ErrorBox e={error} />;
  if (!data) return <Loading />;
  return <>
    <div className="page-head"><div><h1>Règles, zones et conventions</h1>
      <p>Les 22 contrôles sont une structuration technique du document « Les contrôles à implémenter » : chaque règle cite sa formulation d'origine et la convention d'interprétation retenue lorsque le texte laisse une ambiguïté.</p></div></div>
    <section className="panel" style={{ marginBottom: 14 }}>
      <div className="pane-head"><h3>Les 15 zones du bordereau et leurs contrôles</h3><span className="hint">table de correspondance utilisée par le cockpit des zones (aucune applicabilité ajoutée)</span></div>
      <table className="data"><thead><tr><th>Zone</th><th>Contenu</th><th>Règles associées</th></tr></thead>
        <tbody>{data.zones.map((z: any) => <tr key={z.zone_id}><td className="mono">{z.zone_id}</td><td><b>{z.label}</b><div className="hint">{z.description}</div></td>
          <td className="small">{z.rules.map((r: any) => <div key={r.rule_id}><span className="tag rule">{r.rule_id}</span> {r.role}</div>)}</td></tr>)}</tbody></table>
    </section>
    {Object.entries(data.categories).map(([cat, label]: any) => <section key={cat} className="panel" style={{ marginBottom: 14 }}>
      <div className="pane-head"><h3>{cat} — {label}</h3></div>
      <table className="data"><thead><tr><th>Règle</th><th>Formulation du cahier des charges</th><th>Convention</th><th>Résultats sur le corpus</th></tr></thead>
        <tbody>{data.rules.filter((r: any) => r.category === cat).map((r: any) => <tr key={r.id}>
          <td style={{ minWidth: 200 }}><span className="tag rule">{r.id}</span> <b>{r.title}</b><div className="hint">{r.zones.join(", ")}{r.txt_fields.length ? " · " + r.txt_fields.join(", ") : ""}</div></td>
          <td className="small">« {r.spec} »</td>
          <td className="small">{r.convention || <span className="muted">application littérale</span>}</td>
          <td><div className="row" style={{ gap: 4 }}>{Object.entries(r.counts).map(([s, n]: any) =>
            <span key={s} style={{ cursor: s === "ANOMALIE" || s === "NON_VERIFIABLE" ? "pointer" : undefined }} onClick={() => (s === "ANOMALIE" || s === "NON_VERIFIABLE") && go(`/anomalies?regle=${r.id}&statut=${s}`)}>
              <StatusPill s={s} short /> {n}</span>)}</div></td>
        </tr>)}</tbody></table>
    </section>)}
    <section className="panel panel-pad">
      <h2>Limites connues</h2>
      <ul className="small">
        <li>Le corpus ne contient aucune vérité terrain annotée : aucun taux de précision OCR n'est affirmé. Les corrections des agents constituent progressivement un référentiel de validation sur ces mêmes documents.</li>
        <li>Les gabarits de zones sont calibrés sur les trois mises en page du corpus ; un nouveau modèle de bordereau nécessite un nouveau gabarit (la mise en page non reconnue est signalée).</li>
        <li>La détection de signature constate la présence d'un élément ; elle ne certifie jamais l'authenticité.</li>
        <li>Un contrôle documentaire ne prouve pas qu'un soin a été réalisé, et une anomalie n'est pas une fraude.</li>
        <li>Aucune estimation d'économies n'est produite : le corpus n'est pas représentatif.</li>
      </ul>
    </section>
    <section className="panel" style={{ marginTop: 14 }}>
      <div className="pane-head"><h3>Centre de validation des conventions métier</h3><span className="hint">conventions proposées par l'équipe — à valider par la MSA (non officielles)</span></div>
      {!conv.data ? <Loading what="Calcul des effets des conventions sur le corpus" /> : <div className="panel-pad">
        <p className="hint">{conv.data.note}</p>
        {conv.data.conventions.map((c: any) => <div key={c.id} className="zrule" style={{ marginBottom: 10 }}>
          <div className="top"><span className="tag rule">{c.id}</span><b>{c.sujet}</b><span className="tag">{c.version_complete}</span>{c.regles.map((r: string) => <span key={r} className="tag rule">{r}</span>)}</div>
          {Object.entries(c.texte_regles).map(([r, t]: any) => <p key={r} className="small" style={{ margin: "4px 0" }}><b>{r}</b> — « {t} »</p>)}
          <dl className="kv small" style={{ marginTop: 6 }}>
            <dt>Ambiguïté</dt><dd>{c.constat}</dd>
            <dt>Convention appliquée</dt><dd>{c.convention}</dd>
            <dt>Dossiers concernés</dt><dd>{c.dossiers_concernes.length} / {conv.data.n_dossiers}{c.dossiers_concernes.length ? <span className="hint"> ({c.dossiers_concernes.slice(0, 8).join(", ")}{c.dossiers_concernes.length > 8 ? "…" : ""})</span> : null}</dd>
            <dt>Si la convention changeait</dt><dd>{c.effet_changement ? <>Alternative : {c.alternative} → <b>{c.effet_changement.resultats_modifies} résultat(s) modifié(s)</b> dans {c.effet_changement.dossiers_modifies} dossier(s)
              {Object.keys(c.effet_changement.par_transition).length > 0 && <span className="hint"> ({Object.entries(c.effet_changement.par_transition).map(([t, n]: any) => `${t.replace("NON_VERIFIABLE", "non vérifiable").replace(/CONFORME/g, "conforme").replace(/ANOMALIE/g, "anomalie").replace("NON_APPLICABLE", "non applicable")} : ${n}`).join(" ; ")})</span>}
              {c.effet_changement.detail.length > 0 && <details><summary className="small">Détail</summary><div className="small mono">{c.effet_changement.detail.slice(0, 40).map((d: any) => `${d.case_id} ${d.rule_id} ${d.actuel}→${d.alternatif}`).join(" · ")}</div></details>}</>
              : <span className="muted">{c.effet_non_simule}</span>}</dd>
            <dt>Décision de la MSA</dt><dd>{conv.data.decisions?.[c.id]
              ? <><b>{conv.data.decisions[c.id].decision}</b> <span className="hint">— réf. {conv.data.decisions[c.id].reference} · {conv.data.decisions[c.id].par} · {conv.data.decisions[c.id].le}</span></>
              : <span className="muted">aucune décision enregistrée : {c.statut}</span>}
              {user && (user.role === "superviseur" || user.role === "admin") && <DecisionForm amb={c.id} onDone={conv.reload} />}</dd>
          </dl></div>)}
      </div>}
    </section>
  </>;
}

function DecisionForm({ amb, onDone }: { amb: string; onDone: () => void }) {
  const [ref, setRef] = useState("");
  const [open, setOpen] = useState(false);
  const toast = useToast();
  const send = (decision: string) => api.post<any>(`/api/conventions/${amb}/decision`, { decision, reference: ref || "retour à la convention proposée" })
    .then(r => { toast(r.applique_au_moteur ? "Décision enregistrée — réanalyse des dossiers lancée" : "Décision enregistrée (tracée ; sans effet sur le moteur pour cette convention)"); setOpen(false); onDone(); })
    .catch(e => toast(`Échec : ${e.message}`));
  if (!open) return <div><button className="btn small" style={{ marginTop: 4 }} onClick={() => setOpen(true)}>Enregistrer la décision de la MSA…</button></div>;
  return <div className="row" style={{ marginTop: 6, flexWrap: "wrap" }}>
    <input className="input" style={{ minWidth: 260 }} placeholder="Référence (courrier, note, compte rendu)" value={ref} onChange={e => setRef(e.target.value)} />
    <button className="btn small ok" disabled={ref.trim().length < 3} onClick={() => send("validée")}>Convention validée</button>
    <button className="btn small danger" disabled={ref.trim().length < 3} onClick={() => send("rejetée")}>Convention rejetée</button>
    <button className="btn small" onClick={() => send("proposée")}>Revenir à « proposée »</button>
    <button className="btn small" onClick={() => setOpen(false)}>Annuler</button>
  </div>;
}
