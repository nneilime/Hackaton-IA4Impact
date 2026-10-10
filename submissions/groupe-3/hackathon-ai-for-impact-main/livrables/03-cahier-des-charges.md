# Cahier des charges du MVP

## 1. Objectif

Permettre à un enseignant d'Occitanie de transformer son projet pédagogique en une sortie scolaire en train liO **pertinente, faisable, rassurante et pré-réservable**, en autonomie et sans téléphoner.

## 2. Utilisateurs

| Utilisateur | Rôle dans le MVP |
|---|---|
| Enseignant | Utilisateur principal : décrit son projet, compare les propositions, pré-réserve, donne son retour |
| Chargé de clientèle SNCF | Simulé : sa réponse (confirmation ou contre-proposition) est jouée par le système |
| Direction, parents | Lecteurs de la fiche récapitulative |

## 3. Exigences fonctionnelles

| Id | Exigence | Critère d'acceptation | Priorité |
|---|---|---|---|
| EF1 | Saisie du projet en texte libre, avec un formulaire prérempli et modifiable | L'exemple de la fiche (collège de Foix) donne les bons champs : 5e, Moyen Âge, 42 élèves, 4 accompagnateurs, journée, départ le matin, retour avant 19h, Foix | MVP |
| EF2 | Question de relance quand un champ obligatoire manque | Si le nombre d'accompagnateurs manque, une seule question est posée | MVP |
| EF3 | Gare de départ déduite du lieu de départ | « collège de Foix » donne la gare de Foix, avec la distance affichée | MVP |
| EF4 | 3 destinations proposées, **uniquement tirées du catalogue** | Aucun site hors catalogue. Chaque carte affiche l'intérêt pédagogique, les activités, le temps de trajet, l'accès gare → site et l'indice | MVP |
| EF5 | Trains aller et retour pour une destination | Uniquement des trains liO autorisés aux groupes. Arrivée au moins 30 min avant la visite, retour avant l'heure maximale | MVP |
| EF6 | Contrôles R1 à R10 affichés en pastilles | Chaque contrôle affiche un statut (vert, orange ou rouge), une icône et une phrase. La couleur n'est jamais le seul signal | MVP |
| EF7 | Jauge de pré-réservation | Affiche capacité (50), places sous option, places disponibles, nombre de groupes, jamais leur identité. Rouge si les places manquent | MVP |
| EF8 | Indice de confiance avec son détail | Score sur 100, points par critère et une phrase d'explication | MVP |
| EF9 | Alternative quand une proposition est rouge | Message « pas assez fiable, voici pourquoi » et une autre proposition (train suivant, autre date ou autre site) | MVP |
| EF10 | Comparaison de 2 ou 3 propositions | Selon les 6 critères de la fiche : intérêt pédagogique, simplicité du trajet, accessibilité, fiabilité, disponibilité, satisfaction | MVP |
| EF11 | Pré-réservation | Génère une référence de dossier et affiche « Demande de pré-réservation transmise — confirmation en attente ». Le mot « confirmé » n'apparaît jamais à ce stade | MVP |
| EF12 | Retour d'expérience | 5 critères enregistrés. À la recherche suivante, le critère satisfaction de la destination a changé | MVP |
| EF13 | Saisie vocale | Un enregistrement dicté remplit le champ texte de l'écran 1 | Bonus |
| EF14 | Fiche récapitulative en PDF ou lien partageable | Contient le trajet, les contrôles, l'indice et le statut | Bonus |
| EF15 | Trajets avec une correspondance | Foix → Carcassonne via Toulouse, avec un temps de correspondance d'au moins 10 min | Bonus |

## 4. Règles métier

| Id | Règle | Type | Source |
|---|---|---|---|
| R1 | Uniquement des trains liO autorisés aux groupes | Bloquant | Fiche §4, §13 ; Annexe 1 |
| R2 | 6 à 50 voyageurs (accompagnateurs compris), dans la limite des places restantes après les options déjà posées | Bloquant | Fiche §6, §13 ; Annexe 1 |
| R3 | Gare → site : 20 min au maximum à pied (temps de groupe), ou réseau urbain avec moins de 2 correspondances et 1 h au maximum | Vigilance (orange) au-delà | Fiche §5 ; Notes |
| R4 | Arrivée au moins 30 min avant le début de la visite | Vigilance | Fiche §4 ; *Hypothèse* pour les 30 min |
| R5 | Retour au point de départ avant l'heure maximale indiquée | Bloquant | Fiche §4 |
| R6 | Voyages entre 9h et 16h (offre groupe) | Vigilance : « étude au cas par cas » | Annexe 1 |
| R7 | Demande faite au moins 21 jours avant la date du voyage | Vigilance | Annexe 1 |
| R8 | Établissement situé en Occitanie | Bloquant | Annexe 1 |
| R9 | Un autre groupe est déjà positionné sur le train | Vigilance : « validation au cas par cas » | Annexe 1, 2 |
| R10 | Capacité d'accueil du site respectée, si elle est connue | Vigilance, ou « à vérifier » si elle est inconnue | Notes |

**Règles d'affichage, qui ne sont pas négociables :** aucune disponibilité inventée, aucune réservation présentée comme confirmée, chaque écart signalé explicitement (Fiche §13).

**Temps de marche d'un groupe** (*Hypothèse*) : temps individuel × 1,3, plus 5 min de regroupement.

## 5. Indice Confiance Voyageur Scolaire

| Critère | Points | Calcul | Données |
|---|---|---|---|
| Capacité et confort | 20 | 12 si les places disponibles couvrent le groupe avec 10 % de marge, 6 si elles le couvrent tout juste. Plus 8 × le taux de respect de l'emport | `positionnement`, `fiabilite_train` |
| Régularité | 15 | Linéaire : 0 point à 80 % de régularité, 15 points à 98 % ou plus | `fiabilite_train` |
| Risque de suppression | 10 | 10 × (1 − taux de suppression / 5 %), minimum 0 | `fiabilite_train` |
| Faisabilité des horaires | 15 | 5 pour la marge avant la visite (R4), 5 pour le retour à l'heure (R5), 5 si le trajet est dans la plage 9h-16h (R6) | `desserte`, demande |
| Accès gare → site | 15 | 15 si 20 min ou moins à pied, 10 par réseau urbain compatible, 0 au-delà | `site_culturel` |
| Adéquation pédagogique | 15 | Note de 0 à 3 donnée par le LLM à partir des thèmes et niveaux du catalogue, × 5 | Brique IA 2 |
| Satisfaction et coup de cœur | 10 | Moyenne des retours (sur 5) × 2. Sans retour : 5 points (neutre), avec la mention « pas encore de retours » | `retour_experience` |

- Les critères liés au train prennent **le moins bon des deux trains** (aller ou retour).
- **Seuils :** 80 ou plus 🟢 « Fiable » ; 60 à 79 🟠 « Faisable, avec des points de vigilance » ; moins de 60, ou une règle bloquante non respectée, 🔴 « Pas assez fiable », avec une alternative proposée.
- L'IA ne calcule pas l'indice. Le code le calcule, puis la brique IA 3 le reformule en langage clair.

Exemple d'affichage :

```text
🔐 Confiance Voyageur Scolaire : 84/100 🟢 Fiable
   Capacité et confort    18/20  46 places nécessaires, 50 disponibles
   Régularité             13/15  95 % des trains à l'heure depuis janvier
   Risque de suppression   9/10  1 suppression sur 120 circulations
   Horaires               10/15  ⚠️ retour à 17h12, hors plage de l'offre groupe
   Accès gare → site      15/15  14 min à pied pour le groupe
   Adéquation pédagogique 14/15  basilique romane, programme de 5e
   Satisfaction            5/10  pas encore de retours
```

## 6. Exigences non fonctionnelles

| Domaine | Exigence |
|---|---|
| Frugalité | 3 appels au LLM au maximum par parcours (comprendre, proposer, expliquer). Tout le reste est calculé par du code déterministe. C'est un argument du pitch (« IA peu gourmande en énergie », Notes). |
| Fiabilité | Le LLM ne produit jamais d'horaire, de disponibilité ou de score. Il reçoit les chiffres calculés et répond en JSON validé. |
| Temps de réponse | Moins de 3 s pour les étapes calculées, moins de 10 s pour les étapes avec IA, avec un message d'attente. |
| Confidentialité | Les données SNCF ne sont ni commitées (`data/` dans le `.gitignore`) ni publiées. L'identité des autres groupes n'apparaît jamais. |
| Accessibilité | Une pastille porte toujours un texte et une icône, pas seulement une couleur. Contraste suffisant, champs de formulaire avec un libellé. |
| Charte | Couleurs et logo de la charte liO (à récupérer sur lio-occitanie.fr). |
| Démo | Un mode « démo » rejoue les réponses du scénario si le réseau ou l'API du LLM tombe. |

## 7. Hors périmètre

- Paiement et tarification (information seulement : de 10 € à 50 € par train selon la taille du groupe).
- Réservation réelle et back-office SNCF.
- Nuitées, sorties sur plusieurs destinations, mode occitan, documents administratifs.
- Comptes utilisateurs : un e-mail suffit pour le suivi du dossier.

## 8. Stack et contrat d'API

### Stack recommandée

| Couche | Choix | Pourquoi |
|---|---|---|
| Front | React + Vite + TypeScript + Tailwind, Leaflet pour la carte | Rapide à monter. La carte de `visualisation/` utilise déjà Leaflet |
| Back | FastAPI (Python) | L'équipe data et IA écrit ses endpoints elle-même, sans passer par Mohamed |
| Base | SQLite (`lio.db`) | Un seul fichier, aucun serveur à installer |
| IA | Le LLM dont l'équipe a la clé, avec sorties JSON structurées | 3 appels par parcours |
| Voix | API Web Speech du navigateur | Gratuite, sans backend |
| Géographie | API Adresse (data.gouv.fr), `gares.json` (open data SNCF), temps gare → site mesurés à la main dans le catalogue | Fiable et rapide pour 25 à 40 sites |

### Contrat d'API

À figer au kickoff de 3h00. Mohamed code contre ces formats avec des mocks, les autres livrent dans ces formats.

**`POST /api/demande/analyser`** (Khalil)

```jsonc
// requête
{ "texte": "Je souhaite travailler avec ma classe de 5e sur le Moyen Âge..." }

// réponse
{
  "niveau": "5e",
  "theme": "Moyen Âge",
  "nb_eleves": 42,
  "nb_accompagnateurs": 4,
  "date": "2026-11-12",
  "duree": "journee",
  "heure_depart_min": "08:00",
  "heure_retour_max": "19:00",
  "lieu_depart": { "libelle": "Collège de Foix", "lat": 42.96, "lon": 1.61 },
  "gare_depart": { "code_uic": "87611...", "nom": "Foix", "distance_m": 900 },
  "champs_manquants": [],
  "question_relance": null
}
```

**`POST /api/destinations`** (Taha)

```jsonc
// requête : la réponse de /api/demande/analyser

// réponse
[
  {
    "site_id": "toulouse-saint-sernin",
    "nom": "Basilique Saint-Sernin",
    "commune": "Toulouse",
    "gare": { "code_uic": "87611004", "nom": "Toulouse Matabiau" },
    "interet_pedagogique": "Art roman et pèlerinages, au programme d'histoire de 5e.",
    "activites": ["Visite guidée scolaire", "Atelier architecture romane"],
    "temps_trajet_min": 75,
    "acces_gare_site": { "mode": "pied", "minutes_groupe": 18, "statut": "vert" },
    "indice_confiance": 84
  }
]
```

**`POST /api/trajets`** (Taj)

```jsonc
// requête
{ "demande": { "...": "réponse de /api/demande/analyser" }, "site_id": "toulouse-saint-sernin" }

// réponse : une liste de propositions, triées par indice décroissant
[
  {
    "proposition_id": "p1",
    "aller":  { "train": "871234", "depart": "09:12", "arrivee": "10:27", "correspondances": [] },
    "retour": { "train": "871251", "depart": "15:40", "arrivee": "16:55", "correspondances": [] },
    "jauge": { "capacite": 50, "sous_option": 0, "disponibles": 50, "groupes_positionnes": 0, "besoin": 46 },
    "marge_avant_visite_min": 45,
    "controles": [
      { "regle": "R1", "statut": "vert", "message": "Train autorisé aux groupes" },
      { "regle": "R3", "statut": "vert", "message": "Gare → site : 18 min à pied pour le groupe" },
      { "regle": "R6", "statut": "orange", "message": "Retour à 16h55, hors plage de l'offre groupe : étude au cas par cas" }
    ],
    "indice": {
      "score": 84,
      "niveau": "vert",
      "details": [ { "critere": "Régularité", "points": 13, "max": 15, "explication": "95 % à l'heure depuis janvier" } ]
    },
    "explication_ia": "Ce trajet est direct et ponctuel...",
    "alternative": null
  }
]
```

**`POST /api/pre-reservations`** (Taj)

```jsonc
// requête
{ "proposition_id": "p1", "email": "enseignant@ac-toulouse.fr" }

// réponse
{
  "reference": "LIO-2026-000123",
  "statut": "PRE_RESERVATION",
  "message": "Demande de pré-réservation transmise — confirmation en attente"
}
```

**`POST /api/retours`** (Taha)

```jsonc
// requête
{
  "reference": "LIO-2026-000123",
  "satisfaction": 5,
  "adaptation_train": 4,
  "acces_gare_site": 5,
  "confiance": 5,
  "recommande": true,
  "commentaire": "Trajet simple, élèves ravis."
}

// réponse
{ "ok": true }
```

Les numéros de train, codes UIC et coordonnées ci-dessus sont des exemples de format, pas des données réelles.
