# Préavis — prototype temporaire

**Prototype non définitif.** Il sert de point de comparaison pendant le hackathon et
n'est pas la base retenue de l'application.

## D'où il vient

C'est le prototype A, construit le 10/10/2026 entre 00h09 et 00h29 par une session
Claude Opus 5.5 (effort max), seule, à partir de la consigne `PROMPT.md` (consigne
« liberté créative ») et des données fictives du kit. Parmi les quatre premiers
prototypes, c'est celui qu'Alexis a jugé le moins mauvais, à l'aveugle.

- À garder : la carte de la métropole (résidences en carrés proportionnés, liste des
  résidences à droite).
- À ne pas reprendre : la vue « façade » (une case par logement, étage par étage),
  jugée peu intuitive. L'ensemble reste trop chargé.

## Lancer

```bash
./lancer.sh
```

Puis ouvrir http://localhost:8642 (autre port : `PORT=9000 ./lancer.sh`). Python 3
suffit, sans installation. Au lancement, les risques sont recalculés depuis
`donnees/`, un lien vers le dossier `donnees/` à la racine du dépôt.

Attention : le serveur écoute sur toutes les adresses de la machine (`0.0.0.0`). Sur
le réseau Wi-Fi du hackathon, d'autres personnes pourraient l'ouvrir. Les données
sont fictives, mais elles ne doivent pas sortir du cadre du hackathon.

## Ce qu'il contient

- `moteur/` : calcul du risque, explicable (score et raisons pour chaque
  équipement), et mesure sur le passé (`backtest.py`, résultats dans
  `performance.json`, méthode dans `METHODE.md`).
- `preparer.py` : lit les CSV du kit et écrit `app/donnees/*.json` (fichiers
  produits, non suivis par git).
- `app/` : l'interface (HTML, CSS, JavaScript, d3, polices Barlow, contours
  géographiques publics).
- `RESULTAT.md` : le compte rendu écrit par la session elle-même.

Depuis le 10 octobre, le calcul du risque passe par `moteur/bareme.py`, un barème en
points ajusté sur l'historique du kit, décrit dans `moteur/BAREME.md`. Mesure au
31/12/2024, test sur janvier à septembre 2025 : parmi les 128 équipements classés en
tête, 43 ont réellement eu une panne totale, contre 16 pour l'âge seul et 29 pour
l'ancien moteur `risque.py`, gardé pour comparaison (AUC 0,876 contre 0,776 et 0,835).
