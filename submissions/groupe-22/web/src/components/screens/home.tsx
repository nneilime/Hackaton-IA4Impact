import { useState } from "react"
import {
  AccessibilityIcon, BellIcon, CalculatorIcon, ChevronRightIcon, ClipboardListIcon, CreditCardIcon, ListIcon, MessageSquareWarningIcon, MicIcon,
  PiggyBankIcon, ShieldCheckIcon, SparklesIcon,
} from "lucide-react"
import { askCompass, openCompass } from "@/lib/compass"
import { useCustomer } from "@/lib/customer"
import { useDemarches } from "@/lib/demarches"
import { formatEUR, formatSignedEUR, formatShortDate } from "@/lib/format"
import { Link, navigate } from "@/lib/router"
import { TOPICS } from "@/lib/site"
import { useCompass } from "@/lib/store"
import { BankCardVisual, CardStatusPill } from "@/components/bank/bank-card"
import { DemoBadge, LoadError, Panel, Section, SkeletonRows, TxRow } from "@/components/bank/ui"
import { usePage } from "@/components/shell/use-page"
import { useHighlight } from "@/components/shell/highlight"
import { Sheet } from "@/components/shell/sheet"

const TOPIC_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  code_perdu: CreditCardIcon,
  credit: CalculatorIcon,
  reclamation: MessageSquareWarningIcon,
  gestion_privee: PiggyBankIcon,
}

// Profil opens on its accessibility settings, highlighted.
const showAccessibility = () => setTimeout(() => useCompass.getState().setHighlight("accessibility"), 350)

function CompassBar() {
  return (
    <div className="mx-4 flex items-center gap-2 rounded-full bg-white p-1.5 pl-4 shadow-[0_6px_24px_-10px_rgba(8,13,52,0.35)] ring-1 ring-line">
      <SparklesIcon className="size-5 shrink-0 text-brand" aria-hidden />
      <button
        type="button"
        onClick={() => openCompass("text")}
        className="h-11 flex-1 text-left text-[15px] font-medium text-muted-ink"
        aria-label="Écrire à Compass, votre assistant bancaire"
      >
        Que puis-je faire pour vous ?
      </button>
      <button
        type="button"
        onClick={() => openCompass("voice")}
        aria-label="Parler à Compass (conversation vocale)"
        className="flex size-11 items-center justify-center rounded-full bg-navy text-white transition hover:bg-navy-2"
      >
        <MicIcon className="size-5" />
      </button>
    </div>
  )
}

function Greeting({ name, initials, onBell, unread }: { name: string; initials: string; onBell: () => void; unread: boolean }) {
  const today = new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" })
  return (
    <div className="flex items-center gap-3 px-4 pb-4 pt-4">
      <Link href="/profil" aria-label="Mon profil" className="flex size-11 shrink-0 items-center justify-center rounded-full bg-navy text-sm font-extrabold text-white">
        {initials}
      </Link>
      <div className="min-w-0 flex-1">
        <h1 className="text-[22px] font-extrabold leading-tight tracking-tight text-navy">Bonjour {name}</h1>
        <p className="text-xs font-medium capitalize text-muted-ink">{today}</p>
      </div>
      <button type="button" onClick={onBell} aria-label={`Notifications${unread ? " (nouvelles)" : ""}`} className="relative flex size-11 items-center justify-center rounded-full bg-white text-navy ring-1 ring-line">
        <BellIcon className="size-5" />
        {unread && <span className="absolute right-2.5 top-2.5 size-2.5 rounded-full bg-brand ring-2 ring-white" aria-hidden />}
      </button>
    </div>
  )
}

export function HomeScreen() {
  usePage("accueil")
  const { data, error, retry } = useCustomer()
  const demarches = useDemarches((s) => s.demarches)
  const [notifOpen, setNotifOpen] = useState(false)
  const balanceHl = useHighlight<HTMLAnchorElement>("balance")

  if (!data) return error ? <LoadError retry={retry} /> : <div className="p-4"><SkeletonRows n={6} /></div>

  const main = data.accounts.find((a) => a.type === "COMPTE_COURANT")
  const savings = data.accounts.filter((a) => a.type !== "COMPTE_COURANT")
  const physical = data.cards.find((c) => c.kind === "PHYSICAL")
  const recent = data.transactions.slice(0, 4)
  const unknown = data.transactions.find((t) => t.id === "tx_inconnu")

  const actions = [
    { icon: ListIcon, label: "Mes opérations", href: "/operations" },
    { icon: CreditCardIcon, label: "Mes cartes", href: "/cartes" },
    { icon: ClipboardListIcon, label: "Mes démarches", href: "/demarches", count: demarches.length },
    { icon: AccessibilityIcon, label: "Accessibilité", href: "/profil", onClick: showAccessibility },
  ]

  return (
    <div className="flex flex-col gap-5 pb-8">
      <div className="px-4 pt-3">
        <DemoBadge />
      </div>
      <Greeting name={data.customer.firstName} initials={data.customer.initials} onBell={() => setNotifOpen(true)} unread={!!unknown} />
      <CompassBar />

      <Section title="Mes comptes" action={<Link href="/comptes" className="text-sm font-bold text-brand">Tout voir</Link>}>
        <div className="flex flex-col gap-3">
          {main && (
            <Link href={`/comptes?account=${main.id}`} {...balanceHl} className="relative block overflow-hidden rounded-3xl bg-navy p-5 text-white shadow-[0_18px_30px_-16px_rgba(8,13,52,0.7)]">
              <svg aria-hidden className="absolute -right-16 -top-16 size-56 opacity-[0.07]" viewBox="0 0 200 200">
                <circle cx="100" cy="100" r="88" fill="none" stroke="white" strokeWidth="22" />
              </svg>
              <p className="text-sm font-semibold opacity-80">{main.label}</p>
              <p className="tabular mt-1 text-[34px] font-extrabold leading-none tracking-tight">{formatEUR(main.balanceCents)}</p>
              <div className="mt-4 flex items-center justify-between text-xs font-medium opacity-75">
                <span>Solde disponible</span>
                <span className="tabular">{main.maskedIban}</span>
              </div>
            </Link>
          )}
          {savings.map((s) => (
            <Link key={s.id} href={`/comptes?account=${s.id}`} className="hc-outline flex items-center justify-between rounded-3xl bg-white p-4 shadow-sm">
              <div>
                <p className="text-sm font-bold text-navy">{s.label}</p>
                <p className="tabular text-xs text-muted-ink">{s.maskedIban}</p>
              </div>
              <p className="tabular text-lg font-extrabold text-navy">{formatEUR(s.balanceCents)}</p>
            </Link>
          ))}
        </div>
      </Section>

      <Section aria-label="Actions rapides">
        <ul className="grid grid-cols-4 gap-2">
          {actions.map((a) => (
            <li key={a.label}>
              <Link href={a.href} onClick={a.onClick} className="flex flex-col items-center gap-1.5 rounded-2xl p-1 text-center">
                <span className="relative flex size-14 items-center justify-center rounded-2xl bg-white text-brand shadow-sm ring-1 ring-line">
                  <a.icon className="size-6" aria-hidden />
                  {!!a.count && (
                    <span className="absolute -right-1.5 -top-1.5 flex min-w-5 items-center justify-center rounded-full bg-brand px-1 text-[11px] font-extrabold text-white ring-2 ring-surface">
                      <span className="sr-only">(</span>
                      {a.count}
                      <span className="sr-only">)</span>
                    </span>
                  )}
                </span>
                <span className="text-[11.5px] font-bold leading-tight text-navy">{a.label}</span>
              </Link>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Vos démarches avec Compass">
        <div className="grid grid-cols-2 gap-3">
          {TOPICS.map((t) => {
            const Icon = TOPIC_ICONS[t.id] ?? SparklesIcon
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => askCompass(t.question)}
                className="hc-outline flex min-h-28 flex-col items-start justify-between gap-3 rounded-3xl bg-white p-4 text-left shadow-sm transition hover:shadow-md"
              >
                <Icon className="size-6 text-brand" aria-hidden />
                <span>
                  <span className="block text-sm font-bold leading-tight text-navy">{t.title}</span>
                  <span className="mt-1 block text-[11.5px] leading-snug text-muted-ink">{t.text}</span>
                </span>
              </button>
            )
          })}
        </div>
      </Section>

      {physical && (
        <Section title="Ma carte" action={<Link href="/cartes" className="text-sm font-bold text-brand">Gérer</Link>}>
          <Link href="/cartes" className="hc-outline flex items-center gap-4 rounded-3xl bg-white p-3 shadow-sm">
            <div className="w-28 shrink-0">
              <BankCardVisual card={physical} compact />
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-bold text-navy">{physical.label}</p>
              <p className="tabular mb-1.5 text-xs text-muted-ink">•••• {physical.maskedNumber}</p>
              <CardStatusPill status={physical.status} />
            </div>
          </Link>
        </Section>
      )}

      <Section title="Dernières opérations" action={<Link href="/operations" className="text-sm font-bold text-brand">Tout voir</Link>}>
        <Panel className="p-2">
          {recent.map((t) => (
            <TxRow key={t.id} tx={t} onClick={() => navigate(`/operations?tx=${t.id}`)} />
          ))}
        </Panel>
      </Section>

      <Section>
        <Link href="/profil" onClick={showAccessibility} className="hc-outline flex items-center gap-3 rounded-3xl bg-white p-4 shadow-sm">
          <AccessibilityIcon className="size-6 text-navy" aria-hidden />
          <span className="flex-1 text-sm font-bold text-navy">Accessibilité : taille du texte, contraste, voix de Compass</span>
          <ChevronRightIcon className="size-5 text-muted-ink" aria-hidden />
        </Link>
      </Section>

      <Sheet open={notifOpen} onClose={() => setNotifOpen(false)} title="Notifications">
        <ul className="flex flex-col gap-2">
          {unknown && (
            <li>
              <button
                type="button"
                onClick={() => {
                  setNotifOpen(false)
                  navigate(`/operations?tx=${unknown.id}`)
                }}
                className="flex w-full items-start gap-3 rounded-2xl bg-surface p-3 text-left"
              >
                <ShieldCheckIcon className="mt-0.5 size-5 shrink-0 text-brand" aria-hidden />
                <span>
                  <span className="block text-sm font-bold text-navy">Paiement à distance de {formatSignedEUR(unknown.amountCents)}</span>
                  <span className="block text-xs text-muted-ink">
                    {formatShortDate(unknown.timestamp)} · {unknown.label}. Vous ne le reconnaissez pas ? Touchez pour vérifier.
                  </span>
                </span>
              </button>
            </li>
          )}
          <li className="flex items-start gap-3 rounded-2xl p-3">
            <SparklesIcon className="mt-0.5 size-5 shrink-0 text-navy" aria-hidden />
            <span>
              <span className="block text-sm font-bold text-navy">Nouveau : Compass</span>
              <span className="block text-xs text-muted-ink">Dites ce dont vous avez besoin, à la voix ou par écrit : Compass s&apos;occupe du reste.</span>
            </span>
          </li>
        </ul>
      </Sheet>
    </div>
  )
}
