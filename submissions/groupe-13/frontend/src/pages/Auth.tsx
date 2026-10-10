import { useState } from "react";
import { api, User } from "../api";

export default function Auth({ needsSetup, onLogged, production }: { needsSetup: boolean; onLogged: (u: User) => void; production?: boolean }) {
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [f, setF] = useState({ username: "", password: "", admin_username: "admin", admin_display_name: "Administrateur", admin_password: "", confirm: "", create_demo_accounts: false });
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setErr(null);
    if (needsSetup && f.admin_password !== f.confirm) { setErr("Les deux mots de passe ne sont pas identiques."); return; }
    setBusy(true);
    try {
      const r = needsSetup
        ? await api.post<{ user: User }>("/api/setup", { admin_username: f.admin_username, admin_display_name: f.admin_display_name, admin_password: f.admin_password, create_demo_accounts: f.create_demo_accounts })
        : await api.post<{ user: User }>("/api/login", { username: f.username, password: f.password });
      onLogged(r.user);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  return <div className="auth">
    <div className="auth-card">
      <div className="row" style={{ gap: 10, marginBottom: 6 }}>
        <div className="brand-mark" style={{ width: 34, height: 34, borderRadius: 8, background: "#2f3a8f", display: "grid", placeItems: "center" }}>
          <svg width="20" height="20" viewBox="0 0 32 32"><path d="M8 17l5 5 11-12" stroke="#e3a62b" strokeWidth="4" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </div>
        <div><b>iMSA Sentinel</b><div className="hint">Contrôle des justificatifs de dépenses de santé</div></div>
      </div>
      {needsSetup ? <>
        <h1>Première mise en service</h1>
        <p className="muted small">Créez le compte administrateur. Aucun mot de passe n'est fourni par défaut : vous le choisissez ici, il est stocké sous forme d'empreinte (scrypt) dans la base locale.</p>
        <form onSubmit={submit}>
          <label className="field">Identifiant administrateur<input className="input" value={f.admin_username} onChange={set("admin_username")} required /></label>
          <label className="field">Nom affiché<input className="input" value={f.admin_display_name} onChange={set("admin_display_name")} required /></label>
          <label className="field">Mot de passe (8 caractères minimum)<input className="input" type="password" value={f.admin_password} onChange={set("admin_password")} minLength={8} required autoComplete="new-password" /></label>
          <label className="field">Confirmer le mot de passe<input className="input" type="password" value={f.confirm} onChange={set("confirm")} minLength={8} required autoComplete="new-password" /></label>
          {!production && <label className="small" style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
            <input type="checkbox" style={{ marginTop: 3, flex: "none" }} checked={f.create_demo_accounts} onChange={set("create_demo_accounts")} />
            <span><b>Mode démonstration</b> : créer aussi les comptes agent1, agent2, superviseur et auditeur (même mot de passe). À ne pas utiliser en production.</span></label>}
          {err && <div className="error-text">{err}</div>}
          <button className="btn primary" disabled={busy}>Créer le compte et entrer</button>
        </form>
      </> : <>
        <h1>Connexion</h1>
        <form onSubmit={submit}>
          <label className="field">Identifiant<input className="input" value={f.username} onChange={set("username")} autoFocus required autoComplete="username" /></label>
          <label className="field">Mot de passe<input className="input" type="password" value={f.password} onChange={set("password")} required autoComplete="current-password" /></label>
          {err && <div className="error-text">{err}</div>}
          <button className="btn primary" disabled={busy}>Se connecter</button>
        </form>
        <p className="hint" style={{ marginTop: 12 }}>Comptes de démonstration (si créés à la mise en service) : agent1, agent2, superviseur, auditeur.</p>
      </>}
    </div>
  </div>;
}
