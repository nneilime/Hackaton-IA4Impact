# Paysage vu du wagon (WagonInterior.tsx)

Tout passe d'abord par la bibliothèque `~/Documents/godotGame/asset-generator-3d/asset/` ; ici, des copies allégées
pour le web.

| Fichier | Origine | Auteur | Licence |
|---|---|---|---|
| `trees.glb` | « Realistic Trees Collection » — https://sketchfab.com/3d-models/realistic-trees-collection-fe67c886eebf4bcb988d7c45e69995ad | Jungle Jim | **CC-BY 4.0** (crédit affiché dans le wagon) |
| `cypress.glb` | « Cypress tree » — https://sketchfab.com/3d-models/cypress-tree-249d8cb553a8469e9d645713f8e96ed1 | ElectroNick | **CC-BY 4.0** (crédit affiché dans le wagon) |
| `sky.jpg` | HDRI « Alps Field » (JPG tonemappé, réduit à 4096 px) — https://polyhaven.com/a/alps_field | Poly Haven | CC0 |
| `leafy_grass.jpg`, `gravel_stones.jpg`, `dry_mud_field_001.jpg` | textures Poly Haven (diffuse 2k réduite à 1k) | Poly Haven | CC0 |

Les deux `.glb` : `gltf-transform optimize --compress meshopt --texture-compress webp --texture-size 512
--simplify false --join false --flatten false --palette false` (le chargeur a besoin du MeshoptDecoder).
