import { useEffect } from "react"
import { HouseIcon, LockIcon, LogInIcon } from "lucide-react"
import { openLogin } from "@/lib/auth"
import { Link, useLocation } from "@/lib/router"

/** A private page asked for without being logged in (a link, a reload, the address
 * bar): nothing of it is shown, and the server would refuse its data anyway. After the
 * Connexion démo, the same address shows the page. */
export function AuthRequired({ title }: { title: string }) {
  const { pathname, params } = useLocation()
  const here = pathname + (params.size ? `?${params}` : "")
  useEffect(() => {
    document.getElementById("auth-required-title")?.focus()
  }, [pathname])
  return (
    <div className="flex min-h-full flex-col items-center justify-center gap-4 px-6 py-16 text-center">
      <span className="flex size-16 items-center justify-center rounded-3xl bg-white text-brand shadow-sm ring-1 ring-line">
        <LockIcon className="size-8" aria-hidden />
      </span>
      <h1 id="auth-required-title" tabIndex={-1} className="text-[22px] font-extrabold tracking-tight text-navy outline-none">
        Connexion requise
      </h1>
      <p className="max-w-xs text-sm text-muted-ink">
        « {title} » est réservé aux clients connectés. Dans cette démonstration, connectez-vous avec un profil fictif.
      </p>
      <button type="button" onClick={() => openLogin(here)} className="flex h-12 w-full max-w-xs items-center justify-center gap-2 rounded-2xl bg-brand font-bold text-white hover:bg-brand-strong">
        <LogInIcon className="size-5" aria-hidden /> Connexion démo
      </button>
      <Link href="/" className="flex h-11 items-center gap-2 rounded-2xl px-4 text-sm font-bold text-navy hover:bg-white">
        <HouseIcon className="size-4" aria-hidden /> Retour à l&apos;accueil
      </Link>
    </div>
  )
}
