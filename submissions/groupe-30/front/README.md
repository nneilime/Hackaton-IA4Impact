# BâtIA · Prévention des pannes

Application React / TypeScript / Vite reliée à l’API FastAPI locale et à Supabase. Les données du patrimoine, les scores CatBoost et les dossiers sont partagés entre les membres invités.

## Démarrage

Depuis la racine, lancer l’API avec l’environnement Python 3.11 et le `.env` serveur configuré :

```powershell
.\.venv\Scripts\python.exe -m uvicorn scripts.api:app --host 127.0.0.1 --port 8000
```

Dans un second terminal :

```powershell
cd front
npm.cmd ci
npm.cmd run dev
```

Ouvrir http://127.0.0.1:5173 et se connecter avec le compte d’équipe Supabase. Vite transmet `/api` au serveur sur le port 8000. Les secrets restent sur le serveur.

## Parcours

- **À examiner** : classement global, filtres et top 10 %. Les rangs sont établis avant les filtres.
- **Équipements** : tout le patrimoine, y compris les équipements non scorés.
- **Fiche** : identité, cycle de l’appareil, interventions, demandes et sources PDF avec leur page.
- **Actions** : dossiers partagés, visites, clôtures et décisions. Un seul dossier ouvert par équipement ; les versions détectent les modifications concurrentes.
- **Données** : date de prédiction, horizons 90/180/365/730 jours, progression et relance des calculs. Les administrateurs peuvent prévisualiser puis confirmer un lot de CSV.
- **Récupération locale** : aperçu des anciennes données du navigateur, ajout sans écraser les dossiers existants et copie locale conservée après réussite.

Le résultat initial porte sur le 1er janvier 2026, sur l’historique arrêté fin 2025. Les sorties sont des scores de risque non calibrés. Les imports mettent à jour l’inférence sans réentraîner automatiquement les modèles.

Le [guide de la base et des imports](../docs/BASE_ET_IMPORTS.md) décrit les tables, comptes, migrations, artefacts et commandes de calcul.

## Tests et build

```powershell
npm.cmd test
npm.cmd run build
npm.cmd run test:e2e
```

Le build inclut le contrôle TypeScript. Playwright utilise Microsoft Edge et simule l’API/Auth avec les fixtures de test, sans modifier la base. Les captures et traces sont dans `qa/`, ignoré par Git.

Les JSON de consultation sont uniquement dans `tests/fixtures`, jamais dans les fichiers publics servis. `npm.cmd run prepare-data` régénère ces fixtures et copie les sources PDF ; l’application lit toujours l’API. `npm.cmd run format` formate les sources.

L’API reste locale et les modèles doivent être présents sur ce poste. L’hébergement en ligne reste à mettre en place.
