import { useEffect, useId, useRef, useState } from 'react'
import { CheckCircle2, CircleX, ClipboardList, Lock, Minus, Plus, RotateCw, Smartphone, Trophy, Users, Vote, Wifi, WifiOff } from 'lucide-react'
import { api } from '../../api/client'
import type { Sondage } from '../../api/types'
import type { PropsPanneau } from '../types'
import Confettis from '../../features/vote/Confettis'
import CourseTrains from '../../features/vote/CourseTrains'
import QrCodeVote from '../../features/vote/QrCodeVote'
import { commenter as commentaireVote } from '../../features/vote/commentaires'
import { useSondage } from '../../features/vote/useSondage'
import { useUrlVote } from '../../features/vote/useUrlVote'
import { INTERVALLE_ANIMATEUR_MS, libelleVotes, optionGagnante } from '../../features/vote/vote'
import { CadrePanneau, PanneauVide, SqueletteCarte } from './communs'

/** Deux commentaires de Tchouette ne se suivent jamais de plus près : pas de bavardage pendant la course. */
const ECART_MIN_COMMENTAIRES_MS = 3500
/** Petit délai avant de commenter, pour regrouper des votes presque simultanés. */
const ANTI_REBOND_MS = 600
/** Durée de la célébration avant d'enchaîner sur le trajet. */
const DUREE_CELEBRATION_MS = 3000

/** Étape « vote » : QR code, course des trains en direct, commentaires de Tchouette, clôture. */
export default function PanneauVote(props: PropsPanneau) {
  const code = props.reponse.etat.vote_code
  if (!code) {
    return props.chargement ? (
      <SqueletteCarte lignes={2} />
    ) : (
      <PanneauVide
        titre="Le vote n’est pas encore ouvert"
        texte="Tchouette prépare le QR code. Si rien n’apparaît, revenez en arrière avec « Retour » et relancez le vote."
      />
    )
  }
  return <VoteOuvert key={code} code={code} {...props} />
}

interface VoteOuvertProps extends PropsPanneau {
  code: string
}

function VoteOuvert({ code, envoyer, chargement, commenter }: VoteOuvertProps) {
  const titreId = useId()
  const { sondage, etat, erreur, horsLigne, reessayer, remplacer } = useSondage(code, INTERVALLE_ANIMATEUR_MS)
  const adresse = useUrlVote(code)

  const [confirmation, setConfirmation] = useState(false)
  const [fermeture, setFermeture] = useState(false)
  const [erreurFermeture, setErreurFermeture] = useState<string | null>(null)
  const [enchainement, setEnchainement] = useState(false)
  const boutonClore = useRef<HTMLButtonElement>(null)
  const boutonContinuer = useRef<HTMLButtonElement>(null)
  const confirmationOuverte = useRef(false)

  // Les props changent à chaque tour : les timers lisent toujours la dernière version.
  const commenterRef = useRef(commenter)
  const envoyerRef = useRef(envoyer)
  useEffect(() => {
    commenterRef.current = commenter
    envoyerRef.current = envoyer
  })

  // Commentaires en direct : à chaque changement des votes, avec anti-rebond et écart minimal.
  const precedent = useRef<Sondage | null>(null)
  const minuteur = useRef<number | undefined>(undefined)
  const dernierCommentaire = useRef(0)
  useEffect(() => {
    if (!sondage) return
    const avant = precedent.current
    precedent.current = sondage
    if (sondage.statut === 'ferme') return
    const nouveau = commentaireVote(avant, sondage)
    if (!nouveau) return
    window.clearTimeout(minuteur.current)
    const attente = Math.max(ANTI_REBOND_MS, ECART_MIN_COMMENTAIRES_MS - (Date.now() - dernierCommentaire.current))
    minuteur.current = window.setTimeout(() => {
      dernierCommentaire.current = Date.now()
      commenterRef.current(nouveau.texte, nouveau.humeur)
    }, attente)
  }, [sondage])
  useEffect(() => () => window.clearTimeout(minuteur.current), [])

  // Focus clavier : la confirmation reçoit le focus (sur l'action sûre), et le rend au bouton si on renonce.
  useEffect(() => {
    if (confirmation) {
      boutonContinuer.current?.focus()
      confirmationOuverte.current = true
    } else if (confirmationOuverte.current) {
      confirmationOuverte.current = false
      boutonClore.current?.focus()
    }
  }, [confirmation])

  const ferme = sondage?.statut === 'ferme'
  const gagnante = sondage ? optionGagnante(sondage) : null
  const gagnantId = sondage?.gagnant ?? null

  // Après la célébration, on enchaîne tout seul sur le trajet de la destination gagnante.
  useEffect(() => {
    if (!enchainement || !gagnantId) return
    const minuterie = window.setTimeout(() => {
      envoyerRef.current({ type: 'vote_termine', site_id: gagnantId })
    }, DUREE_CELEBRATION_MS)
    return () => window.clearTimeout(minuterie)
  }, [enchainement, gagnantId])

  async function clore() {
    setFermeture(true)
    setErreurFermeture(null)
    try {
      const clos = await api.fermerSondage(code)
      window.clearTimeout(minuteur.current)
      remplacer(clos)
      setConfirmation(false)
      const vainqueur = optionGagnante(clos)
      commenterRef.current(
        vainqueur ? `Et la classe a choisi… ${vainqueur.nom} ! Tout le monde en voiture !` : 'Le vote est terminé.',
        'celebre',
      )
      setEnchainement(true)
    } catch (cause) {
      setErreurFermeture(cause instanceof Error ? cause.message : 'Le vote n’a pas pu être clos. Réessayez.')
    } finally {
      setFermeture(false)
    }
  }

  if (etat === 'chargement') return <SqueletteCarte lignes={2} />

  if (etat === 'introuvable') {
    return (
      <PanneauVide
        titre="Ce vote n’existe plus"
        texte={`Le code ${code} ne correspond à aucun vote. Revenez en arrière avec « Retour » pour en lancer un nouveau.`}
      />
    )
  }

  if (etat === 'erreur' || !sondage) {
    return (
      <div role="alert" className="alert alert-error alert-vertical motion-safe:animate-entree sm:alert-horizontal">
        <CircleX className="size-6 shrink-0" aria-hidden="true" />
        <div className="grid gap-1">
          <h2 className="font-bold">Impossible de charger le vote</h2>
          <p className="text-sm">
            {erreur ?? 'Erreur inattendue.'} Vérifiez que le serveur du copilote est lancé, puis réessayez.
          </p>
        </div>
        <button type="button" onClick={reessayer} className="btn btn-sm min-h-10">
          <RotateCw className="size-4" aria-hidden="true" />
          Réessayer
        </button>
      </div>
    )
  }

  const total = sondage.total_votes
  const aucunVote = total === 0

  return (
    <CadrePanneau titreId={titreId} occupe={false}>
      <div className="@container flex flex-col gap-4 p-4 sm:p-5">
        <header className="flex min-w-0 flex-col gap-1.5 pe-10">
          <h2 id={titreId} className="flex items-center gap-2 text-lg font-bold leading-tight">
            <Vote className="size-5 shrink-0" aria-hidden="true" />
            {ferme ? 'Le vote est clos' : 'Votre classe vote'}
          </h2>
          {!ferme && <EtatDirect horsLigne={horsLigne} />}
        </header>

        {!ferme && (
          <section
            aria-label="Rejoindre le vote"
            className="grid items-center gap-4 @xl:grid-cols-[auto_minmax(0,1fr)]"
          >
            {adresse.etat === 'calcul' && <div className="skeleton aspect-square w-full max-w-64 justify-self-center" />}
            {adresse.etat === 'prete' && (
              <QrCodeVote
                url={adresse.url}
                className="aspect-square w-full max-w-64 justify-self-center rounded-field border-4 border-secondary"
              />
            )}
            {adresse.etat === 'sans-ip' && (
              <div className="grid aspect-square w-full max-w-64 place-items-center justify-self-center rounded-field border-4 border-dashed border-base-300">
                <WifiOff className="size-14 opacity-40" aria-hidden="true" />
              </div>
            )}

            <div className="grid min-w-0 content-center gap-3 text-center @xl:text-left">
              <div className="grid gap-1">
                <p className="flex items-center justify-center gap-1.5 text-sm font-semibold @xl:justify-start">
                  <Smartphone className="size-4 shrink-0" aria-hidden="true" />
                  Scannez pour voter
                </p>
                <p className="text-xs font-semibold uppercase tracking-wide text-base-content/70">Code du vote</p>
                <p
                  className="text-4xl font-extrabold tabular-nums tracking-[0.2em]"
                  aria-label={`Code du vote : ${code.split('').join(' ')}`}
                >
                  {code}
                </p>
              </div>

              {adresse.etat === 'prete' && (
                <div className="grid gap-1">
                  <p className="text-sm">Pas d’appareil photo ? Tapez l’adresse :</p>
                  <p className="[user-select:all] break-all font-mono text-sm font-bold">{adresse.url}</p>
                  <p className="flex items-start justify-center gap-2 text-xs font-semibold @xl:justify-start">
                    <Wifi className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                    <span>Les téléphones doivent être sur le même Wi-Fi que cet ordinateur.</span>
                  </p>
                </div>
              )}
              {adresse.etat === 'sans-ip' && (
                <div role="alert" className="alert alert-warning alert-vertical text-left">
                  <WifiOff className="size-5 shrink-0" aria-hidden="true" />
                  <div className="grid gap-1">
                    <h3 className="font-bold">Adresse réseau introuvable</h3>
                    <p className="text-sm">
                      Les téléphones doivent être sur le même Wi-Fi ; ouvrez le site via l’adresse « Network »
                      affichée par Vite.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </section>
        )}

        <div className="grid gap-1.5 border-t-2 border-dashed border-base-300 pt-4 text-sm">
          <p aria-live="polite" className="flex items-center gap-2 tabular-nums">
            <Users className="size-4 shrink-0" aria-hidden="true" />
            <span>
              <span className="font-extrabold">{total}</span> {total > 1 ? 'votes reçus' : 'vote reçu'}
              {sondage.effectif ? ` sur ${sondage.effectif} élèves` : ''}
            </span>
          </p>
          <p className="flex items-center gap-2 tabular-nums">
            <ClipboardList className="size-4 shrink-0" aria-hidden="true" />
            {sondage.votes_manuels} {sondage.votes_manuels > 1 ? 'votes' : 'vote'} en classe (saisie)
          </p>
          <p className="flex items-center gap-2 tabular-nums">
            <Smartphone className="size-4 shrink-0" aria-hidden="true" />
            {sondage.votes_qr} {sondage.votes_qr > 1 ? 'votes' : 'vote'} par QR
          </p>
        </div>

        {!ferme && <SaisieManuelle code={code} sondage={sondage} onSondage={remplacer} />}

        <div className="min-w-0 max-sm:[&_.font-extrabold.text-xl]:text-base">
          <CourseTrains sondage={sondage} />
        </div>

        {ferme ? (
          <Celebration
            nom={gagnante?.nom ?? null}
            commune={gagnante?.commune ?? null}
            votes={gagnante ? libelleVotes(gagnante.votes) : null}
            enchaine={enchainement}
            occupe={chargement}
            onContinuer={() => {
              if (gagnantId) envoyer({ type: 'vote_termine', site_id: gagnantId })
            }}
            peutContinuer={!!gagnantId}
          />
        ) : (
          <div className="grid gap-2">
            {confirmation ? (
              <div role="alertdialog" aria-labelledby={`${titreId}-clore`} className="grid gap-3 rounded-box border-2 border-secondary bg-base-200 p-3">
                <p id={`${titreId}-clore`} className="text-sm font-semibold">
                  Clore le vote avec {libelleVotes(total)} ? Plus personne ne pourra voter.
                </p>
                <div className="flex flex-col gap-2 sm:flex-row">
                  <button
                    type="button"
                    onClick={() => void clore()}
                    disabled={fermeture}
                    className="btn btn-primary btn-md min-h-11"
                  >
                    {fermeture ? (
                      <span className="loading loading-spinner loading-sm" aria-hidden="true" />
                    ) : (
                      <Lock className="size-4" aria-hidden="true" />
                    )}
                    {fermeture ? 'Clôture en cours…' : 'Oui, clore le vote'}
                  </button>
                  <button
                    ref={boutonContinuer}
                    type="button"
                    onClick={() => setConfirmation(false)}
                    disabled={fermeture}
                    className="btn btn-ghost btn-md min-h-11"
                  >
                    Continuer le vote
                  </button>
                </div>
              </div>
            ) : (
              <>
                <button
                  ref={boutonClore}
                  type="button"
                  onClick={() => setConfirmation(true)}
                  disabled={aucunVote}
                  aria-describedby={aucunVote ? `${titreId}-raison` : undefined}
                  className="btn btn-primary btn-md min-h-11 w-full sm:w-fit"
                >
                  <Lock className="size-4" aria-hidden="true" />
                  Clore le vote
                </button>
                {aucunVote && (
                  <p id={`${titreId}-raison`} className="text-xs">
                    Disponible dès le premier vote de la classe.
                  </p>
                )}
              </>
            )}
            {erreurFermeture && (
              <p role="alert" className="flex items-start gap-2 text-sm font-semibold text-error">
                <CircleX className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                {erreurFermeture}
              </p>
            )}
          </div>
        )}
      </div>
    </CadrePanneau>
  )
}

/** Fraîcheur des chiffres : en direct ou connexion perdue. Statut = icône + texte. */
function EtatDirect({ horsLigne }: { horsLigne: boolean }) {
  if (horsLigne) {
    return (
      <p role="status" className="flex items-center gap-2 text-sm font-semibold">
        <WifiOff className="size-4" aria-hidden="true" />
        Connexion perdue, nouvel essai…
      </p>
    )
  }
  return (
    <p className="flex items-center gap-2 text-sm font-semibold">
      <span className="inline-grid *:[grid-area:1/1]" aria-hidden="true">
        <span className="status status-success motion-safe:animate-ping" />
        <span className="status status-success" />
      </span>
      En direct · actualisé toutes les 2 s
    </p>
  )
}

interface CelebrationProps {
  nom: string | null
  commune: string | null
  votes: string | null
  enchaine: boolean
  occupe: boolean
  peutContinuer: boolean
  onContinuer: () => void
}

/** La classe a choisi : confettis, nom du gagnant, puis on enchaîne sur le trajet. */
function Celebration({ nom, commune, votes, enchaine, occupe, peutContinuer, onContinuer }: CelebrationProps) {
  return (
    <section
      aria-live="polite"
      className="relative grid justify-items-center gap-2 overflow-hidden rounded-box border-2 border-secondary bg-base-200 px-4 py-9 text-center"
    >
      <Confettis />
      <Trophy className="size-8" aria-hidden="true" />
      <p className="text-sm font-semibold">La classe a choisi</p>
      <p className="text-xl font-extrabold leading-tight motion-safe:animate-pop">{nom ?? 'Aucune destination'}</p>
      {commune && votes && (
        <p className="text-sm">
          {commune} · <span className="tabular-nums">{votes}</span>
        </p>
      )}
      {peutContinuer && (
        <button
          type="button"
          onClick={onContinuer}
          disabled={occupe}
          className="btn btn-primary btn-md relative mt-2 min-h-11"
        >
          {occupe && <span className="loading loading-spinner loading-sm" aria-hidden="true" />}
          {enchaine ? 'Voir le trajet maintenant' : 'Voir le trajet'}
        </button>
      )}
    </section>
  )
}

interface SaisieManuelleProps {
  code: string
  sondage: Sondage
  onSondage: (s: Sondage) => void
}

/** Saisie à la main des votes (classes trop jeunes pour un téléphone) ; s'ajoute aux votes par QR. */
function SaisieManuelle({ code, sondage, onSondage }: SaisieManuelleProps) {
  const id = useId()
  const [ouverte, setOuverte] = useState(sondage.votes_manuels > 0)
  const [valeurs, setValeurs] = useState<Record<string, number>>(() =>
    Object.fromEntries(sondage.options.map((o) => [o.site_id, o.votes_manuels])),
  )
  const [enregistrement, setEnregistrement] = useState(false)
  const [erreur, setErreur] = useState<string | null>(null)
  const [ok, setOk] = useState(false)

  const somme = Object.values(valeurs).reduce((a, b) => a + b, 0)
  const plafond = sondage.effectif ?? 50
  const reste = plafond - sondage.votes_qr - somme
  const depasse = reste < 0

  function changer(siteId: string, delta: number) {
    setOk(false)
    setValeurs((v) => ({ ...v, [siteId]: Math.max(0, (v[siteId] ?? 0) + delta) }))
  }

  async function enregistrer() {
    setEnregistrement(true)
    setErreur(null)
    try {
      onSondage(await api.votesManuels(code, valeurs))
      setOk(true)
    } catch (cause) {
      setErreur(cause instanceof Error ? cause.message : 'La saisie n’a pas pu être enregistrée.')
    } finally {
      setEnregistrement(false)
    }
  }

  if (!ouverte) {
    return (
      <button type="button" onClick={() => setOuverte(true)} className="btn btn-outline btn-md min-h-11 w-full sm:w-fit">
        <ClipboardList className="size-4" aria-hidden="true" />
        Saisir les votes à la main
      </button>
    )
  }

  return (
    <section aria-labelledby={`${id}-titre`} className="grid gap-3 rounded-box border-2 border-base-300 p-3">
      <h3 id={`${id}-titre`} className="flex items-center gap-2 font-bold">
        <ClipboardList className="size-5 shrink-0" aria-hidden="true" />
        Votes à main levée
      </h3>
      <p className="text-xs">
        Pour les classes sans téléphone : comptez les mains levées. S’ajoute aux votes par QR code.
      </p>
      <ul className="grid gap-2">
        {sondage.options.map((o) => (
          <li key={o.site_id} className="flex items-center justify-between gap-3">
            <span className="min-w-0 truncate text-sm font-semibold">{o.nom}</span>
            <span className="flex shrink-0 items-center gap-1">
              <button
                type="button"
                onClick={() => changer(o.site_id, -1)}
                disabled={(valeurs[o.site_id] ?? 0) <= 0}
                aria-label={`Un vote de moins pour ${o.nom}`}
                className="btn btn-square btn-outline min-h-11 min-w-11"
              >
                <Minus className="size-4" aria-hidden="true" />
              </button>
              <output className="w-10 text-center text-lg font-extrabold tabular-nums" aria-label={`${valeurs[o.site_id] ?? 0} votes pour ${o.nom}`}>
                {valeurs[o.site_id] ?? 0}
              </output>
              <button
                type="button"
                onClick={() => changer(o.site_id, 1)}
                disabled={reste <= 0}
                aria-label={`Un vote de plus pour ${o.nom}`}
                className="btn btn-square btn-outline min-h-11 min-w-11"
              >
                <Plus className="size-4" aria-hidden="true" />
              </button>
            </span>
          </li>
        ))}
      </ul>
      <p className={`flex items-center gap-2 text-sm tabular-nums ${depasse ? 'font-bold text-error' : ''}`} aria-live="polite">
        {depasse ? <CircleX className="size-4 shrink-0" aria-hidden="true" /> : <Users className="size-4 shrink-0" aria-hidden="true" />}
        {somme} en classe + {sondage.votes_qr} par QR sur {plafond} élèves
        {depasse ? ' : trop de votes' : ` · ${reste} restant${reste > 1 ? 's' : ''}`}
      </p>
      <button
        type="button"
        onClick={() => void enregistrer()}
        disabled={enregistrement || depasse}
        className="btn btn-primary btn-md min-h-11 w-full sm:w-fit"
      >
        {enregistrement ? (
          <span className="loading loading-spinner loading-sm" aria-hidden="true" />
        ) : (
          <CheckCircle2 className="size-4" aria-hidden="true" />
        )}
        Enregistrer la saisie
      </button>
      {ok && (
        <p role="status" className="flex items-center gap-2 text-sm font-semibold">
          <CheckCircle2 className="size-4 shrink-0" aria-hidden="true" />
          Saisie enregistrée
        </p>
      )}
      {erreur && (
        <p role="alert" className="flex items-start gap-2 text-sm font-semibold text-error">
          <CircleX className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          {erreur}
        </p>
      )}
    </section>
  )
}
