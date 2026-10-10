import { useEffect, useMemo, useState } from "react";
import { api, euro, STATUS_LABEL, User } from "../api";
import ImageViewer, { bboxOf, ZoneOverlay } from "../components/ImageViewer";
import TxtViewer, { Hl } from "../components/TxtViewer";
import { ErrorBox, Loading, Modal, StatusPill, go, useActivity, useFetch, useToast } from "../components/ui";
import { CorrectionModal, DecisionModal } from "./CaseDesk";

const FIELD_OF_RULE: Record<string, string> = { R01: "Z1", R02: "Z2", R03: "Z3", R04: "Z4", R05: "Z5", R12: "Z8", R17: "Z12", R22: "Z15" };
type Action = "confirm" | "fp" | "review" | "correct" | "comment" | "next" | "prev";
const DEFAULT_KEYS: Record<Action, string> = { confirm: "c", fp: "f", review: "r", correct: "l", comment: "m", next: "n", prev: "p" };
const ACTION_LABEL: Record<Action, string> = {
  confirm: "Confirmer l'écart", fp: "Faux positif", review: "Revue complémentaire", correct: "Corriger la lecture",
  comment: "Commenter", next: "Suivante", prev: "Précédente",
};

function loadKeys(): Record<Action, string> {
  try { return { ...DEFAULT_KEYS, ...JSON.parse(localStorage.getItem("sentinel.raccourcis") || "{}") }; } catch { return DEFAULT_KEYS; }
}

export default function Review({ user }: { user: User }) {
  const [withNv, setWithNv] = useState(true);
  const queue = useFetch<any[]>(`/api/review/queue?include_nv=${withNv}`);
  const [i, setI] = useState(0);
  const [done, setDone] = useState<Record<string, string>>({});
  const [keys, setKeys] = useState(loadKeys);
  const [keyModal, setKeyModal] = useState(false);
  const [modal, setModal] = useState<any>(null);
  const [corr, setCorr] = useState<any>(null);
  const toast = useToast();
  const items = queue.data || [];
  const item = items[i];
  const cs = useFetch<any>(item ? `/api/cases/${encodeURIComponent(item.case_id)}` : null);
  useActivity(item?.case_id || null);
  const readOnly = user.role === "auditeur";

  const a = cs.data?.analysis;
  const res = a?.results?.find((r: any) => r.rule_id === item?.rule_id);
  const zones = a?.zones || [];
  const zid = item?.zones?.find((z: string) => zones.find((x: any) => x.zone_id === z)?.regions?.length) || item?.zones?.[0];
  const zone = zones.find((z: any) => z.zone_id === zid);
  const overlays: ZoneOverlay[] = zones.map((z: any) => ({ id: z.zone_id, label: z.label, status: z.status, regions: z.regions, flags: z.flags }));
  const target = res?.img_refs?.find((r: any) => r.box)?.box || (zone ? bboxOf(zone.regions) : null);
  const focus = useMemo(() => target ? { box: target, n: Date.now() } : null, [item?.case_id, item?.rule_id, a?.analyzed_at]); // eslint-disable-line
  const hl: Hl[] = res ? [...(res.txt_refs || []), ...((zone?.txt?.links || []).filter((l: any) => l.line_no && !l.absent))]
    .filter((r: any) => r.line_no).slice(0, 40).map((r: any) => ({ line_no: r.line_no, start: r.start, end: r.end, label: r.label })) : [];
  const key = item ? `${item.case_id}/${item.rule_id}` : "";

  const move = (d: number) => setI(x => Math.max(0, Math.min(items.length - 1, x + d)));
  const decide = async (kind: string, comment?: string) => {
    try {
      await api.post(`/api/cases/${item.case_id}/decisions`, { kind, rule_id: item.rule_id, comment });   // enregistré avant affichage
      setDone(m => ({ ...m, [key]: kind })); toast(`${ACTION_LABEL[kind === "confirmation" ? "confirm" : kind === "faux_positif" ? "fp" : kind === "revue_complementaire" ? "review" : "comment"]} enregistré — ${item.case_id} ${item.rule_id}`);
      if (kind !== "commentaire") move(1);
    } catch (e: any) { toast(`Échec : ${e.message} (rien n'a été enregistré)`); throw e; }
  };
  const run = (act: Action) => {
    if (!item || !res) return;
    if (act === "next") return move(1);
    if (act === "prev") return move(-1);
    if (readOnly) return;
    if (act === "confirm" && res.status === "ANOMALIE") setModal({ kind: "confirmation", title: `Confirmer l'écart ${item.rule_id} — ${item.case_id}` });
    if (act === "fp" && res.status === "ANOMALIE") setModal({ kind: "faux_positif", title: `Déclarer ${item.rule_id} faux positif`, needComment: true });
    if (act === "review") setModal({ kind: "revue_complementaire", title: `Revue complémentaire — ${item.rule_id}` });
    if (act === "comment") setModal({ kind: "commentaire", title: `Commenter ${item.rule_id}`, needComment: true });
    if (act === "correct" && FIELD_OF_RULE[item.rule_id]) {
      const f = a.extraction.fields[FIELD_OF_RULE[item.rule_id]];
      const money = ["Z8", "Z12"].includes(f.field);
      setCorr({ target: `fields.${f.field}`, label: f.business, current: money && typeof f.value === "number" ? (f.value / 100).toFixed(2).replace(".", ",") : f.value });
    }
  };
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT") || document.querySelector(".modal") || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === "ArrowRight") return run("next");
      if (e.key === "ArrowLeft") return run("prev");
      const act = (Object.keys(keys) as Action[]).find(x => keys[x].toLowerCase() === e.key.toLowerCase());
      if (act) { e.preventDefault(); run(act); }
    };
    window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k);
  });

  if (queue.error) return <div className="content"><ErrorBox e={queue.error} /></div>;
  if (!queue.data) return <Loading />;
  if (!items.length) return <div className="content"><div className="page-head"><div><h1>Revue rapide</h1>
    <p>Aucune anomalie{withNv ? " ni contrôle non vérifiable" : ""} sans décision dans les dossiers qui vous sont accessibles.</p></div></div>
    <button className="btn" onClick={() => go("/dossiers")}>Voir les dossiers</button></div>;
  const pct = Math.round(100 * Object.keys(done).length / items.length);
  const K = (act: Action) => <span className="kbd">{keys[act].toUpperCase()}</span>;

  return <div className="desk-wrap">
    <div className="review-banner" data-testid="review-banner">
      <span>Revue rapide · <b>{i + 1} / {items.length}</b></span>
      <span>Vous vérifiez la <b>zone {zid}{zone ? ` — ${zone.label}` : ""}</b></span>
      <span className="muted">{item.case_id} · {item.rule_id} {item.title}</span>
      <span className="spacer" />
      <label className="small row" style={{ color: "#fff" }}><input type="checkbox" checked={withNv} onChange={e => { setWithNv(e.target.checked); setI(0); }} /> inclure les non vérifiables</label>
      <button className="btn small" onClick={() => setKeyModal(true)}>Raccourcis</button>
      <a className="btn small" href={`#/controle/${item.case_id}?zone=${zid}`}>Ouvrir le dossier</a>
    </div>
    <div className="progressbar" title={`${Object.keys(done).length} décision(s) enregistrée(s) dans cette session`}><i style={{ width: `${pct}%` }} /></div>
    <div className="review">
      <section aria-label="Bordereau">
        {!a ? <Loading /> : <ImageViewer src={`/api/cases/${item.case_id}/image`} size={a.extraction.size} zones={overlays} showZones legend
          selectedZone={zid} onZoneClick={z => go(`/controle/${item.case_id}?zone=${z}`)} focusRect={focus} rotate180={a.extraction.layout?.rotation === 180} />}
      </section>
      <section aria-label="Contrôle à décider" style={{ borderRight: 0 }}>
        {!res ? <Loading /> : <>
          <div className="detail" style={{ borderTop: 0, overflow: "auto", maxHeight: "58%" }}>
            <div className="row"><span className="tag rule">{res.rule_id}</span><b>{res.title}</b><StatusPill s={res.status} />
              {done[key] && <span className="tag">décision enregistrée : {done[key].replace("_", " ")}</span>}</div>
            <p className="expl" style={{ marginTop: 6 }}>{res.explanation}</p>
            {(res.jpg_value || res.txt_value) && <div className="vs">
              <div><div className="k">Bordereau (JPG) — {zid}</div><div className="v">{res.jpg_value ?? "—"}</div></div>
              <div><div className="k">Fichier (TXT)</div><div className="v">{res.txt_value ?? "—"}</div></div></div>}
            <dl className="kv">
              {res.gap?.amount_cents ? <><dt>Écart mesuré</dt><dd>{euro(res.gap.amount_cents)} ({res.gap.label})</dd></> : null}
              {res.uncertainty && <><dt>Incertitude</dt><dd>{res.uncertainty.level} — {res.uncertainty.reason}</dd></>}
              <dt>Zone(s)</dt><dd>{(item.zones || []).join(", ")} · statut de {zid} : {zone ? STATUS_LABEL[zone.status as keyof typeof STATUS_LABEL] : "—"}</dd>
              <dt>Cahier des charges</dt><dd>« {res.spec} »</dd>
              <dt>Prochaine étape</dt><dd>{res.next_action}</dd>
            </dl>
            {!readOnly && <div className="row" style={{ marginTop: 10 }}>
              {res.status === "ANOMALIE" && <>
                <button className="btn small danger" onClick={() => run("confirm")}>Confirmer l'écart {K("confirm")}</button>
                <button className="btn small ok" onClick={() => run("fp")}>Faux positif {K("fp")}</button></>}
              <button className="btn small" onClick={() => run("review")}>Revue complémentaire {K("review")}</button>
              {FIELD_OF_RULE[item.rule_id] && <button className="btn small" onClick={() => run("correct")}>Corriger la lecture {K("correct")}</button>}
              <button className="btn small" onClick={() => run("comment")}>Commenter {K("comment")}</button>
            </div>}
            <div className="row" style={{ marginTop: 8 }}>
              <button className="btn small" disabled={i === 0} onClick={() => run("prev")}>← Précédente {K("prev")}</button>
              <button className="btn small" disabled={i >= items.length - 1} onClick={() => run("next")}>Suivante {K("next")} →</button>
              <span className="hint">Les flèches ← → naviguent aussi. Une décision n'apparaît validée qu'après son enregistrement.</span>
            </div>
          </div>
          <div className="pane-head"><h3>Facture structurée</h3><span className="hint">{a.txt_file}</span></div>
          <TxtViewer records={a.txt.records} highlights={hl} focusLine={hl[0]?.line_no ?? null} />
        </>}
      </section>
    </div>
    {modal && <DecisionModal m={modal} onClose={() => setModal(null)} onSubmit={c => decide(modal.kind, c).then(() => setModal(null)).catch(() => undefined)} />}
    {corr && <CorrectionModal c={corr} onClose={() => setCorr(null)} onSubmit={(v, comment) =>
      api.post<any>(`/api/cases/${item.case_id}/corrections`, { target: corr.target, corrected: v, comment })
        .then(() => { toast("Lecture enregistrée — contrôles recalculés"); setCorr(null); cs.reload(); })
        .catch((e: any) => toast(`Échec : ${e.message}`))} />}
    {keyModal && <KeysModal keys={keys} onClose={() => setKeyModal(false)} onSave={k => {
      setKeys(k); try { localStorage.setItem("sentinel.raccourcis", JSON.stringify(k)); } catch { /* stockage indisponible */ } setKeyModal(false); }} />}
  </div>;
}

function KeysModal({ keys, onClose, onSave }: { keys: Record<Action, string>; onClose: () => void; onSave: (k: Record<Action, string>) => void }) {
  const [k, setK] = useState(keys);
  const vals = Object.values(k).map(x => x.toLowerCase());
  const dup = vals.some((x, j) => !x || vals.indexOf(x) !== j);
  return <Modal title="Raccourcis clavier de la revue rapide" onClose={onClose}>
    <p className="small muted">Une touche par action (lettre ou chiffre). Les raccourcis sont ignorés pendant une saisie dans un champ.</p>
    <table className="data small"><tbody>{(Object.keys(k) as Action[]).map(act => <tr key={act}><td>{ACTION_LABEL[act]}</td>
      <td><input className="input mono" style={{ width: 60 }} maxLength={1} value={k[act]} onChange={e => setK({ ...k, [act]: e.target.value.toLowerCase() })} aria-label={ACTION_LABEL[act]} /></td></tr>)}</tbody></table>
    {dup && <p className="error-text">Chaque action doit avoir une touche différente.</p>}
    <div className="row" style={{ marginTop: 12, justifyContent: "flex-end" }}>
      <button className="btn" onClick={() => setK(DEFAULT_KEYS)}>Valeurs par défaut</button>
      <button className="btn" onClick={onClose}>Annuler</button>
      <button className="btn primary" disabled={dup} onClick={() => onSave(k)}>Enregistrer</button>
    </div>
  </Modal>;
}
