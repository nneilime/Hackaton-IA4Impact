import { useEffect, useMemo, useRef, useState } from "react";
import { api, CASE_STATUSES, euro, fmtDate, RuleResult, STATUS_LABEL, User } from "../api";
import ImageViewer, { VBox, ZoneOverlay } from "../components/ImageViewer";
import TxtViewer, { Hl } from "../components/TxtViewer";
import ZoneInspector, { Zone } from "../components/ZoneInspector";
import CaseSimple from "./CaseSimple";
import { CaseState, ErrorBox, Loading, Modal, StatusPill, go, useActivity, useFetch, useToast } from "../components/ui";

const FIELD_RULES: Record<string, string> = { R01: "Z1", R02: "Z2", R03: "Z3", R04: "Z4", R05: "Z5", R12: "Z8", R17: "Z12", R22: "Z15" };
const KIND_LABEL: Record<string, string> = {
  examen: "Examen", confirmation: "Écart confirmé", faux_positif: "Faux positif", revue_complementaire: "Revue complémentaire demandée",
  commentaire: "Commentaire", statut: "Statut", escalade: "Transmis au superviseur", priorite: "Priorité", decision_motivee: "Décision motivée",
  affectation: "Affectation",
};

const MODE_KEY = "sentinel.mode";
function readMode(): "simple" | "expert" {
  try { return localStorage.getItem(MODE_KEY) === "expert" ? "expert" : "simple"; } catch { return "simple"; }
}

/** Écran de contrôle : mode simple par défaut (dossier → écart → preuve → décision) ; mode expert à la demande. */
export default function CaseDesk({ id, user, params }: { id: string; user: User; params: URLSearchParams }) {
  const [mode, setMode] = useState<"simple" | "expert">(params.get("zone") || params.get("mode") === "expert" ? "expert" : readMode());
  const set = (m: "simple" | "expert") => { setMode(m); try { localStorage.setItem(MODE_KEY, m); } catch { /* */ } };
  if (mode === "expert") return <CaseExpert id={id} user={user} params={params} onSimple={() => set("simple")} />;
  return <SimpleLoader id={id} user={user} params={params} onExpert={() => set("expert")} />;
}

function SimpleLoader({ id, user, params, onExpert }: { id: string; user: User; params: URLSearchParams; onExpert: () => void }) {
  const { data, error, reload } = useFetch<any>(`/api/cases/${encodeURIComponent(id)}`);
  useActivity(id);
  if (error) return <div className="content"><ErrorBox e={error} /></div>;
  if (!data) return <Loading />;
  if (!data.analysis?.results) return <div className="content"><div className="notice bad">{data.analysis?.error || "Analyse indisponible pour ce dossier."}</div></div>;
  return <CaseSimple id={id} user={user} data={data} reload={reload} onExpert={onExpert} initialRule={params.get("regle")} />;
}

function CaseExpert({ id, user, params, onSimple }: { id: string; user: User; params: URLSearchParams; onSimple: () => void }) {
  const { data, error, reload } = useFetch<any>(`/api/cases/${encodeURIComponent(id)}`);
  const users = useFetch<any[]>(user.role === "agent" ? null : "/api/users");
  const [sel, setSel] = useState<string | null>(params.get("regle"));
  const [tab, setTab] = useState<"zones" | "checks" | "reads" | "obs" | "hist">(params.get("regle") ? "checks" : "zones");
  const [txtTab, setTxtTab] = useState<"raw" | "struct">("raw");
  const [showZones, setShowZones] = useState(false);
  const [showFrames, setShowFrames] = useState(true);
  const [zoneSel, setZoneSel] = useState<string | null>(params.get("zone"));
  const [focusRect, setFocusRect] = useState<{ box: number[]; n: number } | null>(null);
  const [txtHl, setTxtHl] = useState<Hl[] | null>(null);
  const [simOpen, setSimOpen] = useState(false);
  const focusN = useRef(0);
  useActivity(id);
  const [ocrSearch, setOcrSearch] = useState("");
  const [modal, setModal] = useState<null | { kind: string; rule?: string; title: string; needComment?: boolean; value?: string }>(null);
  const [corr, setCorr] = useState<null | { target: string; label: string; current: any; options?: string[] }>(null);
  const toast = useToast();

  const a = data?.analysis;
  const results: RuleResult[] = a?.results || [];
  const selected = results.find(r => r.rule_id === sel) || null;
  const readOnly = user.role === "auditeur";

  const lastDecisionByRule = useMemo(() => {
    const m: Record<string, any> = {};
    (data?.decisions || []).slice().reverse().forEach((d: any) => { if (d.rule_id) m[d.rule_id] = d; });
    return m;
  }, [data]);

  // ---- boîtes de l'image
  const boxes: VBox[] = useMemo(() => {
    if (!a?.extraction) return [];
    const ext = a.extraction; const out: VBox[] = [];
    const q = ocrSearch.trim().toLowerCase();
    Object.values(ext.fields || {}).forEach((f: any) => out.push({ id: `f-${f.field}`, box: f.text_box || f.box, label: f.business,
      title: `${f.zone_label} — lu : ${f.raw ?? "—"} (${f.agreement})`, cls: q && String(f.raw || "").toLowerCase().includes(q) ? "search" : "" }));
    ["Z6", "Z7", "Z10"].forEach(z => (ext.tables?.[z] || []).forEach((r: any) => {
      const txt = Object.values(r.cells).map((c: any) => c.raw).join(" ");
      out.push({ id: `r-${z}-${r.row}`, box: r.box, label: `${z} ligne ${r.row + 1}`, title: txt, cls: q && txt.toLowerCase().includes(q) ? "search" : "" });
    }));
    (ext.signatures?.Z11 || []).forEach((s: any) => s.status !== "VIDE" && out.push({ id: `s-Z11-${s.case}`, box: s.box, label: `Signature case ${s.case}`, title: `${s.status} ${s.nature || ""}` }));
    (ext.signatures?.Z14 || []).forEach((s: any, i: number) => out.push({ id: `s-Z14-${i}`, box: s.box, label: "Zone 14", title: `${s.status}` }));
    if (selected) selected.img_refs.forEach((r, i) => r.box && out.push({ id: `ref-${i}`, box: r.box, label: r.label, cls: selected.status }));
    return out;
  }, [a, selected, ocrSearch]);

  const zones: Zone[] = a?.zones || [];
  const zoneOverlays: ZoneOverlay[] = zones.map(z => ({ id: z.zone_id, label: z.label, status: z.status, regions: z.regions, flags: z.flags }));
  const curZone = zones.find(z => z.zone_id === zoneSel) || null;
  const inZones = tab === "zones";
  const visibleBoxes = inZones ? boxes.filter(b => b.cls === "search" || (showZones && !b.id.startsWith("ref-")))
    : showZones ? boxes : boxes.filter(b => b.id.startsWith("ref-") || b.cls === "search");
  const focusId = !inZones && selected && selected.img_refs.some(r => r.box) ? `ref-${selected.img_refs.findIndex(r => r.box)}` : null;
  const frame = (box: number[] | null) => { if (box) { focusN.current += 1; setFocusRect({ box, n: focusN.current }); } };

  // TXT : positions de la zone sélectionnée (ou de l'élément cliqué), sinon celles du contrôle sélectionné
  const zoneHl: Hl[] = curZone ? [
    ...curZone.txt.links.filter((l: any) => l.line_no && !l.absent).map((l: any) => ({ line_no: l.line_no, start: l.start, end: l.end, label: l.label })),
    ...curZone.rule_results.flatMap((r: any) => (r.txt_refs || []).filter((t: any) => t.line_no).map((t: any) => ({ line_no: t.line_no, start: t.start, end: t.end, label: t.label }))),
  ] : [];
  const ruleHl: Hl[] = selected ? selected.txt_refs.filter(r => r.line_no).map(r => ({ line_no: r.line_no!, start: r.start, end: r.end, label: r.label })) : [];
  const highlights: Hl[] = txtHl ?? (inZones ? zoneHl : ruleHl);
  const focusLine = highlights[0]?.line_no ?? null;

  const selectZone = (zid: string | null) => {
    setZoneSel(zid); setTxtHl(null); setTab("zones");
    const z = zones.find(x => x.zone_id === zid);
    if (z?.bbox) frame(z.bbox);
    const h = window.location.hash.split("?")[0]; const q = new URLSearchParams(window.location.hash.split("?")[1] || "");
    if (zid) q.set("zone", zid); else q.delete("zone"); q.delete("regle");
    window.history.replaceState(null, "", `${h}${q.toString() ? "?" + q.toString() : ""}`);
  };
  // sélection initiale (lien direct ?zone=Z8) : cadrage dès que l'image est prête
  useEffect(() => { if (zoneSel && curZone?.bbox) setTimeout(() => frame(curZone.bbox), 60); }, [a?.analyzed_at]); // eslint-disable-line
  // raccourcis : [ et ] (zones), Échap (toutes les zones) — ignorés pendant une saisie
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable) || document.querySelector(".modal")) return;
      if (!zones.length) return;
      const i = zones.findIndex(z => z.zone_id === zoneSel);
      if (e.key === "]") selectZone(zones[(i + 1 + zones.length) % zones.length].zone_id);
      else if (e.key === "[") selectZone(zones[(i - 1 + zones.length) % zones.length].zone_id);
      else if (e.key === "Escape" && zoneSel) selectZone(null);
    };
    window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k);
  });

  if (error) return <div className="content"><ErrorBox e={error} /></div>;
  if (!data) return <Loading />;
  if (!a?.results) return <div className="content"><div className="notice bad">{a?.error || "Analyse indisponible pour ce dossier."}</div></div>;
  const c = data.case;
  const ext = a.extraction;

  const post = async (url: string, body: any, msg: string | ((r: any) => string)) => {
    try { const r = await api.post<any>(url, body); toast(typeof msg === "function" ? msg(r) : msg); reload(); return r; }
    catch (e: any) { toast(`Échec : ${e.message}`); throw e; }
  };
  const effectMsg = (r: any) => {
    const zc = Object.entries(r?.effect?.zones || {}).map(([k, v]: any) => `${k} ${STATUS_LABEL[v[0] as keyof typeof STATUS_LABEL]} → ${STATUS_LABEL[v[1] as keyof typeof STATUS_LABEL]}`);
    return `${r?.kind === "validation" ? "Lecture validée" : "Lecture corrigée"} — contrôles recalculés${zc.length ? " · " + zc.join(", ") : " · aucune zone modifiée"}`;
  };
  const decide = (kind: string, rule?: string, value?: string, comment?: string) =>
    post(`/api/cases/${id}/decisions`, { kind, rule_id: rule, value, comment }, `${KIND_LABEL[kind] || kind} enregistré(e)`);
  void euro;

  const cats = [...new Set(results.map(r => r.category))];
  const counts = results.reduce((m: any, r) => (m[r.status] = (m[r.status] || 0) + 1, m), {});

  return <div className="desk-wrap">
    <div className="case-bar">
      <button className="btn small" onClick={() => go("/dossiers")}>← Dossiers</button>
      <button className="btn small primary" onClick={onSimple} title="Revenir au parcours simple : écart, preuve, décision">Mode simple</button>
      <h1 className="mono">{c.id}</h1>
      <span>{c.establishment} · FINESS {c.finess} · facture <span className="mono">{c.invoice_no}</span> · {euro(c.billed_cents)}</span>
      <CaseState state={c.state} />
      {a.source === "import" && <span className="tag" title={a.label || ""}>Dossier importé{a.label ? ` — ${a.label}` : ""}</span>}
      {a.pairing.status !== "confirmé" && <span className="pill NON_VERIFIABLE" title={a.pairing.methode}>Appariement {a.pairing.status}</span>}
      <span className="spacer" />
      <span className="hint">{counts.ANOMALIE || 0} anomalie(s) · {counts.NON_VERIFIABLE || 0} non vérifiable(s) · {counts.CONFORME || 0} conforme(s)</span>
      <select className="input" value={c.status} disabled={readOnly} aria-label="Statut du dossier"
        onChange={e => decide("statut", undefined, e.target.value)}>
        {CASE_STATUSES.map(s => <option key={s} disabled={s === "Clôturé" && user.role === "agent"}>{s}</option>)}
      </select>
      {user.role === "agent" && !c.assigned_to && <button className="btn small" onClick={() => post(`/api/cases/${id}/assign`, { user_id: user.id }, "Dossier affecté")}>Prendre le dossier</button>}
      {(user.role === "superviseur" || user.role === "admin") && users.data &&
        <select className="input" value={c.assigned_to || ""} aria-label="Agent assigné"
          onChange={e => post(`/api/cases/${id}/assign`, { user_id: e.target.value ? Number(e.target.value) : null }, "Affectation enregistrée")}>
          <option value="">Non affecté</option>{users.data.filter(u => u.role === "agent").map(u => <option key={u.id} value={u.id}>{u.display_name}</option>)}
        </select>}
      {!readOnly && <button className="btn small" onClick={() => setModal({ kind: "escalade", title: "Transmettre au superviseur", needComment: true })}>Transmettre</button>}
      {(user.role === "superviseur" || user.role === "admin") &&
        <button className="btn small" onClick={() => decide("priorite", undefined, c.priority_override === "haute" ? "normale" : "haute", "Changement de priorité")}>
          {c.priority_override === "haute" ? "Priorité normale" : "Priorité haute"}</button>}
      {!readOnly && a.source !== "import" && <button className="btn small" onClick={() => setSimOpen(true)} title="Copie du dossier avec une valeur du TXT modifiée (le fichier original n'est jamais modifié)">Simuler une modification</button>}
      {!readOnly && <button className="btn small" disabled={!!data.job} onClick={() => post(`/api/cases/${id}/reanalyze`, {}, "Réanalyse lancée")}>Réanalyser</button>}
      <a className="btn small" href={`/api/cases/${id}/report.pdf`}>Rapport PDF</a>
      <a className="btn small" href={`/api/cases/${id}/report.json`}>JSON</a>
    </div>
    {data.job && <div className="notice warn" style={{ margin: 0, borderRadius: 0 }}>Analyse {data.job.status === "en_attente" ? "en attente" : "en cours"} pour ce dossier{data.job.message ? ` — ${data.job.message}` : ""}. <button className="btn small" onClick={reload}>Actualiser</button></div>}
    {ext.cache?.message && <div className="notice warn" style={{ margin: 0, borderRadius: 0 }}>{ext.cache.message}</div>}
    {(ext.corrections_inapplicables || []).length > 0 && <div className="notice bad" style={{ margin: 0, borderRadius: 0 }}>Correction(s) inapplicable(s) après recalcul de l'extraction : {ext.corrections_inapplicables.map((c: any) => `${c.target} (${c.raison})`).join(" ; ")}</div>}

    <div className="desk">
      {/* ------------------------------------------------ bordereau */}
      <section aria-label="Bordereau JPG">
        <div className="pane-head">
          <h3>Bordereau</h3><span className="hint">{a.jpg} · mise en page {ext.layout?.family}</span>
          <span className="spacer" />
          <label className="row small" title="Encadrements colorés des 15 zones selon leur conformité"><input type="checkbox" checked={showFrames} onChange={e => setShowFrames(e.target.checked)} /> 15 zones</label>
          <label className="row small" title="Cadres des valeurs lues par l'OCR"><input type="checkbox" checked={showZones} onChange={e => setShowZones(e.target.checked)} /> Lectures OCR</label>
          <input className="input" style={{ width: 130, padding: "3px 7px" }} placeholder="Chercher (OCR)" value={ocrSearch} onChange={e => setOcrSearch(e.target.value)} aria-label="Rechercher dans le texte OCR" />
        </div>
        <ImageViewer src={`/api/cases/${id}/image`} size={ext.size} boxes={visibleBoxes} focusId={focusId}
          onBoxClick={bid => { if (bid.startsWith("f-")) setTab("reads"); }}
          zones={zoneOverlays} showZones={showFrames} onToggleZones={setShowFrames} legend
          selectedZone={inZones ? zoneSel : null} onZoneClick={zid => selectZone(zid === zoneSel && inZones ? zid : zid)}
          focusRect={focusRect} rotate180={ext.layout?.rotation === 180} />
      </section>

      {/* ------------------------------------------------ contrôles */}
      <section aria-label="Comparaison">
        <div className="pane-head">
          <div className="tabs" role="tablist">
            {([["zones", "15 zones"], ["checks", "Contrôles (22)"], ["reads", "Lectures OCR"], ["obs", `Observations (${a.observations.length})`], ["hist", `Historique (${data.decisions.length})`]] as const).map(([k, l]) =>
              <button key={k} role="tab" aria-selected={tab === k} className={`tab ${tab === k ? "on" : ""}`} onClick={() => { setTab(k as any); setTxtHl(null); }}>{l}</button>)}
          </div>
        </div>
        {tab === "zones" && (data.triage || []).length > 0 && !zoneSel && <details className="panel-pad" style={{ borderBottom: "1px solid var(--line-2)", paddingTop: 8, paddingBottom: 8 }}>
          <summary className="small"><b>Pistes de vérification</b> — {data.triage.length} regroupement(s) d'alertes pouvant partager une même cause</summary>
          {data.triage.map((g: any) => <div key={g.id} className="zrule" style={{ marginTop: 6 }}>
            <div className="top"><b className="small">{g.title}</b>{g.zones.map((zz: string) => <button key={zz} className="zchip" onClick={() => selectZone(zz)}>{zz}</button>)}</div>
            <p className="small" style={{ margin: "4px 0" }}>{g.hypothesis}</p>
            <div className="small"><b>À vérifier d'abord :</b> {g.first_check}</div>
            <div className="hint">Règles : {g.rules.join(", ")} · {g.avertissement}</div></div>)}
        </details>}
        {tab === "zones" && <ZoneInspector zones={zones} selected={zoneSel} onSelect={selectZone} onFocusBox={frame}
          onTxt={h => { setTxtHl(h); setTxtTab("raw"); }} readOnly={readOnly} decisions={data.decisions} corrections={a.corrections || []}
          effective={data.finance?.decisions_effectives || {}}
          onDecision={(kind, rule, title, needComment, value) => setModal({ kind, rule, title: title || kind, needComment, value })}
          onCorrect={setCorr} onOpenRule={rid => { setSel(rid); setTab("checks"); setTxtHl(null); }} />}
        <div className="pane-body" style={{ display: tab === "zones" ? "none" : undefined }}>
          {tab === "checks" && cats.map(cat => <div key={cat}>
            <div className="cat">{cat} — {results.find(r => r.category === cat)?.category_label}</div>
            {results.filter(r => r.category === cat).map(r => {
              const ld = lastDecisionByRule[r.rule_id];
              return <div key={r.rule_id} className={`check ${sel === r.rule_id ? "sel" : ""}`} onClick={() => setSel(sel === r.rule_id ? null : r.rule_id)}
                role="button" tabIndex={0} onKeyDown={e => e.key === "Enter" && setSel(r.rule_id)}>
                <span className="rid">{r.rule_id}</span>
                <span className="t">{r.title} <span className="hint">· {zones.filter(z => z.related_rules.some(x => x.rule_id === r.rule_id)).map(z => z.zone_id).join(" ")}</span></span>
                <StatusPill s={r.status} />
                {(r.status === "ANOMALIE" || r.status === "NON_VERIFIABLE" || ld) && <div className="vals">
                  {r.jpg_value && <span>Bordereau <b>{r.jpg_value}</b></span>}
                  {r.txt_value && <span>Fichier <b>{r.txt_value}</b></span>}
                  {ld && <span className="tag">{KIND_LABEL[ld.kind]} — {ld.display_name}</span>}
                </div>}
              </div>;
            })}
          </div>)}

          {tab === "reads" && <Readings ext={ext} readOnly={readOnly} onCorrect={setCorr} corrections={a.corrections} onCancel={(cid: number) =>
            api.del(`/api/cases/${id}/corrections/${cid}`).then(() => { toast("Correction annulée"); reload(); })} />}

          {tab === "obs" && <div className="panel-pad">
            <p className="hint">Observations techniques hors cahier des charges : elles ne sont pas des non-conformités.</p>
            {a.observations.length === 0 && <p className="muted">Aucune observation.</p>}
            <ul className="timeline">{a.observations.map((o: any, i: number) => <li key={i}>
              <span className="tag">{o.source}</span> <b>{o.code}</b><div>{o.message}</div>
              {o.line_nos?.length > 0 && <div className="hint">Lignes : {o.line_nos.slice(0, 20).join(", ")}</div>}</li>)}</ul>
            <h3 style={{ marginTop: 12 }}>Rapprochement des documents</h3>
            <p className="small">{a.pairing.methode}</p>
            <dl className="kv">{Object.entries(a.pairing.details).map(([k, v]) => <><dt key={k}>{k === "Z2" ? "FINESS (zone 2)" : k === "Z4" ? "N° facture (zone 4)" : "N° assuré (zone 5)"}</dt><dd>{v === null ? "non lu" : v ? "concorde" : "diffère"}</dd></>)}</dl>
          </div>}

          {tab === "hist" && <div className="panel-pad">
            {data.decisions.length === 0 && <p className="muted">Aucune action enregistrée sur ce dossier.</p>}
            <ul className="timeline">{data.decisions.map((d: any) => <li key={d.id}>
              <b>{KIND_LABEL[d.kind] || d.kind}</b>{d.rule_id ? ` — ${d.rule_id}` : ""}{d.value ? ` → ${d.value}` : ""} · {d.display_name || "—"}
              {d.comment && <div>« {d.comment} »</div>}<div className="hint">{fmtDate(d.created_at)}</div></li>)}</ul>
            {a.corrections?.length > 0 && <><h3>Corrections de lecture</h3><ul className="timeline">{a.corrections.map((x: any) => <li key={x.id}>
              {x.target} : « {x.original} » → « {x.corrected} » · {x.username}<div className="hint">{fmtDate(x.created_at)}</div></li>)}</ul></>}
          </div>}
        </div>

        {tab === "checks" && selected && <div className="detail" style={{ maxHeight: "48%", overflow: "auto" }}>
          <div className="row"><span className="tag rule">{selected.rule_id}</span><b>{selected.title}</b><StatusPill s={selected.status} /></div>
          <p className="expl" style={{ marginTop: 6 }}>{selected.explanation}</p>
          {(selected.jpg_value || selected.txt_value) && <div className="vs">
            <div><div className="k">Bordereau (JPG)</div><div className="v">{selected.jpg_value ?? "—"}</div></div>
            <div><div className="k">Fichier (TXT)</div><div className="v">{selected.txt_value ?? "—"}</div></div>
          </div>}
          <dl className="kv">
            {selected.gap?.amount_cents ? <><dt>Écart mesuré</dt><dd>{euro(selected.gap.amount_cents)} ({selected.gap.label})</dd></> : null}
            {selected.uncertainty && <><dt>Incertitude</dt><dd>{selected.uncertainty.level} — {selected.uncertainty.reason}</dd></>}
            <dt>Cahier des charges</dt><dd>« {selected.spec} »</dd>
            {selected.convention && <><dt>Convention retenue</dt><dd>{selected.convention}</dd></>}
            <dt>Zones / champs</dt><dd>{selected.zones.join(", ") || "—"}{selected.txt_fields.length ? " · " + selected.txt_fields.join(", ") : ""}</dd>
            {selected.txt_refs.length > 0 && <><dt>Fichier</dt><dd>{selected.txt_refs.slice(0, 6).map((r, i) => <div key={i}>{r.label} — ligne {r.line_no}{r.start ? `, pos. ${r.start}-${r.end}` : ""}</div>)}</dd></>}
            <dt>Prochaine étape</dt><dd>{selected.next_action}</dd>
            <dt>Traitement</dt><dd className="hint">{fmtDate(selected.processed_at)} · moteur {selected.engine_version} · règles {selected.ruleset_version}</dd>
          </dl>
          {selected.details?.lectures?.length > 0 && <details style={{ marginTop: 6 }}><summary className="small">Lectures OCR individuelles ({selected.details.lectures.length})</summary>
            <table className="data small"><thead><tr><th>Moteur</th><th>Prétraitement</th><th>Texte lu</th><th>Valeur</th><th>Confiance</th></tr></thead>
              <tbody>{selected.details.lectures.map((l: any, i: number) => <tr key={i}><td>{l.moteur}</td><td>{l.pretraitement}</td><td className="mono">{l.texte}</td>
                <td className="mono">{l.valide ? String(l.valeur) : <span className="muted">invalide</span>}{l.note ? <div className="hint">{l.note}</div> : null}</td><td>{l.confiance ?? "—"}</td></tr>)}</tbody></table></details>}
          {!readOnly && <div className="row" style={{ marginTop: 10 }}>
            <button className="btn small" onClick={() => decide("examen", selected.rule_id, undefined, undefined)}>Marquer examiné</button>
            {selected.status === "ANOMALIE" && <>
              <button className="btn small danger" onClick={() => setModal({ kind: "confirmation", rule: selected.rule_id, title: `Confirmer l'écart ${selected.rule_id}` })}>Confirmer l'écart</button>
              <button className="btn small ok" onClick={() => setModal({ kind: "faux_positif", rule: selected.rule_id, title: `Déclarer ${selected.rule_id} faux positif`, needComment: true })}>Faux positif</button>
            </>}
            <button className="btn small" onClick={() => setModal({ kind: "revue_complementaire", rule: selected.rule_id, title: "Demander une revue complémentaire" })}>Revue complémentaire</button>
            <button className="btn small" onClick={() => setModal({ kind: "commentaire", rule: selected.rule_id, title: "Ajouter un commentaire", needComment: true })}>Commenter</button>
            {FIELD_RULES[selected.rule_id] && ext.fields[FIELD_RULES[selected.rule_id]] &&
              <button className="btn small" onClick={() => { const f = ext.fields[FIELD_RULES[selected.rule_id]]; setCorr({ target: `fields.${f.field}`, label: f.business, current: f.value }); }}>Corriger la lecture</button>}
            {selected.rule_id === "R21" && <button className="btn small" onClick={() => setCorr({ target: "signatures.Z14.0", label: "Signature du directeur (zone 14)", current: ext.signatures.Z14[0]?.status, options: ["PRESENT", "VIDE"] })}>Corriger la détection</button>}
          </div>}
        </div>}
        <Assistant id={id} />
      </section>

      {/* ------------------------------------------------ fichier TXT */}
      <section aria-label="Fichier TXT">
        <div className="pane-head">
          <h3>Facture structurée</h3><span className="hint">{a.txt_file}</span><span className="spacer" />
          <div className="tabs"><button className={`tab ${txtTab === "raw" ? "on" : ""}`} onClick={() => setTxtTab("raw")}>Enregistrements</button>
            <button className={`tab ${txtTab === "struct" ? "on" : ""}`} onClick={() => setTxtTab("struct")}>Données extraites</button></div>
        </div>
        {txtTab === "raw" ? <TxtViewer records={a.txt.records} highlights={highlights} focusLine={focusLine}
          badLines={a.txt.observations.filter((o: any) => o.severity === "warning").flatMap((o: any) => o.line_nos)} />
          : <Structured t={a.txt} />}
      </section>
    </div>

    {modal && <DecisionModal m={modal} onClose={() => setModal(null)} onSubmit={(comment) => { decide(modal.kind, modal.rule, modal.value, comment).then(() => setModal(null)).catch(() => undefined); }} />}
    {corr && <CorrectionModal c={corr} onClose={() => setCorr(null)} onSubmit={(v, comment) =>
      post(`/api/cases/${id}/corrections`, { target: corr.target, corrected: v, comment }, effectMsg).then(() => setCorr(null)).catch(() => undefined)} />}
    {simOpen && <SimulationModal a={a} id={id} onClose={() => setSimOpen(false)} />}
  </div>;
}

function SimulationModal({ a, id, onClose }: { a: any; id: string; onClose: () => void }) {
  const t = a.txt;
  const opts: { key: string; label: string; f: any }[] = [];
  const add = (key: string, label: string, f: any) => f && f.line_no && opts.push({ key, label, f });
  add("lot", "NumeroLot (type 1, pos. 20-22)", t.numero_lot);
  add("assure", "NumeroAssure (type 2, pos. 12-24)", t.numero_assure);
  add("facture", "NumeroFacture (type 2, pos. 30-38)", t.numero_facture);
  add("tp", "TotalPrestations (type 5, pos. 42-49)", t.total_prestations);
  add("th", "TotalHonoraires (type 5, pos. 58-65)", t.total_honoraires);
  (t.acts3 || []).forEach((x: any) => opts.push({ key: `a3-${x.line_no}`, label: `Acte ${x.acte} (type 3, ligne ${x.line_no}, pos. 56-60)`, f: { line_no: x.line_no, start: 56, end: 60, raw: (a.txt.records.find((r: any) => r.line_no === x.line_no)?.raw || "").slice(55, 60) } }));
  (t.acts3 || []).forEach((x: any) => opts.push({ key: `g3-${x.line_no}`, label: `NumeroGH de ${x.acte} (type 3, ligne ${x.line_no}, pos. 110-113)`, f: { line_no: x.line_no, start: 110, end: 113, raw: x.gh } }));
  const [k, setK] = useState(opts[0]?.key);
  const cur = opts.find(o => o.key === k)?.f;
  const width = cur ? cur.end - cur.start + 1 : 0;
  const [v, setV] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const toast = useToast();
  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await api.post<any>(`/api/cases/${id}/simulate`, { edits: [{ line_no: cur.line_no, start: cur.start, end: cur.end, value: v }] });
      toast("Simulation créée : analyse par le moteur réel en cours"); onClose(); go(`/import?suivre=${r.id}`);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  return <Modal title="Simuler une modification du fichier TXT" onClose={onClose}>
    <p className="small muted">Une <b>copie</b> du dossier est créée avec la valeur modifiée ; le fichier original n'est jamais modifié. La copie est analysée par le moteur réel, marquée « Simulation » et exclue des statistiques.</p>
    <label className="field">Donnée du fichier<select className="input" value={k} onChange={e => { setK(e.target.value); setV(""); }}>{opts.map(o => <option key={o.key} value={o.key}>{o.label}</option>)}</select></label>
    {cur && <dl className="kv" style={{ marginTop: 8 }}><dt>Valeur actuelle</dt><dd className="mono">«{(cur.raw ?? "").toString()}» ({width} caractère(s), ligne {cur.line_no})</dd></dl>}
    <label className="field" style={{ marginTop: 8 }}>Nouvelle valeur — exactement {width} caractère(s) (positions fixes)
      <input className="input mono" value={v} maxLength={width} onChange={e => setV(e.target.value)} placeholder={"0".repeat(width)} autoFocus /></label>
    <p className="hint">Montants : centimes sans séparateur, complétés à gauche par des zéros (ex. 00082897 = 828,97 €).</p>
    {err && <div className="notice bad">{err}</div>}
    <div className="row" style={{ marginTop: 12, justifyContent: "flex-end" }}>
      <button className="btn" onClick={onClose}>Annuler</button>
      <button className="btn primary" disabled={busy || v.length !== width} onClick={submit}>{busy ? "Création…" : "Créer la simulation"}</button>
    </div>
  </Modal>;
}

export function DecisionModal({ m, onClose, onSubmit }: { m: any; onClose: () => void; onSubmit: (c: string) => void }) {
  const [c, setC] = useState("");
  return <Modal title={m.title} onClose={onClose}>
    <p className="small muted">{m.kind === "confirmation" ? "Vous confirmez que l'écart documentaire est réel après comparaison des deux sources. Cela ne qualifie pas une fraude." :
      m.kind === "faux_positif" ? "Indiquez pourquoi l'écart signalé n'en est pas un (ex. erreur de lecture OCR)." : "Votre action est horodatée et conservée dans l'historique du dossier."}</p>
    <label className="field">Commentaire {m.needComment ? "(obligatoire)" : "(facultatif)"}<textarea className="input" value={c} onChange={e => setC(e.target.value)} autoFocus /></label>
    <div className="row" style={{ marginTop: 12, justifyContent: "flex-end" }}>
      <button className="btn" onClick={onClose}>Annuler</button>
      <button className="btn primary" disabled={m.needComment && !c.trim()} onClick={() => onSubmit(c)}>Enregistrer</button>
    </div>
  </Modal>;
}

export function CorrectionModal({ c, onClose, onSubmit }: { c: any; onClose: () => void; onSubmit: (v: string, comment: string) => void }) {
  const [v, setV] = useState(c.options ? c.options[0] : (c.current ?? "") + "");
  const [com, setCom] = useState("");
  return <Modal title={`Corriger : ${c.label}`} onClose={onClose}>
    <p className="small muted">La lecture d'origine est conservée. Votre correction est attribuée à votre compte, puis les 22 contrôles et les 15 zones sont recalculés.
      Saisir la même valeur que la lecture actuelle la <b>valide</b> (l'incertitude est levée). Pour un montant, saisissez la valeur telle qu'imprimée (ex. 818,97).</p>
    <dl className="kv"><dt>Lecture actuelle</dt><dd className="mono">{String(c.current ?? "—")}</dd></dl>
    {c.options ? <label className="field">Valeur constatée<select className="input" value={v} onChange={e => setV(e.target.value)}>
      {c.options.map((o: string) => <option key={o} value={o}>{o === "PRESENT" ? "Signature présente" : o === "VIDE" ? "Zone vide" : o}</option>)}</select></label>
      : <label className="field">Valeur lue sur le bordereau<input className="input" value={v} onChange={e => setV(e.target.value)} autoFocus /></label>}
    <label className="field" style={{ marginTop: 8 }}>Commentaire<textarea className="input" value={com} onChange={e => setCom(e.target.value)} /></label>
    <div className="row" style={{ marginTop: 12, justifyContent: "flex-end" }}>
      <button className="btn" onClick={onClose}>Annuler</button>
      <button className="btn primary" disabled={!String(v).trim()} onClick={() => onSubmit(String(v), com)}>Enregistrer la correction</button>
    </div>
  </Modal>;
}

const AG: Record<string, string> = { concordant: "lectures concordantes", majoritaire: "majorité des lectures", lecture_unique: "une seule lecture valide",
  divergent: "lectures divergentes", illisible: "illisible", vide: "zone vide", "corrigé": "corrigé par un agent" };

function Readings({ ext, readOnly, onCorrect, corrections, onCancel }: any) {
  const cell = (v: any) => v === null || v === undefined ? "—" : String(v);
  return <div className="panel-pad">
    <p className="hint">Toutes les valeurs extraites du bordereau, avec le niveau d'accord entre lectures OCR. Une valeur douteuse peut être corrigée : l'original est conservé.</p>
    <table className="data small"><thead><tr><th>Champ</th><th>Valeur</th><th>Accord</th><th /></tr></thead><tbody>
      {Object.values(ext.fields).map((f: any) => <tr key={f.field}><td>{f.business}<div className="hint">{f.zone_label}</div></td>
        <td className="mono">{f.field.match(/Z8|Z12|Z13|ST/) && typeof f.value === "number" ? euro(f.value) : cell(f.value)}</td>
        <td>{AG[f.agreement] || f.agreement}{f.notes?.length ? <div className="hint">{f.notes.join(" ; ")}</div> : null}</td>
        <td>{!readOnly && <button className="btn small" onClick={() => onCorrect({ target: `fields.${f.field}`, label: f.business, current: f.value })}>Corriger</button>}</td></tr>)}
    </tbody></table>
    {["Z6", "Z7", "Z10"].map(z => ext.tables[z]?.length > 0 && <div key={z} style={{ marginTop: 12 }}>
      <h3>{z === "Z6" ? "Zone 6 — prestations" : z === "Z7" ? "Zone 7 — LPP / pharmacie" : "Zone 10 — actes (et zone 9 — exécutants)"}</h3>
      <table className="data small"><thead><tr><th>#</th>{Object.keys(ext.tables[z][0].cells).map(k => <th key={k}>{k}</th>)}<th>Type</th></tr></thead><tbody>
        {ext.tables[z].map((r: any) => <tr key={r.row}><td>{r.row + 1}</td>{Object.entries(r.cells).map(([k, c]: any) =>
          <td key={k} className="mono" title={`${AG[c.agreement] || c.agreement}`} style={{ color: c.agreement === "divergent" || c.agreement === "illisible" ? "#8a5a00" : undefined }}>
            {k.match(/montant|honoraires|quantite/) && typeof c.value === "number" ? (c.value / 100).toFixed(2).replace(".", ",") : cell(c.value)}
            {!readOnly && c.agreement !== "vide" && <button className="btn small" style={{ marginLeft: 4, padding: "0 5px" }} title="Corriger"
              onClick={() => onCorrect({ target: `tables.${z}.${r.row}.cells.${k}`, label: `${z} ligne ${r.row + 1} — ${k}`, current: c.value })}>✎</button>}</td>)}
          <td>{r.kind}</td></tr>)}</tbody></table></div>)}
    <h3 style={{ marginTop: 12 }}>Zones de signature</h3>
    <table className="data small"><thead><tr><th>Zone</th><th>Présence</th><th>Nature</th><th>N° lus</th><th /></tr></thead><tbody>
      {[...ext.signatures.Z11.map((s: any, i: number) => ({ ...s, z: `Zone 11 — case ${s.case}`, t: `signatures.Z11.${i}` })), ...ext.signatures.Z14.map((s: any, i: number) => ({ ...s, z: "Zone 14 — directeur", t: `signatures.Z14.${i}` }))]
        .map((s: any) => <tr key={s.t}><td>{s.z}</td><td>{s.status}{s.original_status ? ` (détecté : ${s.original_status})` : ""}</td><td>{s.nature}</td><td className="mono">{(s.numbers || []).join(", ")}</td>
          <td>{!readOnly && <button className="btn small" onClick={() => onCorrect({ target: s.t, label: s.z, current: s.status, options: ["PRESENT", "VIDE"] })}>Corriger</button>}</td></tr>)}
    </tbody></table>
    {corrections?.length > 0 && <><h3 style={{ marginTop: 12 }}>Corrections actives</h3>
      <ul className="timeline">{corrections.map((x: any) => <li key={x.id}>{x.target} : « {x.original} » → « {x.corrected} » ({x.username})
        {!readOnly && <button className="btn small" style={{ marginLeft: 8 }} onClick={() => onCancel(x.id)}>Annuler</button>}</li>)}</ul></>}
  </div>;
}

function Structured({ t }: { t: any }) {
  const fv = (f: any) => f ? <span className="mono">{f.raw}</span> : "—";
  return <div className="pane-body struct">
    <table><tbody>
      <tr><th>NumeroTiers</th><td>{fv(t.numero_tiers)}</td><td className="hint">type 1, pos. 2-10</td></tr>
      <tr><th>NumeroLot</th><td>{fv(t.numero_lot)}</td><td className="hint">type 1, pos. 20-22</td></tr>
      <tr><th>NumeroAssure</th><td>{fv(t.numero_assure)}</td><td className="hint">type 2, pos. 12-24</td></tr>
      <tr><th>NumeroFacture</th><td>{fv(t.numero_facture)}</td><td className="hint">type 2, pos. 30-38</td></tr>
      <tr><th>TotalPrestations</th><td className="mono">{t.total_prestations ? euro(t.total_prestations.cents) : "—"}</td><td className="hint">type 5, pos. 42-49</td></tr>
      <tr><th>TotalHonoraires</th><td className="mono">{t.total_honoraires ? euro(t.total_honoraires.cents) : "—"}</td><td className="hint">type 5, pos. 58-65</td></tr>
    </tbody></table>
    <h3 style={{ marginTop: 12 }}>Prestations hospitalières (type 3)</h3>
    <table><thead><tr><th>Ligne</th><th>Acte</th><th>NumeroGH</th><th>Base (83-90)</th></tr></thead><tbody>
      {t.acts3.map((x: any) => <tr key={x.line_no}><td>{x.line_no}</td><td className="mono">{x.acte}</td><td className="mono">{x.gh}</td><td className="mono">{euro(x.base_cents)}</td></tr>)}</tbody></table>
    <h3 style={{ marginTop: 12 }}>Actes (type 4) et codes CCAM (4-M)</h3>
    <table><thead><tr><th>Ligne</th><th>Acte</th><th>Honoraires (115-121)</th></tr></thead><tbody>
      {t.acts4.map((x: any) => <tr key={x.line_no}><td>{x.line_no}</td><td className="mono">{x.acte}{t.ccam4m.filter((c: any) => c.parent_line === x.line_no).map((c: any) => <span key={c.line_no} className="tag" style={{ marginLeft: 6 }}>CCAM {c.code7} (l. {c.line_no})</span>)}</td><td className="mono">{euro(x.honoraires_cents)}</td></tr>)}</tbody></table>
    <h3 style={{ marginTop: 12 }}>NumeroGH des enregistrements 4-S</h3>
    <p className="mono">{t.gh4s.length ? Object.entries(t.gh4s.reduce((m: any, g: any) => (m[g.gh] = (m[g.gh] || 0) + 1, m), {})).map(([k, v]) => `${k} ×${v}`).join(", ") : "aucun"}</p>
    <h3 style={{ marginTop: 12 }}>Fichier</h3>
    <p className="small">SHA-256 <span className="mono">{t.sha256}</span> · {t.records.length} enregistrements · fins de ligne {t.line_ending}</p>
  </div>;
}

function Assistant({ id }: { id: string }) {
  const [q, setQ] = useState("");
  const [ans, setAns] = useState<any>(null);
  const ask = (question: string) => api.post<any>(`/api/cases/${id}/ask`, { question }).then(setAns);
  const [open, setOpen] = useState(false);
  if (!open) return <div className="assistant"><button className="btn small" onClick={() => setOpen(true)}>Ouvrir l'assistant de contrôle</button>
    <span className="hint" style={{ marginLeft: 8 }}>résumé, ordre de traitement, explications des règles</span></div>;
  return <div className="assistant">
    <div className="row"><b className="small">Assistant</b><span className="hint">réponses construites uniquement à partir du dossier</span><span className="spacer" /><button className="btn small" onClick={() => setOpen(false)}>Fermer</button></div>
    <div className="row" style={{ marginTop: 6 }}>
      {["Résumé", "Que dois-je faire ?", "Écarts de montant", "Éléments à vérifier"].map(x => <button key={x} className="btn small" onClick={() => ask(x)}>{x}</button>)}
    </div>
    <form className="row" style={{ marginTop: 6 }} onSubmit={e => { e.preventDefault(); if (q.trim()) ask(q); }}>
      <input className="input" style={{ flex: 1 }} value={q} onChange={e => setQ(e.target.value)} placeholder="Ex. : pourquoi R12 ?" aria-label="Question à l'assistant" />
      <button className="btn small">Demander</button>
    </form>
    {ans && <div className="answer">{ans.answer}{ans.sources?.length ? <div className="hint" style={{ marginTop: 4 }}>Sources : {ans.sources.join(", ")}</div> : null}</div>}
  </div>;
}
