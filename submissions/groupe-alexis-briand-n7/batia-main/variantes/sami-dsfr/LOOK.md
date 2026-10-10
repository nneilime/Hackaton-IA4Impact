# Variante « look DSFR »

Copie de `chantiers/f-final` à l'enregistrement 8b5857c, habillée dans l'esprit du système de design de l'État : page blanche, surfaces gris clair, texte presque noir, bleu France pour tout ce qui structure, surfaces plates, coins de 4 à 6 px, ombres grises douces. Les couleurs de risque restent vives. Le DSFR, la police Marianne et le bloc République française sont réservés aux sites de l'État, donc rien de tout cela n'est repris et l'en-tête garde « prototype non officiel ».

## Ce qui a changé

Seulement des feuilles de style, le style de la carte et quelques constantes de couleur dans les scripts. Aucune logique, aucune donnée, aucun texte.

- `app/app.css` : les jetons de couleur de `:root` gardent leurs noms et prennent les valeurs du nouveau thème. `--brique` et ses dérivés valent le bleu France, `--papier` le blanc, `--mortier` et `--sable` des gris. Les textures `--assise` et `--grain` valent `none`. `--serif` vaut la pile sans empattement, les titres passent en gras. Les ombres en relief des pastilles et des rangs sont retirées.
- `app/palette.css` : Urgent #CE0500 et Lancer #18753C, les deux tons du DSFR pour l'erreur et le succès. Alerte et Vigilance ne bougent pas. L'étiquette À surveiller devient gris clair.
- `carte/style.mjs`, `carte/carte.css`, `carte/carte.mjs` : fond de carte gris clair, eau bleu pâle, routes blanches, repères des résidences en bleu France. La couleur « à surveiller » sur la carte est #6A6AF4 pour rester visible sur blanc.
- `rejeu/rejeu.css`, `rejeu/rejeu.mjs`, `reel/couche.mjs` : mêmes remplacements. Le bleu du rejeu reste celui d'Okabe et Ito.
- `capot/capot.css`, `capot/index.html`, `capot/capot.mjs` : la page porte ses propres jetons, redéfinis aux mêmes valeurs.
- `app/index.html`, `capot/index.html` : couleur de thème et icône en bleu.
- `app/app.mjs` : une constante d'encre pour les années passées de l'onglet Rénovations passe au bleu.

## Deuxième passe, après critique

Une critique à trois regards, premier utilisateur, langage visuel, repère de carte, a été faite sur la première version. Ce qui en est sorti et a été appliqué :

- La sensation « crémeuse » venait de l'encre brune sur l'orange et le jaune, et du jaune miel. L'encre des pastilles Alerte et Vigilance et des étiquettes DPE B à F est maintenant #161616, l'orange #F77F00, le jaune #FFCA00, le D du DPE #F2E600.
- Règle d'arrondi : plus l'élément est court, plus il est rond. Pastilles et segments en pilule, boutons et champs à 8 px, panneaux à 12 px, bordures à 1 px. Les étiquettes DPE restent carrées. La lettre de résidence devient un disque pour ne plus ressembler à une classe DPE.
- Dans la file, la catégorie est un point de couleur suivi du mot, plus une pastille pleine. Les pastilles pleines restent aux filtres et à la fiche.
- Sur la fiche, Visite est le bouton principal plein, Remplacer reste cerclé, Plus tard est un bouton texte.
- Le repère de carte est une pilule : le nombre est celui de l'onglet, les équipements à visiter, et la couleur est la pire catégorie présente. Plus de barres empilées ni de nombre de résidences. En Énergie le nombre est celui des logements de E à G, en Rénovations celui des opérations. Fichiers : `carte/carte.mjs`, `carte/carte.css`, `app/app.mjs`.
- La fiche donne les nombres derrière l'urgence : points et rang sous la catégorie, taux de pannes observé en 2025 dans la bande, points de chaque raison, ligne « Autres situations », total, seuils. `serveur.mjs` lit aussi les points négatifs et ne coupe plus les raisons à quatre.

## Troisième passe, choix de Sami

- Couleurs des catégories : badges DSFR, fond teinté et texte coloré pour les pastilles de filtre et de fiche, pilules pleines sur la carte. Urgent #CE0500, Alerte #B34000, Vigilance #C8AA39, fonds #FFE9E9, #FFE9E6, #FEECC2. Les points de la file reprennent ces couleurs.
- Étiquettes DPE : les sept couleurs de l'étiquette de 2021, A #329837 à G #E4251F, telles quelles.
- Police : Inter, vendue en local dans `carte/vendor/polices/`, la plus proche de Marianne parmi les polices libres. Source Sans 3 reste en repli.
- Haut de fiche retenu par Sami, H3 : une pilule de points dans la couleur de la bande, puis le taux observé en tuile grise à barre gauche, part en pourcentage et jauge. L'ancienne version H2, mot de la bande et encadré, reste accessible avec `?tete=h2` dans l'adresse. Captures dans `apercu/fiche-h2.png` et `apercu/fiche-h3.png`, planche d'essais dans `apercu/essais.png`.
- « Autres situations » se déplie et montre les raisons repliées avec leurs points. Le moteur sort maintenant ces raisons, colonne `autres_situations` du détail. Les boutons de décision portent leur aide, et une ligne dit ce qu'ils enregistrent.

- Un menu à trois points à droite de la recherche reprend les actions secondaires : Rejeu de 2025, Données, Méthode, et les trois exports. La barre du haut garde la marque, les trois lentilles, la bascule Kit / Réel et la recherche. L'onglet « décidé » n'apparaît qu'à partir de la première décision. Fichiers : `app/index.html`, `app/app.mjs`, `app/app.css`.

## Cinquième passe, les quatre derniers points de la critique

- Pannes : un seul grand compte en tête, puis les trois catégories en pastilles filtrantes et les autres niveaux en pilules grises qui changent d'onglet. Plus de barre d'onglets.
- Chaque ligne de la file porte ses points à droite et le numéro de logement dans la ligne de lieu.
- Énergie : les résidences sans logement au-delà du seuil sont repliées sous une ligne « Et 4 résidences sans logement de E à G ».
- Rénovations : la comparaison avec l'ordre des demandes devient deux tuiles vertes, logements G et F en 2028, et une phrase pour l'énergie.
- Téléphone : la marque et la bascule ne se chevauchent plus.

## Sixième passe, la carte d'abord

Sur la demande de Sami, l'écran se rapproche d'un plan en ligne : la carte est la page, le reste attend un clic.

- Une seule barre blanche en haut à gauche : le mot BâtIA, la recherche, le menu à trois points. Plus de bandeau bleu.
- Les trois lentilles sont des pastilles blanches à droite de la barre. La bascule Kit / Réel reste en haut à droite.
- La liste ne s'ouvre qu'au clic sur une lentille, et se referme par la croix ou en recliquant la lentille.
- À l'échelle de la métropole, chaque résidence est un point de couleur avec son nom et « 16 à visiter » en petit. La pilule à nombre ne reste que pour la métropole vue de loin.
- Corps de texte à 14 px, comptes à 30 px, plus de colonne de points dans les lignes. Les points restent sur la fiche.
- Au téléphone, la barre, puis la rangée de pastilles, puis la bascule ; la liste monte du bas au clic.

## Accessibilité et données réelles

- Les points de la carte ont une zone de clic de 44 px, invisible, et un anneau de focus visible au clavier.
- L'orange Alerte des points et des pilules passe à #E4794A, séparé du rouge Urgent à l'œil et pour les daltoniens, avec texte noir. Les badges gardent le texte #B34000 sur fond teinté, contraste 4,9. Toutes les paires texte sur fond sont au-dessus de 4,5, sauf le blanc sur le vert DPE B, remplacé par du noir.
- En données réelles, la barre reste blanche et le panneau du parc réel s'affiche même quand la liste du kit est fermée. C'était la cause du bandeau noir vide pendant l'inclinaison.

- Les boutons + et − de la carte sont en bas à droite, et se décalent quand une fiche est ouverte. Les échelles France / Sud-Ouest / Métropole vont en bas à gauche quand la liste est fermée. Sur un écran de moins de 1 300 px, les pastilles passent sous la barre et la fiche s'aligne sous elles.

## Réponses au message de Guillaume du 10 octobre midi

- Cercle de compte en haut à droite, compte de démonstration, avec deux rôles : gestionnaire de proximité, qui décide et fait les retours, et direction, qui ne voit pas les boutons de décision et arrive sur Rénovations. Le rôle est gardé dans le navigateur.
- « Mes 10 actions de la semaine » : les dix premiers équipements à visiter, chacun avec sa raison principale et le prix d'un équipement neuf, fourchette de la table des familles du kit.
- Alerte « réparer ou remplacer ? » sur la fiche quand les dépannages cumulés, à 250 € l'intervention par hypothèse, dépassent la moitié du prix neuf minimum.
- Retour terrain : après une décision, deux boutons, panne confirmée ou fausse alerte, enregistrés avec la décision et exportés.
- Réduire les animations : réglage dans le compte, en plus du réglage système, retenu par le navigateur.
- Page direction `/direction.html` : remplacement groupé ou au fil de l'eau, résidence A, hypothèses affichées.
- Non fait : import Excel par glisser-déposer, il existe un import CSV ; CO₂ évité ; copilote en langage naturel.

## Pour reporter dans f-final

Copier les fichiers des deux listes ci-dessus, y compris `serveur.mjs`, `app/app.mjs`, `carte/carte.mjs`. Les fichiers qui ne sont pas listés sont identiques à f-final à 8b5857c. Les captures avant et après sont dans `apercu/`.

## Lancer

Sur Mac ou Linux, avec Node 20 ou plus :

```bash
cd variantes/sami-dsfr
./lancer.sh
```

Sur un Mac, la marche à suivre pas à pas est dans `LANCER-MAC.md`, et `voir-batia.command` est un fichier à double-cliquer qui récupère le dépôt et lance le script.

Le script télécharge le fond de carte la première fois, environ 140 Mo, avec l'outil pmtiles du bon système, puis ouvre http://localhost:4860 dans le navigateur. `PORT=4871 ./lancer.sh` change le port, `./lancer.sh --reseau` ouvre au téléphone sur le réseau local. Sans le script : `node serveur.mjs`, après avoir fabriqué le fond à la main, car `carte/outils/extraire-fond.sh` écrit dans `carte/carte/fond` au lieu de `carte/fond` quand on le lance depuis cette copie.

## Nom et connexion, 10 octobre en début d'après-midi

- L'application s'appelle BâtIA partout : titre, barre du haut, pages Direction et Sous le capot, scripts, notes. Le fichier Mac devient `voir-batia.command`.
- Une page de connexion, `app/connexion.html`, s'ouvre avant tout le reste : identifiant, mot de passe, choix du rôle. Rien n'est vérifié ni envoyé, c'est une démonstration. Le nom tapé donne les initiales du rond en haut à droite, le rôle choisi est celui de l'application, et « Se déconnecter » ramène à cette page. `app/garde.js` fait la redirection quand aucun compte n'est en mémoire du navigateur.
- Pannes : chaque équipement de la file est une carte, badge de catégorie avec icône et score à gauche et à droite, type et lieu en gris, une phrase courte tirée des faits (dépannages et arrêts sur 12 mois, fin de durée de vie, usure signalée, plainte), date du dernier dépannage, « Voir le détail ». La carte choisie passe en bleu pâle bordé de bleu. En tête de file, un sélecteur de résidence : « Toutes les résidences · 8 » quand rien n'est choisi sur la carte, avec la mention que tout le parc est affiché ; choisir une résidence la cadre sur la carte, « Tout le parc » enlève le filtre.
- Import de données, page Données : zone de dépôt pour un classeur Excel ou un CSV. Chaque feuille est reconnue à ses colonnes et à sa clé, rangée dans l'une des 13 tables du kit, fusionnée par identifiant, puis les faits sont recalculés en JS et les scores par le barème Python, à la date du dernier relevé. Rapport ligne par ligne, feuilles ignorées dites avec la raison. Fichiers : `outils/classeur_vers_csv.py`, `outils/rescorer.py`, `risque/donnees.mjs`, `serveur.mjs`, `app/app.mjs`. Un classeur de test est dans `~/Downloads/batia-test-import.xlsx`. Le sélecteur de résidence de la file dit maintenant « aucune résidence choisie sur la carte : les 8 résidences sont affichées », sans bouton en plus.
- Vercel : `vercel.json`, `api/serveur.mjs`, `.vercelignore`, `deployer-vercel.sh`, note `DEPLOIEMENT.md`. Mot de passe serveur par `BATIA_MDP`, route `/api/connexion`, cookie douze heures. En local sans la variable, rien ne change.
