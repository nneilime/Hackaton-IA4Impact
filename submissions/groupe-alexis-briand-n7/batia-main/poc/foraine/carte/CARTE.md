> Dans ce dossier, le module est dans `carte/` et ses outils dans `carte/outils/`. Les passages sur `assise/` décrivent la greffe faite dans la première version d'Assise ; ils servent d'exemple d'intégration.

# La carte vectorielle d'Assise

Une carte qui remplace le fond OpenStreetMap en images passé au filtre sépia. Le fond est vectoriel et reste sur la machine : MapLibre GL JS 6.13.0, un extrait du fond Protomaps (OpenStreetMap) et des glyphes Noto Sans, tous servis depuis `carte/`. Une fois le dossier copié, la carte ne demande plus rien à Internet. `outils/sans-internet.py` le vérifie : il bloque toute requête qui ne va pas vers localhost, et le compte est de 0.

## Lancer

```bash
node carte/serveur.mjs            # page de démonstration : http://localhost:4600/demo/
cd assise && PORT=4500 node serveur.mjs   # Assise avec la nouvelle carte : http://localhost:4500/#/parc
```

La démonstration accepte `?echelle=france|sudouest|toulouse`. Ajoutez `&direct` pour ouvrir sans le glissement depuis la France.

Le fond (`carte/fond/*.pmtiles`, 140 Mo) n'est pas versionné. S'il manque, refaites-le avec `outils/extraire-fond.sh`, décrit plus bas.

## Ce que montre la carte

Il n'y a pas de style clair surmonté d'un filtre : chaque couche a sa propre couleur, prise dans la palette d'Assise (`carte/style.mjs`).

| Couche | Couleur | Quand |
|---|---|---|
| Terre | mortier clair `#F3ECDF` | toujours |
| Mer, lacs, Garonne, canal | ardoise pâle `#BCCAC7` / `#A9BDBA`, seul froid de la carte (le `--froid` d'Assise) | rivières dès le Sud-Ouest |
| Aire urbaine | lavis de brique très clair `#EEDCC9` (la « ville rose ») | toujours, plus net en ville |
| Forêts | grain d'olive `#E8E4D0`, très atténué de loin | toujours |
| Parcs | `#E3E3CA` | métropole et quartier |
| Routes | des joints : âme `#FFFCF6` bordée de sable `#DCC6A6` ; de loin, trait sable foncé | voies rapides dès le Sud-Ouest, grands axes à la métropole, rues au quartier |
| Haute-Garonne | maçonnée : lavis de brique et trait de brique cuite | France, Sud-Ouest |
| Quatre autres départements | trait de joint pointillé, nom et « à raccorder » (celui de la Gironde est posé dans le Médoc, pour laisser Bordeaux lisible) | Sud-Ouest |
| Frontières | trait brun fin et halo | France, Sud-Ouest |
| Secteurs des résidences | cercle de 400 m en pointillé, teinté selon le niveau | métropole rapprochée, quartier |

**Ce qui est retiré** : bâtiments, points d'intérêt, numéros de routes, chemins, voies de service, rails et frontières de régions. Les noms de pays se limitent aux grands voisins (Espagne, Italie, Suisse…).

**Les noms** : villes, hiérarchisées par population, puis quartiers en petites capitales dès le zoom 12. Les noms de grandes rues apparaissent au quartier, ceux des rivières en italique ardoise. Tous sont en français quand OSM le permet (`name:fr`). Comme ils sont vectoriels, ils restent nets entre deux zooms.

**Le zoom** est continu, sans crans. Il s'arrête à 15, l'échelle du quartier. Aucun bâtiment n'est dessiné : une résidence placée à une position fictive ne peut jamais sembler posée sur un vrai immeuble.

**Les repères** sont un carré par résidence, une « brique » à l'échelle de son nombre de logements (la surface suit le nombre). Sa base se remplit de brique cuite pour les logements à visiter et de brique claire pour ceux à surveiller. L'étiquette donne les mêmes chiffres en toutes lettres (doctrine R3 : la couleur n'est jamais seule). Les étiquettes ne se chevauchent pas et ne couvrent pas les grandes villes : la résidence la plus exposée se place d'abord, sur l'une des huit positions autour de sa brique. Une étiquette sans place se tait et réapparaît au survol ou au focus. Au téléphone, elle se réduit au nombre de logements à visiter. Vue de loin, la métropole devient une seule brique (8 résidences, 1 100 logements), qui s'ouvre en huit quand on s'approche : les briques se posent l'une après l'autre.

**Le mouvement** : le passage d'une échelle à l'autre est un vol en arc (1,7 s), sauf si le système demande moins d'animations. À la première ouverture, comme dans Assise, la carte glisse de la France au Sud-Ouest.

## Intégrer le module

Copiez (ou liez) le dossier `carte/` dans les fichiers statiques de l'application. Le serveur doit accepter les requêtes `Range`, car les `.pmtiles` se lisent par morceaux. Ajoutez-y aussi les types `.mjs` → `text/javascript` et `.pbf` / `.pmtiles` → `application/octet-stream`.

```js
const { creerCarte } = await import('/vendor/carte/carte.mjs');
const carte = await creerCarte(document.querySelector('#carte'), {
  residences: [
    // position : [lat, lng] fictive ; aVisiter / aSurveiller : nombre de logements ; communsAVisiter : équipements communs prioritaires
    { id: 'RES-D', nom: 'Résidence D', lettre: 'D', position: [43.566, 1.398], logements: 100, aVisiter: 16, aSurveiller: 26, communsAVisiter: 0 },
  ],
  echelle: 'sudouest',   // échelle d'arrivée : 'france' | 'sudouest' | 'toulouse'
  depuis: 'france',      // facultatif : échelle de départ, pour un premier glissement
  molette: false,        // zoom à la molette (désactivé dans une page qui défile)
});
el.addEventListener('carte:residence', (e) => ouvrir(e.detail.id));   // on a choisi une résidence
el.addEventListener('carte:echelle', (e) => marquer(e.detail.echelle)); // l'échelle a changé (bouton ou geste)
carte.allerA('toulouse');   // passage fluide vers une échelle
carte.detruire();           // avant de remonter la vue
```

Le module charge lui-même ses feuilles de style (`maplibre-gl.css`, `carte.css`). Il trouve ses fichiers à partir de sa propre adresse (`import.meta.url`), quel que soit le chemin où on le sert. Les couleurs des repères reprennent les variables CSS d'Assise (`--encre`, `--brique-cuite`, `--brique-claire`, `--papier`…), avec des valeurs de repli.

**Dans `assise/`**, cinq modifications ont été faites, et rien d’autre :
- `app/vendor/carte` est un lien vers `../../../carte` ;
- `app/index.html` ne charge plus Leaflet ;
- `app/app.js` : `monterCarte()` appelle le module et calcule pour chaque résidence les logements à visiter et à surveiller, à partir du niveau de chaque logement, déjà calculé par Assise ;
- `serveur.mjs` : lecture par plages (`Range`) et deux types de fichiers ;
- `outils/captures.py` : le script attend la nouvelle carte (`.carte-prete`) au lieu de `.leaflet-container`.

L'original reste comparable : `git archive 70b7195 assise | tar -x -C telechargements/avant/`, puis `PORT=4501 node serveur.mjs` dans ce dossier.

## Refaire l'extrait

```bash
outils/extraire-fond.sh            # build Protomaps 20261009 par défaut
outils/extraire-fond.sh 20261108   # un build plus récent (voir https://maps.protomaps.com/builds/)
```

Le script télécharge go-pmtiles v1.31.2, puis découpe trois extraits du build Protomaps. Le fichier source fait 139 Go, mais il n'est lu que par plages : seules les zones demandées descendent.

| Fichier | Zone | Zooms | Taille |
|---|---|---|---|
| `france-z0-8.pmtiles` | -6.2,41.0 → 10.2,51.6 | 0 à 8 | 30 Mo |
| `sud-ouest-z9-11.pmtiles` | -2.3,42.4 → 4.5,45.95 | 9 à 11 | 80 Mo |
| `toulouse-z12-14.pmtiles` | 0.95,43.33 → 1.9,43.95 | 12 à 14 | 30 Mo |

Le module les relie par un protocole `assise-fond://` : chaque niveau de zoom est lu dans son extrait. Hors d'un extrait, par exemple au zoom 10 au-dessus de Lyon, la tuile manquante renvoie une erreur volontaire, et MapLibre affiche à sa place la tuile parente, moins détaillée. Cela évite les trous. Les glyphes (`carte/vendor/glyphes/`, 6 Mo) viennent de `https://protomaps.github.io/basemaps-assets/fonts/` (Noto Sans Regular, Medium et Italic, plages 0 à 8447).

## Vérifications

- `python3 outils/sans-internet.py` : ouvre Assise, bloque toute requête hors localhost et compte celles qui auraient dû sortir. Résultat : une cinquantaine de requêtes locales, 0 vers Internet.
- L'événement `carte:residence` a été vérifié dans la démonstration (le panneau affiche la résidence choisie) et dans Assise (le clic sur une brique ouvre `#/residence/RES-…`).

## Captures

`python3 outils/captures.py [avant|apres] [ordi|tel]` produit `captures/<version>-<appareil>-<échelle>.png` aux trois échelles et au quartier (8 captures avant, 8 après, déjà dans `captures/`). Avant de le lancer, l'original doit tourner sur 4501 et la nouvelle version sur 4500. Chromium tourne sans écran, avec le rendu logiciel SwiftShader.

## Ce qui reste à faire

- La page Méthode d'Assise dit encore que « seul le fond de carte public est chargé depuis Internet ». Ce n'est plus vrai, mais la consigne interdisait de toucher au reste de l'appli : la phrase est à corriger.
- La note sous la carte d'Assise cite OpenStreetMap seul. L'attribution de la carte cite Protomaps et OpenStreetMap ; la note peut s'aligner.
- Le fond n'est détaillé (zooms 12 à 14) qu'autour de la métropole toulousaine. Quand Gironde, Hérault, Landes et Pyrénées-Atlantiques se raccorderont, il faudra un extrait par métropole (environ 30 Mo chacune), ajouté à `EXTRAITS` dans `carte.mjs`.
- Les glyphes Noto Sans ne sont pas les polices d'Assise (Source Sans 3 et Source Serif 4). Les repères, eux, sont en HTML et utilisent les polices d'Assise. On pourrait générer des glyphes Source Sans 3 (avec `build_pbf_glyphs` ou `fontnik`) pour unifier.
- Sur téléphone, l'étiquette se réduit à ce qu'il faut aller voir (« 16 à visiter ») : la taille de la brique dit déjà le nombre de logements. À l'échelle de la métropole, six étiquettes sur huit trouvent leur place. F et C, aux libellés plus longs, se taisent ; leur brique reste touchable. Une liste repliable sous la carte pourrait compléter.
- Les comptages de la démonstration (`carte/demo/residences.mjs`) sont une photographie des données fictives au 31/12/2025. Dans Assise, ils sont recalculés à chaque chargement.
