# Les 15 zones du bordereau CERFA 12278 (S 3404)

Ce document décrit la couche « 15 zones », ajoutée par la version 2.0 et conservée en 3.0 : la géométrie de chaque zone, sa correspondance avec les 22 contrôles, le calcul de son statut et son affichage.

**Version 3.0.** Le calcul des zones n'a pas changé. Deux choses diffèrent :
- **Affichage par défaut** : c'est le mode simple. Seules les zones en écart (rouge) ou à vérifier (gris) y sont marquées, les zones conformes restant discrètes. La présentation complète décrite ci-dessous est celle du **mode expert**.
- **Géométrie** : l'image est redressée si elle est inclinée. La fiabilité géométrique de chaque champ est mesurée : un champ mal localisé rend sa zone « à vérifier ».

> Le statut d'une zone résume ses contrôles ; il ne les remplace jamais. Chaque règle R01 à R22 reste présentée et décidée individuellement.

## 1. Catalogue et correspondance zone ↔ règles

| Zone | Contenu | Règles (rôle) | Donnée du fichier TXT |
|---|---|---|---|
| Z1 | Identifiant du formulaire | R01 | aucune (référence du cahier des charges : 12278*0) |
| Z2 | N° FINESS de l'établissement | R02 | NumeroTiers (type 1, pos. 2-10) |
| Z3 | N° de lot | R03 | NumeroLot (type 1, pos. 20-22) |
| Z4 | N° de facture | R04 | NumeroFacture (type 2, pos. 30-38) |
| Z5 | N° d'immatriculation de l'assuré | R05 | NumeroAssure (type 2, pos. 12-24) |
| Z6 | Prestations : frais de structure et de soins | R06, R07, R08 (principales) ; R09, R10, R16 (référence GHS lue en zone 6) ; R13 (exhaustivité zones 6 et 7) | Actes de type 3 (pos. 56-60) et NumeroGH (pos. 110-113) |
| Z7 | Produits LPP, pharmacie, médicaments | R10, R11 (principales) ; R13 (exhaustivité zones 6 et 7) | Actes de type 3 |
| Z8 | Sous-total des prestations (1+2+3) | R12 (principale) ; R20 (zone 13 = zone 8 + zone 12) | TotalPrestations (type 5, pos. 42-49) |
| Z9 | Identification des exécutants | R18 (associée aux signatures de la zone 11) | aucune (contrôle propre au bordereau) |
| Z10 | Actes médicaux et honoraires | R14, R15, R19 | Actes de type 4 (pos. 76-80), CodeCCAM 4-M (pos. 43-55) |
| Z11 | Signatures des praticiens | R18 (associée aux exécutants de la zone 9) | aucune |
| Z12 | Sous-total des honoraires (4) | R17 (principale) ; R20 | TotalHonoraires (type 5, pos. 58-65) |
| Z13 | Montant total de la facture | R20 | aucune (contrôle arithmétique propre au bordereau) |
| Z14 | Signature du directeur | R21 | aucune |
| Z15 | Code CERFA du document | R22 | aucune (référence : S3404) |

Règles transversales : R09 compare des NumeroGH du fichier entre eux, en référence à l'acte GHS (rattachée à Z6 pour cette référence) ; R13 vérifie l'exhaustivité des zones 6 et 7 ; R18 associe les zones 9 et 11 ; R20 associe les zones 8, 12 et 13. Aucune applicabilité n'est ajoutée au cahier des charges : la table est vérifiée par un test automatique (`test_table_zone_regles_coherente_avec_les_regles`).

## 2. Géométrie

La géométrie est **indépendante des lectures OCR** : elle est calculée à partir des gabarits F1, F2 et F3 (`backend/sentinel/ocr/templates.py`) et du recalage effectif de chaque bordereau (`ext["layout"]` : famille, échelle, translation, orientation). Une zone vide, illisible ou non applicable reste donc localisée, visible et sélectionnable.

| Zone | Régions |
|---|---|
| Z1 à Z5, Z8, Z12, Z13, Z15 | une région : la case de la valeur (marge verticale identique à l'extraction) |
| Z6 | quatre régions : tableau de gauche (6a), tableau de droite (6b), sous-total 1, sous-total 2 |
| Z7 | deux régions : tableau LPP, sous-total 3 |
| Z9 | une région : la colonne « n° d'identification de l'exécutant » du tableau des actes (sa position réelle sur le formulaire) |
| Z10 | une région : le tableau des actes |
| Z11 | huit régions : les cases de signature 1 à 8 |
| Z14 | une région : la case de signature du directeur |

Une zone faite de régions disjointes reçoit plusieurs régions plutôt qu'un rectangle approximatif. Deux valeurs voisines (n° de lot et n° de facture, sous-total 3 et zone 8) ne se recouvrent pas : la frontière est placée au milieu, pour que chacune reste cliquable. Les coordonnées sont fournies en pixels de l'image recalée et normalisées (0 à 1). Si la mise en page n'est pas reconnue, les 15 zones restent listées avec la mention « localisation impossible : mise en page non reconnue ».

## 3. Statut d'une zone

| Statut | Couleur de l'encadrement | Condition |
|---|---|---|
| Anomalie | rouge `#DC2626` | au moins une règle de la zone en anomalie (indicateur « contrôles également incertains » si une autre règle est non vérifiable ou en erreur) |
| Erreur technique | orange `#F59E0B` | aucune anomalie, mais un contrôle n'a pas pu s'exécuter |
| Non vérifiable | gris `#6B7280` | aucune anomalie, au moins un contrôle non vérifiable — **ou** une conformité qui ne repose que sur une lecture OCR isolée |
| Non applicable | gris clair en pointillés | toutes les règles de la zone sont non applicables à ce dossier |
| Conforme | vert `#16A34A` | toutes les règles applicables sont conformes, sans incertitude |

L'indicateur « Résultats mixtes » signale une zone dont les règles ont des statuts différents ; le détail présente chaque résultat. La couleur n'est jamais le seul indicateur : chaque zone porte aussi une icône, un libellé, une infobulle et un focus clavier. Une simple décision « examiné » ne change jamais un statut ; seule une correction ou une validation de lecture, qui modifie les données d'entrée, provoque le recalcul.

## 4. Interface (mode expert)

- **Visionneuse du bordereau** : encadrements colorés superposés à l'image (transparents à l'intérieur), qui suivent le zoom et le déplacement ; badge `Z8` avec icône ; bouton « Masquer / Afficher les encadrements » et légende permanente sous l'image. La sélection ajoute un halo bleu et assombrit le reste de la page, sans remplacer la couleur de conformité.
- **Onglet « 15 zones »** du dossier : pastilles Z1 à Z15, cartes de synthèse (statut, nombre de règles, d'anomalies, de non vérifiables, revue humaine), navigation Précédente / Suivante, touches `[` `]`, Échap pour revenir à la vue d'ensemble.
- **Fiche de zone** :
  - informations générales et motif de la couleur ;
  - contrôles associés, avec leurs valeurs et leurs actions ;
  - extraction : valeur brute, valeur normalisée, méthode, lectures individuelles, accord des moteurs, correction ou validation ;
  - lignes de tableau rapprochées du TXT ;
  - données du TXT, avec leur ligne et leurs positions surlignées ;
  - assistance : ce qui a été comparé, ce qui n'a pas pu être vérifié, action recommandée, revue complémentaire ;
  - traçabilité.
- **Zones particulières** :
  - Z6, Z7 et Z10 : une ligne par prestation ou par acte, avec code, GHS, montant, exécutant, date, ligne du TXT et résultat du rapprochement. Une ligne du TXT absente du bordereau est indiquée avec la zone où elle aurait dû figurer, sans coordonnée inventée.
  - Z9 : liste des exécutants, avec la fiabilité de leur lecture.
  - Z11 et Z14 : pour chaque case, la présence détectée, l'exécutant associé, l'incertitude et une confirmation humaine (présent / vide). La présence n'est jamais assimilée à l'authenticité.
- **Synchronisation** : la même couleur, calculée une seule fois sur le serveur, apparaît dans la visionneuse, les pastilles, la fiche, la liste des dossiers (bande des 15 zones), la revue rapide, la matrice de supervision et le rapport PDF (tableau des zones et illustration du bordereau encadré).

## 5. Vérification

- `backend/tests/test_v2_fiabilite.py` :
  - `test_couverture_825_entrees` : 55 × 15 entrées, géométrie présente et contenue dans l'image, statut, règles ;
  - statut de zone (anomalie et incertitude, conformité sur lecture isolée, non applicable, erreur technique) ;
  - zone sans lecture OCR toujours localisée ;
  - mise en page inconnue.
- `backend/tests/test_v2_api.py` : zones dans le dossier et la liste, recalcul et effet enregistrés après une correction (règles et zones).
- `scripts/e2e_zones.py` (navigateur réel, application lancée), sur 825 entrées :
  - présence des 15 encadrements ;
  - couleur affichée = statut serveur = pastille ;
  - pointillés pour les zones non applicables ;
  - aucun vert sur un contrôle incertain ;
  - clic sur chaque zone : sélection et cadrage visible.

  Sur un dossier de chaque famille, il vérifie aussi l'alignement après zoom et la navigation au clavier, puis la mise à jour des couleurs après une correction et son annulation. Résultat : `data/e2e_zones.json`. Dernière relance (10/10/2026) : 825 entrées sur 825, 0 écart, familles F1, F2 et F3.
