import { useState } from "react"
import { BanIcon, EyeOffIcon, GaugeIcon, GlobeIcon, KeyRoundIcon, LoaderCircleIcon, LockIcon, NfcIcon, ShieldAlertIcon, SparklesIcon, UnlockIcon } from "lucide-react"
import { api, ApiError } from "@/lib/api"
import { askCompass } from "@/lib/compass"
import { refreshCustomer, useCustomer } from "@/lib/customer"
import { formatEUR } from "@/lib/format"
import { Link, navigate, useLocation } from "@/lib/router"
import { cn } from "@/lib/utils"
import { BankCardVisual, CardStatusPill } from "@/components/bank/bank-card"
import { LoadError, Panel, ScreenHeader, Section, SkeletonRows } from "@/components/bank/ui"
import { usePage } from "@/components/shell/use-page"
import { useHighlight } from "@/components/shell/highlight"
import { Sheet } from "@/components/shell/sheet"
import { toast } from "@/components/shell/toast"
import type { Card } from "@/lib/types"

/** Lock or unlock a card here, after a yes on screen: the server changes it
 * (POST /api/cards/<id>/lock|unlock), and Compass reads the same status. */
function LockDialog({ card, onClose }: { card: Card | null; onClose: () => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const unlock = card?.status === "LOCKED"
  async function confirm() {
    if (!card || busy) return
    setBusy(true)
    setError(null)
    try {
      await api(`/api/cards/${encodeURIComponent(card.id)}/${unlock ? "unlock" : "lock"}`, { method: "POST", body: {} })
      refreshCustomer()
      toast(unlock ? "Carte déverrouillée" : "Carte verrouillée")
      onClose()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "L'action n'a pas abouti. Réessayez.")
      refreshCustomer() // its status may have changed meanwhile
    } finally {
      setBusy(false)
    }
  }
  return (
    <Sheet
      open={!!card}
      onClose={() => {
        setError(null)
        onClose()
      }}
      title={unlock ? "Déverrouiller la carte ?" : "Verrouiller la carte ?"}
      description={card ? `${card.label} •••• ${card.maskedNumber}` : undefined}
    >
      <div className="flex flex-col gap-3">
        <p className="text-sm text-navy">
          {unlock
            ? "Elle fonctionnera de nouveau tout de suite : paiements et retraits."
            : "Temporaire : paiements et retraits seront refusés jusqu'à ce que vous la déverrouilliez. Ce n'est pas une opposition : si elle est perdue pour de bon ou volée, faites opposition avec Compass."}
        </p>
        {error && (
          <p role="alert" className="rounded-2xl bg-brand-soft p-3 text-sm font-semibold text-brand">
            {error}
          </p>
        )}
        <div className="grid grid-cols-2 gap-2">
          <button type="button" onClick={onClose} className="h-12 rounded-2xl font-bold text-navy ring-1 ring-line hover:bg-surface">
            Annuler
          </button>
          <button type="button" data-autofocus onClick={confirm} disabled={busy} aria-busy={busy} className="flex h-12 items-center justify-center gap-2 rounded-2xl bg-navy font-bold text-white hover:bg-navy-2 disabled:opacity-60">
            {busy ? <LoaderCircleIcon className="size-5 animate-spin" aria-hidden /> : unlock ? <UnlockIcon className="size-5" aria-hidden /> : <LockIcon className="size-5" aria-hidden />}
            {unlock ? "Déverrouiller" : "Verrouiller"}
          </button>
        </div>
      </div>
    </Sheet>
  )
}

// What can be done on a card: a temporary lock here, with a yes on screen; an opposition
// or a new code through Compass, which asks for the customer's yes, by voice or in
// writing. The server does both, on this session's cards only.
export function CardsScreen() {
  usePage("cartes")
  const { params } = useLocation()
  const { data, error, retry, opposition } = useCustomer()
  const statusHl = useHighlight("card-status")
  const securityHl = useHighlight("card-security")
  const [locking, setLocking] = useState<Card | null>(null)

  if (!data)
    return (
      <>
        <ScreenHeader title="Mes cartes" />
        {error ? (
          <LoadError retry={retry} />
        ) : (
          <div className="px-4">
            <div className="skeleton aspect-[1.586/1] rounded-[22px]" />
            <SkeletonRows n={3} />
          </div>
        )}
      </>
    )

  const cards = data.cards
  const card = cards.find((c) => c.id === params.get("card")) ?? cards.find((c) => c.kind === "PHYSICAL") ?? cards[0]
  const opposed = card.status === "OPPOSED"
  const locked = card.status === "LOCKED"
  const used = Math.min(100, (card.spentThisPeriodCents / card.paymentLimitCents) * 100)

  return (
    <div className="pb-8">
      <ScreenHeader title="Mes cartes" />
      <div className="no-scrollbar flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-2" role="tablist" aria-label="Choisir une carte">
        {cards.map((c) => (
          <button
            key={c.id}
            role="tab"
            aria-selected={c.id === card.id}
            onClick={() => navigate(`/cartes?card=${c.id}`, { replace: true })}
            className={cn("w-[86%] shrink-0 snap-center transition-opacity", c.id !== card.id && "opacity-55")}
          >
            <BankCardVisual card={c} />
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-5 pt-3">
        <Section>
          <div {...statusHl} className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-extrabold text-navy">{card.label}</p>
                <p className="tabular text-xs text-muted-ink">
                  •••• {card.maskedNumber} · expire {card.expiry}
                </p>
              </div>
              <CardStatusPill status={card.status} />
            </div>
            {opposed && opposition && (
              <Panel className="flex flex-col gap-2 bg-brand-soft shadow-none" role="status">
                <p className="flex items-center gap-2 text-sm font-extrabold text-brand">
                  <BanIcon className="size-5" aria-hidden /> Opposition enregistrée
                </p>
                <p className="flex items-baseline justify-between gap-2 text-sm text-navy">
                  <span className="text-xs font-bold uppercase tracking-wide text-muted-ink">Référence</span>
                  <span className="tabular font-extrabold">{opposition.reference}</span>
                </p>
                <p className="text-xs text-navy">{opposition.detail}</p>
                <Link href={`/demarches?ref=${encodeURIComponent(opposition.reference)}`} className="text-xs font-bold text-brand">
                  Voir dans mes démarches
                </Link>
              </Panel>
            )}
            {locked && (
              <Panel className="flex flex-col gap-1 bg-info-soft shadow-none" role="status">
                <p className="flex items-center gap-2 text-sm font-extrabold text-navy">
                  <LockIcon className="size-5" aria-hidden /> Carte verrouillée temporairement
                </p>
                <p className="text-xs text-navy">Paiements et retraits sont refusés. Vous pouvez la déverrouiller à tout moment.</p>
              </Panel>
            )}
            {!opposed && (
              <button
                type="button"
                onClick={() => setLocking(card)}
                className="hc-outline flex min-h-14 w-full items-center gap-3 rounded-2xl bg-white px-4 text-left shadow-sm ring-1 ring-line hover:bg-surface"
              >
                {locked ? <UnlockIcon className="size-5 text-navy" aria-hidden /> : <LockIcon className="size-5 text-navy" aria-hidden />}
                <span className="flex-1">
                  <span className="block text-sm font-extrabold text-navy">{locked ? "Déverrouiller la carte" : "Verrouiller temporairement"}</span>
                  <span className="block text-xs text-muted-ink">{locked ? "Elle fonctionnera de nouveau tout de suite" : "Carte égarée ? Vous pourrez la déverrouiller"}</span>
                </span>
              </button>
            )}
          </div>
        </Section>

        {!opposed && card.kind === "PHYSICAL" && (
          <Section>
            <button
              type="button"
              onClick={() => askCompass("J'ai perdu ma carte bancaire")}
              className="hc-outline flex w-full items-center gap-4 rounded-3xl bg-white p-4 text-left text-navy shadow-sm transition hover:bg-white/80"
            >
              <span className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-brand-soft text-brand">
                <ShieldAlertIcon className="size-6" aria-hidden />
              </span>
              <span className="flex-1">
                <span className="block font-extrabold">Carte perdue ou volée ?</span>
                <span className="block text-xs text-muted-ink">Compass fait opposition pour vous, avec votre accord, 24 h/24.</span>
              </span>
            </button>
          </Section>
        )}

        <Section title="Plafonds">
          <Panel className="flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <GaugeIcon className="size-5 text-navy" aria-hidden />
              <div className="flex-1">
                <div className="flex justify-between text-sm">
                  <span className="font-bold text-navy">Paiements · 30 jours</span>
                  <span className="tabular font-bold text-navy">{formatEUR(card.paymentLimitCents)}</span>
                </div>
                <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-surface" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(used)} aria-label="Plafond de paiement utilisé">
                  <div className="h-full rounded-full bg-brand" style={{ width: `${used}%` }} />
                </div>
                <p className="tabular mt-1 text-xs text-muted-ink">
                  {formatEUR(card.spentThisPeriodCents)} utilisés · {formatEUR(Math.max(0, card.paymentLimitCents - card.spentThisPeriodCents))} disponibles
                </p>
              </div>
            </div>
            {card.withdrawalLimitCents > 0 && (
              <p className="flex justify-between border-t border-line pt-3 text-sm">
                <span className="font-bold text-navy">Retraits · 7 jours</span>
                <span className="tabular font-bold text-navy">{formatEUR(card.withdrawalLimitCents)}</span>
              </p>
            )}
            <button type="button" onClick={() => askCompass("J'ai une question sur le plafond de ma carte")} disabled={opposed} className="h-11 rounded-2xl bg-surface text-sm font-bold text-navy hover:bg-line disabled:opacity-50">
              Une question sur mon plafond ? Compass
            </button>
          </Panel>
        </Section>

        <Section title="Options">
          <Panel className="flex flex-col divide-y divide-line py-1">
            {[
              { icon: GlobeIcon, label: "Paiement à distance", value: card.onlinePayments },
              { icon: NfcIcon, label: "Sans contact", value: card.contactless },
            ].map((o) => (
              <p key={o.label} className="flex min-h-14 items-center gap-3">
                <o.icon className="size-5 text-navy" aria-hidden />
                <span className="flex-1 text-sm font-bold text-navy">{o.label}</span>
                <span className={cn("rounded-full px-2.5 py-1 text-xs font-bold", o.value && card.status === "ACTIVE" ? "bg-ok-soft text-ok" : "bg-surface text-muted-ink")}>
                  {o.value && card.status === "ACTIVE" ? "Activé" : "Désactivé"}
                </span>
              </p>
            ))}
          </Panel>
        </Section>

        <Section title="Sécurité">
          <Panel {...securityHl} className="flex flex-col gap-1 p-2">
            <button type="button" onClick={() => askCompass("J'ai oublié le code de ma carte")} className="flex min-h-14 items-center gap-3 rounded-2xl px-2 text-left hover:bg-surface">
              <KeyRoundIcon className="size-5 text-brand" aria-hidden />
              <span className="flex-1">
                <span className="block text-sm font-bold text-navy">Code oublié</span>
                <span className="block text-xs text-muted-ink">Compass le fait renvoyer par courrier, en braille ou en gros caractères si vous voulez</span>
              </span>
            </button>
            <div className="flex min-h-14 items-center gap-3 px-2">
              <EyeOffIcon className="size-5 text-muted-ink" aria-hidden />
              <span className="flex-1">
                <span className="block text-sm font-bold text-navy">Code secret et cryptogramme</span>
                <span className="block text-xs text-muted-ink">Jamais affichés, et jamais demandés par Compass</span>
              </span>
            </div>
            <button type="button" onClick={() => askCompass("J'ai une question sur la sécurité de ma carte")} className="flex min-h-14 items-center gap-3 rounded-2xl px-2 text-left hover:bg-surface">
              <SparklesIcon className="size-5 text-brand" aria-hidden />
              <span className="flex-1 text-sm font-bold text-navy">Une question ? Demander à Compass</span>
            </button>
          </Panel>
        </Section>
      </div>
      <LockDialog card={locking} onClose={() => setLocking(null)} />
    </div>
  )
}
