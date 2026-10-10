# BâtIA — l'assemblage

Une seule application, prototype non officiel, construite sur BâtIA épurée (`f-epure`, dont l'interface fait foi). Elle reçoit les **données réelles** de `f-reel`, le **rejeu de 2025** de `f-rejeu`, et la page **Sous le capot** de `capot-libre` : une adresse tapée, neuf sources publiques, puis le verdict du même calcul que la carte. Un même gabarit partout : catégories en mots courts, couleurs vives seulement pour ce qui demande une action, « Pourquoi » puis « Plus d'informations », les mêmes touches. Le kit et le réel ne se montrent jamais ensemble.

## Lancer

```bash
node serveur.mjs
```

Puis ouvrir **http://localhost:4860**. Node 20 ou plus récent, aucune dépendance. `PORT=4861 node serveur.mjs` change le port ; `--reseau` ouvre au téléphone sur le réseau local.

Adresses directes : `/?monde=reel` (données réelles), `/?rejeu` (rejeu lancé), `/?rejeu=pause`, `/capot/`, `/capot/?adresse=34 boulevard de l'Embouchure, Toulouse` (une course lancée), `/capot/?filet` (tout depuis les enregistrements).

La page Sous le capot tourne aussi seule : `node capot/serveur.mjs`, sur le port 4861. `node capot/enregistrer.mjs` refait les enregistrements des cinq adresses, un appel à la fois, en une minute environ.

Le kit, le rejeu et la carte réelle ne sortent pas de la machine : fond de carte, parc réel et rejeu sont sur le disque.

Seule la page Sous le capot appelle les services publics, comme prévu. Chaque appel a deux secondes. Pour les cinq adresses prêtes, la réponse enregistrée (`capot/enregistrements/`, 15 Mo) prend le relais sans changer le rythme ; une autre adresse demande le réseau.

Les déroulés complets ont été faits toute requête extérieure bloquée, au projecteur et au téléphone. Les seules requêtes extérieures étaient les tentatives de la page Sous le capot, soit 61 au projecteur et 59 au téléphone. La console n'a montré que les échecs de ces requêtes bloquées, dont quelques « Error » de la carte de la page quand elle passe de la photo aérienne en ligne à celle enregistrée.

Captures du déroulé complet, 15 étapes, au projecteur (1920 × 1080) et au téléphone (390 × 844) :

```bash
python3 outils/captures-demo.py tout      # ou projecteur, ou telephone ; écrit dans captures/demo/
```

## La démonstration, touche par touche

L'en-tête porte trois boutons dans l'ordre du récit : **Rejeu de 2025** (kit seulement), **Kit du jury | Données réelles**, puis **Sous le capot** (données réelles seulement).

1. **Kit du jury** (l'écran d'ouverture), onglet **Pannes** : « 139 à visiter · 535 à surveiller · 0 décidé », avec les pastilles Urgent 45, Alerte 17 et Vigilance 77.
   - Ouvrir une fiche : un clic sur une ligne, ou Tab jusqu'à la liste puis ↓ ↑ (ou j k) et Entrée.
   - Décider : **V** pour Visite, **R** pour Remplacer, **P** pour Plus tard. Les comptes, la carte et l'onglet « décidé » suivent, avec « Annuler » dans le message.
   - **Échap** ferme la fiche, **/** place le curseur dans la recherche.
2. Onglets **Énergie** et **Rénovations** : un clic.
   - Exports : « Données » dans l'en-tête (décisions, file, scores, plan).
   - On trouve aussi « Exporter » dans l'onglet « décidé » et « Exporter le plan » sous les rénovations.
3. **Rejeu de 2025** : le bouton de l'en-tête, ou **L**.
   - **Espace** met en pause ou relance, **V** change la vitesse, **← →** reculent ou avancent, **L** ou **Début** recommencent.
   - Le rejeu s'achève au 30 septembre 2025 : la méthode de l'équipe a vu venir **43 pannes sur 76**, la règle des 128 plus vieux **16 sur 76**.
   - **Échap** ou « Quitter » rend le kit tel qu'il était.
4. **Données réelles** : un clic sur la bascule, ou le curseur sur la bascule puis ← →.
   - La carte vole vers le Sud-Ouest, les immeubles apparaissent en onde depuis Toulouse et le compte monte jusqu'à **6 601 logements · 5 départements**.
   - Catégories : Urgent 10, Alerte 32, Vigilance 24, À surveiller 53, Calme 35. Elles portent sur 154 immeubles d'au moins dix logements In'li ; les petits immeubles et les maisons sont regroupés par commune.
5. **Fiche d'un immeuble réel** : un clic sur une ligne ou sur un point, ou ↓ ↑ puis Entrée (ou Espace). Échap ferme et rend le curseur à la ligne.
   - **34 Boulevard de l'Embouchure** (Toulouse, 11e ligne) : Alerte, étiquette **C** « dans 15 DPE sur 29 · ADEME ».
   - Pourquoi : les chaudières, la ventilation, puis « Fin de la 2G en 2026 : Orange depuis le 9 juin, SFR le 15 nov., Bouygues le 15 déc. ».
   - **541 Le Grand Mail** (Montpellier, 1re ligne) : Urgent, étiquette **D** « dans 20 DPE sur 29 · ADEME ».
6. **Sous le capot** : le bouton à droite de la bascule ouvre `/capot/`. Le curseur est déjà dans le champ.
   - Lancer une adresse : **↓** puis **Entrée** pour la première adresse prête, 34 boulevard de l'Embouchure, ou taper une adresse puis **Entrée**.
   - Les lignes arrivent une par une, chacune avec sa source : IGN, RNB, BDNB, LiDAR HD, ADEME, ARCEP, BRGM, Hub'Eau, Panoramax. La carte vole jusqu'à l'immeuble, le contour se trace sur la photo aérienne, puis la façade apparaît.
   - La ligne Chauffage porte l'étiquette **C**, « dans 15 DPE sur 29 · ADEME ». La ligne Réseau 2G dit « Fin de la 2G en 2026 », puis « Orange depuis le 9 juin, SFR le 15 nov., Bouygues le 15 déc. ».
   - Le verdict tombe : « Risque selon BâtIA », **Alerte**, puis les trois raisons de la fiche de la carte, dans le même ordre.
   - Une fois la course finie : **2** lance 19 rue Rosette (**Urgent**), et **1** à **5** les cinq adresses prêtes. **/** sert à taper une autre adresse, **Entrée** rejoue la course, **H** force les enregistrements, **F** passe en plein écran.
   - **Échap**, **Alt+←** ou « ← BâtIA » ramènent à la carte en données réelles, sans rejouer l'onde. Si une adresse est en cours de frappe, avant toute course, Échap l'efface d'abord.
7. **Kit du jury** : retour au kit tel qu'on l'a laissé, décisions comprises.

Les cinq adresses prêtes reçoivent sur la page le verdict de la carte, avec ou sans réseau :

| Touche | Immeuble | Verdict (carte et Sous le capot) |
|---|---|---|
| 1 | 34 boulevard de l'Embouchure, Toulouse | Alerte |
| 2 | 19 rue Rosette, Toulouse | Urgent |
| 3 | 134 rue de Périole, Toulouse | Alerte |
| 4 | 47 allée du Rouergue, Colomiers | Alerte (Vigilance avec le calcul provisoire de `capot-libre`) |
| 5 | 78 allées Jean-Jaurès, Toulouse | À surveiller |

Une adresse hors du parc reçoit, si le réseau répond, un verdict calculé en direct par le même calcul. Par exemple, 1 place du Capitole à Toulouse donne Vigilance.

Au **téléphone**, l'ordre est le même :
- la bascule est sous la barre de briques ;
- en données réelles, « Sous le capot » occupe toute la bande de briques, à la place des onglets du kit ;
- la page Sous le capot se lit en colonne : carte, lignes, puis le verdict, qui vient sous les yeux ; « ← BâtIA » ramène à la carte ;
- « Rejeu de 2025 » est au pied de la liste ;
- la liste et la fiche réelles ont la même poignée que celles du kit.

## La palette

Une seule palette pour toute l'application : celle de l'onglet Pannes. Elle est dans `app/palette.css`, que chargent l'application et la page Sous le capot.

Une même couleur veut dire la même chose partout :

| Couleur | Variable | Ce qu'elle veut dire |
|---|---|---|
| rouge `#D7261E` | `--urgent` | Urgent ; l'étiquette G ; le compte de ce qui est grave (« 139 à visiter », « 459 logements de E à G ») ; la panne manquée du rejeu |
| orange `#F27C14` | `--alerte` | Alerte ; l'étiquette F |
| jaune `#F7C51E` | `--vigilance` | Vigilance ; l'étiquette E |
| vert `#12965A` | `--lancer` | À lancer, et « ce plan » dans les rénovations ; l'étiquette A |
| sable `#EFE5D3`, bordé | `--surveiller` | À surveiller. Calme est sur le papier. Ni l'un ni l'autre n'a de couleur vive. |

Les étiquettes énergie gardent l'échelle officielle, du vert de A au rouge de G :
- A, E, F et G prennent les couleurs du tableau : une passoire G se voit comme une panne urgente.
- B (`#4FA83D`), C (`#9DC43C`) et D (`#EADC1E`) gardent leurs teintes officielles, en plus franc.
- La lettre est blanche sur A et G, sombre sur les autres.

Où elle s'applique :
- **Pannes** : la référence, sans changement.
- **Énergie** :
  - l'ardoise bleue disparaît : la bande de briques, l'onglet choisi et les briques de la carte sont ceux de Pannes ;
  - « 459 logements de E à G » et le compte d'une résidence ouverte sont en rouge d'« Urgent », comme « 139 à visiter » ;
  - sur l'échelle A–G, les lettres qui comptent portent leur couleur ; les autres restent en retrait ;
  - une brique de la carte se remplit comme dans Pannes : G en bas, en rouge, puis F et E au-dessus ; la brique de la métropole aussi ;
  - dans les barres de répartition, les lettres qui comptent sont vives et les autres pâles ;
  - le compte de chaque ligne est à l'encre : la barre porte déjà la couleur.
- **Rénovations** : mise en page inchangée. Ses couleurs étaient déjà celles de la palette, avec le vert de « Lancer ».
- **Données réelles** : les catégories et les points de la carte avaient déjà ces couleurs ; les étiquettes DPE de la fiche prennent les nouvelles teintes.
- **Sous le capot** : le verdict et l'étiquette DPE lisent `palette.css`.
- **Rejeu** :
  - la panne manquée passe du vermillon au rouge d'« Urgent », sur la carte, dans les grilles et dans la légende ;
  - le bleu de la panne vue venir reste propre au rejeu : il n'a aucun autre sens dans l'application ;
  - la forme double toujours la couleur, avec un disque ou une croix.

Une couleur vive ne sert qu'à ce qui compte. À surveiller et Calme restent sur sable ou papier, les lettres de l'échelle qui ne comptent pas restent en retrait et les comptes des lignes restent à l'encre.

Vérifications, réseau coupé, au projecteur (1920 × 1080) puis au téléphone (390 × 844) :
- dans le kit : Pannes, Énergie avec la fiche d'une résidence, Rénovations ;
- en données réelles : la liste et la fiche d'un immeuble ;
- la page Sous le capot, avec 19 rue Rosette en Urgent ;
- la fin du rejeu, au projecteur.

J'ai ouvert les captures. Aucune erreur de script.

## Ce qui vient de chaque session

| Session | Ce qu'elle apporte | Où |
|---|---|---|
| `f-epure` (la base) | carte plein écran, briques, trois onglets, catégories et couleurs, fiches, décisions, exports, serveur | `app/`, `carte/`, `moteur/`, `risque/`, `serveur.mjs`, `UX.md` |
| `f-reel` | le parc réel précalculé (BDNB, DPE de l'ADEME, DGFiP, GPU, Hub'Eau, ANFR), le calcul de risque, la couche de la carte, la bascule et l'onde | `reel/`, `recherche/reel-contrat.md`, `recherche/recherche-donnees-publiques.md`, fiche 19 |
| `f-rejeu` | le rejeu de 2025 et ses chiffres | `rejeu/` |
| `capot-libre` | la page Sous le capot : neuf sources publiques en chaîne, le relais vers les services qui refusent le navigateur, les enregistrements des cinq adresses, les antennes 2G de l'ANFR | `capot/` |
| cette session | l'assemblage, décrit ci-dessous | |

Ce que l'assemblage a changé :

- **En-tête** (`app/index.html`, `app/app.css`) : `#place-bascule` reçoit les trois boutons ; mises en page pour le projecteur, l'écran moyen et le téléphone.
- **Un monde à la fois** : en données réelles, tout le kit se retire (file, fiche, onglets, recherche, briques), et le rejeu ne s'ouvre ni par le bouton ni par L. Les gestes du kit ne réagissent plus aux clics du monde réel. Avant, ouvrir un immeuble réel laissait une fiche « Introuvable » au retour dans le kit.
- **Le réel prend le gabarit du kit** (`reel/monde.mjs`, `reel/fiche.mjs`, `reel/reel.css` réécrits) :
  - les mêmes classes, les mêmes mots (Urgent, Alerte, Vigilance, À surveiller, Calme) et les mêmes couleurs ;
  - « Pourquoi » avec trois raisons au plus, puis « Plus d'informations » ;
  - les mêmes touches et la même poignée au téléphone ;
  - sur la carte, les points ont ces couleurs, et seules les catégories vives portent une étiquette.
- **Retiré de la fiche réelle** : le quartier prioritaire, la distance aux antennes et la ligne de consommation de la BDNB. Rien de tout cela ne sert la décision.
- **La règle commune** `reel/regles.mjs`, sans dépendance, pour le navigateur comme pour Node :
  - `etiquetteImmeuble` : l'étiquette d'un immeuble est la plus fréquente parmi ses DPE de l'ADEME, la moins bonne à égalité, avec leur nombre (« dans 15 DPE sur 29 · ADEME »). Sans DPE à l'ADEME, c'est l'étiquette de la BDNB, et la source le dit.
  - `phrase2G` : une seule phrase tirée du calendrier de l'ARCEP et d'Orange. Une date passée se dit « depuis le ».
  - Le calcul, la fiche et la page Sous le capot s'en servent.
- **Ce que la règle a changé** : l'Embouchure affichait D dans `f-reel` (l'étiquette de la BDNB) et affiche maintenant C. Les catégories passent de Alerte 31 et À surveiller 54 à Alerte 32 et À surveiller 53.
- **Serveur** : port 4860, routes `/reel/` (sans `cache/` ni `outils/`) et `/rejeu/` (sans les `.py`). Avant toute autre route, `servirCapot` (`capot/relais.mjs`) sert `/capot/` : la page, son relais, `/capot/anfr` et les enregistrements.
- **Sous le capot branché sur le vrai calcul** (`capot/capot.mjs`) : la page importe `/reel/calcul.mjs`, et `calcul-provisoire.mjs` est retiré.
  - Si l'immeuble est au parc d'In'li, reconnu par son identifiant BDNB ou RNB, la page évalue la fiche même de la carte : même niveau, mêmes raisons.
  - Sinon, elle évalue la fiche assemblée en direct (`assemblerFiche`, qui reçoit maintenant le code de la commune et le département).
- **L'étiquette et la 2G de la page** passent par `reel/regles.mjs` (`capot/sources.mjs`).
  - Les dates d'arrêt de la 2G n'ont plus qu'une source. Bouygues coupe le 15 décembre, et non plus le 1er.
  - Hors des cinq départements, la phrase ne donne que SFR et Bouygues.
- **Couleurs de la page** : celles des catégories de l'application, vives pour Urgent, Alerte et Vigilance, sable et contour pour À surveiller et Calme. Les étiquettes DPE ont les couleurs de la fiche de la carte.
- **Le verdict** montre les trois raisons du « Pourquoi » de la carte. Leurs sources sont les lignes au-dessus.
- **Retour** : Échap et « ← BâtIA » ramènent à `/?monde=reel`. Le bouton Précédent du navigateur garde aussi le retour rapide (`reel/monde.mjs`).
- **Téléphone** : une mise en page en colonne pour la page Sous le capot (elle était réduite à un cadre de 219 pixels de haut). L'attribution du fond passe sur deux lignes à gauche de la photo de rue, au lieu de la chevaucher. En données réelles, la bande de briques s'étend sur toute la largeur et porte « Sous le capot ».
- **Le serveur autonome du capot** (`node capot/serveur.mjs`) passe sur le port 4861, dans la plage réservée à ce dossier.
- **Nouveaux fichiers** : `outils/captures-demo.py`, qui fait maintenant une course complète sur la page Sous le capot, et `app/palette.css`, la palette commune (voir « La palette »).

## Test d'usage

Ce test date de l'assemblage, avant l'arrivée de la page Sous le capot. Il a été mené par un agent qui n'a pas construit l'application et n'a lu ni le code ni la documentation. Il a déroulé la démonstration au projecteur, puis au téléphone, en environ 17 minutes.

**Ce qui a marché.** Toutes les étapes ont réussi au premier essai, sauf deux :
- l'export des décisions, trouvé au second essai ;
- Sous le capot, vide comme prévu.

Les détails :
- La décision compte partout et survit au rejeu, à la bascule et au retour.
- La 2G est dite de la même façon sur toutes les fiches.
- Au téléphone, tout le parcours a été fait.
- Aucune requête hors de la machine, aucune erreur.

**Ce qui l'a fait hésiter, et ce qui a été corrigé :**
- **Deux comptes contradictoires sur l'Embouchure.** L'en-tête disait « 15 DPE sur 29 », les sources disaient « 16 DPE sur 29 ». Le second compte portait sur la chaudière. Chaque phrase dit désormais ce qu'elle compte : « dans 15 DPE sur 29 · ADEME » pour l'étiquette, « Chaudières gaz standard dans 16 DPE sur 29 · ADEME » pour la chaudière.
- **« 15 DPE sur 29 » incompris** sans ouvrir « Plus d'informations ». C'est devenu « dans 15 DPE sur 29 ».
- **La 2G d'Orange, coupée le 9 juin, présentée comme à venir.** La phrase est devenue « Fin de la 2G en 2026 : Orange depuis le 9 juin, SFR le 15 nov., Bouygues le 15 déc. ».
- **Le clavier.**
  - Sur la 9e ligne, ↓ ouvrait la 1re. Les flèches partent maintenant de la ligne où se trouve le curseur, dans le kit comme dans le réel.
  - Échap rend le curseur à la ligne.
  - Les lignes réelles se présentent comme des boutons.
- **Les mots.**
  - « 46 logements In'li sur 83 » est devenu « 83 logements, dont 46 In'li ».
  - Les adresses ont des apostrophes typographiques.
  - On lit « VMC SF Autoréglable ».
- **Deux boutons pour la même chose à la fin du rejeu** (« Revoir » et « Recommencer »). Il ne reste que « Revoir » (Espace), qui repart du début.

**Vérifications de la suite « Sous le capot »**, faites par cette session, sans nouveau test par un sous-agent :
- Réseau coupé, les cinq adresses vont au bout depuis les enregistrements, avec les verdicts du tableau ci-dessus et les trois raisons de la carte.
- Avec le réseau, les verdicts sont les mêmes, et une adresse hors parc (1 place du Capitole) reçoit un verdict en direct.
- Le déroulé complet passe au projecteur et au téléphone, réseau coupé, avec la course de l'Embouchure et le retour par Échap ou par « ← BâtIA ». J'ai ouvert les captures.

**Ce qui n'a pas été corrigé** (voir « Ce qui reste ») :
- pas de recherche en données réelles ;
- l'étiquette « Urgent · 139 à visiter » de la métropole, qui se lit comme 139 urgents ;
- des noms de carte cachés sous les points.

## Ce qui reste

- **Couleurs.**
  - L'étiquette D, citron, et l'étiquette E, jaune de « Vigilance », sont proches : la lettre les distingue.
  - Le bleu du rejeu est la seule couleur hors de la palette ; il est gardé pour les daltoniens.
  - Les fonds de la carte (brique, sable, mer) n'ont pas changé.

- **Sous le capot depuis une fiche.** Ouvrir la page avec l'adresse de l'immeuble ouvert sur la carte (`/capot/?adresse=…`) relierait les deux vues.
- **Sous le capot, les lignes et le verdict.** Pour un immeuble du parc, la ligne Chauffage décrit les DPE lus en direct ; l'étiquette et le verdict viennent de la fiche de la carte. Ils concordent pour les cinq adresses ; sur un autre immeuble, des DPE déposés depuis la fabrication du parc pourraient les faire diverger.
- **Sous le capot, d'autres points.**
  - Réseau coupé, la carte de la page écrit quelques « Error » dans la console avant de prendre la photo aérienne enregistrée. Rien ne se voit à l'écran.
  - Pour une adresse hors parc, la ligne Chauffage peut garder un libellé brut de l'ADEME, par exemple « Autres émetteurs à effet joule » pour le Capitole.
  - Au téléphone, l'adresse en titre tient en entier pour les cinq adresses prêtes, dont la plus longue est celle de l'Embouchure. Une adresse plus longue serait coupée par des points de suspension.
  - Un test d'usage de la page par un agent qui ne la connaît pas reste à faire.
- **Sous le capot, ce qui reste fragile** (déjà relevé par `capot-libre`) :
  - Géorisques refuse les appels depuis cette machine, donc la ligne Sol prend l'aléa du BRGM recopié dans la BDNB.
  - La photo de Jean-Jaurès montre le pied de la tour, des bureaux.
  - Le contour se trace deux à trois secondes après sa ligne.
- **Recherche en données réelles.** La liste est rangée par urgence, et l'Embouchure est la 11e ligne. Il faudrait taper une adresse ou une commune dans la recherche de l'en-tête.
- **Étiquette de la métropole sur la carte du kit** (comportement de la base). Elle dit « Urgent · 139 à visiter » ; « 45 urgents · 139 à visiter » se lirait mieux.
- **Adresse de page.** Un immeuble réel n'a pas sa propre adresse, alors qu'une fiche du kit en a une (`#/equipement/…`).
- **Fond de carte.** Il n'est détaillé qu'autour de Toulouse. Ailleurs, à l'échelle de la rue, l'immeuble se pose sur un fond clair.
