# Trains d'Occitanie : carte des dessertes

Carte interactive des trains TER d'Occitanie : tracés sur les voies, filtre par période, par numéro de train et par axe, heures de passage à chaque arrêt quand la période fait moins d'un jour.

## 1. Ajouter les fichiers de données

Les données ne sont pas versionnées dans git. Créez un dossier `data/` à la racine du projet et placez-y :

| Fichier | Source |
|---|---|
| `data/Data_Hackathon.csv` | fourni pour le hackathon (axes, origine/destination, indicateurs mensuels) |
| `data/Détail desserte (1).xlsx` | fourni pour le hackathon (arrêts et horaires de chaque train) |
| `data/top-des-sites-touristiques-2021-enrichi.json` | sites touristiques (nom, commune, visites 2021, mots-clés, coordonnées) |
| `data/lio/` | GTFS du réseau de cars régionaux liO (dossier dézippé : `routes.txt`, `shapes.txt`, `stops.txt`…) |
| `data/gares.json` | open data SNCF, à télécharger (voir ci-dessous) |
| `data/rfn.geojson` | open data SNCF, à télécharger (voir ci-dessous) |

Téléchargez les deux fichiers open data SNCF (coordonnées des gares et tracé du réseau ferré) :

```bash
curl -o data/gares.json "https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/gares-de-voyageurs/exports/json"
```

```bash
curl -o data/rfn.geojson "https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/formes-des-lignes-du-rfn/exports/geojson"
```

## 2. Générer les données de la carte

Il faut Python 3 et ces bibliothèques :

```bash
pip install openpyxl networkx scipy
```

Convertissez ensuite l'Excel en CSV. Le fichier est volumineux, comptez quelques minutes :

```bash
python scripts/xlsx_to_csv.py "data/Détail desserte (1).xlsx" data/desserte.csv
```

Puis construisez `carte/data.js` :

```bash
python scripts/build_data.py
```

Et les sites touristiques (`carte/sites.js`) :

```bash
python scripts/build_sites.py
```

Et le réseau de cars liO (`carte/lio.js`) :

```bash
python scripts/build_lio.py
```

À relancer à chaque changement des fichiers de `data/`.

## 3. Lancer le site

La page doit être servie par un petit serveur web. Ouvrir `index.html` en double-cliquant ne fonctionne pas : le navigateur bloque alors le chargement de `data.js`.

**Sous Windows** : double-cliquez sur `lancer_carte.bat`. Le navigateur s'ouvre sur http://localhost:8765.

**Ou en ligne de commande**, depuis la racine du projet :

```bash
python -m http.server 8765 --directory carte
```

Ouvrez ensuite http://localhost:8765 dans votre navigateur. Pour arrêter le serveur, faites `Ctrl+C`.

## Utilisation

- **Période** : choisissez un début et une fin, ou utilisez les raccourcis Matinée, Journée, Semaine, Tout.
- **Numéro(s) de train** : un ou plusieurs numéros séparés par des virgules. Un début de numéro suffit (`876` affiche tous les trains 876…).
- **Axe** : limite l'affichage à une ligne.
- **Sélection** : cliquez sur un tracé ou sur un train dans la liste. La carte zoome dessus et affiche sa fiche et ses horaires.
- **Réseau liO** (traits pointillés aux couleurs des lignes) : survolez une ligne pour son numéro et son nom. Les arrêts apparaissent à partir du zoom 12 ; cliquez-en un pour voir les lignes qui le desservent. La case « Réseau de cars liO » le masque.
- **Sites touristiques** (★, taille selon la fréquentation) : cliquez pour voir les visites, les mots-clés et la gare la plus proche. La case « Sites touristiques » les masque.
- **Gare** : cliquez sur un arrêt pour voir tous ses passages sur la période.
- **Période de moins d'un jour** : les numéros des trains et les heures aux arrêts s'affichent. Le curseur en bas, avec son bouton ▶, fait rouler les trains.

## Structure

```
data/                 fichiers de données (non versionnés)
scripts/
  xlsx_to_csv.py      Excel des dessertes -> CSV
  build_data.py       construit carte/data.js
  build_sites.py      construit carte/sites.js
  build_lio.py        construit carte/lio.js (GTFS liO)
  geocode_missing.py  aide pour localiser les arrêts absents du référentiel SNCF
carte/
  index.html          la carte (Leaflet + OpenStreetMap)
  data.js             données générées (non versionnées)
  sites.js            sites touristiques générés (non versionnés)
  lio.js              réseau liO généré (non versionné)
lancer_carte.bat      lance le serveur local sous Windows
```
