# Assise — résultat

Application interne pour l'équipe technique d'In'li Sud-Ouest : voir venir les pannes bloquantes et décider quoi réparer d'abord. Données : kit BâtIA (fictif), 8 résidences de la métropole toulousaine, historique jusqu'au 31 décembre 2025.

La théorie d'usage qui fonde chaque écran est dans [`UX.md`](UX.md).

## Lancer

```bash
npm start
```

Puis ouvrir **http://localhost:4321**. Rien à installer (Node 18 ou plus, aucune dépendance), aucun compte, aucune clé. `node serveur.mjs` fait la même chose.

Pour l'ouvrir depuis un téléphone du même réseau : `npm run reseau`, puis `http://<adresse-de-la-machine>:4321`.

Rejouer la mise à l'épreuve de la méthode dans le terminal : `npm run eprouver`. Refaire les captures : lancer un serveur à l'état séparé (`ETAT_LOCAL=/tmp/assise PORT=4398 node serveur.mjs`), puis `BASE=http://localhost:4398 python3 outils/captures.py captures`. Les captures posent quatre décisions de démonstration le temps d'une image, puis les retirent.

## Ce qui marche

**À décider** (écran d'accueil) — une phrase : combien d'équipements risquent une panne bloquante dans les neuf mois suivant le dernier relevé (41), puis la liste dans l'ordre du risque. Le surtitre donne la date des données et, quand des trimestres se sont écoulés depuis, combien sont à importer (lien vers l'import). Chaque ligne dit ce qu'est l'équipement, où il est (résidence, bâtiment, logement, étage) et ses deux premières raisons en clair, les faits (pannes, remplacement demandé, signalements) avant l'âge. Trois listes : à décider, à surveiller (171), décidés. Répartition par résidence (une touche filtre la liste, « Toutes » la rend entière) et filtre par famille d'équipement ; l'ordre, lui, ne change pas : c'est le conseil.

**Fiche équipement** — niveau en mot (Prioritaire / À surveiller / Sans alerte), indice de risque sur 100, raisons pondérées en phrases (« 7 dépannages en 12 mois dont 2 arrêts totaux — le dernier le 29 décembre 2025 », « Noté par le technicien : « Pièce de rechange difficile à obtenir » »…), chacune avec ses points, puis le total (« 115 points, l'indice s'arrête à 100 ») ; repères (pose, âge et durée de vie retenue, contrat, prestataire, coût de remplacement de référence), historique des interventions. En bas, toujours visible : **Remplacer · Faire diagnostiquer · Surveiller · Écarter** + note. Rien ne se déclenche seul ; la décision est datée, conservée sur la machine (`etat-local/decisions.json`), réversible, et « Équipement suivant à décider » enchaîne la séance du lundi. Sur téléphone, la note et les initiales n'apparaissent qu'une fois le choix fait ; après l'enregistrement, un lien mène à la liste du prestataire.

**Décidés** — bilan en une phrase (nombre de remplacements et fourchette de coût aux prix de référence, diagnostics, etc.) et une **liste par prestataire**, prête à envoyer : CSV séparé par des points-virgules (s'ouvre en colonnes dans un tableur français), en-têtes en clair, référence, lieu, étage, deux motifs, note, date, initiales, sans notre coût de référence. L'export de toutes les décisions garde, lui, prestataire et coût.

**Fiche logement** — ses équipements et leur risque, ses **demandes de locataire** : nombre depuis 2019, nombre sur douze mois, demandes rouvertes, rythme par année, et le texte de chaque demande (les plus anciennes se déplient) ; puis les interventions dans le logement et son DPE. La répétition des demandes est montrée telle quelle : c'est un signal que l'équipe pèse, pas une règle.

**Le parc** — carte (fond OpenStreetMap) qui s'ouvre sur la France et glisse vers le Sud-Ouest ; trois échelles : France, Sud-Ouest, métropole toulousaine. Les cinq départements du territoire (31, 33, 34, 40, 64) sont tracés ; la Haute-Garonne est « maçonnée », les quatre autres au trait de joint, avec le geste pour les raccorder (import). À l'échelle de la métropole, chaque résidence est un secteur fictif avec son étiquette (lettre, logements, prioritaires) ; le zoom s'arrête à l'échelle du quartier, si bien qu'un secteur ne désigne jamais un immeuble. Liste des résidences de la plus exposée à la plus calme.

**Résidence** — ce qui menace ici (tous les prioritaires, puis les équipements à surveiller), les logements qui appellent le plus, et tous les logements par bâtiment (étage, type, DPE, demandes, risque) ; un lien la montre sur la carte. Une fiche ouverte depuis une résidence enchaîne sur l'équipement suivant de la même résidence : c'est la tournée sur place.

**Recherche** partout : « B1-001 », « Résidence C », « EQP-01633 ».

**Énergie** (bonus) — seuil d'alerte au choix (D, E, F ou G, puisqu'aucun seuil n'est fixé), répartition des étiquettes par résidence, logements en alerte du plus consommateur au moins consommateur (les 40 premiers, le reste se déplie), opérations du plan d'investissement (hypothétique) dans l'ordre d'inscription actuel, avec le nombre de logements en alerte de chaque résidence.

**Méthode** — ingrédients et poids, mise à l'épreuve calculée au démarrage, **import trimestriel** (fichiers CSV de même nom et mêmes colonnes que le kit ; un fichier incomplet est refusé avec la liste des colonnes manquantes ; les fichiers importés vont dans `etat-local/imports/`, jamais dans `donnees/`), **exports** : classement complet avec raisons, décisions, scores au format du défi (`equipement_id, score_risque`).

**Téléphone** — une colonne, navigation en bas d'écran, fiches qui montent du bas, décision à portée de pouce.

## Méthode de risque

Module isolé et remplaçable : [`app/lib/risque.js`](app/lib/risque.js). Contrat unique : `evaluerRisques(tables, dateReference)` rend, pour chaque équipement du périmètre (1 285), un indice de 0 à 100, un niveau et ses raisons. Seul l'historique antérieur à la date de référence est lu.

Une somme de points, chaque point ayant une raison lisible. Les ingrédients suivent les règles de fabrication de l'onglet HYPOTHESES du kit :

| Ingrédient | Points |
|---|---|
| Usure : probabilité de fin de vie dans les 9 mois (loi de Weibull, forme 3,5) selon l'âge rapporté à la durée de vie de référence ; durée de vie raccourcie jusqu'à −30 % selon le taux d'absence aux visites d'entretien, −7 % pour les logements de 85 m² et plus | jusqu'à 40 |
| Dépannages des 12 derniers mois | 6 chacun (3 au plus), +5 par arrêt total (2 au plus) |
| Commentaires d'usure des techniciens sur 18 mois (« usure avancée », « réparation provisoire »…) | 9 chacun (3 au plus) |
| Anomalies constatées en visite d'entretien sur 18 mois | 7 chacune (2 au plus) |
| « Remplacement nécessaire » conclu et pas de remplacement depuis | 12 |
| Demandes du locataire liées à l'équipement sur 12 mois | 4 chacune (3 au plus) |

Niveaux : prioritaire à partir de 45, à surveiller à partir de 22 ; le total s'arrête à 100. Chaque plafond est écrit sur l'écran Méthode et chaque fiche affiche ses points, pour qu'on puisse refaire le calcul. Une panne bloquante est un dépannage noté « Arrêt total ». Les poids ont été fixés a priori depuis les hypothèses du kit, sans ajustement sur le résultat.

**Mise à l'épreuve (réellement calculée)** : placé au 31 décembre 2024, sans regarder la suite, puis comparé aux pannes bloquantes (dépannage « Arrêt total ») du 1er janvier au 30 septembre 2025 — 76 équipements touchés sur 1 285.

| | AUC | Pannes trouvées dans les 129 premiers (10 %) |
|---|---|---|
| Cette méthode | 0,836 | 33 sur 76 |
| Âge seul (référence du kit) | 0,777 | 16 sur 76 |

Contrôle sur l'année précédente (placé au 31/12/2023, pannes de janvier à septembre 2024) : AUC 0,821 contre 0,712 ; 29 pannes trouvées contre 15. Ces chiffres valent pour des données fictives fabriquées selon des règles connues ; la validation sur le parc réel reste à faire.

## Test d'usage

Un sous-agent qui n'avait pas construit l'application l'a utilisée par l'interface seule (Playwright, ordinateur et téléphone), sans explication, pour sept tâches de l'équipe : les trois équipements à traiter en premier ; un locataire de B1-001 qui rappelle ; décider un remplacement et obtenir la liste pour le prestataire ; la résidence la plus exposée et sa place sur la carte ; les logements F ou G ; pourquoi croire le classement ; sur place à la Résidence C, au téléphone. Les sept ont abouti, avec des hésitations. Corrigé ensuite :

- **Les points de la fiche ne se retrouvaient pas avec la page Méthode** (7 dépannages = 28 points, total 115 pour un indice 100) : plafonds écrits, « pts » sur chaque barre, total affiché, « à partir de 45 », panne bloquante définie.
- **La raison affichée sur la ligne était souvent la plus faible** (l'âge) : deux raisons, les faits d'abord. L'âge, donné de trois façons, n'a plus qu'un énoncé (« 14,6 ans, pour une durée de vie retenue de 14 ans (16 prévus) »).
- **L'échéance « d'ici le 30 septembre 2026 » était passée** le jour de la présentation : l'échéance se lit désormais par rapport à aujourd'hui, et l'accueil dit combien de trimestres sont à importer.
- **La liste pour le prestataire n'était ni trouvable ni envoyable** : lien après la décision, bouton explicite, fichier refait (voir Décidés).
- **Listes tronquées** : tous les prioritaires d'une résidence avant le bouton « voir les autres », logements en alerte et demandes anciennes dépliables.
- **Sur place**, « Équipement suivant à décider » restait dans la liste de l'accueil et quittait la résidence : il reste désormais dans la résidence ouverte. La page d'une résidence mène à la carte, à l'échelle de la métropole.
- Carte : étiquettes de l'Est plus coupées, libellés des départements centrés et visibles sur téléphone, étiquette de la métropole au-dessus de Toulouse. Français : « 1ᵉʳ », « locataire absent », « Choisissez une résidence », « économie visée … kWh/m²/an », plus de « kit » ni de « défi » à l'écran.

**Second tour**, avec un autre testeur neuf, sur les trois tâches qui avaient le plus hésité : recompter l'indice du premier équipement (réussi : « Total : 115 points, l'indice s'arrête à 100 »), décider et récupérer la liste pour l'entreprise (réussi, fichier ouvert proprement dans un tableur français), enchaîner sur place à la Résidence C au téléphone (réussi en partie). Corrigé ensuite : la raison la plus lourde rangée dans « et 4 autres raisons » est nommée (« dont l'âge ») ; filtrée sur une résidence, la liste le dit (« Liste limitée à la Résidence C : 1 à décider, 4 à surveiller »), les compteurs suivent et la pastille choisie reste à l'écran ; la colonne « Motifs » du fichier devient « Constats ». Reste de ce tour : la fiche n'a pas d'adresse propre à partager, et le fichier pour l'entreprise n'a ni adresse postale, ni contact d'accès, ni modèle d'appareil, que les données ne contiennent pas (la note sert à les ajouter).

## Ce qui manque

- Les quatre départements hors Haute-Garonne n'ont pas de données : la carte les montre prêts à raccorder, sans aucun chiffre inventé.
- Les décisions sont partagées par tous ceux qui ouvrent l'application sur la même machine, sans comptes ni droits ; une version interne demanderait une authentification et un journal.
- L'import remplace des fichiers entiers ; il ne fusionne pas des fichiers partiels d'un trimestre.
- Les rapports trimestriels du prestataire (PDF) ne sont pas exploités.
- Le classement des 29 opérations du plan d'investissement sous l'enveloppe de 1,5 M€ (défi 2) n'est pas proposé : l'écran Énergie montre l'ordre actuel et la situation DPE pour aider à juger.
- Relevés du test d'usage non traités : le nombre de logements desservis (chaufferie, ascenseur) n'entre pas dans l'indice (il se lit dans le lieu, la personne en juge) ; pas d'export CSV de la liste énergie ; quelques incohérences propres aux données (logement « vacant » avec des demandes récentes, demande à la fois « rouverte » et « résolue ») sont affichées telles quelles.
- Le fond de carte est chargé depuis les serveurs d'OpenStreetMap (aucune donnée du parc n'y est envoyée) ; hors connexion, la carte n'affiche que les contours des départements.

## Fichiers

- `serveur.mjs` — serveur local sans dépendance (API, exports, import).
- `app/lib/risque.js` — **module de risque remplaçable**. `app/lib/epreuve.js` — mise à l'épreuve. `app/lib/csv.js`, `app/lib/chargement.mjs` — lecture des données.
- `app/index.html`, `app/style.css`, `app/app.js` — interface.
- `app/vendor/` — Leaflet 1.9.4, polices Source Serif 4 et Source Sans 3 (licence OFL), contours des 5 départements (france-geojson, simplifiés).
- `outils/eprouver.mjs`, `outils/captures.py` — vérifications.
- `captures/` — captures réelles, ordinateur et téléphone.
