# Données partagées BâtIA

Supabase contient les sources métier, les résultats et les décisions de l’équipe. Le navigateur consulte l’API FastAPI locale ; il utilise Supabase directement pour la connexion uniquement. Le serveur vérifie le compte et son rôle, puis utilise `batia_api` et les politiques RLS pendant chaque requête. La `DATABASE_URL` reste dans le `.env` serveur, ignoré par Git.

## Tables et relations

| CSV du kit | Table | Clé | Lignes initiales |
|---|---|---|---:|
| 01_residences.csv | residences | residence_id | 8 |
| 02_batiments.csv | batiments | batiment_id | 32 |
| 03_logements.csv | logements | logement_id | 1 100 |
| 04_equipements.csv | equipements | equipement_id | 4 217 |
| 05_demandes_locataires.csv | demandes | demande_id | 5 235 |
| 06_interventions.csv | interventions | intervention_id | 30 630 |
| 07_commandes.csv | commandes | commande_id | 5 253 |
| 08_plan_investissement.csv | investissements | operation_id | 29 |
| 09_prestataires.csv | prestataires | prestataire_id | 14 |
| 10_ref_codes_metiers.csv | metiers | code_metier | 10 |
| 10_ref_familles_equipements.csv | familles | famille | 14 |
| 10_ref_motifs_demandes.csv | motifs | motif + parties | 32 |
| 10_ref_seuils_dpe.csv | seuils_dpe | classe | 7 |
| xlsx_DICTIONNAIRE.csv | dictionnaire | table_source + colonne | 99 |
| xlsx_HYPOTHESES.csv | hypotheses | numero_ligne | 22 |
| xlsx_LISEZMOI.csv | documentation | numero_ligne | 32 |
| Catalogue extra du modèle, dédupliqué | prix_interventions | famille + type_intervention + type_panne | 87 |

Une résidence possède des bâtiments, qui possèdent des logements. Chaque équipement appartient à une résidence et à un bâtiment, avec un logement pour les équipements privatifs. Les interventions pointent vers l’équipement, le métier, le prestataire et éventuellement la demande liée. Les demandes conservent leur rattachement et leur couple `motif/parties`. Les commandes et investissements appartiennent à une résidence. Les clés étrangères contrôlent également la cohérence entre logement, bâtiment et résidence.

Les nombres, booléens et dates sont typés. `Avant 2018`, les intervalles DPE et les libellés restent du texte. `documentation` préserve les six cellules de chaque ligne, y compris la première ligne vide. Les descriptions du dictionnaire sont disponibles comme commentaires des colonnes.

`membres` associe les comptes Auth à un rôle. `imports` journalise les lots et leurs empreintes SHA-256. `calculs` conserve la date, la révision, la version des modèles et la progression ; `predictions` conserve un score et un seuil par équipement et horizon. `inspections`, `historique_inspections` et `signalements` partagent les décisions et les constats. `observations` contient les 42 extraits PDF, avec leurs liens et pages.

## Importer depuis l’app

Un administrateur ouvre **Données → Importer des CSV**, choisit un ou plusieurs fichiers, vérifie les compteurs par fichier et les erreurs avec leurs lignes, puis confirme. Les modèles téléchargeables fournissent les en-têtes attendus. Le nom du fichier n’importe pas : les colonnes identifient la table.

Les CSV métier peuvent être en UTF-8 avec ou sans BOM, séparés par virgules ou points-virgules. Toutes les colonnes de la table sont nécessaires ; les colonnes inconnues sont signalées. Les références peuvent être apportées dans le même lot, indépendamment de l’ordre des fichiers. Un identifiant répété bloque le lot. Les lignes absentes restent en base ; un identifiant existant est actualisé uniquement si ses valeurs changent.

Le lot est appliqué dans une transaction après contrôle des contraintes. Si la base a changé depuis l’aperçu, il faut vérifier à nouveau les fichiers. Un réimport identique conserve la révision et ne recalcule rien. Une modification des équipements, demandes, interventions ou prix lance les quatre inférences, sans réentraînement.

Les prix du catalogue du collègue sont répétés par équipement dans `extra/11_equipements_interventions_pannes_possibles_avec_prix.csv`. La base conserve un tarif par famille, type d’intervention et symptôme. Les CSV `extra` décrivent des possibilités et références dérivées, pas de nouveaux événements réels. Pour préparer un CSV de tarifs importable depuis l’app : `python -m scripts.import_price_catalog --output .cache/prix_interventions.csv`. Ses en-têtes sont `famille,type_intervention,type_panne,prix`. Les contradictions de prix et les montants négatifs sont refusés. La source et son empreinte sont journalisées à l’initialisation.

## Modèles et calculs

Les 27 variables utilisent la même fonction pour les commandes CSV, l’entraînement et l’inférence depuis la base. L’entraînement explicite exporte un instantané cohérent de Supabase puis construit les quatre tables mensuelles. Les métadonnées des artefacts enregistrent la révision et leurs empreintes déterminent la version du modèle.

```powershell
.\.venv\Scripts\python.exe -m scripts.train_from_database
.\.venv\Scripts\python.exe -m scripts.recalculate --as-of-date 2026-01-01
```

L’instantané inclut `prix_interventions.csv`, afin de reproduire aussi les coûts avec la CLI : `python -m scripts.predict_equipment --equipment-id EQP-00001 --as-of-date 2026-01-01 --data-dir training_snapshots/current --price-catalog training_snapshots/current/prix_interventions.csv`.

Les calculs se font par lot en arrière-plan. Les quatre modèles sont chargés en mémoire une fois par version. Le classement est publié en une transaction après réussite ; une interruption est marquée comme échec au redémarrage et peut être relancée. Si un import intervient pendant le calcul, celui-ci est marqué dépassé et un calcul de la nouvelle révision démarre.

L’app sélectionne 90 jours par défaut, puis 180, 365 ou 730 jours. Les rangs sont calculés avant les filtres. La date initiale est le 1er janvier 2026, sur l’historique antérieur, arrêté fin 2025. Les scores CatBoost sont **non calibrés** ; ils servent à prioriser les contrôles. Les équipements hors périmètre ou sans résultat restent non scorés. Les métriques concernent les données fictives du kit. Les liens demandes/interventions et la séparation chronologique restent ceux du modèle existant ; leur validité historique doit être revue avant un usage opérationnel réel.

## Comptes et démarrage local

La fiche équipement appelle `POST /api/predict` avec la session Auth, la référence et la date choisie. Chaque horizon ajoute les trois couples intervention/symptôme et les coûts du catalogue partagé. Les modèles de symptômes sont chargés une fois par version et calculés par famille ; les sorties sont aussi conservées dans `predictions.types_pannes`. Les estimations concernent la première panne éventuelle, utilisent des prix fictifs TTC et des scores non calibrés. Une famille ou un manifeste absent donne « indisponible » ; les anciens scores de risque restent utilisables. `train_from_database --types-only` entraîne les symptômes sur le nouvel instantané en conservant les poids des modèles de risque existants.

Utiliser Python **3.11** et deux terminaux depuis la racine :

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Renseigner .env à partir de .env.example, sans écraser les clés existantes.
.\.venv\Scripts\python.exe -m uvicorn scripts.api:app --host 127.0.0.1 --port 8000
```

```powershell
cd front
npm.cmd ci
npm.cmd run dev
```

Ouvrir http://127.0.0.1:5173. Les migrations versionnées dans `supabase/migrations` sont déjà appliquées au projet connecté. Pour une autre base, les appliquer dans l’ordre, puis initialiser une base vide avec `.\.venv\Scripts\python.exe -m scripts.bootstrap_data --apply` avant d’entraîner les modèles. Sans `--apply`, cette commande valide seulement le kit. La connexion MCP ne remplace pas la `DATABASE_URL` utilisée par l’API. Le compte PostgreSQL doit pouvoir prendre le rôle `batia_api` ; la seconde migration autorise le compte serveur `postgres` du projet.

Dans Supabase **Authentication → Users**, inviter/créer les membres, puis inscrire leur identifiant dans `public.membres` avec `role='membre'` ou `role='admin'`. Aucun compte ne reçoit automatiquement le rôle administrateur. `action.logement@gmail.com` a été ajouté comme premier administrateur sur confirmation de l’utilisateur. Les membres peuvent consulter, recalculer et gérer les inspections ; seuls les administrateurs importent.

La récupération du navigateur est explicite dans **Données → Récupérer les dossiers locaux**. L’aperçu compte les éléments nouveaux et ceux déjà présents. Les dossiers existants sont conservés, les conflits de dossiers ouverts bloquent la récupération, et la copie locale n’est jamais supprimée. Chaque modification de dossier vérifie sa version ; recharger après un conflit.

## Vérification

```powershell
$env:BATIA_DB_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd front
npm.cmd test
npm.cmd run build
npm.cmd run test:e2e
```

Les tests DB utilisent des transactions annulées, des identités temporaires et les rôles réels. Ils vérifient les effectifs et toutes les colonnes des 16 CSV, les variables et scores des quatre horizons, les réimports, corrections, ajouts, annulations, révisions et dossiers concurrents. Playwright utilise des réponses API/Auth simulées et les fixtures de test, sans toucher aux dossiers réels. Les PDF restent dans `front/public/sources`, les copies JSON sont uniquement dans `front/tests/fixtures`.

L’API et les artefacts restent locaux. Les environnements, instantanés, modèles, caches et sorties de tests sont exclus de Git. L’hébergement en ligne reste une étape ultérieure.

L’audit Supabase indique que la protection des mots de passe compromis n’est pas activée dans ce projet ; elle peut être configurée dans Auth selon [la documentation Supabase](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).

Validation locale : 33 tests Python réussis (dont PostgreSQL et routes réelles), 30 tests front et 7 parcours Playwright réussis ; TypeScript et build Vite réussis. Le build signale un bundle principal supérieur à 500 ko, sans bloquer la compilation. Les tests navigateur simulent Auth/API ; la connexion du compte réel se fait avec son mot de passe Supabase.
