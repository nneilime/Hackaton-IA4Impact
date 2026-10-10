# Assise — théorie d'usage

*Assise : rang de briques posées sur la même ligne. C'est aussi ce sur quoi l'on se tient.*

Ce document dit pour qui l'outil est fait, à quel moment on l'ouvre, et en tire chaque décision d'écran, d'ordre, de mot et de geste. Il précède le code : quand une décision d'interface hésite, c'est ici qu'on tranche.

---

## 1. Les gens, le moment, le geste

**Qui ouvre l'outil.** L'équipe technique d'In'li Sud-Ouest : responsables et chargés de patrimoine ou de maintenance. Ils connaissent leurs résidences par leur nom, leurs prestataires par leur contrat, une chaudière par son bruit. Ils ne sont pas statisticiens et n'ont pas à le devenir. Ce qu'ils ignorent aujourd'hui, ce n'est pas le métier : c'est *lequel* des 1 285 équipements suivis va lâcher, et ils l'apprennent par l'appel d'un locataire sans chauffage.

**Trois moments, trois postures.**

| Moment | Posture | Question dans leur tête | Ce que l'outil doit rendre |
|---|---|---|---|
| Lundi matin, au bureau, avant le point avec le prestataire | Assis, vingt minutes, café | « Qu'est-ce que je traite cette semaine, et dans quel ordre ? » | Une liste courte, ordonnée, où chaque ligne dit *pourquoi* — et un geste pour trancher. |
| Un locataire rappelle pour la troisième fois | Au téléphone, une main libre | « Ce logement, il a quoi ? Ce n'est pas la première fois, si ? » | Le logement retrouvé en trois caractères, son historique de demandes visible d'un coup d'œil. |
| Sur place, dans une résidence | Debout, téléphone, dehors | « Ici, qu'est-ce qui menace ? » | La résidence, ses équipements à risque, en une colonne lisible au soleil. |
| Chaque trimestre, à l'arrivée des fichiers | Au bureau, sans urgence | « Mettre à jour, et envoyer la liste à chacun. » | Déposer les fichiers, récupérer les listes. |

**Ce qu'ils doivent pouvoir faire sans apprendre l'outil** : savoir quoi faire d'abord, comprendre pourquoi, décider, transmettre.

## 2. La doctrine

Sept règles. Chacune vient d'un constat sur ces gens-là.

### R1 — On ouvre sur une question, pas sur un tableau.
*Constat : le lundi matin, personne ne veut « explorer des données » ; on veut savoir quoi faire.*
L'écran d'accueil répond par une phrase : combien d'équipements demandent une décision, puis la liste elle-même, dans l'ordre du risque. Pas de rangée de chiffres clés, pas de graphique d'accueil. La carte existe, mais elle n'est pas le premier écran : elle répond à « où ? », qui vient après « quoi ? ».

### R2 — Le lieu avant le numéro.
*Constat : sur le terrain, on se repère par résidence, bâtiment, étage, porte — jamais par `EQP-03865`.*
Chaque équipement est nommé par ce qu'il est et où il est : « Chaudière gaz — Résidence F, bâtiment F2, logement 14, 3ᵉ étage ». L'identifiant technique reste disponible, en petit, pour le bon de commande.

### R3 — Une raison se lit, elle ne se décode pas.
*Constat : un score seul ne convainc ni un technicien ni un prestataire ; une raison, si.*
Le niveau de risque est un **mot** (« Prioritaire », « À surveiller », « Sans alerte ») porté par une couleur, jamais une couleur seule. Les raisons sont des phrases dans la langue du métier : « 21 ans pour 18 prévus », « 3 dépannages depuis mars », « le technicien a noté : usure avancée », « 2 visites d'entretien manquées ». Le score chiffré existe, au second plan, pour trier et exporter.

### R4 — L'outil propose, la personne tranche.
*Constat : la responsabilité d'une dépense reste humaine ; un outil qui « décide » serait contourné.*
Rien n'est déclenché par l'outil. Devant chaque équipement : quatre gestes — **Remplacer**, **Faire diagnostiquer**, **Surveiller**, **Écarter** — et une note libre. La décision est datée et conservée ; elle sort de la liste « à décider » mais reste consultable et réversible. L'outil ne commande rien : il prépare la liste que la personne enverra.

### R5 — Montrer d'où vient la confiance.
*Constat : on ne se fie pas à un chiffre dont on ignore la fabrication.*
La méthode est écrite en clair, une page, avec ses ingrédients et leur poids. Elle est mise à l'épreuve sur le passé : on s'est placé au 31 décembre 2024 et on a regardé ce qui a cassé en 2025. Seuls les chiffres réellement calculés sont affichés, comparés à la règle « âge seul ».

### R6 — Un écran, une question.
*Constat : un écran qui répond à tout ne répond à rien.*
Quatre lieux, quatre questions :
1. **À décider** — « Quoi d'abord ? »
2. **Le parc** — « Où ? » (carte, résidences, logements)
3. **Énergie** — « Quels logements sont des passoires ? » (bonus demandé)
4. **Méthode** — « Pourquoi croire ce classement ? Comment le mettre à jour ? »
La recherche (logement, résidence, équipement) est accessible partout, parce que l'appel d'un locataire n'attend pas.

### R7 — Le téléphone, c'est le terrain.
*Constat : sur place, on a une main, un pouce, et du soleil sur l'écran.*
Une colonne, des cibles larges, un contraste fort, la navigation en bas d'écran, le détail qui monte du bas. Rien qui exige un survol de souris.

## 3. Les mots

On écrit comme on parle dans un service technique, et on s'y tient partout.

| On dit | On ne dit pas | Pourquoi |
|---|---|---|
| Panne bloquante | Incident critique, événement | C'est le terme du défi et du terrain : un dépannage « arrêt total ». |
| Risque, prioritaire, à surveiller | Score, probabilité, prédiction | Le score est un outil de tri, pas un message. |
| Raisons | Variables, facteurs, features | On justifie une décision, on ne décrit pas un modèle. |
| Décider, remplacer, faire diagnostiquer | Valider, traiter le ticket | Ce sont les vrais gestes. |
| Dépannage, visite d'entretien, logement absent | Intervention de type X | Le vocabulaire des comptes rendus de prestataire. |
| D'ici le 30 septembre 2026 | À horizon T+9 | La date réelle, pas une notation. |

Les nombres sont écrits à la française (1 285, 2 600 €), les dates en toutes lettres quand on les lit (« 12 novembre 2025 ») et en chiffres quand on les compare.

## 4. L'ordre

**L'ordre de la liste est l'ordre du risque**, et il n'en change pas sans qu'on le demande. On peut filtrer par résidence ou par famille d'équipement, jamais réordonner par une colonne arbitraire : l'ordre *est* le conseil.

**L'ordre d'une fiche équipement** suit le raisonnement d'un technicien : qu'est-ce que c'est et où → à quel point c'est grave → pourquoi on le pense → ce qui s'est passé (historique) → ce qu'on décide. La décision est en bas parce qu'elle vient après la lecture ; sur téléphone, elle reste à portée de pouce.

**L'ordre d'une fiche logement** : où il est → ses équipements et leur risque → combien de fois le locataire a appelé, et quand → ce que les prestataires ont fait. La répétition des demandes est montrée telle quelle (nombre, rythme dans le temps, demandes rouvertes) : c'est un signal que l'équipe pèse elle-même, pas encore une règle.

## 5. Le déséquilibre : un parc qui se raccorde

Les données couvrent 8 résidences de la métropole toulousaine ; le territoire compte cinq départements. On n'en fait pas un manque, on en fait la **méthode de déploiement** : un outil de ce genre se met à l'épreuve sur un secteur dont on connaît l'histoire, puis s'étend.

À l'écran, cela prend une forme simple : la carte du Sud-Ouest montre les cinq départements. La Haute-Garonne est maçonnée — ses résidences, ses comptages. Les quatre autres sont tracées au trait de joint : le mur est prêt à recevoir ses briques, et le geste pour les poser est là, dans l'import trimestriel. Aucun chiffre n'est inventé pour eux, aucune excuse n'est écrite.

## 6. La beauté qui sert la lecture

L'image de référence est un mur de briques foraines toulousaines : longues, plates, posées en rangs horizontaux, séparées par un joint épais couleur de sable. On en retient une **grammaire**, pas un décor.

- **L'assise horizontale.** Les listes sont faites de rangs longs et bas, séparés par un joint clair : la lecture se fait à l'horizontale, ligne par ligne, comme on compte des rangs.
- **La cuisson comme intensité.** Le risque est exprimé par la couleur de la brique, de la plus cuite (prioritaire, brun-rouge profond) à la plus pâle (sans alerte, sable du joint). Une seule famille de teintes : pas de feu tricolore, pas de vert « tout va bien » qui rassure à tort. Toujours doublée d'un mot.
- **Le joint comme fond.** Le fond de l'application est le sable du mortier ; l'encre est un brun très sombre, jamais le noir pur.
- **Deux voix typographiques.** Un caractère à empattements (Source Serif) pour ce qu'on lit comme une phrase — titres, raisons, chiffres qui comptent ; un caractère sans empattements (Source Sans) pour ce qu'on manipule — boutons, étiquettes, tableaux. Chiffres tabulaires partout où l'on compare.
- **Le mouvement ne sert qu'à dire d'où l'on vient** : la fiche qui monte depuis la ligne touchée, la carte qui glisse de la France au Sud-Ouest puis à Toulouse. Pas d'animation d'agrément.

## 7. Ce que l'outil refuse de faire

- Décider à la place de quelqu'un, ou déclencher une commande.
- Afficher un chiffre de performance qu'il n'a pas calculé.
- Inventer une adresse : les résidences sont placées à des positions fictives, sous forme de secteurs et non de points sur un immeuble.
- Envoyer quoi que ce soit hors de la machine : pas de service en ligne, pas d'IA distante. Le fond de carte public est la seule ressource extérieure, et il ne reçoit aucune donnée du parc.
- Montrer tout à la fois.

## 8. Comment on vérifie qu'on s'y est tenu

- Une personne qui n'a pas construit l'outil doit, sans explication, réussir : « que traiter en premier cette semaine ? », « pourquoi celui-là ? », « ce logement a-t-il déjà appelé ? », « envoyer la liste au prestataire », « où sont les logements classés F ou G ? ». Chaque hésitation observée est corrigée (voir `RESULTAT.md`).
- Chaque écran est relu sur ordinateur et sur téléphone, en captures réelles.

## 9. De la doctrine à l'écran : décisions prises

| Décision d'interface | Règle |
|---|---|
| L'accueil est une phrase (« 41 équipements risquent une panne bloquante dans les neuf mois suivant le dernier relevé ») suivie de la liste, pas un tableau de bord. L'échéance se lit depuis aujourd'hui : tant qu'elle est à venir, c'est une date ; passée, elle est rapportée au relevé, et le surtitre dit combien de trimestres attendent leur import. Des données vieillies ne s'excusent pas, elles appellent un geste. | R1, R5 |
| Sous la phrase, une seule agrégation : combien par résidence, cliquable pour filtrer. Elle sert à grouper les passages du prestataire. | R1, R6 |
| Chaque ligne : ce que c'est (titre), où (résidence · bâtiment · logement · étage), deux raisons en phrase, les faits avant l'âge (une panne qui a eu lieu convainc plus qu'un âge qui approche), puis le niveau en mot. Le rang est à gauche, en chiffre de livre. | R2, R3 |
| « Indice » de risque, pas « score » ni « probabilité » : un chiffre sur 100 qui trie, sans laisser croire à une certitude. | R3, §3 |
| Le niveau est un mot dans une pastille couleur brique ; la bande de gauche de chaque rang reprend la même cuisson. Pas de vert. | R3, §6 |
| La fiche s'ouvre par-dessus la liste (panneau à droite sur ordinateur, feuille montante sur téléphone) : on ne perd jamais sa place dans la liste. Le bouton retour du téléphone la referme. | R6, R7 |
| Les raisons portent leur poids en points et une barre courte : on voit ce qui pèse sans avoir à lire une légende. | R3, R5 |
| La décision tient en quatre verbes et reste collée en bas de la fiche ; « Équipement suivant à décider » enchaîne la séance. | R4, R7 |
| Après décision, l'équipement quitte « À décider » pour « Décidés », d'où sort une liste CSV par prestataire. | R4 |
| La recherche accepte la façon dont on dit un logement au téléphone (« B1-001 », « b1 1 »). | R6 |
| La carte s'ouvre sur la France et glisse vers le Sud-Ouest : on s'oriente comme on le ferait sur une carte murale. Les résidences y sont des secteurs, pas des points. | R6, §5, §7 |
| Les quatre départements sans données sont tracés au trait de joint, avec le geste « raccorder » : le déploiement, pas le manque. | §5 |
| La page Méthode dit en phrases ce que la mise à l'épreuve a donné, avec les vrais chiffres calculés au démarrage. | R5 |
| L'écran Énergie laisse choisir le seuil d'alerte (D à G) puisque l'équipe ne l'a pas encore fixé ; les étiquettes gardent les couleurs réglementaires du DPE, que tout le monde lit déjà. | R3, §3 |
| Chaque barre de la fiche porte ses points, et la fiche donne le total (« 115 points, l'indice s'arrête à 100 ») ; la page Méthode écrit chaque plafond. Une raison qu'on ne peut pas recompter n'inspire pas confiance. | R3, R5 |
| L'âge n'a qu'un énoncé : « 14,6 ans, pour une durée de vie retenue de 14 ans (16 prévus) ». Trois chiffres pour une même idée font douter des trois. | R3 |
| Après une décision, le chemin suivant est sous le pouce : la liste du prestataire, ou l'équipement suivant. Sur place, « suivant » reste dans la résidence où l'on se trouve. | R4, R7 |
| La liste pour un prestataire est un bon de travail : où aller (lieu, étage), pourquoi (deux motifs), ce qui est demandé, qui l'a décidé ; jamais notre coût de référence. Elle s'ouvre en colonnes dans un tableur français. | R4, §3 |
| Sur téléphone, la note et les initiales n'apparaissent qu'une fois le choix fait : avant, l'écran sert à lire. | R7 |
| Une liste coupée dit ce qu'elle cache, et le reste se déplie sur place ; un bouton « voir les autres » ne cache jamais un prioritaire. | R6 |
| Un filtre se dit en toutes lettres : « Liste limitée à la Résidence C », compteurs compris. Un filtre qu'on ne voit plus fait lire une partie pour le tout. | R1, R7 |

Ces sept dernières lignes viennent des deux tours de test d'usage : des utilisateurs qui découvraient l'outil y ont hésité, la règle était déjà là, l'écran ne la tenait pas.
