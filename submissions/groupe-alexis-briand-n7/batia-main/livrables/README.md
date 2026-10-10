# Livrables BâtIA, défi Action Logement / In'li Sud-Ouest

Deux fichiers répondent à la notice, un par défi. Tout le reste est la preuve : les scripts qui les produisent, les mesures dans le passé et les notes de méthode. Les données du kit ne sortent pas du dépôt.

## Défi 1 : prédire les pannes bloquantes

`defi1/score_risque_2026.csv`, 1 285 lignes, une par équipement du périmètre, deux colonnes `equipement_id, score_risque`. Le score est la probabilité d'un dépannage « Arrêt total » entre janvier et septembre 2026, calculée au 31 décembre 2025 avec l'historique antérieur seulement. Les 128 premiers de ce classement, 10 % du parc, sont la liste de visite du défi.

`defi1/detail_2026.csv` donne pour chaque équipement son rang, ses points, sa bande et jusqu'à quatre raisons écrites, telles que le technicien les lira.

Mesure demandée par la notice, référence au 31 décembre 2024, test de janvier à septembre 2025, 76 pannes sur 1 285 :

| | Barème BâtIA | Âge seul |
|---|---|---|
| AUC | 0,876 | 0,776 |
| Pannes dans les 128 visités | 43 | 16 |
| Vraies pannes par visite | une sur trois | une sur huit |

Le gain sur l'âge seul est de 14 à 36 pannes selon le rééchantillonnage du test, positif dans tous les tirages. Sur les quatre années 2022 à 2025, chacune prédite avec les années précédentes, le barème repère 152 des 258 pannes avec 512 visites. La méthode, les points, les bandes et les vérifications sont dans `poc/preavis/moteur/BAREME.md` ; le moteur est `poc/preavis/moteur/bareme.py`, sans dépendance.

## Défi 2 : prioriser les rénovations

`defi2/classement_operations.csv`, 29 lignes, une par opération du plan d'investissement : les cinq critères sur 10, le score et le rang dans cinq réglages de poids dont celui du commanditaire, les pannes attendues par le score du défi 1 sur les équipements cibles, et l'année de début recommandée.

`defi2/plan_recommande.csv` est le calendrier 2026 à 2035 sous le plafond de 1,5 M€ par an : il maximise le score moins les loyers perdus par les logements interdits à la location. Au 1er janvier 2028 il laisse 36 logements F au lieu de 60 avec la règle « conformité d'abord » et économise 2 032 MWh par an au lieu de 1 745, pour 12 logements-années d'infraction de plus. Les autres calendriers comparés sont dans `defi2/plans_comparaison.csv`, la méthode et les hypothèses dans `defi2/README.md`.

## Refaire les deux fichiers

```bash
python3 livrables/defi1/produire.py
uv run --with pandas --with 'pulp<3' python livrables/defi2/prioriser.py donnees/kit-batia/donnees livrables/defi2 livrables/defi1/score_risque_2026.csv
```

Le premier tourne en une minute avec Python seul. Le second prend cinq minutes, le temps des programmes en nombres entiers.

## Ce que les fichiers ne disent pas

Le score repère des pannes à l'avance ; il ne prouve pas qu'une visite les évite. Six résidences sur huit sont générées, une seule année sert de test, les familles rares ne sont pas mesurables. Le loyer de 7 000 € et la valeur de 1 000 € par point de score du défi 2 sont des hypothèses à régler avec le commanditaire. Les signaux de territoire, dureté de l'eau, arrêt de la 2G, qualité du réseau électrique, sont documentés dans `docs/recherche-donnees-publiques.md` et ne pèsent pas encore dans le score, faute de données qui les relient à des pannes.
