import type { BadgeSource } from '../../api/types'
import { ICONES_BADGE, LIBELLES_SOURCE } from './iconesScene'

interface BadgesSourceProps {
  badges: BadgeSource[]
}

/** La donnée utilisée pour la réplique : icône + chiffre + source en petit. La démo se reconnaît au pointillé ET au texte. */
export default function BadgesSource({ badges }: BadgesSourceProps) {
  if (badges.length === 0) return null
  return (
    <ul className="mt-3 flex flex-wrap gap-2" aria-label="Données utilisées pour cette réponse">
      {badges.map((badge, i) => {
        const Icone = ICONES_BADGE[badge.icone]
        const demo = badge.source === 'demo'
        return (
          <li
            key={`${badge.texte}-${i}`}
            className={
              demo
                ? 'badge badge-outline h-auto min-h-7 gap-1.5 border-dashed py-1 motion-safe:animate-entree'
                : 'badge badge-soft h-auto min-h-7 gap-1.5 py-1 motion-safe:animate-entree'
            }
          >
            <Icone className="size-4 shrink-0" aria-hidden="true" />
            <span className="text-sm font-bold tabular-nums">{badge.texte}</span>
            <span className="border-l border-current/40 pl-1.5 text-xs font-semibold opacity-80">
              {LIBELLES_SOURCE[badge.source]}
            </span>
          </li>
        )
      })}
    </ul>
  )
}
