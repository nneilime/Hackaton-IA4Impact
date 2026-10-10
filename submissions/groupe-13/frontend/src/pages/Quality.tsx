import { useState } from "react";
import { api, User } from "../api";
import { ErrorBox, Loading, useFetch, useToast } from "../components/ui";
import { issueTitle, PLAIN_STATUS } from "../labels";

const pct = (v: number | null | undefined) => v === null || v === undefined ? <span className="muted">indisponible</span> : `${(v * 100).toFixed(1).replace(".", ",")} %`;

export default function Quality({ user, tab }: { user: User; tab: "mesures" | "validation" }) {
  const canMeasure = user.role !== "agent";
  const t = canMeasure ? tab : "validation";
  return <>
    <div className="tabs" role="tablist" style={{ marginBottom: 12 }}>
      {canMeasure && <a role="tab" className={`tab ${t === "mesures" ? "on" : ""}`} href="#/qualite">Mesures</a>}
      <a role="tab" className={`tab ${t === "validation" ? "on" : ""}`} href="#/qualite?onglet=validation">Référentiel de validation</a>
    </div>
    {t === "mesures" ? <><Metrics /><Measures /></> : <Validation user={user} />}
  </>;
}

/** Précision, rappel et matrice de confusion — uniquement sur les validations HUMAINES. */
function Metrics() {
  const { data: m } = useFetch<any>("/api/validation/metrics");
  if (!m) return null;
  const x = m.matrice;
  return <section className="panel panel-pad" style={{ marginBottom: 12 }}>
    <h2>Exactitude des alertes sur le référentiel validé</h2>
    <p className="hint">Référentiel : {m.taille_referentiel} contrôle(s) validé(s) par {m.validateurs} validateur(s) humain(s) · {m.double_revue} en double revue · {m.desaccords} désaccord(s).
      La revue assistée par IA ({Object.values(m.revue_assistee || {}).reduce((a: number, b: any) => a + b, 0)} pré-examens) est exclue.</p>
    <div className="kpis">
      <div className="kpi"><div className="v">{pct(m.precision)}<span className="hint" style={{ fontSize: 12, marginLeft: 6 }}>n = {x.VP + x.FP}</span></div><div className="l">Précision</div><div className="d">VP / (VP + FP)</div></div>
      <div className="kpi"><div className="v">{pct(m.rappel)}<span className="hint" style={{ fontSize: 12, marginLeft: 6 }}>n = {x.VP + x.FN}</span></div><div className="l">Rappel</div><div className="d">VP / (VP + FN)</div></div>
    </div>
    <table className="data" style={{ maxWidth: 560 }}><thead><tr><th>Moteur ↓ / validateur →</th><th className="num">Écart réel</th><th className="num">Pas d'écart</th></tr></thead>
      <tbody><tr><th>Écart signalé</th><td className="num">{x.VP} (VP)</td><td className="num">{x.FP} (FP)</td></tr>
        <tr><th>Conforme</th><td className="num">{x.FN} (FN)</td><td className="num">{x.VN} (VN)</td></tr>
        <tr><th>À vérifier</th><td className="num">{x.NV_sur_ecart_reel}</td><td className="num">{x.NV_sur_conforme}</td></tr></tbody></table>
    {Object.keys(m.causes_faux_positifs).length > 0 && <><h3 style={{ marginTop: 10 }}>Causes des faux positifs</h3>
      <ul>{Object.entries(m.causes_faux_positifs).map(([k, v]: any) => <li key={k}><b>{k}</b> {v.libelle} : {v.n}</li>)}</ul></>}
    <p className="hint">{m.note}</p>
  </section>;
}

function Validation({ user }: { user: User }) {
  const { data, error, reload } = useFetch<any>("/api/validation");
  const [only, setOnly] = useState<"todo" | "all">("todo");
  const [cur, setCur] = useState<number>(0);
  const toast = useToast();
  if (error) return <ErrorBox e={error} />;
  if (!data) return <Loading />;
  const items = data.items.filter((i: any) => only === "all" || !i.ma_validation);
  const it = items[Math.min(cur, items.length - 1)];
  const save = async (verdict: string, cause?: string, comment?: string) => {
    try {
      await api.post("/api/validation", { case_id: it.case_id, rule_id: it.rule_id, verdict, cause, comment });
      toast("Validation enregistrée"); reload();
    } catch (e: any) { toast(`Échec : ${e.message}`); }
  };
  return <section className="panel panel-pad">
    <h2>Référentiel de validation humaine</h2>
    <p className="hint">Pour chaque contrôle, regardez l'agrandissement du bordereau et la valeur du fichier, puis dites ce qui est vrai.
      Sont proposés : toutes les alertes et un échantillon fixe d'un contrôle conforme sur dix (pour mesurer les écarts manqués).
      Votre validation porte votre nom et la date ; un second validateur peut se prononcer (double revue).</p>
    <div className="row" style={{ margin: "8px 0" }}>
      <label className="row small"><input type="radio" checked={only === "todo"} onChange={() => { setOnly("todo"); setCur(0); }} /> Non validés par moi ({data.items.filter((i: any) => !i.ma_validation).length})</label>
      <label className="row small"><input type="radio" checked={only === "all"} onChange={() => { setOnly("all"); setCur(0); }} /> Tous ({data.items.length})</label>
    </div>
    {!it ? <p className="muted">Rien à valider.</p> : <div className="s-card" style={{ margin: 0 }}>
      <div className="s-nav"><span className="hint">{Math.min(cur, items.length - 1) + 1} / {items.length}</span><span className="spacer" />
        <button className="btn small" disabled={cur <= 0} onClick={() => setCur(cur - 1)}>Précédent</button>
        <button className="btn small" disabled={cur >= items.length - 1} onClick={() => setCur(cur + 1)}>Suivant</button></div>
      <h3><a href={`#/controle/${it.case_id}?regle=${it.rule_id}`} className="mono">{it.case_id}</a> · {it.rule_id} — {issueTitle(it)}
        <span className="hint"> · moteur : {PLAIN_STATUS[it.status as keyof typeof PLAIN_STATUS]}{it.echantillon_conformes ? " (échantillon de conformes)" : ""}</span></h3>
      <div className="s-proof">
        <div className="s-side"><div className="k">Bordereau (lecture du moteur)</div><div className="v">{it.jpg_value ?? "—"}</div>
          <img className="s-crop" src={`/api/cases/${it.case_id}/crop?rule=${it.rule_id}`} alt="Agrandissement du bordereau" /></div>
        <div className="s-side"><div className="k">Fichier</div><div className="v">{it.txt_value ?? "—"}</div><p className="small">{it.explanation}</p></div>
      </div>
      {it.revue_assistee && <p className="hint">Pré-examen assisté par IA (non compté) : {data.verdicts[it.revue_assistee.verdict]} — {it.revue_assistee.commentaire}</p>}
      {it.consensus && <p className="small">Validations humaines : {it.consensus.details.map((d: any) => `${d.validateur} : ${data.verdicts[d.verdict]}`).join(" · ")}
        {it.consensus.verdict === "desaccord" && <b style={{ color: "var(--ano)" }}> — désaccord entre validateurs</b>}</p>}
      {user.role !== "auditeur" && <ValidateForm it={it} verdicts={data.verdicts} causes={data.causes} onSave={save} />}
    </div>}
  </section>;
}

function ValidateForm({ it, verdicts, causes, onSave }: any) {
  const [cause, setCause] = useState("");
  const [com, setCom] = useState("");
  const ano = it.status === "ANOMALIE";
  const opts = ano ? ["ecart_reel", "faux_positif", "indetermine"] : ["conforme_confirme", "ecart_manque", "ecart_reel", "indetermine"];
  return <div style={{ marginTop: 8 }}>
    <label className="field">Commentaire (facultatif)<input className="input" value={com} onChange={e => setCom(e.target.value)} /></label>
    {ano && <label className="field">Cause, si faux positif<select className="input" value={cause} onChange={e => setCause(e.target.value)}>
      <option value="">—</option>{Object.entries(causes).map(([k, v]: any) => <option key={k} value={k}>{k} — {v}</option>)}</select></label>}
    <div className="s-actions">{opts.filter((o: string) => verdicts[o]).map((o: string) =>
      <button key={o} className={`btn ${o === "ecart_reel" || o === "conforme_confirme" ? "primary" : ""}`}
        disabled={o === "faux_positif" && !cause} onClick={() => { onSave(o, o === "faux_positif" ? cause : undefined, com); setCom(""); setCause(""); }}>{verdicts[o]}</button>)}</div>
  </div>;
}

function Measures() {
  const { data: q, error } = useFetch<any>("/api/quality");
  if (error) return <ErrorBox e={error} />;
  if (!q) return <Loading />;
  const o = q.ocr, al = q.alertes;
  return <>
    <div className="page-head"><div><h1>Qualité mesurée de l'OCR et des alertes</h1>
      <p>Le corpus ne contient pas de vérité terrain : le référentiel se construit à partir des lectures <b>validées</b> ou <b>corrigées</b> par les agents.
        Chaque taux affiche son effectif ; sans donnée, il est « indisponible », jamais 100 %.</p></div></div>
    <div className="kpis">
      <div className="kpi"><div className="v">{o.champs_verifies}</div><div className="l">Champs vérifiés par un agent</div><div className="d">{o.validations_humaines} validation(s), {o.corrections_humaines} correction(s)</div></div>
      <div className="kpi"><div className="v">{pct(al.precision)}<span className="hint" style={{ fontSize: 12, marginLeft: 6 }}>n = {al.confirmees + al.faux_positifs}</span></div><div className="l">Précision des alertes</div><div className="d">{al.confirmees} confirmée(s) / {al.confirmees + al.faux_positifs} décidée(s)</div></div>
      <div className="kpi"><div className="v">{pct(al.rappel)}{al.rappel !== null && <span className="hint" style={{ fontSize: 12, marginLeft: 6 }}>effectif faible</span>}</div><div className="l">Rappel sur cas annotés</div><div className="d">{al.dossiers_annotes} dossier(s) annoté(s) · {al.omissions_signalees} omission(s) signalée(s)</div></div>
      <div className="kpi"><div className="v">{pct(al.taux_faux_positifs)}</div><div className="l">Faux positifs après revue</div><div className="d">parmi les alertes décidées</div></div>
      <div className="kpi"><div className="v">{pct(al.taux_non_verifiables)}</div><div className="l">Contrôles non vérifiables</div><div className="d">sur {al.controles} contrôles du corpus</div></div>
    </div>
    <div className="grid cols-2">
      <section className="panel panel-pad">
        <h2>Exactitude de l'OCR par type de champ</h2>
        {Object.keys(o.par_type).length === 0 ? <p className="muted">Indisponible : aucune lecture n'a encore été validée ou corrigée par un agent. Utilisez « Corriger / valider » dans la fiche d'une zone.</p> :
          <table className="data"><thead><tr><th>Type de champ</th><th className="num">Vérifiés</th><th className="num">Corrects</th><th className="num">Exactitude</th></tr></thead>
            <tbody>{Object.entries(o.par_type).map(([k, v]: any) => <tr key={k}><td>{k}</td><td className="num">{v.verifies}</td><td className="num">{v.corrects}</td><td className="num">{pct(v.exactitude)}</td></tr>)}</tbody></table>}
        <h2 style={{ marginTop: 14 }}>Par zone</h2>
        {Object.keys(o.par_zone).length === 0 ? <p className="muted">Indisponible.</p> :
          <table className="data"><thead><tr><th>Zone</th><th className="num">Vérifiés</th><th className="num">Exactitude</th></tr></thead>
            <tbody>{Object.entries(o.par_zone).sort((a: any, b: any) => Number(a[0].slice(1)) - Number(b[0].slice(1))).map(([k, v]: any) => <tr key={k}><td className="mono">{k}</td><td className="num">{v.verifies}</td><td className="num">{pct(v.exactitude)}</td></tr>)}</tbody></table>}
      </section>
      <section className="panel panel-pad">
        <h2>Désaccords entre moteurs OCR</h2>
        <p className="hint">Mesurable sans vérité terrain : champs dont les moteurs OCR soutiennent des valeurs différentes (lectures divergentes ou ex æquo).</p>
        <table className="data"><thead><tr><th>Zone</th><th className="num">Champs</th><th className="num">Désaccords</th><th className="num">Illisibles</th><th className="num">Taux de désaccord</th></tr></thead>
          <tbody>{Object.entries(o.desaccords_moteurs_par_zone).map(([k, v]: any) => <tr key={k}><td className="mono">{k}</td><td className="num">{v.champs}</td><td className="num">{v.desaccords}</td><td className="num">{v.illisibles}</td><td className="num">{pct(v.champs ? v.desaccords / v.champs : null)}</td></tr>)}</tbody></table>
        <p className="hint" style={{ marginTop: 6 }}>Un champ « illisible » est souvent une case vide imprimée (ex. sous-total 2 sans prestation) : il n'est pas compté comme un désaccord.</p>
      </section>
    </div>
    <p className="hint" style={{ marginTop: 12 }}>{q.note}</p>
  </>;
}
