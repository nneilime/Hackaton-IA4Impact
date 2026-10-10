import { useEffect } from "react"
import { CloudOffIcon } from "lucide-react"
import { AuthRequired } from "@/components/auth/auth-required"
import { PublicHome } from "@/components/public/public-home"
import { AppShell } from "@/components/shell/app-shell"
import { AccountsScreen } from "@/components/screens/accounts"
import { CardsScreen } from "@/components/screens/cards"
import { DemarchesScreen } from "@/components/screens/demarches"
import { HomeScreen } from "@/components/screens/home"
import { OperationsScreen } from "@/components/screens/operations"
import { ProfileScreen } from "@/components/screens/profile"
import { loadSession, useAuth, watchSession } from "@/lib/auth"
import { refreshDemarches } from "@/lib/demarches"
import { useLocation } from "@/lib/router"

// The bank's screens: only for a logged-in demo customer.
const SCREENS: Record<string, { title: string; screen: () => React.ReactNode }> = {
  "/": { title: "Accueil", screen: HomeScreen },
  "/comptes": { title: "Mes comptes", screen: AccountsScreen },
  "/operations": { title: "Opérations", screen: OperationsScreen },
  "/cartes": { title: "Mes cartes", screen: CardsScreen },
  "/demarches": { title: "Mes démarches", screen: DemarchesScreen },
  "/profil": { title: "Profil", screen: ProfileScreen },
}

function Splash() {
  // Until the server says who this is: nothing private, nothing public yet.
  return (
    <div className="flex h-full items-center justify-center" aria-busy="true" aria-label="Chargement">
      <span className="size-10 animate-spin rounded-full border-4 border-line border-t-brand" />
    </div>
  )
}

function Offline() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 px-8 text-center" role="alert">
      <CloudOffIcon className="size-10 text-muted-ink" aria-hidden />
      <p className="text-sm text-navy">Le serveur de démonstration est injoignable. Vérifiez votre connexion, puis réessayez.</p>
      <button type="button" onClick={() => void loadSession()} className="h-11 rounded-2xl bg-navy px-5 text-sm font-bold text-white">
        Réessayer
      </button>
    </div>
  )
}

export default function App() {
  const { pathname } = useLocation()
  const status = useAuth((s) => s.status)
  const path = pathname.replace(/\/+$/, "") || "/"
  const route = SCREENS[path]

  useEffect(() => {
    // The session first: /api/me gives a visitor their cookie.
    void loadSession().then(refreshDemarches)
    watchSession()
  }, [])

  const title = status === "customer" ? (route ?? SCREENS["/"]).title : status === "visitor" && route && path !== "/" ? "Connexion requise" : "Assistant bancaire"
  useEffect(() => {
    document.title = `${title} · Compass (démo)`
  }, [title])

  let page: React.ReactNode
  if (status === "loading") page = <Splash />
  else if (status === "offline") page = <Offline />
  else if (status === "visitor") page = route && path !== "/" ? <AuthRequired title={route.title} /> : <PublicHome />
  else {
    const Screen = (route ?? SCREENS["/"]).screen
    page = <Screen />
  }
  return <AppShell>{page}</AppShell>
}
