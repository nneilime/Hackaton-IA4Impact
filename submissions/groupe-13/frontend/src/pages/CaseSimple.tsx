import { useEffect, useMemo, useState } from "react";
import { api, CASE_STATUSES, euro, fmtDate, RuleResult, User } from "../api";
import ImageViewer, { bboxOf, ZoneOverlay } from "../components/ImageViewer";
import { Zone } from "../components/ZoneInspector";
import { go, Modal, useToast } from "../components/ui";
import { DECISION_LABEL, issueTitle, PLAIN_STATUS, plainDoubt } from "../labels";
import { CorrectionModal } from "./CaseDesk";

/** Contrôle d'un dossier en mode simple (par défaut) : DOSSIER → ÉCART → PREUVE → DÉCISION.
 *  Seuls les éléments utiles à la décision sont affichés ; le détail technique est à la demande. */

const FIELD_OF_RULE: Record<string, string> = { R01: "Z1", R02: "Z2", R03: "Z3", R04: "Z4", R05: "Z5", R12: "Z8", R17: "Z12", R22: "Z15" };
const ZORDER = (r: RuleResult) => Math.min(...(r.zones.length ? r.zones.map(z => parseInt(z.slice(1))) : [99]));

interface Props { id: string; user: User; data: any; reload: () => void; onExpert: () => void; initialRule?: string | null }

export default function CaseSimple({ id, user, data, reload, onExpert, initialRule }: Props) {
  const a = data.analysis; const c = data.case; const ext = a.extraction;
  const results: RuleResult[] = a.results;
  const readOnly = user.role === "auditeur";
  const effective: Record<string, any> = data.finance?.decisions_effectives || {};
  const issues = useMemo(() => results.filter(r => ["ANOMALIE", "NON_VERIFIABLE", "ERREUR_TECHNIQUE"].includes(r.status))
    .sort((x, y) => (x.status === "ANOMALIE" ? 0 : 1) - (y.status === "ANOMALIE" ? 0 : 1) || ZORDER(x) - ZORDER(y)), [results]);
  const todo = issues.filter(r => !effective[r.rule_id]);
  const [cur, setCur] = useState<string | null>(null);
  const [allZones, setAllZones] = useState(false);
  const [zoneInfo, setZoneInfo] = useState<string | null>(null);
  const [fp, setFp] = useState<RuleResult | null>(null);
  const [corr, setCorr] = useState<any>(null);
  const [more, setMore] = useState(false);
  const [focus, setFocus] = useState<{ box: number[]; n: number } | null>(null);
  const toast = useToast();
  const zones: Zone[] = a.zones || [];
  const sel = issues.find(r => r.rule_id === cur) || null;

  const frameRule = (r: RuleResult | null) => {
    if (!r) return;
    const boxes = r.img_refs.filter(x => x.box).map(x => x.box!) as number[][];
    const zb = zones.filter(z => r.zones.includes(z.zone_id)).map(z => z.bbox).filter(Boolean) as number[][];
    const all = boxes.length ? boxes : zb;
    if (all.length) setFocus({ box: bboxOf(all.map(b => ({ box: b })))!, n: Date.now() });
  };
  const open = (rid: string | null) => { setCur(rid); setZoneInfo(null); frameRule(issues.find(r => r.rule_id === rid) || null); };
  // lien direct (?regle=R12) : l'écart est ouvert et cadré dès l'arrivée
  useEffect(() => { if (initialRule && issues.some(r => r.rule_id === initialRule)) setTimeout(() => open(initialRule), 80); }, []); // eslint-disable-line

  const idx = sel ? issues.indexOf(sel) : -1;
  const nextUndecided = (after: string) => {
    const i = issues.findIndex(r => r.rule_id === after);
    return [...issues.slice(i + 1), ...issues.slice(0, i)].find(r => !effective[r.rule_id] && r.rule_id !== after) || null;
  };
  const decide = async (kind: string, r: RuleResult, comment?: string) => {
    try {
      await api.post(`/api/cases/${id}/decisions`, { kind, rule_id: r.rule_id, comment });
      toast(`${DECISION_LABEL[kind]} — enregistré`);
      const n = nextUndecided(r.rule_id);
      reload(); if (n) open(n.rule_id); else setCur(null);
    } catch (e: any) { toast(`Échec : ${e.message}`); }
  };

  // ---------------- zones : problèmes mis en avant, zones conformes discrètes
  const overlays: ZoneOverlay[] = zones.map(z => ({ id: z.zone_id, label: z.label, status: z.status, regions: z.regions, flags: z.flags }));
  const selZone = sel ? sel.zones[0] : zoneInfo;
  const onZone = (zid: string) => {
    const first = issues.find(r => r.zones.includes(zid));
    if (first) open(first.rule_id); else { setCur(null); setZoneInfo(zid); const z = zones.find(x => x.zone_id === zid); if (z?.bbox) setFocus({ box: z.bbox, n: Date.now() }); }
  };

  // ---------------- résultat global en une phrase
  const nA = issues.filter(r => r.status === "ANOMALIE").length, nV = issues.length - nA;
  const headline = issues.length === 0 ? "Aucun écart : les 22 contrôles sont conformes ou sans objet."
    : [nA ? `${nA} écart${nA > 1 ? "s" : ""} à examiner` : "", nV ? `${nV} point${nV > 1 ? "s" : ""} à vérifier manuellement` : ""].filter(Boolean).join(" · ");
  const alerts: string[] = [];
  const ra = a.txt?.realignment;
  if (ra) alerts.push(`Fichier B2 mal formé : un caractère a été inséré en position ${ra.position}. Le fichier a été relu en le réalignant (${ra.preuves.length} vérifications le confirment) : à confirmer, et à signaler à l'établissement.`);
  if (a.pairing?.status && a.pairing.status !== "confirmé") alerts.push(`Le bordereau et le fichier ne semblent pas concerner le même dossier (rapprochement ${a.pairing.status}).`);
  (data.triage || []).filter((g: any) => g.id === "homologue").forEach((g: any) => alerts.push(g.hypothesis));

  return <div className="simple">
    {/* ÉTAPE 1 — le dossier */}
    <header className="s-head">
      <button className="btn small" onClick={() => go("/dossiers")}>← Dossiers</button>
      <div className="s-id">
        <h1>Facture <span className="mono">{c.invoice_no}</span></h1>
        <div className="muted">{c.establishment} · {euro(c.billed_cents)} · dossier <span className="mono">{c.id}</span>{a.source === "import" ? " · dossier importé" : ""}</div>
      </div>
      <div className={`s-result ${nA ? "bad" : nV ? "warn" : "ok"}`} role="status">{headline}</div>
      <span className="spacer" />
      {todo.length > 0 && !sel && <button className="btn primary big" onClick={() => open(todo[0].rule_id)}>Examiner les écarts</button>}
      <div className="s-more">
        <button className="btn" aria-expanded={more} onClick={() => setMore(!more)}>Autres actions ▾</button>
        {more && <div className="menu" onMouseLeave={() => setMore(false)}>
          <label className="menu-row">Statut du dossier
            <select className="input" value={c.status} disabled={readOnly}
              onChange={e => api.post(`/api/cases/${id}/decisions`, { kind: "statut", value: e.target.value }).then(() => { toast("Statut enregistré"); reload(); })}>
              {CASE_STATUSES.map(s => <option key={s} disabled={s === "Clôturé" && user.role === "agent"}>{s}</option>)}</select></label>
          {user.role === "agent" && !c.assigned_to && <button className="menu-item" onClick={() => api.post(`/api/cases/${id}/assign`, { user_id: user.id }).then(() => { toast("Dossier pris en charge"); reload(); })}>Prendre le dossier</button>}
          <a className="menu-item" href={`/api/cases/${id}/report.pdf`}>Rapport PDF</a>
          <button className="menu-item" onClick={onExpert}>Mode expert (22 contrôles, lectures, fichier complet)</button>
        </div>}
      </div>
    </header>
    {alerts.map((t, i) => <div key={i} className="notice bad s-alert">{t}</div>)}
    {data.job && <div className="notice warn s-alert">Analyse en cours pour ce dossier. <button className="btn small" onClick={reload}>Actualiser</button></div>}

    <div className="s-body">
      {/* ÉTAPE 2 — où sont les problèmes */}
      <section className="s-doc" aria-label="Bordereau">
        <ImageViewer src={`/api/cases/${id}/image`} size={ext.size} zones={overlays} showZones legend
          quiet={!allZones} selectedZone={selZone} onZoneClick={onZone} focusRect={focus} rotate180={ext.layout?.rotation === 180} />
        <div className="s-doc-foot">
          <label className="row small"><input type="checkbox" checked={allZones} onChange={e => setAllZones(e.target.checked)} /> Afficher les 15 zones</label>
          <span className="hint">Les zones conformes restent discrètes ; cliquez une zone pour son détail.</span>
        </div>
      </section>

      {/* ÉTAPE 3 — preuve et décision */}
      <section className="s-panel" aria-label="Écarts et décision">
        {!sel && !zoneInfo && <IssueList issues={issues} effective={effective} onOpen={open} headline={headline} />}
        {zoneInfo && !sel && <ZoneCard z={zones.find(z => z.zone_id === zoneInfo)!} onBack={() => setZoneInfo(null)} onExpert={onExpert} />}
        {sel && <div className="s-card" data-testid="issue-card">
          <div className="s-nav">
            <button className="btn small" onClick={() => setCur(null)}>← Liste</button>
            <span className="hint">{idx + 1} / {issues.length}</span>
            <span className="spacer" />
            <button className="btn small" disabled={idx <= 0} onClick={() => open(issues[idx - 1].rule_id)}>Précédente</button>
            <button className="btn small" disabled={idx >= issues.length - 1} onClick={() => open(issues[idx + 1].rule_id)}>Suivante</button>
          </div>
          <h2 className={`s-title ${sel.status}`}>{issueTitle(sel)}</h2>
          {sel.status !== "ANOMALIE" && <p className="s-doubt">{plainDoubt(sel.uncertainty?.reason) || "Le moteur ne peut pas conclure avec certitude."} Regardez la case ci-dessous et corrigez la lecture si besoin.</p>}
          <Proof id={id} r={sel} a={a} />
          {sel.gap?.amount_cents ? <div className="s-diff">{(sel.gap.type === "écart de montant" || sel.gap.type === "incohérence arithmétique")
            ? <><b>Différence :</b> {euro(Math.abs(sel.gap.amount_cents))}</>
            : <><b>Montant concerné :</b> {euro(Math.abs(sel.gap.amount_cents))} <span className="hint">({sel.gap.label})</span></>}</div> : null}
          {sel.details?.caractere_confusable && <p className="hint">Les deux valeurs ne diffèrent que d'un caractère souvent confondu ({sel.details.caractere_confusable}) : vérifiez ce chiffre sur l'image.</p>}
          {sel.details?.lecture_realignee && <p className="hint">Valeur du fichier lue après réalignement (fichier mal formé).</p>}
          <p className="s-expl">{sel.explanation}</p>
          {effective[sel.rule_id] && <div className="notice ok">Décision enregistrée : <b>{effective[sel.rule_id].label}</b> <span className="hint">— {effective[sel.rule_id].by || ""} {fmtDate(effective[sel.rule_id].at)}</span></div>}
          {!readOnly && <div className="s-actions">
            {sel.status === "ANOMALIE" && <>
              <button className="btn primary" onClick={() => decide("confirmation", sel)}>Confirmer l'écart</button>
              <button className="btn" onClick={() => setFp(sel)}>Faux positif</button>
            </>}
            {FIELD_OF_RULE[sel.rule_id] && ext.fields[FIELD_OF_RULE[sel.rule_id]] &&
              <button className={`btn ${sel.status !== "ANOMALIE" ? "primary" : ""}`} onClick={() => { const f = ext.fields[FIELD_OF_RULE[sel.rule_id]]; setCorr({ target: `fields.${f.field}`, label: f.business, current: f.value }); }}>Corriger la lecture</button>}
            {(sel.rule_id === "R21") && <button className="btn" onClick={() => setCorr({ target: "signatures.Z14.0", label: "Signature du directeur (zone 14)", current: ext.signatures.Z14[0]?.status, options: ["PRESENT", "VIDE"] })}>Corriger la détection</button>}
            <button className="btn" onClick={() => decide("revue_complementaire", sel)}>À revoir</button>
          </div>}
          <Details r={sel} a={a} decisions={data.decisions} onExpert={onExpert} />
        </div>}
        {todo.length === 0 && issues.length > 0 && !sel && <div className="notice ok" style={{ margin: 12 }}>
          Tous les écarts de ce dossier ont reçu une décision.
          {!readOnly && c.status !== "Contrôle terminé" && <button className="btn small primary" style={{ marginLeft: 8 }} onClick={() =>
            api.post(`/api/cases/${id}/decisions`, { kind: "statut", value: "Contrôle terminé" }).then(() => { toast("Dossier marqué « Contrôle terminé »"); reload(); })}>Terminer le contrôle</button>}
          <button className="btn small" style={{ marginLeft: 8 }} onClick={() => goNext(id)}>Dossier suivant →</button>
        </div>}
        {issues.length === 0 && <div className="s-card">
          <p>Les zones du bordereau concordent avec la facture. Vous pouvez terminer le contrôle.</p>
          {!readOnly && c.status !== "Contrôle terminé" && <button className="btn primary" onClick={() =>
            api.post(`/api/cases/${id}/decisions`, { kind: "statut", value: "Contrôle terminé" }).then(() => { toast("Dossier marqué « Contrôle terminé »"); reload(); })}>Terminer le contrôle</button>}
          <button className="btn" style={{ marginLeft: 8 }} onClick={() => goNext(id)}>Dossier suivant →</button>
        </div>}
      </section>
    </div>

    {fp && <Modal title="Déclarer un faux positif" onClose={() => setFp(null)}>
      <FpForm onCancel={() => setFp(null)} onOk={com => { const r = fp; setFp(null); decide("faux_positif", r, com); }} />
    </Modal>}
    {corr && <CorrectionModal c={corr} onClose={() => setCorr(null)} onSubmit={(v, comment) =>
      api.post<any>(`/api/cases/${id}/corrections`, { target: corr.target, corrected: v, comment }).then(r => {
        const zc = Object.entries(r?.effect?.zones || {}).map(([k, x]: any) => `${k} ${PLAIN_STATUS[x[0] as keyof typeof PLAIN_STATUS]} → ${PLAIN_STATUS[x[1] as keyof typeof PLAIN_STATUS]}`);
        toast(`Lecture ${r.kind === "validation" ? "validée" : "corrigée"} — contrôles recalculés${zc.length ? " · " + zc.join(", ") : ""}`);
        setCorr(null); reload();
      }).catch(e => toast(`Échec : ${e.message}`))} />}
  </div>;
}

async function goNext(id: string) {
  try {
    const o = await api.get<any>("/api/overview");
    const n = (o.queue || []).find((x: any) => x.id !== id);
    go(n ? `/controle/${n.id}` : "/");
  } catch { go("/"); }
}

function FpForm({ onCancel, onOk }: { onCancel: () => void; onOk: (c: string) => void }) {
  const [c, setC] = useState("");
  return <>
    <p className="small muted">Indiquez pourquoi l'écart signalé n'en est pas un (par exemple : lecture du document erronée).</p>
    <label className="field">Motif (obligatoire)<textarea className="input" value={c} onChange={e => setC(e.target.value)} autoFocus /></label>
    <div className="row" style={{ marginTop: 12, justifyContent: "flex-end" }}>
      <button className="btn" onClick={onCancel}>Annuler</button>
      <button className="btn primary" disabled={!c.trim()} onClick={() => onOk(c)}>Enregistrer</button>
    </div>
  </>;
}

function IssueList({ issues, effective, onOpen, headline }: { issues: RuleResult[]; effective: Record<string, any>; onOpen: (r: string) => void; headline: string }) {
  if (!issues.length) return <div className="s-card"><h2 className="s-title CONFORME">Aucun écart</h2><p className="muted">{headline}</p></div>;
  return <div className="s-card">
    <h2>Écarts et points à vérifier</h2>
    <ul className="s-list">{issues.map(r => <li key={r.rule_id}>
      <button onClick={() => onOpen(r.rule_id)} className={`s-item ${r.status}`}>
        <span className={`dot ${r.status}`} aria-hidden="true" />
        <span className="s-item-t">{issueTitle(r)}<span className="hint"> · {r.zones.join(", ")}</span></span>
        <span className={`s-dec ${effective[r.rule_id] ? "done" : ""}`}>{effective[r.rule_id] ? effective[r.rule_id].label : "à décider"}</span>
      </button></li>)}</ul>
  </div>;
}

/** La preuve : ce que dit le bordereau (agrandissement réel) et ce que dit le fichier (ligne surlignée). */
function Proof({ id, r, a }: { id: string; r: RuleResult; a: any }) {
  const lines = (a.txt?.records || []) as any[];
  const refs = (r.txt_refs || []).filter(x => x.line_no).slice(0, 2);
  return <div className="s-proof">
    <div className="s-side">
      <div className="k">Ce que dit le bordereau</div>
      <div className="v">{r.jpg_value ?? "—"}</div>
      <img className="s-crop" src={`/api/cases/${id}/crop?rule=${r.rule_id}&v=${a.analyzed_at}`} alt={`Agrandissement du bordereau pour ${r.rule_id}`} />
    </div>
    <div className="s-side">
      <div className="k">Ce que dit le fichier de facturation</div>
      <div className="v">{r.txt_value ?? "—"}</div>
      {refs.map((x, i) => {
        const L = lines.find(l => l.line_no === x.line_no); const raw: string = L ? (L.raw_original || L.raw) : "";
        const s = (x.start || 1) - 1, e = x.end || s + 1, from = Math.max(0, s - 14), to = Math.min(raw.length, e + 14);
        return <div key={i} className="s-line"><span className="hint">ligne {x.line_no}, positions {x.start}–{x.end} ({x.label})</span>
          <code>{from > 0 ? "…" : ""}{raw.slice(from, s)}<mark>{raw.slice(s, e)}</mark>{raw.slice(e, to)}{to < raw.length ? "…" : ""}</code></div>;
      })}
    </div>
  </div>;
}

function Details({ r, a, decisions, onExpert }: { r: RuleResult; a: any; decisions: any[]; onExpert: () => void }) {
  const hist = decisions.filter((d: any) => d.rule_id === r.rule_id);
  return <details className="s-details">
    <summary>Voir la règle {r.rule_id} et les détails techniques</summary>
    <dl className="kv">
      <dt>Règle</dt><dd><b>{r.rule_id}</b> — {r.title}<div className="hint">« {r.spec} »</div></dd>
      {r.convention && <><dt>Convention appliquée</dt><dd>{r.convention}{r.details?.interpretations && <div className="hint">Lecture littérale : {PLAIN_STATUS[r.details.interpretations.litterale as keyof typeof PLAIN_STATUS]} · convention : {PLAIN_STATUS[r.details.interpretations.convention as keyof typeof PLAIN_STATUS]} · décision : {r.details.interpretations.decision}</div>}</dd></>}
      <dt>Statut technique</dt><dd>{r.status}{r.uncertainty ? ` — incertitude ${r.uncertainty.level} : ${r.uncertainty.reason}` : ""}</dd>
      {r.txt_refs.length > 0 && <><dt>Positions B2</dt><dd>{r.txt_refs.slice(0, 6).map((x, i) => <div key={i}>{x.label} — ligne {x.line_no}{x.start ? `, pos. ${x.start}-${x.end}` : ""}</div>)}</dd></>}
      {r.img_refs.some(x => x.box) && <><dt>Coordonnées image</dt><dd className="mono small">{r.img_refs.filter(x => x.box).slice(0, 4).map(x => `[${x.box!.join(", ")}]`).join(" ")}</dd></>}
      <dt>Gabarit</dt><dd>{a.extraction.layout?.label} · recalage dx {a.extraction.layout?.dx}, dy {a.extraction.layout?.dy}{a.extraction.layout?.deskew_deg ? ` · redressé de ${a.extraction.layout.deskew_deg}°` : ""}</dd>
      <dt>Versions</dt><dd className="hint">moteur {r.engine_version} · règles {r.ruleset_version} · {fmtDate(r.processed_at)}</dd>
    </dl>
    {r.details?.lectures?.length > 0 && <table className="data small"><thead><tr><th>Moteur</th><th>Prétraitement</th><th>Lu</th><th>Confiance</th></tr></thead>
      <tbody>{r.details.lectures.map((l: any, i: number) => <tr key={i}><td>{l.moteur}</td><td>{l.pretraitement}</td><td className="mono">{l.texte}</td><td>{l.confiance ?? "—"}</td></tr>)}</tbody></table>}
    {hist.length > 0 && <><h4>Historique</h4><ul className="timeline">{hist.map((d: any) => <li key={d.id}>{DECISION_LABEL[d.kind] || d.kind} · {d.display_name} · {fmtDate(d.created_at)}{d.comment ? ` — « ${d.comment} »` : ""}</li>)}</ul></>}
    <button className="btn small" onClick={onExpert}>Ouvrir en mode expert</button>
  </details>;
}

function ZoneCard({ z, onBack, onExpert }: { z: Zone; onBack: () => void; onExpert: () => void }) {
  if (!z) return null;
  return <div className="s-card">
    <div className="s-nav"><button className="btn small" onClick={onBack}>← Liste</button></div>
    <h2 className={`s-title ${z.status}`}>{z.zone_id} — {z.label} : {PLAIN_STATUS[z.status]}</h2>
    <p>{z.explanation}</p>
    <button className="btn small" onClick={onExpert}>Voir le détail de la zone (mode expert)</button>
  </div>;
}
