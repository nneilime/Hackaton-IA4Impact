# Données réelles — le branchement

Le mode « Données réelles » remplace, sur la même carte, les 8 résidences fictives du kit par le parc réel d'In'li Sud-Ouest, immeuble par immeuble, avec un niveau de risque calculé sur des données publiques seulement. Tout vit dans `reel/`. Le reste de BâtIA n'est modifié qu'en quatre lignes.

> **Dans l'assemblage (`f-final`).** La bascule n'est plus créée par `monde.mjs` : elle est écrite dans l'en-tête (`#place-bascule` dans `app/index.html`), entre « Rejeu de 2025 » et « Sous le capot ». Le panneau et la fiche portent les classes du kit (`.panneau.file`, `.panneau.fiche`, `.cat`, `.ligne`, « Pourquoi », « Plus d'informations ») ; `reel.css` ne garde que ce qui diffère. L'étiquette énergie et la phrase de la 2G viennent de `regles.mjs`, la règle commune que la page « Sous le capot » doit importer. Ce qui suit décrit le branchement d'origine ; celui de l'assemblage est dans `RESULTAT.md`.

## Ce qui a été touché hors de `reel/`

| Fichier | Ajout | Rôle |
|---|---|---|
| `serveur.mjs` | 2 lignes (un commentaire et une route) | sert `/reel/*` depuis `reel/`, sauf `reel/cache/` et `reel/outils/` |
| `app/index.html` | `<link rel="stylesheet" href="/reel/reel.css">` | styles de la bascule, du panneau et de la fiche |
| `app/index.html` | `<script type="module" src="/reel/monde.mjs"></script>` | tout le reste |

Pour débrancher le mode, il suffit de retirer ces quatre lignes. Aucun fichier du kit (`donnees/`, `moteur/`, `livrables/`) n'est lu par `reel/`, et aucun fichier de `reel/` n'est lu par le kit.

## Comment le module se pose sur BâtIA

- **Lecture seule de l'application.** `monde.mjs` attend `window.foraine.carte` (exposé par `carte/`) et n'utilise que `map`, `conteneur`, `allerA` et `replacer`. Il ajoute `window.foraine.reel = { S, basculer, ouvrir, fermer, cadrer }`, qui sert aux captures et aux essais.
- **La bascule.** Le contrôle « Kit du jury / Données réelles » est en haut au centre (sous la marque sur le téléphone), avec « Prototype non officiel » juste dessous.
  - L'adresse `/?monde=reel` ouvre directement les données réelles.
- **Un monde à la fois.** En données réelles, `body.monde-reel` masque tout le kit (`reel/reel.css`) : la file, la fiche, le territoire, les outils, les lentilles, les briques des résidences (`.rv`) et les secteurs.
  - La couche `reel-*` est alors montée.
  - Au retour au kit, elle est retirée et chaque réglage du fond de carte qu'elle avait changé est remis : filtres des départements, noms, zoom maximal, bornes de la carte.
  - Les bornes (34° à 56° N) sont levées en données réelles, sinon la France ne tient pas sur un téléphone au-dessus de la feuille du bas.
- **Le moment de bascule.** La carte vole vers le Sud-Ouest et s'incline (38°). Les immeubles apparaissent en onde depuis Toulouse pendant que le compteur de logements monte, puis la carte se remet à plat.
- **Les échelles.** Les boutons France, Sud-Ouest et Métropole de BâtIA sont repris :
  - en données réelles, un clic recadre sur le parc réel, en tenant compte du panneau et de la fiche ;
  - au kit, ils retrouvent leur comportement d'origine.
- **La sélection.** Toucher un point ou une emprise émet l'événement `reel:immeuble` (`{ id, type }`) sur `carte.conteneur`. `monde.mjs` l'écoute, ouvre la fiche et vole jusqu'à l'immeuble (zoom 16,4) ou jusqu'au groupe de la commune (zoom 12,2). Échap ferme la fiche.
  - Le fond n'est détaillé qu'autour de Toulouse. Ailleurs, le vol s'arrête d'abord au zoom 11, pour que MapLibre ait une tuile parente à agrandir, puis descend au zoom 15,2 (11,6 pour un groupe).

## Les fichiers

| Fichier | Rôle |
|---|---|
| `monde.mjs` | bascule, chargement du parc, regroupement par commune, panneau du parc, branchement de la couche et de la fiche |
| `calcul.mjs` | `evaluer(fiche)` : points, niveau et raisons, dans la forme de `recherche/reel-contrat.md` ; durées de vie publiques citées |
| `couche.mjs` | `monterCouche(carte)` : points colorés par niveau aux trois échelles, emprises BDNB et bâtiments du fond à l'échelle de la rue, onde d'apparition, `reel:immeuble` |
| `fiche.mjs` | fiche courte (catégorie, étiquette et sa source, 3 raisons au plus) ; le reste derrière « Plus d'informations » ; fiche d'un groupe de commune |
| `regles.mjs` | la règle commune : `etiquetteImmeuble` (la plus fréquente des DPE de l'ADEME, avec leur nombre) et `phrase2G` |
| `reel.css` | styles, tous sous `.bascule`, `.re-*` ou `body.monde-reel` |
| `donnees/parc-reel.json` | le parc fabriqué (705 groupes de bâtiments BDNB), relu sans Internet |
| `donnees/communes.json` | centres officiels des communes, où se posent les groupes |
| `outils/fabriquer_parc.py` | fabrique `parc-reel.json` (BDNB, DPE ADEME, DGFiP, GPU, Hub'Eau, ANFR) ; cache dans `reel/cache/`, non versionné |
| `outils/communes.py` | fabrique `communes.json` (geo.api.gouv.fr) |
| `outils/captures-reel.py` | captures ordinateur et téléphone, avec blocage et comptage de toute requête hors de la machine |

## Le contrat du calcul

`evaluer(fiche)` renvoie `{ niveau, libelle, points, raisons: [{ texte, points, source }], manque }`. Les raisons sont triées de la plus lourde à la plus légère, 4 au plus. `manque` liste ce que les sources n'ont pas donné.

| `niveau` | à partir de | mot affiché | couleur |
|---|---|---|---|
| `urgence` | 70 points | Urgent | #D8231B |
| `alerte` | 48 points | Alerte | #F2711C |
| `vigilance` | 30 points | Vigilance | #F4B820 |
| `surveiller` | 15 points | À surveiller | #9CC35B |
| `calme` | — | Calme | #4F9A72 |

Les points ne s'affichent jamais : l'écran ne montre que le mot et la couleur. Le calcul estime une exposition. Il n'a jamais été vérifié sur des pannes réelles, car aucune donnée publique de pannes n'existe.

## Règles tenues

- **Un monde à la fois.** Kit et réel ne se mélangent jamais : aucune donnée du kit n'est posée sur un immeuble réel.
- **Pas de logement isolé.** Un immeuble de moins de 10 logements d'In'li, ou une maison individuelle, n'est jamais montré seul : il rejoint le groupe de sa commune, posé au centre officiel de celle-ci.
- **Vie privée.** On reste à l'échelle de l'immeuble. Le complément d'adresse des DPE n'est ni lu ni gardé, et aucune statistique de quartier n'est utilisée.
- **Sans Internet.** La démonstration ne fait aucun appel hors de la machine (0 requête bloquée lors des captures).
