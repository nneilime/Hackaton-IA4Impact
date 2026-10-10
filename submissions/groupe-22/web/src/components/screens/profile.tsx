import { useState } from "react"
import { EarIcon, KeyboardIcon, LoaderCircleIcon, LockIcon, LogOutIcon, MicIcon, ShieldCheckIcon, Trash2Icon, Volume2Icon } from "lucide-react"
import { logout } from "@/lib/auth"
import { closeChat } from "@/lib/chat"
import { useCustomer } from "@/lib/customer"
import { clearDemarches } from "@/lib/demarches"
import { savePrefs, usePrefs, type Preferences } from "@/lib/prefs"
import { cn } from "@/lib/utils"
import { voiceActive } from "@/lib/voice"
import { Panel, ScreenHeader, Section } from "@/components/bank/ui"
import { Switch } from "@/components/ui/switch"
import { toast } from "@/components/shell/toast"
import { usePage } from "@/components/shell/use-page"
import { useHighlight } from "@/components/shell/highlight"
import { AccessibilitySettings, SettingRow as Row } from "@/components/settings/accessibility"

function Choice<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: { value: T; label: string; icon?: React.ComponentType<{ className?: string }> }[]; onChange: (v: T) => void }) {
  return (
    <div className="py-3">
      <p className="mb-2 text-sm font-bold text-navy">{label}</p>
      <div role="radiogroup" aria-label={label} className="grid grid-cols-2 gap-2">
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={value === o.value}
            onClick={() => onChange(o.value)}
            className={cn("flex h-12 items-center justify-center gap-2 rounded-xl text-sm font-extrabold", value === o.value ? "bg-navy text-white" : "bg-surface text-navy")}
          >
            {o.icon && <o.icon className="size-4" aria-hidden />}
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}

export function ProfileScreen() {
  usePage("profil")
  const { data } = useCustomer()
  const prefs = usePrefs()
  const a11yHl = useHighlight("accessibility")
  const [leaving, setLeaving] = useState(false)
  const set = (change: Partial<Preferences>, message?: string) => {
    savePrefs(change)
    if (message) toast(message)
  }

  return (
    <div className="pb-10">
      <ScreenHeader title="Profil et paramètres" />
      <div className="flex flex-col gap-5">
        <Section>
          <Panel className="flex items-center gap-4">
            <span className="flex size-14 items-center justify-center rounded-full bg-navy text-lg font-extrabold text-white">{data?.customer.initials ?? "…"}</span>
            <div className="flex-1">
              <p className="text-lg font-extrabold text-navy">{data?.customer.displayName ?? "…"}</p>
              <p className="text-xs text-muted-ink">Session de démonstration · profil fictif</p>
            </div>
          </Panel>
          <button
            type="button"
            disabled={leaving}
            onClick={async () => {
              setLeaving(true)
              await logout()
            }}
            className="mt-3 flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-white font-bold text-brand ring-1 ring-line hover:bg-brand-soft disabled:opacity-60"
          >
            {leaving ? <LoaderCircleIcon className="size-5 animate-spin" aria-hidden /> : <LogOutIcon className="size-5" aria-hidden />}
            Se déconnecter
          </button>
        </Section>

        <Section title="Accessibilité">
          <Panel {...a11yHl} className="flex flex-col divide-y divide-line py-1">
            <AccessibilitySettings />
          </Panel>
        </Section>

        <Section title="Compass">
          <Panel className="flex flex-col divide-y divide-line py-1">
            <Choice
              label="Le bouton Compass ouvre"
              value={prefs.mode}
              options={[
                { value: "text", label: "L'écrit", icon: KeyboardIcon },
                { value: "voice", label: "La voix", icon: MicIcon },
              ]}
              onChange={(mode) => set({ mode })}
            />
            <Row icon={Volume2Icon} label="Voix de Compass" hint="Conversation vocale en temps réel (OpenAI Realtime), à partir du prochain appel">
              <select
                value={prefs.voice}
                onChange={(e) => set({ voice: e.target.value as Preferences["voice"] })}
                aria-label="Voix de Compass"
                className="h-10 rounded-xl bg-surface px-3 text-sm font-bold text-navy"
              >
                <option value="marin">Marin</option>
                <option value="cedar">Cedar</option>
              </select>
            </Row>
            <Row icon={EarIcon} label="Pièce bruyante" hint="À la voix, je touche « Parler », je pose ma question, puis « Envoyer ». À partir du prochain appel.">
              <Switch checked={prefs.pushToTalk} onCheckedChange={(v) => set({ pushToTalk: v }, v ? "Pièce bruyante activée" : "Pièce bruyante désactivée")} aria-label="Pièce bruyante" />
            </Row>
          </Panel>
        </Section>

        <Section title="Nos engagements">
          <Panel className="flex flex-col gap-2.5 text-sm text-navy">
            {[
              "À la voix, Compass ne parle jamais de ce qui est affiché : tout se fait sans regarder l'écran.",
              "Vous pouvez lui couper la parole en parlant, en touchant l'orbe, ou avec la touche Échap sur un clavier.",
              "Par écrit, les réponses sont lues par votre lecteur d'écran une fois écrites, en entier.",
              "Il répète chaque nombre que vous lui donnez, et lit les numéros de référence par groupes de chiffres.",
              "Les récapitulatifs PDF sont balisés (PDF/UA) : titres et tableaux lus dans l'ordre.",
            ].map((text) => (
              <p key={text} className="flex items-start gap-2">
                <ShieldCheckIcon className="mt-0.5 size-4 shrink-0 text-ok" aria-hidden />
                {text}
              </p>
            ))}
          </Panel>
        </Section>

        <Section title="Sécurité">
          <Panel className="flex flex-col gap-2 text-sm text-navy">
            <p className="flex items-start gap-2">
              <LockIcon className="mt-0.5 size-5 shrink-0 text-navy" aria-hidden />
              Compass ne vous demandera jamais votre code secret, votre mot de passe ou un code reçu par SMS. Une opposition se fait toujours après votre oui.
            </p>
          </Panel>
        </Section>

        <Section title="Confidentialité">
          <Panel className="flex flex-col gap-3 text-sm text-navy">
            <p>
              Pour répondre, Compass transmet vos messages et votre voix à OpenAI (Realtime) ; les numéros de carte ou de téléphone écrits par erreur sont masqués avant. Les récapitulatifs PDF,
              avec vos réponses, restent 24 heures sur le serveur, pour vous seul·e. Vos démarches restent le temps de la session : la déconnexion les efface.
            </p>
            <p className="text-xs text-muted-ink">Prototype : données fictives. Aucune conformité réglementaire n&apos;est revendiquée.</p>
            <button
              type="button"
              onClick={async () => {
                closeChat(voiceActive())
                try {
                  await clearDemarches()
                  toast("Conversation et démarches effacées.")
                } catch {
                  toast("Les démarches n'ont pas pu être effacées. Réessayez.", "error")
                }
              }}
              className="flex h-11 items-center justify-center gap-2 rounded-2xl bg-surface font-bold text-navy hover:bg-line"
            >
              <Trash2Icon className="size-4" aria-hidden /> Effacer ma conversation et mes démarches
            </button>
          </Panel>
        </Section>
      </div>
    </div>
  )
}
