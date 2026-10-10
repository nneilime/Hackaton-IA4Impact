import { useEffect, useRef, useState } from "react"
import { CalendarIcon, CheckIcon, ClipboardListIcon, CopyIcon, MessageSquareTextIcon, SparklesIcon, Trash2Icon } from "lucide-react"
import { askCompass } from "@/lib/compass"
import { clearDemarches, refreshDemarches, STATUS_LABEL, useDemarches } from "@/lib/demarches"
import { useLocation } from "@/lib/router"
import type { Demarche } from "@/lib/types"
import { cn } from "@/lib/utils"
import { DEMARCHE_ICONS, RecapButton } from "@/components/compass/cards"
import { Panel, ScreenHeader, Section, SkeletonRows } from "@/components/bank/ui"
import { toast } from "@/components/shell/toast"
import { usePage } from "@/components/shell/use-page"

function when(at: number): string {
  const time = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" }).format(at)
  const today = new Date().toDateString() === new Date(at).toDateString()
  return today ? `Aujourd'hui à ${time}` : `${new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long" }).format(at)} à ${time}`
}

const MODE: Record<string, string> = { voice: "à la voix", text: "par écrit", app: "dans l'application" }

function DemarcheItem({ demarche, highlighted }: { demarche: Demarche; highlighted: boolean }) {
  const [copied, setCopied] = useState(false)
  const ref = useRef<HTMLLIElement>(null)
  const Icon = DEMARCHE_ICONS[demarche.kind] ?? ClipboardListIcon

  useEffect(() => {
    if (highlighted) ref.current?.scrollIntoView({ block: "center" })
  }, [highlighted])

  async function copy() {
    try {
      await navigator.clipboard.writeText(demarche.reference)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* no clipboard (HTTP, or refused): the number stays on screen */
    }
  }

  return (
    <li ref={ref} data-highlighted={highlighted ? "true" : undefined} className="hc-outline flex flex-col gap-3 rounded-3xl bg-white p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-ok-soft text-ok">
          <Icon className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="font-extrabold leading-tight text-navy">{demarche.title}</h2>
          <p className="text-xs text-muted-ink">
            {when(demarche.at)} · {MODE[demarche.mode] ?? demarche.mode}
          </p>
          <p className="mt-0.5 text-xs font-bold text-ok">{STATUS_LABEL[demarche.status] ?? demarche.status}</p>
        </div>
      </div>
      <p className="flex items-baseline justify-between gap-2 rounded-2xl bg-surface px-3 py-2">
        <span className="text-[11px] font-bold uppercase tracking-wide text-muted-ink">Référence</span>
        <span className="tabular text-base font-extrabold tracking-wide text-navy">{demarche.reference}</span>
      </p>
      <p className="text-sm text-navy">{demarche.detail}</p>
      <div className={cn("grid gap-2", demarche.pdf && "grid-cols-2")}>
        <button type="button" onClick={copy} className="flex min-h-11 items-center justify-center gap-2 rounded-xl text-sm font-bold text-navy ring-1 ring-line hover:bg-surface">
          {copied ? <CheckIcon className="size-4" aria-hidden /> : <CopyIcon className="size-4" aria-hidden />}
          {copied ? "Copiée" : "Copier la référence"}
        </button>
        {demarche.pdf && <RecapButton pdf={demarche.pdf} />}
      </div>
    </li>
  )
}

export function DemarchesScreen() {
  usePage("demarches")
  const { params } = useLocation()
  const demarches = useDemarches((s) => s.demarches)
  const loaded = useDemarches((s) => s.loaded)
  const [confirming, setConfirming] = useState(false)
  const highlighted = params.get("ref")

  useEffect(() => {
    void refreshDemarches()
  }, [])

  return (
    <div className="pb-10">
      <ScreenHeader title="Mes démarches" back="/" />
      <div className="flex flex-col gap-5">
        <Section>
          <Panel className="flex flex-col gap-3">
            <p className="text-sm text-navy">
              Expliquez votre situation à Compass : il fait la démarche avec vous, ou vous passe à un conseiller qui a tout le contexte. Vous n&apos;avez rien à répéter.
            </p>
            <button
              type="button"
              onClick={() => askCompass("Je voudrais parler à un conseiller.")}
              className="flex h-12 items-center justify-center gap-2 rounded-2xl bg-brand font-bold text-white hover:bg-brand-strong"
            >
              <SparklesIcon className="size-5" aria-hidden /> Parler à un conseiller avec Compass
            </button>
          </Panel>
        </Section>

        <Section title="Ce que Compass a fait pour vous">
          {!loaded ? (
            <Panel>
              <SkeletonRows n={2} />
            </Panel>
          ) : demarches.length === 0 ? (
            <Panel className="flex flex-col items-center gap-2 py-8 text-center">
              <ClipboardListIcon className="size-8 text-muted-ink" aria-hidden />
              <p className="font-extrabold text-navy">Aucune démarche pour l&apos;instant</p>
              <p className="text-sm text-muted-ink">Une opposition, une simulation de crédit transmise, une réclamation : vous les retrouverez ici, avec leur numéro de référence.</p>
            </Panel>
          ) : (
            <>
              <ul className="flex flex-col gap-3">
                {demarches.map((d) => (
                  <DemarcheItem key={d.reference} demarche={d} highlighted={d.reference === highlighted} />
                ))}
              </ul>
              <p className="mt-3 text-xs text-muted-ink">Démarches simulées : elles restent le temps de votre session de démonstration. La déconnexion les efface.</p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                {confirming ? (
                  <>
                    <span className="text-sm font-semibold text-navy">Tout effacer de cet appareil ?</span>
                    <button
                      type="button"
                      onClick={async () => {
                        try {
                          await clearDemarches()
                        } catch {
                          toast("Les démarches n'ont pas pu être effacées. Réessayez.", "error")
                        }
                        setConfirming(false)
                      }}
                      className="h-10 rounded-xl bg-brand px-3 text-sm font-bold text-white"
                    >
                      Oui, tout effacer
                    </button>
                    <button type="button" onClick={() => setConfirming(false)} className="h-10 rounded-xl px-3 text-sm font-bold text-navy hover:bg-white">
                      Annuler
                    </button>
                  </>
                ) : (
                  <button type="button" onClick={() => setConfirming(true)} className="flex h-10 items-center gap-1.5 rounded-xl px-3 text-sm font-bold text-navy hover:bg-white">
                    <Trash2Icon className="size-4" aria-hidden /> Tout effacer
                  </button>
                )}
              </div>
            </>
          )}
        </Section>

        <Section title="Autres moyens de contact">
          <Panel className="flex flex-col divide-y divide-line py-1 text-sm">
            <div className="flex min-h-14 items-center gap-3 opacity-70">
              <MessageSquareTextIcon className="size-5 text-navy" aria-hidden />
              <span className="flex-1">
                <span className="block font-bold text-navy">Messagerie sécurisée</span>
                <span className="block text-xs text-muted-ink">Non simulée dans ce prototype</span>
              </span>
            </div>
            <button type="button" onClick={() => askCompass("Je voudrais prendre rendez-vous avec un conseiller.")} className="flex min-h-14 items-center gap-3 text-left">
              <CalendarIcon className="size-5 text-brand" aria-hidden />
              <span className="flex-1">
                <span className="block font-bold text-navy">Rendez-vous avec un conseiller</span>
                <span className="block text-xs text-muted-ink">Compass le prépare, vous confirmez (simulation)</span>
              </span>
            </button>
          </Panel>
        </Section>
      </div>
    </div>
  )
}
