# BâtIA — théorie de l'usage

BâtIA est l'outil de l'équipe technique d'In'li Sud-Ouest pour voir venir les pannes et décider quoi réparer d'abord. Ce texte dit pour qui il est fait, à quel moment on l'ouvre, et ce qui en découle pour chaque écran, chaque mot et chaque geste. Il a été écrit avant le code ; quand un choix d'écran hésitait, c'est ici qu'il a été tranché.

## 0. Version épurée (10 octobre)

Les retours d'Alexis ont tranché trois points, qui priment sur la suite de ce texte quand ils la contredisent :

- **Une catégorie, pas un nombre.** L'indice disparaît de l'écran. Chaque équipement porte la catégorie du barème rendu au jury, en mot court : Urgent, Alerte, Vigilance, À surveiller, Calme, RAS. Les seuls nombres restants sont des comptes (« 139 à visiter ») ou des montants.
- **La couleur vive est réservée à l'action.** Rouge pour Urgent, orange pour Alerte, jaune pour Vigilance à partir de 45 points, vert pour une rénovation à lancer cette année. Tout le reste est sable, contour ou encre. Le mot est toujours écrit dans la pastille.
- **Ce qui est secondaire passe derrière un geste.** Une ligne de file dit la catégorie, l'appareil et la résidence, rien d'autre. Une fiche dit la catégorie, les décisions et le pourquoi ; le reste est derrière « Plus d'informations ». L'encart du territoire et la date du relevé vont sur la page Données.

Une troisième lentille, **Rénovations**, montre le plan recommandé sous le plafond annuel. On y voit ce qu'on lance cette année, l'effet du plan face à l'ordre actuel des demandes, puis les années suivantes. La méthode de classement se lit dans la fiche d'une opération, en mots (fort, moyen, faible), et sur la page Méthode.

## 1. Qui ouvre BâtIA

**La personne qui pilote la maintenance** (responsable technique, chargé·e de patrimoine). Elle connaît ses résidences par leur lettre, ses bâtiments, ses prestataires et leur contrat. Elle parle en dépannages, arrêts totaux, visites d'entretien, bons de commande, ECS, VMC. Elle ne parle pas en probabilités et n'a pas à le faire. Elle doit pouvoir défendre chaque décision devant sa hiérarchie, devant un prestataire, devant un locataire : un score nu ne lui sert à rien, un fait daté lui sert toujours.

**La personne sur le terrain** (technicien·ne, gardien·ne). Elle a un téléphone, une main occupée, quelques secondes, et elle est devant une résidence ou une porte.

**Plus rarement, la direction du patrimoine**, qui prépare les rénovations énergétiques et regarde le parc par résidence plutôt que par équipement.

## 2. Quand et pour quoi faire

| Moment | Question réelle | Ce que BâtIA doit rendre immédiat |
|---|---|---|
| Lundi matin, au bureau, un quart d'heure | « Qu'est-ce qui va casser, et qu'est-ce que je déclenche cette semaine ? » | Une file d'équipements, du plus menacé au moins menacé, avec la raison et trois décisions possibles. |
| Devant une résidence, au téléphone | « Qu'est-ce qui cloche ici ? » | La résidence touchée sur la carte, ses équipements à visiter, un logement en deux gestes. |
| Un locataire appelle | « Ce logement a-t-il déjà un historique ? » | La recherche d'un numéro de logement, puis toutes ses demandes et interventions, datées. |
| Chaque trimestre, rapport du prestataire reçu | « Qu'est-ce qui a changé ? Qu'est-ce que j'envoie au prestataire ? » | Importer le trimestre, relire la file, exporter la liste des visites décidées. |
| Préparation des travaux | « Où sont les passoires ? Qu'est-ce qui est déjà envisagé ? » | Le même parc, vu par l'énergie : étiquettes, seuil choisi, opérations envisagées. |

Le lundi matin est le moment qui décide de tout le reste : c'est lui qui fixe l'ordre, la densité et les mots.

## 3. La doctrine

**D1. La carte est le plan de travail, pas l'illustration.** Le parc est un lieu ; tout ce qu'on ouvre y a une place. Choisir un équipement dans la file, c'est s'y rendre : la carte vole vers sa résidence. Toucher une résidence sur la carte, c'est filtrer la file. Les panneaux se posent sur les bords et la caméra se recentre dans l'espace qu'ils laissent libre : la carte n'est jamais un papier peint derrière une fenêtre.

**D2. La file avant le tableau.** Le lundi, on ne cherche pas, on dépile. Une ligne répond à trois questions dans cet ordre : quoi (l'appareil), où (résidence, bâtiment, logement), pourquoi (une raison, en clair). Pas de colonnes de chiffres, pas de tuiles de synthèse : le nombre qui compte est en tête de la file (« 48 à visiter ») et sur la carte.

**D3. Une raison, pas un score.** L'indice sert à trier ; la raison sert à décider. Chaque raison est un fait vérifiable, dans le vocabulaire du métier : « 7 dépannages en 12 mois, dont 2 arrêts totaux », « Noté « Usure avancée constatée » le 12 novembre 2025 », « 19 ans de service pour 18 prévus ». Chaque fait se retrouve, daté, dans l'historique de la fiche.

**D4. L'humain décide, d'un geste, et peut se dédire.** BâtIA propose un ordre, jamais une action. Trois verbes calqués sur le métier : **Visite** (envoyer le prestataire), **Remplacer** (préparer la commande), **Plus tard** (écarter pour l'instant). Une décision sort l'équipement de la file, reste visible dans « Décidé », s'exporte depuis cet onglet même, s'annule en un clic. Un geste vaut une décision : un double clic ne décide pas puis ne défait pas dans la foulée. Rien ne se décide seul.

**D5. Les mêmes mots partout.** « À visiter », « à surveiller », « décidé » : le mot de l'étiquette sur la carte est celui de l'onglet, de la fiche et de l'export. Un mot par idée ; pas de synonyme pour faire joli.

**D6. La couleur ne parle jamais seule.** La palette vient de la brique toulousaine : brique cuite pour « à visiter », brique claire pour « à surveiller », mortier pour le calme. L'énergie prend l'ardoise, le seul froid de la carte : une passoire, c'est de la chaleur qui fuit. Chaque couleur est accompagnée d'un nombre et d'un mot.

**D7. Une seule forme à apprendre, et on la connaît déjà.** La brique est le seul signe : sur la carte, une brique par résidence, dont la taille suit le nombre de logements et dont la base se remplit de ce qui est à visiter ; dans la file, le rang est posé sur une petite brique de la même couleur. Rien d'autre à décoder.

**D8. Montrer peu, ouvrir sur place.** Parc → résidence → logement → équipement : chaque niveau s'ouvre là où l'on est, un panneau par côté. La file à gauche, la fiche à droite, la carte entre les deux.

**D9. Pas de phrase qui explique l'écran.** Des nombres, des mots courts, des commandes. Ce qui doit vraiment être expliqué (la méthode de risque, sa validation, les données) est sur une page à part, « Méthode ».

**D10. La confiance se gagne par la trace.** La date du relevé est toujours visible ; au-delà d'un trimestre, son âge s'y ajoute, et une prévision dont la fenêtre est passée est dite telle sur la page Méthode. Un outil qui vieillit sans le dire perd la confiance qu'il a gagnée. Chaque nombre d'une fiche renvoie aux lignes qui le fondent. La page Méthode donne la mesure réellement calculée sur l'année 2025, face à la méthode « âge seul », et rien d'autre.

**D11. Le déséquilibre est un chantier.** Huit résidences de la métropole toulousaine, sur un parc de cinq départements : c'est la première assise d'un mur. Vue de loin, la carte montre la Haute-Garonne maçonnée et les quatre autres départements au trait de joint, « à raccorder » ; sous la carte, une assise de briques : chaque brique vaut cent logements, celles qui sont posées sont pleines. Raccorder est une commande (importer les fichiers trimestriels), pas une excuse.

**D12. Le téléphone est un terrain.** La carte en haut, une feuille en bas qu'on tire du pouce, par sa poignée ou par tout son en-tête. Sur la carte, l'étiquette se réduit à ce qu'il faut aller voir. Des cibles de 44 px. La recherche d'un logement est à un geste : toute la loupe est la cible. Devant une résidence, sa fiche porte ce qui y est à visiter, sans avoir à la fermer pour retrouver la file.

**D13. Le mouvement relie, il ne décore pas.** Les vols de caméra gardent l'orientation entre deux lieux (arc de 1,7 s entre échelles, plus court vers une résidence) ; les panneaux glissent depuis leur bord. Tout s'arrête si le système demande moins d'animations.

## 4. Ce qui en découle, écran par écran

**L'ouverture.** La carte glisse de la France au Sud-Ouest (D1, D11). Une fois posée, la file arrive par la gauche : ce qu'il faut décider vient juste après le parc. Au téléphone, la feuille du bas monte jusqu'à montrer le nombre à décider.

**La barre du haut** : la marque et la mention « prototype non officiel », les trois lentilles (**Pannes** · **Énergie** · **Rénovations**), la recherche, **Données** et **Méthode**. Au centre, une place réservée à la bascule des données. Rien d'autre (D8).

**La file (lentille Pannes).** Trois onglets : **À décider**, **À surveiller**, **Décidé**, chacun avec son nombre. Une ligne = rang sur brique, appareil, lieu, première raison. Survoler une ligne fait battre la brique de sa résidence sur la carte ; la choisir fait voler la carte et ouvre la fiche (D1). Une résidence choisie sur la carte filtre la file ; le filtre se montre comme une pastille qu'on retire (D8).

**La fiche équipement.** Dans l'ordre de la décision : ce que c'est et où ; le niveau et l'indice ; les trois décisions ; pourquoi (raisons et leur poids relatif) ; les faits (pose, âge, contrat, visites manquées) ; l'historique mêlant interventions et demandes du locataire, du plus récent au plus ancien (D3, D4, D10).

**La fiche logement** (demandée par In'li) : le nombre de demandes sur 12 mois et depuis 2019, toutes les demandes datées avec leur motif et le texte du locataire, les équipements du logement et leur niveau, l'étiquette DPE. La répétition des demandes compte dans le risque et se lit en tête.

**La fiche résidence** : identité (année, logements, bâtiments, chauffage, étiquette dominante), ce qui est à visiter, à surveiller, décidé, puis les bâtiments.

**La lentille Énergie** (le bonus) : la même carte, les briques se remplissent d'ardoise selon la part des logements au-delà du seuil choisi. Le seuil n'a pas été fixé par In'li ; il se choisit d'un geste sur l'échelle A–G (E par défaut, l'exemple cité) et reste sur l'appareil. La liste range les résidences par nombre de logements au-delà du seuil, avec les opérations déjà envisagées dans le plan.

**Données** : la date du relevé, l'import d'un trimestre (mêmes colonnes que les fichiers actuels), les exports (la file et les décisions pour le prestataire ; les scores au format du défi).

**Méthode** : la seule page de texte. Comment le risque est calculé, sur quelles données, ce qu'il a donné sur 2025 face à l'âge seul, ses limites.

## 5. Les mots

- On écrit « à visiter » plutôt que « critique », « prioritaire » ou « rouge » : c'est ce qu'on va faire, pas un état d'âme.
- « Indice » plutôt que « probabilité » : le nombre classe, il ne promet rien.
- Dates en toutes lettres et courtes (« 12 nov. 2025 ») dans les listes, complètes dans les fiches.
- Lieux du plus large au plus précis : « D · bât. D2 · logt 025 · 2ᵉ ».
- Jamais « IA », jamais « intelligent » : l'outil classe, la personne décide.
