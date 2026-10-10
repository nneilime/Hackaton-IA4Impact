# Ajouter une nouvelle source officielle

Une source est un module Python de `veille_reglementaire/sources/` : **aucune autre ligne du code n'est à modifier**, elle est découverte automatiquement.

## 1. Créer le squelette
```bash
./veille new-source agrofit --name "AGROFIT (MAPA)" --country-code BR --country Brésil --region "Amérique du Sud" --format "API REST" --lang PT
```
(ou, dans l'interface d'administration : onglet « Sources et périmètre » → « Ajouter une nouvelle source officielle »).
Cela crée `sources/agrofit.py` à partir de `_template.py`.

## 2. Remplir trois choses
| À faire | Où | Règle |
|---|---|---|
| L'adresse du jeu de données | `DATASET_URL` | de préférence un fichier **ouvert, pris en bloc** ; `collect()` utilise `polite_http.download` (requêtes conditionnelles, pauses, journal) |
| La lecture des lignes | `passages()` | un `Passage` par usage ; le texte recopie les valeurs de la source **telles quelles** ; `passage_id` stable |
| Les colonnes structurées (si elles existent) | `gold` | dose, nombre d'applications… : elles servent d'étalon à `./veille eval`. Sinon laisser vide |

## 3. Dire quoi chercher
Dans `config/scope.json`, ajouter aux produits concernés la clé de la source : `"agrofit": ["NOM DU PRODUIT TEL QU'ÉCRIT DANS LA SOURCE"]`
(ou onglet « Sources et périmètre » de l'interface).

## 4. Essayer
```bash
./veille collect --only agrofit
./veille index --only agrofit
./veille extract --source agrofit --per-product 3      # essai rapide
./veille review                                        # ce que l'IA ne tranche pas
./veille eval                                          # si la source a un gold
```

## Pièges fréquents
- **Texte tronqué ou reformulé** : le contrôle de preuve cherche mot à mot ; garder les valeurs de la source telles quelles.
- **Source qui exige une inscription ou une clé** : ne pas redistribuer les données ; fournir le script de collecte (c'est la règle du défi) et documenter l'accès.
- **Pas de vérité structurée** (étiquettes PDF) : pas de mesure automatique d'exactitude ; prévoir un contrôle par échantillon par un expert (`./veille review`).
- **Licence des données** : l'indiquer dans `NOTICE`.
- Ajouter l'identifiant dans les produits du périmètre **avant** de collecter, sinon `passages()` ne renvoie rien.

## Contrat d'une source
`INFO` (id, name, country_code, country, region, format, lang) · `collect(scope=None)` · `passages(scope)`. Détail dans `sources/__init__.py` ; test : `tests/test_sources.py`.
