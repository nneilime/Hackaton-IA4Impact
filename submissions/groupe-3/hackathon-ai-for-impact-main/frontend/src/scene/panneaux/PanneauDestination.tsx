import { useId, useState } from 'react'
import type { ReactNode } from 'react'
import { Bus, CheckCircle2, Compass, Gauge, Footprints, MapPin, TrainFront, Vote } from 'lucide-react'
import type { PropsPanneau } from '../types'
import { AnneauScore } from '../../components/voyage/IndiceConfiance'
import PastilleNiveau from '../../components/voyage/PastilleNiveau'
import { formaterDuree, libelleCorrespondances } from '../../components/voyage/format'
import { CadrePanneau, DetailPourquoi, PanneauVide, SqueletteCarte } from './communs'
import { LIBELLES_ACCES, LIBELLES_INDICE } from './libelles'
import CarteDestinations from './CarteDestinations'

/** Au-delà, le texte pédagogique est replié sur deux lignes avec un bouton « Tout lire ». */
const LONGUEUR_REPLIABLE = 150

function Indicateur({ icone, libelle, children }: { icone: ReactNode; libelle: string; children: ReactNode }) {
  return (
    <div className="grid min-w-0 grid-cols-[6rem_minmax(0,1fr)] items-center gap-3 rounded-field bg-base-200 p-3 @lg:flex @lg:flex-col @lg:items-start @lg:gap-1.5">
      <p className="flex items-center gap-1.5 text-xs font-semibold text-base-content/70">
        {icone}
        {libelle}
      </p>
      <div className="flex min-w-0 flex-col items-start gap-1.5">{children}</div>
    </div>
  )
}

/** Étape « destination » : UNE grande carte sobre. Les badges de source sont déjà sous la bulle de Tchouette. */
export default function PanneauDestination({ reponse, chargement, envoyer }: PropsPanneau) {
  const titreId = useId()
  const [toutLire, setToutLire] = useState(false)
  const [selection, setSelection] = useState<string[]>([])
  const destination = reponse.destination

  if (!destination) {
    return chargement ? (
      <SqueletteCarte />
    ) : (
      <PanneauVide
        titre="Pas encore de destination à vous montrer"
        texte="Précisez votre projet à Tchouette, ou revenez à l’étape précédente avec « Retour »."
      />
    )
  }

  const { acces_gare_site: acces } = destination
  const IconeAcces = acces.mode === 'pied' ? Footprints : Bus
  const depart = reponse.etat.demande.gare_depart?.nom ?? reponse.etat.demande.lieu_depart?.libelle ?? null
  const decouverte = destination.site_id.startsWith('dt-')
  const interet = destination.interet_pedagogique
  const replie = interet.length > LONGUEUR_REPLIABLE && !toutLire

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <CadrePanneau titreId={titreId} occupe={chargement}>
        <div className="@container flex flex-col gap-4 p-4 sm:p-5">
          <header className="flex min-w-0 flex-col gap-1.5 pe-10">
            {decouverte && (
              <span className="badge badge-accent badge-sm w-fit gap-1 font-bold">
                <Compass className="size-3.5" aria-hidden="true" />
                Découverte
              </span>
            )}
            <h2 id={titreId} className="text-xl font-bold leading-tight">
              {destination.nom}
            </h2>
            <p className="flex flex-wrap items-center gap-x-1.5 text-sm">
              <MapPin className="size-4 shrink-0" aria-hidden="true" />
              <span className="font-semibold">{destination.commune}</span>
              <span aria-hidden="true">·</span>
              <span>Gare : {destination.gare.nom}</span>
            </p>
          </header>

          <div className="grid gap-1">
            <p className={replie ? 'line-clamp-2 text-sm leading-relaxed' : 'text-sm leading-relaxed'}>{interet}</p>
            {interet.length > LONGUEUR_REPLIABLE && (
              <button
                type="button"
                onClick={() => setToutLire((v) => !v)}
                aria-expanded={toutLire}
                className="btn btn-ghost btn-sm min-h-10 w-fit px-2 text-secondary"
              >
                {toutLire ? 'Réduire' : 'Tout lire'}
              </button>
            )}
          </div>

          {decouverte && (
            <p role="note" className="rounded-field border-2 border-dashed border-accent bg-accent/15 p-2.5 text-sm">
              <span className="font-bold">À vérifier : </span>
              horaires et accueil de groupe à vérifier auprès du site.
            </p>
          )}

          <div className="grid gap-2 border-t-2 border-dashed border-base-300 pt-4 @lg:grid-cols-3">
            <Indicateur icone={<TrainFront className="size-3.5 shrink-0" aria-hidden="true" />} libelle="Trajet">
              <p className="text-lg font-extrabold leading-none tabular-nums">
                {formaterDuree(destination.temps_trajet_min)}
              </p>
              <p className="text-xs leading-snug">
                {libelleCorrespondances(destination.correspondances)}
                {depart && <span className="block">depuis {depart}</span>}
              </p>
            </Indicateur>

            <Indicateur icone={<IconeAcces className="size-3.5 shrink-0" aria-hidden="true" />} libelle="Gare → site">
              <p className="text-lg font-extrabold leading-none tabular-nums">
                {acces.minutes_groupe}
                <span className="text-xs font-semibold"> min</span>
              </p>
              <p className="text-xs leading-snug">{acces.mode === 'pied' ? 'à pied' : 'en transport urbain'}</p>
              <PastilleNiveau niveau={acces.niveau} libelle={LIBELLES_ACCES[acces.niveau]} />
            </Indicateur>

            <Indicateur icone={<Gauge className="size-3.5 shrink-0" aria-hidden="true" />} libelle="Confiance">
              <AnneauScore score={destination.indice_confiance} niveau={destination.niveau} />
              <PastilleNiveau niveau={destination.niveau} libelle={LIBELLES_INDICE[destination.niveau]} />
            </Indicateur>
          </div>
        </div>
      </CadrePanneau>

      <SelectionCandidates
        reponse={reponse}
        chargement={chargement}
        envoyer={envoyer}
        selection={selection}
        onChanger={setSelection}
      />

      {reponse.carte && (
        <CarteDestinations carte={reponse.carte} selectionnes={(reponse.choix_destinations ?? []).flatMap((d, i) => (selection.includes(d.site_id) ? [i + 1] : []))} />
      )}

      {reponse.detail && <DetailPourquoi key={reponse.detail.titre} detail={reponse.detail} titre="Pourquoi ce choix ?" />}
    </div>
  )
}

const MAX_CHOIX = 4

interface PropsSelection {
  reponse: PropsPanneau['reponse']
  chargement: boolean
  envoyer: PropsPanneau['envoyer']
  selection: string[]
  onChanger: (ids: string[]) => void
}

/** Multi-sélection : 2 à 4 candidates soumises au vote de la classe, ou une seule pour passer directement au trajet. */
function SelectionCandidates({ reponse, chargement, envoyer, selection, onChanger }: PropsSelection) {
  const groupeId = useId()
  const liste = reponse.choix_destinations ?? []
  if (liste.length < 2) return null
  const max = Math.min(MAX_CHOIX, liste.length)
  const n = selection.length
  const plein = n >= max

  function basculer(id: string) {
    onChanger(selection.includes(id) ? selection.filter((x) => x !== id) : plein ? selection : [...selection, id])
  }

  const unique = n === 1
  const plage = max === 2 ? 'les 2' : `2 à ${max}`
  const libelleBouton = unique ? 'Choisir cette destination' : 'Soumettre au vote de la classe'
  const aide =
    n === 0
      ? `Cochez 1 destination pour la choisir, ou ${plage} pour faire voter la classe.`
      : unique
        ? 'Une seule destination : on passe directement au trajet.'
        : 'Les élèves voteront entre ces destinations.'

  return (
    <fieldset className="flex min-w-0 flex-col gap-3 rounded-box border-2 border-secondary bg-base-100 p-4">
      <legend className="flex items-center gap-2 px-1 text-base font-bold">
        <Vote className="size-5 shrink-0" aria-hidden="true" />
        Mes destinations candidates
      </legend>
      <p className="text-sm tabular-nums" id={`${groupeId}-aide`}>
        <span className="font-extrabold">{n}</span> choisie{n > 1 ? 's' : ''} sur {max} possibles. {aide}
      </p>
      <ul className="grid gap-2" aria-describedby={`${groupeId}-aide`}>
        {liste.map((d, i) => {
          const coche = selection.includes(d.site_id)
          const bloque = !coche && plein
          return (
            <li key={d.site_id}>
              <label
                className={`flex min-h-14 cursor-pointer items-start gap-3 rounded-field border-2 p-3 ${
                  coche ? 'border-secondary bg-base-200' : 'border-base-300'
                } ${bloque ? 'cursor-not-allowed opacity-60' : ''}`}
              >
                <input
                  type="checkbox"
                  className="checkbox checkbox-secondary mt-0.5 size-6 shrink-0"
                  checked={coche}
                  disabled={bloque || chargement}
                  onChange={() => basculer(d.site_id)}
                />
                <span className="grid min-w-0 gap-1">
                  <span className="flex items-center gap-2 font-bold leading-tight">
                    <span className="inline-grid size-6 shrink-0 place-items-center rounded-full bg-accent text-xs font-extrabold text-secondary tabular-nums">
                      {i + 1}
                    </span>
                    {d.nom}
                    {coche && <CheckCircle2 className="size-4 shrink-0" aria-label="choisie" />}
                  </span>
                  <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs tabular-nums">
                    <span className="flex items-center gap-1">
                      <MapPin className="size-3.5" aria-hidden="true" />
                      {d.commune}
                    </span>
                    <span className="flex items-center gap-1">
                      <TrainFront className="size-3.5" aria-hidden="true" />
                      {formaterDuree(d.temps_trajet_min)}
                    </span>
                    <span className="flex items-center gap-1">
                      <Footprints className="size-3.5" aria-hidden="true" />
                      {d.acces_gare_site.minutes_groupe} min
                    </span>
                    <PastilleNiveau niveau={d.niveau} libelle={`${d.indice_confiance}/100 · ${LIBELLES_INDICE[d.niveau]}`} />
                  </span>
                </span>
              </label>
            </li>
          )
        })}
      </ul>
      <button
        type="button"
        disabled={n === 0 || chargement}
        onClick={() => envoyer({ type: 'soumettre_vote', ids: selection })}
        className="btn btn-primary btn-md min-h-11 w-full sm:w-fit"
      >
        {unique ? <CheckCircle2 className="size-4" aria-hidden="true" /> : <Vote className="size-4" aria-hidden="true" />}
        {n === 0 ? 'Cochez au moins une destination' : libelleBouton}
      </button>
    </fieldset>
  )
}
