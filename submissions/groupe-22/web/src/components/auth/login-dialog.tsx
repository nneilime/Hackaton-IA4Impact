import { useEffect, useId, useState } from "react"
import { LoaderCircleIcon, LogInIcon, ShieldAlertIcon } from "lucide-react"
import { api } from "@/lib/api"
import { closeLogin, login, useAuth, type Profile } from "@/lib/auth"
import { cn } from "@/lib/utils"
import { Sheet } from "@/components/shell/sheet"

/** The Connexion démo: a fictional profile and the demo code, checked by the server,
 * which opens the customer's session (HttpOnly cookie). Never a real bank's login: no
 * identifier or password field, and it says so. */
export function LoginDialog() {
  const open = useAuth((s) => s.loginOpen)
  const id = useId()
  const [profiles, setProfiles] = useState<Profile[] | null>(null)
  const [demoCode, setDemoCode] = useState("")
  const [profile, setProfile] = useState("camille")
  const [code, setCode] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open || profiles) return
    api<{ profiles: Profile[]; demoCode: string }>("/api/auth/profiles")
      .then((r) => {
        setProfiles(r.profiles)
        setDemoCode(r.demoCode)
      })
      .catch((e: Error) => setError(e.message))
  }, [open, profiles])

  useEffect(() => {
    if (!open) {
      setCode("")
      setError(null)
    }
  }, [open])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (loading) return
    if (!code.trim()) {
      setError("Saisissez le code de démonstration indiqué ci-dessus.")
      return
    }
    setLoading(true)
    setError(null)
    try {
      await login(profile, code)
    } catch (err) {
      setError(err instanceof Error ? err.message : "La connexion a échoué. Réessayez.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Sheet open={open} onClose={closeLogin} title="Connexion démo" description="Profils fictifs : n'entrez jamais vos vrais identifiants bancaires." z="z-[80]">
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        <p className="flex items-start gap-2 rounded-2xl bg-warn-soft p-3 text-xs font-semibold leading-snug text-navy">
          <ShieldAlertIcon className="mt-0.5 size-4 shrink-0 text-warn" aria-hidden />
          Démonstration : aucune vraie banque derrière. Ni identifiant, ni mot de passe, ni code de carte : seulement un profil fictif et le code de démo.
        </p>

        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-sm font-bold text-navy">Profil fictif</legend>
          {!profiles && !error && <div className="skeleton h-16 rounded-2xl" aria-busy="true" aria-label="Chargement des profils" />}
          {profiles?.map((p) => (
            <label
              key={p.id}
              className={cn(
                "hc-outline flex min-h-16 cursor-pointer items-center gap-3 rounded-2xl p-3 ring-1 transition",
                profile === p.id ? "bg-navy/5 ring-2 ring-navy" : "ring-line hover:bg-surface",
              )}
            >
              <input type="radio" name={`${id}-profile`} value={p.id} checked={profile === p.id} onChange={() => setProfile(p.id)} className="size-5 accent-[var(--navy)]" />
              <span>
                <span className="block font-extrabold text-navy">{p.displayName}</span>
                <span className="block text-xs text-muted-ink">{p.description}</span>
              </span>
            </label>
          ))}
        </fieldset>

        <div className="flex flex-col gap-1.5">
          <label htmlFor={`${id}-code`} className="text-sm font-bold text-navy">
            Code de démonstration
          </label>
          <p id={`${id}-hint`} className="text-xs text-muted-ink">
            {demoCode ? (
              <>
                Pour la démo, le code est <strong className="font-extrabold text-navy">{demoCode}</strong>.
              </>
            ) : (
              "Le code est indiqué ici une fois chargé."
            )}
          </p>
          <input
            id={`${id}-code`}
            data-autofocus
            value={code}
            onChange={(e) => setCode(e.target.value)}
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
            aria-describedby={`${id}-hint${error ? ` ${id}-error` : ""}`}
            aria-invalid={!!error}
            className="h-12 rounded-2xl bg-surface px-4 text-[15px] text-navy ring-1 ring-line outline-none focus:ring-2 focus:ring-navy aria-[invalid=true]:ring-brand"
          />
        </div>

        {error && (
          <p id={`${id}-error`} role="alert" className="rounded-2xl bg-brand-soft p-3 text-sm font-semibold text-brand">
            {error}
          </p>
        )}

        <button type="submit" disabled={loading} aria-busy={loading} className="flex h-12 items-center justify-center gap-2 rounded-2xl bg-brand font-bold text-white hover:bg-brand-strong disabled:opacity-70">
          {loading ? <LoaderCircleIcon className="size-5 animate-spin" aria-hidden /> : <LogInIcon className="size-5" aria-hidden />}
          {loading ? "Connexion…" : "Se connecter (démo)"}
        </button>
      </form>
    </Sheet>
  )
}
