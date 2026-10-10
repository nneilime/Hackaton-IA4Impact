# AGENTS.md — Calculateur de l'Indicateur de Confiance (Hackathon TER liO)

> À placer à la racine du dossier du projet sous le nom `AGENTS.md`
> (lu automatiquement par Antigravity CLI), ou à coller dans le premier prompt.

## Contexte
Hackathon "IA for Impact" — Défi SNCF TER liO « Dessine-moi une mobilité durable ».
Copilote du voyage scolaire. L'Indicateur de Confiance est un score de 0 à 100 qui mesure la
**sérénité opérationnelle** d'une sortie scolaire en train. Il est recalculé pour chaque triplet :
[train liO + trajet gare-site + effectif de la classe]. Il est calculé seulement sur les 2-3 meilleures
propositions présélectionnées (architecture en entonnoir) : la rapidité vient de là, pas du code.

## Contraintes de code (le développeur est niveau débutant+)
- Python 3, pandas autorisé. Fonctions simples + dictionnaires, **pas de classes**.
- Commentaires et noms en français. Chaque fonction a une docstring d'une ligne.
- Tous les paramètres réglables sont des constantes en haut du fichier (jamais cachées dans une fonction).
- Le résultat est un dict sérialisable en JSON (pour l'interface). Aucun nom d'école dans les sorties.
- Chaque règle de gestion est testée avec pytest.

## Les données (faits vérifiés sur les vrais fichiers)
**`Data_Hackathon.csv`** : séparateur `;`, encodage `utf-8-sig`, 1 891 lignes, 217 trains. **1 ligne = 1 train × 1 mois (2026).**
- Colonnes utiles : `N° Train` (int), `Axe`, `Circ Prévues Théorique`, `Circ Prévues réalisé`, `Frequentation` (sans accent, 8 vides),
  `Taux régularité du train` (texte `'63,20%'`, de 0 à 100), `Nombre de suppressions`, `Taux SUPP` (texte `'9,52%'`).
- Colonne parasite finale `Unnamed: 17` (100 % vide) : l'ignorer.
- ⚠️ **`Taux SUPP` est VIDE quand il y a 0 suppression** (714 lignes). Ne jamais faire la moyenne de cette colonne
  (les mois à zéro seraient ignorés et le taux gonflé). Recalculer : somme des suppressions ÷ somme des circulations réalisées.
- Ce taux peut dépasser 100 % (ex. 22 suppressions pour 20 circulations réalisées = 110 %) : plafonner à 100.
- Agrégation d'un train sur ses mois : régularité = moyenne **pondérée** par les circulations réalisées ;
  stabilité = réalisées ÷ prévues ; fréquentation = moyenne puis **percentile** parmi tous les trains (0 = calme, 1 = le plus chargé).
- Les noms de colonnes doivent être trouvés de façon robuste (normaliser accents/casse/symbole `°`), pas en dur.

**`Détail desserte (Liste des trains groupes).csv`** : même format (`;`, `utf-8-sig`), 796 179 lignes, 766 trains, février à juin 2026.
Colonnes : `Date` (`JJ/M/AAAA`, ex. `30/4/2026`), `Numéro de circulation`, `Heure d'arrivée` / `Heure de départ` (`HH:MM:SS`),
`Libellé arrêt`, `Code arrêt`, `Ordre desserte`. **1 ligne = 1 arrêt d'un train un jour donné.**
- Jointure : `Numéro de circulation` = `N° Train` (entiers, aucun nettoyage). 210 des 217 trains sont présents.
  Les 7 absents sont des trains estivaux (juillet-août) : **ce n'est pas une erreur** → pas d'horaire, la marge horaire n'est pas évaluée.
- Ce fichier est le **catalogue des trains éligibles aux groupes** : un train absent n'est pas proposé.
- Ne jamais lire ce fichier à chaque calcul : le charger une fois (≈ 2-3 s) en filtrant sur les trains utiles.

## Règles métier (validées par l'équipe — ne pas modifier)
- Échelle 0-100. Vert 85-100 / Orange 65-84 / Rouge < 65.
- 4 piliers (répartition de 100 points validée par l'enseignant) : **Capacité 40 %** (critère « couperet »), **Fiabilité 30 %**,
  **Faisabilité terrain 20 %**, **Pairs 10 %** (somme = 1).
- Marge horaire : l'enseignant exige **15 à 20 min** entre l'arrivée devant le site et le début de l'activité (recompter, toilettes, sacs).
  Marche maximale tolérée : 20 min.
- Vitesse de marche de groupe 2,5-3 km/h. ≤ 20 min à pied = note max. Un bus urbain unique = légère décote.
- Plafond strict de **50 voyageurs** : classe + options déjà posées. Les options des autres écoles sont un **nombre**, jamais une identité.
- **Veto → rouge, score plafonné à 64, trajet affiché (jamais masqué) avec une explication** : jauge > 50 ; suppressions chroniques ;
  marche > 20 min sans bus ; cheminement piéton dangereux ; marge horaire insuffisante.
- Avis des enseignants **simulés** pour le PoC. Badge « Coup de cœur des enseignants » si note élevée.
- Aucun élément de paiement dans cet indicateur.

## Les 8 sous-critères (poids internes et seuils = hypothèses à valider, tous en constantes)
| Pilier | Sous-critère | Poids interne | Note 0-100 |
|---|---|---|---|
| Fiabilité | Régularité | 40 % | taux de régularité pondéré |
| | Suppressions | 25 % | `100 − 5 × taux` ; veto si taux ≥ 10 % |
| | Stabilité de l'offre | 15 % | réalisées ÷ prévues |
| | Fréquentation (anti-pointe) | 20 % | `100 × (1 − percentile)` |
| Faisabilité | Accès dernier km | 50 % | ≤ 20 min : 100 ; bus : 85 ; sinon veto |
| | Sécurité du cheminement | 20 % | trottoir : 100 ; sans : veto ; inconnu : ignoré + alerte |
| | Marge horaire avant l'activité | 30 % | ≥ 20 min : 100 ; 15-20 min : 60→100 ; < 15 min : veto ; sans horaires : ignorée |
| Capacité | Places restantes | 100 % | 100 jusqu'à 60 % de remplissage, puis descend à 40 ; > 50 : veto |
| Pairs | Avis (coup de cœur) | 50 % | note/5 × 100 ; sans avis : 70 neutre |
| | Logistique de survie | 25 % | pique-nique couvert 60 + consignes 40 |
| | Adéquation pédagogique | 25 % | thème du projet dans les thèmes du site : 100 ; sinon 30 |

Un sous-critère sans donnée est **ignoré** et les poids restants sont re-répartis (jamais compté comme 0).

## Contrat d'interface (à respecter exactement : les tests l'utilisent)
```
charger_profils_trains(chemin_csv)  -> {"86960": {regularite_pct, suppression_pct, stabilite_pct,
                                        frequentation_percentile, axe, nb_mois}}
charger_desserte(chemin_csv, trains_utiles=None) -> DataFrame (train, date, gare, arrivee_min, depart_min, ordre)
trains_eligibles(desserte) -> {"871813", ...}
heure_arrivee_en_gare(desserte, n_train, date, gare) -> minutes depuis minuit ou None
calculer_indice(train, site, effectif, options_actives, theme_projet=None,
                heure_arrivee_gare=None, heure_debut_activite=None) -> dict
```
`site` = dict : `distance_m, bus_unique, trottoir_ok, pique_nique_couvert, consignes, themes, note_moyenne, nb_avis` (valeurs possibles `None`).
Résultat de `calculer_indice` : `score, couleur, bloque, vetos, alertes, message, composantes (note, poids, points, details), point_faible, badge_coup_de_coeur`.

## Tâche 1 — Calculateur (`indice_confiance.py`)
Implémenter le contrat ci-dessus. Le fichier `test_indice_confiance.py` est la référence (49 tests).

## Tâche 1 bis — Données simulées
Script `generer_donnees_simulees.py` (graine fixe) → `donnees_simulees/` : `sites.csv` (15 sites d'Occitanie, `gare_proche` = nom EXACT
d'un `Libellé arrêt` réel, avec les colonnes de `site`), `options.csv` (30 vrais N° Train, dates, places déjà prises 0-45, jamais de nom d'école).
Colonne `source` = « simulé ». Inclure des cas pièges : site à 35 min sans bus, train presque plein, site sans avis, chemin sans trottoir.

## Tâche 2 — UI/UX (après validation de la tâche 1)
Composant d'affichage pour l'interface existante : jauge colorée, message explicatif, 4 piliers en barres, alertes, badge,
et pour un trajet bloqué : message clair + alternative. Il consomme uniquement le dict JSON de `calculer_indice`.

## Définition de « terminé »
1. `pytest -v` passe entièrement ; ne jamais modifier ni assouplir `test_indice_confiance.py`.
2. En fin de tâche 1, afficher sur les vrais fichiers : les quantiles (min, 10 %, 25 %, 50 %, 75 %, 90 %, max) de la régularité,
   du taux de suppression et de la stabilité sur les 217 trains, et combien dépassent le seuil de suppressions chroniques de 10 %.
3. Résumer en langage simple ce qui a été fait et les choix qui restent à valider.

---

# CHECKLIST CONTRÔLEUR (pour toi, pas pour Antigravity)

1. **Config** : piliers fiabilité 0.30 / faisabilité 0.20 / capacité 0.40 / pairs 0.10 (somme 1), sous-poids qui somment à 1,
   seuils 85 et 65, capacité 50, marge 15-20 min, marche 20 min.
2. **Tests** : `pytest -v` toi-même, tout vert, et `test_indice_confiance.py` non modifié.
3. **Piège « Taux SUPP vide »** : le taux de suppression d'un train est recalculé sur les compteurs, pas moyenné.
4. **Veto** : 51 voyageurs → rouge et bloqué ; exactement 50 → pas bloqué. Un veto ne donne jamais orange/vert.
5. **Valeurs manquantes** : jamais comptées comme 0 ; sous-critère ignoré et dit dans les alertes.
6. **Anonymat** : `options_actives` reste un nombre ; aucun nom d'école dans le JSON.
7. **Pas de magie** : aucune constante cachée, aucun score inventé sans commentaire.
8. **Explicabilité** : chaque message dit POURQUOI (veto ou alerte), pas seulement la couleur.
9. **Calibration** : regarde les quantiles demandés en fin de tâche. Si 40 % des trains dépassent le seuil de 10 %, le seuil est trop strict : à rediscuter.
10. **Hypothèses restant à valider** : poids internes des sous-critères, seuil de suppressions (10 %), décote bus (15 pts),
    durée supposée du bus (15 min), note neutre sans avis (70). Les poids des piliers et la marge (15-20 min) sont validés par l'enseignant.
