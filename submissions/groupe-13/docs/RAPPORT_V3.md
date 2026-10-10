# Rapport de la version 3.0 — iMSA Sentinel

10 octobre 2026. Moteur 3.0.0, règles R22-2026.10-v3, extraction `extract-3.0`.

Ce rapport ne présente comme démontré que ce qui a été mesuré. Une valeur qui n'a pas pu être mesurée est notée **« À établir »** ou **« indisponible »**, jamais estimée.

Documents liés :
- [DIAGNOSTIC_V3.md](DIAGNOSTIC_V3.md) : la reproduction et la classification des fausses anomalies ;
- [REPONSE_CRITIQUES.md](REPONSE_CRITIQUES.md) : la réponse aux critiques ;
- [CONFORMITE_JURIDIQUE.md](CONFORMITE_JURIDIQUE.md) : la matrice juridique ;
- [PROTOCOLE_MESURES.md](PROTOCOLE_MESURES.md) : les tests utilisateurs, pas encore réalisés ;
- [GUIDE_1_PAGE.pdf](GUIDE_1_PAGE.pdf) : le guide utilisateur ;
- [ARCHITECTURE.md](ARCHITECTURE.md) : la documentation technique.

## 1. En bref

- **Fausses anomalies.** Le diagnostic des 76 résultats « en anomalie » ou « à vérifier » de la version 2.0 a trouvé **12 résultats faux, tous dans Facture2_06**. Leur cause unique était un caractère inséré dans le fichier B2. Cette cause est corrigée dans le parseur, par un réalignement **démontré** et signalé comme une interprétation. Les 64 autres résultats sont, selon une revue assistée, de vrais écarts entre les deux documents. **Cela reste à confirmer par un validateur humain.**
- **Robustesse.** Sur 36 copies transformées de bordereaux (rotations de -5° à +5°, marges, réduction, luminosité, compression, décalage), la version 3.0 ne produit **aucune fausse anomalie**. La version 2.0, testée sur les mêmes copies, en produit 30.
- **Simplicité.** Un parcours unique (dossier → écart → preuve → décision) s'affiche par défaut, et les détails techniques ne s'ouvrent qu'à la demande. Un test automatique a réalisé ce parcours sur les 55 dossiers. **Aucun test avec de vrais utilisateurs n'a encore eu lieu.**
- **Confidentialité.** Le n° d'assuré est masqué côté serveur dans les vues globales, les exports et le journal d'audit. Le corpus et le cache OCR sont retirés du dépôt Git à partir du commit de la version 3.0, mais **l'historique Git les contient encore**.

## 2. Comparaison version 2.0 / version 3.0

Toutes les valeurs ci-dessous ont été mesurées sur le corpus fourni (55 dossiers, 1 210 contrôles), avec le même poste.

| Indicateur | Version 2.0 | Version 3.0 | Source de la mesure |
|---|---:|---:|---|
| Contrôles en anomalie | 75 | 64 | `scripts/snapshot_corpus.py` |
| Contrôles non vérifiables | 1 | 0 | idem |
| Contrôles conformes / sans objet | 994 / 140 | 1 007 / 139 | idem |
| Statuts modifiés entre les deux versions | — | 13, tous dans Facture2_06 ; les 1 197 autres statuts sont identiques | idem, après recalcul complet de l'OCR |
| Dossiers avec au moins un écart | 50 | 50 | idem |
| Fausses anomalies identifiées par le diagnostic | 12 (11 anomalies + 1 non vérifiable) | 0 constatée | `DIAGNOSTIC_V3.md` (revue assistée, **à confirmer**) |
| Précision des alertes (validation humaine) | indisponible | **indisponible** | 0 validation humaine saisie |
| Rappel des alertes (validation humaine) | indisponible | **indisponible** | idem |
| Copies transformées : fausses anomalies | 30 | **0** | `scripts/test_robustesse.py`, 36 copies, 792 contrôles |
| Copies transformées : champs simples lus faux | 14 | 1 | idem, 432 champs (hors cellules de tableaux, voir 4.2) |
| Copies transformées : contrôles identiques à l'original | 476 / 792 | 753 / 792 (les 39 autres deviennent « à vérifier ») | idem |
| Copies transformées : mise en page mal identifiée | 9 / 36 | 0 / 36 | idem |
| Test à l'aveugle (17 dossiers fabriqués), deux moteurs | 17 / 17 | **17 / 17**, aucun contrôle à vérifier | `scripts/test_aveugle.py` |
| Test à l'aveugle, RapidOCR seul | 11 exacts, 0 fausse anomalie | 11 exacts, 6 avec au moins un contrôle à vérifier, 0 fausse anomalie, 0 falsification manquée (identique à la 2.0) | idem, `NO_TESS=1` |
| Clics pour ouvrir un dossier, trouver l'écart et décider | non mesuré | 3 | `scripts/e2e_parcours_simple.py` (parcours automatisé) |
| Clics pour retrouver un dossier traité | non mesuré | 4 | idem |
| Taux de réussite des tâches par des utilisateurs | À établir | **À établir** | protocole prêt, non réalisé |
| Temps de contrôle d'un dossier par un agent | À établir | **À établir** | idem |
| Gain de temps par rapport au contrôle manuel | À établir | **À établir** | protocole croisé prêt, non réalisé |
| Lecture OCR d'un bordereau (poste de test à 2 cœurs, deux moteurs) | non comparé | mise en page 1 : 11 à 12 s ; mise en page 2 : 33 à 36 s ; mise en page 3 : 7 à 9 s ; 17,5 min pour les 55 | journal `cli extract --force` |
| N° d'assuré dans les vues globales, exports et journal | en clair dans la liste des écarts et l'export CSV (valeurs et explications des écarts R05) | masqué côté serveur | code de l'API 2.0 ; `test_v3.py` |
| Tests automatiques | 109 | 125 | `pytest` |

La comparaison des copies transformées a été obtenue en lançant le **même** script sur le code de la version 2.0 (étiquette Git `v2.0-ref`) et sur celui de la version 3.0. Les deux versions ont lu les mêmes 36 copies.

## 3. Fausses anomalies : de la reproduction à la correction

Le détail est dans [DIAGNOSTIC_V3.md](DIAGNOSTIC_V3.md). En résumé :

| Cause (classification du cahier) | Constat | Correction |
|---|---|---|
| FP-B2, lecture du fichier | **Facture2_06** : blanc inséré en position 11, soit 11 fausses anomalies et 1 faux « non vérifiable » | Réalignement démontré par au moins 3 vérifications internes au fichier, sans le bordereau ; ligne d'origine conservée ; alerte « fichier mal formé » |
| FP-GEO, localisation | Écart maximal de 1,5 px sur le corpus ; aucun cas | Préventif : fiabilité géométrique par champ et par tableau (un champ mal localisé donne « à vérifier ») |
| FP-GEO, identification de la mise en page | Aucun cas sur le corpus. **Sur des copies transformées**, la version 2.0 se trompait de mise en page 9 fois sur 36 : 6 rotations, 2 copies avec marges (Facture1_04 et Facture3_01 prises pour la mise en page 2, d'où par exemple les fausses anomalies R17 et R20 de Facture3_01) et 1 scan assombri (Facture1_04 pris pour la mise en page 3) | Redressement avant identification ; carte des traits recadrée sur son contenu ; fond du papier ramené au blanc. Corpus inchangé (55 / 55 recalages identiques) ; 0 erreur sur les 36 copies |
| FP-OCR, lecture | 0 erreur parmi les 38 valeurs retenues | Avertissement « chiffres souvent confondus » (0/8…) sans changement de statut |
| FP-TABLE | Aucun cas | Contrôles structurels des tableaux |
| FP-CONVENTION | R01 : 52 résultats dépendent de la convention | Lecture littérale et convention affichées ; décision de la MSA enregistrable |
| FP-CACHE | Interface ancienne restée dans le cache du navigateur | Page jamais mise en cache (correctif publié en 2.0) |
| FP-PAIR, FP-NORM, FP-RULE, FP-UI | Aucun cas | — |

**Comparaison par cas.** Seul Facture2_06 change (13 contrôles) :

| Contrôle | 2.0 | 3.0 | Raison |
|---|---|---|---|
| R02 FINESS | Anomalie | **Anomalie** | écart réel : 490002037 sur le bordereau, 490002137 dans le fichier (positions 2-10, avant le caractère inséré) |
| R03 lot | Anomalie | Conforme | 351 = 351 après réalignement (lu 135 en 2.0) |
| R04 facture | Anomalie | Conforme | 261034506 (lu 126103450 en 2.0) |
| R05 assuré | Anomalie | Conforme | n° complet après réalignement |
| R07, R08, R13 | Anomalie | Conforme | actes GHS et FJA lus correctement (lus 9GHS, 9FJA en 2.0) |
| R09 | Non vérifiable | Conforme | référence GHS retrouvée |
| R12, R17 | Anomalie | Conforme | 1 013,22 € et 936,68 € (lus 900 101,32 € et 200 093,66 € en 2.0) |
| R14, R15, R19 | Anomalie | Conforme | actes de type 4 et codes CCAM lus aux bonnes positions |
| R16 | Sans objet | Conforme | les NumeroGH deviennent lisibles |

**Ce qui n'a pas été fait, volontairement** :
- aucune règle n'a été assouplie ;
- aucune valeur du TXT n'a été recopiée dans une lecture du bordereau ;
- les 52 résultats R01 ne sont pas changés en silence : ils attendent une décision de la MSA, enregistrable dans l'application.

## 4. Tests et preuves

### 4.1 Matrice de confusion

**Indisponible.** Le référentiel de validation humaine est en place (écran « Qualité et validation », onglet « Référentiel ») mais il ne contient encore **aucune validation humaine**. Précision et rappel ne sont calculés que sur des validations humaines ; ils ne sont donc pas affichés, et jamais remplacés par 100 %.

Pour information seulement, **hors métrique** : la revue assistée par IA du diagnostic classe les 76 résultats ainsi :
- 64 écarts réels ;
- 12 résultats de la version 2.0 qui sont en réalité conformes (Facture2_06).

Elle est chargée dans l'application comme « revue assistée, à confirmer ». Elle ne mesure pas les écarts manqués : aucun échantillon de dossiers conformes n'a été annoté.

### 4.2 Recalage et lecture sur copies transformées

36 copies de Facture1_04, Facture2_01 et Facture3_01 (une par mise en page) ont été produites, puis relues sans cache et comparées à la lecture de l'original. Les originaux ne sont jamais modifiés.

**Version 3.0**

| Transformation (3 bordereaux) | Champs faux | Champs à vérifier | Contrôles devenus « à vérifier » | Fausses anomalies | Mise en page erronée |
|---|---:|---:|---:|---:|---:|
| rotation -5° | 0 | 2 | 1 | 0 | 0 |
| rotation -3° | 0 | 1 | 3 | 0 | 0 |
| rotation -1° | 0 | 1 | 4 | 0 | 0 |
| rotation +1° | 0 | 1 | 2 | 0 | 0 |
| rotation +3° | 0 | 3 | 2 | 0 | 0 |
| rotation +5° | 0 | 5 | 7 | 0 | 0 |
| plus sombre (-40) | 0 | 0 | 0 | 0 | 0 |
| plus clair (+30) | 0 | 2 | 2 | 0 | 0 |
| JPEG qualité 40 | 0 | 2 | 3 | 0 | 0 |
| réduit à 85 % | 1 | 1 | 9 | 0 | 0 |
| marges blanches ajoutées | 0 | 1 | 4 | 0 | 0 |
| décalé de 12 px / 9 px | 0 | 0 | 2 | 0 | 0 |

**Version 2.0, mêmes copies (référence)**

| Transformation (3 bordereaux) | Champs faux | Champs à vérifier | Contrôles devenus « à vérifier » | Fausses anomalies | Mise en page erronée |
|---|---:|---:|---:|---:|---:|
| rotation -5° | 0 | 32 | 42 | 4 (Facture1_04 R08,R19; Facture2_01 R19; Facture3_01 R19) | 2 |
| rotation -3° | 2 | 27 | 39 | 5 (Facture1_04 R03,R19; Facture2_01 R11; Facture3_01 R13,R19) | 1 |
| rotation -1° | 2 | 14 | 26 | 2 (Facture2_01 R08; Facture3_01 R13) | 0 |
| rotation +1° | 4 | 14 | 25 | 2 (Facture1_04 R17; Facture3_01 R11) | 0 |
| rotation +3° | 2 | 31 | 35 | 7 (Facture1_04 R13,R19; Facture2_01 R13,R19; Facture3_01 R12,R13,R19) | 2 |
| rotation +5° | 1 | 32 | 36 | 6 (Facture1_04 R19; Facture2_01 R11,R19; Facture3_01 R03,R13,R19) | 1 |
| plus sombre (-40) | 0 | 1 | 0 | 0 | 1 |
| plus clair (+30) | 0 | 2 | 2 | 0 | 0 |
| JPEG qualité 40 | 0 | 2 | 3 | 0 | 0 |
| réduit à 85 % | 1 | 1 | 9 | 0 | 0 |
| marges blanches ajoutées | 2 | 15 | 21 | 4 (Facture2_01 R08,R13; Facture3_01 R17,R20) | 2 |
| décalé de 12 px / 9 px | 0 | 0 | 2 | 0 | 0 |

En version 2.0, les fausses anomalies viennent surtout des rotations, qui n'étaient pas redressées : des lignes de tableau étaient mal découpées, d'où des prestations « absentes » (R08, R11, R13, R19). Les marges ajoutées produisaient aussi des erreurs d'identification de la mise en page.

Lecture :
- **0 fausse anomalie, 0 mise en page mal identifiée.** Quand la transformation crée un doute, le contrôle devient « à vérifier » (39 cas sur 792) : l'outil reconnaît son doute au lieu de conclure.
- **1 champ simple lu faux.** Sur Facture3_01 réduit à 85 %, le sous-total 1 est lu 398,31 au lieu de 398,30. Aucun contrôle n'en dépend directement, et aucun statut ne change.
- **Cellules de tableaux.** Elles ne sont pas comptées dans les 432 champs. Des codes restent mal lus dans 6 copies :
  - Facture1_04 assombri : ligne parasite « M » ;
  - Facture1_04 et Facture2_01 réduits à 85 % : GHS → PHSI, PAS → PASI, FJ → IFJ ;
  - Facture2_01 JPEG 40 : FJ → IFJ, JCPD001 → UCPD001 ;
  - Facture2_01 à -5° et -3° : YYYY405 → YY405.

  Aucune n'a produit de fausse anomalie : la règle concernée devient « à vérifier ».
- **Un vrai écart devient « à vérifier ».** Sur Facture1_04 tourné de +1°, l'écart R12 de 0,01 € passe en « à vérifier » : il n'est pas perdu, mais il n'est plus affirmé.
- **Version 2.0** : en plus des 30 fausses anomalies, 46 contrôles conformes y devenaient silencieusement « sans objet » sur les copies (tableaux non lus).
- **Limites** :
  - seules 3 images sources sont transformées, et les transformations sont synthétiques, pas de vrais scans ;
  - la perspective (photo prise de biais) n'est pas traitée ;
  - l'écart de similarité entre la bonne mise en page et la deuxième plus proche peut être faible sur une copie avec marges (0,025 pour Facture3_01). En dessous de 0,05, l'identification est déclarée « peu sûre » dans l'extraction.

### 4.3 Interface

**Test automatique en navigateur réel** (`scripts/e2e_parcours_simple.py`, compte gestionnaire, mode simple) :
- sur les 55 dossiers, le résultat annoncé correspond aux chiffres du serveur ;
- les 64 écarts s'ouvrent, avec les deux valeurs et l'agrandissement réel ;
- les zones conformes sont discrètes ; aucune erreur.

Parcours chronométré des cinq tâches :

| Tâche | Clics | Temps (automate) |
|---|---:|---:|
| Ouvrir un dossier à traiter | 1 | 0,15 s |
| Trouver l'écart | 1 | 0,07 s |
| Comparer les deux valeurs | 0 (affichées ensemble) | 0,01 s |
| Enregistrer une décision | 1 | 0,85 s |
| Retrouver le dossier traité | 4 | 0,74 s |

Ces temps sont ceux d'un automate. Ils prouvent que le parcours est réalisable et donnent son coût minimal en clics. **Ils ne mesurent ni la compréhension ni la durée pour un humain.** Le test avec 5 à 8 utilisateurs ([PROTOCOLE_MESURES.md](PROTOCOLE_MESURES.md)) reste à faire.

**Mode expert** : `scripts/e2e_zones.py` vérifie les 825 zones (55 × 15) dans le navigateur, avec la couleur affichée égale au statut du serveur. Résultat avec le code final : **825 entrées sur 825, 0 erreur**.

### 4.4 Sécurité et confidentialité

| Vérification | Résultat | Preuve |
|---|---|---|
| N° d'assuré dans la liste des écarts, le CSV, les regroupements et le journal d'audit | masqué (ex. `2••••••••••06`) | `test_vues_globales_exports_et_journal_sans_numero_d_assure_complet` |
| Journal d'audit | masqué **dès l'écriture**, si bien qu'un ancien export ne peut pas le révéler | `db.audit`, même test |
| Document de résultats publiable (`RESULTATS.md`) | n° d'assuré masqués | `scripts/export_results_md.py` |
| Corpus absent | l'application démarre, affiche un bandeau et reste utilisable | `test_corpus_absent_signale_sans_bloquer` |
| Mots de passe | aucun dans le code ni dans les journaux ; scrypt | tests 2.0 conservés |
| Corpus et cache OCR | exclus de Git, retirés de l'index | `.gitignore`, `git rm --cached` |

**Reste à traiter** :
- l'historique Git (section 7) ;
- les captures d'écran de la documentation montrent des bordereaux du corpus, sur lesquels le n° d'assuré est imprimé. Elles devront être floutées avant toute publication hors du défi.
- quelques n° d'assuré du corpus figurent dans les tests automatiques (`test_parser.py`, `test_v3.py`), car ces tests vérifient justement la lecture et le masquage. Ils pourront être remplacés par des dossiers fabriqués si le dépôt devient public.
- l'illustration d'une ligne B2 dans le tutoriel PDF est désormais masquée.

### 4.5 Régressions évitées

| Changement envisagé | Effet constaté | Décision |
|---|---|---|
| Recadrer l'image sur le cadre du formulaire avant d'identifier la mise en page | Recalage modifié sur les 20 bordereaux de la mise en page 2 | Abandonné |
| Recadrer la carte des traits sur son contenu | Corrigeait les marges, mais un scan assombri était alors pris pour une autre mise en page | Complété par la normalisation du fond. Contrôle final : 55 / 55 recalages identiques et 36 / 36 mises en page exactes |
| Réalignement B2 sans condition sur les identifiants | Un fichier normal pouvait être « réaligné » (test négatif en échec) | Condition impérative ajoutée : identifiants entièrement numériques |
| Test `DEBUT_FACTURE_REPETE` sur Facture2_06 | L'observation venait du décalage lui-même | Test réécrit, avec la justification documentée dans le test |
| Valeur « Différence » affichée pour une prestation absente | Laissait croire à un écart de montant | Affichage de « Montant concerné » |

Non-régression : `snapshot_corpus.py` compare les statuts des 1 210 contrôles un par un. En dehors de Facture2_06, aucun ne change.

## 5. Métriques, par niveau

Les niveaux ne sont jamais additionnés ni confondus.

| Niveau | Mesure | Valeur sur le corpus | Statut |
|---|---|---|---|
| Technique (lecture) | Écart des traits d'ancrage | ≤ 1,5 px sur les 55 images | mesuré |
| Technique (lecture) | Exactitude de l'OCR | indisponible | nécessite des lectures validées par un humain |
| Contrôle (alertes) | Anomalies / non vérifiables | 64 / 0 | mesuré (sortie du moteur) |
| Contrôle (alertes) | Précision, rappel | indisponible | 0 validation humaine |
| Financier | Montant facturé (TXT) | 62 685,22 € | mesuré |
| Financier | Montant en anomalie, sans double comptage | 1 834,80 € | mesuré, **non confirmé** |
| Financier | dont écarts sur les totaux | 0,12 € | mesuré (12 écarts de 0,01 €) |
| Financier | dont lignes présentes d'un seul côté | 1 834,68 € | mesuré |
| Financier | Montant facturé des dossiers en alerte | 58 142,22 € | ce n'est **pas** un indu |
| Financier | Écarts confirmés par un agent | 0,00 € | aucune décision réelle (seule une décision du test automatique, annulée) |
| Financier | Indu établi, montant récupéré | non calculable | hors application |
| Productivité | Temps de lecture OCR | médiane 11,6 s par bordereau | mesuré |
| Productivité | Temps de revue actif, délais | indisponible | aucune revue réelle. Le seul délai enregistré (897 s) provient du test automatique et n'a pas de valeur de mesure |
| Productivité | Gain par rapport au manuel | À établir | protocole croisé prêt |

## 6. Architecture d'intégration proposée (non réalisée)

Le POC reste un poste local (FastAPI, SQLite, React). Aucune connexion à la MSA, à la CNAM ni à une base de droits n'a été simulée. Pour un déploiement, l'architecture cible proposée, **à valider par la DSI et le RSSI**, serait la suivante :

| Brique | POC 3.0 | Cible proposée |
|---|---|---|
| Entrée des dossiers | dépôt de fichiers, archive du défi | flux de l'outil de numérisation et des factures B2 de l'organisme, via un connecteur fourni par la DSI |
| Base | SQLite locale | base relationnelle serveur (PostgreSQL par exemple), chiffrée au repos, sauvegardée |
| Traitement OCR | dans le processus de l'API | file de travaux et travailleurs dédiés, à dimensionner sur mesure |
| Authentification | comptes locaux, scrypt | annuaire de l'organisme (SSO), habilitations par rôle |
| Journalisation | table `audit`, NIR masqué | journal centralisé, protégé contre l'altération, durée de conservation définie |
| Hébergement | poste de l'utilisateur | infrastructure interne ou hébergeur certifié HDS selon la décision juridique |
| Gabarits | 3 mises en page déclaratives | éditeur de gabarits validé par le métier, avec un jeu de test par mise en page |

## 7. Historique Git : procédure proposée (non exécutée)

`.gitignore` et `git rm --cached` empêchent les **prochains** commits de contenir le corpus et le cache OCR. En revanche, **les commits déjà poussés les contiennent toujours.** Les retirer suppose de réécrire l'historique, ce qui change tous les identifiants de commit et oblige chaque copie du dépôt à être reclonée. Rien n'a donc été fait sans décision de l'équipe.

Procédure, **après validation et après sauvegarde** :

```bash
# 1. sauvegarde complète du dépôt, historique compris
git clone --mirror <url-du-depot> sauvegarde-sentinel.git

# 2. réécriture de l'historique sur une copie miroir (outil git-filter-repo)
git clone --mirror <url-du-depot> nettoyage.git && cd nettoyage.git
git filter-repo --invert-paths --path data/General-main.zip --path data/cache/ --path data/e2e_zones.json

# 3. vérification : aucune trace des fichiers retirés
git log --all --oneline -- data/General-main.zip data/cache    # doit être vide

# 4. publication (forcée), puis chaque membre reclone le dépôt
git push --force --mirror <url-du-depot>
```

Sur GitHub, des copies peuvent subsister : forks, caches, demandes de fusion. Si le dépôt a été public, il faut le considérer comme diffusé et en informer le DPO.

## 8. Limites

- **Aucune validation humaine** des résultats. La revue du diagnostic a été faite avec un assistant IA.
- **Aucun test avec des utilisateurs** : le caractère « simple » de l'interface n'est pas démontré, seulement visé.
- **Aucun gain de productivité** n'est mesuré ni annoncé.
- **Robustesse** : testée sur 3 images sources et des transformations synthétiques, sans perspective ni vrais scans dégradés.
- **Réalignement B2** : un seul type de défaut est traité, le blanc unique inséré au même index.
- **Identification de la mise en page** : elle repose sur les 3 mises en page du corpus. Une nouvelle mise en page n'est pas reconnue.
- **Cadre juridique** : aucune certification ni conformité n'est revendiquée (voir la matrice).
- **Production** : l'application n'est **pas prête pour une production institutionnelle**. Il manque la validation métier des conventions, la validation humaine des résultats, les tests utilisateurs, l'AIPD et l'homologation de sécurité.
