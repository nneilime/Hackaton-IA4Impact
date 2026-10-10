import { CreditCardIcon, HouseIcon, UserIcon, WalletIcon } from "lucide-react"
import { openCompass } from "@/lib/compass"
import { Link, useLocation } from "@/lib/router"
import { useCompass } from "@/lib/store"
import { cn } from "@/lib/utils"
import { CompassMark } from "@/components/compass/compass-mark"

const ITEMS = [
  { href: "/", label: "Accueil", icon: HouseIcon, match: (p: string) => p === "/" },
  { href: "/comptes", label: "Comptes", icon: WalletIcon, match: (p: string) => p.startsWith("/comptes") || p.startsWith("/operations") },
  null,
  { href: "/cartes", label: "Cartes", icon: CreditCardIcon, match: (p: string) => p.startsWith("/cartes") },
  { href: "/profil", label: "Profil", icon: UserIcon, match: (p: string) => p.startsWith("/profil") },
]

export function BottomNav() {
  const { pathname } = useLocation()
  const sheet = useCompass((s) => s.sheet)
  return (
    <nav id="bottom-nav" aria-label="Navigation principale" className="relative z-30 shrink-0 border-t border-line bg-white/95 pb-[max(env(safe-area-inset-bottom),8px)] backdrop-blur lg:pb-5">
      <ul className="grid grid-cols-5 items-end px-2 pt-1.5">
        {ITEMS.map((item, i) =>
          item ? (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={item.match(pathname) ? "page" : undefined}
                className={cn(
                  "flex min-h-12 flex-col items-center justify-center gap-0.5 rounded-xl text-[11px] font-semibold transition-colors",
                  item.match(pathname) ? "text-brand" : "text-muted-ink hover:text-navy",
                )}
              >
                <item.icon className="size-[22px]" strokeWidth={item.match(pathname) ? 2.4 : 1.9} aria-hidden />
                {item.label}
              </Link>
            </li>
          ) : (
            <li key={`compass-${i}`} className="flex justify-center">
              <button
                type="button"
                onClick={() => (sheet === "open" ? useCompass.getState().setSheet("peek") : openCompass())}
                aria-label="Ouvrir Compass, votre assistant bancaire"
                aria-expanded={sheet === "open"}
                className="-mt-6 flex flex-col items-center gap-0.5 text-[11px] font-bold text-navy"
              >
                <span className="flex size-14 items-center justify-center rounded-full bg-brand text-white shadow-[0_8px_20px_-6px_rgba(6,36,153,0.55)] ring-4 ring-white transition-transform active:scale-95">
                  <CompassMark className="size-7" />
                </span>
                Compass
              </button>
            </li>
          ),
        )}
      </ul>
    </nav>
  )
}
