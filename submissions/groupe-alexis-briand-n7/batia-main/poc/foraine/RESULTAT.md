# Foraine — résultat

Foraine est l'outil interne de l'équipe technique d'In'li Sud-Ouest pour voir venir les pannes et décider quoi réparer d'abord. La carte du parc occupe tout l'écran, tout le temps. La file des priorités, les fiches et la lentille Énergie se posent par-dessus. Choisir une ligne fait voler la carte vers sa résidence ; toucher une brique sur la carte filtre la file et ouvre la fiche de la résidence.

La théorie de l'usage, et les décisions d'écran qui en découlent, sont dans [`UX.md`](UX.md).

## Lancer

```bash
node serveur.mjs
```

Puis ouvrir **http://localhost:4720**. Il faut Node 20 ou plus récent ; aucune dépendance à installer, aucun compte, aucune clé. `npm start` fait la même chose.

- `node serveur.mjs --reseau` écoute aussi sur le réseau local, pour ouvrir Foraine depuis un téléphone (http://adresse-de-la-machine:4720).
- `PORT=4721 node serveur.mjs` change le port.
- Le fond de carte (`carte/fond/*.pmtiles`, 140 Mo) n'est pas versionné. Il est présent sur cette machine ; ailleurs, `carte/outils/extraire-fond.sh` le refait (voir `carte/CARTE.md`).

Au démarrage, le serveur lit les CSV de `donnees/kit-batia/donnees/` (sans jamais y écrire) et calcule tous les indices en moins d'une seconde.

## Ce qui marche

**La carte est l'application**
- La carte vectorielle locale (module `carte/`) en plein écran, aux trois échelles France, Sud-Ouest et Métropole. À l'ouverture, elle glisse de la France au Sud-Ouest, puis la file arrive par la gauche.
- Une brique par résidence : sa taille suit le nombre de logements, sa base se remplit de ce qui est à visiter (brique cuite) et à surveiller (brique claire). L'étiquette dit les mêmes chiffres en toutes lettres. Les étiquettes ne se chevauchent pas, et elles restent dans l'espace que les panneaux laissent libre.
- File → carte : survoler une ligne fait battre la brique de sa résidence. La choisir fait voler la carte jusqu'au secteur, tracé en brique cuite.
- Carte → file : survoler une brique fait ressortir ses lignes dans la file. La toucher filtre la file (une pastille qu'on retire) et ouvre la fiche de la résidence.
- La caméra se cadre toujours dans la zone que laissent libre la file, la fiche et la barre d'échelles. Elle ne passe jamais sous un panneau.

**Décider (défi 1)**
- La file a trois onglets : **À visiter** (48 au 31/12/2025), **À surveiller** (140), **Décidé**. Elle se filtre par résidence et par type d'équipement.
- Une ligne : le rang sur une brique, l'appareil, le lieu (« D · bât. D2 · logt 025 · 2ᵉ »), la raison principale en clair, l'indice.
- La fiche équipement donne le niveau, l'indice et le rang, puis trois décisions : **Visite**, **Remplacer**, **Plus tard**, avec une note facultative. Suivent les raisons et leur poids relatif, les faits (pose, âge, durée de vie, dépannages, visites manquées, contrat et prestataire), puis l'historique mêlant interventions et demandes du locataire liées à l'appareil.
- Une décision sort l'équipement de la file, met à jour les briques, et se défait d'un clic (« Annuler » dans le bandeau ou dans la fiche). Un bouton « Suivant » mène au prochain équipement de la file. Rien n'est décidé automatiquement.
- Au clavier : `↑` et `↓` (ou `j` et `k`) parcourent la file, `V`, `R` et `P` décident, `Échap` ferme, `/` cherche.
- Un double clic ne décide pas puis n'annule pas dans la foulée.
- Les décisions sont enregistrées sur la machine (`etat/decisions.json`). L'ordinateur et le téléphone voient donc les mêmes. L'onglet « Décidé » les exporte d'un geste.

**Le logement et la résidence (demandés par In'li)**
- La fiche logement donne le nombre de demandes en 12 mois et depuis 2019, puis toutes les demandes datées avec leur motif, leur priorité et le texte du locataire. On y trouve aussi les équipements du logement et leur niveau, l'étiquette DPE avec l'alerte si elle dépasse le seuil, et les interventions. La répétition des demandes entre dans le calcul du risque et apparaît dans les raisons.
- La fiche résidence donne l'identité de la résidence et les comptes (à visiter, à surveiller, décidés, demandes sur 12 mois). Elle détaille aussi les bâtiments un par un, la répartition des étiquettes DPE et les opérations envisagées.
- La recherche (`/`) trouve un logement (« D2-025 »), une résidence ou un équipement.

**Énergie (le bonus)**
- La lentille **Énergie** recolore les briques en ardoise selon le nombre de logements au-delà du seuil.
- Le seuil d'alerte se choisit d'un geste sur l'échelle A–G. Il vaut E par défaut, l'exemple cité par In'li, et reste mémorisé sur l'appareil.
- Les résidences sont rangées par nombre de logements au-delà du seuil, avec leur répartition DPE et les opérations envisagées dans le plan d'investissement (coût et gain).

**Le territoire et le déséquilibre**
- De loin, la Haute-Garonne est maçonnée ; les quatre autres départements sont tracés au trait de joint, « à raccorder ».
- La carte « Parc In'li Sud-Ouest » montre une assise de briques, une par centaine de logements, dont 11 posées sur ≈ 63 (1 100 / ≈ 6 300 logements). En dessous, les cinq départements : la Haute-Garonne raccordée, et un lien « à raccorder » pour chacun des quatre autres.

**Données, import, export**
- Dès que le relevé a plus d'un trimestre, son âge s'affiche sous le nom (« relevé au 31 déc. 2025 · il y a 9 mois »). Si la fenêtre de prévision est passée, la page Méthode le dit.
- La page Données donne la date du relevé et les volumes. Elle permet d'importer un trimestre au format actuel : un CSV d'interventions ou de demandes, contrôlé, rangé dans `imports/`, après quoi tous les indices sont recalculés.
- Trois exports : les décisions (pour le prestataire, fichier daté du jour), la file à visiter et à surveiller avec raisons et décisions (CSV pour Excel), et les indices au format du défi (`equipement_id,score_risque`).
- La page Méthode explique le calcul et donne la validation réellement calculée face à « âge seul ».

**Ordinateur et téléphone**
- Au téléphone, la carte reste en haut. La file et les fiches vivent dans une feuille qu'on tire du pouce, par sa poignée ou par son en-tête (trois hauteurs). La recherche est derrière la loupe. La fiche d'une résidence liste ce qui y est à visiter, pour qui est sur place. Données et Méthode sont au pied de la liste.

**Sans Internet**
- `python3 outils/captures.py` bloque toute requête qui ne va pas vers localhost. Résultat : 0 requête vers Internet, sur ordinateur comme sur téléphone, et aucune erreur dans la console.
- Aucun service d'IA ni service en ligne ne reçoit les données.

## Test d'usage

Un agent qui n'avait pas construit Foraine l'a utilisée sans explication, sur ordinateur puis sur téléphone, pour huit tâches de l'équipe technique : les trois premiers du lundi et une décision, les demandes du logement 025 du bâtiment D2, la résidence qui a le plus à visiter, annuler une décision, les logements en F ou G et les opérations de la résidence G, le fichier pour le prestataire, la résidence B depuis le téléphone, et de quoi convaincre un directeur. Les huit tâches ont abouti, en 3 à 8 gestes. Attention : l'application a changé pendant le test (seuils et file mis à jour en cours de route). Les tâches 1 à 5 ont donc vu des chiffres que l'on ne retrouve plus aujourd'hui.

Ce qui l'a fait hésiter, et ce qui a été corrigé :

| Constat | Correction |
|---|---|
| Au téléphone, la loupe ne réagissait pas au doigt | Tout le bouton ouvre la recherche (vérifié au toucher) |
| Rien ne disait que le relevé date de 9 mois ni que la fenêtre de prévision est passée | Âge du relevé sous le nom ; avertissement sur la page Méthode |
| Export cherché d'abord dans l'onglet « Décidé » | Lien « Exporter » dans cet onglet ; fichier nommé à la date du jour |
| Après « Annuler », « Plus tard » réapparaît sous le pointeur : un double clic écarte l'équipement | Le second clic d'un double clic est ignoré (vérifié) |
| Au téléphone, il fallait fermer la fiche de la résidence pour voir quoi visiter, et la feuille ne se tirait que par une poignée de 22 px | La fiche liste ce qui est à visiter ; la feuille se tire aussi par son en-tête |
| Énergie : titre coupé (« de E à / G »), « 5 opérations » dans la liste contre 7 dans la fiche, « gardé sur cet appareil » obscur | Titre sur une ligne ; « opérations à gain énergétique » partout ; mention retirée |
| Lettre illisible sur une brique pleine en Énergie | Halo clair autour de la lettre |
| Texte qui défile collé sous l'en-tête des fiches ; bouton × sur la dernière colonne du tableau de la Méthode ; bandeau de confirmation sur le zoom et la fiche | En-tête séparé ; tableau réduit ; bandeau en haut, dans l'espace libre |

Un second agent, neuf lui aussi, a ensuite refait trois tâches sur la version corrigée : la résidence B depuis la recherche du téléphone (réussie en 3 gestes), une décision puis son export et son annulation (6 clics, fichier correct), et la fraîcheur des données (lue sans un geste). Suites données : la fiche d'un équipement décidé dit « Décidé » et non plus « À visiter », l'âge du relevé est plus contrasté et s'affiche aussi au téléphone, et la file arrive plus tôt après l'ouverture.

Ce qui reste signalé et n'est pas corrigé :
- Les rangs restent ceux du parc entier : dans la liste d'une résidence, on lit 8 et 13, pas 1 et 2, et rien ne le dit.
- Dans les captures sans carte graphique (rendu logiciel), la fiche met jusqu'à 3 secondes à se remplir pendant le vol de la caméra. Le serveur, lui, répond en 3 ms.
- Il n'existe pas de classement des résidences. On compare sur la carte, et quand les deux panneaux sont ouverts à l'échelle Métropole, certaines étiquettes s'effacent pour ne pas se chevaucher.
- Le mot « indice » et les priorités P1 à P4 des demandes ne s'expliquent que sur la page Méthode, ou pas du tout pour P1 à P4.
- L'export pour le prestataire n'a ni adresse, ni contact du locataire : ces données ne sont pas dans le jeu fourni.
- La carte ne se recadre pas quand on ferme une fiche. Au téléphone, « Pyrénées-Atlantiques » peut chevaucher l'étiquette de la métropole.

## Méthode de risque

Le module `risque/risque.mjs` est remplaçable : il rend, pour chaque équipement du périmètre (1 285), `{ score, probabilite, niveau, raisons, faits }`. Le lecteur des données est `risque/donnees.mjs`, et `node risque/verifier.mjs` refait tout le calcul et la validation.

- **Cible** : un dépannage « Arrêt total » dans les 9 mois qui suivent le relevé (du 1er janvier au 30 septembre 2026 pour le relevé du 31 décembre 2025).
- **Méthode** : régression logistique écrite à la main, déterministe, sur 10 critères lisibles par un technicien :
  - l'âge rapporté à la durée de vie de référence ;
  - les dépannages et les arrêts totaux sur 12 mois, et les dépannages sur 3 mois ;
  - les commentaires de fin de vie notés par les techniciens et les anomalies relevées en visite, sur 18 mois et depuis la dernière pose ;
  - la part des visites d'entretien manquées ;
  - les demandes du locataire liées à l'appareil sur 12 mois ;
  - la surface du logement ;
  - un remplacement demandé mais pas encore posé.

  Les poids sont appris sur les situations au 31 décembre de 2020 à 2024. Ils sont contraints dans le sens des règles métier, si bien qu'aucune raison ne va contre le bon sens. Les raisons affichées sont les critères qui pèsent le plus pour l'équipement, écrites comme des faits datés.
- **Indice** : la probabilité × 100, arrondie. Il sert à ranger, ce n'est pas une promesse. Seuils : **à visiter** à partir de 30, **à surveiller** de 6 à 29.
- **Validation réellement calculée** : modèle appris sur 2020 à 2023, appliqué au 31 décembre 2024, comparé aux arrêts totaux réels du 1er janvier au 30 septembre 2025 (76 équipements sur 1 285).

| | Foraine | Âge seul |
|---|---|---|
| Arrêts totaux parmi les 50 premiers | 32 | 7 |
| Arrêts totaux parmi les 100 premiers | 44 | 14 |
| Arrêts totaux parmi les 54 premiers (taille du niveau « à visiter » ce jour-là) | 33 | 7 |
| AUC | 0,880 | 0,777 |

Ces chiffres valent pour des données fictives, fabriquées selon des règles connues (onglet HYPOTHESES) : sur les données réelles d'In'li, la mesure serait à refaire. Le modèle est aussi trop confiant en tête de liste : en validation, 64 % des 50 premiers ont réellement connu un arrêt total, alors que leurs indices sont plus élevés. C'est pourquoi l'écran parle d'« indice » et jamais de pourcentage.

## Ce qui manque

- Les données s'arrêtent au 31 décembre 2025. Un vrai usage demande d'importer chaque trimestre, sinon l'indice vieillit : Foraine le montre, mais ne le corrige pas seule.
- Les décisions n'ont pas d'auteur : pas de compte, comme demandé. Une version d'équipe noterait qui a décidé.
- L'import accepte les interventions et les demandes. Les autres tables (nouveaux équipements, nouvelles résidences) demanderaient encore une petite page de contrôle.
- Raccorder un département demande ses fichiers et un extrait de fond de carte détaillé pour sa métropole (environ 30 Mo, voir `carte/CARTE.md`). La commande existe dans l'outil, pas encore le flux complet.
- Le plan d'investissement (défi 2) est montré par résidence dans la lentille Énergie, mais Foraine ne propose pas d'arbitrage sous l'enveloppe annuelle de 1,5 M€.
- Les positions des résidences sont celles, fictives, du module de carte. Aucun bâtiment n'est dessiné.

## Fichiers

- `serveur.mjs` : le serveur local (application, carte, API, décisions, import et export).
- `app/` : l'interface (`index.html`, `app.css`, `app.mjs`), sans cadriciel ni étape de construction.
- `risque/` : le module de risque remplaçable, le lecteur de CSV et le script de vérification.
- `carte/` : le module de carte fourni. Ajouts : la zone occupée par les panneaux, le choix et le survol d'une résidence, la mise à jour des briques, le vol vers une résidence, la lentille Énergie.
- `outils/captures.py` : les captures ordinateur et téléphone, avec le blocage d'Internet.
- `UX.md` : la théorie de l'usage.
