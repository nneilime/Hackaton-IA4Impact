# Barème en points du défi 1

`bareme.py` remplace les poids réglés à la main de `risque.py` par des points ajustés sur l'historique du kit. Il lit les mêmes CSV, prend la même date de référence et rend la même structure : un score et des raisons par équipement. `backtest.py` et `preparer.py` l'utilisent depuis le 10 octobre ; `risque.py` reste dans le dossier pour comparaison.

## Ce que le score veut dire

Le score est la probabilité, en pour cent, d'un dépannage « Arrêt total » dans les neuf mois qui suivent la date de référence. Il se calcule en deux temps. On additionne les points des situations présentes dans le dossier de l'appareil, puis on convertit le total : probabilité = 1 / (1 + exp(−(−4,672 + total / 20))). Zéro point donne 0,9 %, 45 points donnent 8 %, 87 points donnent 42 %. Quatorze points doublent la cote.

## Les points

| Situation à la date de référence | Points |
|---|---|
| Âge entre le quart et la moitié de la durée de vie de référence | 11 |
| Âge entre la moitié et les trois quarts | 28 |
| Âge entre les trois quarts et la durée de vie | 35 |
| Âge au-delà de la durée de vie | 40 |
| Un commentaire d'usure du technicien dans les 12 mois | 15 |
| Deux commentaires ou plus | 39 |
| Un de ces commentaires écrit pendant un dépannage, en plus | 28 |
| Une demande chauffage ou eau chaude du locataire dans les 12 mois | 20 |
| Deux demandes ou plus | 31 |
| La demande nomme l'appareil, dans les 6 mois, en plus | 28 |
| Dépannage dans les 6 derniers mois | 11 |
| Panne bloquante réparée sans remplacement dans les 24 mois | 9 |
| Visites d'entretien manquées, de 10 à 30 % depuis la pose | 2 |
| Visites manquées, plus de 30 % | moins 1 |
| Remplacement déjà jugé nécessaire par un technicien | moins 20 |

Les six commentaires d'usure sont les phrases du kit : nombreux redémarrages, traces de corrosion, usure avancée, pièce de rechange difficile, appareil vieillissant, réparation provisoire. Les demandes chauffage sont celles dont le motif est une panne d'équipement individuel, une température basse, une absence de chauffage collectif, une panne d'ascenseur ou une VMC bruyante. « La demande nomme l'appareil » teste la présence d'un mot de la famille dans le texte, par exemple « chaudi » pour une chaudière, « cumulus », « ballon » ou « chauffe-eau » pour un ballon, « radiateur » ou « convecteur » pour des convecteurs ; la liste est dans `MOTS_FAMILLE`.

Seule la vie de l'appareil en place compte : l'historique antérieur au dernier remplacement est ignoré. Seules les lignes antérieures à la date de référence sont lues.

## D'où viennent les points

Une régression logistique sur les 7 710 situations observées au 1er janvier de 2019 à 2024, avec 343 pannes bloquantes dans les neuf mois suivants. Chaque coefficient est multiplié par 20 et arrondi. Les bornes d'âge, les plafonds à deux et les fenêtres ont été fixés avant l'ajustement. Le détail des vérifications, la calibration par bande et la stabilité des points d'une année à l'autre sont dans la note d'explication tenue par Sami.

## Mesure dans le passé

Avec la méthode de la notice, référence au 31/12/2024 et test de janvier à septembre 2025, sur 1 285 équipements et 76 pannes :

| | Barème | Âge seul | Ancien moteur `risque.py` |
|---|---|---|---|
| AUC | 0,876 | 0,776 | 0,835 |
| Pannes trouvées parmi les 128 visités | 43 | 16 | 29 |

Le même test refait au 31/12/2023 sur 2024 donne 40 sur 128, mais 2024 fait partie des années d'ajustement. Sur les quatre années 2022 à 2025, chacune prédite avec les points ajustés sur les années précédentes, le barème trouve 152 des 258 pannes avec 512 visites, soit 30 % de vraies pannes dans la liste.

Les 33 pannes de 2025 manquées se répartissent ainsi : 12 n'avaient aucun signe en dehors de l'âge, 21 avaient un signe mais moins de 46 points.

## Bandes plutôt que décimales

Pour l'écran du technicien, le score se lit par bande, avec ce qui est réellement arrivé l'an dernier aux appareils de la même bande, points au 1er janvier 2025 et pannes de janvier à septembre :

| Points | Bande | Pannes bloquantes à 9 mois | Dans les 3 mois | Appareils au 31/12/2025 |
|---|---|---|---|---|
| 0 | Rien à signaler | 0 sur 241 | 0 | 254 |
| 1 à 20 | Calme | 7 sur 434, 2 % | 3 | 357 |
| 21 à 40 | À surveiller | 18 sur 439, 4 % | 4 | 499 |
| 41 à 60 | Vigilance | 14 sur 109, 13 % | 3 | 113 |
| 61 à 80 | Alerte | 9 sur 16 | 2 | 17 |
| plus de 80 | Urgence | 28 sur 46, 61 % | 18, soit 40 % | 45 |

La fonction `bande(points)` rend le nom et ces deux phrases ; `scorer` les joint à chaque équipement. Les 128 visites du défi, 10 % du parc, couvrent les bandes Urgence et Alerte et les 66 appareils les plus hauts de Vigilance, à partir de 45 points.

## Rafraîchir chaque trimestre

Le même barème recalculé au 1er janvier, au 1er avril et au 1er juillet 2025, avec le même budget de 128 visites réparties en 43, 43 et 42, repère 44 des 76 pannes au lieu de 43 quand on visite tout en janvier. Un barème ajusté sur des situations trimestrielles au lieu d'annuelles en repère 45, un barème à horizon de trois mois 46. L'écart est dans le bruit, mais le trimestre a deux autres avantages : la visite tombe plus près de la panne, et les signes apparus depuis janvier, commentaires et demandes, comptent. C'est le rythme à proposer.

## Mesures au format bancaire

Sur le test 2025, en plus de l'AUC de 0,876 : Gini 0,75, soit 2 × AUC − 1, et KS 0,63, l'écart maximal entre la part des pannes et la part des non-pannes déjà classées en descendant le score. Les raisons affichées sont limitées à quatre, les plus lourdes d'abord, comme les codes motifs d'un score de crédit ; le reste est regroupé sur une ligne « Autres situations » pour que le total reste exact.

Courbe de seuil, pour choisir un budget de visites autre que 10 % :

| Part du parc visitée | Visites | Pannes trouvées sur 76 | Vraies pannes par visite | Part des pannes couvertes |
|---|---|---|---|---|
| 5 % | 64 | 37 | 58 % | 49 % |
| 10 % | 128 | 43 | 34 % | 57 % |
| 15 % | 193 | 52 | 27 % | 68 % |
| 20 % | 257 | 59 | 23 % | 78 % |
| 25 % | 321 | 63 | 20 % | 83 % |
| 30 % | 386 | 65 | 17 % | 86 % |

Les 64 premières visites trouvent 37 pannes, les 64 suivantes 6. Si le budget est serré, 5 % du parc capte la moitié des pannes annoncées.

Stabilité de la population, indice PSI sur les six bandes de points : 0,004 entre le 1er janvier 2024 et le 1er janvier 2025, 0,018 entre le 1er janvier 2025 et le 31 décembre 2025. Les seuils d'usage bancaire sont 0,10 pour surveiller et 0,25 pour réexaminer le modèle ; la population notée ne bouge pas.

## Refaire

```bash
cd poc/preavis && python3 -m moteur.backtest
python3 livrables/defi1/produire.py
```
