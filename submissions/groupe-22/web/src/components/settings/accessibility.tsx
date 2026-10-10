import { AccessibilityIcon, BookOpenTextIcon } from "lucide-react"
import { setChatSimple } from "@/lib/chat"
import { savePrefs, usePrefs } from "@/lib/prefs"
import { cn } from "@/lib/utils"
import { Switch } from "@/components/ui/switch"

/** Remembered on this device, for visitors and customers alike (public home, Profil). */
export function setSimple(simple: boolean) {
  savePrefs({ simple })
  setChatSimple(simple) // the written conversation in progress; a call: from the next one
}

export function SettingRow({ icon: Icon, label, hint, children }: { icon?: React.ComponentType<{ className?: string }>; label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="flex min-h-14 items-center gap-3 py-2">
      {Icon && <Icon className="size-5 shrink-0 text-navy" aria-hidden />}
      <div className="min-w-0 flex-1">
        <p className="text-sm font-bold text-navy">{label}</p>
        {hint && <p className="text-xs text-muted-ink">{hint}</p>}
      </div>
      {children}
    </div>
  )
}

/** Text size, contrast, motion, and Compass's simple explanations. */
export function AccessibilitySettings() {
  const prefs = usePrefs()
  return (
    <>
      <div className="py-3">
        <p id="ts-label" className="mb-2 text-sm font-bold text-navy">
          Taille du texte
        </p>
        <div role="radiogroup" aria-labelledby="ts-label" className="grid grid-cols-3 gap-2">
          {([1, 1.15, 1.3] as const).map((s) => (
            <button
              key={s}
              type="button"
              role="radio"
              aria-checked={prefs.textScale === s}
              onClick={() => savePrefs({ textScale: s })}
              className={cn("h-12 rounded-xl font-extrabold", prefs.textScale === s ? "bg-navy text-white" : "bg-surface text-navy")}
              style={{ fontSize: `${14 * s}px` }}
            >
              {s === 1 ? "A" : s === 1.15 ? "A+" : "A++"}
              <span className="sr-only">{` ${Math.round(s * 100)} %`}</span>
            </button>
          ))}
        </div>
      </div>
      <SettingRow icon={AccessibilityIcon} label="Contraste élevé" hint="Textes et contours plus marqués">
        <Switch checked={prefs.highContrast} onCheckedChange={(v) => savePrefs({ highContrast: v })} aria-label="Contraste élevé" />
      </SettingRow>
      <SettingRow label="Réduire les animations" hint="Respecte aussi le réglage de votre appareil">
        <Switch checked={prefs.reducedMotion} onCheckedChange={(v) => savePrefs({ reducedMotion: v })} aria-label="Réduire les animations" />
      </SettingRow>
      <SettingRow icon={BookOpenTextIcon} label="Explications simples" hint="Compass répond en phrases courtes, avec des mots de tous les jours">
        <Switch checked={prefs.simple} onCheckedChange={setSimple} aria-label="Explications simples" />
      </SettingRow>
    </>
  )
}
