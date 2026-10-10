# Préavis : résultat

> « Une panne s'annonce des mois avant. Préavis l'écoute. »
> L'application interne de l'équipe technique d'In'li Sud-Ouest pour voir venir les pannes et décider quoi réparer d'abord.

## Lancer l'application

```bash
./lancer.sh
```

Ouvrir ensuite http://localhost:8642 (port modifiable : `PORT=9000 ./lancer.sh`).

La commande recalcule tous les risques à partir des CSV du kit (Python 3, bibliothèque standard uniquement, environ 2 s), puis sert l'application. Il n'y a ni compte, ni clé, ni appel réseau vers un service d'IA. d3, les polices et les contours géographiques publics (france-geojson) sont copiés dans `app/` : l'application marche donc hors ligne.

Pour la mise à jour trimestrielle, il suffit de lancer `./lancer.sh chemin/vers/dossier-du-trimestre`, où le dossier contient les 13 CSV au même format.

## Ce qui fonctionne

- **Le parc (« Où ? »)** : une carte qui descend de la France vers l'Occitanie, puis la métropole toulousaine, puis une résidence, avec un fil d'Ariane.
  - Les cinq départements d'In'li Sud-Ouest sont dessinés. La Haute-Garonne est « à l'écoute » avec ses 1 100 logements. Les quatre autres (33, 34, 40, 64) apparaissent en pointillé, avec la mention « au prochain import ». Une jauge montre 1 100 logements sur environ 6 300 : le déséquilibre du kit devient un rendez-vous.
  - Les 8 résidences sont placées à des **positions fictives**, sur un fond sans rues ni bâtiments. Chacune est un carré proportionné à son nombre de logements, dont la base se remplit de la part de logements à visiter (rouge) et à surveiller (ambre).
- **Les façades** : chaque résidence est dessinée en élévation, bâtiment par bâtiment. Chaque logement est une fenêtre, placée à son étage et colorée selon son risque. Un point signale les demandes répétées du locataire. Les équipements communs sont à leur place : ascenseur dans sa gaine, VMC sur le toit, chaufferie au sous-sol.
- **Les locataires qui redemandent** : pour chaque résidence, le volet liste les logements où le même sujet a été demandé au moins deux fois en 24 mois, avec le niveau de risque du logement. Un clic ouvre la fiche.
- **La fiche logement** comporte :
  - un verdict en une phrase ;
  - la « vie du logement » sur une frise de 2018 à septembre 2026 : demandes du locataire, entretiens, absences, dépannages selon leur gravité, notes d'usure des techniciens, remplacements. Les neuf mois du préavis sont dilatés et portent la barre de risque ;
  - pour chaque équipement, un score sur 100 et **ses raisons chiffrées**, avec leurs points ;
  - l'historique complet des demandes, où chaque demande répétée est marquée (« 2e fois sur 3 », « rouverte ») ;
  - les équipements communs du bâtiment.
- **Lundi matin (« Quoi d'abord ? »)** : la file des 128 équipements à visiter (les 10 % les plus à risque), avec pour chacun ses trois raisons principales.
  - Trois décisions humaines possibles : « Programmer une visite », « Garder à l'œil », « Écarter ». Elles sont datées et conservées dans le navigateur.
  - Filtres par résidence et par type d'équipement.
  - Deux exports : la file avec les décisions (CSV pour tableur) et tous les scores au format du défi (`equipement_id,score_risque`).
  - Le bouton « Imprimer la tournée » produit une version papier de la file, sans les menus.
  - Un encadré de preuve montre la mesure réelle de 2025 (voir plus bas).
- **Énergie (« Que rénover ? »)** :
  - le calendrier de la loi Climat et résilience (G en 2025, F en 2028, E en 2034) avec le nombre de logements concernés ;
  - pour chaque résidence, une case par logement à la couleur de son DPE ;
  - les opérations du plan d'investissement (table 08), avec leur coût, leur gain et leur rang dans l'ordre d'arrivée actuel, croisées avec les pannes de 2025 et les équipements à visiter.
- L'application est utilisable sur téléphone : les écrans s'empilent, la fiche passe en plein écran et la frise se resserre.

## Ce qui manque

- L'import se fait en relançant la commande avec un dossier, pas encore par glisser-déposer dans l'interface.
- Les décisions sont gardées dans le navigateur du poste, et partagées par l'export CSV. Il n'y a pas encore de base commune à l'équipe.
- Les trois rapports PDF du prestataire ne sont pas exploités.
- Le défi 2 (classement des 29 opérations sous l'enveloppe de 1,5 M€) est seulement préparé : les opérations sont mises en regard du DPE et des pannes, mais aucun classement multicritère n'est calculé.
- Sur téléphone, les façades des grandes résidences restent petites ; on les fait défiler.

## La méthode de calcul du risque (`moteur/risque.py`, module isolé et remplaçable)

1. Le module a une entrée simple (les lignes des CSV et une date de référence) et une sortie simple (pour chaque équipement : `score` et `raisons`). On peut le remplacer sans toucher à l'interface.
2. Le score est une somme de points plafonnée à 100. Chaque point vient d'une raison écrite en clair. Il n'y a ni modèle de langage ni apprentissage opaque.
3. **Usure** : l'âge de l'appareil en place, divisé par sa durée de vie de référence, est porté au cube (forme de Weibull). Cela donne 40 points à 100 % de la durée de vie, et jusqu'à 55 au-delà.
4. **Dépannages des 12 derniers mois** : 9 points par arrêt total, 6 par fonctionnement dégradé, 2,5 par gêne mineure (30 points au plus).
5. **Notes des techniciens sur 18 mois** : 9 points par note d'usure (« usure avancée », « réparation provisoire », « corrosion »…), 14 par note de fin de vie (« panne irréparable », « hors service »…), 32 points au plus.
6. **Anomalies constatées en visite**, ou « remplacement nécessaire », sur 18 mois : 5 points chacune (15 au plus).
7. **Entretien manqué** : la part des visites où le logement était absent, sur 3 ans, vaut jusqu'à 10 points.
8. **Demandes du locataire** liées à l'équipement sur 12 mois : 6 points chacune (14 au plus), plus 6 si la demande revient ou a été rouverte. C'est le signal de répétition demandé par In'li.
9. **Contre les fuites d'information** : seules les données datées au plus tard à la date de référence sont lues. L'âge est recalculé à cette date, et `nb_remplacements_2018_2025` n'est jamais utilisé.
10. Les niveaux affichés sont « à visiter » pour les 10 % les plus à risque (score de 39,9 ou plus) et « à surveiller » de 10 à 25 % (score de 19,5 ou plus). L'outil recommande, l'utilisateur décide.

## Mesure de performance (réellement calculée, `python3 -m moteur.backtest`)

La mesure suit la méthode de la notice : on se place au 31/12/2024, on calcule les variables avec l'historique antérieur seulement, puis on teste sur janvier à septembre 2025. La cible est au moins un dépannage de gravité « Arrêt total » sur l'équipement pendant la période. Elle porte sur les 1 285 équipements du périmètre, dont 76 sont tombés en panne (taux de base 5,9 %).

| Mesure 2025 | Préavis | Âge seul (âge / durée de vie) |
|---|---|---|
| AUC | **0,835** | 0,776 |
| Pannes trouvées en visitant les 10 % désignés (128) | **29 sur 76** | 16 sur 76 |
| Précision du top 10 % | **22,7 %** | 12,5 % |

Les poids ont été réglés sur une fenêtre antérieure : référence au 31/12/2023, test de janvier à septembre 2024. Sur cette fenêtre, l'AUC était de 0,819 contre 0,712, avec 29 pannes trouvées contre 15. Les poids ont ensuite été appliqués sans retouche à 2025. Les chiffres sont dans `moteur/performance.json`.

## Fichiers

- `lancer.sh` : la commande unique.
- `preparer.py` : lecture des CSV, appel du moteur, écriture de `app/donnees/*.json` (fichiers générés, non versionnés).
- `moteur/risque.py` (le score), `moteur/backtest.py` (la mesure), `moteur/METHODE.md`.
- `app/` : l'interface (HTML, CSS et JavaScript sans framework, avec d3 en local).
