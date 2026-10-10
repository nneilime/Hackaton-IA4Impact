# Contrat d'API du copilote liO

Source de vérité partagée entre `backend/` (FastAPI, modèles Pydantic) et `frontend/src/api/types.ts`. Toute modification se fait ici d'abord, puis des deux côtés.

- Base : `http://localhost:8000/api` (le front passe par le proxy Vite sur `/api`).
- Format : JSON, noms de champs en `snake_case`, dates `AAAA-MM-JJ`, heures `HH:MM`, horodatages ISO 8601.
- Erreurs : statut HTTP 4xx/5xx avec `{ "detail": "message lisible en français" }`.
- Niveaux de statut partout : `"vert" | "orange" | "rouge"`.
- Données de démonstration : tant que les vrais fichiers SNCF ne sont pas chargés, l'API sert un jeu de démonstration et le dit (`GET /api/sante` → `donnees: "demo"`).

## Objets

```ts
type Niveau = "vert" | "orange" | "rouge";

interface Gare { code_uic: string; nom: string; lat: number; lon: number; distance_m?: number | null }

interface LieuDepart { libelle: string; lat: number | null; lon: number | null }

interface Demande {
  niveau: string | null;              // "5e"
  theme: string | null;               // "Moyen Âge"
  nb_eleves: number | null;
  nb_accompagnateurs: number | null;
  date: string | null;                // "2026-11-12"
  duree: "journee" | "demi-journee" | null;
  heure_depart_min: string | null;    // "08:00"
  heure_retour_max: string | null;    // "19:00"
  lieu_depart: LieuDepart | null;
  gare_depart: Gare | null;           // déduite du lieu si absente
  destination_souhaitee: string | null; // quand l'enseignant sait déjà où aller
  champs_manquants: string[];         // noms des champs obligatoires encore vides
}

interface AccesGareSite { mode: "pied" | "urbain"; minutes_groupe: number; niveau: Niveau; message: string }

interface Destination {
  site_id: string; nom: string; commune: string;
  gare: Gare;
  interet_pedagogique: string;
  activites: string[];
  themes: string[]; niveaux: string[];
  temps_trajet_min: number | null;    // trajet train depuis la gare de départ, meilleur cas
  correspondances: number;
  acces_gare_site: AccesGareSite;
  indice_confiance: number;           // 0-100, meilleur trajet trouvé
  niveau: Niveau;
}

interface Segment { train: string; gare_depart: string; gare_arrivee: string; depart: string; arrivee: string }

interface Trajet { segments: Segment[]; depart: string; arrivee: string; duree_min: number; correspondances: number }

interface Jauge { capacite: number; sous_option: number; disponibles: number; groupes_positionnes: number; besoin: number; niveau: Niveau }

interface Controle { regle: string; libelle: string; niveau: Niveau; message: string }

interface CritereIndice { critere: string; points: number; max: number; explication: string }

interface Indice { score: number; niveau: Niveau; details: CritereIndice[] }

interface Proposition {
  proposition_id: string;
  site_id: string;
  date: string;
  aller: Trajet;
  retour: Trajet;
  jauge_aller: Jauge;
  jauge_retour: Jauge;
  marge_avant_visite_min: number;
  controles: Controle[];
  indice: Indice;
  explication_ia: string;             // phrase claire, jamais d'horaire ou de place inventés
  est_alternative: boolean;
  remplace: string | null;            // proposition_id de la proposition rouge qu'elle remplace
}

type Statut = "OPTION" | "PRE_RESERVATION" | "CONFIRMATION" | "CONTRE_PROPOSITION" | "ANNULE";

interface EtapeDossier { statut: Statut; date: string; message: string }

interface Dossier {
  reference: string;                  // "LIO-2026-000123"
  statut: Statut;
  message: string;                    // ex. "Demande de pré-réservation transmise — confirmation en attente"
  email: string;
  demande: Demande;
  site: Destination;
  proposition: Proposition;
  historique: EtapeDossier[];
  cree_le: string;
}

interface MessageChat { role: "user" | "assistant"; content: string }
```

## Routes

| Méthode et route | Corps envoyé | Réponse | Rôle |
|---|---|---|---|
| `GET /api/sante` | — | `{ ok: true, mode: "llm" \| "demo", donnees: "demo" \| "sncf" }` | État de l'API, affiché discrètement dans le front |
| `POST /api/chat` | `{ messages: MessageChat[], demande: Demande \| null }` | `{ reponse: string, demande: Demande, complete: boolean, suggestions: string[], mode: "llm" \| "demo" }` | Conversation avec Tchouette. Remplit la `Demande` au fil des messages. `complete` passe à `true` quand les champs obligatoires sont remplis. `suggestions` = 2 à 4 réponses rapides cliquables |
| `POST /api/demande/valider` | `{ demande: Demande }` (champs saisis dans le formulaire) | `Demande` | Chemin formulaire : géocode le lieu, trouve la gare, recalcule `champs_manquants` |
| `POST /api/destinations` | `{ demande: Demande }` | `{ destinations: Destination[], message: string }` | 3 destinations au plus, tirées du catalogue uniquement. Si `destination_souhaitee` est remplie, elle passe en premier |
| `POST /api/trajets` | `{ demande: Demande, site_id: string }` | `{ site: Destination, propositions: Proposition[], message: string }` | Propositions triées par indice décroissant. Une proposition rouge est suivie de son alternative (`est_alternative: true`) |
| `POST /api/pre-reservations` | `{ proposition_id: string, email: string, demande: Demande }` | `Dossier` | Pose une OPTION puis transmet la demande : statut `PRE_RESERVATION`. Jamais `CONFIRMATION` à ce stade |
| `GET /api/pre-reservations/{reference}` | — | `Dossier` | Suivi du dossier |
| `POST /api/pre-reservations/{reference}/simuler-reponse` | `{ decision: "confirmer" \| "contre-proposition" }` | `Dossier` | Démo : simule la réponse du chargé de clientèle SNCF |
| `POST /api/retours` | `{ reference, satisfaction, adaptation_train, acces_gare_site, confiance, recommande, commentaire }` (notes de 1 à 5, `recommande` booléen) | `{ ok: true, indice_avant: number, indice_apres: number, message: string }` | Retour d'expérience, qui fait évoluer le critère satisfaction de l'indice du site |

## Champs obligatoires de la `Demande`

`niveau`, `theme` (sauf si `destination_souhaitee` est remplie), `nb_eleves`, `nb_accompagnateurs`, `date`, `lieu_depart`. Les autres ont une valeur par défaut : `duree = "journee"`, `heure_depart_min = "08:00"`, `heure_retour_max = "18:00"`.

## Vote en classe (v2)

L'enseignant fait voter sa classe entre les destinations proposées. Il projette un QR code ; les élèves le scannent avec leur téléphone (même réseau Wi-Fi) et votent. Les votes sont anonymes : aucun prénom, seulement un identifiant aléatoire stocké dans le navigateur de l'élève pour éviter les doubles votes (un élève peut changer d'avis tant que le vote est ouvert).

```ts
interface OptionSondage {
  site_id: string;
  nom: string;
  commune: string;
  interet_pedagogique: string;
  indice_confiance: number;
  niveau: Niveau;
  votes: number;
}

interface Sondage {
  code: string;                       // 6 caractères sans ambiguïté, ex. "TCH4K7"
  titre: string;                      // ex. "Où part la 5e pour le Moyen Âge ?"
  statut: "ouvert" | "ferme";
  options: OptionSondage[];           // dans l'ordre des destinations proposées
  total_votes: number;
  gagnant: string | null;             // site_id, renseigné à la fermeture (égalité : meilleur indice)
  cree_le: string;
}
```

| Méthode et route | Corps envoyé | Réponse | Rôle |
|---|---|---|---|
| `POST /api/sondages` | `{ demande: Demande, destinations: Destination[] }` | `Sondage` | Crée le vote : au moins 2 destinations (sinon 422), seules les 4 premières sont gardées |
| `GET /api/sondages/{code}` | — | `Sondage` | Lecture (le front de l'enseignant interroge toutes les 2 s) ; 404 si code inconnu |
| `POST /api/sondages/{code}/votes` | `{ site_id: string, votant_id: string }` | `Sondage` | Vote ou change de vote ; 409 `{detail}` si le vote est fermé, 422 si `site_id` n'est pas dans le vote |
| `POST /api/sondages/{code}/fermer` | — | `Sondage` | Ferme le vote et désigne le gagnant |
| `GET /api/reseau` | — | `{ ip_locale: string \| null }` | Adresse IP de la machine sur le réseau local, pour fabriquer l'URL du QR code quand le site est ouvert sur `localhost` |

## Scène « Tchouette est l'interface » (v3)

Une seule route pilote tout le parcours conversationnel : `POST /api/scene`. Le back est une **machine à états** (les étapes ne sautent jamais) ; le front est **sans logique métier** : il envoie un événement, reçoit la réplique, les cartes, l'humeur et la position de Tchouette, et les affiche. L'état est **renvoyé par le front à chaque tour** (le back ne garde pas de session) : `etat` est opaque pour l'UI, qui le stocke tel quel (sessionStorage) et le renvoie.

```ts
type Etape =
  | "accueil"      // scène 1 : bienvenue, 3 portes d'entrée
  | "theme"        // scène 2a : choix du thème par grandes cartes
  | "criteres"     // scène 2b : un critère à la fois (classe, effectif, date, lieu, horaires)
  | "destination"  // scène 3a : UNE destination à la fois
  | "trajet"       // scène 3b : le meilleur trajet pour la date demandée
  | "vote"         // scène 4 : vote de la classe (QR code)
  | "prereservation" // scène 5
  | "fin";

type HumeurScene = "repos" | "reflexion" | "parle" | "joie" | "inquiete" | "salue" | "pointe" | "loupe" | "celebre";
type AncreScene = "centre" | "gauche" | "droite" | "haut-droite" | "bas-droite";

interface EtatScene {
  etape: Etape;
  demande: Demande;                  // critères recueillis (type existant)
  candidats: string[];               // site_id proposés, dans l'ordre
  rang: number;                      // index du candidat présenté (0-based)
  site_id: string | null;            // destination acceptée
  proposition_id: string | null;     // trajet accepté
  vote_code: string | null;
  dossier_reference: string | null;
  carnet: Replique[];                // 30 dernières répliques (carnet de voyage)
  tours: number;
}

interface Replique { qui: "tchouette" | "enseignant"; texte: string }

type EvenementScene =
  | { type: "demarrer" }
  | { type: "texte"; texte: string }                       // saisie écrite ou voix
  | { type: "choix"; id: string }                          // clic sur une carte
  | { type: "valeur"; champ: "effectif" | "date" | "lieu_depart"; valeur: Record<string, string | number> }
  | { type: "retour" }                                     // revenir à l'étape précédente
  | { type: "vote_termine"; site_id: string }              // la classe a voté (le front a clos le sondage)
  | { type: "prereservation_faite"; reference: string }    // le front a appelé POST /api/pre-reservations
  | { type: "soumettre_vote"; ids: string[] };             // étape destination : 1 id = choix direct (→ trajet), 2 à 4 = vote de la classe

// Icônes : jeu FERMÉ de clés, le front les associe à des icônes lucide-react.
type IconeScene = "chateau" | "os" | "colonnes" | "planete" | "feuille" | "palette" | "ampoule" | "pin"
  | "etincelles" | "train" | "qr" | "coeur" | "oui" | "non" | "retour" | "loupe" | "calendrier" | "groupe";

interface CarteScene {
  id: string;                        // renvoyé tel quel dans { type: "choix", id }
  titre: string;                     // 1 à 4 mots
  sous_titre?: string;               // une ligne
  icone?: IconeScene;
  style?: "primaire" | "neutre";     // une seule carte primaire (action dominante) par réplique
}

type Saisie =
  | null
  | { type: "effectif"; min: 6; max: 50; eleves?: number; accompagnateurs?: number }
  | { type: "date"; min: string; aide?: string }           // min = AAAA-MM-JJ ; aide : « 21 jours avant, de préférence »
  | { type: "lieu"; suggestions: string[] };

interface BadgeSource {
  icone: "chart" | "database" | "shield" | "train" | "pin" | "euro" | "users" | "clock";
  texte: string;                     // ex. « À l'heure 94 % »
  source: "sncf" | "datatourisme" | "catalogue" | "calcul" | "demo";  // affichée en petit : « SNCF 2026 », « DATAtourisme »…
}

interface PuceCritere { cle: string; libelle: string; valeur: string }   // « Classe · 5e », « Voyageurs · 46 »

interface DetailScene {              // « Pourquoi ce train ? » : affiché UNIQUEMENT à la demande
  titre: string;
  lignes: { libelle: string; valeur: string; niveau: Niveau | null }[];
}

interface ReponseScene {
  etat: EtatScene;
  etape: Etape;
  replique: string;                  // UNE réplique, 25 mots au plus
  humeur: HumeurScene;
  ancre: AncreScene;                 // où se place Tchouette
  cartes: CarteScene[];              // 0 à 4
  saisie: Saisie;
  badges: BadgeSource[];             // la donnée utilisée pour CETTE réplique (0 à 4)
  puces: PuceCritere[];              // critères déjà recueillis
  manquants: string[];               // libellés lisibles des critères restants
  destination: Destination | null;   // renseignée aux étapes destination / trajet / vote / prereservation
  proposition: Proposition | null;   // renseignée aux étapes trajet / vote / prereservation
  detail: DetailScene | null;        // renseigné après le choix « pourquoi »
  mode: "llm" | "demo";
  choix_destinations: Destination[]; // étape destination : les candidates à cocher (dans l'ordre de etat.candidats), sinon []
  carte: CarteGeo | null;            // étapes destination et vote (null si coordonnées manquantes)
}

interface PointCarte { lat: number; lon: number; libelle: string; type: "depart" | "arrivee" | "destination" | "candidate"; numero?: number; actif: boolean }
interface CarteGeo { centre: [number, number]; zoom: number; points: PointCarte[]; traces: [number, number][][] } // traces[0] = marche gare → site actif
```

| Route | Corps | Réponse | Rôle |
|---|---|---|---|
| `POST /api/scene` | `{ etat: EtatScene \| null, evenement: EvenementScene }` | `ReponseScene` | Un tour de dialogue. `etat: null` + `demarrer` = nouvelle conversation |

**Garanties du back** :
- `texte` libre en mode `llm` : le modèle comprend et reformule, **jamais** il n'invente un horaire, une place, un lieu : il appelle des outils branchés sur les services existants. Mode `demo` (sans clé) : parseur à règles + réponses scriptées, le parcours doit s'achever sans LLM.
- Une humeur et une ancre sont **toujours** renvoyées ; `replique` ≤ 25 mots, vouvoiement, jamais « réservé » ou « confirmé » avant la vraie confirmation.
- `badges` ne contient que des chiffres réellement calculés. Les données de démonstration sont marquées `source: "demo"`.
- Une destination dont l'indice est calculé à la **date demandée** (jamais le meilleur indice toutes dates confondues) ; un trajet bloqué (règle bloquante) n'est jamais présenté comme « meilleur » : Tchouette dit « pas assez fiable, voici pourquoi » et propose l'alternative.
- Toute destination issue de DATAtourisme a un `site_id` préfixé `dt-` ; le front affiche alors l'étiquette « Découverte » (info à vérifier auprès du site).
- Un événement impossible pour l'étape courante renvoie 409 `{detail}` en français.

**Vote** : quand l'enseignant choisit « Faire voter la classe » (carte `vote`), le **back crée le sondage** (service `sondages`, avec les candidats de l'état) et renseigne `etat.vote_code`. Le front affiche alors QR code et course avec les routes « Vote en classe » existantes (`GET /api/sondages/{code}`), clôt avec `POST /api/sondages/{code}/fermer`, puis envoie `vote_termine` avec le `site_id` gagnant : la scène enchaîne sur le trajet de cette destination. **Sélection multiple** : à l'étape destination, l'enseignant coche 1 à 4 candidates (parmi `etat.candidats`) et envoie `soumettre_vote {ids}`. 1 id : même effet que « Celle-ci ! » (étape trajet). 2 à 4 ids : le back crée le sondage limité à ces destinations (`etat.vote_code`, étape vote). Un id hors candidates → 409. **Saisie manuelle** (classes trop jeunes pour un téléphone) : `POST /api/sondages/{code}/votes-manuels {votes: {site_id: n}}` remplace la saisie précédente ; refus 422 si site inconnu, nombre négatif, ou saisie + votes QR > effectif de la classe ; 409 si le vote est clos. `Sondage` et `OptionSondage` exposent `votes` (total), `votes_qr`, `votes_manuels` ; `Sondage.effectif`. Égalité : l'indice de confiance départage. **Pré-réservation** : le front appelle `POST /api/pre-reservations`, puis envoie `prereservation_faite`.

## Trajet modifiable et dates proches (ajout)

`ReponseScene` gagne deux champs : `alternatives` (étape `trajet`, `{aller: OptionHoraire[], retour: OptionHoraire[]}`, 2 à 5 circulations faisables par sens, calculées par le serveur avec les mêmes contrôles R1–R10 ; chaque option : `id` (numéros de train joints par `+`), `depart`, `arrivee`, `duree_min`, `correspondances`, `places_disponibles` (≤ 50, options comprises), `besoin`, `niveau`, `score`, `actuel`) et `dates_proches` (`DateProche[]`, vide sauf si aucun train à la date demandée).

Nouveaux événements `{type:"choix", id}` à l'étape `trajet` : `changer_aller:<id>`, `changer_retour:<id>` (l'id doit appartenir aux options renvoyées, sinon 409 ; le retour respecte `heure_retour_max`), `retour_etape` (= `retour`, l'état est conservé), `choisir_date:AAAA-MM-JJ` (la date doit figurer dans `dates_proches`, sinon 409 ; relance le parcours avec cette date).

`POST /api/dates-proches` : `{date, gare_depart (UIC ou nom), site_id | gare_arrivee, effectif, heure_retour_max?, heure_depart_min?}` -> `{date_demandee, propositions: [{date, ecart_jours (signé), aller, retour, niveau, score}]}` (2 à 3 dates, fenêtre ±21 jours, jours ouvrés hors fériés fixes, jamais dans le passé).
