# Cas de démo (comparaisons réelles)

Généré par `scripts/find_demo_cases.py` le 2026-10-10 05:27 UTC, lecture seule sur la base partagée. Les chiffres sont des comptes de lignes extraites : une absence ne prouve jamais une absence d'homologation. Les sœurs sont des hypothèses (`to_verify`). Les doses gardent leur unité originale (jamais converties).

Base URL des requêtes : `http://localhost:3000/api` (lancer `uvicorn backend.app.main:app --port 3000`).

## a) Produits pilotes et sœurs : lignes comparables par paire de pays

`use` = culture × cible, `crop` = culture seule (granularity=crop). Trié par `crop` puis `use`.

| Produit | ID | Type | Paire | Lignes use | Lignes crop |
|---|---|---|---|---|---|
| LALGUARD M52 OD | P-LPC-M52 | pilote | FR,DE | 2 | 5 |
| LALGUARD M52 OD | P-LPC-M52 | pilote | CA,DE | 0 | 5 |
| LALSTOP G46 WG | P-LPC-G46 | pilote | CA,DE | 0 | 4 |
| PRESTOP | P-CA-28820 | sœur (hypothèse) | CA,DE | 0 | 4 |
| PRESTOP WG | P-CA-32404 | sœur (hypothèse) | CA,DE | 0 | 4 |
| PRESTOP | P-FR-EPHY-2120177 | PRESTOP | CA,DE | 0 | 4 |
| PRESTOP 4B | P-FR-EPHY-2150847 | PRESTOP | CA,DE | 0 | 4 |
| PRESTOP (WP) | P-DE-BVL-027495-00 | PRESTOP | CA,DE | 0 | 4 |
| LALSTOP G46 WG | P-LPC-G46 | pilote | FR,DE | 1 | 3 |
| PRESTOP | P-CA-28820 | sœur (hypothèse) | FR,DE | 1 | 3 |
| PRESTOP WG | P-CA-32404 | sœur (hypothèse) | FR,DE | 1 | 3 |
| PRESTOP | P-FR-EPHY-2120177 | PRESTOP | FR,DE | 1 | 3 |
| LALSTOP G46 WG | P-LPC-G46 | pilote | FR,CA | 0 | 1 |
| LALGUARD M52 OD | P-LPC-M52 | pilote | FR,CA | 0 | 1 |
| PRESTOP | P-CA-28820 | sœur (hypothèse) | FR,CA | 0 | 1 |
| PRESTOP WG | P-CA-32404 | sœur (hypothèse) | FR,CA | 0 | 1 |
| PRESTOP | P-FR-EPHY-2120177 | PRESTOP | FR,CA | 0 | 1 |
| PRESTOP 4B | P-FR-EPHY-2150847 | PRESTOP | FR,CA | 0 | 1 |

Requêtes à utiliser en démo :

- LALGUARD M52 OD (FR,DE, 5 lignes crop) : `GET /compare?productId=P-LPC-M52&countries=FR,DE&granularity=crop`
- LALGUARD M52 OD (CA,DE, 5 lignes crop) : `GET /compare?productId=P-LPC-M52&countries=CA,DE&granularity=crop`
- LALSTOP G46 WG (CA,DE, 4 lignes crop) : `GET /compare?productId=P-LPC-G46&countries=CA,DE&granularity=crop`
- PRESTOP (CA,DE, 4 lignes crop) : `GET /compare?productId=P-CA-28820&countries=CA,DE&granularity=crop`
- PRESTOP WG (CA,DE, 4 lignes crop) : `GET /compare?productId=P-CA-32404&countries=CA,DE&granularity=crop`
- LALSTOP G46 WG (FR,CA, 1 lignes crop) : `GET /compare?productId=P-LPC-G46&countries=FR,CA&granularity=crop`
- LALGUARD M52 OD (FR,CA, 1 lignes crop) : `GET /compare?productId=P-LPC-M52&countries=FR,CA&granularity=crop`
- PRESTOP (FR,CA, 1 lignes crop) : `GET /compare?productId=P-CA-28820&countries=FR,CA&granularity=crop`

## b) Top 10 des couples culture × cible présents en FR et en DE

Nombre de produits (non synthétiques) ayant un usage sur ce couple, par pays. Trié par le plus petit des deux comptes.

| Culture | Cible | Produits FR | Produits DE |
|---|---|---|---|
| Barley | Rhynchosporium leaf blotch (Rhynchosporium secalis) | 115 | 164 |
| Rye | Rhynchosporium leaf blotch (Rhynchosporium secalis) | 101 | 136 |
| Wheat | Fusarium diseases | 91 | 104 |
| Oats | Crown rust | 85 | 55 |
| Wheat | Eyespot | 48 | 44 |
| Grapevine | Botrytis cinerea | 50 | 37 |
| Barley | Eyespot | 34 | 34 |
| Pome fruit | Scab | 103 | 31 |
| Pome fruit | Aphids | 24 | 87 |
| Roses | Aphids | 36 | 23 |

Requêtes :

- Barley × Rhynchosporium leaf blotch (Rhynchosporium secalis) : `GET /products?crop=Barley&target=Rhynchosporium leaf blotch (Rhynchosporium secalis)` puis `GET /compare?productId=<id>&countries=FR,DE&crop=Barley&target=Rhynchosporium leaf blotch (Rhynchosporium secalis)`
- Rye × Rhynchosporium leaf blotch (Rhynchosporium secalis) : `GET /products?crop=Rye&target=Rhynchosporium leaf blotch (Rhynchosporium secalis)` puis `GET /compare?productId=<id>&countries=FR,DE&crop=Rye&target=Rhynchosporium leaf blotch (Rhynchosporium secalis)`
- Wheat × Fusarium diseases : `GET /products?crop=Wheat&target=Fusarium diseases` puis `GET /compare?productId=<id>&countries=FR,DE&crop=Wheat&target=Fusarium diseases`
- Oats × Crown rust : `GET /products?crop=Oats&target=Crown rust` puis `GET /compare?productId=<id>&countries=FR,DE&crop=Oats&target=Crown rust`
- Wheat × Eyespot : `GET /products?crop=Wheat&target=Eyespot` puis `GET /compare?productId=<id>&countries=FR,DE&crop=Wheat&target=Eyespot`

## c) Top 10 des cultures avec des produits retirés ou expirés

Produits distincts par culture et par pays (statut normalisé `withdrawn` ou `expired` vs `active`). Un produit peut compter dans les deux colonnes s'il a plusieurs homologations.

**Aucune culture n'a de produit retiré/expiré avec des usages.** Dans les données actuelles, les homologations retirées (FR : `RETIRE`) n'ont aucun usage extrait, donc aucun lien avec une culture ; DE n'a pas de statut (`unknown`). Ce n'est pas une preuve d'absence de retraits par culture.

| Pays | Statut normalisé | Homologations | Usages |
|---|---|---|---|
| CA | active | 2089 | 87816 |
| CA | unknown | 11 | 489 |
| DE | unknown | 2165 | 82239 |
| FR | active | 1687 | 18023 |
| FR | withdrawn | 11882 | 0 |

Cas de démo possible : lister les retraits sans culture avec `GET /expirations?country=FR`.

Requêtes :

- (voir ci-dessus : `GET /expirations?country=FR`)

## d) Opportunité marché : espaces libres pour le biocontrôle

**Aide à l'analyse, pas une décision réglementaire ; classification biologique/chimique par règle, à vérifier.** Par couple culture × cible normalisés : usages ACTIFS de produits chimiques vs biologiques (catégorie déduite du nom de la substance active, hypothèse). Score = usages chimiques / (1 + usages biologiques). Aucun usage retiré n'existe dans les sources : le classement montre l'état actuel, pas un recul. « Retirés, même substance » = produits retirés du même pays contenant une substance de ces chimiques, SANS lien culture × cible (ce ne sont pas des usages retirés). Un 0 biologique ne prouve pas l'absence de produit biologique homologué.

Requête exacte : `GET /opportunities?country=FR&limit=5`

| Culture × cible | Pays | Usages chimiques | Usages biologiques | Score | Produits LPC / sœurs autorisés | Retirés, même substance |
|---|---|---|---|---|---|---|
| General treatments × Slugs and snails | FR | 165 | 0 | 165.0 | aucun | 285 |
| Wheat × Rust | FR | 151 | 0 | 151.0 | aucun | 254 |
| Wheat × Septoria leaf spot | FR | 134 | 0 | 134.0 | aucun | 481 |
| Barley × Rust | FR | 128 | 0 | 128.0 | aucun | 144 |
| Barley × Rhynchosporium leaf blotch (Rhynchosporium secalis) | FR | 126 | 0 | 126.0 | aucun | 202 |

Requête exacte : `GET /opportunities?country=DE&limit=5`

| Culture × cible | Pays | Usages chimiques | Usages biologiques | Score | Produits LPC / sœurs autorisés | Retirés, même substance |
|---|---|---|---|---|---|---|
| Ornamental plants × Spider mites | DE | 1135 | 0 | 1135.0 | aucun | n/a |
| Ornamental plants × Scale insects | DE | 826 | 0 | 826.0 | aucun | n/a |
| Ornamental plants × Aphids | DE | 743 | 0 | 743.0 | aucun | n/a |
| Ornamental plants × Sucking insects | DE | 712 | 0 | 712.0 | aucun | n/a |
| Bottle gourd × Sucking insects | DE | 594 | 0 | 594.0 | aucun | n/a |

Requête exacte : `GET /opportunities?country=FR&lpcOnly=true&limit=5`

| Culture × cible | Pays | Usages chimiques | Usages biologiques | Score | Produits LPC / sœurs autorisés | Retirés, même substance |
|---|---|---|---|---|---|---|
| Tomato; Eggplant × Brown spot diseases | FR | 51 | 4 | 10.2 | PRESTOP (sister_candidate) | 161 |
| Cucurbits with edible peel × Brown spot diseases | FR | 19 | 1 | 9.5 | PRESTOP (sister_candidate) | 59 |
| Tomato; Eggplant × Mites | FR | 25 | 2 | 8.33 | LALGUARD M52 OD (lpc_product) | 78 |
| Grapevine × Thrips | FR | 18 | 2 | 6.0 | LALGUARD M52 OD (lpc_product) | 110 |
| Cut flowers and foliage plants × Botrytis cinerea | FR | 15 | 2 | 5.0 | PRESTOP (sister_candidate) | 86 |

Requête exacte : `GET /opportunities?productId=P-LPC-M52&limit=5`

| Culture × cible | Pays | Usages chimiques | Usages biologiques | Score | Produits LPC / sœurs autorisés | Retirés, même substance |
|---|---|---|---|---|---|---|
| Leek × Thrips | DE | 7 | 0 | 7.0 | aucun | n/a |
| Onion × Thrips | DE | 7 | 0 | 7.0 | aucun | n/a |
| Grapevine × Thrips | DE | 6 | 0 | 6.0 | aucun | n/a |

Avec `lpcOnly=true`, seuls les couples où un produit LPC, un candidat sœur ou un produit de même substance est déjà autorisé sont gardés (potentiel d'extension d'un produit déjà présent). Avec `productId`, la liste montre les couples où la substance du produit est autorisée dans au moins un pays mais pas dans le pays indiqué. Les produits sœurs et de même substance sont des hypothèses (`to_verify`). Question `/ask` associée : « Où les usages chimiques reculent-ils sur la vigne ? » ou « Quelles opportunités pour LALGUARD M52 ? ».

## e) Canada : usages chimiques retirés (historique Health Canada) × produits LPC autorisés

Seul le Canada publie des usages de produits retirés (937 homologations « withdrawn » avec leur date de fin officielle). `GET /opportunities?country=CA` renvoie donc, par couple culture × cible : `withdrawnChemicalUses`, `withdrawnChemicalProducts`, `lastWithdrawalDate` (plus grande `expiration_date`) et `withdrawnEvidenceIds` (homologations retirées citées). Pour FR et DE ces champs valent `null`.

⚠️ **Résultats NON remplis : impossible avec les données actuelles.** Vérifié en lecture seule sur la base : sur les 37 126 usages CA retirés (et sur les 88 305 usages actifs), **aucune ligne n'a à la fois une culture et une cible** (`crop_name_original` et `target_name_original` ne sont jamais renseignés ensemble : 16 025 lignes ont une culture, 21 101 ont une cible, 0 les deux). L'API de production le dit déjà : « CA : 0 usages actifs sur 88305 ont une culture et une cible normalisées ». Ce n'est donc pas un manque de normalisation (relancer `--normalize-db` ne changera rien) mais la forme des données CA telles que chargées. Relier une culture à une cible reviendrait à inventer un lien : non fait. Aucun chiffre n'est donné ici (règle : pas de donnée inventée). Le code est prêt : dès que des lignes CA porteront culture ET cible, `withdrawnChemicalUses`, `lastWithdrawalDate` et `/ask` les utiliseront sans autre changement. Le SQL ci-dessous s'exécute sans erreur sur la base (résultat vide pour l'instant).

Requête API (classement par score ; `lpcOnly=true` garde les couples où un produit LPC ou sœur est autorisé) : `GET /opportunities?country=CA&lpcOnly=true&limit=5`

Requête SQL exacte, lecture seule, pour classer par **usages chimiques retirés** les 5 premiers couples CA où un produit LPC ou un candidat sœur (lien exact `product_aliases.related_product_id`) est autorisé (même règle chimique/biologique que l'API : substance sans nom de micro-organisme) :

```sql
WITH retire AS (          -- usages chimiques retirés (Canada)
    SELECT u.crop_name_normalized AS crop, u.target_name_normalized AS target,
           count(*) AS retired_chemical_uses, count(DISTINCT p.product_id) AS retired_chemical_products,
           max(r.expiration_date) AS last_withdrawal_date
    FROM uses u
    JOIN registrations r ON r.registration_id = u.registration_id
    JOIN products p ON p.product_id = r.product_id
    WHERE r.country_code = 'CA' AND r.status_normalized = 'withdrawn'
      AND NOT u.is_synthetic AND NOT r.is_synthetic AND NOT p.is_synthetic
      AND u.crop_name_normalized IS NOT NULL AND u.target_name_normalized IS NOT NULL
      AND left(p.product_id, 6) <> 'P-LPC-'
      AND coalesce(btrim(p.active_entity_original), '') <> ''
      AND p.active_entity_original !~* '(bacillus|trichoderma|clonostachys|gliocladium|coniothyrium|metarhizium|beauveria|pseudomonas|streptomyces|saccharomyces|paecilomyces|purpureocillium|isaria|lecanicillium|verticillium|akanthomyces|ampelomyces|aureobasidium|pythium|candida|metschnikowia|phlebiopsis|chondrostereum|arthrobotrys|virus|bacteriophage)'
    GROUP BY 1, 2
), lpc_autorise AS (      -- produits LPC ou sœurs (hypothèses) avec un usage ACTIF sur le couple
    SELECT DISTINCT u.crop_name_normalized AS crop, u.target_name_normalized AS target,
           p.product_id, p.commercial_name
    FROM uses u
    JOIN registrations r ON r.registration_id = u.registration_id
    JOIN products p ON p.product_id = r.product_id
    WHERE r.country_code = 'CA' AND r.status_normalized IN ('active', 'unknown')
      AND NOT u.is_synthetic AND NOT r.is_synthetic AND NOT p.is_synthetic
      AND (left(p.product_id, 6) = 'P-LPC-'
           OR p.product_id IN (SELECT a.related_product_id FROM product_aliases a
                               WHERE NOT a.is_synthetic AND a.related_product_id IS NOT NULL
                                 AND a.relationship_type IN ('sister_product_candidate', 'confirmed_sister_product')))
)
SELECT w.crop, w.target, w.retired_chemical_uses, w.retired_chemical_products, w.last_withdrawal_date,
       string_agg(DISTINCT l.commercial_name, ', ') AS lpc_or_sister_products
FROM retire w
JOIN lpc_autorise l ON l.crop = w.crop AND l.target = w.target
GROUP BY w.crop, w.target, w.retired_chemical_uses, w.retired_chemical_products, w.last_withdrawal_date
ORDER BY w.retired_chemical_uses DESC, w.crop, w.target
LIMIT 5;
```

Les produits sœurs restent des hypothèses (`to_verify`). Un résultat vide ne prouve pas l'absence d'opportunité. Question `/ask` associée : « Quels espaces libres pour le biocontrôle au Canada ? » (la réponse cite le nombre d'usages chimiques retirés et la date du dernier retrait, faits uniquement).
