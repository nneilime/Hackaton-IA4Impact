# Test à l'aveugle : l'application ne « connaît » pas les réponses

Question légitime : les 22 contrôles ont-ils appris par cœur les 55 dossiers fournis ? Non. Rien n'est entraîné sur le corpus et aucun résultat n'est stocké par dossier. Chaque dépôt est relu et recontrôlé :

1. le fichier TXT est relu caractère par caractère aux positions du cahier des charges ;
2. le bordereau est relu par OCR (le cache n'est utilisé que si l'image est **identique octet pour octet**, empreinte SHA-256 ; une image modifiée, même d'un pixel, est relue entièrement) ;
3. les 22 règles comparent ces deux lectures.

Ce qui vient du corpus, c'est la **connaissance du formulaire** : l'emplacement des 15 zones pour les trois mises en page de bordereau (comme un agent qui sait où regarder sur un CERFA). Un bordereau d'une autre mise en page est signalé « non reconnu » au lieu d'être contrôlé à l'aveugle.

## Le test

`scripts/test_aveugle.py` fabrique 17 dossiers qui n'existent pas dans le corpus, les analyse sans cache et compare au résultat attendu :

- des **contrôles négatifs** : documents authentiques transformés (agrandis, recompressés, décalés, retournés, floutés), qui ne doivent produire **aucune** anomalie ;
- des **bordereaux falsifiés** : valeurs réécrites dans une autre police, signatures et cachets effacés ;
- des **factures TXT modifiées** autrement que dans les données fournies : code CCAM, n° d'assuré, prestation supprimée, total, code d'acte inventé (« DIA »), n° GHS.

| Cas | Dossier fabriqué | Attendu | Deux moteurs OCR | RapidOCR seul |
|---|---|---|---|---|
| N1 | Facture2_01 agrandie de 12 % et recompressée (JPEG 70) | aucune | OK | OK, R18 à vérifier |
| N2 | Facture1_02 décalée de 14 px / 11 px | aucune | OK | OK, R04 et R19 à vérifier |
| N3 | Facture3_13 scannée à l'envers (180°) | aucune | OK | OK |
| N4 | Facture3_13 floue + JPEG qualité 60 | aucune | OK | OK |
| I1 | Facture1_02 : zone 8 réécrite 818,97 → 828,97 | R12, R20 | OK | OK, R04 et R19 à vérifier |
| I2 | Facture2_01 : lot réécrit 351 → 357 | R03 | OK | OK |
| I3 | Facture1_02 : n° facture réécrit 260800002 → 260800092 | R04 | OK | OK, R19 à vérifier |
| I4 | Facture3_01 : montant total réécrit 448.78 → 498.78 | R20 | OK | OK |
| I5 | Facture3_01 : signature du directeur effacée | R21 | OK | OK |
| I6 | Facture2_01 : cachets des cases 1 et 2 (zone 11) effacés | R18 | OK | OK |
| I7 | Facture2_01 : acte APC réécrit « ACO » en zone 10 | R14, R19 | OK | OK |
| T1 | Facture2_01.txt : code CCAM YYYY405 → YYYY406 | R15, R19 | OK | OK |
| T2 | Facture3_01.txt : n° d'assuré modifié | R05 | OK | OK |
| T3 | Facture1_02.txt : prestation EMI supprimée | R11 | OK | OK, R04 et R19 à vérifier |
| T4 | Facture2_01.txt : TotalHonoraires 936,68 → 950,00 | R17 | OK | OK |
| T5 | Facture2_01.txt : FJA remplacé par « DIA » | R08, R13 | OK | R08 trouvé, R13 à vérifier |
| T6 | Facture2_01.txt : NumeroGH d'un 4-S → 4199 | R16 | OK | OK |

**Avec les deux moteurs OCR (configuration recommandée) : 17 cas sur 17 exacts** — toutes les falsifications détectées, aucune fausse alerte sur les documents authentiques transformés, aucun contrôle laissé non vérifiable.

**Avec RapidOCR seul** (PC sans Tesseract) : aucune fausse anomalie, toutes les falsifications détectées (pour T5, l'une des deux règles reste à vérifier) ; 6 cas demandent en plus une vérification humaine (statut « non vérifiable »), principalement la lecture du code d'acte « K » d'une seule lettre.

**Version 2.0 — résultats relancés le 10/10/2026 avec le code final, OCR recalculé sans cache :**
- deux moteurs : **17 / 17 exacts**, identique à la version 1.2 ;
- RapidOCR seul : 11 cas exacts, 6 cas avec au moins un contrôle à vérifier, **0 fausse anomalie**, 0 falsification manquée.

La seule différence avec la version 1.2 est **R04 sur les trois variantes de Facture1_02 (N2, I1, T3)**. Sans Tesseract, RapidOCR lit le n° de facture deux fois « 260800002 » et deux fois « 26080002 », soit une égalité parfaite. La version 1.2 retenait alors la lecture qui concordait avec le TXT ; c'est précisément le biais corrigé en priorité P0 par la version 2.0. Une égalité entre lectures contradictoires donne désormais « non vérifiable », et les deux lectures sont présentées à l'agent. Avec les deux moteurs, Tesseract départage, et R04 est conforme. C'est pourquoi `INSTALLER.bat` installe désormais Tesseract automatiquement (via winget), et l'application indique en bas du menu les moteurs OCR actifs.

**Version 3.0 — résultats relancés le 10/10/2026 avec le code final, OCR recalculé sans cache :**
- deux moteurs : **17 / 17 exacts**, sans aucun contrôle laissé à vérifier ;
- RapidOCR seul : 11 cas exacts, 6 cas avec au moins un contrôle à vérifier (les mêmes qu'en 2.0), **0 fausse anomalie**, 0 falsification manquée.

Les corrections de la version 3.0 (redressement, échelle, identification de la mise en page, garde-fous géométriques) n'ont donc dégradé aucun cas du test à l'aveugle.

## Ce que le test a permis de corriger

Le premier passage n'était pas parfait ; les défauts trouvés ont été corrigés de façon générale (pas pour ces cas précis), puis le corpus complet a été réanalysé pour vérifier qu'aucun résultat ne changeait :

- un numéro d'exécutant mal lu sur une seule ligne créait une fausse alerte de signature → les lectures d'un même exécutant sont maintenant recoupées entre les lignes du tableau ;
- un léger décalage de l'image était mal compensé → recalage précis sur les traits du formulaire ;
- le moteur RapidOCR fusionnait parfois deux zéros consécutifs (« 260800002 » lu « 26080002 ») → lecture supplémentaire avec étirement horizontal ;
- le vote entre lectures accordait trop de poids aux variantes d'un même moteur → l'accord de deux moteurs différents prime désormais ;
- un montant collé au bord de sa case était parfois lu tronqué (« 936,6 ») → une lecture tronquée soutient la valeur complète au lieu de la contredire.

Relancer le test : `python scripts/test_aveugle.py` (depuis la racine du projet, environnement activé), ou avec RapidOCR seul : `set NO_TESS=1` puis la même commande. Les dossiers fabriqués sont écrits dans `data/test_aveugle/`.
