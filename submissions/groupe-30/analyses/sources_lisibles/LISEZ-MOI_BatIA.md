# Source : DATA 2 _le kit étudiants\BatIA_Kit_Hackathon\LISEZ-MOI_BatIA.pdf
Pages : 2

## Page 1

BâtIA · Kit de données fictives · Hackathon IA for Impact 2026 · In'li Sud-Ouest
1/2
BâtIA — Kit de données
Hackathon IA for Impact 2026 · Défi In'li Sud-Ouest
« Hacker le bâtiment avant qu'il ne casse »
Données 100 % fictives. Elles sont calibrées sur des statistiques réelles agrégées d'In'li Sud-Ouest, mais aucune ligne ne
correspond à un logement, un locataire ou un prestataire réel. N'essayez pas de les rattacher à des résidences existantes.
Le contexte
In'li Sud-Ouest gère 6 300 logements intermédiaires. Aujourd'hui, les rénovations sont traitées par ordre chronologique et les
pannes sont découvertes trop tard, en urgence. Ce kit simule 8 résidences (A à H), 1 100 logements et leur vie de 2018 au
31/12/2025 : équipements qui vieillissent, entretiens, pannes, demandes des locataires, commandes.
Deux défis au choix (ou les deux)
- 1. Détection précoce de panne. Pour les 1 285 équipements du périmètre (dans_perimetre_prediction = Oui), estimer le
risque de panne bloquante (dépannage de gravité « Arrêt total ») entre le 01/01/2026 et le 30/09/2026. Le jury détient la
réponse : vos prédictions seront comparées à ce qui s'est « réellement » passé.
- 2. Priorisation des rénovations. Proposer un scoring multicritère explicable pour classer les 29 opérations de la table 08
(hypothétique), sous une enveloppe annuelle plafonnée à 1,5 M€, au lieu de l'ordre chronologique actuel.
Comment les tables se relient
Résidences
8 lignes
Bâtiments
32 lignes
Logements
1 100 lignes
Équipements
4 217 lignes
Interventions
30 630 lignes
Demandes locataires
5 235 lignes
Commandes
5 253 lignes
logement_id
Un équipement est un emplacement fonctionnel : quand une chaudière est remplacée, son identifiant reste le même et sa date de pose
change. Les commandes et demandes sans logement_id concernent les parties communes.
Contenu du kit
Fichier
Format
Contenu
donnees/ (13 fichiers)
CSV UTF-8
9 tables + 4 référentiels. Séparateur virgule, dates AAAA-MM-JJ, une ligne
d'en-tête
BatIA_Hackathon_Donnees_Fictives.xlsx
Excel
Les mêmes tables + LISEZMOI, DICTIONNAIRE (chaque colonne et son
équivalent réel), HYPOTHESES (règles de fabrication et niveau de preuve)
rapports_prestataire/ (3 PDF)
PDF
Rapports d'activité trimestriels fictifs (T2, T3, T4 2025) d'un prestataire
multiservices, avec observations en texte libre
BatIA_notebook_demarrage.ipynb
Jupyter
Chargement, jointures, validation dans le passé, baselines et fichier de
soumission


## Page 2

BâtIA · Kit de données fictives · Hackathon IA for Impact 2026 · In'li Sud-Ouest
2/2
Défi 1 — ce que le jury attend
- Livrable : un CSV avec une ligne par équipement du périmètre et deux colonnes : equipement_id, score_risque
(plus le score est élevé, plus la panne est probable). Le notebook génère un exemple.
- Évaluation : (1) capacité à classer les équipements (AUC) ; (2) précision sur les 10 % les plus à risque : si l'on inspecte les
équipements que vous désignez, combien de vraies pannes évite-t-on ? Les deux sont comparés à une baseline « âge seul ».
- Explicabilité : pour chaque équipement à risque, savoir dire pourquoi (âge, dépannages répétés, visites manquées, signal
dans un commentaire…). Pas de boîte noire.
- Validez dans le passé : vous n'avez pas 2026. Placez-vous au 31/12/2024, calculez vos variables avec l'historique antérieur
uniquement, et testez sur janvier-septembre 2025. Attention aux fuites d'information (utiliser une donnée postérieure à la
date de référence).
Pistes de signaux (à vous de juger lesquels comptent)
Source
Exemples de signaux
04 Équipements
Âge, âge rapporté à la durée de vie de référence, famille, contrat d'entretien, remplacements passés
06 Interventions
Fréquence et gravité des dépannages, symptômes, absences aux visites, anomalies constatées, commentaires
des techniciens
05 Demandes
Motifs, textes libres (« eau tiède », « le problème revient »…), réouvertures, délais
Rapports PDF
Observations du technicien référent : un copilote GenAI peut-il les transformer en alertes ?
03 Logements
Typologie, rotation des locataires, DPE
Défi 2 — repères
Table 08 : coût, gain énergétique estimé, logements concernés, rang chronologique actuel. Croisez avec le DPE (03), les coûts
de maintenance (07), les pannes (06) et le calendrier réglementaire (interdiction progressive de louer les logements G puis F).
Attendu : un classement argumenté et une restitution compréhensible par une équipe non technique.
Règles du jeu
- RGPD et anonymisation : même fictives, ces données ne quittent pas le cadre du hackathon.
- « L'IA recommande, l'humain décide » : aucune décision automatique sans validation humaine.
- Les données suivent des règles de fabrication documentées (onglet HYPOTHESES). Les découvrir fait partie du jeu ; les
critiquer aussi.
- Ce qu'on est curieux de voir : une détection précoce inattendue, un copilote qui rend le score compréhensible sur le terrain,
une piste de mutualisation à l'échelle du groupe Action Logement.
Contact référent : Guillaume Rougé, Responsable RSE & Innovation, In'li Sud-Ouest — guillaume.rouge@inli.fr
