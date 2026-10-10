// Petits raccourcis SMIL (<animate>, <animateTransform>) pour la mascotte.
// Toutes les animations bouclent à l'infini ; par défaut elles sont adoucies
// (ease-in-out) entre chaque valeur clé.

const ADOUCI = '0.45 0 0.55 1'

export interface Boucle {
  /** Valeurs clés, dans l'ordre. */
  valeurs: (string | number)[]
  /** Durée d'un cycle, en secondes. */
  duree: number
  /** Instants clés (0 → 1), un par valeur. Répartis uniformément si absent. */
  temps?: number[]
  /** Décalage du départ, en secondes. */
  debut?: number
  /** `adouci` (défaut), `lineaire` ou `discret` (saut sans interpolation). */
  rythme?: 'adouci' | 'lineaire' | 'discret'
}

function attributs({ valeurs, duree, temps, debut, rythme = 'adouci' }: Boucle) {
  return {
    values: valeurs.join(';'),
    dur: `${duree}s`,
    keyTimes: temps?.join(';'),
    begin: debut === undefined ? undefined : `${debut}s`,
    calcMode: rythme === 'adouci' ? 'spline' : rythme === 'discret' ? 'discrete' : 'linear',
    keySplines: rythme === 'adouci' ? Array(valeurs.length - 1).fill(ADOUCI).join(';') : undefined,
    repeatCount: 'indefinite',
  }
}

/** Anime l'attribut `transform` de l'élément parent (qui ne doit pas en avoir). */
export function Transfo({ type, ...boucle }: Boucle & { type: 'translate' | 'rotate' | 'scale' }) {
  return <animateTransform attributeName="transform" type={type} {...attributs(boucle)} />
}

/** Anime un attribut quelconque de l'élément parent. */
export function Attr({ nom, ...boucle }: Boucle & { nom: string }) {
  return <animate attributeName={nom} {...attributs(boucle)} />
}
