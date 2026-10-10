import { Castle, Church, Landmark, Microscope, Mountain, Palette, Rocket, Waves } from 'lucide-react'
import type { OptionSondage } from '../../api/types'

type Pictogramme = 'espace' | 'edifice-religieux' | 'chateau' | 'grotte' | 'eau' | 'art' | 'sciences' | 'monument'

const sansAccents = (texte: string) =>
  texte
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()

/** Le nom du lieu d'abord, puis son intérêt pédagogique : un pictogramme reconnaissable par des élèves. */
const REGLES: [RegExp, Pictogramme][] = [
  [/\b(espace|astronom|fusee|planet|etoile)/, 'espace'],
  [/\b(basilique|cathedrale|eglise|abbaye|cloitre|chapelle)\b/, 'edifice-religieux'],
  [/\b(chateau|cite|fort|forteresse|rempart|donjon|citadelle)\b/, 'chateau'],
  [/\b(grotte|gouffre|prehistoire|prehistorique|caverne)/, 'grotte'],
  [/\b(aquarium|ocean|mer|canal|riviere)\b/, 'eau'],
  [/\b(musee d'art|beaux-arts|peinture|art)\b/, 'art'],
  [/\b(sciences?|museum|nature|biodiversite)\b/, 'sciences'],
]

function pictogramme(option: OptionSondage): Pictogramme {
  for (const texte of [option.nom, option.interet_pedagogique]) {
    const t = sansAccents(texte)
    const regle = REGLES.find(([motif]) => motif.test(t))
    if (regle) return regle[1]
  }
  return 'monument'
}

/** Pictogramme lucide d'une destination (décoratif : le nom est toujours écrit à côté). */
export function IconeDestination({ option, className }: { option: OptionSondage; className: string }) {
  switch (pictogramme(option)) {
    case 'espace':
      return <Rocket className={className} aria-hidden="true" />
    case 'edifice-religieux':
      return <Church className={className} aria-hidden="true" />
    case 'chateau':
      return <Castle className={className} aria-hidden="true" />
    case 'grotte':
      return <Mountain className={className} aria-hidden="true" />
    case 'eau':
      return <Waves className={className} aria-hidden="true" />
    case 'art':
      return <Palette className={className} aria-hidden="true" />
    case 'sciences':
      return <Microscope className={className} aria-hidden="true" />
    case 'monument':
      return <Landmark className={className} aria-hidden="true" />
  }
}
