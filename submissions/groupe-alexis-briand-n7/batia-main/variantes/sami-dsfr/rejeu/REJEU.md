# Le rejeu de 2025

Vingt secondes pour montrer que la méthode de l'équipe voit venir les pannes. On revient au 1er janvier 2025. Le barème ne connaît que ce qui était écrit avant ce jour-là ; il choisit les 128 équipements à visiter en priorité, un sur dix, et ils s'allument sur la carte. Puis janvier à septembre défilent. Chaque panne bloquante du kit tombe dans sa résidence, à sa date : un disque bleu si elle était parmi les 128 (« vue venir »), une croix vermillon sinon (« manquée »). Deux compteurs montent côte à côte : la méthode de l'équipe, et le choix des 128 équipements les plus vieux.

Toutes les données sont les données fictives du kit BâtIA. « En 2025 » s'entend dans ces données.

## Lancer

```bash
node serveur.mjs                 # puis http://localhost:4850
```

- Dans BâtIA, le bouton discret **Rejeu de 2025**, posé à droite de la barre des échelles (France, Sud-Ouest, Métropole) et à sa hauteur. Si l'attribution du fond de carte occupe cette place (écran de 1 440 px), il se pose sous la barre d'outils, en haut à droite, comme au téléphone ; en bas au centre si aucune de ces barres n'existe. Ou la touche **L**.
- Ouverture directe : `http://localhost:4850/?rejeu` lance la lecture dès que la carte est posée ; `?rejeu=pause` attend au 1er janvier.

| Touche | Effet |
|---|---|
| `L` | depuis BâtIA : ouvre le rejeu et le lance ; pendant le rejeu : recommence depuis le début |
| `Espace` (ou `K`) | lecture, pause ; à la fin, « Revoir » |
| `V` | vitesse ×1, ×2, ×0,5 |
| `→` / `←` | avance ou recule d'un mois environ (1,5 s de séquence) |
| `Début` | revient au 1er janvier, en pause |
| `Échap` | quitte le rejeu et rend BâtIA telle qu'elle était |

Pendant le rejeu, le clavier est à lui seul : `V`, `R` ou `P` ne peuvent pas décider une visite par mégarde dans la file de BâtIA.

## Le rythme (vitesse ×1)

| Instant | Ce qu'on voit |
|---|---|
| 0 à 1 s | « 1er janvier 2025 ». Les huit briques se posent : un carré par équipement, 1 285 en tout. |
| 1 à 3 s | Les 128 s'allument, du score le plus haut au plus bas, puis la zone qu'ils forment au bas de chaque brique s'entoure d'un trait bleu : là où la méthode regarde. |
| 3,8 à 16,8 s | Janvier à septembre en treize secondes. La date se lit en grand, la barre des mois avance. Chaque panne arrive avec une onde, puis sa marque reste. Les compteurs et leurs gaufres (une case par panne) montent en même temps. |
| 16,8 s | « 30 septembre 2025 ». Les équipements sans panne s'estompent : restent les zones bleues et les pannes. |
| 17,3 s | Chaque gaufre se range : les pannes vues venir d'abord. On lit d'un coup d'œil quatre rangées de dix contre une et demie. |
| 20 s | Fin : 43 sur 76 contre 16 sur 76. L'image reste ; `Espace` la rejoue. |

La lecture ne part qu'une fois la caméra posée sur la métropole et les tuiles du fond chargées (quatre secondes au plus), pour que la séquence ne se joue jamais sur un fond qui se dessine. L'horloge suit le temps réel : sur une machine qui peine, les images sont moins nombreuses, mais la séquence dure toujours vingt secondes. À l'arrêt, et sur l'image finale, rien n'est redessiné.

Dans chaque brique, les équipements sont rangés par score au 1er janvier 2025 : les visités en forment la base, comme la base de la brique de BâtIA se remplit de ce qui est à visiter. La position de la brique est celle, fictive, du secteur de la résidence dans BâtIA ; à l'intérieur, l'ordre des carrés ne désigne aucun logement.

## Couleurs et formes

- Bleu `#0072B2` pour la panne vue venir, propre au rejeu. Le vermillon d'Okabe et Ito de la panne manquée est devenu le rouge d'« Urgent » (`#D7261E`, `app/palette.css`) dans l'assemblage. Le bleu et le rouge se distinguent pour les trois formes de daltonisme, et la forme double toujours la couleur : disque pour vue venir, croix pour manquée.
- La couleur n'est jamais seule : disque plein = vue venir, croix = manquée, carré clair cerné de bleu = visite prévue. Dans les gaufres, carré plein contre croix. La légende dit les mots.
- Une voile claire atténue le fond de carte ; les cercles de secteur de BâtIA sont retirés le temps du rejeu (ils passeraient sous les briques).

## Les chiffres

`python3 rejeu/preparer.py` les recalcule depuis les CSV du kit avec le barème de `moteur/` et écrit `rejeu/donnees/rejeu-2025.json` (168 Ko). Le module n'affiche rien d'autre que ce fichier.

- Référence au 31/12/2024 : le barème ne lit que les lignes antérieures au 1er janvier 2025.
- Les 128 visites : les 10 % des 1 285 équipements du périmètre aux scores les plus hauts, ex aequo départagés par identifiant (`moteur.backtest.top10`).
- Le choix par l'âge : les 128 équipements à l'âge rapporté à la durée de vie de référence le plus haut, même départage.
- Une panne bloquante : un dépannage « Arrêt total » du 1er janvier au 30 septembre 2025. 86 dépannages de ce type touchent 76 équipements du périmètre ; chaque équipement compte une fois, à la date de sa première panne de la période, comme dans `BAREME.md`.
- Le script refait le calcul de `moteur.backtest.evaluer` et s'arrête en erreur si un compte diffère.

Résultat : 1 285 équipements, 128 visites, 76 pannes ; la méthode de l'équipe en a vu venir 43, les 128 plus vieux 16. Ce sont les chiffres de `moteur/BAREME.md`.

## Branchement dans BâtIA

> **Dans l'assemblage (`f-final`).** Le bouton d'entrée n'est plus posé en bas de l'écran : c'est « Rejeu de 2025 » dans l'en-tête, à gauche de la bascule (`#rejeu-entree`), et au téléphone au pied de la liste (`[data-rejeu]`). Le rejeu ne s'ouvre pas en données réelles, ni par le bouton ni par la touche L. `serveur.mjs` sert `/rejeu/`, sauf les `.py`. Ce qui suit décrit le branchement d'origine.

Deux lignes, rien d'autre dans le code de BâtIA :

1. `serveur.mjs` sert le dossier `rejeu/` sous `/rejeu/`, à côté de `/carte/` :
   ```js
   if (p.startsWith('/rejeu/')) { base = join(RACINE, 'rejeu'); p = p.slice('/rejeu'.length); } // rejeu de 2025 (rejeu/REJEU.md)
   ```
2. `app/index.html` charge le module après l'application :
   ```html
   <script type="module" src="/rejeu/rejeu.mjs"></script>
   ```

Le module ne dépend que de `window.foraine.carte` (l'objet rendu par `creerCarte`, déjà exposé par `app.mjs`) et des variables CSS de BâtIA, avec des valeurs de repli. Il charge sa feuille `rejeu/rejeu.css`, ajoute son bouton, écoute le clavier en phase de capture et, à l'ouverture :

- pose la classe `rejeu-actif` sur `body`, qui masque la marque, les outils, les panneaux, le territoire, les échelles et les briques de BâtIA ;
- retient la caméra, coupe les gestes de la carte et masque les couches `secteurs`, `secteurs-trait` et `secteurs-choisi` ;
- attend que BâtIA ait fini son glissement d'ouverture, puis vole vers la métropole et cadre les huit résidences dans l'espace que laisse son panneau.

À la sortie (`Échap` ou « Quitter »), il rend tout : caméra, gestes, couches, panneaux. Si une autre session renomme ces éléments de BâtIA, seule la liste de sélecteurs en tête de `rejeu.css` est à revoir.

Pour retirer le rejeu : enlever les deux lignes ci-dessus et le dossier `rejeu/`.

## Fichiers

| Fichier | Rôle |
|---|---|
| `preparer.py` | recalcule les chiffres, écrit `donnees/rejeu-2025.json` |
| `donnees/rejeu-2025.json` | les 1 285 équipements (résidence, score en points, visité, parmi les plus vieux, date de panne), les résidences et la vérification |
| `rejeu.mjs` | la séquence : briques sur un calque `canvas`, panneau, commandes, clavier |
| `rejeu.css` | le calque, le panneau, le bouton d'entrée ; projecteur, écran moyen, téléphone |
| `captures.py` | captures (début, milieu, fin) au projecteur et au téléphone ; `--video` fabrique `captures/rejeu.webm` image par image (mise en page du projecteur réduite en 1280 × 720, 6 images par seconde, ffmpeg) |

```bash
python3 rejeu/captures.py                # 6 captures dans captures/
python3 rejeu/captures.py --video        # et la vidéo de la séquence complète
```
