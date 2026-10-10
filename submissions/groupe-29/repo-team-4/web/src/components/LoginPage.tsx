import { FormEvent, useState } from "react"
import { Icon } from "../App"
import { useAuth } from "../auth"

const DEMO_ACCOUNTS = [
  { username: "agent", password: "agent", label: "Agent de contrôle", hint: "Traite la file des factures" },
  { username: "admin", password: "admin", label: "Manager", hint: "Tableaux de bord, cliniques, escalades" },
]

export default function LoginPage() {
  const { login } = useAuth()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)

  const submit = async (event?: FormEvent, account?: { username: string; password: string }) => {
    event?.preventDefault()
    const credentials = account ?? { username, password }
    if (!credentials.username || !credentials.password) return
    setBusy(true)
    setError("")
    try {
      await login(credentials.username, credentials.password)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-[#f8fafc] p-6">
      <div className="w-full max-w-[420px]">
        <div className="mb-8 flex items-center gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-blue-600 text-white shadow-sm">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 3.3 19.5 7.6v8.8L12 20.7l-7.5-4.3V7.6L12 3.3Z" stroke="currentColor" strokeWidth="1.7" />
              <path d="M8.1 12h7.8M12 8.1v7.8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </span>
          <div>
            <p className="text-lg font-semibold tracking-tight text-slate-950">Contrôle des factures</p>
            <p className="text-xs text-slate-500">Bordereaux CERFA et flux B2 des établissements de santé</p>
          </div>
        </div>

        <form onSubmit={submit} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-[0_1px_2px_rgba(15,23,42,0.02)]">
          <h1 className="text-xl font-semibold tracking-tight text-slate-900">Connexion</h1>
          <p className="mt-1 text-sm text-slate-500">Identifiez-vous pour accéder à votre espace.</p>
          <label className="mt-6 block text-xs font-semibold text-slate-700">
            Identifiant
            <input
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              className="mt-2 h-10 w-full rounded-lg border border-slate-200 px-3 text-sm font-normal text-slate-800 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-50"
            />
          </label>
          <label className="mt-4 block text-xs font-semibold text-slate-700">
            Mot de passe
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              className="mt-2 h-10 w-full rounded-lg border border-slate-200 px-3 text-sm font-normal text-slate-800 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-50"
            />
          </label>
          {error && <p className="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</p>}
          <button
            type="submit"
            disabled={busy || !username || !password}
            className="mt-6 flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-blue-600 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {busy ? "Connexion..." : "Se connecter"}
            {!busy && <Icon name="arrow" size={16} />}
          </button>
        </form>

        <div className="mt-5 rounded-2xl border border-dashed border-slate-300 bg-white/60 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Comptes de démonstration</p>
          <div className="mt-3 grid grid-cols-2 gap-2">
            {DEMO_ACCOUNTS.map((account) => (
              <button
                key={account.username}
                onClick={() => submit(undefined, account)}
                disabled={busy}
                className="rounded-xl border border-slate-200 bg-white p-3 text-left transition-colors hover:border-blue-300 hover:bg-blue-50/40"
              >
                <p className="text-xs font-semibold text-slate-800">{account.label}</p>
                <p className="mt-0.5 font-mono text-[11px] text-slate-500">
                  {account.username} / {account.password}
                </p>
                <p className="mt-1 text-[10px] text-slate-400">{account.hint}</p>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
