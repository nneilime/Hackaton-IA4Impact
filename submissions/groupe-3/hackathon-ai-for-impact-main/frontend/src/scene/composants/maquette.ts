import type {
  CarteScene,
  Demande,
  Etape,
  EtatScene,
  EvenementScene,
  PuceCritere,
  ReponseScene,
  Replique,
} from '../../api/types'

// Jeu de réponses FACTICES pour travailler la scène sans le back. Utilisé UNIQUEMENT si
// VITE_SCENE_MAQUETTE === '1' (jamais par défaut) : `installerMaquette()` répond à POST /api/scene
// à la place du réseau. Parcours : accueil -> thème -> critères (classe, effectif, date, lieu) -> destination -> fin.
// Mots magiques dans la zone de saisie : « erreur » (réponse 500) et « lent » (réponse après 4 s).

const DEMANDE_VIDE: Demande = {
  niveau: null,
  theme: null,
  nb_eleves: null,
  nb_accompagnateurs: null,
  date: null,
  duree: null,
  heure_depart_min: null,
  heure_retour_max: null,
  lieu_depart: null,
  gare_depart: null,
  destination_souhaitee: null,
  champs_manquants: [],
}

const THEMES: Record<string, string> = {
  histoire: 'Histoire',
  sciences: 'Sciences',
  nature: 'Nature',
  arts: 'Arts',
}

function dansJours(jours: number): string {
  const date = new Date()
  date.setDate(date.getDate() + jours)
  return date.toISOString().slice(0, 10)
}

function puces(demande: Demande): PuceCritere[] {
  const liste: PuceCritere[] = []
  if (demande.theme) liste.push({ cle: 'theme', libelle: 'Thème', valeur: demande.theme })
  if (demande.niveau) liste.push({ cle: 'niveau', libelle: 'Classe', valeur: demande.niveau })
  if (demande.nb_eleves !== null) {
    liste.push({
      cle: 'effectif',
      libelle: 'Voyageurs',
      valeur: String(demande.nb_eleves + (demande.nb_accompagnateurs ?? 0)),
    })
  }
  if (demande.date) liste.push({ cle: 'date', libelle: 'Date', valeur: demande.date.split('-').reverse().join('/') })
  if (demande.lieu_depart) liste.push({ cle: 'lieu', libelle: 'Départ', valeur: demande.lieu_depart.libelle })
  return liste
}

function manquants(demande: Demande): string[] {
  const liste: string[] = []
  if (!demande.theme) liste.push('le thème')
  if (!demande.niveau) liste.push('la classe')
  if (demande.nb_eleves === null) liste.push("l'effectif")
  if (!demande.date) liste.push('la date')
  if (!demande.lieu_depart) liste.push('le lieu de départ')
  return liste
}

function reponse(
  precedent: EtatScene | null,
  etape: Etape,
  demande: Demande,
  replique: string,
  reste: Partial<ReponseScene>,
  question?: string,
): ReponseScene {
  const carnet: Replique[] = [...(precedent?.carnet ?? [])]
  if (question) carnet.push({ qui: 'enseignant', texte: question })
  carnet.push({ qui: 'tchouette', texte: replique })
  const etat: EtatScene = {
    etape,
    demande,
    candidats: [],
    rang: 0,
    site_id: null,
    proposition_id: null,
    vote_code: null,
    dossier_reference: null,
    carnet,
    tours: (precedent?.tours ?? 0) + 1,
  }
  return {
    etat,
    etape,
    replique,
    humeur: 'parle',
    ancre: 'centre',
    cartes: [],
    saisie: null,
    badges: [],
    puces: puces(demande),
    manquants: manquants(demande),
    destination: null,
    proposition: null,
    detail: null,
    mode: 'demo',
    ...reste,
  }
}

const CARTES_ACCUEIL: CarteScene[] = [
  { id: 'projet', titre: 'Un projet de classe', sous_titre: 'Je pars de votre thème', icone: 'ampoule', style: 'primaire' },
  { id: 'lieu', titre: 'Un lieu en tête', sous_titre: 'Je cherche le train', icone: 'pin' },
  { id: 'surprise', titre: 'Surprenez-moi', sous_titre: 'Une idée de sortie', icone: 'etincelles' },
]

const CARTES_THEME: CarteScene[] = [
  { id: 'theme:histoire', titre: 'Histoire', sous_titre: 'Châteaux, patrimoine', icone: 'chateau' },
  { id: 'theme:sciences', titre: 'Sciences', sous_titre: 'Espace, laboratoires', icone: 'planete' },
  { id: 'theme:nature', titre: 'Nature', sous_titre: 'Faune, flore, grand air', icone: 'feuille' },
  { id: 'theme:arts', titre: 'Arts', sous_titre: 'Musées, ateliers', icone: 'palette' },
]

const CARTES_CLASSE: CarteScene[] = ['6e', '5e', '4e', '3e'].map((n) => ({
  id: `niveau:${n}`,
  titre: n,
  sous_titre: 'Collège',
  icone: 'groupe',
}))

function accueil(precedent: EtatScene | null): ReponseScene {
  return reponse(
    precedent,
    'accueil',
    DEMANDE_VIDE,
    'Bonjour ! Je suis Tchouette. Que voulez-vous préparer avec votre classe ?',
    { humeur: 'salue', ancre: 'centre', cartes: CARTES_ACCUEIL },
  )
}

function suite(etat: EtatScene, evenement: EvenementScene): ReponseScene {
  const demande = etat.demande

  if (evenement.type === 'retour') return accueil(etat)

  if (evenement.type === 'texte') {
    const mot = evenement.texte.trim().toLowerCase()
    if (mot === 'erreur') throw new Error('maquette-erreur')
    return reponse(
      etat,
      etat.etape,
      demande,
      `J'ai bien noté : « ${evenement.texte} ». Voyons la suite ensemble.`,
      { humeur: 'reflexion', ancre: 'gauche', cartes: CARTES_THEME },
      evenement.texte,
    )
  }

  if (evenement.type === 'valeur') {
    if (evenement.champ === 'effectif') {
      const suivante: Demande = {
        ...demande,
        nb_eleves: Number(evenement.valeur.eleves),
        nb_accompagnateurs: Number(evenement.valeur.accompagnateurs),
      }
      return reponse(
        etat,
        'criteres',
        suivante,
        'Parfait. Quel jour souhaitez-vous partir ?',
        {
          humeur: 'pointe',
          ancre: 'droite',
          saisie: { type: 'date', min: dansJours(21), aide: '21 jours avant, de préférence' },
        },
        `${evenement.valeur.eleves} élèves, ${evenement.valeur.accompagnateurs} accompagnateurs`,
      )
    }
    if (evenement.champ === 'date') {
      const suivante: Demande = { ...demande, date: String(evenement.valeur.date) }
      return reponse(
        etat,
        'criteres',
        suivante,
        'Noté. Et d’où part la classe ?',
        {
          humeur: 'parle',
          ancre: 'gauche',
          saisie: {
            type: 'lieu',
            suggestions: ['Toulouse Matabiau', 'Montpellier Saint-Roch', 'Perpignan', 'Carcassonne'],
          },
        },
        String(evenement.valeur.date),
      )
    }
    const suivante: Demande = {
      ...demande,
      lieu_depart: { libelle: String(evenement.valeur.lieu), lat: null, lon: null },
    }
    return destination(etat, suivante, String(evenement.valeur.lieu))
  }

  if (evenement.type === 'choix') {
    const { id } = evenement
    if (id === 'projet' || id === 'lieu' || id === 'surprise') {
      return reponse(
        etat,
        'theme',
        demande,
        'Super ! Quel thème pédagogique voulez-vous travailler ?',
        { humeur: 'pointe', ancre: 'gauche', cartes: CARTES_THEME },
        id === 'projet' ? 'Un projet de classe' : id === 'lieu' ? 'Un lieu en tête' : 'Surprenez-moi',
      )
    }
    if (id.startsWith('theme:')) {
      const theme = THEMES[id.slice(6)] ?? id
      return reponse(
        etat,
        'criteres',
        { ...demande, theme },
        `${theme}, excellent choix. Quelle est la classe ?`,
        { humeur: 'parle', ancre: 'droite', cartes: CARTES_CLASSE },
        theme,
      )
    }
    if (id.startsWith('niveau:')) {
      const niveau = id.slice(7)
      return reponse(
        etat,
        'criteres',
        { ...demande, niveau },
        'Combien de voyageurs, en comptant les accompagnateurs ?',
        { humeur: 'pointe', ancre: 'gauche', saisie: { type: 'effectif', min: 6, max: 50 } },
        `Classe de ${niveau}`,
      )
    }
    if (id === 'oui') {
      return reponse(
        etat,
        'fin',
        demande,
        'Voilà, la maquette de la scène est terminée. Le vrai parcours continue avec le trajet.',
        {
          humeur: 'celebre',
          ancre: 'centre',
          cartes: [{ id: 'recommencer', titre: 'Recommencer', sous_titre: 'Un autre projet', icone: 'retour' }],
        },
        'Je le prends',
      )
    }
    if (id === 'recommencer') return accueil(etat)
    if (id === 'non') return destination(etat, demande, 'Autre idée', true)
    if (id === 'pourquoi') {
      return reponse(
        etat,
        'destination',
        demande,
        'Parce qu’elle colle à votre thème et que le train est fiable ce jour-là.',
        { humeur: 'loupe', ancre: 'haut-droite', cartes: cartesDestination(), badges: badgesDestination() },
        'Pourquoi ce lieu ?',
      )
    }
  }

  return accueil(etat)
}

function cartesDestination(): CarteScene[] {
  return [
    { id: 'oui', titre: 'Je le prends', sous_titre: 'Voir le meilleur train', icone: 'oui', style: 'primaire' },
    { id: 'non', titre: 'Autre idée', sous_titre: 'Une autre destination', icone: 'non' },
    { id: 'pourquoi', titre: 'Pourquoi ce lieu ?', icone: 'loupe' },
    { id: 'vote', titre: 'Faire voter', sous_titre: 'Avec la classe', icone: 'qr' },
  ]
}

function badgesDestination(): ReponseScene['badges'] {
  return [
    { icone: 'chart', texte: 'À l’heure 94 %', source: 'sncf' },
    { icone: 'euro', texte: '8,40 € par élève', source: 'calcul' },
    { icone: 'database', texte: 'Site accessible', source: 'catalogue' },
    { icone: 'clock', texte: 'Départ 8:12', source: 'demo' },
  ]
}

function destination(etat: EtatScene, demande: Demande, question: string, autre = false): ReponseScene {
  return reponse(
    etat,
    'destination',
    demande,
    autre
      ? 'Voici une autre piste : la Cité de l’Espace, avec une belle correspondance à Toulouse.'
      : 'Je vous propose la Cité de Carcassonne : un train direct, et des ateliers pour votre thème.',
    { humeur: 'joie', ancre: 'haut-droite', cartes: cartesDestination(), badges: badgesDestination() },
    question,
  )
}

/** Remplace `fetch` pour POST /api/scene : à n'appeler que si VITE_SCENE_MAQUETTE === '1'. */
export function installerMaquette(): void {
  const fetchReel = window.fetch.bind(window)
  window.fetch = async (entree, options) => {
    const url = typeof entree === 'string' ? entree : entree instanceof URL ? entree.href : entree.url
    if (!url.endsWith('/api/scene') || options?.method !== 'POST') return fetchReel(entree, options)
    const corps = JSON.parse(String(options.body)) as { etat: EtatScene | null; evenement: EvenementScene }
    const lent = corps.evenement.type === 'texte' && corps.evenement.texte.trim().toLowerCase() === 'lent'
    await new Promise((fin) => setTimeout(fin, lent ? 4000 : 700))
    try {
      const resultat =
        corps.evenement.type === 'demarrer' || !corps.etat ? accueil(null) : suite(corps.etat, corps.evenement)
      return new Response(JSON.stringify(resultat), { status: 200, headers: { 'Content-Type': 'application/json' } })
    } catch {
      return new Response(JSON.stringify({ detail: 'Tchouette a raté son aiguillage (erreur simulée par la maquette).' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      })
    }
  }
}
