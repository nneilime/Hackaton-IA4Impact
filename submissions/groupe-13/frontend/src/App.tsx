import { useEffect, useState } from "react";
import { api, ROLE_LABEL, User } from "./api";
import { Icon, go, Loading, ToastProvider, useRoute } from "./components/ui";
import Auth from "./pages/Auth";
import Overview from "./pages/Overview";
import Cases from "./pages/Cases";
import CaseDesk from "./pages/CaseDesk";
import Compare from "./pages/Compare";
import Anomalies from "./pages/Anomalies";
import Investigations from "./pages/Investigations";
import Supervision from "./pages/Supervision";
import Reports from "./pages/Reports";
import Audit from "./pages/Audit";
import Rules from "./pages/Rules";
import Imports from "./pages/Imports";
import Review from "./pages/Review";
import Quality from "./pages/Quality";

interface Status { state: { phase: string; done: number; total: number; current: string | null; error: string | null; warning?: string | null }; needs_setup: boolean; engine_version: string; ruleset_version: string; ocr?: Record<string, string | null>; production?: boolean }

// Navigation en trois espaces (version 3.0) : le quotidien de l'agent, le pilotage (selon le rôle),
// et les outils avancés regroupés dans un menu repliable. Aucune capacité n'est supprimée.
const PILOT = ["superviseur", "admin", "auditeur"];
const NAV: { path: string; label: string; roles?: string[]; group: "mes" | "pilotage" | "avance"; hint?: string }[] = [
  { path: "/", label: "Mes dossiers", group: "mes", hint: "Dossiers à traiter et dossier suivant" },
  { path: "/dossiers", label: "Tous les dossiers", group: "mes" },
  { path: "/anomalies", label: "Écarts à examiner", group: "mes" },
  { path: "/revue", label: "Revue rapide", group: "mes" },
  { path: "/supervision", label: "Supervision de caisse", roles: PILOT, group: "pilotage" },
  { path: "/investigations", label: "Investigations", group: "pilotage" },
  { path: "/qualite", label: "Qualité et validation", roles: PILOT.concat(["agent"]), group: "pilotage" },
  { path: "/rapports", label: "Rapports", group: "pilotage" },
  { path: "/comparaison", label: "Comparer deux bordereaux", group: "avance" },
  { path: "/import", label: "Imports et simulations", group: "avance" },
  { path: "/regles", label: "Règles et conventions", group: "avance" },
  { path: "/audit", label: "Journal d'audit", roles: PILOT, group: "avance" },
];
const GROUP_LABEL = { mes: "Mes contrôles", pilotage: "Pilotage", avance: "Outils avancés" };

export default function App() {
  return <ToastProvider><Root /></ToastProvider>;
}

function Root() {
  const [status, setStatus] = useState<Status | null>(null);
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const [route, params] = useRoute();
  const [q, setQ] = useState("");

  useEffect(() => {
    let t: any;
    const poll = () => api.get<Status>("/api/status").then(s => {
      setStatus(s);
      if (s.state.phase !== "prêt" && s.state.phase !== "erreur") t = setTimeout(poll, 1500);
    }).catch(() => { t = setTimeout(poll, 2000); });
    poll();
    api.get<User>("/api/me").then(setUser).catch(() => setUser(null));
    const un = () => setUser(null);
    window.addEventListener("sentinel:unauthorized", un);
    return () => { clearTimeout(t); window.removeEventListener("sentinel:unauthorized", un); };
  }, []);

  if (!status || user === undefined) return <Loading what="Démarrage d'iMSA Sentinel" />;
  if (!user) return <Auth needsSetup={status.needs_setup} onLogged={setUser} production={status.production} />;
  if (status.state.phase !== "prêt") {
    return <div className="auth"><div className="auth-card">
      <h1>Préparation du corpus</h1>
      <p className="muted">{status.state.phase}{status.state.total ? ` — ${status.state.done}/${status.state.total} dossiers (${status.state.current || ""})` : ""}</p>
      {status.state.error && <div className="notice bad">{status.state.error}</div>}
      <p className="hint">Lecture de l'archive, vérification des empreintes SHA-256, extraction des bordereaux et application des 22 contrôles. Les résultats d'extraction sont mis en cache : les démarrages suivants sont immédiats.</p>
    </div></div>;
  }

  const nav = NAV.filter(n => !n.roles || n.roles.includes(user.role))
    .filter(n => n.group !== "pilotage" || user.role !== "agent" || ["/investigations", "/rapports", "/qualite"].includes(n.path));
  const base = "/" + (route.split("/")[1] || "");
  let page: JSX.Element;
  const seg = route.split("/").filter(Boolean);
  switch (seg[0]) {
    case undefined: page = <Overview user={user} />; break;
    case "dossiers": page = <Cases user={user} params={params} />; break;
    case "controle": page = seg[1] ? <CaseDesk key={seg[1]} id={decodeURIComponent(seg[1])} user={user} params={params} /> : <Cases user={user} params={params} pick />; break;
    case "comparaison": page = <Compare user={user} params={params} />; break;
    case "anomalies": page = <Anomalies params={params} />; break;
    case "validation": page = <Quality user={user} tab="validation" />; break;
    case "investigations": page = <Investigations user={user} />; break;
    case "supervision": page = <Supervision user={user} />; break;
    case "rapports": page = <Reports user={user} />; break;
    case "audit": page = <Audit />; break;
    case "regles": page = <Rules user={user} />; break;
    case "import": page = <Imports user={user} params={params} />; break;
    case "revue": page = <Review user={user} />; break;
    case "qualite": page = <Quality user={user} tab={params.get("onglet") === "validation" ? "validation" : "mesures"} />; break;
    default: page = <div className="empty">Page introuvable.</div>;
  }
  const flush = seg[0] === "controle" && seg[1] || seg[0] === "comparaison" || seg[0] === "revue";

  return <div className="shell">
    <nav className="rail" aria-label="Navigation principale">
      <div className="brand">
        <div className="brand-mark"><svg width="18" height="18" viewBox="0 0 32 32"><path d="M8 17l5 5 11-12" stroke="#e3a62b" strokeWidth="4" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg></div>
        <div><b>iMSA Sentinel</b><span>Contrôle des justificatifs</span></div>
      </div>
      {(["mes", "pilotage", "avance"] as const).map(g => {
        const items = nav.filter(n => n.group === g);
        if (!items.length) return null;
        const links = items.map(n => <a key={n.path} href={"#" + n.path} title={n.hint}
          className={base === n.path || (n.path === "/" && route === "/") ? "active" : ""}>{n.label}</a>);
        if (g !== "avance") return <div key={g}><div className="rail-group">{GROUP_LABEL[g]}</div>{links}</div>;
        const inside = items.some(n => base === n.path);
        return <details key={g} className="rail-adv" open={inside || undefined}><summary className="rail-group">{GROUP_LABEL[g]}</summary>{links}</details>;
      })}
      <div className="rail-foot">Moteur {status.engine_version} · règles {status.ruleset_version}<br />Traitement 100 % local<br />
        OCR : RapidOCR{status.ocr?.tesseract ? " + Tesseract" : ""}
        {status.ocr && !status.ocr.tesseract && <div style={{ color: "#f3c96b", marginTop: 4 }}>Tesseract absent : les nouveaux dépôts n'ont qu'un moteur OCR, relancez INSTALLER.bat.</div>}</div>
    </nav>
    <div className="main">
      <header className="topbar">
        <form className="search" onSubmit={e => { e.preventDefault(); go(`/dossiers?q=${encodeURIComponent(q)}`); }}>
          <Icon.search />
          <input value={q} onChange={e => setQ(e.target.value)} placeholder="Rechercher un dossier, un n° de facture, un établissement…" aria-label="Recherche" />
        </form>
        <div className="who">
          <div style={{ textAlign: "right" }}><div>{user.display_name}</div><div className="role">{ROLE_LABEL[user.role]}</div></div>
          <button className="btn small" onClick={() => api.post("/api/logout").then(() => setUser(null))}>Se déconnecter</button>
        </div>
      </header>
      {status.state.warning && <div className="notice warn" style={{ margin: 0, borderRadius: 0 }}>{status.state.warning}</div>}
      <main className={`content ${flush ? "flush" : ""}`}>{page}</main>
    </div>
  </div>;
}
