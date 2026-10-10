import {
  Bone,
  Castle,
  CalendarDays,
  Check,
  ChartColumn,
  Clock,
  Database,
  Euro,
  Heart,
  Landmark,
  Leaf,
  Lightbulb,
  MapPin,
  Orbit,
  Palette,
  QrCode,
  Search,
  ShieldCheck,
  Sparkles,
  TrainFront,
  Undo2,
  Users,
  X,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { BadgeSource, IconeScene } from '../../api/types'

/** Jeu fermé d'icônes des cartes-réponses : clé du back -> icône lucide-react. */
export const ICONES_CARTE: Record<IconeScene, LucideIcon> = {
  chateau: Castle,
  os: Bone,
  colonnes: Landmark,
  planete: Orbit,
  feuille: Leaf,
  palette: Palette,
  ampoule: Lightbulb,
  pin: MapPin,
  etincelles: Sparkles,
  train: TrainFront,
  qr: QrCode,
  coeur: Heart,
  oui: Check,
  non: X,
  retour: Undo2,
  loupe: Search,
  calendrier: CalendarDays,
  groupe: Users,
}

/** Icônes des badges de source. */
export const ICONES_BADGE: Record<BadgeSource['icone'], LucideIcon> = {
  chart: ChartColumn,
  database: Database,
  shield: ShieldCheck,
  train: TrainFront,
  pin: MapPin,
  euro: Euro,
  users: Users,
  clock: Clock,
}

/** Nom lisible de la source d'une donnée (jamais la couleur seule). */
export const LIBELLES_SOURCE: Record<BadgeSource['source'], string> = {
  sncf: 'SNCF',
  datatourisme: 'DATAtourisme',
  catalogue: 'Catalogue',
  calcul: 'Calcul',
  demo: 'Données de démo',
}
