# Présentation — « L'Occitanie en train »

Diapo-pub du site, aux couleurs de la charte liO. **React + TypeScript (strict) + Vite.** Tout tourne hors ligne
(polices et three.js sont dans le projet).

```bash
cd presentation
npm install           # une fois
npm run dev           # http://localhost:4321 — la page se recharge à chaque modification, sur la même slide
npm run typecheck     # vérification TypeScript
npm run build         # version autonome dans dist/ (s'ouvre depuis n'importe quel dossier)
```

Option d'URL : `?lite` retire les scènes WebGL (intros 3D, « Suivez le train », histoire low poly) et remplace les
transitions TER 3D par le TER 2D, au cas où une machine rame pendant la présentation.

**→ / Espace / clic** : suivante · **←** : précédente · **F** ou bouton : plein écran · `#12` dans l'URL ouvre la 12ᵉ slide.

## Organisation

| Dossier | Ce qu'il contient |
|---|---|
| `src/slides/` | une slide = un objet `SlideDef` : son contenu (composant React) et son comportement à l'entrée. **L'ordre du diapo est dans `src/slides/index.ts`** |
| `src/textes.ts` | tous les textes (français). `<em>` = souligné rouge, `<b>` = gras |
| `src/components/` | `Deck` (scène 1920 × 1080, clavier, souris), `Controls` (ligne de train, plein écran), `Net` (carte du réseau), titres en mots, trame |
| `src/engine/` | moteur d'animation : entrée des blocs, mouvements lents, transitions, TER 2D, trains sur la carte |
| `src/three/` | scènes 3D de la carte (intro courte, intro complète, « Suivez le train »), transitions TER 3D et histoire low poly (three.js), chargées à la demande |
| `src/data/` | `network.json`, `photos.json`, `videos.json` (générés), typés par `index.ts` |
| `public/assets/` | photos, paysages, images de l'histoire, modèles, vidéos |
| `public/vendor/` | `<model-viewer>` et son décodeur meshopt, pour le monument 3D (slide « Lieux à découvrir ») |

**Pourquoi un moteur à côté de React.** React rend le contenu des slides une fois ; ensuite le moteur anime le DOM
directement (Web Animations + une boucle `requestAnimationFrame` partagée). Aucun rendu React pendant un mouvement :
c'est ce qui garde le diapo à 60 images/s. React ne se met à jour qu'au changement de slide (compteur, ligne de train).

### Animer une slide

Dans le contenu, un bloc porte `data-in` (entrée : `up`, `left`, `right`, `zoom`, `pop`, `mask`, `flap`, `trame`,
`draw`, `throw`, `kenburns`, et `words` via `<Words>`), décalé par `data-d` (pas de 70 ms) ou placé à `data-at` ms ;
`data-idle` ajoute un mouvement lent sans fin (`float`, `bob`, `pulse`, `drift`, `sway`, `spin`, `spin-rev`, `wheel`).
Le reste (démo, carte, compteur) va dans `enter({ el, t0, run })` : `run.tick` / `run.later` s'arrêtent tout seuls
quand on quitte la slide.

Transitions (`trans` de la slide d'arrivée) : `train` (TER dessiné en 2D), `ter3d` (TER 3D de profil), `ter3d-front`
(TER 3D qui fonce vers la caméra), `zoom`, `cube`, `iris`, `flap`, `push`. Tant que three.js n'est pas chargé (ou
avec `?lite`), `ter3d` retombe sur `train` et `ter3d-front` sur `zoom`.

**Fluidité** : n'animer que `transform`, `opacity`, `clip-path` ; ce qui bouge à chaque image sur une carte va dans
le SVG superposé (`.net-ov`) ; pas d'animation à l'intérieur d'un SVG ou sous un `filter`. Ce sont ces règles qui ont
supprimé les saccades.

## Régénérer les données

```bash
backend/.venv/bin/python presentation/scripts/build-data.py   # réseau, itinéraire réel, photos, idées de sorties
presentation/scripts/story-upscale.sh                          # images de l'histoire -> JPEG 2048 px
```

Les vidéos du site sont enregistrées par `scripts/record/` (Claude pilote le vrai site) : pour les refaire,
`cd scripts/record && npm install`, le site doit tourner (front :5173 + API :8000) ; chaque démo réécrit
`src/data/videos.json`.
