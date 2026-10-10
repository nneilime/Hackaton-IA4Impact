# Livrables de nuit : copilote du voyage scolaire liO

Hackathon For IA, 9 et 10 octobre 2026, défi SNCF Voyageurs « Dessine-moi une mobilité durable ».
Plan établi à 3h00, **rendu à 15h30** (12 h 30 de travail).

Sources lues en entier : fiche de cadrage (13 pages), pitch participants (6 diapos), `analyse-brief.md`, `notes.md`, `description_architecture.pdf`, et le code de `visualisation/`.

## Par où commencer

| Fichier | Qui le lit | Contenu |
|---|---|---|
| [01-plan-de-nuit.md](01-plan-de-nuit.md) | **Tout le monde, maintenant** | Qui fait quoi, à quelle heure, qui dort quand |
| [02-synthese-et-mvp.md](02-synthese-et-mvp.md) | Tout le monde | Ce que disent les documents, les contradictions, les besoins, le périmètre du MVP |
| [03-cahier-des-charges.md](03-cahier-des-charges.md) | Mohamed, Taj, Khalil, Taha | Exigences, règles métier, indice de confiance, **contrat d'API** |
| [04-parcours-utilisateur.md](04-parcours-utilisateur.md) | Mohamed, Taha | Parcours corrigé, avec les cas d'erreur |
| [05-mcd-mld.md](05-mcd-mld.md) | Hamza, Taj, Mohamed | Modèle de données |
| [06-data-pipeline-eda.md](06-data-pipeline-eda.md) | Hamza, Grégorie, Taj | Pipeline et analyses à montrer au jury |
| [07-ecrans.md](07-ecrans.md) | Mohamed | Les 6 écrans, avec wireframes |

## Le scénario de démo

Tout le monde construit vers ce scénario. C'est l'exemple de la fiche de cadrage (§2, p. 2), enrichi pour montrer chaque brique demandée.

> « Je souhaite travailler avec ma classe de 5e sur le Moyen Âge. Nous sommes 42 élèves et 4 accompagnateurs. Nous souhaitons faire une sortie sur une journée, en train liO, avec un départ le matin et un retour avant 19h. Nous partons du collège de Foix. »
> Date choisie pour la démo : **jeudi 12 novembre 2026** (plus de 21 jours après aujourd'hui, comme l'exige l'offre groupe).

Ce que la démo doit montrer, dans l'ordre :

1. L'IA extrait les 7 champs et trouve seule la gare de Foix.
2. Elle propose 3 destinations Moyen Âge, toutes issues de notre catalogue.
3. Une destination est verte : gare à moins de 20 min à pied, train fiable.
4. Une destination est orange : la gare est loin du site, mais le réseau urbain la dessert. *Exemple à vérifier par Taha : la Cité de Carcassonne.*
5. Sur un train, la jauge est rouge : une option simulée d'un autre groupe ne laisse pas 46 places. L'IA le dit, explique pourquoi et propose le train suivant.
6. L'enseignant compare, puis pré-réserve. Il obtient une référence de dossier et le statut « Demande de pré-réservation transmise, confirmation en attente ».
7. Il remplit le retour d'expérience, et le critère « satisfaction » de l'indice change.

## Décisions à prendre maintenant (au kickoff de 3h00)

1. **Quelle stack ?**
   Recommandation : React + Vite + Tailwind pour le front, FastAPI en Python pour le back, SQLite comme base. L'équipe data et IA code en Python : avec FastAPI, Taj, Khalil et Taha écrivent eux-mêmes leurs endpoints, et Mohamed ne fait que le front et le branchement.

2. **Quelles dates de trains pour une sortie en novembre ?**
   Les horaires fournis couvrent février à juin 2026 (annexe 3), alors qu'une sortie demandée aujourd'hui partirait après le 31 octobre.
   Recommandation : un « jour type ». Une date demandée est ramenée au même jour de la semaine dans la période de référence, et l'écran affiche « horaires indicatifs basés sur la grille 2026 ».

3. **Deux groupes peuvent-ils partager un train ?**
   L'annexe 1 dit qu'un seul groupe est accepté par train, sinon c'est du cas par cas. La fiche (§6) montre pourtant une jauge de 50 places partagée entre groupes.
   Recommandation : faire la jauge partagée, puisque c'est elle que le jury veut voir, et ajouter une pastille orange « un autre groupe est positionné : validation au cas par cas par SNCF ».

## À faire tout de suite

Les données SNCF sont « uniquement réservées au hackathon » (annexe 3), et le repo n'a pas de `.gitignore`. Il faut ajouter `data/` au `.gitignore` avant que quelqu'un commite les fichiers.
