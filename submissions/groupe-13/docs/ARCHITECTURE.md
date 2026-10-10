# Architecture et choix techniques (version 3.0)

> Les sections 1 à 6 bis décrivent la base héritée de la version 2.0, toujours en place. Les changements de la version 3.0 sont regroupés en section 6 ter.

## 1. Audit des ressources (phase 1)

| Élément | Constat vérifié |
|---|---|
| Archive | `General-main.zip`, 112 entrées, intégrité ZIP vérifiée, aucun chemin dangereux |
| Bordereaux | 55 JPG : famille 1 (20, 1190×1684), famille 2 (20, 1190×1683), famille 3 (15, 1684×2382) |
| Factures | 55 TXT, ASCII, fins de ligne CRLF, aucun enregistrement de type 0 |
| Spécification | `Les contrôles à implémenter.docx` (nom encodé `#U00f4` dans l'archive, décodé à l'extraction) |
| Mises en page | 3 logiciels d'établissement différents, une mise en page par famille ; à l'intérieur d'une famille, les images sont parfaitement superposables (décalage mesuré : 0 px) |
| Types d'enregistrement | 1 (55), 2 (56), 2-S (19), 3 (116), 3-S (94), 3-H (20), 4 (318), 4-S (282), 4-M (167), 4-B (38), 5 (55), 6 (55) |
| Longueurs de ligne | variables : 70 à 129 caractères selon le type |
| Particularités | `Facture2_06.txt` décalé d'un caractère ; les numéros de facture de la famille 3 sont cadrés sur 9 chiffres (`000491901`) alors que le bordereau imprime `491901` ; le bordereau imprime `12278*01` alors que le cahier des charges écrit `12278*0` |

## 2. Architecture

```
            ┌──────────────┐   ┌──────────────────┐
 ZIP ──────►│ corpus.py    │──►│ manifeste SHA-256│
            │ extraction   │   │ appariement JPG/TXT (hypothèse par nom)
            └──────┬───────┘   └──────────────────┘
                   │
       ┌───────────┴────────────┐
       ▼                        ▼
 ┌────────────┐          ┌─────────────────────────────────────────┐
 │ b2parser   │          │ ocr/ : qualité → orientation → famille → │
 │ positions  │          │ recalage → gabarit → lecture multiple →  │
 │ fixes      │          │ tableaux → signatures → coordonnées      │
 └─────┬──────┘          └───────────────┬─────────────────────────┘
       │                                  │ cache JSON (sha256)
       └──────────────┬───────────────────┘
                      ▼
            ┌────────────────────┐   corrections / validations humaines (validées, historisées)
            │ rules.py (R01-R22) │◄───────────────────────────────
            │ + observations     │
            │ + rapprochement    │
            └─────────┬──────────┘
                      ▼
            ┌────────────────────┐   géométrie des gabarits + recalage + résultats des règles
            │ zones.py (Z1-Z15)  │   → statut, régions, données extraites, liens TXT par zone
            └─────────┬──────────┘
                      ▼
            ┌────────────────────┐      ┌────────────────────────────────────┐
            │ pipeline + SQLite  │◄────►│ api.py (FastAPI)                   │◄── interface React
            │ jobs.py (verrous)  │      │ rôles, journal, PDF, finance.py,   │
            └────────────────────┘      │ triage.py, conventions.py, backup  │
                                        └────────────────────────────────────┘
```

Tout s'exécute en local. L'IA (OCR, détection de présence) est utilisée pour les tâches perceptives ; les vérifications d'identifiants, codes, montants et relations sont **déterministes**.

## 3. Modèle de données

| Entité (prompt) | Réalisation |
|---|---|
| SourceFile | table `source_files` (chemin, type, taille, SHA-256, lecture seule) |
| DocumentPair / ReviewCase | table `cases` (paire, statut d'appariement, statut d'instruction, agent, priorité) |
| Invoice, InvoiceAct | `ParsedB2` (enregistrements, actes 3/4, CCAM 4-M, GH 4-S, totaux) avec provenance ligne/positions |
| ExtractedField, OCRRegion | champs `fields`, `tables`, `signatures` de l'extraction : valeur brute, normalisée, zone, boîte en pixels et normalisée, méthode, lectures individuelles, confiance des moteurs, niveau d'accord |
| RuleDefinition | `RULES` (id, catégorie, formulation du cahier des charges, convention) |
| CheckResult / Anomaly | `check_results` + résultat complet dans `analyses` (valeurs confrontées, écart, preuves image/TXT, incertitude, version, provenance) |
| ReviewDecision | `decisions` (type, règle, valeur, commentaire, auteur, horodatage) et `corrections` (original conservé) |
| User | `users` (mot de passe scrypt salé), `sessions` (jeton aléatoire stocké haché, cookie HttpOnly) |
| AuditEvent | `audit` |

## 4. Parseur TXT

- Positions du cahier des charges, numérotées à partir de 1 et inclusives (`ligne[début-1:fin]`).
- Sous-types selon les priorités du document : 2-S (pos. 39), 3-S (pos. 39) avant 3-H (pos. 36), 4-S/4-M/4-B (pos. 36).
- Aucun `strip()` global ; les codes sont nettoyés localement au champ ; les identifiants restent des chaînes ; les montants sont en centimes entiers.
- Aucune ligne perdue (test sur les 55 fichiers) ; lignes trop courtes, inconnues, non rattachées, débuts de facture répétés, lignes identiques et décalages de positions signalés en **observations**.

## 5. Extraction des bordereaux

1. Qualité (netteté, luminosité), orientation (0/180°), identification de la mise en page par corrélation de la carte des traits du formulaire avec trois références, puis recalage sur des lignes d'ancrage. En 3.0 : redressement des petites inclinaisons, ajustement d'échelle et fiabilité géométrique par champ (section 6 ter).
2. Gabarits normalisés des 15 zones (et colonnes des tableaux) par mise en page.
3. Effacement des traits du formulaire par inpainting (les caractères traversés par un trait sont reconstruits).
4. **Lecture multiple** de chaque champ et de chaque cellule : RapidOCR (brut, sans traits, ×2) et Tesseract (sans traits, brut). Chaque lecture est normalisée puis validée par le format attendu du champ ; les valeurs valides sont soumises à un vote. Le niveau d'accord (`concordant`, `majoritaire`, `lecture_unique`, `divergent`, `illisible`, `vide`) est conservé avec toutes les lectures.
5. Tableaux : segmentation des lignes par projection, lecture cellule par cellule, distinction lignes d'acte / lignes de détail (codes de biologie).
6. Signatures : détection de **présence** (taux d'encre, composantes, tracés larges), jamais d'authenticité ; lecture du numéro d'exécutant imprimé dans chaque case pour l'association zone 9 ↔ zone 11.

Normalisations documentées (visibles dans les lectures) : séparateur du n° CERFA lu comme un symbole → `*` ; préfixe du code CERFA lu `8`/`5`/`$` → `S` ; `O`→`0` dans la partie numérique d'un code CCAM ; « GHS » dont le G est traversé par un trait de colonne.

## 6. Moteur de règles

Chaque règle est une fonction indépendante qui renvoie `CONFORME`, `ANOMALIE`, `NON_VERIFIABLE`, `NON_APPLICABLE` ou `ERREUR_TECHNIQUE` (une exception n'interrompt jamais les autres règles).

Décision sur un champ lu par OCR :
- `CONFORME` si la valeur la plus soutenue égale la valeur attendue ;
- `ANOMALIE` si aucune lecture valide ne correspond et que la valeur retenue est soutenue par au moins deux lectures concordantes (ou une lecture unique de confiance élevée, signalée « à confirmer ») ;
- `NON_VERIFIABLE` sinon. Un non vérifiable n'est jamais compté comme conforme.

Les rapprochements de codes (R08, R11, R13, R14, R15, R19) se font **occurrence par occurrence**. Les conventions d'interprétation sont listées dans l'écran « Règles et limites » et dans la supervision (AMB-01 à AMB-08).

## 6 bis. Nouveautés de la version 2.0

### Politique d'incertitude (`rules.compare_read`)
La valeur du fichier TXT ne sert **jamais** à choisir une lecture du bordereau :
- **Ex æquo** : des lectures contradictoires ayant le même niveau de preuve (même nombre de moteurs distincts, même nombre de lectures) donnent `NON_VERIFIABLE`, même si l'une d'elles égale la valeur attendue.
- **Moteurs en désaccord** (accord « divergent ») : `NON_VERIFIABLE`.
- **Rapprochement des codes des tableaux** : un appariement fondé sur une lecture minoritaire, divergente ou ex æquo est marqué incertain, et la règle ne conclut pas à la conformité.
- **Ligne GHS de la zone 6** : si elle n'est identifiée que par une lecture minoritaire, les règles qui en dépendent (R06, R07, R10, R16) ne concluent pas.
- **R20** : uniquement sur des montants fiables (lectures concordantes ou majoritaires, ou correction d'un agent). Aucune combinaison de candidats n'est recherchée. Les valeurs candidates sont conservées.
- **Lever l'incertitude** : une validation ou une correction humaine le fait.

### Cache OCR versionné (`ocrcache.py`)
- **Clé** : SHA-256 de l'image + empreinte du code d'extraction. Cette empreinte couvre les sources `ocr/*.py`, `normalize.py`, les gabarits et les cartes de référence, et elle est calculée indépendamment des fins de ligne Windows/Linux.
- **Configuration OCR** (version de RapidOCR, version majeure de Tesseract ou son absence) : enregistrée avec chaque extraction. Une configuration différente de celle du poste est **signalée** dans le dossier, et `cli extract --force` recalcule l'extraction.
- **Écriture et intégrité** : écriture atomique, empreinte du contenu vérifiée à la lecture. Un fichier corrompu est mis à l'écart puis recalculé. Un ancien format ou un code modifié rend l'extraction obsolète et la fait recalculer.
- **Clé d'analyse** (`pipeline.analysis_key`) : sources JPG et TXT, versions du moteur et des règles, code d'extraction et code d'analyse (parseur, règles, zones). Au démarrage, `sync_cases` analyse seulement les dossiers nouveaux ou modifiés et marque « source absente » ceux dont les fichiers ont disparu (leurs décisions sont conservées).

### Couche des 15 zones (`zones.py`)
Vue dérivée : géométrie issue des gabarits et du recalage, indépendante de l'OCR, table zone ↔ règles, statut de zone et contenu de la fiche. Détail dans `docs/ZONES.md`.

### Traitements (`jobs.py`)
- **Table `jobs`** : type, cible, statut (en attente, en cours, terminé, erreur, interrompu), progression, dates, durée, résultat ou erreur.
- **Idempotence** : une soumission identique renvoie le traitement en cours.
- **Verrous** : un verrou par dossier (analyse, réanalyse et correction sérialisées, aucune analyse ancienne n'écrase une plus récente) et une maintenance exclusive pour la purge.
- **Reprise** : un traitement interrompu par un arrêt est marqué « interrompu ». Aucune infrastructure externe n'est utilisée.

### Corrections (`corrections.py`)
- **Contrôles** : liste blanche des cibles, existence et indices de tableau, type et format (montant, FINESS à 9 chiffres, code CCAM, GHS…), valeurs PRESENT et VIDE pour les signatures. Une correction invalide est refusée (400) et n'est jamais enregistrée.
- **Validation** : saisir la valeur déjà lue la valide.
- **Effet** : l'effet de chaque correction (règles et zones modifiées) est enregistré.

### Finances (`finance.py`)
- Un écart est rattaché au dossier, à la règle, à ses lignes et à la dernière décision non annulée de cette règle.
- Un montant n'est confirmé que si la règle est en anomalie **et** confirmée.
- Pas de double comptage : par famille (prestations, honoraires), on retient le maximum entre l'écart sur le total et la somme des lignes.
- R20 est exclu, car il ne porte pas sur un montant facturé.
- Indu établi et montant récupéré : non calculables.

### Autres modules
- `triage.py` : regroupements d'alertes, formulés au conditionnel et sans score.
- `conventions.py` : effet d'un changement de convention, rejoué sur le corpus.
- `backup.py` : sauvegarde transactionnelle vérifiée et restauration contrôlée.
- `cli.py` : `sync`, `cache`, `backup`, `restore`, `reset-password`, `create-admin`.

## 6 ter. Nouveautés de la version 3.0

Point de départ : le diagnostic des fausses anomalies (`docs/DIAGNOSTIC_V3.md`). Chaque modification corrige une cause constatée ou ferme un risque démontré. Aucune règle n'a été assouplie pour réduire le nombre d'alertes.

### Fichier B2 mal formé (`b2parser.detect_insertion`)
- **Cas traité** : un blanc inséré au même index dans au moins 90 % des lignes (Facture2_06).
- **Preuve exigée** : au moins 3 vérifications internes au fichier qui échouent avant et réussissent après le retrait du blanc. Ces vérifications portent sur les marqueurs de sous-type, le n° de facture unique, les codes d'actes, les dates AAMMJJ des lignes 3 et la somme des bases égale au TotalPrestations.
- **Condition impérative** : les identifiants (positions 12-24 et 30-38) restent entièrement numériques.
- **Ce qui n'intervient jamais** : le bordereau.
- **Traçabilité** : la ligne d'origine est conservée (`Record.raw_original`) et `original_position()` reporte le surlignage sur le fichier d'origine.
- **Signalement** : observation `FICHIER_REALIGNE` (alerte), note sur chaque contrôle concerné, priorité +15 avec son motif.

### Géométrie (`ocr/layout.py`, `ocr/extract.py`)
- **Inclinaison** : `estimate_skew` (profil de projection, ±6°), puis `deskew` et nouveau recalage si l'inclinaison est ≥ 0,3°. L'image servie à l'interface est l'image redressée (`normalized_image`).
- **Échelle** : `_fit_axis` ajuste échelle (±20 %) et décalage sur chaque axe à partir des traits du formulaire. L'ajustement est retenu seulement s'il retrouve nettement plus de traits d'ancrage.
- **Seuil d'encre** adaptatif : Otsu, borné entre 150 et 200.
- **Identification de la mise en page** :
  - la carte des traits est recadrée sur son contenu, si bien que des marges ajoutées ne font plus reconnaître une autre mise en page ;
  - le fond d'un scan assombri est ramené au blanc ;
  - l'écart avec la deuxième mise en page la plus proche est enregistré (`family_margin`, ≥ 0,19 sur le corpus). En dessous de 0,05, l'identification est déclarée peu sûre.
- **Fiabilité locale** (`anchor_residuals`, `box_geometry`) : pour chaque champ, on mesure l'écart entre les traits d'ancrage voisins attendus et réels (médiane des 4 plus proches). Un champ dont la géométrie n'est pas fiable donne `NON_VERIFIABLE`, jamais une anomalie ni une conformité.
- **Tableaux** (`_table_structure`) : lignes détectées, lignes anormalement hautes et encre hors des lignes. Un tableau douteux rend « à vérifier » les règles qui en dépendent (`rules._table_gate`).

### Règles (`rules.py`)
- **R01** : la lecture littérale (`12278*0`) et la convention (`12278*01`) sont évaluées toutes les deux et affichées. Une décision de la MSA enregistrée (`/api/conventions/{amb}/decision`) est appliquée et entre dans la clé d'analyse.
- **Caractères souvent confondus** (0/8, 1/7, 5/6…) : un avertissement est affiché quand deux valeurs ne diffèrent que par l'un d'eux. Le statut ne change pas.
- **Total incohérent dans le fichier lui-même** : une note est ajoutée quand le total du fichier diffère de la somme de ses lignes.

### Confidentialité (`privacy.py`, `db.py`, `api.py`)
- `mask_text` masque toute suite de 13 à 17 chiffres : 1ᵉʳ chiffre + • + 2 derniers.
- **Où** : liste des écarts, exports CSV, regroupements et revue, journal d'audit (masqué dès l'écriture).
- **Où le n° reste en clair** : seul l'écran du dossier, réservé au contrôle détaillé, l'affiche.

### Référentiel de validation humaine (`validation.py`, table `validations`)
- **Verdicts** : écart réel, faux positif, conforme confirmé, écart manqué, indéterminé. **Cause** : FP-GEO à FP-UI.
- **Saisie** : validateur et date, double revue, désaccords.
- **Métriques** : calculées sur les **seules validations humaines**. La revue assistée par IA (`data/revue_assistee_v3.json`) est chargée comme « à confirmer » et n'entre dans aucune mesure.

### Interface
- **Mode simple** par défaut (`CaseSimple.tsx`) : dossier → écart → preuve (agrandissement réel de la case via `/api/cases/{id}/crop`, ligne B2 surlignée) → décision.
- **Mode expert** : l'ancien poste de contrôle, inchangé (`?mode=expert` ou « Autres actions → Mode expert »).
- **Navigation** en trois espaces : Mes contrôles, Pilotage, Outils avancés (repliés).
- **Libellés métier** dans `labels.ts`.

### Corpus absent
L'archive du corpus n'est plus versionnée. Si elle manque, l'application démarre, affiche un bandeau et reste utilisable (imports).

## 7. Sécurité et confidentialité

- Traitement 100 % local ; aucune API externe ; OCR hors ligne.
- Extraction ZIP protégée (chemins absolus, `..`, liens symboliques, taille et nombre de fichiers) ; originaux en lecture seule ; empreintes SHA-256.
- Aucun mot de passe codé en dur : l'administrateur est créé au premier lancement ; mots de passe hachés (scrypt) ; sessions par jeton aléatoire stocké haché ; cookie HttpOnly SameSite=Strict.
- Comptes de démonstration : seulement sur demande explicite (« mode démonstration »), marqués `is_demo`, interdits avec `SENTINEL_MODE=production`.
- Imports et simulations : affectés à l'agent qui les dépose. Les autres agents n'y ont pas accès, et le contrôle est fait côté serveur sur la liste, le dossier, les fichiers, les rapports, les décisions, la réanalyse et la suppression.
- Récupération d'un compte : en local seulement, avec `python -m sentinel.cli reset-password <nom>`. Le mot de passe est saisi sans être affiché ni journalisé, et les sessions ouvertes sont fermées.
- Sauvegardes : `data/backups/` (empreinte et intégrité vérifiées). Une sauvegarde automatique est faite avant toute purge et avant toute restauration.
- Rôles : agent (dossiers non affectés ou affectés à lui), gestionnaire de caisse (affectation, priorité, clôture, supervision), administrateur technique (comptes, relance, purge), auditeur (lecture seule).
- Journal des actions sensibles. Le numéro d'assuré est masqué **côté serveur** dans les vues globales, les exports et le journal (3.0) ; il n'apparaît en clair que dans le dossier.
- Purge des métadonnées de session (décisions, corrections, affectations, journal) depuis « Rapports » (administrateur).

## 8. Tests

`python -m pytest -q tests` — 125 tests (version 3.0). `test_v3.py` couvre le réalignement démontré et son cas négatif, le garde-fou géométrique, le redressement, l'échelle, l'identification de la mise en page (marges, scan assombri), R01, le masquage et le référentiel de validation. Les tests de la version 2.0 restent en place : `test_v2_fiabilite.py` (politique d'incertitude, R20, cache, finances, corrections, sauvegarde, traitements, 825 entrées de zones) et `test_v2_api.py` (zones, droits des imports, décisions et montants confirmés, simulation, revue rapide, conventions, qualité, sauvegarde). Hors pytest : `scripts/e2e_zones.py` (navigateur réel, 825 entrées, mode expert), `scripts/e2e_parcours_simple.py` (parcours simple sur les 55 dossiers), `scripts/test_robustesse.py` (36 copies transformées), `scripts/diagnostic_anomalies.py`, `scripts/test_aveugle.py` (17 dossiers fabriqués), `scripts/snapshot_corpus.py` (non-régression des 1 210 résultats). Tests historiques :
- parseur sur les 55 fichiers (aucune perte de ligne, positions, zéros initiaux, montants, sous-types, lignes courtes, décalage de Facture2_06) ;
- moteur de règles (statuts, normalisations, rapprochement par occurrence, isolement des erreurs techniques) — données de test structurelles, jamais comptées dans les statistiques ;
- corpus (ZIP malveillant refusé, manifeste, appariement) ;
- intégration (fichier → extraction → règles → stockage, instantané de régression des résultats réels) ;
- API (authentification, rôles, correction OCR historisée et recalcul, décisions motivées, clôture réservée, rapports PDF/JSON, supervision, journal, comparaison d'images) ;
- reproductibilité de l'OCR (ré-extraction d'un bordereau comparée au cache).

Aucun taux de précision OCR n'est affirmé : le corpus ne contient pas de vérité terrain annotée. Les validations et corrections des agents constituent progressivement ce référentiel ; l'écran « Qualité et validation » en calcule l'exactitude avec ses effectifs.
