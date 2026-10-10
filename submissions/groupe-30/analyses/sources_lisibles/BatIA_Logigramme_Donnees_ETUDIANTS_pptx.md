# Source : DATA 2 _le kit étudiants\BatIA_Logigramme_Donnees_ETUDIANTS.pptx

## ppt/slides/slide1.xml

VOS DONNÉES BÂTIA, EN UN COUP D’ŒIL
Hackathon IA for Impact 2026 · Défi « Hacker le bâtiment avant qu’il ne casse » · données 100 % fictives
1
Le patrimoine
Tables 01 · 02 · 03
8 résidences (A à H), 4 modes d’énergie : gaz individuel, chaufferie collective, électrique, pompe à chaleur
32 bâtiments, 1 100 logements
Pour chaque logement : typologie, surface, étage, DPE détaillé, rotation des locataires
2
Les équipements
Table 04 · 4 217 équipements
Chaudières, PAC, ballons, convecteurs, VMC, ascenseurs…
Date de pose, origine de cette date, durée de vie de référence, contrat d’entretien
1 285 équipements à scorer (dans_perimetre_prediction = Oui)
3
Leur vie, 2018-2025
Tables 05 · 06 + 3 rapports PDF
30 630 interventions : entretiens, dépannages (symptôme, gravité, commentaire), remplacements
5 235 demandes de locataires, avec texte libre
Rapports prestataire : observations en texte libre (piste GenAI)
4
Ce que ça coûte
Tables 07 · 08
5 253 commandes : remplacements, réparations, remises en état
Plan d’investissement : 29 opérations (hypothétiques), traitées aujourd’hui par ordre d’arrivée
Enveloppe plafonnée à 1,5 M€ par an : il faut arbitrer
5
Vos deux défis
Au choix, ou les deux
Défi 1 — Détection précoce : quel équipement risque une panne bloquante (« Arrêt total ») entre janvier et septembre 2026 ?
Défi 2 — Rénovation : classer les 29 opérations avec un scoring multicritère explicable
6
Votre livrable
Ce que le jury attend
Défi 1 : un CSV « equipement_id, score_risque » pour les 1 285 équipements
Évaluation : capacité à classer (AUC) et pannes trouvées dans votre top 10 %
Un score explicable : l’IA recommande, l’humain décide
Les clés pour relier les tables : 
residence_id → batiment_id → logement_id → equipement_id   ·   Vos données s’arrêtent au 31/12/2025 : validez-vous dans le passé (fin 2024 → 2025)
BâtIA · Kit de données fictives · In’li sud-ouest | Action Logement · Détails : LISEZ-MOI_BatIA.pdf et onglet DICTIONNAIRE du classeur Excel

## Notes ppt/notesSlides/notesSlide1.xml

1