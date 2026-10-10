# Frontend — carte et itinéraires

React + Vite + Leaflet. Carte des gares desservies par les **trains liO** (TER Occitanie), liste des
gares par département, et calcul d'itinéraire via le backend (`/route`) : trajets directs,
correspondances avec attente estimée, nombre d'arrêts et de trains par jour. Direction artistique
inspirée de la charte liO (marine `#0f2149`, rouge `#c90c0f`, jaune `#ffd500`, capsules et points).
Le front affiche ce que sert l'API : avec `IA_DATASET=full` côté backend, les arrêts de car liO
apparaissent aussi (plus discrets, et dans l'onglet Lieux seulement en cherchant).
Interface en anglais et en français, langue détectée depuis le navigateur.

## Lancer

Le backend doit tourner sur le port 8000 (voir `../backend/README.md`) :

```bash
cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8000
```

Puis :

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

En dev, Vite relaie `/api/*` vers `http://127.0.0.1:8000`. Pour un build pointant
vers une API déployée : `VITE_API_URL=https://… npm run build`.

## Structure

```
src/
├── api.ts                 # client du backend
├── i18n.tsx               # textes EN / FR + détection de langue
├── App.tsx                # état : départ, arrivée, itinéraire, lieu sélectionné
└── components/
    ├── Header.tsx
    ├── RoutePanel.tsx     # formulaire + frise des tronçons
    ├── PlacesPanel.tsx    # gares groupées par département
    ├── MapView.tsx        # carte Leaflet (réseau, gares, trajet)
    ├── Discovery.tsx      # fiche d'un lieu à découvrir (photo, bouton « Voir en 3D »)
    ├── ModelViewer.tsx    # visionneuse 3D three.js, chargée à la demande
    └── Trame.tsx          # motif de capsules et de points
```

## Modèles 3D des monuments

Quand un lieu a un modèle, sa fiche affiche un bouton **Voir en 3D**. Les modèles sont dans
`public/models/<id>.glb` (l'`id` est celui de `src/data/discoveries.ts`), leurs crédits dans
`src/data/model-credits.json` : c'est ce fichier qui décide si le bouton apparaît.

Ils viennent de Sketchfab (scans photogrammétriques, 10 à 160 Mo bruts) et sont allégés pour le web :
décimation à ~120 000 faces dans Blender quand le scan n'a aucun sommet partagé, puis
`gltf-transform optimize --compress meshopt --texture-compress webp --texture-size 1024`.
Cible : moins de 3 Mo par modèle. Carcassonne vient d'un scan de tout le quartier, recadré
dans Blender sur la cité (faces **et** texture découpées selon les UV, pour garder la résolution sur les remparts).

⚠️ Licences : Champollion (CC BY-NC) interdit l'usage commercial ; Carcassonne, Arènes de Nîmes,
Maison Carrée et Viaduc de Millau sont en CC BY (créditer l'auteur, déjà affiché
sous le modèle).
