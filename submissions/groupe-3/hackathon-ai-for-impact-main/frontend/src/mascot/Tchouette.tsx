import { useId, type ReactNode } from 'react'
import { Attr, Transfo } from './animation'
import { useMouvementReduit } from './useMouvementReduit'

// Tchouette : tchou-tchou + chouette. La face avant d'un petit train régional
// est le visage d'une chouette. Style « Memphis » : aplats, contours épais
// bleu nuit, ombre portée dure décalée. Animations en SMIL uniquement, jamais
// émises si l'utilisateur demande à réduire les animations.

export type HumeurTchouette = 'repos' | 'reflexion' | 'parle' | 'joie' | 'inquiete' | 'salue' | 'pointe' | 'loupe' | 'celebre'

export interface TchouetteProps {
  /** Expression et animation de la mascotte. */
  humeur?: HumeurTchouette
  /** Largeur en pixels ; la hauteur suit le ratio du dessin (carré). */
  taille?: number
  /** Texte alternatif. Vide pour une mascotte purement décorative. */
  titre?: string
  className?: string
}

/* ---------- Palette de marque (fixe : un asset de marque ne suit pas le thème) ---------- */

const ROUGE = '#C8102E'
const ROUGE_FONCE = '#A00D24'
const NUIT = '#0B2341'
const NUIT_PROFONDE = '#071629'
const OR = '#FFCD00'
const BLANC = '#FFFFFF'
const BRUME = '#F4F5F7'

/* ---------- Géométrie (dessin centré sur x = 100) ---------- */

/** Cadre carré : marge pour le liseré, l'ombre décalée, les sauts et les ailes levées. */
const VIEWBOX = '-4 -10 214 214'
const CONTOUR = 6
const LISERE = CONTOUR + 8
const DECALAGE_OMBRE = 6
/** Symétrie gauche ↔ droite autour de l'axe x = 100. */
const MIROIR = 'matrix(-1 0 0 1 200 0)'

/** Cabine en dôme, presque un œuf ; le bas est caché par le châssis. */
const CORPS = 'M34 142 V102 C34 58 62 30 100 30 C138 30 166 58 166 102 V142 Q166 148 160 148 H40 Q34 148 34 142 Z'
/** Aigrette gauche en triangle, plume intérieure en zigzag façon pantographe (la droite est en miroir). */
const AIGRETTE = 'M56 62 L40 6 L94 38 Z'
const AIGRETTE_PLUME = 'M58 50 L47 19 L60 30 L64 22 L84 37 Z'
/** Volet latéral gauche (aile), avec deux lames d'aération comme des plumes. */
const AILE = 'M44 108 C30 110 21 122 21 141 Q21 148 28 148 H44 Z'
const AILE_LAMES = 'M29 127 H39 M27 137 H39'
const PIVOT_AILE = '44 110'
const ANGLE_AILE_LEVEE = 20
/** Coucou (`salue`) : l'aile gauche monte au-dessus de la tête puis s'agite. */
const ANGLE_SALUT = 122
const CYCLE_SALUT = 3.2
const PARE_BRISE = 'M76 40 H124 Q130 40 132.5 45 L137 54 Q139.5 59.5 133 59.5 H67 Q60.5 59.5 63 54 L67.5 45 Q70 40 76 40 Z'
const REFLET = 'M121 43.5 H127 L121.5 56 H115.5 Z'
const CHASSIS = { x: 40, y: 144, width: 120, height: 14, rx: 6 }
const ROUES = [70, 130] as const
const Y_ROUE = 166
const R_ROUE = 15
const YEUX = [70, 130] as const
const Y_YEUX = 102
const R_PHARE = 23
const R_BLANC = 15
const BEC = 'M88 118 H112 L100 136 Z'
const MACHOIRE = 'M94 127 L106 127 L100 137 Z'
const BOUCHE_FERMEE = 'M96 123 L104 123 L102 129 L100 131 L98 129 Z'
const BOUCHE_OUVERTE = 'M89 120 L111 120 L109 139 L100 146 L91 139 Z'
const SOURCIL = 'M52 81 L84 70'
const BOUCHE_ENTROUVERTE = 'M91 120 L109 120 L108 134 L100 142 L92 134 Z'

/** `pointe` : l'aile droite, rallongée, s'étend vers la droite et le bas, puis tape deux fois. */
const ANGLE_POINTE = 52
const ANGLE_POINTE_RECUL = 42
const ALLONGE_AILE = 'translate(44 110) scale(1 1.2) translate(-44 -110)'
const CYCLE_POINTE = 1.9
/** `celebre` : ailes levées au-dessus de la tête, qui battent. */
const ANGLE_AILES_HAUTES = [138, 162] as const
const CYCLE_SAUT = 0.9
/** Sol sous les roues : point fixe de l'écrasement du saut. */
const Y_SOL = 181
/** Cadrage réduit : laisse la place au saut, aux confettis, à la loupe et à son afficheur. */
const CADRAGE: Partial<Record<HumeurTchouette, string>> = {
  celebre: 'translate(14 30) scale(0.86)',
  loupe: 'translate(-4 24) scale(0.72)',
  pointe: 'translate(-8 12) scale(0.9)',
}
/** `loupe` : le balayage dure 4,4 s (lent vers la droite, pause, retour plus vif). */
const CYCLE_LOUPE = 4.4
const TEMPS_LOUPE = [0, 0.62, 0.7, 1]

interface Pose {
  /** Décalage des pupilles depuis le centre de l'œil. */
  regard: [number, number]
  rayonPupille: number
}

/** Inclinaison du corps (réflexion : penchée ; pointe : se tourne vers ce qu'elle montre). */
const ROTATION: Partial<Record<HumeurTchouette, string>> = {
  reflexion: 'rotate(-5 100 170)',
  pointe: 'rotate(3 100 170)',
}

const OUVERTURE: Record<HumeurTchouette, Ouverture> = {
  repos: 'ferme',
  reflexion: 'ferme',
  parle: 'parle',
  joie: 'ferme',
  inquiete: 'ferme',
  salue: 'ferme',
  pointe: 'entrouvert',
  loupe: 'ferme',
  celebre: 'grande',
}

const POSES: Record<HumeurTchouette, Pose> = {
  repos: { regard: [0, 1.5], rayonPupille: 8.5 },
  reflexion: { regard: [-4.5, -5], rayonPupille: 8 },
  parle: { regard: [0, 0.5], rayonPupille: 8.5 },
  joie: { regard: [0, 0], rayonPupille: 8.5 },
  inquiete: { regard: [0, 1], rayonPupille: 5 },
  salue: { regard: [0, 0], rayonPupille: 8.5 },
  pointe: { regard: [6, 2], rayonPupille: 8.5 },
  loupe: { regard: [3, 3], rayonPupille: 8 },
  celebre: { regard: [0, 0], rayonPupille: 8.5 },
}

/** Position des ailes : au repos, levées de joie, ou une seule levée pour saluer. */
type PoseAiles = 'repos' | 'levees' | 'salut' | 'hautes' | 'pointe' | 'sans-droite'

function poseAiles(humeur: HumeurTchouette): PoseAiles {
  switch (humeur) {
    case 'joie':
      return 'levees'
    case 'salue':
      return 'salut'
    case 'celebre':
      return 'hautes'
    case 'pointe':
      return 'pointe'
    case 'loupe':
      // Le bras de la loupe (dessiné à part) remplace l'aile droite.
      return 'sans-droite'
    default:
      return 'repos'
  }
}

/* ---------- Pièces ---------- */

/**
 * Paire d'ailes : la gauche telle quelle, la droite en miroir.
 * `levees` : les deux ailes battent ensemble. `salut` : seule l'aile gauche
 * monte, fait coucou deux ou trois fois, redescend, puis marque une pause.
 */
function Ailes({ pose, anime, children }: { pose: PoseAiles; anime: boolean; children: ReactNode }) {
  const haut = `${ANGLE_AILE_LEVEE} ${PIVOT_AILE}`
  const angle = (a: number) => `${a} ${PIVOT_AILE}`
  const [bas, sommet] = ANGLE_AILES_HAUTES
  let gauche: ReactNode
  let droite: ReactNode = <g>{children}</g>
  if (pose === 'salut') {
    gauche = (
      <g transform={`rotate(${angle(ANGLE_SALUT)})`}>
        {anime && (
          <Transfo
            type="rotate"
            valeurs={[angle(0), angle(ANGLE_SALUT), angle(100), angle(138), angle(100), angle(138), angle(108), angle(0), angle(0)]}
            temps={[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.75, 1]}
            duree={CYCLE_SALUT}
          />
        )}
        {children}
      </g>
    )
  } else if (pose === 'hautes') {
    // Les deux ailes battent ensemble, bien au-dessus des épaules.
    gauche = (
      <g transform={`rotate(${angle((bas + sommet) / 2)})`}>
        {anime && <Transfo type="rotate" valeurs={[angle(bas), angle(sommet), angle(bas)]} duree={0.36} />}
        {children}
      </g>
    )
    droite = gauche
  } else if (pose === 'levees') {
    gauche = (
      <g transform={`rotate(${haut})`}>
        {anime && <Transfo type="rotate" valeurs={[haut, `-2 ${PIVOT_AILE}`, haut]} duree={0.45} />}
        {children}
      </g>
    )
    droite = gauche
  } else {
    gauche = <g>{children}</g>
    if (pose === 'pointe') {
      // Aile droite tendue et rallongée ; deux petits coups vers l'avant, puis une pause bras tendu.
      const tendu = angle(ANGLE_POINTE)
      const recul = angle(ANGLE_POINTE_RECUL)
      droite = (
        <g transform={`rotate(${tendu})`}>
          {anime && (
            <Transfo
              type="rotate"
              valeurs={[tendu, recul, tendu, recul, tendu, tendu]}
              temps={[0, 0.09, 0.18, 0.27, 0.36, 1]}
              duree={CYCLE_POINTE}
            />
          )}
          <g transform={ALLONGE_AILE}>{children}</g>
        </g>
      )
    } else if (pose === 'sans-droite') {
      droite = null
    }
  }
  return (
    <>
      {gauche}
      <g transform={MIROIR}>{droite}</g>
    </>
  )
}

/** Silhouette pleine d'une seule couleur : ombre portée et liseré d'autocollant. */
function Silhouette(props: { couleur: string; epaisseur: number; pose: PoseAiles; anime: boolean; roues: boolean }) {
  const { couleur, epaisseur, pose, anime, roues } = props
  return (
    <g fill={couleur} stroke={couleur} strokeWidth={epaisseur} strokeLinejoin="round">
      {[undefined, MIROIR].map((t) => (
        <g key={t ?? 'gauche'} transform={t}>
          <path d={AIGRETTE} />
        </g>
      ))}
      <Ailes pose={pose} anime={anime}>
        <path d={AILE} />
      </Ailes>
      <path d={CORPS} />
      {roues && (
        <>
          <rect {...CHASSIS} />
          {ROUES.map((x) => (
            <circle key={x} cx={x} cy={Y_ROUE} r={R_ROUE} />
          ))}
        </>
      )}
    </g>
  )
}

function Oeil({ cx, humeur, anime }: { cx: number; humeur: HumeurTchouette; anime: boolean }) {
  const { regard, rayonPupille } = POSES[humeur]
  const cligne = anime && (humeur === 'repos' || humeur === 'parle')
  return (
    <g transform={`translate(${cx} ${Y_YEUX})`}>
      <circle r={R_PHARE} fill={OR} stroke={NUIT} strokeWidth={5} />
      {humeur === 'joie' || humeur === 'salue' || humeur === 'celebre' ? (
        <>
          <circle r={R_BLANC} fill={BLANC} stroke={NUIT} strokeWidth={2.5} />
          <path d="M-9 5 Q0 -12 9 5" fill="none" stroke={NUIT} strokeWidth={6} strokeLinecap="round" />
        </>
      ) : (
        <>
          {/* Paupière, visible seulement pendant le clignement. */}
          <circle r={R_BLANC} fill={ROUGE_FONCE} />
          <g>
            {cligne && (
              <Transfo
                type="scale"
                valeurs={['1 1', '1 1', '1 0.08', '1 1']}
                temps={[0, 0.92, 0.96, 1]}
                duree={humeur === 'parle' ? 3.1 : 4.2}
                rythme="lineaire"
              />
            )}
            <circle r={R_BLANC} fill={BLANC} stroke={NUIT} strokeWidth={2.5} />
            <g transform={`translate(${regard[0]} ${regard[1]})`}>
              {humeur === 'loupe' && anime && (
                // Les yeux suivent la loupe : même durée, mêmes instants.
                <Transfo type="translate" valeurs={['-6 3', '7 3', '7 3', '-6 3']} temps={TEMPS_LOUPE} duree={CYCLE_LOUPE} />
              )}
              <circle r={rayonPupille} fill={NUIT} />
              <circle cx={-rayonPupille * 0.35} cy={-rayonPupille * 0.4} r={rayonPupille * 0.38} fill={BLANC} />
            </g>
          </g>
        </>
      )}
    </g>
  )
}

type Ouverture = 'ferme' | 'entrouvert' | 'parle' | 'grande'

/** Bec-nez du train. En `parle`, la mandibule descend et dévoile la bouche ; `entrouvert` et `grande` restent fixes. */
function Bec({ ouverture, anime }: { ouverture: Ouverture; anime: boolean }) {
  const ouvert = ouverture !== 'ferme'
  const bouche = ouverture === 'entrouvert' ? BOUCHE_ENTROUVERTE : BOUCHE_OUVERTE
  const decalage = ouverture === 'entrouvert' ? 6 : 10
  const parle = ouverture === 'parle'
  return (
    <g stroke={NUIT} strokeWidth={4} strokeLinejoin="round">
      {ouvert ? (
        <>
          <path d={bouche} fill={NUIT_PROFONDE}>
            {anime && parle && <Attr nom="d" valeurs={[BOUCHE_OUVERTE, BOUCHE_FERMEE, BOUCHE_OUVERTE]} duree={0.34} />}
          </path>
          <path d={MACHOIRE} fill={OR} transform={`translate(0 ${decalage})`}>
            {anime && parle && <Transfo type="translate" valeurs={['0 10', '0 0', '0 10']} duree={0.34} />}
          </path>
        </>
      ) : (
        <path d={MACHOIRE} fill={OR} />
      )}
      <path d={BEC} fill={OR} />
    </g>
  )
}

/**
 * Afficheur de destination. `sequence` : trois points or qui s'allument tour à tour (elle réfléchit) ;
 * `clignote` : les trois points clignotent ensemble (elle lit des données).
 */
function Afficheur({ mode, anime }: { mode: 'repos' | 'sequence' | 'clignote'; anime: boolean }) {
  return (
    <g>
      <rect x={82} y={43} width={36} height={12} rx={4} fill={NUIT_PROFONDE} />
      {[91, 100, 109].map((x, i) => (
        <circle key={x} cx={x} cy={49} r={3.2} fill={OR}>
          {mode === 'sequence' && anime && (
            <Attr nom="opacity" valeurs={[0.2, 1, 0.2, 0.2]} temps={[0, 0.2, 0.45, 1]} duree={1.35} debut={i * 0.27} />
          )}
          {mode === 'clignote' && anime && (
            <Attr nom="opacity" valeurs={[1, 1, 0.15, 0.15]} temps={[0, 0.45, 0.5, 0.95]} duree={0.7} rythme="discret" />
          )}
        </circle>
      ))}
    </g>
  )
}

function Roue({ cx, tourne }: { cx: number; tourne: boolean }) {
  return (
    <g transform={`translate(${cx} ${Y_ROUE})`}>
      <g>
        {tourne && <Transfo type="rotate" valeurs={[0, 360]} duree={0.9} rythme="lineaire" />}
        <circle r={R_ROUE} fill={OR} stroke={NUIT} strokeWidth={5} />
        <path d="M-9 0 H9 M0 -9 V9" stroke={NUIT} strokeWidth={3.5} strokeLinecap="round" />
        <circle r={5} fill={NUIT} />
      </g>
    </g>
  )
}

/** Étincelle or à quatre branches. */
function Etincelle({ x, y, rayon, debut, anime }: { x: number; y: number; rayon: number; debut: number; anime: boolean }) {
  const r = rayon
  const p = rayon * 0.28
  return (
    <g transform={`translate(${x} ${y})`}>
      <g>
        {anime && <Transfo type="scale" valeurs={[1, 0.5, 1]} duree={0.9} debut={debut} />}
        <path
          d={`M0 ${-r} L${p} ${-p} L${r} 0 L${p} ${p} L0 ${r} L${-p} ${p} L${-r} 0 L${-p} ${-p} Z`}
          fill={OR}
          stroke={NUIT}
          strokeWidth={3}
          strokeLinejoin="round"
        />
      </g>
    </g>
  )
}

/** Goutte de sueur de l'inquiétude. */
function Goutte({ anime }: { anime: boolean }) {
  return (
    <g transform="translate(174 58)">
      <g>
        {anime && (
          <>
            <Transfo type="translate" valeurs={['0 0', '0 0', '0 10']} temps={[0, 0.35, 1]} duree={1.8} rythme="lineaire" />
            <Attr nom="opacity" valeurs={[1, 1, 0]} temps={[0, 0.6, 1]} duree={1.8} rythme="lineaire" />
          </>
        )}
        <path
          d="M0 -10 C4 -4 7 0 7 4 A7 7 0 0 1 -7 4 C-7 0 -4 -4 0 -10 Z"
          fill={BRUME}
          stroke={NUIT}
          strokeWidth={3}
          strokeLinejoin="round"
        />
      </g>
    </g>
  )
}

/** Mouvement d'ensemble propre à chaque humeur. */
function MouvementGlobal({ humeur }: { humeur: HumeurTchouette }) {
  switch (humeur) {
    case 'repos':
      return <Transfo type="translate" valeurs={['0 0', '0 -3', '0 0']} duree={3.2} />
    case 'reflexion':
      return <Transfo type="translate" valeurs={['0 0', '0 -2', '0 0']} duree={4} />
    case 'parle':
      return <Transfo type="translate" valeurs={['0 0', '0 -1.5', '0 0']} duree={0.68} />
    case 'joie':
      return <Transfo type="translate" valeurs={['0 0', '0 -6', '0 0']} duree={0.9} />
    case 'pointe':
      return <Transfo type="translate" valeurs={['0 0', '0 -2', '0 0']} duree={CYCLE_POINTE / 2} />
    case 'loupe':
      return <Transfo type="translate" valeurs={['0 0', '0 -1.5', '0 0']} duree={3} />
    case 'celebre':
      // Accroupie, décolle, culmine, retombe : le temps de contact au sol laisse place à l'écrasement.
      return <Transfo type="translate" valeurs={['0 0', '0 0', '0 -22', '0 0', '0 0']} temps={[0, 0.15, 0.5, 0.85, 1]} duree={CYCLE_SAUT} />
    case 'salue':
      // Petit rebond calé sur les coucous de l'aile (3,2 s / 5 ≈ un rebond par coucou).
      return <Transfo type="translate" valeurs={['0 0', '0 -2.5', '0 0']} duree={CYCLE_SALUT / 5} />
    case 'inquiete':
      return (
        <Transfo
          type="translate"
          valeurs={['0 0', '-1.6 0', '1.6 0', '-1.2 0', '1.2 0', '0 0', '0 0']}
          temps={[0, 0.07, 0.14, 0.21, 0.28, 0.35, 1]}
          duree={1.5}
          rythme="lineaire"
        />
      )
  }
}

/* ---------- Décors propres aux nouvelles humeurs ---------- */

/** Écrasement et étirement du saut, autour du point de contact avec le sol. */
function Ecrasement({ anime, children }: { anime: boolean; children: ReactNode }) {
  if (!anime) return <>{children}</>
  return (
    <g transform={`translate(100 ${Y_SOL})`}>
      <g>
        <Transfo
          type="scale"
          valeurs={['1.07 0.91', '0.95 1.06', '1 1', '0.96 1.05', '1.07 0.91']}
          temps={[0, 0.15, 0.5, 0.85, 1]}
          duree={CYCLE_SAUT}
        />
        <g transform={`translate(-100 -${Y_SOL})`}>{children}</g>
      </g>
    </g>
  )
}

type FormeConfetti = 'cercle' | 'triangle' | 'losange'

const FORMES_CONFETTI: Record<FormeConfetti, string> = {
  cercle: 'M-7 0 A7 7 0 1 0 7 0 A7 7 0 1 0 -7 0 Z',
  triangle: 'M0 -10.5 L10.5 7.5 L-10.5 7.5 Z',
  losange: 'M0 -11.5 L8 0 L0 11.5 L-8 0 Z',
}

/** Confettis : jaillissent du sommet de la tête, retombent sur les côtés, deux sont déjà en l'air à l'arrivée. */
const CONFETTIS: {
  forme: FormeConfetti
  couleur: string
  x: number
  bas: number
  duree: number
  decalage: number
  tours: number
}[] = [
  {
    forme: 'cercle',
    couleur: OR,
    x: 14,
    bas: 150,
    duree: 2.2,
    decalage: 0,
    tours: 1,
  },
  {
    forme: 'triangle',
    couleur: ROUGE,
    x: 188,
    bas: 140,
    duree: 2.4,
    decalage: 0.5,
    tours: -1,
  },
  {
    forme: 'losange',
    couleur: BLANC,
    x: 30,
    bas: 120,
    duree: 2,
    decalage: 1,
    tours: 1,
  },
  {
    forme: 'cercle',
    couleur: BLANC,
    x: 174,
    bas: 160,
    duree: 2.1,
    decalage: 1.3,
    tours: -1,
  },
  {
    forme: 'losange',
    couleur: OR,
    x: 200,
    bas: 105,
    duree: 2.3,
    decalage: 1.7,
    tours: 1,
  },
]
const ORIGINE_CONFETTIS = { x: 100, y: 30 }
const TEMPS_PIC = 0.28

/** Hauteur d'un confetti à l'instant t (0 → 1) : monte jusqu'à TEMPS_PIC, puis retombe en accélérant. */
function hauteurConfetti(t: number, bas: number): number {
  const chute = bas - ORIGINE_CONFETTIS.y
  const g = chute / (1 - 2 * TEMPS_PIC)
  const v = 2 * g * TEMPS_PIC
  return ORIGINE_CONFETTIS.y - v * t + g * t * t
}

const ECHANTILLONS = Array.from({ length: 11 }, (_, i) => i / 10)

function Confettis({ anime }: { anime: boolean }) {
  return (
    <g stroke={NUIT} strokeWidth={2.5} strokeLinejoin="round">
      {CONFETTIS.map(({ forme, couleur, x, bas, duree, decalage, tours }) => {
        const piece = <path d={FORMES_CONFETTI[forme]} fill={couleur} />
        if (!anime) {
          // Pose fixe : chacun suspendu en cours de chute.
          const t = 0.45 + decalage * 0.2
          const px = ORIGINE_CONFETTIS.x + (x - ORIGINE_CONFETTIS.x) * t
          return (
            <g key={`${forme}-${x}`} transform={`translate(${px} ${hauteurConfetti(t, bas)}) rotate(${decalage * 40})`}>
              {piece}
            </g>
          )
        }
        return (
          <g key={`${forme}-${x}`}>
            <g>
              <Transfo
                type="translate"
                valeurs={[`${ORIGINE_CONFETTIS.x} 0`, `${x} 0`]}
                duree={duree}
                debut={-decalage}
                rythme="lineaire"
              />
              <g>
                <Transfo
                  type="translate"
                  valeurs={ECHANTILLONS.map((t) => `0 ${hauteurConfetti(t, bas).toFixed(1)}`)}
                  duree={duree}
                  debut={-decalage}
                  rythme="lineaire"
                />
                <g>
                  <Attr nom="opacity" valeurs={[0, 1, 1, 0]} temps={[0, 0.04, 0.88, 1]} duree={duree} debut={-decalage} rythme="lineaire" />
                  <g>
                    <Transfo type="rotate" valeurs={[0, 360 * tours]} duree={duree * 0.7} debut={-decalage} rythme="lineaire" />
                    {piece}
                  </g>
                </g>
              </g>
            </g>
          </g>
        )
      })}
    </g>
  )
}

/* La loupe vit dans le cadre complet (hors cadrage réduit de la mascotte) : elle est dessinée DERRIÈRE
   la mascotte, qui cache l'attache du bras. Le bras est élastique, comme dans un dessin animé. */
const PANNEAU = { x: 142, y: 78, width: 56, height: 88 }
const LIGNES_DONNEES = [
  { y: 92, couleur: OR, longueur: 26 },
  { y: 106, couleur: ROUGE, longueur: 16 },
  { y: 120, couleur: NUIT, longueur: 28 },
  { y: 134, couleur: OR, longueur: 20 },
  { y: 148, couleur: ROUGE, longueur: 12 },
]
const EPAULE = { x: 112, y: 122 }
const LENTILLE_Y = 112
const LENTILLE_X = [162, 183] as const
const R_LENTILLE = 15
/** Le bout du bras est caché sous le manche, en bas à gauche de la lentille. */
const DECALAGE_MANCHE = { x: -19, y: 19 }

function Loupe({ anime }: { anime: boolean }) {
  const position = anime ? undefined : `${(LENTILLE_X[0] + LENTILLE_X[1]) / 2} ${LENTILLE_Y}`
  const [x0, x1] = LENTILLE_X
  const bras = (x: number) => `M${EPAULE.x} ${EPAULE.y} L${x + DECALAGE_MANCHE.x} ${LENTILLE_Y + DECALAGE_MANCHE.y}`
  const xs = [x0, x1, x1, x0]
  const brasD = anime ? undefined : bras((x0 + x1) / 2)
  return (
    <g strokeLinecap="round" strokeLinejoin="round">
      {/* Afficheur de données : ombre dure décalée, liseré blanc, corps clair. */}
      <rect
        x={PANNEAU.x + 5}
        y={PANNEAU.y + 5}
        width={PANNEAU.width}
        height={PANNEAU.height}
        rx={6}
        fill={NUIT}
        stroke={BLANC}
        strokeWidth={10}
      />
      <rect {...PANNEAU} rx={6} fill={BRUME} stroke={NUIT} strokeWidth={4} />
      {LIGNES_DONNEES.map(({ y, couleur, longueur }, i) => (
        <g key={y}>
          <rect x={PANNEAU.x + 8} y={y} width={7} height={7} rx={2} fill={couleur} stroke={NUIT} strokeWidth={2}>
            {anime && i === 1 && <Attr nom="opacity" valeurs={[1, 0.15, 1]} temps={[0, 0.5, 1]} duree={0.9} rythme="discret" />}
          </rect>
          <path d={`M${PANNEAU.x + 20} ${y + 3.5} h${longueur}`} stroke={NUIT} strokeWidth={4} />
        </g>
      ))}

      {/* Bras élastique : liseré blanc, contour bleu nuit, chair rouge foncé. */}
      {[
        { c: BLANC, l: 17 },
        { c: NUIT, l: 11 },
        { c: ROUGE_FONCE, l: 5.5 },
      ].map(({ c, l }) => (
        <path key={c} d={brasD ?? bras(x0)} fill="none" stroke={c} strokeWidth={l}>
          {anime && <Attr nom="d" valeurs={xs.map(bras)} temps={TEMPS_LOUPE} duree={CYCLE_LOUPE} />}
        </path>
      ))}

      {/* Loupe : manche, anneau or à contour bleu nuit, verre clair. */}
      <g transform={anime ? undefined : `translate(${position})`}>
        {anime && <Transfo type="translate" valeurs={xs.map((x) => `${x} ${LENTILLE_Y}`)} temps={TEMPS_LOUPE} duree={CYCLE_LOUPE} />}
        <path d="M-10 10 L-22 22" stroke={BLANC} strokeWidth={14} />
        <path d="M-10 10 L-22 22" stroke={NUIT} strokeWidth={9} />
        <circle r={R_LENTILLE} fill="none" stroke={BLANC} strokeWidth={13} />
        <circle r={R_LENTILLE} fill="none" stroke={NUIT} strokeWidth={9.5} />
        <circle r={R_LENTILLE} fill={BLANC} fillOpacity={0.2} stroke={OR} strokeWidth={5} />
        <path d="M-6 -3 Q-4 -7 0 -8" fill="none" stroke={BLANC} strokeWidth={2.5} />
      </g>
    </g>
  )
}

/* ---------- Composant ---------- */

export default function Tchouette({ humeur = 'repos', taille = 160, titre = 'Tchouette', className }: TchouetteProps) {
  const anime = !useMouvementReduit()
  // Identifiants SVG uniques par instance (plusieurs Tchouette par page).
  const id = useId().replace(/[^a-zA-Z0-9_-]/g, '')
  const idTitre = `tchouette-titre-${id}`
  const idCorps = `tchouette-corps-${id}`
  const decoratif = !titre
  const joie = humeur === 'joie'
  const silhouette = { pose: poseAiles(humeur), anime }

  return (
    <svg
      // `key` : changer d'humeur remonte tout le SVG, ce qui remet son horloge SMIL à zéro.
      // Chaque animation repart donc de son début (le coucou commence aile baissée).
      key={humeur}
      xmlns="http://www.w3.org/2000/svg"
      viewBox={VIEWBOX}
      width={taille}
      height={taille}
      className={className}
      data-humeur={humeur}
      role={decoratif ? undefined : 'img'}
      aria-hidden={decoratif ? true : undefined}
      aria-labelledby={decoratif ? undefined : idTitre}
      focusable="false"
    >
      {!decoratif && <title id={idTitre}>{titre}</title>}
      <defs>
        <clipPath id={idCorps}>
          <path d={CORPS} />
        </clipPath>
      </defs>

      {humeur === 'loupe' && <Loupe anime={anime} />}

      <g transform={CADRAGE[humeur]}>
        <g>
          {anime && <MouvementGlobal humeur={humeur} />}
          <Ecrasement anime={anime && humeur === 'celebre'}>
            <g transform={ROTATION[humeur]}>
              {/* Liseré blanc d'autocollant (lisible sur fond bleu nuit), puis ombre portée dure. */}
              <Silhouette couleur={BLANC} epaisseur={LISERE} roues {...silhouette} />
              <g transform={`translate(${DECALAGE_OMBRE} ${DECALAGE_OMBRE})`}>
                <Silhouette couleur={BLANC} epaisseur={LISERE} roues={false} {...silhouette} />
                <Silhouette couleur={NUIT} epaisseur={CONTOUR} roues={false} {...silhouette} />
              </g>

              {/* Aigrettes-pantographes */}
              {[undefined, MIROIR].map((t) => (
                <g key={t ?? 'gauche'} transform={t}>
                  <path d={AIGRETTE} fill={ROUGE} stroke={NUIT} strokeWidth={CONTOUR} strokeLinejoin="round" />
                  <path d={AIGRETTE_PLUME} fill={ROUGE_FONCE} />
                </g>
              ))}

              {/* Cabine : disque facial de chouette et bande de livrée, découpés au corps. */}
              <path d={CORPS} fill={ROUGE} />
              <g clipPath={`url(#${idCorps})`}>
                {YEUX.map((cx) => (
                  <circle key={cx} cx={cx} cy={Y_YEUX} r={30} fill={ROUGE_FONCE} />
                ))}
                <rect x={0} y={137} width={200} height={8} fill={BRUME} />
              </g>
              <path d={CORPS} fill="none" stroke={NUIT} strokeWidth={CONTOUR} strokeLinejoin="round" />

              {/* Volets latéraux = ailes */}
              <Ailes pose={poseAiles(humeur)} anime={anime}>
                <path d={AILE} fill={ROUGE_FONCE} stroke={NUIT} strokeWidth={CONTOUR} strokeLinejoin="round" />
                <path d={AILE_LAMES} stroke={NUIT} strokeWidth={3.5} strokeLinecap="round" />
              </Ailes>

              {/* Pare-brise et afficheur de destination */}
              <path d={PARE_BRISE} fill={NUIT} stroke={NUIT} strokeWidth={3} strokeLinejoin="round" />
              <path d={REFLET} fill={BRUME} />
              <Afficheur mode={humeur === 'reflexion' ? 'sequence' : humeur === 'loupe' ? 'clignote' : 'repos'} anime={anime} />

              {/* Yeux-phares */}
              {YEUX.map((cx) => (
                <Oeil key={cx} cx={cx} humeur={humeur} anime={anime} />
              ))}
              {humeur === 'inquiete' &&
                [undefined, MIROIR].map((t) => (
                  <path key={t ?? 'gauche'} d={SOURCIL} transform={t} stroke={NUIT} strokeWidth={6} strokeLinecap="round" />
                ))}

              <Bec ouverture={OUVERTURE[humeur]} anime={anime} />

              {/* Châssis et roues */}
              <rect {...CHASSIS} fill={NUIT} />
              {ROUES.map((x) => (
                <Roue key={x} cx={x} tourne={anime && humeur === 'parle'} />
              ))}

              {joie && (
                <>
                  <Etincelle x={22} y={44} rayon={11} debut={0} anime={anime} />
                  <Etincelle x={180} y={28} rayon={13} debut={0.3} anime={anime} />
                  <Etincelle x={190} y={84} rayon={7} debut={0.6} anime={anime} />
                </>
              )}
              {humeur === 'inquiete' && <Goutte anime={anime} />}
            </g>
          </Ecrasement>
        </g>
      </g>

      {humeur === 'celebre' && <Confettis anime={anime} />}
    </svg>
  )
}
