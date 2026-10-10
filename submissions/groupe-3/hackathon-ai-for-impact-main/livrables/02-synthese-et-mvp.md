# Synthèse des documents, besoins et périmètre du MVP

Abréviations des sources : **Fiche** = fiche de cadrage (section § et page p.), **Pitch** = pitch participants (diapo), **Notes** = `notes.md` (brief oral), **Archi** = `description_architecture.pdf`.

## 1. Tout ce que disent les documents

| # | Information | Source | Catégorie |
|---|---|---|---|
| 1 | Problématique : transformer le projet pédagogique d'un enseignant en une sortie scolaire **pertinente, réalisable, rassurante et pré-réservable** en train liO | Fiche §1 p.1, §14 p.9 ; Pitch 2 | Critère du jury |
| 2 | Logique cible : je décris mon projet → l'IA propose où aller → elle vérifie comment y aller → elle me rassure → je pré-réserve | Fiche §1 p.1 | Besoin |
| 3 | L'enseignant ne connaît pas forcément sa destination | Fiche §2 p.2 ; Pitch 3 | Besoin |
| 4 | Informations saisies : niveau, thème, élèves + accompagnateurs, date ou période, durée, horaires, lieu réel de départ, gare connue (facultatif) | Fiche §2 p.2, §10 p.6 ; Pitch 3 ; Archi | Donnée |
| 5 | L'IA trouve seule la gare de départ quand elle n'est pas renseignée | Fiche §2 p.2 | Besoin |
| 6 | La demande peut être vocale | Fiche §2 p.2 ; Pitch 3 (icône micro) | Besoin (bonus) |
| 7 | Critères de choix d'une destination : programme, intérêt culturel, activités, accès en train liO, lieu de départ, durée, sortie à la journée, horaires | Fiche §3 p.2 | Besoin |
| 8 | Plusieurs destinations à comparer avant de choisir | Fiche §3 p.2, §10 p.7 ; Pitch 2 | Besoin |
| 9 | Vérifications du trajet : trains autorisés aux groupes, horaires aller et retour, correspondances, capacité, nombre de voyageurs, horaires de l'activité, marge avant la visite, faisabilité du retour, options des autres groupes | Fiche §4 p.3 ; Pitch 2 | Contrainte |
| 10 | **Uniquement les trains liO** | Fiche §4 p.3, §13 p.8 ; Pitch 5 | Contrainte |
| 11 | Gare → site : 20 min à pied au maximum, ou réseau urbain compatible ; au-delà, point de vigilance signalé ; temps calculé pour un groupe, pas pour une personne seule | Fiche §5 p.3 ; Pitch 4 | Contrainte |
| 12 | Affichage attendu : « 📍 14 min à pied 🟢 », « 🚌 8 min en réseau urbain 🟢 », « ⚠️ 32 min à pied 🔴 alternative à rechercher » | Fiche §5 p.3 | Besoin (interface) |
| 13 | Jauge : **50 places groupe par train**, places sous option, places disponibles, nombre de groupes positionnés ; identité des autres groupes jamais communiquée | Fiche §6 p.4 ; Pitch 4, 5 | Contrainte |
| 14 | Statuts : PROPOSITION → OPTION → PRÉ-RÉSERVATION → CONFIRMATION ; une option n'est jamais présentée comme confirmée | Fiche §6 p.4 ; Pitch 4 | Contrainte |
| 15 | Une fiche récapitulative est envoyée à l'enseignant lors de l'option | Fiche §6 p.4 | Besoin |
| 16 | **Indice Confiance Voyageur Scolaire** : capacité, régularité, suppressions, horaires, accès gare → site, satisfaction, coup de cœur, adéquation pédagogique. L'enseignant doit comprendre *pourquoi* la note est attribuée | Fiche §7 p.4 ; Pitch 4 | Besoin, critère du jury |
| 17 | Données SNCF : liste des trains groupes et détail des dessertes (février à juin 2026) ; « Data hackathon » depuis janvier 2026 (fréquentation, retards, régularité, suppressions, respect de l'emport, incidents, ventes, minutes perdues) | Fiche §8 p.5 ; Annexe 3 p.13 ; Pitch 5 | Donnée |
| 18 | À croiser avec : data tourisme, ressources pédagogiques, données géographiques et de mobilité, open data SNCF | Fiche §8 p.5 ; Pitch 5 | Donnée |
| 19 | Chaîne de croisement : projet → destinations → lieu de départ → gares → trains groupes → capacité → horaires et fiabilité → gare → site → faisabilité → confiance → pré-réservation | Fiche §9 p.5 | Donnée |
| 20 | 5 écrans : Mon projet, Où aller ?, Comment y aller ?, Comparer, Pré-réserver ; charte graphique liO | Fiche §10 p.6–7 ; Pitch 6 | Besoin (interface) |
| 21 | Pré-réservation : référence de dossier et message « Demande de pré-réservation transmise — confirmation en attente » | Fiche §10 p.7 | Contrainte |
| 22 | Retour d'expérience après le voyage : 4 à 5 critères au choix, qui alimentent l'indicateur ; signal « Coup de cœur des enseignants » (ex. « 92 % recommandent ») | Fiche §11 p.7 ; Pitch 6 | Besoin, critère du jury |
| 23 | L'IA est un **copilote**, pas un moteur de recherche de trains. Elle doit savoir dire : « Cette proposition n'est pas suffisamment fiable ou adaptée à votre groupe. Voici pourquoi et voici une alternative. » | Fiche §12 p.8 ; Pitch 2 | Critère du jury |
| 24 | **Aucune disponibilité inventée, aucune réservation présentée comme confirmée, écarts signalés explicitement** | Fiche §13 p.8 ; Pitch 5 | Contrainte |
| 25 | Le prototype doit démontrer le parcours complet en 10 étapes | Fiche §14 p.9 ; Pitch 3, 6 | Critère du jury |
| 26 | Tarifs : de 10 € (6 à 10 voyageurs) à 50 € (41 à 50 voyageurs) par train | Annexe 1 p.11 | Hors périmètre (information) |
| 27 | Conditions de l'offre groupe : établissement d'Occitanie ; 6 à 50 personnes ; devis au moins **21 jours** avant ; pas de place attitrée ; trains ouverts aux groupes ; voyages **entre 9h et 16h** ; pas d'autre groupe déjà réservé sur le train, sinon cas par cas | Annexe 1 p.11 | Contrainte |
| 28 | Processus actuel : appel téléphonique, vérification dans un fichier Excel, le service production vérifie la capacité, puis acceptation ou contre-proposition | Annexe 2 p.12 | Besoin (ce qu'on remplace) |
| 29 | Heures creuses privilégiées | Annexe 2 p.12 | Contrainte |
| 30 | Données réservées au hackathon | Annexe 3 p.13 | Contrainte (ne pas publier) |
| 31 | Finalité : faire découvrir l'Occitanie autrement, mobilité responsable, fidélisation | Fiche p.1 ; Pitch 6 | Critère du jury |
| 32 | Un vrai travail d'exploration des données est attendu ; l'expérience client passe avant tout | Notes | Critère du jury (oral) |
| 33 | IA utile, utilisable, utilisée, et peu gourmande en énergie | Notes | Critère du jury (oral) |
| 34 | Réseau urbain : moins de 2 correspondances hors liO ; pas de location de bus | Notes | Contrainte (oral) |
| 35 | Pas de paiement ni de gestion des tarifs | Notes | Hors périmètre |
| 36 | L'équipe avait prévu un formulaire : thème, effectifs, période, départ, gare facultative | Archi | Décision d'équipe |

## 2. Contradictions entre documents

| # | Écart | Sources | Ce qu'on fait |
|---|---|---|---|
| C1 | L'offre groupe couvre les voyages **entre 9h et 16h**, mais l'exemple de la fiche demande un **retour avant 19h** | Annexe 1 vs Fiche §2 | On accepte les trains hors plage, avec une pastille orange « hors plage de l'offre groupe : étude au cas par cas ». Les trains de 9h à 16h passent en premier dans le tri. |
| C2 | Un seul groupe par train (sinon cas par cas), contre une jauge de 50 places partagée | Annexe 1 et 2 vs Fiche §6 | Jauge partagée, avec une pastille orange quand un autre groupe est positionné. **Décision 2 du README.** |
| C3 | Les horaires couvrent février à juin 2026, mais une sortie demandée aujourd'hui part après le 31 octobre 2026 | Annexe 3 vs règle des 21 jours | Projection par jour type. **Décision 1 du README.** |
| C4 | Réseau urbain : « moins de 2 correspondances, 1 h maximum » à l'oral, « délai compatible » à l'écrit | Notes vs Fiche §5 | On garde la règle orale comme seuil par défaut, marquée *Hypothèse*. |
| C5 | « Capacité des trains » dans les données, mais un plafond fixe de 50 places groupe | Fiche §8 vs §6, §13 | 50 est le quota groupe par train. La capacité totale et la fréquentation servent au confort (le groupe pourra-t-il s'asseoir ?) dans l'indice. |

**Points flous de `analyse-brief.md` désormais tranchés :**
- « Poser une option » : la fiche définit les 4 statuts (§6).
- « Pas de réservation » : la pré-réservation est dans le périmètre, mais elle est simulée et jamais présentée comme confirmée.
- « Qui valide ? » : un chargé de clientèle SNCF (annexe 1). Côté prototype, on simule sa réponse.

## 3. Informations manquantes

| Manque | Impact | Valeur par défaut (*Hypothèse*) |
|---|---|---|
| Catalogue des sites culturels | Pas de destination à proposer | Catalogue construit par Taha (25 à 40 sites), chaque ligne avec sa source |
| Horaires d'ouverture et capacité d'accueil des sites | Marge avant la visite, règle R10 | Horaires des sites officiels quand on les trouve, sinon « à vérifier auprès du site » |
| Options déjà posées par d'autres groupes | Jauge | Données simulées, marquées « démo » |
| Retours d'enseignants | Critère satisfaction de l'indice | Critère neutre avec la mention « pas encore de retours » ; quelques retours simulés pour la démo |
| Coordonnées des établissements scolaires | Gare de départ | Annuaire de l'éducation (open data), ou API Adresse |
| Vitesse de marche d'un groupe | Temps gare → site | Temps individuel × 1,3, plus 5 min de regroupement |
| Marge avant la visite | Contrôle des horaires | 30 min minimum |
| Pondération de l'indice | Score | Proposée dans [03-cahier-des-charges.md §5](03-cahier-des-charges.md) |
| Schéma de parcours de l'équipe | Analyse du parcours | Non fourni : on part du parcours en 10 étapes de la fiche ([04-parcours-utilisateur.md](04-parcours-utilisateur.md)) |

## 4. Les besoins de l'utilisateur

**Persona :** Sophie, professeure d'histoire-géographie dans un collège de Foix. Elle a 2 classes de 5e et peu de temps, et la sortie engage sa responsabilité devant la direction et les parents. Aujourd'hui, elle doit appeler un numéro, attendre une réponse et n'est jamais sûre que le groupe pourra monter dans le train.

| Rang | Besoin | Ce qui y répond |
|---|---|---|
| 1 | **Être sûre que tout le groupe pourra partir et revenir à l'heure** | Jauge, pastilles, train de retour, train suivant en secours |
| 2 | Trouver une sortie qui sert vraiment le programme, sans y passer des heures | 3 propositions avec l'intérêt pédagogique expliqué |
| 3 | Pouvoir justifier son choix auprès de la direction et des parents | Indice détaillé, fiche récapitulative partageable |
| 4 | Ne plus dépendre du téléphone et savoir où en est sa demande | Pré-réservation en ligne, référence, statut clair |
| 5 | Un trajet gare → site faisable avec des enfants | Temps calculé pour un groupe, pastille dédiée |

**Ce qui crée la confiance :** une note qu'on peut décomposer, des statuts honnêtes (une option n'est pas une réservation), et une IA qui sait dire non et proposer mieux.

## 5. Périmètre du MVP

| Fonctionnalité | Niveau | Justification |
|---|---|---|
| Saisie du projet en texte libre, avec un formulaire prérempli et modifiable | **Indispensable** | Étapes 1 et 2 du parcours (Fiche §14) |
| Gare de départ trouvée automatiquement | **Indispensable** | Fiche §2, demandé explicitement |
| 3 destinations issues du catalogue, avec l'intérêt pédagogique | **Indispensable** | Étape 3, cœur du rôle de l'IA |
| Trains liO groupes aller et retour, en direct | **Indispensable** | Étape 5 |
| Contrôles R1 à R10 affichés en pastilles | **Indispensable** | Étape 6, Fiche §13 |
| Jauge de pré-réservation | **Indispensable** | Une des 3 briques à soigner (Pitch 4) |
| Indice de confiance avec son détail | **Indispensable** | Une des 3 briques à soigner (Pitch 4) |
| « Pas assez fiable, voici pourquoi, voici une alternative » | **Indispensable** | Phrase citée deux fois dans les documents |
| Comparer 2 ou 3 propositions | **Indispensable** | Étape 8, écran 4 |
| Pré-réservation : référence et statut | **Indispensable** | Étape 9, écran 5 |
| Retour d'expérience qui alimente l'indice | **Indispensable** | Étape 10, attendu du prototype (Pitch 6) |
| Trajets avec une correspondance | Bonus | Utile (Foix → Carcassonne passe par Toulouse), mais coûteux à coder |
| Saisie vocale (API Web Speech du navigateur) | Bonus | Rapide à ajouter, fort effet en démo |
| Fiche récapitulative en PDF | Bonus | Fiche §6 |
| Carte du trajet (réutiliser `visualisation/carte`) | Bonus | Déjà codée par l'équipe |
| Économie de CO₂ par rapport au car | Bonus | Sert le message « mobilité durable » du pitch |
| Back-office du chargé SNCF | Feuille de route | Le prototype simule sa réponse |
| Sorties sur plusieurs destinations, nuitées | Feuille de route | Hors du temps imparti |
| Mode occitan, documents administratifs générés, liste d'attente | Feuille de route | Hors du temps imparti |
