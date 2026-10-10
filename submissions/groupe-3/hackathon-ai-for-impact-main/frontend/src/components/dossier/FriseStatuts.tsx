const ETAPES = [
  { libelle: 'Proposition', detail: 'Le trajet choisi' },
  { libelle: 'Option', detail: 'Places retenues' },
  { libelle: 'Pré-réservation', detail: 'Transmise à SNCF' },
  { libelle: 'Confirmation', detail: 'Validée par SNCF' },
] as const

/** Issue particulière affichée à la place de l'étape « Confirmation ». */
export type IssueFrise = 'contre-proposition' | 'annule'

interface FriseStatutsProps {
  /** Index de l'étape en cours : 0 Proposition, 1 Option, 2 Pré-réservation, 3 Confirmation. */
  etapeActuelle: number
  issue?: IssueFrise
}

/**
 * Frise compacte des statuts de la fiche : PROPOSITION → OPTION → PRÉ-RÉSERVATION → CONFIRMATION.
 * Horizontale dès 640 px, verticale sur téléphone. Chaque gare : pastille + libellé + détail court.
 */
export default function FriseStatuts({ etapeActuelle, issue }: FriseStatutsProps) {
  return (
    <ol
      aria-label="Étapes de la demande de pré-réservation"
      className="steps steps-vertical w-full text-xs sm:steps-horizontal"
    >
      {ETAPES.map((etape, index) => {
        const derniere = index === ETAPES.length - 1
        const faite = index < etapeActuelle
        const actuelle = index === etapeActuelle

        if (derniere && issue) {
          const contre = issue === 'contre-proposition'
          return (
            <li
              key={etape.libelle}
              data-content={contre ? '!' : '✕'}
              aria-current="step"
              className={contre ? 'step step-warning' : 'step step-error'}
            >
              <span className="flex flex-col items-start sm:items-center">
                <span className="font-bold">{contre ? 'Contre-proposition' : 'Annulée'}</span>
                <span className="text-base-content/70">{contre ? 'SNCF propose autre chose' : "La demande n'a pas abouti"}</span>
              </span>
            </li>
          )
        }

        const confirmee = derniere && actuelle
        return (
          <li
            key={etape.libelle}
            data-content={faite || confirmee ? '✓' : undefined}
            aria-current={actuelle ? 'step' : undefined}
            className={confirmee ? 'step step-success' : faite || actuelle ? 'step step-secondary' : 'step'}
          >
            <span className="flex flex-col items-start sm:items-center">
              <span className="font-bold">
                {etape.libelle}
                {faite && <span className="sr-only"> (étape franchie)</span>}
                {!faite && !actuelle && <span className="sr-only"> (à venir)</span>}
              </span>
              {actuelle && !confirmee ? (
                <span className="badge badge-secondary badge-xs mt-0.5 font-bold motion-safe:animate-pop">
                  Vous êtes ici
                </span>
              ) : (
                <span className="text-base-content/70">{etape.detail}</span>
              )}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
