# Résultats réels sur le corpus fourni

Moteur 3.0.0, règles R22-2026.10-v3. Corpus : `General-main.zip` — 55 bordereaux JPG, 55 factures TXT, 55 dossiers, 1210 contrôles exécutés. Ces chiffres sont produits par `python -m sentinel.cli stats` et sont reproductibles (extraction OCR mise en cache, règles déterministes).

> Une anomalie est un écart documentaire constaté entre le bordereau et le fichier : ce n'est pas une fraude démontrée.

> Les n° d'assuré sont masqués dans ce document publiable (1ᵉʳ chiffre + • + 2 derniers).

> Statut de ces résultats : sortie du moteur, examinée par une revue assistée (docs/DIAGNOSTIC_V3.md) **mais pas encore validée par un validateur humain** (référentiel de validation, écran « Qualité et validation »).

## Par règle

| Règle | Intitulé | Évaluables | Conformes | Anomalies | Non vérifiables | Non applicables | Erreurs |
|---|---|---:|---:|---:|---:|---:|---:|
| R01 | Identifiant du formulaire (CERFA 12278*0) | 55 | 52 | 3 | 0 | 0 | 0 |
| R02 | N° d'établissement (FINESS) = NumeroTiers | 55 | 54 | 1 | 0 | 0 | 0 |
| R03 | N° de lot = NumeroLot | 55 | 52 | 3 | 0 | 0 | 0 |
| R04 | N° de facture = NumeroFacture | 55 | 51 | 4 | 0 | 0 | 0 |
| R05 | N° d'assuré (13 premiers caractères) = NumeroAssure | 55 | 51 | 4 | 0 | 0 | 0 |
| R06 | Présence d'une prestation GHS avec son numéro | 55 | 55 | 0 | 0 | 0 | 0 |
| R07 | N° GHS du bordereau = NumeroGH (type 3, prestation GHS) | 55 | 53 | 2 | 0 | 0 | 0 |
| R08 | Prestations de la zone 6 (avec montant) présentes dans le fichier | 55 | 55 | 0 | 0 | 0 | 0 |
| R09 | NumeroGH des actes de type 3 = NumeroGH de l'acte GHS | 40 | 36 | 4 | 0 | 15 | 0 |
| R10 | NumeroGH des actes de type 3 (LPP) = n° GHS de la zone 6 | 20 | 18 | 2 | 0 | 35 | 0 |
| R11 | Prestations de la zone 7 présentes dans le fichier | 20 | 18 | 2 | 0 | 35 | 0 |
| R12 | Sous-total 1+2+3 (zone 8) = TotalPrestations | 55 | 49 | 6 | 0 | 0 | 0 |
| R13 | Prestations du fichier présentes en zone 6 ou 7 | 55 | 53 | 2 | 0 | 0 | 0 |
| R14 | Actes de la zone 10 codés sur ≤ 4 caractères présents dans le fichier | 40 | 36 | 4 | 0 | 15 | 0 |
| R15 | Actes CCAM (7 caractères) de la zone 10 présents dans le fichier | 35 | 32 | 3 | 0 | 20 | 0 |
| R16 | NumeroGH des enregistrements 4-S = n° GHS de la zone 6 | 53 | 50 | 3 | 0 | 2 | 0 |
| R17 | Sous-total 4 (zone 12) = TotalHonoraires | 55 | 49 | 6 | 0 | 0 | 0 |
| R18 | Signatures des exécutants (zone 11) | 40 | 38 | 2 | 0 | 15 | 0 |
| R19 | Actes du fichier (type 4 / 4-M) présents en zone 10 | 53 | 46 | 7 | 0 | 2 | 0 |
| R20 | Montant total (zone 13) = zone 8 + zone 12 | 55 | 55 | 0 | 0 | 0 | 0 |
| R21 | Signature du directeur de l'établissement (zone 14) | 55 | 52 | 3 | 0 | 0 | 0 |
| R22 | Code CERFA (zone 15) = S3404 | 55 | 52 | 3 | 0 | 0 | 0 |

**Dossiers** : 55 — avec au moins une anomalie : 50 — avec un contrôle non vérifiable : 0 — sans écart : 5 — rapprochement bordereau/fichier ambigu : 1.

## Par zone du bordereau (15 zones CERFA)

Nombre de dossiers par statut de zone (voir docs/ZONES.md pour la correspondance zone ↔ règles).

| Zone | Contenu | Conformes | Anomalies | Non vérifiables | Non applicables | Erreurs |
|---|---|---:|---:|---:|---:|---:|
| Z1 | Identifiant du formulaire | 52 | 3 | 0 | 0 | 0 |
| Z2 | N° FINESS de l'établissement | 54 | 1 | 0 | 0 | 0 |
| Z3 | N° de lot | 52 | 3 | 0 | 0 | 0 |
| Z4 | N° de facture | 51 | 4 | 0 | 0 | 0 |
| Z5 | N° d'immatriculation de l'assuré | 51 | 4 | 0 | 0 | 0 |
| Z6 | Prestations — frais de structure et de soins | 46 | 9 | 0 | 0 | 0 |
| Z7 | Produits LPP, pharmacie et médicaments | 50 | 5 | 0 | 0 | 0 |
| Z8 | Sous-total des prestations (1+2+3) | 49 | 6 | 0 | 0 | 0 |
| Z9 | Identification des exécutants | 38 | 2 | 0 | 15 | 0 |
| Z10 | Actes médicaux et honoraires | 45 | 10 | 0 | 0 | 0 |
| Z11 | Signatures des praticiens | 38 | 2 | 0 | 15 | 0 |
| Z12 | Sous-total des honoraires (4) | 49 | 6 | 0 | 0 | 0 |
| Z13 | Montant total de la facture | 55 | 0 | 0 | 0 | 0 |
| Z14 | Signature du directeur de l'établissement | 52 | 3 | 0 | 0 | 0 |
| Z15 | Code CERFA du document | 52 | 3 | 0 | 0 | 0 |

## Par dossier

| Dossier | Anomalies | Constat (explication produite par le moteur) |
|---|---|---|
| Facture1_01 | R18 | **R18** — Aucune signature trouvée en zone 11 pour l'exécutant 201400330. Une vérification est nécessaire. |
| Facture1_02 | — | Aucun écart détecté. |
| Facture1_03 | R21 | **R21** — La zone 14 (signature du directeur de l'établissement) apparaît vide. Une vérification est nécessaire. |
| Facture1_04 | R12 | **R12** — Total des prestations différent. Bordereau : 818,97 €. Fichier (TotalPrestations) : 818,98 €. Écart : 0,01 €. Une vérification est nécessaire. Remarque : la somme des lignes du fichier (818,97 €) est égale à la valeur du bordereau ; c'est le total du fichier qui diffère de ses propres lignes. |
| Facture1_05 | R05 | **R05** — N° d'assuré différent. Bordereau (13 premiers caractères) : 2••••••••••05. Fichier : 2••••••••••00. Une vérification est nécessaire. |
| Facture1_06 | R17 | **R17** — Total des honoraires différent. Bordereau : 28,80 €. Fichier (TotalHonoraires) : 28,81 €. Écart : 0,01 €. Une vérification est nécessaire. Remarque : la somme des lignes du fichier (28,80 €) est égale à la valeur du bordereau ; c'est le total du fichier qui diffère de ses propres lignes. |
| Facture1_07 | R03 | **R03** — N° de lot différent. Valeur du bordereau : 574. Valeur du fichier : 575. Une vérification est nécessaire. |
| Facture1_08 | R04 | **R04** — N° de facture différent. Valeur du bordereau : 260800008. Valeur du fichier : 268800008. Une vérification est nécessaire. |
| Facture1_09 | R13 | **R13** — Élément(s) PH7 facturé(s) dans le fichier (Acte de type 3) mais absent(s) du bordereau (zones 6 et 7). Une vérification est nécessaire. |
| Facture1_10 | R19 | **R19** — Élément(s) C facturé(s) dans le fichier (Acte de type 4 / CodeCCAM 4-M) mais absent(s) du bordereau (zone 10). Une vérification est nécessaire. |
| Facture1_11 | R11, R13 | **R11** — Prestation(s) PH8 présente(s) sur le bordereau (zone 7) mais absente(s) du fichier (Acte de type 3). Une vérification est nécessaire.<br>**R13** — Élément(s) PH7 facturé(s) dans le fichier (Acte de type 3) mais absent(s) du bordereau (zones 6 et 7). Une vérification est nécessaire. |
| Facture1_12 | R14, R19 | **R14** — Prestation(s) K présente(s) sur le bordereau (zone 10) mais absente(s) du fichier (Acte de type 4). Une vérification est nécessaire.<br>**R19** — Élément(s) C facturé(s) dans le fichier (Acte de type 4 / CodeCCAM 4-M) mais absent(s) du bordereau (zone 10). Une vérification est nécessaire. |
| Facture1_13 | R11 | **R11** — Prestation(s) EMI présente(s) sur le bordereau (zone 7) mais absente(s) du fichier (Acte de type 3). Une vérification est nécessaire. |
| Facture1_14 | R14 | **R14** — Prestation(s) K présente(s) sur le bordereau (zone 10) mais absente(s) du fichier (Acte de type 4). Une vérification est nécessaire. |
| Facture1_15 | R09, R10 | **R09** — NumeroGH incohérent : PH8 porte 9616 alors que l'acte GHS porte 9606. Une vérification est nécessaire.<br>**R10** — NumeroGH différent du n° GHS lu en zone 6 (9606) : PH8 porte 9616. Une vérification est nécessaire. |
| Facture1_16 | — | Aucun écart détecté. |
| Facture1_17 | R22 | **R22** — Code CERFA lu « S4404 » au lieu de S3404. Une vérification est nécessaire. |
| Facture1_18 | R01 | **R01** — Identifiant du formulaire lu « 22278*01 » : ne correspond pas à « 12278*0 » (préfixe « 12278*0 »). Une vérification est nécessaire. |
| Facture1_19 | R09, R10, R16 | **R09** — NumeroGH incohérent : PH8 porte 9607, EMI porte 9607 alors que l'acte GHS porte 9606. Une vérification est nécessaire.<br>**R10** — NumeroGH différent du n° GHS lu en zone 6 (9606) : PH8 porte 9607, EMI porte 9607. Une vérification est nécessaire.<br>**R16** — 1 enregistrement(s) 4-S porte(nt) un NumeroGH différent du n° GHS lu en zone 6 (9606) : 9607. Une vérification est nécessaire. |
| Facture1_20 | R12, R17 | **R12** — Total des prestations différent. Bordereau : 818,97 €. Fichier (TotalPrestations) : 818,98 €. Écart : 0,01 €. Une vérification est nécessaire. Remarque : la somme des lignes du fichier (818,97 €) est égale à la valeur du bordereau ; c'est le total du fichier qui diffère de ses propres lignes.<br>**R17** — Total des honoraires différent. Bordereau : 28,80 €. Fichier (TotalHonoraires) : 28,81 €. Écart : 0,01 €. Une vérification est nécessaire. Remarque : la somme des lignes du fichier (28,80 €) est égale à la valeur du bordereau ; c'est le total du fichier qui diffère de ses propres lignes. |
| Facture2_01 | — | Aucun écart détecté. |
| Facture2_02 | R18 | **R18** — Aucune signature trouvée en zone 11 pour l'exécutant 491053989. Une vérification est nécessaire. |
| Facture2_03 | R22 | **R22** — Code CERFA lu « S3403 » au lieu de S3404. Une vérification est nécessaire. |
| Facture2_04 | R01, R04, R05 | **R01** — Identifiant du formulaire lu « 12280*01 » : ne correspond pas à « 12278*0 » (préfixe « 12278*0 »). Une vérification est nécessaire.<br>**R04** — N° de facture différent. Valeur du bordereau : 261034503. Valeur du fichier : 261034504. Une vérification est nécessaire.<br>**R05** — N° d'assuré différent. Bordereau (13 premiers caractères) : 2••••••••••03. Fichier : 2••••••••••04. Une vérification est nécessaire. |
| Facture2_05 | R21 | **R21** — La zone 14 (signature du directeur de l'établissement) apparaît vide. Une vérification est nécessaire. |
| Facture2_06 | R02 | **R02** — N° d'établissement différent. Valeur du bordereau : 490002037. Valeur du fichier : 490002137. Une vérification est nécessaire. |
| Facture2_07 | R05 | **R05** — N° d'assuré différent. Bordereau (13 premiers caractères) : 2••••••••••07. Fichier : 2••••••••••17. Une vérification est nécessaire. |
| Facture2_08 | R03 | **R03** — N° de lot différent. Valeur du bordereau : 351. Valeur du fichier : 331. Une vérification est nécessaire. |
| Facture2_09 | R04 | **R04** — N° de facture différent. Valeur du bordereau : 261034509. Valeur du fichier : 261034519. Une vérification est nécessaire. |
| Facture2_10 | R07, R09 | **R07** — N° GHS différent. Valeur du bordereau : 4158. Valeur du fichier : 4159. Une vérification est nécessaire.<br>**R09** — NumeroGH incohérent : FJA porte 4158 alors que l'acte GHS porte 4159. Une vérification est nécessaire. |
| Facture2_11 | R09 | **R09** — NumeroGH incohérent : FJA porte 4159 alors que l'acte GHS porte 4158. Une vérification est nécessaire. |
| Facture2_12 | R16 | **R16** — 1 enregistrement(s) 4-S porte(nt) un NumeroGH différent du n° GHS lu en zone 6 (4158) : 4159. Une vérification est nécessaire. |
| Facture2_13 | R16 | **R16** — 1 enregistrement(s) 4-S porte(nt) un NumeroGH différent du n° GHS lu en zone 6 (4158) : 4159. Une vérification est nécessaire. |
| Facture2_14 | R12 | **R12** — Total des prestations différent. Bordereau : 1 013,22 €. Fichier (TotalPrestations) : 1 013,23 €. Écart : 0,01 €. Une vérification est nécessaire. Remarque : la somme des lignes du fichier (1 013,22 €) est égale à la valeur du bordereau ; c'est le total du fichier qui diffère de ses propres lignes. |
| Facture2_15 | R17 | **R17** — Total des honoraires différent. Bordereau : 936,68 €. Fichier (TotalHonoraires) : 936,69 €. Écart : 0,01 €. Une vérification est nécessaire. Remarque : la somme des lignes du fichier (936,68 €) est égale à la valeur du bordereau ; c'est le total du fichier qui diffère de ses propres lignes. |
| Facture2_16 | R12, R17 | **R12** — Total des prestations différent. Bordereau : 1 013,22 €. Fichier (TotalPrestations) : 1 013,23 €. Écart : 0,01 €. Une vérification est nécessaire. Remarque : la somme des lignes du fichier (1 013,22 €) est égale à la valeur du bordereau ; c'est le total du fichier qui diffère de ses propres lignes.<br>**R17** — Total des honoraires différent. Bordereau : 936,68 €. Fichier (TotalHonoraires) : 936,69 €. Écart : 0,01 €. Une vérification est nécessaire. Remarque : la somme des lignes du fichier (936,68 €) est égale à la valeur du bordereau ; c'est le total du fichier qui diffère de ses propres lignes. |
| Facture2_17 | R15, R19 | **R15** — Prestation(s) JCPD001 présente(s) sur le bordereau (zone 10) mais absente(s) du fichier (CodeCCAM de type 4-M). Une vérification est nécessaire.<br>**R19** — Élément(s) JCPD002 facturé(s) dans le fichier (Acte de type 4 / CodeCCAM 4-M) mais absent(s) du bordereau (zone 10). Une vérification est nécessaire. |
| Facture2_18 | R14, R19 | **R14** — Prestation(s) B présente(s) sur le bordereau (zone 10) mais absente(s) du fichier (Acte de type 4). Une vérification est nécessaire.<br>**R19** — Élément(s) BIO facturé(s) dans le fichier (Acte de type 4 / CodeCCAM 4-M) mais absent(s) du bordereau (zone 10). Une vérification est nécessaire. |
| Facture2_19 | R14 | **R14** — Prestation(s) B présente(s) sur le bordereau (zone 10) mais absente(s) du fichier (Acte de type 4). Une vérification est nécessaire. |
| Facture2_20 | R19 | **R19** — Élément(s) BIO facturé(s) dans le fichier (Acte de type 4 / CodeCCAM 4-M) mais absent(s) du bordereau (zone 10). Une vérification est nécessaire. |
| Facture3_01 | — | Aucun écart détecté. |
| Facture3_02 | R21 | **R21** — La zone 14 (signature du directeur de l'établissement) apparaît vide. Une vérification est nécessaire. |
| Facture3_03 | R12 | **R12** — Total des prestations différent. Bordereau : 398,30 €. Fichier (TotalPrestations) : 398,31 €. Écart : 0,01 €. Une vérification est nécessaire. Remarque : la somme des lignes du fichier (398,30 €) est égale à la valeur du bordereau ; c'est le total du fichier qui diffère de ses propres lignes. |
| Facture3_04 | R05 | **R05** — N° d'assuré différent. Bordereau (13 premiers caractères) : 1••••••••••04. Fichier : 1••••••••••14. Une vérification est nécessaire. |
| Facture3_05 | R17 | **R17** — Total des honoraires différent. Bordereau : 50,48 €. Fichier (TotalHonoraires) : 50,49 €. Écart : 0,01 €. Une vérification est nécessaire. Remarque : la somme des lignes du fichier (50,48 €) est égale à la valeur du bordereau ; c'est le total du fichier qui diffère de ses propres lignes. |
| Facture3_06 | R03 | **R03** — N° de lot différent. Valeur du bordereau : 925. Valeur du fichier : 995. Une vérification est nécessaire. |
| Facture3_07 | R04 | **R04** — N° de facture différent. Valeur du bordereau : 491907. Valeur du fichier : 000491917. Une vérification est nécessaire. |
| Facture3_08 | R07 | **R07** — N° GHS différent. Valeur du bordereau : 9603. Valeur du fichier : 9601. Une vérification est nécessaire. |
| Facture3_09 | R15 | **R15** — Prestation(s) JVRP008 présente(s) sur le bordereau (zone 10) mais absente(s) du fichier (CodeCCAM de type 4-M). Une vérification est nécessaire. |
| Facture3_10 | R22 | **R22** — Code CERFA lu « S3405 » au lieu de S3404. Une vérification est nécessaire. |
| Facture3_11 | R01 | **R01** — Identifiant du formulaire lu « 12279*01 » : ne correspond pas à « 12278*0 » (préfixe « 12278*0 »). Une vérification est nécessaire. |
| Facture3_12 | R12, R17 | **R12** — Total des prestations différent. Bordereau : 398,30 €. Fichier (TotalPrestations) : 398,31 €. Écart : 0,01 €. Une vérification est nécessaire. Remarque : la somme des lignes du fichier (398,30 €) est égale à la valeur du bordereau ; c'est le total du fichier qui diffère de ses propres lignes.<br>**R17** — Total des honoraires différent. Bordereau : 50,48 €. Fichier (TotalHonoraires) : 50,49 €. Écart : 0,01 €. Une vérification est nécessaire. Remarque : la somme des lignes du fichier (50,48 €) est égale à la valeur du bordereau ; c'est le total du fichier qui diffère de ses propres lignes. |
| Facture3_13 | — | Aucun écart détecté. |
| Facture3_14 | R15, R19 | **R15** — Prestation(s) JVRP008 présente(s) sur le bordereau (zone 10) mais absente(s) du fichier (CodeCCAM de type 4-M). Une vérification est nécessaire.<br>**R19** — Élément(s) JVRP009 facturé(s) dans le fichier (Acte de type 4 / CodeCCAM 4-M) mais absent(s) du bordereau (zone 10). Une vérification est nécessaire. |
| Facture3_15 | R19 | **R19** — Élément(s) JVRP009 facturé(s) dans le fichier (Acte de type 4 / CodeCCAM 4-M) mais absent(s) du bordereau (zone 10). Une vérification est nécessaire. |

## Contrôles implémentés

Les 22 règles sont implémentées et exécutées sur les 55 dossiers (aucune erreur technique). Les règles suivantes reposent sur une convention d'interprétation explicite (à valider par le métier) :

- **R01** (AMB-01) : convention proposée, non validée : préfixe `12278*0` exigé, chiffre de version accepté (le bordereau imprime `12278*01`). Chaque résultat montre aussi la lecture littérale ; une décision de la MSA peut être enregistrée.
- **R03, R04** : comparaison numérique, zéros de cadrage ignorés.
- **Fiabilité géométrique (v3.0)** : un champ ou un tableau mal localisé rend le contrôle *non vérifiable*, jamais anomalie ni conforme.
- **Politique d'incertitude (v2.0)** : des lectures OCR contradictoires ex æquo ou des moteurs en désaccord rendent le contrôle *non vérifiable*, même si l'une des lectures égale la valeur du fichier ; R20 n'utilise que des montants lus de façon fiable.
- **R09 / R10** : R09 contrôle interne au fichier (référence : GHS de type 3) ; R10 : actes de la zone 7 comparés au GHS lu en zone 6.
- **R08, R11, R13, R14, R15, R19** : rapprochement occurrence par occurrence ; R19 retrouve un acte suivi d'un 4-M par son code CCAM.
- **R14** : lignes de détail de biologie (codes à 4 chiffres sous un acte B, sans exécutant ni montant) exclues.

## Contrôles partiellement pris en charge

- **R18** : l'association exécutant ↔ case de signature se fait par le numéro imprimé dans la case. Si ce numéro est illisible alors qu'un élément est présent, le contrôle passe en *non vérifiable* (association non prouvée) plutôt qu'en conforme.
- **R18, R21** : détection de présence d'un élément (tracé, cachet, mention « par mandat », signature électronique) ; l'authenticité n'est jamais certifiée.
- **Recalage** (v3.0) : redressement des inclinaisons jusqu'à ±6° et ajustement d'échelle ; pas de correction de perspective (photo prise de biais).

## Limites et ambiguïtés

- Aucune vérité terrain validée par un humain : aucun taux de précision n'est affirmé (référentiel de validation prêt, vide).
- Gabarits calibrés sur les 3 mises en page du corpus ; un nouveau modèle de bordereau est signalé « non reconnu ».
- `Facture2_06.txt` contient un blanc inséré en position 11 : le fichier est relu en le réalignant, car le point d'insertion est démontré par 4 vérifications internes au fichier, sans le bordereau. Cette lecture est signalée comme une interprétation, avec une alerte « fichier mal formé » (docs/DIAGNOSTIC_V3.md).
- Le montant de 100 000 € (contrôle interne 2025) est une donnée de contexte, non comparable et non extrapolée.
- Les points à clarifier sont listés (AMB-01 à AMB-08), avec l'effet calculé d'un changement de convention, dans l'écran « Règles et conventions ».
