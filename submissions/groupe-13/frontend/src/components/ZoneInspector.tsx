import { euro, fmtDate, RuleStatus, STATUS_LABEL } from "../api";
import { Hl } from "./TxtViewer";
import { StatusPill } from "./ui";

export interface Zone {
  zone_id: string; label: string; description: string; regions: { box: number[]; label: string; role: string }[]; bbox: number[] | null;
  localisation: string; related_rules: { rule_id: string; role: string }[]; status: RuleStatus; flags: string[]; reason: string;
  explanation: string; counts: Record<string, number>; needs_human_review: boolean; rule_results: any[]; extracted: any;
  txt: { links: any[]; absence?: string | null }; traceability: any;
}

const AG: Record<string, string> = {
  concordant: "lectures concordantes", majoritaire: "majorité des moteurs", lecture_unique: "une seule lecture valide",
  divergent: "moteurs en désaccord", illisible: "illisible", vide: "zone vide", "corrigé": "corrigé / validé par un agent",
};
const FLAG: Record<string, string> = {
  controles_egalement_incertains: "Contrôles également incertains", mixte: "Résultats mixtes",
  conformite_sur_lecture_isolee: "Conformité sur lecture isolée",
};
const fmtVal = (v: any, money = false) => v === null || v === undefined || v === "" ? "—" : money && typeof v === "number" ? euro(v) : String(v);
const MONEY = new Set(["Z8", "Z12", "Z13", "ST1", "ST2", "ST3"]);

interface Props {
  zones: Zone[]; selected: string | null; onSelect: (id: string | null) => void;
  onFocusBox: (box: number[]) => void; onTxt: (h: Hl[]) => void; readOnly: boolean;
  decisions: any[]; corrections: any[]; effective: Record<string, any>;
  onDecision: (kind: string, rule?: string, title?: string, needComment?: boolean, value?: string) => void;
  onCorrect: (c: { target: string; label: string; current: any; options?: string[] }) => void;
  onOpenRule: (rid: string) => void;
}

export default function ZoneInspector({ zones, selected, onSelect, onFocusBox, onTxt, readOnly, decisions, corrections, effective, onDecision, onCorrect, onOpenRule }: Props) {
  const idx = zones.findIndex(z => z.zone_id === selected);
  const z = idx >= 0 ? zones[idx] : null;
  const go = (d: number) => onSelect(zones[(Math.max(0, idx) + d + zones.length) % zones.length].zone_id);
  const counts = zones.reduce((m: any, x) => (m[x.status] = (m[x.status] || 0) + 1, m), {});

  return <div className="pane-body" data-testid="zone-inspector">
    <div className="zchips" role="toolbar" aria-label="Zones Z1 à Z15">
      {zones.map(x => <button key={x.zone_id} className={`zchip ${x.status} ${x.zone_id === selected ? "on" : ""}`} data-chip={x.zone_id}
        title={`${x.zone_id} — ${x.label} — ${STATUS_LABEL[x.status]}`} aria-pressed={x.zone_id === selected}
        onClick={() => onSelect(x.zone_id === selected ? null : x.zone_id)}>{x.zone_id}</button>)}
    </div>
    <div className="znav">
      <button className="btn small" onClick={() => go(-1)} aria-label="Zone précédente">← Précédente</button>
      <span className="small">{z ? <><b>{z.zone_id}</b> · {idx + 1} / 15</> : "Aucune zone sélectionnée"}</span>
      <button className="btn small" onClick={() => go(z ? 1 : 0)} aria-label="Zone suivante">Suivante →</button>
      <button className="btn small" onClick={() => onSelect(null)}>Toutes les zones</button>
      <span className="spacer" />
      <span className="hint"><span className="kbd">[</span> <span className="kbd">]</span> naviguer · <span className="kbd">Échap</span> tout afficher</span>
    </div>

    {!z && <>
      <p className="hint" style={{ padding: "8px 12px 0" }}>
        {counts.ANOMALIE || 0} zone(s) en anomalie · {counts.NON_VERIFIABLE || 0} non vérifiable(s) · {counts.CONFORME || 0} conforme(s) · {counts.NON_APPLICABLE || 0} non applicable(s){counts.ERREUR_TECHNIQUE ? ` · ${counts.ERREUR_TECHNIQUE} en erreur technique` : ""}.
        Cliquez une zone ici ou sur le bordereau : elle est cadrée et ses contrôles sont détaillés.</p>
      <div className="zgrid">
        {zones.map(x => <button key={x.zone_id} className={`ztile ${x.status}`} onClick={() => onSelect(x.zone_id)} data-tile={x.zone_id}>
          <span className="row" style={{ justifyContent: "space-between" }}><span className="zid">{x.zone_id}</span><StatusPill s={x.status} /></span>
          <span className="zl">{x.label}</span>
          <span className="zc">{x.related_rules.length} règle(s){x.counts.ANOMALIE ? ` · ${x.counts.ANOMALIE} anomalie(s)` : ""}{x.counts.NON_VERIFIABLE ? ` · ${x.counts.NON_VERIFIABLE} non vérif.` : ""}</span>
          {x.needs_human_review && <span className="flag grey" title="Une vérification humaine est nécessaire">Revue humaine</span>}
        </button>)}
      </div>
    </>}

    {z && <ZoneSheet z={z} onFocusBox={onFocusBox} onTxt={onTxt} readOnly={readOnly} decisions={decisions} corrections={corrections}
      effective={effective} onDecision={onDecision} onCorrect={onCorrect} onOpenRule={onOpenRule} />}
  </div>;
}

function ZoneSheet({ z, onFocusBox, onTxt, readOnly, decisions, corrections, effective, onDecision, onCorrect, onOpenRule }: any) {
  const rules = new Set(z.related_rules.map((r: any) => r.rule_id));
  const f = z.extracted.field;
  const zDecisions = decisions.filter((d: any) => (d.rule_id && rules.has(d.rule_id)) || d.value === z.zone_id);
  const targets = new Set<string>([f?.target, ...((z.extracted.signatures || []).map((s: any) => s.target))].filter(Boolean));
  const zCorr = corrections.filter((c: any) => targets.has(c.target) || c.target.startsWith(`tables.${z.zone_id}.`) ||
    (z.zone_id === "Z9" && c.target.startsWith("tables.Z10.") && c.target.endsWith(".executant")) ||
    (z.zone_id === "Z6" && /fields\.ST[12]/.test(c.target)) || (z.zone_id === "Z7" && c.target === "fields.ST3"));
  const notVerifiable = z.rule_results.filter((r: any) => r.status === "NON_VERIFIABLE");
  const worst = z.rule_results.find((r: any) => r.status === "ANOMALIE") || notVerifiable[0] || z.rule_results.find((r: any) => r.status === "ERREUR_TECHNIQUE");
  const txtHl = (l: any): Hl => ({ line_no: l.line_no, start: l.start, end: l.end, label: l.label || l.code });

  return <div className="zsheet" data-testid="zone-sheet" data-zone={z.zone_id} data-status={z.status}>
    <div className="zhead">
      <span className="tag rule">{z.zone_id}</span><h2>{z.label}</h2><StatusPill s={z.status} />
      {z.flags.map((fl: string) => <span key={fl} className="flag grey">{FLAG[fl] || fl}</span>)}
    </div>
    <p className="small muted" style={{ marginTop: 4 }}>{z.description}</p>
    <div className={`zwhy ${z.status}`}><b>Zone {z.zone_id.slice(1)} — {STATUS_LABEL[z.status as RuleStatus]}.</b> {z.reason} <span className="muted">{z.explanation}</span></div>
    <div className="row" style={{ marginTop: 8 }}>
      {z.regions.length ? <button className="btn small" onClick={() => onFocusBox(z.bbox)}>Recadrer la zone</button> : null}
      <span className="hint">{z.localisation} · {z.regions.length} région(s){z.regions.length > 1 ? " : " + z.regions.map((r: any) => r.label).join(", ") : ""}</span>
    </div>

    <h4>Contrôles associés ({z.rule_results.length})</h4>
    {z.rule_results.map((r: any) => {
      const eff = effective?.[r.rule_id];
      return <div key={r.rule_id} className="zrule" data-rule={r.rule_id}>
        <div className="top"><button className="tag rule" style={{ border: 0, cursor: "pointer" }} onClick={() => onOpenRule(r.rule_id)} title="Ouvrir dans la liste des 22 contrôles">{r.rule_id}</button>
          <b className="small">{r.title}</b><StatusPill s={r.status} />{eff && <span className="tag">{eff.label} — {eff.by}</span>}</div>
        <div className="role">{r.role}</div>
        <p className="small" style={{ margin: "4px 0" }}>{r.explanation}</p>
        {(r.jpg_value || r.txt_value) && <div className="vs">
          <div><div className="k">Bordereau (JPG)</div><div className="v">{r.jpg_value ?? "—"}</div></div>
          <div><div className="k">Fichier (TXT)</div><div className="v">{r.txt_value ?? "—"}</div></div></div>}
        {r.gap?.amount_cents ? <div className="small">Écart mesuré : <b>{euro(r.gap.amount_cents)}</b> ({r.gap.label})</div> : null}
        {r.uncertainty && <div className="small muted">Incertitude {r.uncertainty.level} : {r.uncertainty.reason}</div>}
        {r.txt_refs?.length > 0 && <div className="row" style={{ marginTop: 4 }}>{r.txt_refs.slice(0, 6).map((t: any, i: number) =>
          <button key={i} className="btn small" onClick={() => onTxt([txtHl(t)])}>Fichier : ligne {t.line_no}{t.start ? `, pos. ${t.start}-${t.end}` : ""}</button>)}</div>}
        {!readOnly && r.status !== "CONFORME" && r.status !== "NON_APPLICABLE" && <div className="row" style={{ marginTop: 6 }}>
          {r.status === "ANOMALIE" && <>
            <button className="btn small danger" onClick={() => onDecision("confirmation", r.rule_id, `Confirmer l'écart ${r.rule_id}`)}>Confirmer l'écart</button>
            <button className="btn small ok" onClick={() => onDecision("faux_positif", r.rule_id, `Déclarer ${r.rule_id} faux positif`, true)}>Faux positif</button></>}
          <button className="btn small" onClick={() => onDecision("revue_complementaire", r.rule_id, `Revue complémentaire — ${r.rule_id}`)}>Revue complémentaire</button>
          <button className="btn small" onClick={() => onDecision("commentaire", r.rule_id, `Commenter ${r.rule_id}`, true)}>Commenter</button>
        </div>}
      </div>;
    })}

    <h4>Extraction du bordereau</h4>
    {f && <FieldBlock f={f} money={MONEY.has(f.field)} readOnly={readOnly} onCorrect={onCorrect} onFocusBox={onFocusBox} />}
    {z.extracted.subtotals?.length > 0 && <div style={{ marginTop: 6 }}>{z.extracted.subtotals.map((s: any) =>
      <FieldBlock key={s.field} f={s} money readOnly={readOnly} onCorrect={onCorrect} onFocusBox={onFocusBox} compact />)}</div>}
    {z.extracted.rows && <RowsTable z={z} onFocusBox={onFocusBox} onTxt={onTxt} readOnly={readOnly} onCorrect={onCorrect} />}
    {z.extracted.executants && (z.extracted.executants.length === 0 ? <p className="muted small">Aucun numéro d'exécutant lu dans le tableau des actes.</p> :
      <table className="data small"><thead><tr><th>N° d'exécutant</th><th>Lecture</th><th>Type</th><th /></tr></thead><tbody>
        {z.extracted.executants.map((e: any, i: number) => <tr key={i} className="clickable" onClick={() => e.box && onFocusBox(e.box)}>
          <td className="mono">{e.value}</td><td>{AG[e.agreement] || e.agreement}{e.reliable === false ? <div className="hint">{e.note || "lecture à vérifier"}</div> : e.note ? <div className="hint">{e.note}</div> : null}</td>
          <td>{e.etablissement ? "établissement (pas de signature exigée)" : "praticien"}</td>
          <td>{!readOnly && <button className="btn small" onClick={ev => { ev.stopPropagation(); onCorrect({ target: `tables.Z10.${e.row}.cells.executant`, label: `Exécutant (ligne ${e.row + 1})`, current: e.value }); }}>Corriger</button>}</td></tr>)}
      </tbody></table>)}
    {z.extracted.signatures && <>
      <div className="notice warn small" style={{ marginBottom: 6 }}>{z.extracted.avertissement}</div>
      <table className="data small"><thead><tr><th>Case</th><th>Présence</th><th>Exécutant(s)</th><th>Incertitude</th><th /></tr></thead><tbody>
        {z.extracted.signatures.map((s: any) => <tr key={s.target} className="clickable" onClick={() => onFocusBox(s.box)}>
          <td>{s.case ?? "directeur"}</td>
          <td><StatusPill s={s.status === "PRESENT" ? "CONFORME" : s.status === "VIDE" ? "NON_APPLICABLE" : "NON_VERIFIABLE"} short /> {s.status === "PRESENT" ? "élément présent" : s.status === "VIDE" ? "vide" : "indéterminée"}
            {s.original_status && <div className="hint">détecté : {s.original_status} — corrigé par {s.corrected_by}</div>}
            {s.nature && <div className="hint">{s.nature}</div>}</td>
          <td className="mono">{(s.executants_associes || []).join(", ") || (s.numbers || []).join(", ") || "—"}</td>
          <td className="hint nowrap">{s.incertitude}{s.ink_ratio !== undefined && s.ink_ratio !== null ? <div>encre {(s.ink_ratio * 100).toFixed(1).replace(".", ",")} %</div> : null}</td>
          <td>{!readOnly && <button className="btn small" title="Confirmer ou corriger la présence" onClick={ev => { ev.stopPropagation(); onCorrect({ target: s.target, label: `Signature ${s.case ? "case " + s.case : "du directeur"}`, current: s.status, options: ["PRESENT", "VIDE"] }); }}>✎</button>}</td></tr>)}
      </tbody></table></>}
    {!f && !z.extracted.rows && !z.extracted.executants && !z.extracted.signatures && <p className="muted small">Aucune donnée extraite pour cette zone.</p>}

    <h4>Facture TXT</h4>
    {z.txt.links.length === 0 && <p className="small muted">{z.txt.absence || "Aucune donnée du fichier n'est rattachée à cette zone."}</p>}
    {z.txt.links.length > 0 && <>
      <table className="data small"><thead><tr><th>Donnée du fichier</th><th>Valeur</th><th>Ligne / positions</th></tr></thead><tbody>
        {z.txt.links.slice(0, 40).map((l: any, i: number) => <tr key={i} className="clickable" onClick={() => l.line_no && onTxt([txtHl(l)])}>
          <td>{l.label}</td><td className="mono">{l.absent ? <span className="muted">absente du fichier</span> : l.cents !== undefined && l.cents !== null ? euro(l.cents) : fmtVal(l.raw ?? l.value)}{l.gh ? <span className="hint"> · GH {l.gh}</span> : null}</td>
          <td>{l.line_no ? `ligne ${l.line_no}, pos. ${l.start}-${l.end}` : "—"}</td></tr>)}
      </tbody></table>
      {z.txt.links.length > 1 && <button className="btn small" style={{ marginTop: 6 }} onClick={() => onTxt(z.txt.links.filter((l: any) => l.line_no).map(txtHl))}>Surligner toutes les positions</button>}
    </>}

    <h4>Assistance</h4>
    <dl className="kv">
      <dt>Ce qui a été comparé</dt><dd>{z.rule_results.length ? z.rule_results.map((r: any) => `${r.rule_id} : ${r.title}`).join(" ; ") : "—"}</dd>
      <dt>Non vérifiable</dt><dd>{notVerifiable.length ? notVerifiable.map((r: any) => `${r.rule_id} — ${r.uncertainty?.reason || r.explanation}`).join(" ; ") : "Rien : toutes les vérifications applicables ont pu être conduites."}</dd>
      <dt>Action recommandée</dt><dd>{worst ? worst.next_action : "Aucune action requise."}</dd>
    </dl>
    {!readOnly && z.needs_human_review && <button className="btn small" style={{ marginTop: 6 }}
      onClick={() => onDecision("revue_complementaire", undefined, `Revue complémentaire de la zone ${z.zone_id}`, true, z.zone_id)}>Demander une revue complémentaire de la zone</button>}

    <h4>Traçabilité</h4>
    <dl className="kv small">
      <dt>Bordereau</dt><dd className="mono">{z.traceability.jpg} · {String(z.traceability.jpg_sha256 || "").slice(0, 16)}…</dd>
      <dt>Facture</dt><dd className="mono">{z.traceability.txt} · {String(z.traceability.txt_sha256 || "").slice(0, 16)}…</dd>
      <dt>Versions</dt><dd>extracteur {z.traceability.extractor_version} · moteur {z.traceability.engine_version} · règles {z.traceability.ruleset_version}{z.traceability.cache ? ` · cache OCR : ${z.traceability.cache}` : ""}</dd>
      <dt>Dernière correction</dt><dd>{zCorr.length ? `${zCorr[zCorr.length - 1].target} : « ${zCorr[zCorr.length - 1].original} » → « ${zCorr[zCorr.length - 1].corrected} » (${zCorr[zCorr.length - 1].username}, ${fmtDate(zCorr[zCorr.length - 1].created_at)})` : "aucune"}</dd>
      <dt>Dernière décision</dt><dd>{zDecisions.length ? `${zDecisions[0].kind.replace("_", " ")}${zDecisions[0].rule_id ? " " + zDecisions[0].rule_id : ""} — ${zDecisions[0].display_name || ""}, ${fmtDate(zDecisions[0].created_at)}` : "aucune"}</dd>
    </dl>
    {zDecisions.length > 1 && <details style={{ marginTop: 6 }}><summary className="small">Historique de la zone ({zDecisions.length})</summary>
      <ul className="timeline">{zDecisions.map((d: any) => <li key={d.id}>{d.kind.replace("_", " ")}{d.rule_id ? ` — ${d.rule_id}` : ""}{d.value ? ` → ${d.value}` : ""} · {d.display_name}
        {d.comment && <div>« {d.comment} »</div>}<div className="hint">{fmtDate(d.created_at)}</div></li>)}</ul></details>}
  </div>;
}

function FieldBlock({ f, money, readOnly, onCorrect, onFocusBox, compact }: any) {
  return <div className="zrule">
    <div className="top"><b className="small">{f.business}</b>
      <span className="tag">{AG[f.agreement] || f.agreement}</span>
      {f.corrected_by && <span className="tag">{f.original !== undefined && f.original !== null && f.original !== f.value ? "corrigé" : "validé"} par {f.corrected_by}</span>}
      <span className="spacer" />
      {f.box && <button className="btn small" onClick={() => onFocusBox(f.box)}>Voir</button>}
      {!readOnly && <button className="btn small" onClick={() => onCorrect({ target: f.target, label: f.business, current: money && typeof f.value === "number" ? (f.value / 100).toFixed(2).replace(".", ",") : f.value })}>Corriger / valider</button>}
    </div>
    <div className="vs"><div><div className="k">Valeur brute OCR</div><div className="v">{fmtVal(f.raw)}</div></div>
      <div><div className="k">Valeur normalisée</div><div className="v">{fmtVal(f.value, money)}</div></div></div>
    {!compact && <>
      {f.original !== undefined && f.original !== null && <div className="small">Lecture d'origine conservée : <span className="mono">{fmtVal(f.original, money)}</span></div>}
      {f.candidates?.length > 1 && <div className="small">Valeurs candidates : {f.candidates.map((c: any) => `${fmtVal(c.value, money)} (${c.votes} lecture(s), ${c.engines.join(" + ")})`).join(" ; ")}</div>}
      <div className="hint">{f.method}{f.notes?.length ? " · " + f.notes.join(" ; ") : ""}</div>
      {f.readings?.length > 0 && <details style={{ marginTop: 4 }}><summary className="small">Lectures individuelles ({f.readings.length})</summary>
        <table className="data small"><thead><tr><th>Moteur</th><th>Prétraitement</th><th>Texte lu</th><th>Valeur</th><th>Confiance</th></tr></thead>
          <tbody>{f.readings.map((l: any, i: number) => <tr key={i}><td>{l.engine}</td><td>{l.prep}</td><td className="mono">{l.raw}</td>
            <td className="mono">{l.valid ? fmtVal(l.value, money) : <span className="muted">invalide</span>}{l.note ? <div className="hint">{l.note}</div> : null}</td><td>{l.conf ?? "—"}</td></tr>)}</tbody></table></details>}
    </>}
  </div>;
}

function RowsTable({ z, onFocusBox, onTxt, readOnly, onCorrect }: any) {
  const rows = z.extracted.rows;
  const isActs = z.zone_id === "Z10";
  const money = (c: any) => c && typeof c.value === "number" ? euro(c.value) : fmtVal(c?.value);
  return <>
    {rows.length === 0 ? <p className="muted small">Aucune ligne détectée dans cette zone{z.zone_id === "Z7" ? " (zone sans prestation LPP pour ce dossier)" : ""}.</p> :
      <table className="data small" data-testid="zone-rows"><thead><tr><th>#</th>{isActs && <th>Exécutant</th>}<th>Code</th>{isActs && <th>Date</th>}<th>GHS</th><th>Montant</th><th>Fichier TXT</th><th>Résultat</th></tr></thead>
        <tbody>{rows.map((r: any) => <tr key={`${r.table}-${r.row}`} className="clickable" onClick={() => { onFocusBox(r.box); if (r.txt.length) onTxt(r.txt.map((t: any) => ({ line_no: t.line_no, start: t.start, end: t.end, label: t.code }))); }}>
          <td>{r.row + 1}</td>
          {isActs && <td className="mono">{fmtVal(r.executant?.value)}</td>}
          <td className="mono">{fmtVal(r.code?.value)}{r.code && !["concordant", "majoritaire", "corrigé", "vide"].includes(r.code.agreement) ? <div className="hint">{AG[r.code.agreement] || r.code.agreement}</div> : null}
            {!readOnly && r.code && r.code.agreement !== "vide" && <button className="btn small" style={{ marginLeft: 4, padding: "0 5px" }} title="Corriger le code"
              onClick={ev => { ev.stopPropagation(); onCorrect({ target: `tables.${z.zone_id}.${r.row}.cells.${isActs ? "code" : "prestation"}`, label: `${z.zone_id} ligne ${r.row + 1} — code`, current: r.code.value }); }}>✎</button>}</td>
          {isActs && <td className="mono">{fmtVal(r.date?.value)}</td>}
          <td className="mono">{fmtVal(r.ghs?.value)}</td>
          <td className="mono">{money(r.montant)}</td>
          <td className="small">{r.txt.length ? r.txt.map((t: any) => `${t.code} (l. ${t.line_no})`).join(", ") : "—"}</td>
          <td className="small">{r.resultat}</td></tr>)}</tbody></table>}
    {z.extracted.txt_only?.length > 0 && <div className="notice bad small" style={{ marginTop: 8 }}>
      <b>Lignes du fichier absentes du bordereau</b> — elles auraient dû figurer en {z.extracted.txt_only[0].attendu_en} (aucune position n'est inventée sur l'image) :
      <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>{z.extracted.txt_only.map((t: any, i: number) => <li key={i}>
        <button className="btn small" onClick={() => { onTxt([{ line_no: t.line_no, start: t.start, end: t.end, label: t.label }]); if (z.bbox) onFocusBox(z.bbox); }}>
          {t.label} — ligne {t.line_no}{t.start ? `, pos. ${t.start}-${t.end}` : ""} ({t.rule_id})</button></li>)}</ul></div>}
  </>;
}
