# Livrable du défi 2 : priorisation des rénovations

`prioriser.py` note les 29 opérations du plan d'investissement sur cinq critères, puis construit un calendrier 2026 à 2035 sous un plafond de 1,5 M€ par an. Il lit les CSV du kit sans rien y modifier et écrit six fichiers dans ce dossier.

```bash
uv run --with pandas --with 'pulp<3' python livrables/defi2/prioriser.py donnees/kit-batia/donnees livrables/defi2 livrables/defi1/score_risque_2026.csv
```

Le troisième argument, le score du défi 1, est facultatif. Quand il est donné, chaque opération reçoit une colonne « pannes attendues par an » calculée sur ses équipements cibles. Elle est affichée, elle n'entre pas dans le score.

## Les fichiers

| Fichier | Contenu |
|---|---|
| `classement_operations.csv` | Une ligne par opération : les cinq critères sur 10, le score et le rang dans chacun des cinq réglages de poids, les pannes attendues, l'année de début recommandée, les alertes de données |
| `plan_recommande.csv` | Le calendrier recommandé : année de début, durée, coût par an, écart avec l'année souhaitée |
| `plans_comparaison.csv` | Les mêmes mesures pour les huit calendriers comparés : dépense par an, étiquettes G, F, E au 1er janvier 2026, 2028, 2031 et 2034, énergie économisée, logements-années en infraction, loyers perdus, statut du solveur |
| `poids_effectifs.csv` | Pour chaque réglage, le poids annoncé de chaque critère et son poids réellement exercé sur le classement |
| `plans_tous.csv` | L'année de début de chaque opération dans chacun des huit calendriers |
| `operations_enrichies.csv` | Toutes les variables intermédiaires, une ligne par opération |

## Les cinq critères

| Critère | Ce qu'il mesure | Source |
|---|---|---|
| Réglementaire | Points d'étiquette retirés par l'opération, 3 par logement qui sort de G, 2 de F, 1 de E, recalculés à partir des consommations de la table 03 et du gain déclaré | tables 03 et 08 |
| Énergie par euro | kWh d'énergie primaire économisés par an et par euro investi | tables 03 et 08 |
| Maintenance | Moitié dépenses de commandes liées à l'opération sur 2023 à 2025, moitié indice de pannes des équipements cibles, 3 par arrêt total, 2 par fonctionnement dégradé, 1 par gêne mineure | tables 06 et 07 |
| Locataire | 60 % demandes liées au sujet de l'opération sur 2023 à 2025, 20 % vacance, 20 % rotation | tables 03 et 05 |
| Fin de vie | Âge moyen des équipements cibles rapporté à leur durée de vie de référence, plafonné à 120 % | tables 04 et 10 |

Chaque critère est ramené sur 10. Le réglage de base pèse 25 réglementaire, 20 énergie, 20 maintenance, 15 locataire, 20 fin de vie. Trois autres réglages servent de curseur, réglementaire d'abord, coût d'abord, locataire d'abord, et un cinquième reproduit la pondération du commanditaire.

## Les quatre corrections du 10 octobre

Elles viennent de la relecture critique de la première version de la méthode. Les trois premières changent le code, la quatrième change ce qu'on dit.

**Plafond au 90e centile.** Chaque critère était ramené sur 10 en divisant par son maximum. Une seule opération hors norme, le solaire de la résidence H sur l'énergie par euro, écrasait tout le critère : les autres opérations y valaient presque zéro et le critère ne pesait plus rien. Les valeurs sont maintenant plafonnées au 90e centile des valeurs non nulles avant la mise à l'échelle. La fin de vie garde son échelle fixe, 120 % de la durée de vie vaut 10, parce qu'elle est déjà bornée. Le classement bouge peu, mais le critère énergie compte de nouveau.

**Poids effectifs affichés.** Un poids annoncé n'est pas un poids exercé : un critère dont presque toutes les opérations sont à zéro ne départage personne. `poids_effectifs.csv` donne, par réglage, la part réelle de chaque critère dans le score moyen. Dans le réglage de base, le critère locataire pèse 27 % pour 15 annoncés, et le réglementaire 17 % pour 25 annoncés, parce que presque toutes les opérations ont des demandes de locataires et peu d'entre elles sortent des logements de G ou F. Il faut le dire plutôt que le cacher. Si l'équipe veut que les poids exercés égalent les poids annoncés, il suffit de diviser chaque critère par sa moyenne ; ce n'est pas fait, parce que le classement serait alors dicté par les critères les plus rares.

**Pondération du commanditaire dans le curseur.** Les documents du kit donnent la pondération du commanditaire : 40 état technique, 30 impact énergétique, 20 coût, 10 urgence sociale. Elle est reproduite ainsi : état technique = maintenance 20 + fin de vie 20, énergie = MWh économisés par an 30, coût = 20 pour l'opération la moins chère et 0 pour la plus chère, urgence sociale = locataire 10. Son top 5 partage quatre opérations avec le nôtre, les convecteurs de G, les chaudières de F, les ballons de G et la chaufferie de C ; il ne contient pas l'ITE de G, parce qu'il ignore le calendrier légal. Le critère coût y pèse 43 % du score moyen pour 20 annoncés.

**Objectif monétisé au lieu de « conformité d'abord ».** La première version minimisait d'abord le nombre de logements-années en infraction, puis le score. Ce choix achetait 76 logements-années au lieu de 88 au prix de 290 MWh par an d'économies d'énergie en 2028 et de 24 logements F de plus au 1er janvier 2028. Le calendrier recommandé maximise maintenant un seul objectif : les points de score, moins les loyers perdus par les logements interdits à la location, à raison d'un point de score pour 1 000 €. Un logement en infraction coûte un loyer annuel de 7 000 € multiplié par le taux de rotation de sa résidence, lu dans la table 03. Le loyer de 7 000 € n'est nulle part dans le kit : c'est une hypothèse à afficher et à faire régler par le commanditaire. Le tableau ci-dessous donne la frontière pour 250, 500, 1 000 et 2 000 € par point.

**Sur la date d'interdiction des G.** Les logements G ne peuvent plus être loués depuis le 1er janvier 2025, les F à partir de 2028, les E à partir de 2034. Le compte des infractions commence au 1er janvier 2027, parce qu'aucune opération lancée en 2026 n'est achevée avant la fin 2026 : sur le 1er janvier 2026 et sur le 1er janvier 2027, les 38 logements G sont en infraction quel que soit le plan, et les compter n'aurait changé aucun classement. La table 03 en donne 39 ; les étiquettes recalculées à partir des consommations en donnent 38, sur 6 logements où l'étiquette fournie et l'étiquette recalculée diffèrent.

Le statut du solveur est imprimé et enregistré pour chaque calendrier : toutes les résolutions sont « Optimal », avec un délai de 240 secondes par résolution ; l'ordre chronologique n'a pas besoin de solveur.

## Résultats

Classement de base, p90, avec le rang dans la pondération du commanditaire :

| Rang | Opération | Résidence | Score | Rang commanditaire |
|---|---|---|---|---|
| 1 | Convecteurs remplacés par radiateurs à inertie | G | 72,0 | 1 |
| 2 | Chaudières individuelles à condensation | F | 57,0 | 2 |
| 3 | Ballons électriques remplacés par thermodynamiques | G | 53,2 | 3 |
| 4 | Chaufferie collective | C | 50,6 | 4 |
| 5 | Isolation thermique par l'extérieur | G | 47,5 | 9 |
| 6 | Production d'eau chaude solaire | H | 41,6 | 10 |
| 7 | Chaudières individuelles, renouvellement anticipé | A | 41,5 | 5 |

Les huit calendriers comparés :

| Calendrier | Logements-années en infraction 2027 à 2035 | F au 1er janvier 2028 | E au 1er janvier 2034 | MWhEP par an économisés en 2028 | Retard moyen sur l'année souhaitée |
|---|---|---|---|---|---|
| Ordre chronologique des demandes, trous comblés | 221 | 153 | 4 | 641 | 1,41 |
| Score seul | 302 | 67 | 48 | 1 667 | 0,86 |
| Conformité d'abord | 76 | 60 | 4 | 1 745 | 2,07 |
| Monétisé, 250 € par point | 82 | 35 | 7 | 2 091 | 1,41 |
| Monétisé, 500 € par point | 85 | 36 | 7 | 2 032 | 1,24 |
| Monétisé, 1 000 € par point, recommandé | 88 | 36 | 7 | 2 032 | 1,31 |
| Monétisé, 2 000 € par point | 118 | 36 | 7 | 2 032 | 1,17 |
| Pondération du commanditaire, monétisé à 1 000 € | 85 | 36 | 7 | 2 032 | 1,24 |

Lecture. Aucun calendrier ne vide les F au 1er janvier 2028 sous 1,5 M€ par an ; le plancher est à 35 ou 36 logements. Le calendrier recommandé accepte 12 logements-années de plus que « conformité d'abord », soit environ 12 000 € de loyers, et rapporte 290 MWh par an de plus en 2028, 24 logements F de moins au 1er janvier 2028 et 68 points de score en plus. Les calendriers monétisés et le score seul ramènent les G à zéro au 1er janvier 2028 ; l'ordre chronologique en laisse 9 et « conformité d'abord » 3. Au 1er janvier 2031 il ne reste aucun F sauf avec le score seul, 34, et l'ordre chronologique, 1.

Le calendrier recommandé :

| Année | Opérations | Dépense |
|---|---|---|
| 2026 | Convecteurs de G, chaufferie de C, solaire de H, ballons de B, halls de A, toiture de G, porte de hall de B | 1,50 M€ |
| 2027 | Ballons thermodynamiques de G, combles de F, VMC de A, ascenseurs de C, halls de G et de F, ascenseur de B | 1,49 M€ |
| 2028 | ITE de G, première année, pompes à chaleur de D, halls de C | 1,49 M€ |
| 2029 | ITE de G, seconde année, combles de A, ballons thermodynamiques de E | 1,48 M€ |
| 2030 | Chaudières de F, ascenseurs de G, halls de B, toiture de C | 1,38 M€ |
| 2031 | Menuiseries de C, toiture de F | 1,41 M€ |
| 2032 et 2033 | ITE de C sur deux ans | 1,45 M€ par an |
| 2034 | Chaudières de A, menuiseries de F | 1,38 M€ |
| 2035 | VMC hygroréglable de G | 0,38 M€ |

Deux lignes demandent un arbitrage humain. Les chaudières de A, posées en 2016, sont repoussées à 2034 parce qu'aucune ne dépasse sa durée de vie avant ; le score du défi 1 y attend pourtant 14 pannes bloquantes par an, le chiffre le plus élevé du plan, et c'est l'argument pour avancer. Les chaudières de F passent de 2026 à 2030, parce que l'ITE de G et les convecteurs de G prennent le budget des premières années pour sortir les G.

## Limites

Les gains d'énergie sont ceux déclarés dans la table 08, appliqués uniformément aux logements du périmètre. Les menuiseries n'ont pas de famille d'équipement dans le kit, les volets roulants en tiennent lieu. Les toitures et les halls n'ont ni équipement ni commande rattachée, leur score ne vient que des demandes des locataires. Le loyer de 7 000 € et la valeur de 1 000 € par point sont des hypothèses. Le plafond de 1,5 M€ par an vient de la notice ; une enveloppe exceptionnelle en 2026 et 2027 est le seul moyen de descendre sous 35 logements F au 1er janvier 2028.
