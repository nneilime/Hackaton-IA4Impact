import { useEffect, useState, type ReactNode, type FormEvent } from "react";
import type { Session } from "@supabase/supabase-js";
import { authClient, setSession } from "./api";
export function AuthGate({ children }: { children: ReactNode }) {
  const [session, updateSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let alive = true;
    let unsubscribe = () => {};
    authClient()
      .then(async (client) => {
        const { data, error } = await client.auth.getSession();
        if (!alive) return;
        if (error) throw error;
        setSession(data.session);
        updateSession(data.session);
        setReady(true);
        const subscription = client.auth.onAuthStateChange((_event, next) => {
          setSession(next);
          if (alive) updateSession(next);
        });
        unsubscribe = () => subscription.data.subscription.unsubscribe();
      })
      .catch((e) => {
        if (alive) {
          setError(e.message);
          setReady(true);
        }
      });
    return () => {
      alive = false;
      unsubscribe();
    };
  }, []);
  async function login(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const client = await authClient();
      const { error } = await client.auth.signInWithPassword({
        email,
        password,
      });
      if (error) throw error;
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!ready)
    return (
      <div className="boot-state">
        <h1>Connexion à votre espace</h1>
        <span className="loader" />
      </div>
    );
  if (session) return <div key={session.user.id}>{children}</div>;
  return (
    <div className="boot-state">
      <div className="surface login-card">
        <img src="/brand/action-logement-logo.png" alt="Action Logement" />
        <h1>Votre espace BâtIA</h1>
        <p>Connectez-vous avec votre compte d’équipe.</p>
        <form onSubmit={login}>
          <label>
            Courriel
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label>
            Mot de passe
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error && (
            <p role="alert" className="form-error">
              {error}
            </p>
          )}
          <button className="button primary" disabled={busy}>
            Se connecter
          </button>
        </form>
        <p className="fine-print">
          Les comptes sont ajoutés par un administrateur.
        </p>
      </div>
    </div>
  );
}
