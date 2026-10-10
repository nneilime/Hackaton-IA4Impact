# Cadrage du besoin : prévention des pannes BatIA

Analyse du kit fourni, réalisée le 9 octobre 2026. Le scénario de prédiction reste fixé au **31 décembre 2025**, quelle que soit la date réelle du hackathon. Les constats chiffrés sont calculés sur les fichiers locaux, pas sur un patrimoine réel.

## Le besoin en une phrase

**Aider les équipes techniques du bailleur à choisir les équipements à inspecter en priorité, à partir des signaux déjà disponibles, pour intervenir avant une panne bloquante et justifier chaque alerte avec des preuves datées.**

Le problème métier décrit dans les documents est une maintenance trop souvent déclenchée en urgence. L'information utile existe dans plusieurs sources : passages des techniciens, entretien, demandes des occupants et rapports. Il faut la rapprocher au bon niveau, détecter une dégradation et permettre une action réalisable par les équipes.

Les utilisateurs principaux sont les équipes techniques et patrimoniales et les personnes qui coordonnent les prestataires. Les occupants bénéficient d'une meilleure continuité du chauffage, de l'eau chaude, de la ventilation ou des équipements collectifs. La direction attend une solution défendable et une valeur mesurable. Cette répartition des usages est une proposition de cadrage, à confirmer avec le référent métier.

## Le contrat précis du hackathon

| Point | Attendu explicite du kit |
| --- | --- |
| Objet évalué | Un **équipement**, identifié par `equipement_id` |
| Périmètre | Les **1 285** lignes de `04_equipements` où `dans_perimetre_prediction = Oui` |
| Informations disponibles | Historique jusqu'à la fin du **31/12/2025** |
| Événement à anticiper | Au moins une intervention `type_intervention = Dépannage` et `gravite = Arrêt total` |
| Horizon | Du **01/01/2026 au 30/09/2026 inclus** |
| Soumission | CSV, exactement une ligne par équipement, colonnes `equipement_id,score_risque` |
| Sens du score | Plus le score est élevé, plus l'équipement est à risque |
| Évaluation | AUC et précision parmi les 10 % les plus à risque, comparées à une baseline d'âge |
| Explicabilité | Pouvoir expliquer les alertes à une équipe métier |
| Décision | Validation humaine des actions |

Le score demandé est un classement. Un affichage en pourcentage exige en plus de vérifier la calibration des probabilités. Le kit ne demande ni une date exacte de panne, ni une durée de vie restante, ni un diagnostic de pièce défectueuse. Plusieurs arrêts pour un même équipement ne créent qu'une cible positive sur l'horizon.

**Notre périmètre est uniquement la prévention des pannes.** La priorisation des rénovations, les 29 opérations d'investissement et l'enveloppe de 1,5 M€ sont hors périmètre. Le document MBA décrit un projet plus large : ses choix de déploiement, son exemple de scoring énergétique et son modèle économique ne constituent pas des obligations pour notre prototype.

Attention : le PDF du hackathon et le logigramme étudiants numérotent la prévention « défi 1 ». L'onglet LISEZMOI du classeur inverse les numéros. Se fier au sujet et à la définition de la cible. De même, la « Phase 2 » du document MBA désigne une phase académique, pas le défi de rénovation du hackathon.

Sources de ces exigences : [consignes du hackathon](../DATA%202%20_le%20kit%20%C3%A9tudiants/BatIA_Kit_Hackathon/LISEZ-MOI_BatIA.pdf), pages 1-2, et [notebook extrait](sources_lisibles/BatIA_notebook_demarrage.md), cellules 6-11. Le [document MBA](sources_lisibles/02_PHASE2_BatIA_INLISO.md), sections 8 et 10, apporte le contexte.

## Ce que contiennent réellement les données

Le kit simule **8 résidences, 32 bâtiments et 1 100 logements**. Les 13 CSV et leurs onglets Excel contiennent les mêmes valeurs après normalisation des représentations numériques : aucune divergence détectée. Les CSV sont donc le point de départ le plus simple. Le classeur reste indispensable pour son dictionnaire et ses hypothèses, absents des CSV originaux.

| Source | Volume | Utilité pour notre défi |
| --- | ---: | --- |
| Équipements (04) | 4 217 | Population à scorer, familles, pose, entretien, localisation |
| Interventions (06) | 30 630 | Historique technique et construction des cibles passées |
| Demandes (05) | 5 235 | Symptômes et récurrence perçus par les occupants |
| Logements / bâtiments / résidences (03 / 02 / 01) | 1 100 / 32 / 8 | Contexte et rattachement territorial |
| Rapports PDF | 3 trimestres en 2025 | Observations à transformer en éléments explicables et sourcés |
| Commandes (07) | 5 253 | Contexte de coût éventuel, couverture partielle de la maintenance |
| Prestataires et référentiels | 14 prestataires, 4 référentiels | Sens des codes, familles et hypothèses de durée de vie |
| Plan d'investissement (08) | 29 | Hors périmètre |

Le périmètre de prédiction comprend **1 240 équipements rattachés aux logements et 45 équipements collectifs**. Limiter le projet aux chaudières individuelles ferait perdre une partie du défi.

| Famille à scorer | Effectif |
| --- | ---: |
| Chaudière gaz individuelle | 400 |
| Ballon ECS électrique | 230 |
| Ensemble de convecteurs électriques | 230 |
| Ensemble de panneaux rayonnants | 140 |
| Ballon thermodynamique | 140 |
| Pompe à chaleur | 100 |
| Caisson VMC collectif | 23 |
| Ascenseur | 15 |
| Chaufferie collective | 5 |
| Production ECS solaire collective | 2 |

Les bouches VMC, la robinetterie, les volets et les portes de hall restent hors de la soumission. Leur historique peut fournir du contexte, mais leurs propres arrêts ne doivent pas définir la cible des appareils à scorer.

Les relations utiles sont décrites dans le [guide de données](GUIDE_DONNEES.md). Le résultat des contrôles est disponible dans l'[audit](AUDIT_DONNEES.md).

## Les subtilités qui conditionnent une solution crédible

### 1. Un identifiant représente un emplacement, avec plusieurs vies d'appareil

`equipement_id` reste identique lors d'un remplacement. `date_pose` décrit l'appareil présent fin 2025. On compte 866 remplacements pour 846 identifiants, dont 20 remplacés plusieurs fois et 12 dans notre périmètre.

Il faut reconstruire la pose connue à chaque date de référence. Les symptômes, l'usure et les visites du cycle précédent ne sont pas automatiquement ceux du nouvel appareil. À fin 2024, le compteur de dépannages sur 12 mois du notebook contient **137 interventions antérieures au dernier remplacement pour 61 appareils du périmètre**. Garder cet historique comme contexte est possible, à condition de le distinguer de l'état du matériel actuel.

`date_pose_precedente` ne conserve qu'une pose précédente. Pour les validations anciennes, elle ne suffit pas toujours à retrouver le tout premier appareil. La bonne réaction est de signaler une histoire inconnue, pas d'inventer une date. Les validations 2023 et 2024 ne présentent pas d'âge négatif dans la baseline reproduite. En revanche, on en trouve 8 à fin 2018, 2 à fin 2019 et 1 à fin 2020.

### 2. Une validation dans le passé exige de reconstruire ce qui était connu

Filtrer les interventions est nécessaire, mais insuffisant. `nb_remplacements_2018_2025`, la rotation des occupants, le statut d'occupation actuel ou l'origine actuelle de la pose décrivent une situation fin 2025. Pour une validation à fin 2024, **79 appareils** ont un nombre de remplacements actualisé qui inclut le futur. **135 DPE** ont aussi été établis en 2025.

Les délais de résolution, clôtures, réouvertures et nombres d'échanges d'une demande peuvent être connus seulement après son ouverture. Au 31/12/2023, une demande ouverte avait une clôture future dans le fichier. Le nombre d'échanges et la réouverture ne disposent pas d'un journal permettant de les restituer exactement à une date passée.

Les rapports T2-T4 2025 sont disponibles pour la prédiction 2026. Les injecter dans une validation où l'on se place fin 2024 constituerait une fuite. Leur apport numérique ne peut pas être validé sur ce seul backtest, faute de rapports équivalents de 2024.

### 3. Les heures rendent les bornes du notebook trompeuses

Les interventions et demandes portent des heures. `<= '2024-12-31'` signifie minuit et exclut le reste de la journée : **9 interventions** sont ainsi omises à fin 2024. De même, la cible du notebook oublie un équipement positif du **30 septembre 2024**. En 2025, cette seconde erreur ne change pas le nombre de positifs, mais la méthode reste incorrecte.

Utiliser des intervalles explicites : historique `< 2025-01-01`, cible `>= 2025-01-01 et < 2025-10-01`. Pour le scoring final : historique `< 2026-01-01`. Les dates de pose et les heures des remplacements doivent être harmonisées sans supposer que des horaires simulés établissent une causalité.

### 4. Une demande ne désigne pas nécessairement un appareil

La table des demandes n'a pas de `equipement_id`. Seuls **368 des 9 955 dépannages** ont une demande liée, soit environ **3,7 %**. Leur absence ne signifie donc pas une absence de problème.

**370 logements** ont plusieurs équipements du périmètre : une demande d'eau chaude ne doit pas ajouter arbitrairement du risque à chaque équipement du logement. Utiliser le motif, le texte, la famille et le lien explicite d'intervention lorsqu'il existe. Conserver les rattachements incertains comme contexte.

Autre écart avec la description simplifiée du kit : les **968 demandes de parties communes possèdent toutes un `logement_id`**. Pour déterminer la portée d'une demande, il faut aussi lire `parties`, `motif` et son rattachement au bâtiment. Ne pas assimiler un logement renseigné à un problème privatif.

### 5. Les rapports sont partiels et résument parfois plusieurs vies

Les PDF couvrent six codes du contrat multiservices. Ils omettent notamment les ascenseurs, chaufferies collectives et installations ECS solaires. Un même code, `MUPPR`, couvre aussi dans les CSV des équipements hors contrat. Le filtre sur le code seul produit donc des écarts artificiels avec les rapports.

Les observations sont une sélection, pas un recensement exhaustif. Un appareil absent du PDF n'est pas déclaré sain. Certaines alertes résument neuf mois pendant lesquels l'appareil a été remplacé. Exemple : `EQP-01533` a été remplacé le 22 juillet 2025 et reste cité au T4. Il faut retrouver les événements datés avant d'attribuer toute l'usure résumée au matériel présent fin décembre.

Un PDF, un commentaire d'intervention et une demande peuvent décrire le même épisode. Les compter comme trois pannes indépendantes doublerait ou triplerait le signal.

### 6. Les données fictives portent des règles de fabrication

L'[onglet HYPOTHESES extrait](sources_lisibles/xlsx_HYPOTHESES.csv) documente une durée de vie simulée par loi de Weibull, une usure accentuée par les absences à l'entretien et les grands logements, une saisonnalité du chauffage et des signaux faibles pendant **10 à 20 mois** avant certaines fins de vie.

Ces mécanismes sont des hypothèses de simulation, pas des relations causales démontrées dans un patrimoine réel. L'âge de référence n'est pas une date certaine de panne. Les commentaires ne comptent que **18 formulations non vides distinctes**, ce qui favorise une détection de modèles de texte. Retrouver ces formulations peut aider dans le jeu, mais ne prouve pas la robustesse face aux comptes rendus réels.

Les absences doivent servir à préparer une visite accessible ou une relance adaptée. Elles ne justifient pas de blâmer les occupants ni de les priver de maintenance.

### 7. Les métriques du jury ne prouvent pas des pannes évitées

Entre janvier et septembre 2025, **76 équipements sur 1 285** ont connu au moins un arrêt total, soit **5,9 %**, pour 86 événements. Un classement peut avoir une AUC satisfaisante tout en trouvant peu de pannes dans les premières inspections.

La baseline d'âge relatif du notebook donne ici une **AUC de 0,777**. Avec une convention de 129 appareils pour le top 10 % et départage par identifiant, elle trouve **16 des 76 équipements positifs**, soit **12,4 % de précision** et **21,1 % de rappel**. Ces chiffres décrivent la baseline reproduite, avec ses limites, pas une solution finale.

La précision mesure les appareils qui tomberaient en panne dans l'historique observé. Elle ne démontre pas qu'une inspection aurait empêché la panne. L'efficacité préventive, les économies et la durée d'indisponibilité évitée nécessitent un pilote terrain et un protocole de comparaison. Les commandes sous-représentent en outre les dépannages sous contrat : leur total ne mesure pas le coût complet de maintenance.

Les petits effectifs de certaines familles et les rares positifs rendent les comparaisons instables. Ne pas annoncer une famille « sans risque » parce qu'elle n'a aucun arrêt sur une seule année.

## Une direction de solution simple et défendable

Proposition pour la suite, sans implémentation du modèle final dans cet audit :

1. Construire une table par équipement et par date de référence, avec une chronologie des remplacements et la disponibilité temporelle de chaque donnée.
2. Comparer l'âge relatif seul à un modèle tabulaire explicable simple. Ajouter progressivement les dépannages récents, leur gravité, les anomalies, les visites réellement réalisées et les signaux de texte. Mesurer l'apport de chaque famille de signaux.
3. Valider sur plusieurs périodes successives lorsque l'état passé est reconstructible. Garder la période janvier-septembre 2025 comme test final de développement. Entraîner uniquement sur des exemples dont les cibles sont déjà observées à la date de l'entraînement.
4. Restituer une liste d'inspection et une fiche d'équipement : date du score, raisons vérifiables, événements sources, qualité des informations, action proposée et décision humaine enregistrée.
5. Générer le CSV officiel à partir de la même table de résultats, avec contrôle des identifiants, de l'effectif, des doublons et des scores numériques finis.

Parcours cible : le coordinateur consulte la liste, ouvre une fiche, vérifie les raisons et la chronologie, puis valide un diagnostic, une visite ou une reprise d'entretien. Le prestataire renseigne le constat, ce qui enrichit le prochain calcul. Le nombre d'inspections doit rester compatible avec la capacité opérationnelle.

Un équipement collectif peut toucher plusieurs logements. Pour l'exploitation, afficher cette criticité à côté de la probabilité. Le classement soumis au jury reste celui du risque demandé. Une pondération d'impact modifie l'objectif et doit constituer une vue métier explicitement distincte.

La GenAI peut être utile pour structurer les observations et rédiger une explication fidèle à des faits déjà calculés. Chaque information extraite doit conserver sa source, sa date et son identifiant, avec possibilité de s'abstenir. Le document MBA privilégie un copilote en restitution ; le kit ouvre aussi une piste d'extraction d'alertes. Aucune architecture complexe ni aucun capteur IoT n'est un prérequis dans les données fournies. Un extracteur déterministe peut suffire pour les textes très répétitifs de ce kit.

## Questions ciblées à confirmer avec les organisateurs

- Les 10 % correspondent-ils à 128 ou 129 équipements ? Comment le jury départage-t-il les ex aequo et combine-t-il les deux métriques ?
- La baseline du jury utilise-t-elle l'âge absolu ou l'âge relatif, et des bornes de journées complètes ?
- Quelle date de disponibilité attribuer aux rapports trimestriels ? Peut-on obtenir des rapports antérieurs pour tester leur apport sans fuite ?
- Quelles actions sont réellement possibles après une alerte, avec quelle capacité d'inspection et quel délai utile ?
- Le livrable oral ou la démonstration ont-ils des critères supplémentaires ? Aucun barème complet de pitch n'est présent dans le dépôt.

Les règles du kit imposent de garder les données dans le cadre du hackathon et de valider humainement les décisions. Les extractions et calculs de cet audit restent dans le dépôt. Aucun envoi à un service externe n'a été effectué par les scripts d'analyse.

## Position retenue

Le projet à défendre est un **outil de préparation des inspections préventives, avec un risque expliqué au niveau de chaque équipement**. Sa crédibilité dépend surtout de la chronologie, du rattachement des signaux et d'une évaluation honnête de la valeur de la liste proposée. Une démonstration centrée sur ces éléments répond directement au besoin exprimé.
