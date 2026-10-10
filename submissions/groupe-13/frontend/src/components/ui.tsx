import React, { createContext, useContext, useEffect, useState } from "react";
import { RuleStatus, STATUS_LABEL } from "../api";

export const Icon = {
  ok: (p: any) => <svg width="12" height="12" viewBox="0 0 12 12" {...p}><path d="M2.5 6.2l2.2 2.2 4.8-5" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>,
  ano: (p: any) => <svg width="12" height="12" viewBox="0 0 12 12" {...p}><path d="M6 1.2l5 9H1z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /><path d="M6 4.6v2.6M6 8.6v.1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>,
  nv: (p: any) => <svg width="12" height="12" viewBox="0 0 12 12" {...p}><circle cx="6" cy="6" r="4.6" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="M4.6 4.7a1.5 1.5 0 1 1 1.9 1.4c-.4.2-.5.4-.5.9M6 8.6v.1" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinecap="round" /></svg>,
  na: (p: any) => <svg width="12" height="12" viewBox="0 0 12 12" {...p}><path d="M3 6h6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>,
  err: (p: any) => <svg width="12" height="12" viewBox="0 0 12 12" {...p}><path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>,
  search: (p: any) => <svg width="15" height="15" viewBox="0 0 16 16" {...p}><circle cx="7" cy="7" r="4.8" fill="none" stroke="currentColor" strokeWidth="1.6" /><path d="M10.6 10.6L14 14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>,
};

const STATUS_ICON: Record<RuleStatus, (p: any) => JSX.Element> = {
  CONFORME: Icon.ok, ANOMALIE: Icon.ano, NON_VERIFIABLE: Icon.nv, NON_APPLICABLE: Icon.na, ERREUR_TECHNIQUE: Icon.err,
};

export function StatusPill({ s, short }: { s: RuleStatus; short?: boolean }) {
  const I = STATUS_ICON[s];
  return <span className={`pill ${s}`} title={STATUS_LABEL[s]}><I />{short ? null : STATUS_LABEL[s]}</span>;
}

export function CaseState({ state }: { state: string }) {
  const map: Record<string, [RuleStatus, string]> = {
    anomalie: ["ANOMALIE", "Anomalie(s)"], lecture_humaine: ["NON_VERIFIABLE", "Lecture humaine"],
    conforme: ["CONFORME", "Aucun écart"], erreur: ["ERREUR_TECHNIQUE", "Erreur"],
  };
  const [s, l] = map[state] || ["NON_APPLICABLE", state];
  const I = STATUS_ICON[s];
  return <span className={`pill ${s}`}><I />{l}</span>;
}

// ------------------------------------------------------------------ routing (hash)
export function useRoute(): [string, URLSearchParams] {
  const parse = () => {
    const h = window.location.hash.replace(/^#/, "") || "/";
    const [p, q] = h.split("?");
    return [p, new URLSearchParams(q || "")] as [string, URLSearchParams];
  };
  const [r, setR] = useState(parse);
  useEffect(() => {
    const f = () => setR(parse());
    window.addEventListener("hashchange", f);
    return () => window.removeEventListener("hashchange", f);
  }, []);
  return r;
}
export const go = (path: string) => { window.location.hash = path; };

// ------------------------------------------------------------------ toast
const ToastCtx = createContext<(m: string) => void>(() => {});
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => { if (msg) { const t = setTimeout(() => setMsg(null), 3200); return () => clearTimeout(t); } }, [msg]);
  return <ToastCtx.Provider value={setMsg}>{children}{msg && <div className="toast" role="status">{msg}</div>}</ToastCtx.Provider>;
}
export const useToast = () => useContext(ToastCtx);

export function Loading({ what = "Chargement" }: { what?: string }) {
  return <div className="empty">{what}…</div>;
}

export function ErrorBox({ e }: { e: any }) {
  return <div className="notice bad">{String(e?.message || e)}</div>;
}

export function useFetch<T>(url: string | null, deps: any[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<any>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!url) return;
    let alive = true;
    setError(null);
    fetch(url, { credentials: "same-origin" }).then(async r => {
      if (r.status === 401) window.dispatchEvent(new Event("sentinel:unauthorized"));
      if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail; } catch { /* */ } throw new Error(m); }
      return r.json();
    }).then(d => { if (alive) setData(d); }).catch(e => { if (alive) setError(e); });
    return () => { alive = false; };
  }, [url, n, ...deps]);
  return { data, error, reload: () => setN(x => x + 1), setData };
}

export function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  return <div className="modal-bg" onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}>
    <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
      <h2>{title}</h2>{children}
    </div>
  </div>;
}

/** Temps de travail ACTIF sur un dossier : un signal toutes les 30 s, seulement si l'onglet est visible et
 *  qu'une interaction (souris, clavier, molette) a eu lieu dans la dernière minute. */
export function useActivity(caseId: string | null) {
  useEffect(() => {
    if (!caseId) return;
    let last = Date.now();
    const mark = () => { last = Date.now(); };
    const evs = ["mousemove", "keydown", "wheel", "pointerdown"];
    evs.forEach(e => window.addEventListener(e, mark, { passive: true }));
    const t = setInterval(() => {
      if (document.visibilityState === "visible" && Date.now() - last < 60000)
        fetch(`/api/cases/${encodeURIComponent(caseId)}/activity`, { method: "POST", credentials: "same-origin",
          headers: { "Content-Type": "application/json" }, body: JSON.stringify({ active_seconds: 30 }) }).catch(() => undefined);
    }, 30000);
    return () => { clearInterval(t); evs.forEach(e => window.removeEventListener(e, mark)); };
  }, [caseId]);
}

export function ZoneStrip({ zones }: { zones: Record<string, string> }) {
  const ids = Array.from({ length: 15 }, (_, i) => `Z${i + 1}`);
  if (!zones || !Object.keys(zones).length) return <span className="muted">—</span>;
  return <span className="zstrip" aria-label="Statut des 15 zones">{ids.map(z =>
    <i key={z} className={zones[z] || ""} title={`${z} — ${STATUS_LABEL[(zones[z] || "NON_APPLICABLE") as RuleStatus]}`} />)}</span>;
}
