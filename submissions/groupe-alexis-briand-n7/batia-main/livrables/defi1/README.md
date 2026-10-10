# Livrable du défi 1

`score_risque_2026.csv` est le fichier demandé par la notice : une ligne par équipement du périmètre, deux colonnes `equipement_id, score_risque`, un score plus haut voulant dire une panne plus probable. Le score est la probabilité d'un dépannage « Arrêt total » entre janvier et septembre 2026, calculée au 31 décembre 2025 avec l'historique antérieur seulement.

`detail_2026.csv` donne pour chaque équipement son rang, ses points, la liste des raisons telles qu’un technicien les lira, et dans `autres_situations` le détail des raisons repliées sous « Autres situations ». Le seuil des 10 % les plus à risque est à 45 points, les égalités étant départagées par identifiant croissant.

Le barème est décrit dans `poc/preavis/moteur/BAREME.md`. Pour régénérer les deux fichiers :

```bash
python3 livrables/defi1/produire.py
```

## Contrat pour l'application

`detail_2026.json` est la même information que `detail_2026.csv`, déjà structurée pour une interface : un en-tête (`date_reference`, `nb_equipements`, `budget` avec le nombre de visites, le seuil en points et le nombre d'équipements à ce seuil ou plus) puis une liste `equipements`. Chaque entrée porte `rang`, `points`, `bande` (`nom`, `neuf_mois`, `trois_mois`), `raisons` (liste de `texte` et `points`, qui se somment aux points), `remplacement_juge_necessaire_le`, `dans_budget`, `age_ans`, `pose` et `probabilite_pct`.

Ce que l'écran d'un équipement montre, décidé le 10 octobre :

1. Le nom de la bande et ses deux phrases observées, pas la probabilité. « Alerte : 9 pannes sur 16 l'an dernier. »
2. Jusqu'à quatre raisons avec leurs points, la plus lourde en premier, puis « Autres situations ». Le total fait les points.
3. Le rang sur 1 285 et si l'équipement est dans le budget de visites. Le budget est les 128 premiers rangs ; 139 équipements atteignent 45 points, les égalités sont départagées par identifiant.
4. Les dates derrière les raisons tirées des textes sont déjà dans la phrase.
5. La ligne « Remplacement déjà jugé nécessaire » est une information opérationnelle. Le moteur la garde toujours visible, elle n'est jamais repliée dans « Autres situations ». Le champ `remplacement_juge_necessaire_le` la donne à part.
6. Les signaux de territoire, dureté de l'eau, arrêt de la 2G, réseau, peuvent apparaître en badges texte. Ils ne pèsent aucun point.

À ne pas faire côté interface : recalculer ou repondérer des points, le moteur est la seule source et les poids ne changent que dans `POINTS` de `bareme.py` ; afficher des décimales de probabilité ; dire « pannes évitées », dire « repérées » ; dire « bank-grade », dire « méthode classique des scorecards de crédit ».
