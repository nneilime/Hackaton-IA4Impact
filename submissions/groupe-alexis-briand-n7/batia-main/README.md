# BâtIA : voir venir les pannes, décider quoi rénover

Prototype réalisé en 24 heures pour le défi **Action Logement / In'li Sud-Ouest** du hackathon IA for Impact, organisé par La Mêlée à l'ENSEEIHT, Toulouse, les 9 et 10 octobre 2026. Équipe : Alexis Briend, Sami Ennedoui, Daylami Affane, Clément Bergeot, Alexandre Chaufoureau, Edik Planson.

In'li Sud-Ouest n'a pas de techniciens en interne. Ses gestionnaires pilotent des prestataires. BâtIA leur dit chaque semaine quels équipements faire vérifier, pourquoi, pour combien, et donne à la direction de quoi trancher entre remplacer au cas par cas et rénover une résidence d'un coup.

## Voir l'application

Il faut Node 20 ou plus. Le fond de carte, 134 Mo, se télécharge une fois.

    git clone https://github.com/ai-for-impact-team/batia.git
    # déposer le kit du hackathon dans donnees/kit-batia/ (voir donnees/README.md)
    cd batia/variantes/sami-dsfr && ./lancer.sh

Sur Mac, le fichier `variantes/sami-dsfr/voir-batia.command` fait tout en un double-clic. Une adresse en ligne, protégée par mot de passe, est donnée à l'oral : elle sert la même version. Un compte de démonstration suffit : n'importe quel identifiant et mot de passe, puis le rôle, gestionnaire de proximité ou direction.

Parcours conseillé : la carte, la lentille Pannes, une carte d'équipement, sa fiche et ses raisons, Visite puis le retour terrain ; le rond du compte en haut à droite, les dix actions de la semaine ; le rôle direction et la page sur la résidence A ; la page Données et le dépôt d'un classeur Excel.

## Ce que fait BâtIA

**Pour le gestionnaire de proximité.** Une file des équipements à faire vérifier, classés par un score explicable. Chaque carte dit la catégorie, le score, le lieu, une phrase tirée des faits et le dernier dépannage. La fiche détaille les points de chaque raison et ce qui a été observé l'an dernier dans la même bande de score, par exemple 28 pannes sur 46. Trois décisions, Visite, Remplacer, Plus tard, puis après le passage du prestataire, Panne confirmée ou Fausse alerte. Une alerte « réparer ou remplacer » quand le cumul des dépannages approche le prix du neuf. Les dix actions de la semaine avec raison et coût.

**Pour la direction.** La page `direction.html` prend la résidence A, 160 chaudières gaz posées en 2016, et compare sur dix ans le remplacement groupé et le cas par cas : suivi de la résidence comme un ensemble, seuil de bascule, année recommandée dans l'enveloppe de 1,5 M€ et les autres opérations du plan. Les hypothèses de prix sont écrites sur la page.

**Les données.** Tout est calculé sur le kit du hackathon, rien d'autre. La page Données accepte un classeur Excel ou un CSV par glisser-déposer : chaque feuille est reconnue à ses colonnes, fusionnée par identifiant dans l'une des treize tables, puis les historiques et les scores sont recalculés. C'est le chemin prévu pour brancher un jour les vraies données.

**Au-delà du kit.** Une bascule « Données réelles » retrouve le parc réel d'In'li Sud-Ouest dans les données publiques, et la page « Sous le capot » décrit n'importe quel immeuble à partir d'une adresse avec les sources de l'État. Un rejeu de l'année 2025 montre ce que l'outil aurait vu venir.

## Défi 1 : le score de panne

Un barème à points, lisible par un technicien, pas un modèle opaque. Chaque raison pèse des points : âge rapporté à la durée de vie, commentaires d'usure du technicien, dépannages récents, panne bloquante réparée sans remplacement, demandes du locataire, visites d'entretien manquées, remplacement déjà jugé nécessaire. Le total donne une bande, Urgent, Alerte, Vigilance, À surveiller, Calme, et chaque bande affiche le taux de panne réellement observé l'an dernier. Le barème est dans `poc/preavis/moteur/BAREME.md`, la méthode dans `METHODE.md`.

Réglé sur 2024, testé sur 2025, sans regarder l'avenir : au 31 décembre 2024, le barème classe les 1 285 équipements du périmètre, puis on compte les pannes bloquantes de janvier à septembre 2025.

| | Barème BâtIA | Âge seul, comme le notebook du kit |
|---|---|---|
| AUC | 0,876 | 0,776 |
| Pannes bloquantes captées en visitant les 128 équipements les mieux classés, sur 76 | 43 | 16 |

Le livrable demandé est `livrables/defi1/score_risque_2026.csv`, calculé au 31 décembre 2025 pour les neuf mois suivants. `detail_2026.csv` donne pour chaque équipement ses raisons avec leurs points. L'application lit ce fichier et ne recalcule rien, sauf après un import.

## Défi 2 : le calendrier des rénovations

`livrables/defi2/prioriser.py` note les 29 opérations du plan d'investissement sur cinq critères, réglementaire, énergie par euro, maintenance, locataire, fin de vie, puis construit un calendrier 2026 à 2035 sous 1,5 M€ par an. Huit calendriers sont comparés, dont l'ordre chronologique des demandes. Le calendrier recommandé, `plan_recommande.csv`, sort les logements des étiquettes G et F plus vite : au 1er janvier 2028, plus aucun logement en G et 36 en F, contre 9 en G et 153 en F en suivant l'ordre des demandes, pour 2 030 MWh d'énergie primaire économisés par an contre 640. Les poids réellement exercés par chaque critère sont publiés dans `poids_effectifs.csv`.

## Ce que nous disons aussi

- Le prix d'un remplacement groupé n'est pas dans les données. La page Direction pose 20 % de moins que l'unité et le dit.
- Les seuils des bandes sont calibrés sur l'historique 2018 à 2025 du kit. De vraies données demandent une nouvelle calibration, le backtest du moteur sait la faire.
- La connexion est une démonstration en local. En ligne, un mot de passe serveur protège les données du kit.
- Non réalisés : le CO₂ évité par opération et le copilote en langage naturel.
- Aucun composant, police ni bloc de marque de l'État n'est utilisé, l'en-tête garde « prototype non officiel ».

## Ce dépôt public

Version publique du dépôt de travail de l'équipe, qui reste privé. **Les données du kit du hackathon n'y sont pas** : la règle du kit veut qu'elles ne quittent pas le cadre du hackathon. Sont donc retirés le kit lui-même, les fichiers qui en sont tirés (scores par équipement, calendriers des rénovations, rejeu 2025, page Direction précalculée), les enregistrements d'immeubles réels, les notes internes et l'historique. Le code, le barème, les scripts des livrables et les diapositives du pitch sont là ; voir `donnees/README.md` pour relancer avec le kit.

| Dossier | Contenu |
|---|---|
| `variantes/sami-dsfr/` | l'application présentée, son `README.md`, ses notes de design et de lancement |
| `livrables/defi1/`, `livrables/defi2/` | les scripts qui produisent les fichiers rendus (les fichiers eux-mêmes, tirés du kit, ne sont pas publiés) |
| `poc/preavis/moteur/` | le barème du défi 1, son backtest et sa performance |
| `pitch/effort-max/` | les diapositives du pitch (HTML, 1920 × 1080) |
| `donnees/` | vide : y déposer le kit du hackathon |
