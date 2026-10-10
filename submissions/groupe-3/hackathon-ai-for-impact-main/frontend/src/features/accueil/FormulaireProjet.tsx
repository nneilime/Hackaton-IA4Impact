import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BookOpen,
  CalendarDays,
  CircleX,
  ClipboardPen,
  Flag,
  GraduationCap,
  MapPin,
  RotateCcw,
  School,
  TrainFront,
  TriangleAlert,
  Users,
} from 'lucide-react'
import { api, ErreurApi } from '../../api/client'
import type { Demande, Gare, LieuDepart } from '../../api/types'
import { useVoyage } from '../../state/VoyageContext'
import {
  DELAI_CONSEILLE_JOURS,
  EFFECTIF_MAX,
  EFFECTIF_MIN,
  GROUPES_NIVEAUX,
  HEURE_DEPART_PAR_DEFAUT,
  HEURE_RETOUR_PAR_DEFAUT,
  ID_FORMULAIRE_PROJET,
  LIBELLES_MANQUANTS,
  THEMES,
  champsManquants,
  demainIso,
  joursAvantDepart,
  listeEnFrancais,
} from './demande'
import type { EtatFormulaire } from './demande'

interface Valeurs {
  niveau: string
  theme: string
  destination: string
  nbEleves: string
  nbAccompagnateurs: string
  date: string
  duree: 'journee' | 'demi-journee'
  heureDepart: string
  heureRetour: string
  lieu: string
  gare: string
}

type Champ = keyof Valeurs | 'effectif'
type Erreurs = Partial<Record<Champ, string>>

/** Ordre de lecture du formulaire, pour placer le focus sur la première erreur. */
const ORDRE: Champ[] = [
  'niveau',
  'theme',
  'destination',
  'nbEleves',
  'nbAccompagnateurs',
  'effectif',
  'date',
  'heureDepart',
  'heureRetour',
  'lieu',
  'gare',
]

const ID: Record<Champ, string> = {
  niveau: 'fp-niveau',
  theme: 'fp-theme',
  destination: 'fp-destination',
  nbEleves: 'fp-eleves',
  nbAccompagnateurs: 'fp-accompagnateurs',
  effectif: 'fp-eleves',
  date: 'fp-date',
  duree: 'fp-duree',
  heureDepart: 'fp-heure-depart',
  heureRetour: 'fp-heure-retour',
  lieu: 'fp-lieu',
  gare: 'fp-gare',
}

/** Champs manquants renvoyés par l'API → champ du formulaire et message à afficher dessous. */
const ERREURS_SERVEUR: Record<string, { champ: Champ; message: string }> = {
  niveau: { champ: 'niveau', message: 'Classe non reconnue : choisissez-la dans la liste.' },
  theme: { champ: 'theme', message: 'Indiquez un thème ou une destination souhaitée.' },
  nb_eleves: { champ: 'nbEleves', message: "Indiquez le nombre d'élèves." },
  nb_accompagnateurs: { champ: 'nbAccompagnateurs', message: "Indiquez le nombre d'accompagnateurs." },
  date: { champ: 'date', message: 'Choisissez la date.' },
  lieu_depart: { champ: 'lieu', message: 'Lieu introuvable. Précisez, par exemple « Collège de Foix ».' },
}

function entier(texte: string): number | null {
  if (texte.trim() === '') return null
  const nombre = Number(texte)
  return Number.isInteger(nombre) && nombre >= 0 ? nombre : null
}

function valeursDepuis(d: Demande | null): Valeurs {
  return {
    niveau: d?.niveau ?? '',
    theme: d?.theme ?? '',
    destination: d?.destination_souhaitee ?? '',
    nbEleves: d?.nb_eleves?.toString() ?? '',
    nbAccompagnateurs: d?.nb_accompagnateurs?.toString() ?? '',
    date: d?.date ?? '',
    duree: d?.duree ?? 'journee',
    heureDepart: d?.heure_depart_min ?? '',
    heureRetour: d?.heure_retour_max ?? '',
    lieu: d?.lieu_depart?.libelle ?? '',
    gare: d?.gare_depart?.nom ?? '',
  }
}

/** Traduit le formulaire en `Demande`, en gardant le lieu et la gare déjà localisés s'ils n'ont pas changé. */
function construireDemande(v: Valeurs, base: Demande | null): Demande {
  const lieuTexte = v.lieu.trim()
  const lieu: LieuDepart | null = !lieuTexte
    ? null
    : base?.lieu_depart?.libelle === lieuTexte
      ? base.lieu_depart
      : { libelle: lieuTexte, lat: null, lon: null }
  const gareTexte = v.gare.trim()
  // Gare saisie à la main : l'API la retrouve par son nom (code UIC vide).
  const gare: Gare | null = !gareTexte
    ? null
    : base?.gare_depart?.nom === gareTexte
      ? base.gare_depart
      : { code_uic: '', nom: gareTexte, lat: 0, lon: 0, distance_m: null }
  const demande: Demande = {
    niveau: v.niveau || null,
    theme: v.theme.trim() || null,
    nb_eleves: entier(v.nbEleves),
    nb_accompagnateurs: entier(v.nbAccompagnateurs),
    date: v.date || null,
    duree: v.duree,
    heure_depart_min: v.heureDepart || null,
    heure_retour_max: v.heureRetour || null,
    lieu_depart: lieu,
    gare_depart: gare,
    destination_souhaitee: v.destination.trim() || null,
    champs_manquants: [],
  }
  return { ...demande, champs_manquants: champsManquants(demande) }
}

function valider(v: Valeurs): Erreurs {
  const erreurs: Erreurs = {}
  if (!v.niveau) erreurs.niveau = 'Choisissez la classe qui part.'
  if (!v.theme.trim() && !v.destination.trim()) {
    erreurs.theme = 'Indiquez un thème, ou une destination souhaitée.'
  }
  const eleves = entier(v.nbEleves)
  const accompagnateurs = entier(v.nbAccompagnateurs)
  if (eleves === null || eleves < 1) erreurs.nbEleves = "Nombre d'élèves, en chiffres."
  if (accompagnateurs === null) erreurs.nbAccompagnateurs = "Nombre d'adultes, en chiffres."
  else if (accompagnateurs < 1) erreurs.nbAccompagnateurs = 'Au moins un accompagnateur.'
  if (!erreurs.nbEleves && !erreurs.nbAccompagnateurs && eleves !== null && accompagnateurs !== null) {
    const total = eleves + accompagnateurs
    if (total > EFFECTIF_MAX) {
      erreurs.effectif = `${total} voyageurs : un groupe liO en compte ${EFFECTIF_MAX} au plus. Prévoyez deux groupes.`
    } else if (total < EFFECTIF_MIN) {
      erreurs.effectif = `${total} voyageurs : un groupe liO commence à ${EFFECTIF_MIN}, adultes compris.`
    }
  }
  if (!v.date) erreurs.date = 'Choisissez la date.'
  else if (v.date < demainIso()) erreurs.date = 'Choisissez une date à partir de demain.'
  if (v.heureDepart && v.heureRetour && v.heureRetour <= v.heureDepart) {
    erreurs.heureRetour = 'Le retour doit suivre le départ.'
  }
  if (!v.lieu.trim()) erreurs.lieu = 'Indiquez votre établissement ou sa commune.'
  return erreurs
}

/** Concatène les identifiants utiles pour aria-describedby. */
function decrire(...ids: (string | false | null | undefined)[]): string | undefined {
  const utiles = ids.filter((id): id is string => Boolean(id))
  return utiles.length > 0 ? utiles.join(' ') : undefined
}

function MessageErreur({ id, texte }: { id: string; texte: string | undefined }) {
  if (!texte) return null
  return (
    <p id={id} className="flex items-start gap-1 text-xs font-semibold text-error motion-safe:animate-entree">
      <CircleX className="mt-px size-3.5 shrink-0" aria-hidden="true" />
      {texte}
    </p>
  )
}

const CLASSE_LIBELLE = 'label whitespace-normal text-sm font-semibold text-base-content'
const CLASSE_AIDE = 'text-xs text-base-content/70'
/** Un bloc du formulaire : contour fin, légende posée sur le bord comme une étiquette. */
const CLASSE_BLOC = 'fieldset min-w-0 content-start gap-2 rounded-box border border-base-300 px-3 pb-3 pt-1'
const CLASSE_LEGENDE = 'fieldset-legend gap-1.5 px-1 text-xs font-semibold uppercase tracking-wide text-secondary'

export default function FormulaireProjet({ surEtat }: { surEtat: (etat: EtatFormulaire) => void }) {
  const navigate = useNavigate()
  const { demande, definirDemande } = useVoyage()
  const [valeurs, setValeurs] = useState<Valeurs>(() => valeursDepuis(demande))
  const [touches, setTouches] = useState<ReadonlySet<Champ>>(() => new Set())
  const [tentative, setTentative] = useState(false)
  const [erreursServeur, setErreursServeur] = useState<Erreurs>({})
  const [autresManquants, setAutresManquants] = useState<string[]>([])
  const [envoi, setEnvoi] = useState(false)
  const [erreurApi, setErreurApi] = useState<string | null>(null)
  const gareSaisieALaMain = useRef(false)
  const formulaireRef = useRef<HTMLFormElement>(null)

  // En quittant le formulaire, Tchouette retrouve son calme.
  useEffect(() => () => surEtat('repos'), [surEtat])

  const erreursClient = valider(valeurs)
  const effectifTouche = touches.has('nbEleves') || touches.has('nbAccompagnateurs')
  function erreur(champ: Champ): string | undefined {
    if (erreursServeur[champ]) return erreursServeur[champ]
    const visible = tentative || touches.has(champ) || (champ === 'effectif' && effectifTouche)
    return visible ? erreursClient[champ] : undefined
  }

  const eleves = entier(valeurs.nbEleves)
  const accompagnateurs = entier(valeurs.nbAccompagnateurs)
  const total = eleves !== null && accompagnateurs !== null ? eleves + accompagnateurs : null
  const jours = valeurs.date && !erreursClient.date ? joursAvantDepart(valeurs.date) : null
  const departProche = jours !== null && jours < DELAI_CONSEILLE_JOURS
  const niveauHorsListe =
    valeurs.niveau !== '' && !GROUPES_NIVEAUX.some((groupe) => groupe.niveaux.includes(valeurs.niveau))

  function modifier<K extends keyof Valeurs>(champ: K, valeur: Valeurs[K]) {
    const suivant: Valeurs = { ...valeurs, [champ]: valeur }
    // La gare déduite de l'ancien lieu n'est plus valable si le lieu change.
    if (champ === 'lieu' && !gareSaisieALaMain.current) suivant.gare = ''
    if (champ === 'gare') gareSaisieALaMain.current = true
    setValeurs(suivant)
    if (erreursServeur[champ]) {
      setErreursServeur((avant) => {
        const copie = { ...avant }
        delete copie[champ]
        return copie
      })
    }
    // Le billet se met à jour en direct, et la conversation repart de ces valeurs.
    definirDemande(construireDemande(suivant, demande))
  }

  function toucher(champ: Champ) {
    setTouches((avant) => (avant.has(champ) ? avant : new Set(avant).add(champ)))
  }

  async function soumettre(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault()
    if (envoi) return
    setTentative(true)
    const erreurs = valider(valeurs)
    const premiere = ORDRE.find((champ) => erreurs[champ])
    if (premiere) {
      document.getElementById(ID[premiere])?.focus()
      return
    }
    setEnvoi(true)
    setErreurApi(null)
    setAutresManquants([])
    surEtat('envoi')
    try {
      const validee = await api.validerDemande(construireDemande(valeurs, demande))
      definirDemande(validee)
      if (validee.champs_manquants.length === 0) {
        surEtat('repos')
        navigate('/destinations')
        return
      }
      const serveur: Erreurs = {}
      const autres: string[] = []
      for (const nom of validee.champs_manquants) {
        const correspondance = ERREURS_SERVEUR[nom]
        if (correspondance) serveur[correspondance.champ] = correspondance.message
        else autres.push(LIBELLES_MANQUANTS[nom] ?? nom)
      }
      setErreursServeur(serveur)
      setAutresManquants(autres)
      // Gare trouvée par l'API à partir du lieu : on l'affiche dans le champ.
      if (validee.gare_depart && !valeurs.gare.trim()) {
        gareSaisieALaMain.current = false
        setValeurs((avant) => ({ ...avant, gare: validee.gare_depart?.nom ?? '' }))
      }
      surEtat('repos')
      const premiereServeur = ORDRE.find((champ) => serveur[champ])
      if (premiereServeur) document.getElementById(ID[premiereServeur])?.focus()
    } catch (e) {
      setErreurApi(e instanceof ErreurApi ? e.message : 'La vérification a échoué. Réessayez dans un instant.')
      surEtat('erreur')
    } finally {
      setEnvoi(false)
    }
  }

  const erreurNiveau = erreur('niveau')
  const erreurTheme = erreur('theme')
  const erreurEleves = erreur('nbEleves')
  const erreurAccompagnateurs = erreur('nbAccompagnateurs')
  const erreurEffectif = erreur('effectif')
  const erreurDate = erreur('date')
  const erreurRetour = erreur('heureRetour')
  const erreurLieu = erreur('lieu')

  return (
    <form
      id={ID_FORMULAIRE_PROJET}
      ref={formulaireRef}
      onSubmit={soumettre}
      noValidate
      aria-labelledby="fp-titre"
      aria-describedby="fp-consigne"
      aria-busy={envoi || undefined}
      className="rounded-box border-2 border-secondary bg-base-100 shadow-[4px_4px_0_0] shadow-secondary"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 border-b-2 border-secondary px-3 py-2 lg:px-4">
        <h2 id="fp-titre" className="flex items-center gap-2 text-base font-bold">
          <ClipboardPen className="size-4 shrink-0" aria-hidden="true" />
          Votre sortie en quatre blocs
        </h2>
        <p id="fp-consigne" className={CLASSE_AIDE}>
          Tout est obligatoire, sauf « facultatif ».
        </p>
      </div>

      <div className="grid gap-3 p-3 md:grid-cols-2 lg:p-4">
        {/* 1. La classe */}
        <fieldset className={CLASSE_BLOC}>
          <legend className={CLASSE_LEGENDE}>
            <GraduationCap className="size-4" aria-hidden="true" />
            La classe
          </legend>
          <div className="grid grid-cols-2 gap-x-2 gap-y-2">
            <div className="flex min-w-0 flex-col gap-1">
              <label htmlFor="fp-niveau" className={CLASSE_LIBELLE}>
                Niveau
              </label>
              <select
                id="fp-niveau"
                value={valeurs.niveau}
                onChange={(e) => modifier('niveau', e.target.value)}
                onBlur={() => toucher('niveau')}
                aria-invalid={erreurNiveau ? true : undefined}
                aria-describedby={decrire(erreurNiveau && 'fp-niveau-erreur')}
                className={erreurNiveau ? 'select select-error w-full' : 'select w-full'}
              >
                <option value="" disabled>
                  Choisir
                </option>
                {niveauHorsListe && <option value={valeurs.niveau}>{valeurs.niveau}</option>}
                {GROUPES_NIVEAUX.map((groupe) => (
                  <optgroup key={groupe.groupe} label={groupe.groupe}>
                    {groupe.niveaux.map((niveau) => (
                      <option key={niveau} value={niveau}>
                        {niveau}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
              <MessageErreur id="fp-niveau-erreur" texte={erreurNiveau} />
            </div>

            <div className="flex min-w-0 flex-col gap-1">
              <label htmlFor="fp-theme" className={CLASSE_LIBELLE}>
                Thème
              </label>
              <label className={erreurTheme ? 'input input-error w-full' : 'input w-full'}>
                <BookOpen className="size-4 shrink-0 opacity-70" aria-hidden="true" />
                <input
                  id="fp-theme"
                  type="text"
                  list="fp-themes"
                  value={valeurs.theme}
                  onChange={(e) => modifier('theme', e.target.value)}
                  onBlur={() => toucher('theme')}
                  placeholder="Moyen Âge"
                  autoComplete="off"
                  aria-invalid={erreurTheme ? true : undefined}
                  aria-describedby={decrire(erreurTheme && 'fp-theme-erreur')}
                  className="min-w-0 grow"
                />
              </label>
              <datalist id="fp-themes">
                {THEMES.map((theme) => (
                  <option key={theme} value={theme} />
                ))}
              </datalist>
              <MessageErreur id="fp-theme-erreur" texte={erreurTheme} />
            </div>

            <div className="col-span-2 flex min-w-0 flex-col gap-1">
              <label htmlFor="fp-destination" className={CLASSE_LIBELLE}>
                Destination souhaitée <span className="font-normal text-base-content/70">(facultatif)</span>
              </label>
              <label className="input w-full">
                <Flag className="size-4 shrink-0 opacity-70" aria-hidden="true" />
                <input
                  id="fp-destination"
                  type="text"
                  value={valeurs.destination}
                  onChange={(e) => modifier('destination', e.target.value)}
                  placeholder="Cité de Carcassonne"
                  aria-describedby="fp-destination-aide"
                  className="min-w-0 grow"
                />
              </label>
              <p id="fp-destination-aide" className={CLASSE_AIDE}>
                Tchouette vérifie d’abord ce lieu.
              </p>
            </div>
          </div>
        </fieldset>

        {/* 2. Les voyageurs */}
        <fieldset className={CLASSE_BLOC}>
          <legend className={CLASSE_LEGENDE}>
            <Users className="size-4" aria-hidden="true" />
            Les voyageurs
          </legend>
          <div className="grid grid-cols-2 gap-x-2 gap-y-2">
            <div className="flex min-w-0 flex-col gap-1">
              <label htmlFor="fp-eleves" className={CLASSE_LIBELLE}>
                Élèves
              </label>
              <input
                id="fp-eleves"
                type="number"
                inputMode="numeric"
                min={1}
                max={EFFECTIF_MAX}
                step={1}
                value={valeurs.nbEleves}
                onChange={(e) => modifier('nbEleves', e.target.value)}
                onBlur={() => toucher('nbEleves')}
                placeholder="42"
                aria-invalid={erreurEleves || erreurEffectif ? true : undefined}
                aria-describedby={decrire(erreurEleves && 'fp-eleves-erreur', erreurEffectif && 'fp-effectif-erreur')}
                className={
                  erreurEleves || erreurEffectif ? 'input input-error w-full tabular-nums' : 'input w-full tabular-nums'
                }
              />
              <MessageErreur id="fp-eleves-erreur" texte={erreurEleves} />
            </div>

            <div className="flex min-w-0 flex-col gap-1">
              <label htmlFor="fp-accompagnateurs" className={CLASSE_LIBELLE}>
                Accompagnateurs
              </label>
              <input
                id="fp-accompagnateurs"
                type="number"
                inputMode="numeric"
                min={1}
                max={EFFECTIF_MAX}
                step={1}
                value={valeurs.nbAccompagnateurs}
                onChange={(e) => modifier('nbAccompagnateurs', e.target.value)}
                onBlur={() => toucher('nbAccompagnateurs')}
                placeholder="4"
                aria-invalid={erreurAccompagnateurs || erreurEffectif ? true : undefined}
                aria-describedby={decrire(
                  erreurAccompagnateurs && 'fp-accompagnateurs-erreur',
                  erreurEffectif && 'fp-effectif-erreur',
                )}
                className={
                  erreurAccompagnateurs || erreurEffectif
                    ? 'input input-error w-full tabular-nums'
                    : 'input w-full tabular-nums'
                }
              />
              <MessageErreur id="fp-accompagnateurs-erreur" texte={erreurAccompagnateurs} />
            </div>

            <div className="col-span-2 flex flex-col gap-1">
              <p className="flex items-baseline justify-between gap-2 text-xs">
                <span className="text-base-content/70">
                  De <span className="tabular-nums">{EFFECTIF_MIN}</span> à{' '}
                  <span className="tabular-nums">{EFFECTIF_MAX}</span> voyageurs, adultes compris
                </span>
                <span className="shrink-0 tabular-nums">
                  <strong className="text-sm">{total ?? '–'}</strong> / {EFFECTIF_MAX}
                </span>
              </p>
              <progress
                className={
                  total !== null && total > EFFECTIF_MAX
                    ? 'progress progress-error h-1.5 w-full'
                    : 'progress h-1.5 w-full'
                }
                value={total === null ? 0 : Math.min(total, EFFECTIF_MAX)}
                max={EFFECTIF_MAX}
                aria-label={
                  total === null
                    ? 'Total des voyageurs à préciser'
                    : `${total} voyageurs sur ${EFFECTIF_MAX} au maximum`
                }
              />
              <MessageErreur id="fp-effectif-erreur" texte={erreurEffectif} />
            </div>
          </div>
        </fieldset>

        {/* 3. La date et les horaires */}
        <fieldset className={CLASSE_BLOC}>
          <legend className={CLASSE_LEGENDE}>
            <CalendarDays className="size-4" aria-hidden="true" />
            La date et les horaires
          </legend>
          {/* Date et durée côte à côte seulement si le bloc est assez large (requête de conteneur) */}
          <div className="@container">
            <div className="grid grid-cols-2 gap-x-2 gap-y-2">
              <div className="col-span-2 flex min-w-0 flex-col gap-1 @xs:col-span-1">
                <label htmlFor="fp-date" className={CLASSE_LIBELLE}>
                  Date
                </label>
                <input
                  id="fp-date"
                  type="date"
                  min={demainIso()}
                  value={valeurs.date}
                  onChange={(e) => modifier('date', e.target.value)}
                  onBlur={() => toucher('date')}
                  aria-invalid={erreurDate ? true : undefined}
                  aria-describedby={decrire(erreurDate && 'fp-date-erreur', departProche && 'fp-date-alerte')}
                  className={erreurDate ? 'input input-error w-full tabular-nums' : 'input w-full tabular-nums'}
                />
                <MessageErreur id="fp-date-erreur" texte={erreurDate} />
              </div>

              <div className="col-span-2 flex min-w-0 flex-col gap-1 @xs:col-span-1">
                <label htmlFor="fp-duree" className={CLASSE_LIBELLE}>
                  Durée
                </label>
                <select
                  id="fp-duree"
                  value={valeurs.duree}
                  onChange={(e) => modifier('duree', e.target.value === 'demi-journee' ? 'demi-journee' : 'journee')}
                  className="select w-full"
                >
                  <option value="journee">Journée</option>
                  <option value="demi-journee">Demi-journée</option>
                </select>
              </div>

              <div className="flex min-w-0 flex-col gap-1">
                <label htmlFor="fp-heure-depart" className={CLASSE_LIBELLE}>
                  Départ dès
                </label>
                <input
                  id="fp-heure-depart"
                  type="time"
                  value={valeurs.heureDepart}
                  onChange={(e) => modifier('heureDepart', e.target.value)}
                  aria-describedby="fp-horaires-aide"
                  className="input w-full tabular-nums"
                />
              </div>

              <div className="flex min-w-0 flex-col gap-1">
                <label htmlFor="fp-heure-retour" className={CLASSE_LIBELLE}>
                  Retour avant
                </label>
                <input
                  id="fp-heure-retour"
                  type="time"
                  value={valeurs.heureRetour}
                  onChange={(e) => modifier('heureRetour', e.target.value)}
                  onBlur={() => toucher('heureRetour')}
                  aria-invalid={erreurRetour ? true : undefined}
                  aria-describedby={decrire('fp-horaires-aide', erreurRetour && 'fp-heure-retour-erreur')}
                  className={erreurRetour ? 'input input-error w-full tabular-nums' : 'input w-full tabular-nums'}
                />
                <MessageErreur id="fp-heure-retour-erreur" texte={erreurRetour} />
              </div>
            </div>
          </div>
          <p id="fp-horaires-aide" className={CLASSE_AIDE}>
            Horaires facultatifs : <span className="tabular-nums">{HEURE_DEPART_PAR_DEFAUT}</span> →{' '}
            <span className="tabular-nums">{HEURE_RETOUR_PAR_DEFAUT}</span> par défaut.
          </p>
          {departProche && (
            <p
              id="fp-date-alerte"
              className="flex items-start gap-1.5 rounded-field bg-warning px-2 py-1 text-xs text-warning-content motion-safe:animate-entree"
            >
              <TriangleAlert className="mt-px size-3.5 shrink-0" aria-hidden="true" />
              <span>
                <strong>Point de vigilance : </strong>
                départ dans moins de {DELAI_CONSEILLE_JOURS} jours, étude au cas par cas.
              </span>
            </p>
          )}
        </fieldset>

        {/* 4. Le départ */}
        <fieldset className={CLASSE_BLOC}>
          <legend className={CLASSE_LEGENDE}>
            <MapPin className="size-4" aria-hidden="true" />
            Le départ
          </legend>
          <div className="grid gap-y-2">
            <div className="flex min-w-0 flex-col gap-1">
              <label htmlFor="fp-lieu" className={CLASSE_LIBELLE}>
                Lieu de départ
              </label>
              <label className={erreurLieu ? 'input input-error w-full' : 'input w-full'}>
                <School className="size-4 shrink-0 opacity-70" aria-hidden="true" />
                <input
                  id="fp-lieu"
                  type="text"
                  value={valeurs.lieu}
                  onChange={(e) => modifier('lieu', e.target.value)}
                  onBlur={() => toucher('lieu')}
                  placeholder="Collège de Foix"
                  aria-invalid={erreurLieu ? true : undefined}
                  aria-describedby={decrire('fp-lieu-aide', erreurLieu && 'fp-lieu-erreur')}
                  className="min-w-0 grow"
                />
              </label>
              <p id="fp-lieu-aide" className={CLASSE_AIDE}>
                Établissement ou commune : Tchouette trouve la gare.
              </p>
              <MessageErreur id="fp-lieu-erreur" texte={erreurLieu} />
            </div>

            <div className="flex min-w-0 flex-col gap-1">
              <label htmlFor="fp-gare" className={CLASSE_LIBELLE}>
                Gare connue <span className="font-normal text-base-content/70">(facultatif)</span>
              </label>
              <label className="input w-full">
                <TrainFront className="size-4 shrink-0 opacity-70" aria-hidden="true" />
                <input
                  id="fp-gare"
                  type="text"
                  value={valeurs.gare}
                  onChange={(e) => modifier('gare', e.target.value)}
                  placeholder="Foix"
                  aria-describedby="fp-gare-aide"
                  className="min-w-0 grow"
                />
              </label>
              <p id="fp-gare-aide" className={CLASSE_AIDE}>
                Si vous préférez une gare précise.
              </p>
            </div>
          </div>
        </fieldset>

        {autresManquants.length > 0 && (
          <div role="alert" className="alert alert-warning gap-2 px-3 py-2 text-sm md:col-span-2">
            <TriangleAlert className="size-4 shrink-0" aria-hidden="true" />
            <p>
              <strong>Point de vigilance : </strong>
              il manque encore {listeEnFrancais(autresManquants)}.
            </p>
          </div>
        )}

        {erreurApi && (
          <div
            role="alert"
            className="alert alert-error alert-soft alert-vertical gap-2 px-3 py-2 text-sm sm:alert-horizontal md:col-span-2"
          >
            <CircleX className="size-4 shrink-0" aria-hidden="true" />
            <p className="min-w-0">
              <strong>La vérification n’a pas abouti.</strong> {erreurApi}
            </p>
            <button
              type="button"
              className="btn btn-sm max-lg:h-10"
              onClick={() => formulaireRef.current?.requestSubmit()}
            >
              <RotateCcw className="size-4" aria-hidden="true" />
              Réessayer
            </button>
          </div>
        )}
      </div>
    </form>
  )
}
