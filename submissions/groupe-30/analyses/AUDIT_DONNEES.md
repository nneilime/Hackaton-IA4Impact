# Audit des données BatIA

Périmètre : prévention des pannes. Résultats calculés localement par `scripts/audit_sources.py`. Les anomalies sont documentées sans modification des sources.

## Intégrité et couverture

| Table | Lignes | Colonnes |
| --- | ---: | ---: |
| 01_residences | 8 | 16 |
| 02_batiments | 32 | 5 |
| 03_logements | 1 100 | 16 |
| 04_equipements | 4 217 | 17 |
| 05_demandes_locataires | 5 235 | 15 |
| 06_interventions | 30 630 | 14 |
| 07_commandes | 5 253 | 13 |
| 08_plan_investissement | 29 | 12 |
| 09_prestataires | 14 | 4 |
| 10_ref_codes_metiers | 10 | 2 |
| 10_ref_familles_equipements | 14 | 10 |
| 10_ref_motifs_demandes | 32 | 3 |
| 10_ref_seuils_dpe | 7 | 3 |

- Les clés primaires vérifiées sont uniques et renseignées. Aucun identifiant non vide ne pointe vers une référence absente dans les contrôles réalisés.
- Les localisations redondantes vérifiées entre logements, bâtiments, équipements, interventions et demandes concordent.
- Les 13 CSV ont les mêmes en-têtes, nombres de lignes et valeurs que les onglets Excel correspondants après normalisation numérique.
- La clé du référentiel des motifs est le couple `(motif, parties)`. Le motif VMC apparaît pour les parties privatives et communes.
- Les 24 empreintes SHA-256 des sources sont inchangées. Le fichier temporaire Excel préexistant est exclu.

## Pannes observées dans notre périmètre

| Janvier-septembre | Arrêts totaux (événements) | Équipements positifs | Prévalence | Positifs omis par la borne du notebook |
| --- | ---: | ---: | ---: | ---: |
| 2018 | 39 | 34 | 2.6% | 1 |
| 2019 | 69 | 57 | 4.4% | 0 |
| 2020 | 64 | 54 | 4.2% | 1 |
| 2021 | 64 | 52 | 4.0% | 1 |
| 2022 | 76 | 60 | 4.7% | 0 |
| 2023 | 64 | 59 | 4.6% | 0 |
| 2024 | 75 | 64 | 5.0% | 1 |
| 2025 | 86 | 76 | 5.9% | 0 |

La cible est binaire par équipement. Les événements répétés ne sont pas des équipements supplémentaires. Les très petits effectifs par famille limitent l'interprétation.

| Famille | Équipements | Positifs janvier-septembre 2025 |
| --- | ---: | ---: |
| ascenseur | 15 | 1 |
| ballon_ecs_electrique | 230 | 10 |
| ballon_thermodynamique | 140 | 10 |
| caisson_vmc | 23 | 2 |
| chaudiere_gaz_individuelle | 400 | 29 |
| chaufferie_collective | 5 | 2 |
| convecteurs_electriques | 230 | 8 |
| panneaux_rayonnants | 140 | 0 |
| pompe_a_chaleur | 100 | 14 |
| production_ecs_solaire | 2 | 0 |

## Audit temporel du notebook

| Référence au 31/12 | Âges négatifs | Passages du dernier jour omis | Appareils dont le cumul actuel de remplacements inclut le futur | Dépannages de l'ancien appareil dans le compteur 12 mois |
| --- | ---: | ---: | ---: | ---: |
| 2017 | 17 | 0 | 459 | 0 |
| 2018 | 8 | 5 | 430 | 63 |
| 2019 | 2 | 6 | 374 | 103 |
| 2020 | 1 | 6 | 322 | 107 |
| 2021 | 0 | 3 | 266 | 117 |
| 2022 | 0 | 2 | 204 | 119 |
| 2023 | 0 | 5 | 144 | 90 |
| 2024 | 0 | 9 | 79 | 137 |
| 2025 | 0 | 6 | 0 | 136 |

L'année 2017 sert uniquement à vérifier la reconstruction avant le début des interventions. Les âges négatifs des validations anciennes montrent que la pose immédiatement précédente ne suffit pas à retrouver tous les premiers appareils.

Le notebook ne se sert pas du cumul actuel de remplacements dans ses deux variables : le risque de fuite apparaît si l'on ajoute directement ce champ à un modèle. Son compteur de dépannages mélange en revanche effectivement les cycles de vie.

135 DPE ont été établis après fin 2024. Les 347 valeurs `Avant 2018` des entrées d'occupants sont des valeurs textuelles prévues par le dictionnaire, pas des dates corrompues. Une demande ouverte à fin 2023 possède une clôture future. Les réouvertures et échanges ne sont pas horodatés individuellement.

## Demandes et textes

- 368 dépannages sur 9955 portent une demande liée (3.7%), pour 362 demandes distinctes.
- 370 logements ont plusieurs appareils du périmètre de prédiction. Une jointure par logement ne suffit pas à attribuer un symptôme.
- Les 968 demandes indiquées comme communes possèdent toutes un logement renseigné. Leur portée doit aussi utiliser `parties` et le motif.
- 18 formulations non vides distinctes dans les commentaires des techniciens. La diversité est celle de modèles de simulation.

## Remplacements et rapports PDF

866 remplacements concernent 846 identifiants. 20 identifiants ont plusieurs remplacements, dont 12 dans le périmètre de prédiction. Pour tous les emplacements remplacés, la pose actuelle correspond au jour du dernier remplacement.

Les rapports couvrent six codes et les équipements sous contrat. Les appareils hors contrat partageant `MUPPR` doivent être exclus pour réconcilier les tableaux.

| Rapport | Dépannages réconciliés | Arrêts totaux | Alertes listées | Alertes hors soumission | Appareils alertés remplacés dans les neuf mois résumés |
| --- | ---: | ---: | ---: | ---: | ---: |
| T2 2025 | 225 | 39 | 14 | 1 | 4 |
| T3 2025 | 223 | 32 | 14 | 0 | 8 |
| T4 2025 | 276 | 25 | 14 | 0 | 5 |

Les totaux correspondent aux PDF. L'absence d'un appareil dans les observations ne constitue pas un constat de bon fonctionnement. La mention dans un rapport ne précise pas à elle seule la date du symptôme ou le cycle de vie concerné.

## Baseline d'âge et limites de validation

Âge relatif seul, au 31/12/2024, cible du notebook en janvier-septembre 2025 : **AUC 0.777181**, **16/129** équipements positifs dans le top 10 %, précision **12.4%**, rappel **21.1%**, lift **2.10**.

Après inclusion des journées complètes et normalisation des dates de pose : AUC **0.777181**, mêmes 16 positifs dans les 129 premiers appareils. Ce contrôle ne corrige pas toute la reconstruction des validations anciennes.

Convention de cet audit : top 10 % arrondi au supérieur, soit 129 appareils, et ex aequo départagés par identifiant. Le jury peut employer une autre convention. L'AUC a été vérifiée par deux méthodes indépendantes, comparaisons de paires et rangs.

La baseline logistique n'a pas été exécutée, car scikit-learn est absent du runtime. Aucun modèle final, aucune prédiction 2026 et aucun CSV de soumission ne sont produits dans cette phase de cadrage.

## Sources et reproductibilité

- `audit_resultats.json` : contrôles et résultats détaillés, dont les identifiants concernés.
- `profil_donnees.json` : colonnes, catégories, valeurs manquantes, exemples et bornes de dates.
- `profil_classeur.json` : contenu documentaire et structure du classeur.
- `inventaire_sources.json` : fichiers et empreintes SHA-256.
- [Consignes extraites](sources_lisibles/LISEZ-MOI_BatIA.md), [dictionnaire](sources_lisibles/xlsx_DICTIONNAIRE.csv), [hypothèses](sources_lisibles/xlsx_HYPOTHESES.csv) et [notebook](sources_lisibles/BatIA_notebook_demarrage.md).
- Rapports [T2](sources_lisibles/Rapport_activite_T2_2025_FICTIF.md), [T3](sources_lisibles/Rapport_activite_T3_2025_FICTIF.md), [T4](sources_lisibles/Rapport_activite_T4_2025_FICTIF.md).

Les contrôles prouvent les points décrits ici. Ils ne constituent pas une certification de toutes les valeurs simulées ni une validation de performance sur données réelles.
