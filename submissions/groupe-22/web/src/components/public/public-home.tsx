import { useState } from "react"
import {
  AccessibilityIcon, ChevronRightIcon, HeadsetIcon, KeyRoundIcon, LockIcon, LogInIcon, MessageSquareWarningIcon, MicIcon, CalculatorIcon,
  SparklesIcon, UserPlusIcon,
} from "lucide-react"
import { openLogin } from "@/lib/auth"
import { askCompass, openCompass } from "@/lib/compass"
import { STATUS_LABEL, useDemarches } from "@/lib/demarches"
import { PUBLIC_SUGGESTIONS } from "@/lib/site"
import { DemoBadge, Panel, Section } from "@/components/bank/ui"
import { CompassMark } from "@/components/compass/compass-mark"
import { AccessibilitySettings } from "@/components/settings/accessibility"
import { Sheet } from "@/components/shell/sheet"
import { usePage } from "@/components/shell/use-page"

const ICONS = [CalculatorIcon, KeyRoundIcon, MessageSquareWarningIcon, HeadsetIcon, UserPlusIcon]

/** The visitor's home: Compass for public questions, and the Connexion démo. Nothing
 * of a customer here: no balance, no card, no operation (the server gives a visitor
 * none, and Compass has no tool to read them). */
export function PublicHome() {
  usePage("accueil")
  const requests = useDemarches((s) => s.demarches)
  const [a11yOpen, setA11yOpen] = useState(false)

  return (
    <div className="flex flex-col gap-6 pb-10">
      <div className="-mb-3 px-4 pt-3">
        <DemoBadge />
      </div>
      <header className="flex items-center gap-3 px-4">
        <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-brand text-white shadow-[0_10px_24px_-12px_rgba(6,36,153,0.8)]" aria-hidden>
          <CompassMark className="size-6" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-lg font-extrabold leading-tight tracking-tight text-navy">Compass</p>
          <p className="truncate text-[11px] font-bold uppercase tracking-wide text-muted-ink">Banque fictive</p>
        </div>
        <button type="button" onClick={() => openLogin()} className="flex h-11 shrink-0 items-center gap-1.5 rounded-full bg-navy px-4 text-sm font-bold text-white hover:bg-navy-2">
          <LogInIcon className="size-4" aria-hidden /> Connexion démo
        </button>
      </header>

      <section aria-labelledby="hero-title" className="relative mx-4 overflow-hidden rounded-[28px] bg-navy p-5 text-white shadow-[0_18px_30px_-16px_rgba(8,13,52,0.7)]">
        <svg aria-hidden className="absolute -right-16 -top-16 size-56 opacity-[0.07]" viewBox="0 0 200 200">
          <circle cx="100" cy="100" r="88" fill="none" stroke="white" strokeWidth="22" />
        </svg>
        <p className="relative text-[13px] font-semibold text-white/75">Vous avez une question bancaire ? Compass vous accompagne.</p>
        <h1 id="hero-title" className="relative mt-2 text-[28px] font-extrabold leading-[1.1] tracking-tight">
          Comment pouvons-nous vous aider ?
        </h1>
        <p className="relative mt-2 text-[15px] text-white/85">Posez votre question à Compass, votre assistant bancaire.</p>
        <div className="relative mt-4 flex items-center gap-2 rounded-full bg-white p-1.5 pl-4">
          <SparklesIcon className="size-5 shrink-0 text-brand" aria-hidden />
          <button type="button" onClick={() => openCompass("text")} className="h-11 min-w-0 flex-1 truncate text-left text-[15px] font-medium text-muted-ink" aria-label="Écrire à Compass">
            Écrivez votre question…
          </button>
          <button type="button" onClick={() => openCompass("voice")} aria-label="Parler à Compass (conversation vocale)" className="flex size-11 shrink-0 items-center justify-center rounded-full bg-brand text-white hover:bg-brand-strong">
            <MicIcon className="size-5" aria-hidden />
          </button>
        </div>
        <p className="relative mt-3 text-[11.5px] font-semibold text-white/65">À l&apos;écrit ou à la voix. Sans connexion : aucune donnée de compte.</p>
      </section>

      <Section title="Questions fréquentes">
        <ul className="flex flex-col gap-2">
          {PUBLIC_SUGGESTIONS.map((q, i) => {
            const Icon = ICONS[i] ?? SparklesIcon
            return (
              <li key={q}>
                <button
                  type="button"
                  onClick={() => askCompass(q)}
                  className="hc-outline flex min-h-14 w-full items-center gap-3 rounded-2xl bg-white p-3 text-left shadow-sm transition hover:shadow-md"
                >
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-brand-soft text-brand">
                    <Icon className="size-[18px]" aria-hidden />
                  </span>
                  <span className="flex-1 text-[14.5px] font-bold leading-snug text-navy">{q}</span>
                  <ChevronRightIcon className="size-5 shrink-0 text-muted-ink" aria-hidden />
                </button>
              </li>
            )
          })}
        </ul>
      </Section>

      <Section title="Parler à un conseiller">
        <Panel className="flex flex-col gap-3">
          <p className="text-sm text-navy">
            Compass prépare une demande avec le contexte de votre question. Vous la relisez, puis vous la confirmez ou l&apos;annulez.
          </p>
          <p className="rounded-2xl bg-surface p-3 text-xs font-semibold text-navy">
            Prototype : c&apos;est une demande de démonstration, enregistrée ici. Aucun conseiller réel ne vous contactera, et aucune coordonnée n&apos;est demandée.
          </p>
          <button type="button" onClick={() => askCompass("Je voudrais parler à un conseiller.")} className="flex h-12 items-center justify-center gap-2 rounded-2xl bg-brand font-bold text-white hover:bg-brand-strong">
            <HeadsetIcon className="size-5" aria-hidden /> Préparer une demande
          </button>
          {requests.length > 0 && (
            <div className="border-t border-line pt-3">
              <h3 className="mb-2 text-sm font-extrabold text-navy">Vos demandes de démonstration</h3>
              <ul className="flex flex-col gap-2">
                {requests.map((d) => (
                  <li key={d.reference} className="rounded-2xl bg-surface px-3 py-2">
                    <p className="flex items-baseline justify-between gap-2">
                      <span className="text-sm font-bold text-navy">{d.title}</span>
                      <span className="tabular shrink-0 text-xs font-extrabold text-navy">{d.reference}</span>
                    </p>
                    <p className="text-xs font-semibold text-ok">{STATUS_LABEL[d.status] ?? d.status}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Panel>
      </Section>

      <Section title="Vos comptes">
        <Panel className="flex flex-col gap-3">
          <p className="flex items-start gap-2 text-sm text-navy">
            <LockIcon className="mt-0.5 size-5 shrink-0 text-brand" aria-hidden />
            Solde, opérations, cartes, démarches : réservés aux clients connectés. Compass ne les lit qu&apos;après la connexion.
          </p>
          <button type="button" onClick={() => openLogin()} className="flex h-12 items-center justify-center gap-2 rounded-2xl bg-navy font-bold text-white hover:bg-navy-2">
            <LogInIcon className="size-5" aria-hidden /> Connexion démo
          </button>
          <p className="text-center text-[11.5px] text-muted-ink">Profils fictifs : n&apos;entrez jamais vos vrais identifiants.</p>
        </Panel>
      </Section>

      <Section>
        <button type="button" onClick={() => setA11yOpen(true)} className="hc-outline flex w-full items-center gap-3 rounded-3xl bg-white p-4 text-left shadow-sm">
          <AccessibilityIcon className="size-6 text-navy" aria-hidden />
          <span className="flex-1 text-sm font-bold text-navy">Accessibilité : taille du texte, contraste, explications simples</span>
          <ChevronRightIcon className="size-5 text-muted-ink" aria-hidden />
        </button>
      </Section>

      <footer className="px-6 text-center text-[11px] leading-relaxed text-muted-ink">
        Prototype de démonstration : banque fictive, données fictives, démarches simulées. Ce n&apos;est l&apos;application d&apos;aucune banque réelle. Pour répondre, Compass
        transmet vos messages et votre voix à OpenAI.
      </footer>

      <Sheet open={a11yOpen} onClose={() => setA11yOpen(false)} title="Accessibilité" description="Réglages gardés sur cet appareil.">
        <div className="flex flex-col divide-y divide-line">
          <AccessibilitySettings />
        </div>
      </Sheet>
    </div>
  )
}
