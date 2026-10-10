import { useEffect, useState } from "react";
import { api, CaseRow, User } from "../api";
import ImageViewer, { View } from "../components/ImageViewer";
import { ErrorBox, Loading, go, useFetch } from "../components/ui";

export default function Compare({ user, params }: { user: User; params: URLSearchParams }) {
  const cases = useFetch<CaseRow[]>("/api/cases");
  const [a, setA] = useState(params.get("a") || "Facture2_01");
  const [b, setB] = useState(params.get("b") || "Facture2_02");
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<"side" | "overlay" | "diff">("side");
  const [opacity, setOpacity] = useState(0.5);
  const [view, setView] = useState<View>({ s: 0.45, x: 10, y: 6 });
  const [focus, setFocus] = useState<string | null>(null);
  const [sizeA, setSizeA] = useState<[number, number] | null>(null);
  const [zfocus, setZfocus] = useState<{ box: number[]; n: number } | null>(null);
  const [zsel, setZsel] = useState<string | null>(null);

  const run = () => {
    setBusy(true); setErr(null); setRes(null); setFocus(null);
    go(`/comparaison?a=${a}&b=${b}`);
    api.post<any>("/api/compare", { a, b }).then(r => { setRes(r); setSizeA(r.size_a); }).catch(setErr).finally(() => setBusy(false));
  };
  useEffect(() => { run(); }, []); // eslint-disable-line

  if (cases.error) return <ErrorBox e={cases.error} />;
  if (!cases.data) return <Loading />;
  const opts = cases.data.map(c => <option key={c.id} value={c.id}>{c.id} — {c.establishment}</option>);
  const boxes = (res?.regions || []).map((r: any) => ({ id: `g${r.id}`, box: r.box, label: `#${r.id} ${r.zone}`, cls: "ANOMALIE", title: r.kind }));
  const sameSize = res && res.size_a[0] === res.size_b[0] && res.size_a[1] === res.size_b[1];
  const showZone = (z: any) => { if (!z.bbox) return; setZsel(z.zone_id); setFocus(null); setZfocus({ box: z.bbox, n: Date.now() }); };
  const zoneBoxes = zsel && res?.zones ? res.zones.filter((z: any) => z.zone_id === zsel && z.bbox).map((z: any) => ({ id: `z-${z.zone_id}`, box: z.bbox, label: z.zone_id, cls: "search", title: z.label })) : [];
  const allBoxes = [...boxes, ...zoneBoxes];

  return <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
    <div className="case-bar">
      <h1>Comparaison d'images</h1>
      <label className="row small">A <select className="input" value={a} onChange={e => setA(e.target.value)}>{opts}</select></label>
      <label className="row small">B <select className="input" value={b} onChange={e => setB(e.target.value)}>{opts}</select></label>
      <button className="btn primary" onClick={run} disabled={busy || a === b}>{busy ? "Comparaison…" : "Comparer"}</button>
      <span className="spacer" />
      <div className="tabs">
        {([["side", "Côte à côte"], ["overlay", "Superposition"], ["diff", "Carte des différences"]] as const).map(([k, l]) =>
          <button key={k} className={`tab ${mode === k ? "on" : ""}`} onClick={() => setMode(k)} disabled={k !== "side" && !sameSize}>{l}</button>)}
      </div>
      {mode === "overlay" && <label className="row small">Opacité B <input type="range" min={0} max={1} step={0.05} value={opacity} onChange={e => setOpacity(+e.target.value)} /></label>}
    </div>
    {err && <div style={{ padding: 12 }}><ErrorBox e={err} /></div>}
    {res && <div className={`notice ${res.homologous ? "" : "warn"}`} style={{ margin: "8px 12px 0" }}>
      <b>{res.mode}.</b> {res.warning || "Les deux images portent les mêmes identifiants : les différences relevées peuvent être comparées, sans présumer qu'une version est correcte."}
      <span className="hint"> Identifiants lus — {Object.entries(res.identifiers).map(([k, v]: any) => `${k} : ${v.a ?? "?"} / ${v.b ?? "?"}`).join(" · ")}</span>
    </div>}
    <div style={{ flex: 1, minHeight: 0, display: "grid", gridTemplateColumns: "1fr 330px", marginTop: 8 }}>
      {res && sizeA ? (mode === "side" ?
        <div className="cmp-grid">
          <div><div className="pane-head"><h3>A — {a}</h3><a className="btn small" href={`#/controle/${a}`}>Ouvrir le dossier</a></div>
            <ImageViewer src={`/api/cases/${a}/image`} size={res.size_a} boxes={allBoxes} focusId={focus} view={view} onView={setView} onBoxClick={setFocus} focusRect={zfocus} /></div>
          <div><div className="pane-head"><h3>B — {b}</h3><a className="btn small" href={`#/controle/${b}`}>Ouvrir le dossier</a></div>
            <ImageViewer src={`/api/cases/${b}/image`} size={res.size_b} boxes={allBoxes} focusId={focus} view={view} onView={setView} onBoxClick={setFocus} /></div>
        </div> :
        <div className="cmp-grid" style={{ gridTemplateColumns: "1fr" }}><div>
          <div className="pane-head"><h3>{mode === "overlay" ? "A avec B superposé" : "Différences : rouge = encre présente seulement dans A, bleu = seulement dans B"}</h3></div>
          <ImageViewer src={mode === "overlay" ? `/api/cases/${a}/image` : `/api/compare/visual?a=${a}&b=${b}&mode=diff`} size={res.size_a}
            overlaySrc={mode === "overlay" ? `/api/cases/${b}/image` : null} overlayOpacity={opacity}
            boxes={allBoxes} focusId={focus} view={view} onView={setView} onBoxClick={setFocus} focusRect={zfocus} /></div></div>)
        : <div className="empty">{busy ? "Alignement et comparaison en cours…" : "Choisissez deux bordereaux puis « Comparer »."}</div>}
      <aside className="panel" style={{ borderRadius: 0, overflow: "auto" }}>
        <div className="pane-head"><h3>Comparaison par zone (Z1 à Z15)</h3></div>
        {res?.zones_note && <p className="hint" style={{ padding: "6px 12px 0" }}>{res.zones_note}</p>}
        {res?.zones?.length > 0 && <table className="data small"><tbody>{res.zones.filter((z: any) => z.nature !== "identique").map((z: any) =>
          <tr key={z.zone_id} className={`clickable ${zsel === z.zone_id ? "sel" : ""}`} onClick={() => showZone(z)}>
            <td className="mono">{z.zone_id}</td><td>{z.label}<div className="hint">{z.nature}{z.regions.length ? ` · région(s) ${z.regions.map((r: number) => "#" + r).join(", ")}` : ""}</div>
              {(z.valeur_a !== null || z.valeur_b !== null) && z.valeur_a !== z.valeur_b && <div className="mono">A : {String(z.valeur_a ?? "∅")} · B : {String(z.valeur_b ?? "∅")}</div>}</td></tr>)}
          {res.zones.every((z: any) => z.nature === "identique") && <tr><td className="muted">Aucune zone modifiée.</td></tr>}
          <tr><td colSpan={2} className="hint">Zones identiques : {res.zones.filter((z: any) => z.nature === "identique").map((z: any) => z.zone_id).join(", ") || "aucune"}</td></tr></tbody></table>}
        {res && !res.homologous && <p className="hint" style={{ padding: "6px 12px" }}>Dossiers différents : une différence entre deux patients n'est pas une anomalie de facturation. La conformité JPG ↔ TXT se vérifie dans l'écran de contrôle de chaque dossier.</p>}
        <div className="pane-head"><h3>Régions modifiées ({res?.regions?.length ?? 0})</h3></div>
        {res?.alignment && <p className="hint" style={{ padding: "6px 12px 0" }}>Alignement : décalage de {res.alignment.dx}, {res.alignment.dy} px ({res.alignment.method}). Les écarts d'impression de quelques pixels sont filtrés.</p>}
        {res && !res.same_layout && <p className="hint" style={{ padding: 12 }}>Mises en page différentes : pas de différence pixel à pixel, seule la comparaison des champs est pertinente.</p>}
        <ul className="timeline" style={{ padding: "0 12px" }}>{(res?.regions || []).map((r: any) => <li key={r.id} style={{ cursor: "pointer", background: focus === `g${r.id}` ? "#fff8e8" : undefined }} onClick={() => setFocus(`g${r.id}`)}>
          <b>#{r.id}</b> {r.zone_label || r.zone}<div className="small">{r.kind}</div>
          {(r.text_a || r.text_b) && <div className="small mono">A : {r.text_a || "∅"}<br />B : {r.text_b || "∅"}</div>}</li>)}</ul>
        <div className="pane-head" style={{ marginTop: 8 }}><h3>Champs extraits différents ({res?.field_diffs?.length ?? 0})</h3></div>
        <ul className="timeline" style={{ padding: "0 12px" }}>{(res?.field_diffs || []).map((d: any) => <li key={d.field}>
          <b>{d.label}</b> <span className="tag">{d.type}</span><div className="small mono">A : {String(d.a ?? "∅")}<br />B : {String(d.b ?? "∅")}</div></li>)}</ul>
      </aside>
    </div>
  </div>;
}
