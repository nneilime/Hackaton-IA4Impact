# Rapport technique — iMSA Sentinel 2.0

Date : 10 octobre 2026. Version du moteur : 2.0.0. Version des règles : R22-2026.10-v2.

Ce rapport ne décrit que ce qui a été **vérifié** : par un test automatique, par le test d'interface en navigateur réel, ou par une relance mesurée sur le corpus. Ce qui n'a pas été fait, ou pas mesuré, figure dans la section 9.

---

## 1. Anomalies corrigées (priorité P0)

| # | Défaut constaté dans la version 1.2 | Correction | Vérification |
|---|---|---|---|
| P0-1 | `compare_read` : en cas d'égalité de votes entre deux lectures OCR contradictoires, la lecture qui concordait avec le TXT était retenue. Le contrôle devenait « conforme » alors que l'image ne permettait pas de trancher. | Une égalité entre lectures contradictoires donne **non vérifiable**, avec les deux lectures présentées. Une lecture divergente donne aussi non vérifiable. Une concordance qui repose sur une lecture minoritaire est signalée « incertaine ». | `test_v2_fiabilite.py` (égalité, divergence, lecture isolée) ; ancien test `test_rules.py` mis à jour ; test à l'aveugle sans Tesseract (R04 de Facture1_02, section 6) |
| P0-2 | R20 essayait les combinaisons de lectures candidates des zones 8, 12 et 13 jusqu'à trouver une somme juste. | R20 n'utilise que des valeurs fiables (lectures concordantes, majoritaires ou corrigées). Sinon, non vérifiable, avec les candidats en détail. | 4 tests R20 |
| P0-3 | Cache OCR indexé sur l'image seule : un changement du code d'extraction réutilisait d'anciennes lectures ; écriture non atomique ; aucune vérification d'intégrité. | Clé = image + empreinte du code d'extraction (fins de ligne normalisées) + profil des moteurs. Écriture atomique, empreinte du contenu, quarantaine d'un fichier corrompu puis recalcul, recalcul forcé (`cli extract --force`, bouton administrateur). | tests cache, fins de ligne, corruption ; les 55 extractions ont été recalculées avec le code final |
| P0-4 | Aucune clé d'analyse : rien ne garantissait qu'un résultat enregistré correspondait encore au TXT, à l'image, aux règles et au code actuels. | Clé d'analyse = empreintes JPG + TXT + versions du moteur et des règles + empreinte du code OCR + empreinte du code d'analyse. `sync_cases` traite les sources nouvelles, modifiées et disparues. | test de clé d'analyse ; la géométrie des zones est recalculée après une modification du code |
| P0-5 | Montants : le montant « confirmé » était calculé au niveau du dossier, avec un risque de double comptage entre total et lignes. | Décision effective **par règle** (la dernière décision non annulée). Par famille (prestations, honoraires), le montant retenu est le maximum entre l'écart de total et la somme des lignes, jamais leur somme. R20 est exclue. L'indu et les montants récupérés sont « non calculables ». | 6 tests finances, 1 test d'API |
| P0-6 | Imports : un dossier importé par un agent était visible par tous les agents (liste des imports, dossier, image, TXT). | Un dossier importé ou simulé est privé à son auteur, sauf affectation. Le contrôle est fait par le serveur sur la liste, le dossier, l'image, le TXT, le rapport, le traitement, les décisions, la réanalyse et la suppression. | `test_v2_api.py` : agent2 reçoit 403 sur chacun ; l'auditeur est en lecture seule |
| — | R12 plantait (TypeError) quand la lecture du montant était absente, car l'explication était construite trop tôt. | Explication calculée à la demande. | test d'API de correction |
| — | Une importation de l'utilisateur pouvait se glisser dans les tests (56 dossiers au lieu de 55). | Les tests utilisent des dossiers temporaires pour les imports et les sauvegardes. | suite complète |

## 2. Fichiers modifiés et créés

**Créés (backend)** : `zones.py` (couche des 15 zones), `ocrcache.py`, `finance.py`, `corrections.py` (liste blanche), `jobs.py` (traitements et verrous), `backup.py`, `triage.py` (regroupements d'alertes), `conventions.py` (AMB-01 à AMB-08).

**Modifiés (backend)** : `rules.py` (politique d'incertitude, R20, appariements), `pipeline.py`, `api.py`, `db.py` (migrations non destructives), `reports.py` (section des 15 zones et bordereau encadré), `compare.py` (comparaison par zone), `imports.py`, `cli.py`, `__init__.py`.

**Créés (interface)** : `components/ZoneInspector.tsx`, `pages/Review.tsx` (revue rapide), `pages/Quality.tsx`.

**Modifiés (interface)** : `ImageViewer.tsx` (encadrements, légende, halo), `CaseDesk.tsx`, `Supervision.tsx`, `Cases.tsx`, `Compare.tsx`, `Rules.tsx`, `Reports.tsx`, `Imports.tsx`, `Investigations.tsx`, `Overview.tsx`, `Auth.tsx`, `App.tsx`, `ui.tsx`, `Charts.tsx`, `styles.css`.

**Tests et scripts** : `test_v2_fiabilite.py`, `test_v2_api.py` (créés) ; `conftest.py`, `test_rules.py`, `test_ocr.py` (adaptés) ; `scripts/e2e_zones.py`, `scripts/snapshot_corpus.py` (créés) ; `scripts/test_aveugle.py`, `scripts/export_results_md.py` (adaptés).

**Documentation** : `README.md`, `docs/ZONES.md` (nouveau), `docs/GUIDES.md`, `docs/ARCHITECTURE.md`, `docs/TEST_AVEUGLE.md`, `docs/RESULTATS.md`, ce rapport, et le tutoriel PDF (nouveau chapitre « Contrôler les 15 zones du bordereau, pas à pas » avec captures réelles).

Au total : 48 fichiers source, 4 372 lignes ajoutées, 433 supprimées. L'application n'a pas été réécrite : la structure, les 22 règles et les écrans de la version 1.2 sont conservés.

## 3. Nouvelles fonctionnalités

1. **Cockpit des 15 zones** (onglet par défaut d'un dossier) :
   - les 15 zones encadrées sur le bordereau : vert conforme `#16A34A`, rouge anomalie `#DC2626`, gris non vérifiable `#6B7280`, gris clair en pointillés non applicable, orange erreur technique `#F59E0B` ;
   - encadrements transparents qui suivent le zoom, cliquables, avec infobulle, badge, icône et focus clavier ; bouton « Masquer / Afficher les encadrements » ; légende permanente ;
   - indicateurs « Contrôles également incertains » et « Résultats mixtes » ;
   - pastilles Z1 à Z15, navigation Précédente / Suivante, touches `[` `]` et Échap ; zone sélectionnée dans l'adresse (`?zone=Z8`) ;
   - fiche de zone : motif de la couleur, contrôles, lectures OCR, données TXT surlignées, lignes de tableau rapprochées (Z6, Z7, Z10), exécutants (Z9), cases de signature (Z11, Z14), assistance, traçabilité, historique.
2. **Géométrie indépendante de l'OCR**, calculée à partir des gabarits et du recalage. Une zone vide ou illisible reste localisée.
3. **Même couleur partout**, calculée une seule fois par le serveur : visionneuse, pastilles, fiche, liste des dossiers (bande des 15 zones), revue rapide, matrice de supervision, rapport PDF (tableau et bordereau encadré).
4. **Mise à jour en temps réel après une correction** : les 22 contrôles et les 15 zones sont recalculés, et le message indique les zones dont la couleur a changé. Une correction peut être annulée.
5. **Revue rapide** : une anomalie après l'autre, par priorité, avec la zone annoncée et des raccourcis clavier configurables.
6. **Regroupements d'alertes** (pistes de vérification au conditionnel), **qualité mesurée** (avec effectifs), **centre des conventions** (effet calculé d'un changement de convention).
7. **Supervision** : matrice des 15 zones avec liens filtrés, montants par niveau, activité et productivité (temps de revue actif mesuré).
8. **Comparaison de deux bordereaux zone par zone** (identique, différence purement graphique, différence documentaire).
9. **Simulation** : copie privée d'un dossier avec une valeur du TXT modifiée, analysée par le moteur réel et exclue des statistiques. L'original n'est jamais touché.
10. **Robustesse** :
    - traitements en arrière-plan idempotents et verrous par dossier ;
    - liste blanche des corrections ;
    - sauvegardes SQLite vérifiées (empreinte et intégrité), restauration avec sauvegarde de sécurité ;
    - purge précédée d'une sauvegarde ;
    - commandes `reset-password` et `create-admin` (saisie masquée) ;
    - `SENTINEL_MODE=production` interdit les comptes de démonstration.

## 4. Fonctionnalités conservées

Les 22 contrôles R01 à R22 et leurs explications, la vue « Contrôles » par catégorie A à F, le surlignage du TXT, les lectures OCR, les observations, les décisions et leur historique, l'assistant, l'import de nouveaux dossiers, la comparaison, les investigations, la supervision, les rapports PDF et JSON, l'export CSV, le journal d'audit, les rôles (agent, superviseur, auditeur, administrateur) et l'installation Windows (`INSTALLER.bat`, `LANCER.bat`). La base de la version 1.2 est migrée sans perte, uniquement par ajout de colonnes.

## 5. Tests exécutés

| Test | Portée |
|---|---|
| `pytest` (backend/tests) | règles, analyseur B2, OCR (reproductibilité), API, politique d'incertitude, cache, finances, corrections, zones, sauvegardes, traitements, droits |
| `scripts/snapshot_corpus.py` | non-régression des 1 210 résultats du corpus |
| `scripts/test_aveugle.py` | 17 dossiers fabriqués, absents du corpus, OCR recalculé ; avec deux moteurs puis avec RapidOCR seul |
| `scripts/e2e_zones.py` | navigateur réel (Chromium) : 55 dossiers × 15 zones = 825 entrées |

## 6. Résultats des tests

- **pytest : 109 tests réussis, 0 échec**, test OCR compris.
- **Test d'interface** : 825 / 825, 0 écart (détail ci-dessous).
- **Test à l'aveugle, deux moteurs OCR** : 17 / 17 exacts, comme en version 1.2.
- **Test à l'aveugle, RapidOCR seul** : 11 cas exacts et 6 cas avec au moins un contrôle à vérifier. Aucune fausse anomalie, aucune falsification manquée. Nouveauté de la version 2.0 : R04 devient non vérifiable sur les trois variantes de Facture1_02. RapidOCR y lit le numéro de facture deux fois « 260800002 » et deux fois « 26080002 ». La version 1.2 tranchait cette égalité en faveur du TXT ; c'est exactement le biais P0-1.

**Test d'interface `scripts/e2e_zones.py`, relance finale du 10/10/2026** (Chromium, application en marche, compte agent) : **825 entrées vérifiées sur 825, 0 écart**, sur 55 dossiers et les trois mises en page F1, F2 et F3, en 276 secondes. Pour chaque dossier :
- les 15 encadrements sont présents ;
- couleur affichée = statut du serveur = pastille ;
- les zones non applicables sont en pointillés ;
- aucune zone n'est verte sur un contrôle incertain ;
- chaque zone se sélectionne et se cadre au clic.

Sur un dossier par famille, l'alignement après zoom et la touche `]` ont été vérifiés. La correction de Z8 sur Facture1_04 fait passer Z13 au rouge, et son annulation la ramène au vert. Résultat détaillé : `data/e2e_zones.json`.

## 7. Évolution des résultats sur les 55 dossiers

| | Version 1.2 | Version 2.0 |
|---|---:|---:|
| Contrôles exécutés | 1 210 | 1 210 |
| Conformes | 994 | 994 |
| Anomalies | 75 | 75 |
| Non vérifiables | 1 | 1 |
| Non applicables | 140 | 140 |
| Dossiers avec au moins une anomalie | 50 | 50 |
| Dossiers sans écart | 5 | 5 |

**Aucun des 1 210 résultats n'a changé** : instantané avant / après les corrections P0, puis à nouveau après le recalcul complet de l'OCR (0 différence). Sur le corpus, aucune égalité contradictoire ne porte sur une valeur décisive : la politique P0-1 n'y change donc aucun résultat. Elle agit sur des images plus difficiles (section 6). Le détail règle par règle et dossier par dossier est dans `docs/RESULTATS.md`.

## 8. Couverture des 15 zones

- **825 entrées sur 825** (55 dossiers × 15 zones) disposent d'une géométrie contenue dans l'image, d'un statut, de leurs règles et d'une fiche. Test automatique `test_couverture_825_entrees` et test d'interface.
- Les trois mises en page (F1, F2, F3) sont couvertes.
- Statuts des zones sur le corpus :
  - aucune zone non vérifiable ni en erreur technique ;
  - Z9 et Z11 non applicables sur 15 dossiers, ceux qui n'ont pas d'actes exécutés ;
  - zones en anomalie : Z10 sur 11 dossiers, Z6 sur 10, Z8 et Z12 sur 7. Le tableau complet est dans `docs/RESULTATS.md`.
- La zone grise (non vérifiable) a été vérifiée sur un import réel : bordereau Facture1_02 dont le montant total a été effacé. Z13 est gris et R20 est non vérifiable (capture `14-zone-non-verifiable.png`).

## 9. Limites restantes

- **Pas d'éditeur de gabarits** : une 4ᵉ mise en page de bordereau n'est pas prise en charge. Elle est signalée « mise en page non reconnue » et les zones ne sont pas localisées.
- **Pas de correction des petites rotations** (au-delà du retournement à 180° et de la translation/échelle) : un scan penché de quelques degrés peut décaler les encadrements.
- **Productivité** : le temps de revue actif est mesuré. En revanche, aucune comparaison « revue manuelle contre revue assistée » n'a été mesurée, et aucun gain n'est donc annoncé.
- **Rappel des alertes** : il n'est calculable que sur les dossiers annotés par un agent. Avec peu d'annotations, il est affiché avec son effectif et la mention « effectif faible ».
- **Signatures** : seule la présence d'un élément est détectée, jamais l'authenticité. Une mention « par mandat » ou un cachet compte comme présent (convention AMB-05, à valider).
- **Conventions AMB-01 à AMB-08** : ce sont des propositions de l'équipe, non validées par la MSA. AMB-04 et AMB-05 ne sont pas simulables de façon fiable.
- **Sans Tesseract**, davantage de contrôles restent non vérifiables (section 6). C'est voulu : l'application préfère demander une vérification plutôt que deviner.
- Les montants « indu établi » et « récupéré » ne sont pas calculables à partir des documents fournis.

## 10. Recommandations

1. Faire valider par la MSA les huit conventions, en s'appuyant sur l'effet calculé affiché par le centre des conventions.
2. Installer Tesseract sur tous les postes (fait automatiquement par `INSTALLER.bat`).
3. En production :
   - définir `SENTINEL_MODE=production` ;
   - créer l'administrateur avec `create-admin` ;
   - planifier une sauvegarde quotidienne (`python -m sentinel.cli backup`) ;
   - ne jamais publier le corpus ni le cache OCR, qui contiennent des données de santé.
4. Constituer un jeu annoté (décisions d'agents sur quelques centaines de dossiers) pour mesurer le rappel et la précision de façon significative.
5. Pour de nouvelles mises en page, développer un éditeur de gabarits et un redressement des petites rotations avant tout déploiement élargi.
6. Mesurer la productivité par une expérience contrôlée (mêmes dossiers, avec et sans cockpit) avant d'annoncer un gain.
