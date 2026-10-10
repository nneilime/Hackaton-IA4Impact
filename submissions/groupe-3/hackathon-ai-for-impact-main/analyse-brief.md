# Analyse et organisation du brief : voyages scolaires en train liO

> Synthèse des notes de cadrage du hackathon AI for Impact (brief oral + `notes.md`).

---

## 1. Vision

**Problème :** organiser une sortie scolaire en train régional liO demande beaucoup de travail aux enseignants (logistique, sécurité, coordination). Aujourd'hui, tout passe par un agent au téléphone qui vérifie à la main, dans un fichier Excel, si un groupe est déjà positionné sur un train.

**Solution :** un assistant numérique, appuyé par l'IA, qui aide les enseignants à monter un voyage culturel en train liO pour faire découvrir aux élèves les sites de leur région, **en partant du projet pédagogique et non du train**.

**Promesse de marque :** rassurant, efficace, sérieux, digne de confiance. Ce n'est pas un simple ajout, c'est le cœur du produit. Chaque fonctionnalité doit réduire l'inquiétude de l'enseignant.

**Critères d'évaluation implicites :**

- Expérience client avant tout, avec une solution technique solide derrière
- Les données ne suffisent pas : un vrai travail d'exploration (EDA) est attendu
- Une IA utile, utilisable et réellement utilisée, et qui consomme peu d'énergie
- La pertinence de la réponse par rapport au besoin de l'enseignant

---

## 2. Parcours utilisateur

1. **Entrée.** L'enseignant se connecte et identifie son école ou son collège, ce qui donne la gare de départ.
2. **Intention.** Trois cas de départ possibles :
   - une destination précise ;
   - un thème lié au programme (ex. : le Moyen Âge) ;
   - aucune idée : l'IA fait des propositions.
3. **Filtres.** Effectif, date, durée, niveau de la classe, une ou plusieurs destinations.
4. **Propositions de l'IA.** Lieux et activités en lien avec le programme, gares proches, trains autorisés, trajet complet porte à porte.
5. **Vérification.** Contrôle automatique de toutes les contraintes (voir section 3), affiché sous forme de pastilles.
6. **Validation et partage.** Récapitulatif partageable avec la direction, les parents et les collègues.
7. **Suivi.** Demande d'accord préalable transmise au service SNCF dédié : confirmation, appel, réorganisation si besoin.

---

## 3. Règles métier (les contraintes fermes)

| # | Règle | Détail |
|---|---|---|
| R1 | **Trains liO autorisés uniquement** | Liste fermée de trains désignés qui acceptent les groupes scolaires, pour éviter les heures de pointe (plus de 500 trains disponibles) |
| R2 | **50 personnes max** | Accompagnateurs compris, quelle que soit la répartition |
| R3 | **Accès école ↔ gare et gare ↔ site** | ≤ 20 min à pied **ou** réseau urbain avec ≤ 2 correspondances (hors liO) et ≤ 1 h. Pas de location de bus |
| R4 | **Places non attribuées** | Pas de réservation possible sur liO, d'où l'analyse de l'historique de fréquentation |
| R5 | **Pas de conflit de groupes** | Vérifier qu'aucun autre groupe scolaire n'est déjà positionné sur le même train (planification à moyen terme) |
| R6 | **Capacité d'accueil** | Respecter la capacité du site culturel visité |
| R7 | **Sérénité du retour** | Le trajet doit ramener tout le monde à l'école sans stress (marge de sécurité, train de secours) |

### Hors périmètre

- **Pas de réservation** de places
- **Pas de paiement** ni de gestion des tarifs (pour information : groupe scolaire à partir de 1 € par personne et par train emprunté)
- Pas de vérification des nuits d'hôtel si une nuitée est envisagée

### Données disponibles

- Liste des trains autorisés à embarquer des groupes
- Historique de fréquentation de ces trains

---

## 4. Fonctionnalités

### Indispensables

- Recherche par destination, thème du programme ou suggestion de l'IA
- Calcul du trajet complet école → gare → site → retour
- Contrôle automatique des règles R1 à R7
- **Pastilles de statut** pour savoir d'un coup d'œil si un train convient (vert / orange / rouge)
- Récapitulatif partageable (lien, PDF)

### Différenciantes

- **Indice de confiance** pour chaque proposition (fréquentation, marge, risque de conflit)
- Calendrier commun des positionnements entre écoles (anti-conflit), avec **liste d'attente**
- Demande d'**accord préalable** envoyée au service SNCF (remplace l'appel téléphonique et le fichier Excel)
- Sorties à plusieurs destinations dans la région, avec estimation du temps de trajet et de visite
- Génération automatique des documents administratifs (autorisations, formulaires)
- Calcul de l'empreinte CO2 et de l'énergie économisée par rapport au car
- Saisie écrite ou vocale
- Mode occitan
- Retour d'expérience de l'enseignant après la sortie (a-t-on pu monter, s'asseoir ?) pour enrichir les données

### IA

- Proposition de lieux et d'activités selon le thème et le niveau de la classe
- Conversation adaptative : courte si l'enseignant sait ce qu'il veut, guidée sinon
- Script économe en tokens : l'IA intervient seulement là où elle apporte quelque chose (idées, reformulation), le reste repose sur des règles déterministes (horaires, contraintes, conflits)

---

## 5. Points flous à trancher avant de coder

1. **Liaison avec la SNCF :** le terme « webhook » est technique, mais le besoin décrit est un **canal de demande et d'escalade** (accord préalable, rappel, modification). Pour le hackathon, une notification ou un e-mail simulé vers un faux service SNCF suffit.
2. **« Assurance » / « poser une option » :** s'agit-il d'une garantie que le groupe pourra monter, ou d'une simple pré-demande ? Sans réservation possible, il faut définir précisément ce que l'outil promet, sinon on crée une fausse confiance.
3. **Données :** quel est le format et la granularité de l'historique de fréquentation (par train, par jour, par tranche horaire) ? Ça détermine la qualité de l'indice de confiance.
4. **Format :** application mobile ou site web ? Pour des enseignants qui préparent depuis un ordinateur, un site web responsive semble le plus adapté.
5. **Qui valide ?** L'enseignant seul, ou un circuit avec la direction ?

---

## 6. Recommandation pour le hackathon

Le brief en fait trop pour le temps imparti. Mieux vaut tout mettre sur **un seul parcours complet et fiable** :

> Thème du programme → 3 propositions de l'IA → trajet vérifié (pastilles R1 à R7) → indice de confiance → récapitulatif partageable.

Des pastilles visibles du type « ✓ Train autorisé groupes · ✓ 42/50 personnes · ✓ Gare à 12 min à pied · ✓ Aucun autre groupe positionné » valent plus que dix fonctionnalités. C'est exactement ce qui donne la confiance demandée.

L'exploration des données de fréquentation doit apparaître dans le pitch (graphiques, trains les plus sûrs), puisque le jury l'attend explicitement.

Les sorties à plusieurs destinations, le lien avec la SNCF, le mode vocal et le mode occitan peuvent être présentés comme maquettes ou feuille de route, plutôt que développés à moitié.
