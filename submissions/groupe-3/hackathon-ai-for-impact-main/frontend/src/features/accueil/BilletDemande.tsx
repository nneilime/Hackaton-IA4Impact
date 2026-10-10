import type { ReactNode } from 'react'
import { ArrowDown, CircleCheck, CircleDashed, CircleX, Clock, Ticket, TrainFront, TriangleAlert } from 'lucide-react'
import type { Demande } from '../../api/types'
import Tchouette from '../../mascot/Tchouette'
import {
  CHAMPS_OBLIGATOIRES,
  DELAI_CONSEILLE_JOURS,
  EFFECTIF_MAX,
  EFFECTIF_MIN,
  HEURE_DEPART_PAR_DEFAUT,
  HEURE_RETOUR_PAR_DEFAUT,
  LIBELLES_DUREE,
  LIBELLES_MANQUANTS,
  demandePrete,
  etatEffectif,
  formaterDateCourte,
  formaterDistance,
  joursAvantDepart,
  listeEnFrancais,
  manquantsObligatoires,
  totalVoyageurs,
} from './demande'

/**
 * Une case du billet : coche et valeur si c'est compris, pointillés sinon.
 * Quand la case passe de « à préciser » à « compris », elle fait un petit bond.
 */
function Case({
  libelle,
  valeur,
  parDefaut,
  large = false,
  children,
}: {
  libelle: string
  valeur: string | null | undefined
  parDefaut?: string
  large?: boolean
  children?: ReactNode
}) {
  const rempli = Boolean(valeur)
  return (
    <div className={large ? 'col-span-2 min-w-0' : 'min-w-0'}>
      <div
        key={rempli ? 'compris' : 'vide'}
        className={rempli ? 'flex items-start gap-1.5 motion-safe:animate-pop' : 'flex items-start gap-1.5'}
      >
        {rempli ? (
          <CircleCheck className="mt-0.5 size-4 shrink-0 text-success" aria-hidden="true" />
        ) : parDefaut ? (
          <Clock className="mt-0.5 size-4 shrink-0 text-base-content/60" aria-hidden="true" />
        ) : (
          <CircleDashed className="mt-0.5 size-4 shrink-0 text-base-content/50" aria-hidden="true" />
        )}
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-base-content/70">{libelle}</p>
          <div className="min-w-0">
            {rempli ? (
              <span className="block text-sm font-bold leading-snug tabular-nums break-words">{valeur}</span>
            ) : parDefaut ? (
              <span className="block text-sm leading-snug tabular-nums text-base-content/80">{parDefaut}</span>
            ) : (
              <span className="flex items-end gap-1.5 text-xs">
                <span aria-hidden="true" className="mb-1 h-2 flex-1 border-b-2 border-dotted border-base-content/40" />
                <span className="italic text-base-content/70">à préciser</span>
              </span>
            )}
            {children}
          </div>
        </div>
      </div>
    </div>
  )
}

/** Alerte compacte sous la grille : couleur + icône + texte. */
function Alerte({ niveau, children }: { niveau: 'vigilance' | 'pas-adapte'; children: ReactNode }) {
  const vigilance = niveau === 'vigilance'
  return (
    <li
      className={
        vigilance
          ? 'flex items-start gap-1.5 rounded-field bg-warning px-2 py-1 text-xs text-warning-content motion-safe:animate-entree'
          : 'flex items-start gap-1.5 rounded-field bg-error px-2 py-1 text-xs text-error-content motion-safe:animate-entree'
      }
    >
      {vigilance ? (
        <TriangleAlert className="mt-px size-3.5 shrink-0" aria-hidden="true" />
      ) : (
        <CircleX className="mt-px size-3.5 shrink-0" aria-hidden="true" />
      )}
      <span>
        <strong>{vigilance ? 'Point de vigilance : ' : 'Pas adapté : '}</strong>
        {children}
      </span>
    </li>
  )
}

interface BilletDemandeProps {
  demande: Demande | null
  /** Tchouette met le billet à jour (réponse ou vérification en cours). */
  occupe?: boolean
}

/** Le billet « Ce que j'ai compris » : récapitulatif compact, mis à jour en direct. */
export default function BilletDemande({ demande, occupe = false }: BilletDemandeProps) {
  const manquants = manquantsObligatoires(demande)
  const renseignes = CHAMPS_OBLIGATOIRES.length - manquants.length
  const total = totalVoyageurs(demande)
  const effectif = total === null ? null : etatEffectif(total)
  const jours = demande?.date ? joursAvantDepart(demande.date) : null
  const pret = demandePrete(demande)
  const gare = demande?.gare_depart ?? null

  const projet = demande?.theme ?? demande?.destination_souhaitee ?? null
  const horaires =
    demande?.heure_depart_min || demande?.heure_retour_max
      ? `${demande.heure_depart_min ?? HEURE_DEPART_PAR_DEFAUT} → ${demande.heure_retour_max ?? HEURE_RETOUR_PAR_DEFAUT}`
      : null

  return (
    <article
      aria-labelledby="billet-titre"
      className="relative rounded-box border-2 border-secondary bg-base-100 shadow-[4px_4px_0_0] shadow-secondary"
    >
      <header className="flex items-center justify-between gap-2 rounded-t-[14px] bg-secondary px-3 py-2 text-secondary-content">
        <h2 id="billet-titre" className="flex items-center gap-2 text-base font-bold">
          <Ticket className="size-4 shrink-0" aria-hidden="true" />
          Ce que j’ai compris
        </h2>
        <p className="flex shrink-0 items-center gap-1.5">
          {occupe && <span className="loading loading-dots loading-xs" aria-hidden="true" />}
          <span key={renseignes} className="badge badge-accent badge-sm font-bold tabular-nums motion-safe:animate-pop">
            <span className="sr-only">Informations obligatoires comprises : </span>
            {renseignes}/{CHAMPS_OBLIGATOIRES.length} compris
          </span>
        </p>
      </header>
      {/* Traverses de rail sous l'en-tête du billet */}
      <div
        aria-hidden="true"
        className="h-2 border-b-2 border-secondary bg-[repeating-linear-gradient(90deg,var(--color-secondary)_0_3px,transparent_3px_10px)]"
      />

      <div className="grid grid-cols-2 gap-x-3 gap-y-2.5 px-3 pb-1 pt-3">
        <Case libelle="Classe" valeur={demande?.niveau} />
        <Case libelle={demande?.theme ? 'Thème' : 'Thème ou lieu'} valeur={projet}>
          {demande?.theme && demande.destination_souhaitee && (
            <span className="block text-xs">
              Lieu souhaité : <strong>{demande.destination_souhaitee}</strong>
            </span>
          )}
        </Case>
        <Case libelle="Élèves" valeur={demande?.nb_eleves != null ? String(demande.nb_eleves) : null} />
        <Case
          libelle="Adultes"
          valeur={demande?.nb_accompagnateurs != null ? String(demande.nb_accompagnateurs) : null}
        />

        {/* Jauge fine : voyageurs sur 50 */}
        <div className="col-span-2">
          <p className="flex items-baseline justify-between gap-2 text-xs">
            <span className="font-semibold uppercase tracking-wide text-base-content/70">Voyageurs</span>
            <span className="tabular-nums">
              <strong className="text-sm">{total ?? '–'}</strong> / {EFFECTIF_MAX} max
            </span>
          </p>
          <progress
            className={effectif === 'trop' ? 'progress progress-error mt-1 h-1.5 w-full' : 'progress mt-1 h-1.5 w-full'}
            value={total === null ? 0 : Math.min(total, EFFECTIF_MAX)}
            max={EFFECTIF_MAX}
            aria-label={
              total === null ? 'Nombre de voyageurs à préciser' : `${total} voyageurs sur ${EFFECTIF_MAX} au maximum`
            }
          />
        </div>

        <Case libelle="Date" valeur={demande?.date ? formaterDateCourte(demande.date) : null}>
          {demande?.date && (
            <span className="block text-xs">
              {LIBELLES_DUREE[demande.duree ?? 'journee']}
              {jours !== null && jours >= 0 && <span className="tabular-nums"> · J-{jours}</span>}
            </span>
          )}
        </Case>
        <Case
          libelle="Horaires"
          valeur={horaires}
          parDefaut={`${HEURE_DEPART_PAR_DEFAUT} → ${HEURE_RETOUR_PAR_DEFAUT}`}
        />
        <Case libelle="Départ" valeur={demande?.lieu_depart?.libelle} large>
          {gare ? (
            <span className="mt-0.5 flex items-start gap-1 text-xs">
              <TrainFront className="mt-px size-3.5 shrink-0" aria-hidden="true" />
              <span>
                {gare.code_uic ? 'Gare : ' : 'Gare indiquée : '}
                <strong>{gare.nom}</strong>
                {gare.distance_m != null && (
                  <span className="tabular-nums"> · à {formaterDistance(gare.distance_m)}</span>
                )}
                {!gare.code_uic && ' (vérifiée ensuite)'}
              </span>
            </span>
          ) : demande?.lieu_depart ? (
            <span className="mt-0.5 flex items-start gap-1 text-xs text-base-content/70">
              <TrainFront className="mt-px size-3.5 shrink-0" aria-hidden="true" />
              Je cherche la gare la plus proche.
            </span>
          ) : null}
        </Case>
      </div>

      {(effectif === 'trop' || effectif === 'trop-peu' || (jours !== null && jours < DELAI_CONSEILLE_JOURS)) && (
        <ul className="space-y-1 px-3 pt-2" aria-label="Points à vérifier">
          {effectif === 'trop' && (
            <Alerte niveau="pas-adapte">au-delà de {EFFECTIF_MAX} voyageurs, prévoyez deux groupes.</Alerte>
          )}
          {effectif === 'trop-peu' && (
            <Alerte niveau="vigilance">un groupe liO commence à {EFFECTIF_MIN} voyageurs.</Alerte>
          )}
          {jours !== null && jours < 0 && <Alerte niveau="pas-adapte">cette date est déjà passée.</Alerte>}
          {jours !== null && jours >= 0 && jours < DELAI_CONSEILLE_JOURS && (
            <Alerte niveau="vigilance">
              moins de {DELAI_CONSEILLE_JOURS} jours avant le départ, étude au cas par cas.
            </Alerte>
          )}
        </ul>
      )}

      {/* Ligne de perforation : encoches sur les bords et trous du billet */}
      <div aria-hidden="true" className="relative my-1.5 h-4">
        <span className="absolute -left-2.5 top-0 size-4 rounded-full border-2 border-secondary bg-base-200 [clip-path:inset(0_0_0_50%)]" />
        <span className="absolute -right-2.5 top-0 size-4 rounded-full border-2 border-secondary bg-base-200 [clip-path:inset(0_50%_0_0)]" />
        <span className="absolute inset-x-4 top-1/2 h-1.5 -translate-y-1/2 bg-[radial-gradient(circle,var(--color-secondary)_1.5px,transparent_2px)] bg-[length:8px_6px] bg-repeat-x" />
      </div>

      {/* Le talon : un rappel discret, l'action principale vit dans la barre du bas */}
      <div className="px-3 pb-3" aria-live="polite">
        {pret ? (
          <p key="pret" className="flex items-center gap-2 text-sm font-semibold motion-safe:animate-entree">
            <Tchouette humeur="joie" taille={32} titre="" className="shrink-0" />
            <span className="min-w-0 flex-1">Tout y est ! Cliquez sur « Voir les destinations ».</span>
            <ArrowDown className="size-4 shrink-0 text-primary" aria-hidden="true" />
          </p>
        ) : manquants.length > 0 ? (
          <p className="text-xs">
            <span className="font-bold">Il me manque : </span>
            {listeEnFrancais(manquants.map((champ) => LIBELLES_MANQUANTS[champ] ?? champ))}.
          </p>
        ) : (
          <p className="text-xs">
            <span className="font-bold">Ajustez l’effectif : </span>
            de {EFFECTIF_MIN} à {EFFECTIF_MAX} voyageurs par groupe.
          </p>
        )}
      </div>
    </article>
  )
}
