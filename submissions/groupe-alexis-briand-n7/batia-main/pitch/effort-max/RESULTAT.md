# Les diapositives du pitch BâtIA : résultat

Ouvrir `index.html` dans un navigateur (ou `python3 -m http.server 4980 --bind 127.0.0.1` puis http://127.0.0.1:4980/). Flèches gauche et droite pour avancer, **F** pour le plein écran, `#5` à la fin de l'adresse pour arriver directement sur une diapositive (utile pour revenir de la démo sur la 6, puis repartir). Tout est local : polices, images, script. Aucune connexion n'est nécessaire.

Livrables : `index.html` (scène fixe 1920 × 1080), `diapositives.pdf` (9 pages en 1920 × 1080), `apercus/diapositive-01.png` à `-09.png`. Le script `scripts/exporter.py` (Playwright pour Python) refait le PDF et les aperçus : `python3 scripts/exporter.py` pendant que le serveur tourne sur le port 4980.

## Le style choisi : « Panneaux sur la ville »

Le style reprend la grammaire de l'application Foraine : l'application pose des panneaux blancs aux coins arrondis sur une carte plein écran ; les diapositives posent les mêmes panneaux blancs (rayon 12 px, ombre douce) sur une photo plein écran, voilée de bleu nuit. Les couleurs sont celles de l'application : bleu profond #000091, bleu pâle #E3E3FD, gris très clair #F6F6F6, texte #161616, pastilles Urgent, Alerte et Vigilance, étiquettes énergie officielles de A à G.

- **Texte** : Inter, la police de l'application (fichiers de `matiere/polices/`).
- **Titres et chiffres** : Archivo, en largeur étroite et graisse 800 (licence OFL, téléchargée chez Google Fonts et rangée dans `fonts/`). C'est une grotesque de la même famille qu'Inter, mais étroite et dense comme une façade : les gros chiffres tiennent sur une ligne et se lisent du fond de la salle.
- **Rythme** : on alterne fonds photo sombres (1, 2, 7, 8, 9), fonds clairs proches de l'application (3, 5, 6) et un fond bleu plein quadrillé comme un plan (4), pour que chaque diapositive se reconnaisse d'un coup d'œil derrière les orateurs.
- **Pourquoi celui-là** : trois directions ont été pesées, sans aperçus rendus faute de temps. Un style éditorial clair, très sage, aurait été trop proche d'un rapport. Un style sombre et néon aurait trahi la direction artistique de l'application. Ce style-ci reste de la même famille que la démo, ce qui rend la bascule vers l'application et le retour sans à-coup.

Choix notables :
- **Diapositive 2, l'avis** : la capture n'est pas posée au milieu. On en garde deux bandes recadrées (étoile, date, titre « Inaction totale ! », puis la phrase sur la chaudière en panne) dans un panneau légèrement incliné au bord déchiré. Une pastille rouge « Urgent » de l'application porte le « 9 °C à l'intérieur », et la dernière phrase du locataire est reprise en grand. Le prénom et les initiales sont hors cadre. La date d'expérience et la température extérieure (absentes de `CHIFFRES.md`) sont aussi hors cadre ou masquées.
- **Diapositive 3, l'équipe** : chaque emplacement charge `photos/<prenom>.jpg` s'il existe (testé avec une image factice, recadrage propre), sinon un motif neutre de plan quadrillé portant l'initiale du prénom.
- **Diapositive 4, les outils** : la manière de travailler est montrée comme trois pistes d'agents en parallèle dont une seule est retenue. Les nombres d'`OUTILS.md` (directions, analyses, versions) ne sont pas affichés, car ils ne figurent pas dans `CHIFFRES.md`.
- **Diapositive 5, la démo** : une capture de l'application recadrée sur la barre d'outils et la carte, sans aucun chiffre (la bulle « 139 à visiter » est hors cadre), plus les pastilles et les étiquettes énergie, qui montrent les choix artistiques.
- **Diapositive 6** : vide, avec seulement le titre discret « Le scoring des données du kit » et le pied de page, pour Sami.
- **Diapositive 7, les résultats** : trois chiffres (loyers sauvés, énergie, pannes évitées aux locataires) et la projection sur In'li Sud-Ouest, chacun avec sa mention entre parenthèses.

## Les photos et leurs sources

Toutes viennent de **Pexels** (licence Pexels, usage libre). Unsplash refusait les téléchargements depuis cette machine (erreur 401). Le détail est dans `CREDITS.md`.

| Fichier | Diapositive | Ce qu'elle montre | Page de la photo |
|---|---|---|---|
| `images/titre.jpg` | 1 | Façade géométrique en damier bleu, sur un ciel uni (Jan van der Wolf) | https://www.pexels.com/photo/blue-glass-facade-of-modern-building-18193138/ |
| `images/froid.jpg` | 2 | Givre sur une vitre (Алена) | https://www.pexels.com/photo/frost-pattern-on-glass-20740356/ |
| `images/chaufferie.jpg` | 7 | Local technique, tuyaux et machines (Jonathan Cooper) | https://www.pexels.com/photo/blue-industrial-machine-under-building-pipes-10290629/ |
| `images/facade.jpg` | 8 | Façade de logements, balcons répétés (Victor Moragriega) | https://www.pexels.com/photo/symmetrical-urban-building-facade-with-balconies-28952340/ |
| `images/nuit.jpg` | 9 | Immeuble la nuit, fenêtres éclairées (Alexey Demidov) | https://www.pexels.com/photo/apartment-building-at-night-10562341/ |

Une photo des toits de Paris, avec la tour Eiffel, a été téléchargée puis écartée : elle était hors sujet pour un pitch toulousain sur le Sud-Ouest. Aucune photo n'est légendée ni présentée comme une résidence du kit. Il n'y a aucun logo, aucune image de Google Maps, et la capture de la diapositive 5 vient de l'application elle-même (fond Protomaps et OpenStreetMap).

Autres fichiers : `assets/avis-*.png` (bandes recadrées de `matiere/avis-trustpilot.png`), `assets/demo-carte.jpg` (recadrage de `matiere/demo/demo-1-carte-sud-ouest.png`), `fonts/` (Inter et Archivo, licence OFL).

## Ce qui reste à faire

1. **Les photos de l'équipe** : déposer `alexis.jpg`, `sami.jpg`, `daylami.jpg`, `clement.jpg`, `alexandre.jpg` et `edik.jpg` dans `photos/` (format portrait, visage dans le tiers haut), puis relancer `python3 scripts/exporter.py` pour mettre à jour le PDF et les aperçus.
2. **La diapositive 6** : Sami y met la sienne. Le plus simple est de remplir la section `id="s6"` de `index.html` ; le titre discret et le pied de page sont déjà en place.
3. **À relire par l'équipe** : la reformulation des rôles (diapositive 3) ; « (site officiel) » comme mention du chiffre de 6 239 logements ; le titre « La panne, on la subit. » et la tournure « nourries par nos scrapings » (diapositive 8).
4. **Le jour J** : tester sur le projecteur de la salle (la scène se met à l'échelle sans se déformer) et repérer le passage à la démo puis le retour : diapositive 5, démo, retour sur la 6 (touche flèche droite, ou `#6` dans l'adresse), démo, puis la 7.
5. Il n'y a pas de mode d'édition dans la page (la compétence le propose par défaut) : il a été écarté pour qu'une touche pressée par mégarde pendant le pitch ne fasse rien d'inattendu. Les textes se modifient directement dans `index.html`.
