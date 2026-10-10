# Modèle de prévention des pannes : choix et protocole

Recherche effectuée le 9 octobre 2026, uniquement pour le défi de prévention. Cette recommandation combine les sources techniques citées et l'audit du kit. Aucun des modèles proposés n'a encore été entraîné sur ces données : leur classement reste à mesurer.

**Choix de départ : un modèle tabulaire supervisé, avec EBM comme candidat privilégié pour l'explicabilité, et CatBoost comme concurrent pour la performance.** Comparer ces deux modèles à l'âge relatif et à une régression logistique régularisée. Ajouter TabPFN local seulement après avoir obtenu une comparaison fiable des premiers modèles.

Le « meilleur algorithme » sera celui qui améliore le classement sur des années ultérieures, avec des alertes compréhensibles et un coût de mise en œuvre raisonnable. Le benchmark [TabArena, accepté à NeurIPS 2025](https://arxiv.org/abs/2506.16791) montre que les arbres boostés restent compétitifs, que les modèles de fondation sont intéressants sur les petits jeux tabulaires et que le budget de calcul et la validation changent les conclusions. Il ne permet pas de désigner le gagnant sur BatIA.

## Ce que le modèle doit apprendre

Une ligne représente **un équipement à une date de référence**. Les variables décrivent uniquement ce qui était connu à cette date. La cible vaut 1 si cet identifiant connaît au moins un `Dépannage` avec `Arrêt total` entre le 1er janvier et le 30 septembre suivant, et 0 sinon.

Pour la soumission : informations antérieures au `2026-01-01`, événements à anticiper dans `[2026-01-01, 2026-10-01)`, exactement 1 285 scores. La cible concerne l'emplacement fonctionnel : un remplacement pendant l'horizon ne permet pas d'exclure arbitrairement les pannes suivantes de cet identifiant.

Le modèle est commun aux familles d'équipement, avec la famille comme variable. Les 2 équipements solaires, 5 chaufferies et 15 ascenseurs ne permettent pas d'apprendre chacun un modèle indépendant fiable. Les performances de ces petites familles doivent être décrites avec leurs effectifs.

Les détails du contrat et des sources se trouvent dans le [cadrage](CADRAGE_PREVENTION_PANNES.md), les [consignes originales](../DATA%202%20_le%20kit%20%C3%A9tudiants/BatIA_Kit_Hackathon/LISEZ-MOI_BatIA.pdf), page 2, et le [notebook extrait](sources_lisibles/BatIA_notebook_demarrage.md).

## Les candidats à comparer

| Candidat | Rôle dans notre protocole | Compromis |
| --- | --- | --- |
| Âge / durée de vie de référence | Référence obligatoire | Déjà performant dans le kit, mais ignore les symptômes |
| Régression logistique régularisée | Vérifier le gain d'un modèle très simple | Relations principalement linéaires, sauf transformations explicites |
| **EBM — Explainable Boosting Machine** | **Candidat privilégié pour la solution métier** | Apprend des effets non linéaires et quelques interactions directement lisibles |
| **CatBoostClassifier** | **Concurrent pour améliorer le classement** | Apprend des interactions plus complexes ; explications à ajouter et à défendre |
| TabPFN local | Concurrent facultatif après les précédents | Modèle récent, contraintes de calcul et explications plus indirectes |

EBM additionne des contributions apprises pour chaque variable, éventuellement complétées par des interactions entre deux variables. On peut donc montrer les courbes d'effet et les facteurs qui augmentent le score d'un appareil. Cette propriété convient à la demande « pas de boîte noire » du kit. L'équivalence de performance avec CatBoost sur nos données reste une hypothèse à tester. [Documentation officielle d'EBM](https://interpret.ml/docs/ebm.html).

CatBoost prend en charge les variables catégorielles, utiles pour la famille, le type de contrat et les symptômes. On les transmet comme catégories, sans fabriquer manuellement leur encodage à partir des cibles. [Documentation officielle de CatBoost](https://catboost.ai/docs/en/features/categorical-features).

CatBoost peut fournir des contributions SHAP par équipement. Elles expliquent le calcul du modèle ; elles ne prouvent pas qu'un facteur cause la panne. Ajouter SHAP ne transforme pas un ensemble d'arbres en modèle intrinsèquement transparent. Retenir CatBoost pour la restitution suppose que cette forme d'explication satisfasse l'exigence du jury. [Documentation SHAP de CatBoost](https://catboost.ai/docs/en/concepts/shap-values).

TabPFN est pertinent à examiner : ses auteurs ont publié des résultats sur les petits jeux tabulaires dans [Nature en 2025](https://www.nature.com/articles/s41586-024-08328-6). La version 3.5 a été publiée le 15 septembre 2026 ; ses nouveaux résultats viennent de son éditeur et ne constituent pas une validation sur nos données. [Publication officielle 3.5](https://priorlabs.ai/technical-reports/tabpfn-3-5).

Le dépôt officiel recommande environ 8 Go de mémoire GPU et distingue l'exécution locale du client cloud. Notre machine possède une RTX 3050 Laptop avec **4 096 MiB**, vérifiés par `nvidia-smi`. Une exécution peut demander des adaptations ; son impossibilité n'a pas été démontrée. Sur CPU, la configuration actuelle limite par défaut les versions récentes à 5 000 exemples, alors que plusieurs cohortes annuelles peuvent dépasser ce volume. Utiliser uniquement une exécution locale pour respecter le périmètre d'utilisation du kit. Les poids ont une licence distincte de celle du code. [Dépôt officiel TabPFN](https://github.com/PriorLabs/TabPFN).

## Préparer les variables avant de régler l'algorithme

Commencer avec environ 20 à 30 variables compréhensibles. Ce nombre est un budget de départ proposé, pas un optimum démontré.

| Bloc | Variables proposées | Précaution |
| --- | --- | --- |
| Usure | Âge réel à la date de référence, âge relatif, famille, durée de vie de référence | Retrouver l'appareil présent à cette date ; indiquer un âge inconnu si nécessaire |
| Dégradation récente | Dépannages sur 3, 6, 12 et 24 mois, gravités, délai depuis le dernier incident | Séparer la vie de l'appareil actuel des vies précédentes |
| Entretien | Visites effectuées, anomalies, absences rapportées aux visites observées | Une absence de ligne ne prouve pas une visite manquée |
| Symptômes | Présence et récence de symptômes dans les commentaires et demandes | Rattachement compatible avec la famille et preuves datées |
| Contexte stable | Surface ou typologie du logement, équipement privatif ou collectif | Utiliser les attributs reconstructibles à la date de référence |
| Historique de l'emplacement | Remplacements déjà observés, incidents de la vie précédente | Ne pas confondre cet historique avec l'usure du nouvel appareil |

Les fenêtres longues ont une raison propre au kit : les [hypothèses du classeur](sources_lisibles/xlsx_HYPOTHESES.csv) annoncent des signaux faibles 10 à 20 mois avant certaines fins de vie. Il faut tester leur apport réel plutôt que recopier la mécanique du générateur comme si elle décrivait parfaitement le terrain.

Les commentaires ne contiennent que 18 formulations non vides distinctes. Des indicateurs de symptômes et des règles de rapprochement simples sont un premier choix pratique. Un LLM peut ensuite extraire ou reformuler des preuves ; la prédiction doit rester reproductible et mesurable indépendamment de sa rédaction.

Écarter au départ les identifiants bruts et les champs de situation fin 2025 impossibles à reconstituer dans le passé : compteur global de remplacements, occupation actuelle, rotation ou information future de clôture. Garder les rapports 2025 comme éléments documentaires de l'alerte tant que leur apport prédictif ne peut pas être validé sur des rapports antérieurs comparables. Ne pas inventer de poids numérique pour compenser cette absence de validation.

## Tester dans le même sens que l'utilisation future

Construire une fonction unique de préparation, paramétrée par la date de référence. Tous les modèles utilisent les mêmes lignes, les mêmes variables disponibles et les mêmes découpages temporels. La documentation de [scikit-learn sur les fuites de données](https://scikit-learn.org/stable/common_pitfalls.html) rappelle que les transformations apprises et la sélection des variables doivent rester confinées à l'entraînement.

Proposition de découpage, sous réserve de vérifier la reconstruction des vies d'appareil :

| Étape | États utilisés pour apprendre | Cohorte évaluée | Pannes servant à l'évaluation |
| --- | --- | --- | --- |
| Validation A | Fins 2018 à 2021, avec cibles 2019 à 2022 | Fin 2022 | Janvier–septembre 2023 |
| Validation B | Fins 2018 à 2022, avec cibles 2019 à 2023 | Fin 2023 | Janvier–septembre 2024 |
| Test final réservé | Fins 2018 à 2023, avec cibles 2019 à 2024 | Fin 2024 | Janvier–septembre 2025 |

Les dates annuelles gardent le même horizon et la même saisonnalité que la soumission. Elles évitent aussi de multiplier artificiellement des lignes mensuelles dont les cibles sur neuf mois se chevauchent. Pour les toutes premières années, un historique de 24 mois est incomplet : ajouter sa durée observable et traiter explicitement les valeurs inconnues. Comparer éventuellement une variante limitée aux années suffisamment documentées sur les validations A et B.

Séparer des cohortes annuelles entières. Un partage aléatoire de lignes peut utiliser une année future pour apprendre à prédire une année passée. Appliquer directement un découpage temporel à des lignes triées sans respecter les cohortes n'est pas suffisant non plus. Le même équipement peut légitimement apparaître à plusieurs années : l'usage visé consiste à prédire l'avenir du patrimoine connu. Un test sur une résidence exclue mesurerait une autre question, celle du transfert vers un patrimoine nouveau.

Le test 2025 a déjà servi à examiner la baseline d'âge. Il peut encore servir de test final des nouveaux modèles s'il n'est plus utilisé pour choisir leurs variables ou réglages ; il faut déclarer cette exploration préalable. Tout réglage motivé par ses résultats en ferait une validation supplémentaire, plus un test réservé.

Après avoir fixé le choix et les paramètres, réentraîner avec toutes les cohortes dont les cibles sont connues, y compris les pannes de janvier–septembre 2025. Puis préparer l'état fin 2025 pour scorer 2026. Ne pas réentraîner sur une cible 2026 encore inconnue.

## Mesurer le gain qui compte

L'[audit local](AUDIT_DONNEES.md) a mesuré, sur janvier–septembre 2025, **76 équipements positifs sur 1 285**, soit 5,9 %. La baseline d'âge relatif atteint **0,777 d'AUC** et retrouve **16 équipements avec panne parmi les 129 premiers**, soit 12,4 % de précision. Ce sont des résultats historiques sur données fictives, pas des performances annoncées pour 2026.

Pour chaque candidat, conserver l'AUC et la précision parmi les 10 % les plus à risque, critères du kit. Ajouter le nombre de pannes retrouvées, le rappel de ce groupe, et l'average precision pour examiner le classement des cas rares. Prendre `ceil(0,10 × N)` pour notre comparaison et documenter cette convention ; l'arrondi exact du jury n'est pas précisé. [Documentation officielle des métriques](https://scikit-learn.org/stable/modules/model_evaluation.html).

Un modèle répondant toujours « aucune panne » aurait environ 94,1 % de bonnes réponses sur cette année : cette accuracy ne mesure pas la qualité de notre priorisation. Un seuil de 0,5 n'a pas non plus de raison de définir les inspections prioritaires.

Sur les deux validations, ajouter les variables par blocs : âge ; puis interventions ; puis entretien ; puis symptômes et contexte. Conserver les blocs qui améliorent le classement de façon suffisamment stable. Examiner les erreurs, notamment les remplacements récents et les rares équipements collectifs. Tester plusieurs graines sur les finalistes pour repérer un classement instable ; cela ne remplace pas la diversité des années.

## Régler peu de paramètres et choisir une solution défendable

Pour commencer, limiter EBM aux effets individuels, puis tester quelques interactions justifiées, comme âge relatif × famille et âge relatif × symptômes. Tester CatBoost avec des arbres de profondeur modérée, par exemple 3 à 6, une régularisation et un arrêt anticipé piloté sur une cohorte ultérieure. Ces valeurs sont des points de départ proposés. Les [paramètres CatBoost](https://catboost.ai/docs/en/concepts/parameter-tuning) permettent ce réglage.

Vérifier aussi les mécanismes internes de validation : EBM prévoit par défaut une fraction de validation pour son arrêt anticipé. Une solution simple est de désactiver cet arrêt interne et de régler le nombre d'itérations sur les validations annuelles externes ; une autre consiste à configurer explicitement des partitions compatibles. La procédure et le coût en calcul doivent être documentés. [API officielle EBM](https://interpret.ml/docs/python/api/ExplainableBoostingClassifier.html).

Commencer sans rééquilibrage automatique des classes. Tester une pondération seulement si elle améliore les critères temporels ; elle ne garantit pas un meilleur classement et peut modifier le sens probabiliste du score. Une recherche restreinte, par exemple une vingtaine de configurations par candidat, est un budget pratique de hackathon, pas une preuve d'optimalité.

Retenir EBM si les performances sont proches ou variables selon l'année. Retenir CatBoost pour la solution métier si le gain est net et stable et si ses explications répondent à l'exigence du jury. Un ensemble de modèles ne devient utile que s'il améliore les validations et reste explicable ; il ajoute sinon du travail sans bénéfice démontré. Ne pas déclarer un gagnant après avoir essayé de nombreux réglages sur le test final.

## Transformer le classement en prévention

Le score sert d'abord à classer. Pour afficher une « probabilité de panne de 23 % », vérifier sa calibration sur des cohortes chronologiques distinctes de celles d'entraînement et du test final. Une calibration sigmoidale est un premier candidat quand les positifs sont peu nombreux ; l'isotonique exige davantage de données. Sans cette vérification, afficher un score relatif. [Documentation de la calibration](https://scikit-learn.org/stable/modules/calibration.html).

Pour chaque alerte, restituer l'équipement, ses principaux facteurs, les dates et sources des observations, la qualité du rattachement, et une action proposée : inspection ciblée, contrôle d'entretien ou vérification d'un symptôme. Les contributions d'EBM ou de SHAP ne doivent pas être présentées comme des points de pourcentage sans la transformation appropriée.

Le volume d'inspections détermine combien d'appareils retenir. La criticité d'un équipement collectif peut servir à organiser les interventions, à côté du risque de panne. Elle ne doit pas modifier silencieusement le classement soumis au jury. La mesure des pannes réellement évitées demandera ensuite un suivi des actions ; une AUC ne prouve pas cet effet.

L'analyse de survie serait intéressante pour prédire à plusieurs horizons et gérer les événements censurés. C'est une extension possible, pas notre premier chantier : les vies successives, remplacements et pannes récurrentes nécessitent de définir correctement l'événement étudié. La classification à neuf mois correspond directement au barème actuel. [Introduction officielle à l'analyse de survie](https://scikit-survival.readthedocs.io/en/stable/user_guide/00-introduction.html).

## Livrables à produire pour passer à l'entraînement

1. Table des états historiques et cibles, avec contrôles des dates, remplacements et données inconnues.
2. Comparatif des quatre premiers candidats sur les mêmes validations, avec gain par bloc de variables.
3. Choix fixé avant le test final, puis modèle et résultats reproductibles avec versions et paramètres enregistrés.
4. CSV final des 1 285 scores, contrôlé pour les identifiants, doublons et valeurs finies.
5. Fiches d'alerte avec facteurs, preuves datées et action validable par une équipe technique.

Les fichiers sources n'ont pas été envoyés à un service externe. Cette recherche a consulté uniquement des publications et documentations publiques. L'entraînement et la soumission restent à réaliser.
