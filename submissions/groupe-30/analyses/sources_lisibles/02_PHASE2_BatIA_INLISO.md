# Source : DATA 2 _le kit étudiants\DATA_MBA\02_PHASE2_BatIA_INLISO.pdf
Pages : 23

## Page 1

BâtIA, Phase 2, Groupe 6   |   Page 1 
OneMBA, Global Residency Asia 2026 
Groupe 6, Cours d'Intelligence Artificielle, Prof. Rod Togneri 
PHASE 2 
BâtIA 
Assistant IA de priorisation des rénovations et de maintenance 
prédictive pour le logement intermédiaire 
Stratégie, ingénierie et management de la solution retenue 
 
 
 
 


## Page 2

BâtIA, Phase 2, Groupe 6   |   Page 2 
 
 
Sommaire 
1. Nom du projet ................................ ................................ ................................ ................................  3 
2. Secteur sélectionné ................................ ................................ ................................ ........................  3 
3. Lien entre le secteur et les ODD ................................ ................................ ................................ ...... 4 
4. Lien entre la solution et les ODD ................................ ................................ ................................ ..... 4 
5. Défis identifiés ................................ ................................ ................................ ...............................  5 
6. Résumé des solutions et techniques d'IA applicables ................................ ................................ ....... 6 
7. Cas d'usage IA et conclusions clés ................................ ................................ ................................ ... 7 
8. Solution retenue (Chosen Solution) ................................ ................................ ................................ . 9 
9. Plan stratégique ................................ ................................ ................................ ............................  11 
10. Plan de mise en œuvre (AI Engineering) ................................ ................................ .......................  14 
11. Plan de management ................................ ................................ ................................ ................... 18 
12. Considérations éthiques et de responsabilité................................ ................................ ................ 20 
13. Conclusion ................................ ................................ ................................ ................................ .. 21 
14. Glossaire ................................ ................................ ................................ ................................ ..... 22 
15. Références ................................ ................................ ................................ ................................ .. 22 

## Page 3

BâtIA, Phase 2, Groupe 6   |   Page 3 
 
1. Nom du projet 
BâtIA, Assistant de priorisation des rénovations et de maintenance prédictive pour le logement intermédiaire. 
Ce nom, retenu dès la Phase 1, est conservé sans modification pour la Phase 2 : il continue de refléter fidèlement 
le périmètre de la solution retenue comme Chosen Solution (section 8), à savoir le duo priorisation des rénovations 
et maintenance prédictive, présenté comme un bloc unique et non dissociable. 
2. Secteur sélectionné 
2.1 Vue d'ensemble du secteur 
Le logement intermédiaire désigne les logements destinés aux ménages dont les revenus sont trop élevés pour 
accéder au logement social, mais insuffisants pour se loger décemment dans le parc privé. En France, ce segment 
est porté par des bailleurs institut ionnels tels qu'Action Logement, In'li, CDC Habitat ou Vivest , avec des loyers 
encadrés généralement 10 à 20 % sous le prix du marché local. Dans les zones urbaines tendues, cette classe 
moyenne active peine à se loger près de son bassin d'emploi, ce qui pèse sur la mobilité professionnelle et 
l'attractivité économique des territoires. 
Le parc immobilier concerné est souvent ancien, avec des performances énergétiques hétérogènes, et les bailleurs 
doivent arbitrer entre plusieurs centaines de logements à rénover avec des budgets contraints. La décision repose 
aujourd'hui largement sur des  visites terrain et des tableurs, sans consolidation automatisée des données, c'est 
précisément ce vide que BâtIA cherche à combler. 
2.2 In'li Sud-Ouest et Action Logement 
In'li Sud-Ouest est une filiale régionale d'In'li, elle-même filiale du groupe Action Logement, un acteur institutionnel 
français majeur du logement lié à l'emploi, financé par une contribution obligatoire des employeurs. In'li intervient 
spécifiquement dans les zones tendues, où l'offre de logement à l'année peine à répondre à la demande. Sur ce 
segment, In'li est propriétaire et gestionnaire de son parc résidentiel et directement responsable des décisions de 
rénovation et de maintenance que BâtIA vise à accompagner. 
Ces enjeux se mesurent à une échelle réelle et significative. In'li Sud-Ouest gère un patrimoine de 6 000 logements 
locatifs en Occitanie et en Nouvelle-Aquitaine (métropoles de Toulouse, Montpellier et Bordeaux notamment), ce 
qui définit l'échelle du Palier 1 et du Palier 2 de déploiement (section 9.2). À l'échelle nationale, le groupe Action 
Logement gère un patrimoine de 1,2 million de logements sociaux et intermédiaires, dont près de 80 000 logements 
intermédiaires portés par le groupe In'li, c'est l'échelle potentielle du Palier 3 (mutualisation groupe), qui donne au 
projet BâtIA une perspective de réplicabilité bien au-delà de son périmètre pilote initial.1 
Pour la Phase 2, ce positionnement est précisé : la solution est développée comme si elle était proposée en interne 
à In'li Sud -Ouest, dans une posture de collaborateur ou de consultant porteur d'un projet d'innovation, et non 
comme une startup externe cherchant à vendre un produit non éprouvé. Ce choix conditionne l'ensemble du plan 
stratégique et du plan de management développés dans ce document. 
2.3 Une problématique internationale 
Ce phénomène n'est pas propre à la France : chaque pays représenté dans l'équipe dispose d'un dispositif 
comparable, à des degrés de maturité et de déploiement différents, ce qui confirme que le « chaînon manquant » 
entre logement social et marché libre es t une tendance de fond. Cette comparaison internationale reste 
 
1Chiffres de patrimoine : sites institutionnels In'li Sud-Ouest (inli-sudouest.fr) et In'li (inli.com) ; patrimoine du groupe Action 
Logement (1,2 million de logements sociaux et intermédiaires) : Action Logement, communiqué de résultats 2025 
(groupe.actionlogement.fr). 

## Page 4

BâtIA, Phase 2, Groupe 6   |   Page 4 
volontairement synthétique : l'ensemble du projet, en Phase 1 comme en Phase 2, est développé autour du cas 
français.2 
Pays Dispositif équivalent 
France Logement Locatif Intermédiaire (LLI), loyers 10 à 20 % sous le marché, géré par des 
bailleurs institutionnels (Action Logement, In'li, CDC Habitat, Vivest). 
Brésil Minha Casa Minha Vida, nouvelle Faixa 4 (2026) ouverte aux ménages jusqu'à 13 000 
R$/mois avec taux d'intérêt réduits. 
Maroc Logement Locatif Intermédiaire marocain, projets pilotes dès 2026 à Casablanca, Rabat, 
Marrakech et Tanger. 
Chine Logement en copropriété partagée (共有产权房), introduit à Pékin en 2017 et étendu à 
d'autres grandes villes. 
Soudan Khartoum State Housing Development Fund (KSHDF), plus de 41 000 unités construites 
via un mécanisme de subventions croisées. 
 
3. Lien entre le secteur et les ODD 
Indépendamment de toute solution technologique, le secteur du logement intermédiaire se rattache 
structurellement à deux Objectifs de Développement Durable, du seul fait de son objet social. Tout acteur de ce 
secteur, In'li, CDC Habitat, Vivest, ou tout autre bailleur comparable, contribuerait à ces deux ODD, avec ou sans 
BâtIA. 
ODD Cible mobilisée Justification 
ODD 11 — Villes et 
communautés durables 
Cible 11.1 : accès pour tous 
à un logement adéquat et 
abordable 
Cœur du secteur : le logement intermédiaire 
existe précisément pour répondre à cette cible, 
en logeant les ménages qui ne trouvent leur 
place ni dans le logement social ni sur le marché 
libre. 
ODD 10 — Réduction des 
inégalités 
Cible 10.2 : autonomiser et 
favoriser l'inclusion sociale, 
économique et politique de 
tous 
Le logement intermédiaire cible spécifiquement 
une population aux revenus trop élevés pour le 
logement social mais insuffisants pour le 
marché libre — une réduction d'inégalité 
d'accès au logement inhérente à la définition 
même du secteur. 
 
Ces deux ODD constituent donc le socle sectoriel du projet, indépendant de la nature de la solution retenue. La 
section suivante précise la contribution propre de BâtIA, en tant que solution IA spécifique, à des ODD distincts de 
ceux du secteur. 
4. Lien entre la solution et les ODD 
Au-delà des ODD sectoriels identifiés en section 3, BâtIA apporte une contribution propre à trois ODD 
supplémentaires, directement liés à l'usage de l'intelligence artificielle plutôt qu'à la nature du secteur lui-même. 
 
2Données compilées par les membres de l'équipe à partir de sources nationales officielles et institutionnelles propres à chaque pays 
représenté dans l'équipe (voir Annexe IA pour le détail des recherches). 

## Page 5

BâtIA, Phase 2, Groupe 6   |   Page 5 
ODD Cible mobilisée Justification Thème associé 
ODD 7 — Énergie 
propre et d'un coût 
abordable 
Cible 7.3 (efficacité 
énergétique) et cible 7.2 
(part des énergies 
renouvelables) 
Le scoring de priorisation cible en 
priorité les rénovations à fort impact 
énergétique (cible 7.3). Le périmètre 
des interventions priorisables par BâtIA 
peut également couvrir des 
installations d'énergie renouvelable — 
panneaux photovoltaïques en toiture,  
géothermie pour le chauffage collectif, 
ou raccordement à un réseau de 
chaleur urbain — ce qui mobilise aussi 
la cible 7.2, et non la seule efficacité 
énergétique. 
Construction 
et 
maintenance 
ODD 13 — Lutte 
contre les 
changements 
climatiques 
Cible 13.2 : intégrer des 
mesures climatiques 
dans les politiques et 
stratégies 
Conséquence directe de l'ODD 7 : moins 
de bâtiments énergivores et davantage 
d'énergies renouvelables signifient 
moins d'émissions carbone à l'échelle 
du parc. 
Construction 
et 
maintenance ; 
Logistique et 
finance 
ODD 9 — Industrie, 
innovation et 
infrastructure 
Cible 9.4 : moderniser les 
infrastructures et 
adapter les industries 
existantes pour les 
rendre durables, avec 
une utilisation des 
ressources plus efficiente 
et un recours accru aux 
technologies propres 
Le scoring de priorisation oriente les 
investissements de rénovation vers la 
modernisation d'un bâti existant — 
infrastructure au sens de la cible 9.4 — 
plutôt que vers un enjeu d'accès aux 
technologies de l'information (cible 9.c, 
écartée car plus éloignée du cœur de la 
solution). BâtIA  rend cette 
modernisation plus efficiente en 
priorisant les interventions selon leur 
impact réel. 
Construction 
et 
maintenance 
 
Pour la Chosen Solution développée à partir de la section 8 (priorisation des rénovations et maintenance 
prédictive), les trois ODD de solution (7, 9, 13) sont directement mobilisés, aux côtés de l'ODD 11 sectoriel. L'ODD 
10, sectoriel mais non directement  solution, reste davantage porté par les extensions futures orientées 
communication et accompagnement des locataires (chatbot, section 8.4) que par le cœur technique de BâtIA. 
5. Défis identifiés 
Au-delà du déficit quantitatif de logements intermédiaires, les bailleurs et opérateurs de ce segment font face à 
des défis opérationnels précis, qui constituent autant de points d'entrée pour une solution basée sur l'IA. Ces défis 
sont regroupés en trois grandes catégories : construction et maintenance, logistique et finance, puis 
communication. 
Construction et maintenance 
● Priorisation des rénovations, vieillissement du parc existant, coûts de rénovation énergétique élevés, 
difficulté à prioriser les interventions faute de données consolidées. 
● Maintenance prédictive plutôt que curative, pannes découvertes trop tardivement (plomberie, chauffage, 
ascenseurs), générant des coûts d'urgence et une insatisfaction des locataires. 
● Absence de diagnostic précoce, absence d'outils de détection précoce des dégradations du bâti, alors que 
des signaux faibles précèdent souvent une panne majeure de plusieurs semaines. 

## Page 6

BâtIA, Phase 2, Groupe 6   |   Page 6 
Ces trois défis s'articulent en réalité comme un seul cercle vicieux : sans priorisation objectivée, les rénovations se 
font par ordre chronologique ou selon l'urgence apparente ; sans diagnostic précoce, une dégradation mineure 
évolue en panne majeure ava nt d'être détectée ; et cette réactivité permanente absorbe des ressources qui 
auraient pu financer une rénovation préventive. C'est ce cercle que la Chosen Solution (section 8) vise directement 
à rompre. 
Logistique et finance 
● Financement et arbitrage budgétaire, les rénovations engagent des budgets contraints ; les bailleurs ont 
besoin d'un calcul de retour sur investissement fiable pour arbitrer entre projets concurrents. 
● Chaîne d'approvisionnement, approvisionnement en matériaux de rénovation à coûts et délais maîtrisés, 
en particulier pour les matériaux durables. 
● Choix des matériaux non optimisé, sélection principalement fondée sur le coût d'achat initial, sans prise 
en compte suffisante du cycle de vie complet. 
Ces défis logistiques et financiers ne sont pas indépendants du thème précédent : une meilleure priorisation des 
rénovations rend également les arbitrages budgétaires plus objectivables, puisqu'elle fournit un critère de 
classement commun à des projets par ailleurs difficiles à comparer entre eux (un ravalement de façade contre le 
remplacement d'une chaudière collective, par exemple). 
Communication 
● Communication locataires, manque de canal direct et réactif entre locataires et bailleur pour signaler les 
problèmes ou suivre l'avancement des travaux. 
Ce défi a une dimension double : il pénalise la qualité de service perçue par les locataires, mais il représente aussi 
une perte d'information pour le bailleur, puisque les locataires sont souvent les premiers témoins de signaux faibles 
(bruit inhabituel, humidité, baisse de performance d'un équipement) qui pourraient enrichir un dispositif de 
diagnostic précoce s'ils étaient mieux capturés. 
Pour la Phase 2, le thème Construction et maintenance constitue le périmètre direct de la Chosen Solution. Les 
thèmes Logistique et finance ainsi que Communication restent documentés dans ce rapport pour la cohérence 
d'ensemble du projet, mais sont traités comme des enjeux connexes plutôt que comme l'objet du plan d'ingénierie 
et de déploiement détaillé en sections 10 à 12. 
6. Résumé des solutions et techniques d'IA applicables 
Cette section met en correspondance les défis identifiés en section 5 avec l'éventail des solutions IA ou d'aide à la 
décision envisageables pour chacun, et la famille de technique applicable. L'objectif est de montrer la diversité des 
alternatives considérées sur les trois thèmes, avant que la section 8 n'explique quelle solution a été retenue pour 
l'approfondissement, et que les sections 8.3 et 10 ne détaillent comment elle est mise en œuvre pour BâtIA en 
particulier. 
Défi métier Solution IA 
envisageable Technique applicable Ce qu'elle ferait 
Détection tardive des 
pannes d'équipement 
Maintenance 
prédictive 
ML prédictif sur données 
historiques structurées ; 
analyse de séries 
temporelles si capteurs 
disponibles 
Estimer la probabilité et 
l'horizon de survenue 
d'une panne 
Absence de diagnostic 
précoce de la 
dégradation du bâti 
Détection précoce / 
anomalies 
Détection de signaux 
faibles sur données 
structurées et historiques 
(analogie diagnostic 
médical) 
Signaler un écart avant 
qu'il ne devienne une 
panne majeure 

## Page 7

BâtIA, Phase 2, Groupe 6   |   Page 7 
Défi métier Solution IA 
envisageable Technique applicable Ce qu'elle ferait 
Difficulté à prioriser les 
rénovations sur un grand 
parc 
Aide à la décision pour 
la priorisation 
Scoring multicritère 
explicable, pondéré par les 
équipes métier 
Classer les bâtiments 
selon un critère combiné 
technique, énergétique, 
coût et urgence 
Arbitrage budgétaire et 
financement 
Modèle de ROI 
automatisé / tableau 
de bord financier 
Aide à la décision par 
optimisation 
Comparer des projets de 
rénovation concurrents 
sur une base coût -
bénéfice 
Maîtrise des coûts et 
délais 
d'approvisionnement 
Recommandation de 
matériaux 
Optimisation / aide à la 
décision multicritère 
Recommander 
fournisseurs ou matériaux 
selon coût, durabilité et 
délai 
Choix des matériaux 
fondé sur le seul coût 
initial 
Aide à la décision sur 
le coût du cycle de vie Optimisation multicritère 
Arbitrer entre coût initial 
et coût sur cycle de vie 
complet 
Absence de canal direct 
de communication avec 
les locataires 
Chatbot locataires GenAI conversationnelle 
Collecter et structurer les 
signalements ; informer 
sur l'avancement des 
demandes 
 
Trois familles de techniques reviennent dans cette cartographie, et méritent d'être distinguées sur le plan 
conceptuel avant d'être discutées dans le contexte d'une solution particulière : 
● Machine Learning : un modèle qui apprend à estimer un résultat, par exemple la probabilité et l'horizon 
de survenue d'une panne, à partir de données historiques structurées, sans que chaque règle soit 
programmée explicitement. 
● Scoring multicritère : un mécanisme d'aide à la décision, pas du Machine Learning au sens strict, dont les 
critères et les pondérations sont définis et gouvernés par les équipes métier plutôt qu'appris 
automatiquement, même s'il s'appuie sur des données structurées. 
● GenAI : utilisée ici dans un rôle d'interprétation et de communication, transformant un résultat technique 
en explications en langage naturel, plutôt que dans un rôle de prédiction ou de décision. 
La section 8 explique pourquoi la combinaison priorisation des rénovations et maintenance prédictive a été retenue 
comme BâtIA, la Chosen Solution du projet, parmi cet éventail plus large d'options. Les sections 8.3 et 10 détaillent 
ensuite comment chacune de ces trois familles de techniques est concrètement mise en œuvre, validée et 
gouvernée pour BâtIA. 
7. Cas d'usage IA et conclusions clés 
Plusieurs cas d'usage, issus du secteur du bâtiment comme d'autres industries, viennent nourrir et valider les choix 
techniques de BâtIA. 
● Secteur du logement en France, l'Union sociale pour l'habitat (USH) a publié en 2025 une étude 
cartographiant les cas d'usage de l'IA sur l'ensemble de la chaîne de valeur du logement social et 
intermédiaire, confirmant que la profession identifie la rénov ation et la maintenance comme un terrain 
prioritaire d'application de l'IA.3 
 
3Union Sociale pour l'Habitat, « Intelligence artificielle (IA) et logement social : les cas d'usages appliqués à la maîtrise d'ouvrage et 
au patrimoine », Repères n°143, 11 février 2025. 

## Page 8

BâtIA, Phase 2, Groupe 6   |   Page 8 
Deux bailleurs sociaux français, Vilogia et Domofrance , illustrent concrètement le principe retenu en section 9.1 
(maîtrise d'ouvrage interne, développement par un prestataire externe) : ils pilotent leurs propres projets d'IA 
appliqués à la gestion patrimoniale tout en faisant développer la brique technique par un partenaire spécialisé. 
L'enseignement pour BâtIA n'est pas seulement organisationnel : il confirme que le modèle MOA/MOE retenu en 
section 9.1 n'est pas une solution de repli faute de compétences internes, mais une pratique déjà éprouvée par 
des pairs directs du secteur, ce qui renforce la crédibilité du positionnement stratégique de ce rapport. 
 
Les quatre domaines d'application de l'IA identifiés par l'étude USH (2025) 
● Smart building, les plateformes de gestion technique de bâtiment couplées à l'IA, telles qu'EcoStruxure  
Building de Schneider Electric, démontrent que la combinaison de capteurs IoT et de modèles prédictifs 
réduit significativement les coûts de maintenance. L'enseignement principal pour BâtIA est la nécessité 
d'une architecture de collecte de données robuste avant même de sophistiquer les modèles prédictifs.4 
 
Principe générique du smart building : capteurs IoT et modèle prédictif (schéma original) 
● Chatbot / assistance client, les grandes plateformes d'e -commerce montrent qu'un principe de « filet de 
sécurité humain » est indispensable pour l'acceptabilité d'un canal conversationnel. 
Ce cas appelle toutefois une réserve critique avant transposition à BâtIA : un chatbot e -commerce répond à des 
demandes largement standardisables (suivi de commande, retour produit), alors qu'un signalement locataire porte 
souvent sur une situation ambiguë (bruit, humidité, dysfonctionnement partiel) que le locataire lui-même a du mal 
à qualifier précisément. Le « filet de sécurité humain » devrait donc, pour BâtIA, intervenir plus tôt dans le parcours 
qu'en e-commerce, une nuance à intégrer si ce chatbot est développé au-delà du périmètre de la Phase 2 (section 
8.4). 
● Scoring financier, les modèles de scoring de risque utilisés en finance, tels que les modèles de type RiskCalc, 
montrent l'importance de la transparence et de l'explicabilité pour l'acceptation par des décideurs non -
techniques, un enseignement central pour le plan d'ingénierie de la section 10.5 
La limite de ce parallèle est également à noter : un scoring de crédit s'appuie sur des historiques de défaut de 
paiement massifs et standardisés à l'échelle d'un marché entier, alors que le scoring de risque de panne de BâtIA  
devra, au moins au Palier 1, se construire sur l'historique propre et plus limité du seul parc d'In'li Sud -Ouest. La 
 
4Schneider Electric, « Artificial Intelligence solutions and AI use cases », se.com, page produit EcoStruxure / IA, consultée en 2026. 
5Cf. lecture préparatoire du cours OneMBA sur les modèles de credit scoring (Moody's RiskCalc, Prof. Jeunghyun Kim). 


## Page 9

BâtIA, Phase 2, Groupe 6   |   Page 9 
méthode (scoring explicable, pondération transparente) est transposable ; le volume et la maturité des données 
disponibles, non, ce qui justifie l'attention portée à la validation rétrospective du modèle avant tout déploiement 
(section 10.5). 
● Santé / diagnostic prédictif, un risque détecté tôt réduit drastiquement le coût et la gravité d'une 
intervention ultérieure ; le retour sur investissement d'un outil prédictif se mesure autant en évitement 
de coûts qu'en gain de qualité de service. 
Synthèse des défis, techniques et cas d'usage 
Thème Technique IA associée 
Priorisation des rénovations Scoring multicritère explicable (mécanisme de 
décision, pas du Machine Learning) 
Maintenance prédictive Prédiction de pannes par séries temporelles ou 
données structurées (ML) 
Absence de diagnostic précoce Détection de signaux faibles (ML), analogie diagnostic 
médical 
Financement et arbitrage Modèle de ROI automatisé, tableau de bord financier 
Communication locataires Chatbot conversationnel (GenAI) 
 
Conclusion clé retenue pour la Phase 2 : la priorité opérationnelle n'est pas le choix d'un algorithme 
sophistiqué, mais la structuration d'une base de données fiable et un scoring explicable, c'est ce principe qui 
structure l'ensemble du plan d'ingénierie développé en section 10. 
 
8. Solution retenue (Chosen Solution) 
8.1 Périmètre exact et justification du choix 
La solution retenue pour la Phase 2 est le duo priorisation des rénovations et maintenance prédictive, traité comme 
un bloc unique et non dissociable : le scoring de priorisation utilise le risque de panne comme intrant, et la 
maintenance prédictive alimen te en retour ce scoring , il s'agit d'un seul moteur de données avec deux sorties 
opérationnelles, plutôt que de deux solutions juxtaposées. 
Ce choix est cohérent avec le nom même du projet, avec les ODD sectoriels et de solution identifiés en sections 3 
et 4, et avec la décision prise dès la Phase 1 de privilégier des techniques d'IA défendables (scoring explicable, 
analyse de données structurées) plutôt que des architectures plus sophistiquées mais plus difficiles à justifier. 
Le module de recommandation de matériaux durables et le chatbot locataires sont volontairement relégués au 
rang d'extensions futures (section 8.4) : ils enrichiraient le dispositif mais ne constituent pas son cœur fonctionnel, 
et leur inclusion dans le pér imètre d'ingénierie détaillé aurait dilué la profondeur d'analyse exigée par le barème 
de la Phase 2. 
8.2 Proposition de valeur 
Pour In'li Sud-Ouest, la proposition de valeur de BâtIA se résume en trois bénéfices mesurables : 
● Réduction du coût de maintenance : substitution progressive d'une part des interventions d'urgence, 
structurellement plus coûteuses, par des interventions planifiées. 

## Page 10

BâtIA, Phase 2, Groupe 6   |   Page 10 
● Optimisation du budget de rénovation : allocation des enveloppes disponibles vers les bâtiments où 
l'impact énergétique et le risque de panne sont les plus élevés, plutôt que selon une logique d'urgence 
apparente ou d'ordre chronologique. 
● Traçabilité et défendabilité des choix : un scoring  explicable permet de justifier chaque arbitrage de 
rénovation auprès des équipes internes, de la direction, et le cas échéant des financeurs publics. 
Ces bénéfices restent volontairement présentés en termes qualitatifs plutôt que chiffrés à ce stade : le secteur du 
logement social et intermédiaire commence seulement à s'outiller sur ce type de solution, comme le montre 
l'étude USH citée en section 7, et  aucune donnée chiffrée propre au parc résidentiel français n'est encore 
publiquement disponible pour étayer un ordre de grandeur fiable. L'ampleur réelle des gains devra être mesurée 
directement sur le périmètre du Palier 1 (section 9.2), selon le cadre d 'évaluation économique détaillé en section 
9.6, plutôt qu'estimée par extrapolation d'études portant sur d'autres secteurs ou d'autres pays. 
Cette proposition de valeur est transposable, avec adaptation du paramétrage, à tout bailleur de logement 
intermédiaire ou social gérant un parc de taille comparable, ce qui ouvre, à moyen terme, une logique de solution 
mutualisable au sein d'Action Logement plutôt que strictement propriétaire d'In'li Sud-Ouest. 
8.3 Rôle de la GenAI dans la solution : un copilote ancré dans les données 
Conformément à la thématique (GenAI-Driven Business Transformation), la GenAI n'est pas cantonnée à un usage 
périphérique de mise en forme de texte : elle constitue une composante à part entière de l'architecture de BâtIA, 
positionnée dans la couche de res titution (section 10.6) plutôt que dans le moteur de scoring lui -même, dont le 
rôle reste tenu par le Machine Learning et le scoring multicritère (section 6). 
Ce copilote GenAI joue trois rôles, tous ancrés dans les données propres à In'li Sud -Ouest plutôt que dans une 
connaissance générale non vérifiée : 
● Synthèse contextualisée : il récupère l'historique de maintenance, les diagnostics de performance 
énergétique et les recommandations de scoring d'un bâtiment donné, et les restitue sous forme de 
synthèse rédigée, compréhensible par une équipe terrain non data scientist. 
● Explication interactive du score : un manager peut interroger le copilote en langage naturel sur les raisons 
d'un classement donné (« pourquoi ce bâtiment est -il prioritaire par rapport à celui -ci ? »), le copilote 
reformulant alors les critères et pondérations du scoring sans jamais recalculer ni modifier le résultat lui-
même. 
● Rédaction assistée de comptes rendus : génération d'une première version de compte rendu de visite ou 
de note de synthèse à destination de la direction, à partir des données du dossier, systématiquement relue 
et validée par un humain avant diffusion (principe posé en section 12.4). 
Ce choix de conception répond à une exigence de fiabilité : la GenAI reste ancrée aux données et documents 
propres à In'li Sud-Ouest, historiques de maintenance, diagnostics, résultats du scoring, plutôt que de générer une 
réponse à partir de sa seule connaissance générale, ce qui limite le risque d'erreur factuelle sur un sujet où la 
fiabilité de l'information conditionne une décision de rénovation. La décision elle -même reste entièrement 
produite par le scoring multicritère et l'analyse prédictive décrits en section 10.3 : la GenAI n'intervient qu'en aval, 
sur l'interprétation et la communication du résultat, jamais sur son calcul. 
Ce positionnement diffère de celui du chatbot  locataires (section 8.4) : ce dernier reste une extension future, 
orientée collecte de signalements côté locataires, alors que le copilote de reporting décrit ici fait partie du 
périmètre d'ingénierie de la Phase 2, au même titre que le moteur de scoring. 
8.4 Extensions futures hors périmètre Phase 2 
● Chatbot locataires (GenAI) : canal de signalement et de suivi, positionné comme source future de données 
qualitatives pour affiner le scoring. 
● Recommandation de matériaux durables : module d'aide à la décision technique, envisageable une fois le 
moteur de scoring principal stabilisé et adopté. 
● Modèle de ROI automatisé et tableau de bord financier : extension naturelle du scoring vers les équipes 
finance, à développer après validation opérationnelle par les équipes techniques. 

## Page 11

BâtIA, Phase 2, Groupe 6   |   Page 11 
9. Plan stratégique 
9.1 Positionnement stratégique : maîtrise d'ouvrage interne, développement externalisé  
Conformément à la précision apportée en section 2.2, BâtIA  est porté comme un projet d'amélioration 
opérationnelle interne à In'li Sud -Ouest, et non selon une logique de startup cherchant une entrée de marché 
externe. Guillaume, porteur du projet, occupe une position de maîtrise d'ouvrage (MOA) : Responsable RSE & 
Innovation, en mesure de cadrer le besoin et de porter le projet directement auprès de la direction technique et 
patrimoniale d'In'li Sud -Ouest, sans pour autant disposer, ni lui ni les équipes internes, des compétences de 
développement IA nécessaires à la maîtrise d'œuvre (MOE). 
Le développement technique de la solution est donc confié à un prestataire externe spécialisé en IA et en 
traitement de données, sélectionné selon les modalités usuelles de commande publique ou de marché de 
prestation applicables à un acteur du groupe Acti on Logement. In'li Sud-Ouest conserve la maîtrise du besoin, la 
propriété et la gouvernance des données, et la validation métier des résultats, le prestataire apporte l'expertise 
technique de mise en œuvre. Cette répartition des rôles est cohérente avec ce  qu'observe l'étude USH citée en 
section 7 : plusieurs bailleurs (Vilogia, Domofrance) pilotent leurs projets d'IA en interne tout en faisant développer 
la brique technique par un partenaire externe. Cette externalisation du développement ne dispense toutefois pas 
In'li Sud-Ouest de spécifier précisément son besoin auprè s du prestataire, les exigences de données, l'approche 
attendue du scoring et les critères de validation sont formalisés dans le cahier des charges fonctionnel détaillé en 
section 10, et les modalités de gouvernance de cette relation sont précisées en section 9.7. 
Ce positionnement conserve un avantage stratégique réel par rapport à une approche startup classique : 
contrairement à un éditeur externe qui devrait d'abord convaincre un bailleur de lui confier ses données, In'li Sud-
Ouest n'a pas de client à conquérir ni de confiance à construire, les données lui appartiennent déjà. Cet avantage 
ne dispense toutefois pas d'un travail de fond réel : la mise en état d'exploitation de ces données (nettoyage, 
structuration, consolidation entre systèmes) reste un chantier à p art entière, qui conditionne le calendrier de 
déploiement retenu en section 9.2. 
9.2 Déploiement progressif par paliers 
La stratégie de déploiement retenue suit une logique de démonstration de valeur avant extension, inspirée 
directement du cas EcoStruxure Building identifié en section 7 (« déploiement progressif, bâtiment pilote par 
bâtiment pilote »). Les horizons ci -dessous intègrent le temps nécessaire à la préparation des données et à la 
sélection puis au cadrage du prestataire externe, étapes structurellement plus longues que dans un scénario de 
développement interne : 
● Palier 1, Pilote restreint (6 à 14 mois) : audit et structuration des données existantes, sélection du 
prestataire IA externe, développement et calibrage du modèle sur un sous -ensemble représentatif de 
bâtiments d'une agence locale d'In'li Sud -Ouest, sélec tionné pour sa diversité (âges de construction, 
typologies, niveaux d'instrumentation). 
● Palier 2, Extension régionale (14 à 30 mois) : généralisation à l'ensemble du parc In'li Sud -Ouest, une fois 
le modèle validé sur données historiques et les premiers résultats terrain confirmés, sous réserve des 
critères de passage définis en section 10.5. 
● Palier 3, Mutualisation groupe (30 à 54 mois) : ouverture de la solution aux autres filiales régionales d'In'li, 
voire à d'autres opérateurs d'Action Logement, sous réserve d'une gouvernance de la donnée harmonisée 
entre entités (section 9.7). 
9.3 Modèle économique 
Conformément à l'orientation posée dès la Phase 1, le modèle retenu est un modèle de type SaaS (Software as a 
Service) fourni par le prestataire externe : In'li Sud -Ouest souscrit à la solution développée et hébergée par ce 
partenaire, avec une tarification indexée sur le nombre de logements gérés. Ce modèle évite à In'li de porter en 
interne la charge de maintenance technique de l'outil, cohérente avec son positionnement de maîtrise d'ouvrage 
plutôt que de développeur. 

## Page 12

BâtIA, Phase 2, Groupe 6   |   Page 12 
Le financement du Palier 1 pourrait combiner fonds propres d'In'li Sud -Ouest, subventions publiques liées à la 
rénovation énergétique, et une négociation tarifaire dégressive avec le prestataire en contrepartie du statut de 
site pilote. Si la solution est étendue au-delà d'Action Logement (Palier 3, hypothèse haute), la même logique SaaS 
resterait pertinente, avec une base d'abonnés élargie répartissant le coût de développement initial sur un plus 
grand nombre de logements gérés. 
9.4 Analyse concurrentielle et positionnement 
À la différence d'un marché B2C où BâtIA affronterait des concurrents commerciaux directs, le « marché » pertinent 
ici est avant tout interne : la vraie alternative à BâtIA n'est pas un produit concurrent, mais le statu quo (arbitrages 
sur tableur, décisions fondées sur l'urgence apparente) décrit en section 2.1. 
Il existe cependant des éditeurs de GMAO (Gestion de Maintenance Assistée par Ordinateur) déjà positionnés sur 
la maintenance prédictive bâtimentaire, à examiner comme risque concurrentiel indirect plutôt qu'à ignorer. 
Siveco Group, éditeur français, propose Coswin 8i, une solution de GMAO intégrant des modules IoT et de Business 
Intelligence pour la maintenance prédictive, utilisée notamment dans le secteur tertiaire.6 Alteva propose de son 
côté Mission One, une GMAO dédiée à la gestion et à la maintenance de bâtiments et d'infrastructures, elle aussi 
positionnée sur le secteur tertiaire au sens large.7 
Ces deux éditeurs illustrent en creux l'arbitrage stratégique qu'In'li Sud -Ouest a dû trancher pour la Chosen 
Solution, entre trois options de sourcing : souscrire tel quel à une GMAO généraliste déjà mature comme Coswin 
8i ou Mission One, rapide à déployer, mais sans logique de scoring intégrant les critères sociaux et ODD propres au 
logement intermédiaire ; développer une solution entièrement en interne, écarté faute des compétences IA 
nécessaires (section 9.1) ; ou co -développer la solution avec un prestataire IA spécialisé, dans le c adre d'un 
partenariat évolutif plutôt que d'une livraison logicielle ponctuelle. C'est cette troisième option qui est retenue : 
elle seule permet d'ajuster le scoring et ses critères, palier après palier (section 9.2), avec un prestataire qui monte 
en connaissance du secteur du logement intermédiaire au fil du projet, un compromis entre la rapidité d'une 
solution sur étagère et la maîtrise complète d'un développement i nterne, cohérent avec le positionnement de 
maîtrise d'ouvrage retenu en section 9.1. 
Ni l'un ni l'autre de ces éditeurs ne cible spécifiquement le logement social ou intermédiaire, ni ne propose de 
logique de scoring  intégrant les critères propres à ce secteur (urgence sociale, alignement ODD, contraintes de 
loyers encadrés). C'est cette spécialisation sectorielle, plutôt qu'une différenciation purement technique, qui 
constitue la principale valeur ajoutée de BâtIA face à des solutions génériques de GMAO déjà matures : une GMAO 
généraliste optimiserait la maintenance d'un patrimoine sans arbitrer entre les bâtiments selon des critères sociaux 
et environnementaux propres au logement intermédiaire, alors que c'est pré cisément la fonction du scoring 
multicritère décrit en section 10.3. 
Le principal risque concurrentiel serait donc qu'un de ces éditeurs généralistes, ou un nouvel entrant PropTech , 
package une offre spécifiquement adaptée au logement social et intermédiaire avant qu'In'li Sud -Ouest n'ait 
engagé son propre projet avec un prestataire dédié, ce qui plaide pour un cadrage rapide du besoin au Palier 1 
plutôt que pour une phase de conception prolongée. 
À plus long terme (Palier 3), si la solution est mutualisée au sein d'Action Logement, le positionnement se 
rapprocherait de celui d'un outil métier propriétaire au groupe, à la manière des plateformes de gestion technique 
de bâtiment évoquées en section 7  (EcoStruxure Building), plutôt que d'un produit ouvert au marché face à des 
éditeurs comme Siveco ou Alteva. 
9.5 Facteurs clés de succès et risques stratégiques 
Facteur Risque associé Mitigation 
Qualité et disponibilité des 
données historiques 
Données de maintenance 
incomplètes ou mal structurées 
selon les agences 
Audit de données préalable au Palier 
1 ; scoring conçu pour tolérer des 
données partielles au démarrage 
 
6Siveco Group, « Coswin 8i », siveco.com/coswin-smart-generat/coswin-8i/, consulté en 2026. 
7Alteva, « Logiciel de GMAO Mission One pour la Maintenance immobilière », alteva.fr/logiciel-gmao-mission/, consulté en 2026. 

## Page 13

BâtIA, Phase 2, Groupe 6   |   Page 13 
Facteur Risque associé Mitigation 
Adhésion des équipes 
techniques 
Perception d'un outil de contrôle 
plutôt que d'aide à la décision 
Association des équipes techniques 
dès la conception du Palier 1 ; 
conservation de leurs catégories de 
travail existantes 
Soutenabilité budgétaire du 
déploiement 
Coût de développement non 
compensé à court terme par les 
économies générées 
Démarrage sur périmètre restreint 
pour objectiver le ROI avant 
extension (section 9.6) 
Dépendance au prestataire 
externe 
Risque de verrouillage 
technologique (lock-in) ou de perte 
de maîtrise du modèle 
Clauses contractuelles de 
réversibilité et de portabilité des 
données dès le Palier 1 (section 9.7) 
 
9.6 Cadre d'évaluation économique du pilote 
Sans disposer aujourd'hui de données chiffrées fiables pour établir un calcul de retour sur investissement (section 
8.2), le Palier 1 doit être conçu pour produire lui -même les éléments permettant, à son issue, d'évaluer 
objectivement la pertinence économique d'une extension au Palier 2. Ce cadre d'évaluation repose sur le suivi de 
quatre catégories de coûts et de bénéfices, sur le périmètre pilote uniquement : 
● Coûts de maintenance curative (avant BâtIA) : coût des interventions d'urgence sur le périmètre pilote 
avant déploiement, établi à partir de l'historique GMAO déjà disponible (section 10.2), la seule donnée de 
référence fiable dont dispose In'li Sud-Ouest aujourd'hui. 
● Coûts de maintenance planifiée (après BâtIA) : coût des interventions programmées à la suite des 
recommandations du scoring, à comparer au poste précédent. 
● Coûts du prestataire et de l'abonnement SaaS (section 9.3) : coût de développement du Palier 1 et coût 
récurrent de la souscription, rapportés au nombre de logements couverts. 
● Temps des équipes techniques : temps consacré à l'arbitrage manuel des priorités avant BâtIA, à comparer 
au temps consacré à la validation des recommandations du scoring après déploiement. 
Le gain lié aux pannes évitées ou anticipées précocement n'est pas suivi comme une catégorie additive distincte : 
il est déjà capté dans la différence entre les deux premiers postes ci-dessus, puisqu'une panne évitée ou détectée 
plus tôt est précisément ce  qui transforme une intervention d'urgence coûteuse en une intervention planifiée 
moins onéreuse. Le compter une seconde fois, valorisé au coût moyen d'une intervention d'urgence comparable, 
reviendrait à comptabiliser deux fois le même bénéfice. Les pannes évitées se rapportent mieux comme le facteur 
explicatif du glissement des coûts curatifs vers les coûts planifiés, plutôt que comme une cinquième catégorie à 
additionner aux trois autres. 
Le suivi de ces catégories, dès le Palier 1, permet de construire un calcul de retour sur investissement propre au 
périmètre pilote d'In'li Sud-Ouest, plutôt que d'extrapoler un chiffre depuis un secteur ou un pays différent (limite 
déjà identifiée en section 8.2). La décision de passage au Palier 2 (section 9.2) s'appuie sur ce calcul, aux côtés des 
critères techniques de validation définis en section 10.5. 
9.7 Gouvernance de l'externalisation : propriété, portabilité et réversibilité 
Le choix d'un développement externalisé (section 9.1) soulève des questions de gouvernance qui doivent être 
tranchées contractuellement dès le Palier 1, sous peine de fragiliser la maîtrise du besoin et des données qu'In'li 
Sud-Ouest entend conserver en tant que maîtrise d'ouvrage (section 9.1) : 
● Propriété du modèle et du code : le contrat de prestation doit distinguer la plateforme logicielle générique 
et la technologie de modèle sous-jacente du prestataire, dont celui-ci reste propriétaire et qu'il peut garder 
propriétaire sous un modèle SaaS (section 9.3), de ce qui doit rester portable et sous le contrôle d'In'li Sud-
Ouest : ses propres données, les règles et pondérations du scoring définies par les équipes métier (section 
10.3), les configurations appliquées au modèle, et les résultats produits. In'li doit conserver la pleine 
propriété et le droit d'usage de ce second ensemble, y compris en cas de changement de prestataire. 

## Page 14

BâtIA, Phase 2, Groupe 6   |   Page 14 
● Portabilité des données et des résultats : le contrat doit garantir à In'li Sud-Ouest un droit d'export, dans 
un format standard et documenté, de l'ensemble de ses données d'entrée, des règles et pondérations du 
scoring, et des résultats produits, une clause de réversibilité déjà identifiée comme mitigation du risque 
de verrouillage technologique (section 9.5), précisée ici sous forme d'obligation contractuelle explicite 
plutôt que de principe général. 
● Réutilisation par le prestataire pour d'autres clients : la plateforme générique du prestataire peut 
légitimement être réutilisée pour d'autres bailleurs, ce qui est cohérent avec un modèle SaaS et permet 
de mutualiser le coût de développement sur une base d'abonnés plus large. Le contrat doit en revanche 
exclure explicitement la réutilisation ou le partage des données, des règles de scoring et des résultats 
propres à In'li Sud-Ouest avec d'autres clients du prestataire. 
● Changement de prestataire : la clause de réversibilité mentionnée ci -dessus doit couvrir un délai de 
transition minimal (accompagnement du prestataire sortant, transfert documenté des données et des 
règles et pondérations du scoring) pour éviter toute rupture de service en cas de changement, notamment 
au moment de la bascule vers le Palier 3. 
Ces clauses gagnent en importance à mesure que le déploiement progresse par paliers (section 9.2) : au Palier 3, 
une éventuelle extension à d'autres filiales d'Action Logement suppose que le modèle contractuel retenu au Palier 
1 soit déjà conçu pour être r épliqué à l'identique par d'autres entités du groupe, sans dépendance à un accord 
bilatéral spécifique à In'li Sud-Ouest. 
10. Plan de mise en œuvre (AI Engineering) 
Ce plan d'ingénierie est conçu comme le cahier des charges fonctionnel qu'In'li Sud-Ouest, en position de maîtrise 
d'ouvrage (section 9.1), formaliserait à destination du prestataire IA externe chargé du développement. Il décrit 
les exigences de données, l'approche attendue du scoring et les critères de validation, le « comment » technique 
précis (choix d'implémentation, infrastructure) relevant de la réponse du prestataire retenu. 
10.1 Modèle de maturité IA comme cadre de référence 
Plutôt que de construire une trajectoire d'implémentation ad hoc, ce plan s'appuie sur un modèle de maturité IA 
reconnu, celui de Gartner, qui distingue cinq stades : Fondation (expérimentation ponctuelle, coordination limitée), 
Émergence (premiers pilotes , intérêt croissant de la direction), Opérationnel (l'IA est intégrée à des processus 
définis, avec une gouvernance claire), Généralisé (l'IA est déployée à travers plusieurs fonctions, avec un ROI 
mesurable), et Transformationnel (l'IA remodèle la prise d e décision, le modèle opérationnel et la stratégie 
concurrentielle).8 
In'li Sud-Ouest se situe aujourd'hui au stade Fondation sur le sujet de la maintenance et de la priorisation des 
rénovations : le besoin est identifié (ce rapport en est la preuve), mais aucun projet IA formel n'a encore été engagé 
sur ce périmètre. Les trois paliers de déploiement définis en section 9.2 sont conçus pour faire progresser In'li Sud-
Ouest le long de ce modèle plutôt que comme une simple montée en charge du nombre de logements couverts : 
Palier Niveau de maturité 
visé Caractéristique 
Avant Palier 1 Fondation Besoin identifié, aucun projet IA formel engagé sur ce 
périmètre. 
Palier 1 — Pilote Émergence Premier projet IA formel, périmètre restreint, 
gouvernance encore légère (section 11.1). 
Palier 2 — Extension 
régionale Opérationnel 
L'IA est intégrée aux processus de gestion patrimoniale 
de l'ensemble d'In'li Sud -Ouest, avec une gouvernance 
des données formalisée (référent data, section 11.4). 
 
8Gartner, « AI Maturity Model and AI Roadmap Toolkit », gartner.com/en/chief-information-officer/research/ai-maturity-model-
toolkit, consulté en 2026. 

## Page 15

BâtIA, Phase 2, Groupe 6   |   Page 15 
Palier Niveau de maturité 
visé Caractéristique 
Palier 3 — Mutualisation 
groupe Généralisé Déploiement à travers plusieurs filiales d'Action 
Logement, avec un ROI mesurable à l'échelle groupe. 
 
Ce cadrage répond à une exigence de méthode : il évite de traiter l'implémentation de BâtIA comme un simple 
projet informatique, et la relie explicitement à une trajectoire de maturation organisationnelle progressive, 
cohérente avec le choix d'un déploiement par paliers plutôt qu'un déploiement massif immédiat (section 9.2). 
10.2 Architecture de données 
Le principal enseignement retenu de la section 7 (« la priorité n'est pas l'algorithme mais la donnée ») structure 
directement ce plan d'ingénierie. L'architecture s'appuie sur trois sources de données potentiellement mobilisables 
chez In'li Sud-Ouest, sous réserve d'un travail préalable réel de collecte, de nettoyage et de structuration, qui ne 
doit pas être sous-estimé dans le calendrier (voir section 9.2) : 
● Historique de maintenance (GMAO) : interventions passées, nature des pannes, coûts, délais de résolution. 
● Diagnostics de performance énergétique (DPE) : classement énergétique, année de construction, 
matériaux, système de chauffage. 
● Données patrimoniales : âge des équipements structurants (chaudières, ascenseurs, réseaux), historique 
des rénovations déjà réalisées. 
Les données de capteurs IoT (température, humidité, consommation électrique en continu), lorsqu'elles existent 
sur certains bâtiments déjà instrumentés, viennent enrichir le modèle sans en constituer un prérequis, ce qui 
permet un déploiement réaliste dès le Palier 1, y compris sur des bâtiments peu instrumentés. 
10.3 Approche technique du scoring et du modèle prédictif 
Conformément à la décision prise en Phase 1 de ne pas nommer d'algorithmes précis dans le corps du document, 
le principe retenu est décrit à un niveau conceptuel, suffisant pour être défendu sans expertise data science 
approfondie : 
● Un scoring multicritère explicable pour la priorisation des rénovations, combinant état technique, impact 
énergétique, coût estimé et urgence, avec une pondération ajustable et restituable de façon transparente 
aux équipes de gestion patrimoniale, un mécanisme de dé cision défini par les équipes métier, non un 
modèle de Machine Learning (section 6). 
● Une composante de Machine Learning, distincte du scoring  ci-dessus, pour l'analyse prédictive sur 
données structurées et historiques : elle estime la probabilité et l'horizon de survenue d'une panne, à 
partir de l'âge, des matériaux et de l'historique d'incidents plutôt que de séries temporelles denses de 
capteurs, non disponibles à grande échelle sur le parc actuel. 
Ce choix, données tabulaires structurées plutôt que séries temporelles continues, est un arbitrage assumé : il 
correspond au niveau d'instrumentation réel du parc de logement intermédiaire aujourd'hui, et reste défendable 
sans expertise en réseaux de neurones récurrents. 
10.4 Exemple illustratif de calcul de scoring 
L'exemple suivant, entièrement fictif, illustre le principe de fonctionnement du scoring multicritère décrit ci-dessus, 
sur trois bâtiments hypothétiques du parc In'li Sud -Ouest. Chaque critère est noté de 0 (situation favorable) à 10 
(situation critique), et le score final pondère l'état technique et le risque de panne (poids 40 %), l'impact  
énergétique (poids 30 %), le coût estimé de l'intervention (poids 20 %) et l'urgence sociale perçue (poids 10 %), 
une pondération de départ, ajustable par les équipes techniques d'In'li Sud-Ouest lors du Palier 1. 

## Page 16

BâtIA, Phase 2, Groupe 6   |   Page 16 
Bâtiment (fictif) État technique / 
risque 
Impact 
énergétique Coût estimé Urgence sociale Score (/10) 
Résidence A — 
1978, chaudière 
collective 
8 9 6 7 7,7 
Résidence B — 2005, 
façade récente 3 4 5 3 3,7 
Résidence C — 1992, 
ascenseur 
vieillissant 
7 5 8 5 6,4 
 
Lecture de l'exemple : la Résidence A obtient le score le plus élevé (7,7/10) principalement du fait de son état 
technique et de son impact énergétique, elle serait donc prioritaire dans le plan de rénovation, avant la 
Résidence C (6,4/10) et la Résidence B (3,7/10). Ces chiffres sont purement illustratifs et destinés à démontrer 
le mécanisme de calcul ; ils ne reposent sur aucune donnée réelle du patrimoine d'In'li Sud-Ouest. 
 
10.5 Validation et fiabilisation du modèle 
La validation n'est pas une étape unique et indifférenciée : elle s'applique différemment à la composante Machine 
Learning, au scoring multicritère et au copilote GenAI, puisque chacun joue un rôle distinct dans la solution (section 
6). 
Valider le modèle prédictif de Machine Learning 
Avant tout déploiement, le modèle est testé de façon rétrospective sur l'historique déjà connu du bailleur : on 
vérifie s'il aurait correctement anticipé les pannes effectivement survenues par le passé, sur un échantillon de 
bâtiments déjà documentés. Cett e étape de validation, indispensable avant toute confiance opérationnelle, 
permet d'ajuster le modèle et d'éviter deux écueils symétriques : de fausses alertes qui décrédibiliseraient l'outil 
auprès des équipes techniques, ou des pannes réelles non anticipées qui videraient la solution de son intérêt. 
Au-delà du taux de correspondance rétrospective (section 11.5), la validation s'appuie sur des critères plus précis, 
définis avant le lancement du Palier 1 : 
● Taux de fausses alertes : proportion des pannes signalées par le modèle qui ne se sont pas confirmées 
dans le délai anticipé, à maintenir sous un seuil que les équipes techniques jugeront acceptable pour ne 
pas décrédibiliser l'outil. 
● Délai d'anticipation utile : le modèle doit signaler un risque de panne suffisamment en amont pour 
permettre une intervention planifiée plutôt qu'une intervention d'urgence, un délai mesuré en semaines 
plutôt qu'en jours, à ajuster selon les types d'équipements. 
● Comparaison à une méthode de référence (baseline) : les recommandations du modèle sont comparées, 
sur l'échantillon de validation, aux arbitrages qu'aurait produits la méthode actuelle (ordre chronologique 
ou urgence apparente, section 2.1), afin de démontrer un gain réel et non supposé. 
● Critères de passage au Palier 2 (go/no-go) : le passage du Palier 1 au Palier 2 (section 9.2) est conditionné 
à l'atteinte conjointe d'un taux de correspondance rétrospective jugé suffisant, d'un taux de fausses alertes 
maîtrisé, et d'un taux d'adoption des recommandations par les équipes techniques (section 11.5) 
démontrant une confiance opérationnelle réelle plutôt que théorique. À défaut, le Palier 1 est prolongé 
plutôt qu'étendu. 
Gouverner le scoring multicritère, un exercice distinct de la validation ML 
La pondération du scoring multicritère, impact énergétique, urgence, coût et les autres critères décrits en section 
10.3, n'est pas un paramètre à optimiser pour la précision prédictive : elle reflète les priorités organisationnelles 

## Page 17

BâtIA, Phase 2, Groupe 6   |   Page 17 
d'In'li Sud-Ouest, et sa justesse ne peut pas se mesurer face à une vérité historique comme peuvent l'être les 
prédictions de panne du modèle ML. Cette pondération doit plutôt être gouvernée comme une décision métier : 
proposée par les équipes techniques et de gestion patrimoniale, approuvée par la maîtrise d'ouvrage (section 11.2), 
et revue périodiquement, par exemple à chaque changement de palier (section 9.2), plutôt que réoptimisée 
silencieusement dès que de nouvelles données sont disponibles. Maintenir  cette distinction explicite évite de 
traiter un choix de gouvernance comme s'il s'agissait d'une erreur de modélisation à corriger automatiquement. 
Valider le copilote GenAI 
Le copilote GenAI (section 8.3) requiert son propre protocole de validation, plus léger, distinct des tests de précision 
du modèle ML, puisque son rôle est l'interprétation et la communication, non la prédiction : 
● Fidélité aux données sous-jacentes : les explications du copilote doivent refléter fidèlement le score et les 
données source qu'elles décrivent, vérifié par un contrôle par sondage d'un échantillon d'explications 
générées face aux données sous-jacentes avant la mise en service du Palier 1. 
● Abstention en cas d'information manquante : lorsque la donnée nécessaire pour répondre à une question 
n'est pas disponible, le copilote doit l'indiquer explicitement plutôt que de générer une réponse non 
étayée, un comportement spécifiquement testé lors de la validation. 
● Traçabilité des réponses : chaque réponse du copilote doit rester traçable jusqu'aux enregistrements 
précis et à la version de score dont elle est issue, cohérent avec l'exigence d'auditabilité déjà posée en 
section 12.6. 
10.6 Architecture fonctionnelle du moteur BâtIA 
L'architecture retenue s'organise en trois couches, volontairement simples pour rester maintenables par une 
équipe technique de taille réduite : 
● Couche de collecte : agrégation périodique (mensuelle) des données GMAO, DPE et patrimoniales 
existantes, sans capture temps réel obligatoire au démarrage. 
● Couche d'analyse : calcul du scoring de priorisation et de l'indicateur de risque de panne par bâtiment, 
recalculé à chaque mise à jour des données sources. 
● Couche de restitution : tableau de bord destiné aux équipes techniques, présentant le classement des 
bâtiments, les critères ayant motivé chaque score, un historique des recommandations passées, et le 
copilote GenAI ancré dans les données (section 8.3) per mettant d'interroger et de faire expliciter ces 
résultats en langage naturel. 
Cette séparation en couches permet de faire évoluer chaque brique indépendamment, par exemple, enrichir la 
couche de collecte avec des données de capteurs IoT sur un sous-ensemble de bâtiments, sans devoir reconcevoir 
la couche d'analyse ou de restitution. 
10.7 Ingénierie du passage à l'échelle (scale et coûts) 
Le passage du Palier 1 au Palier 2 (section 9.2) repose sur une architecture pensée dès le départ pour être réplicable 
: les catégories de données utilisées doivent rester génériques d'une agence à l'autre, même si le niveau de qualité 
des données varie. L e coût marginal d'extension à une agence supplémentaire est donc principalement un coût 
d'intégration de données (format, qualité, historique disponible) plutôt qu'un coût de reconception du modèle lui-
même. 
Le passage au Palier 3 (mutualisation groupe) introduit un enjeu de gouvernance de la donnée inter -entités qui 
dépasse le périmètre strictement technique et qui est traité en section 11 (Plan de management) et en section 9.7 
(Gouvernance de l'externalisation). 
10.8 Structure de coûts indicative 
Sans prétendre à un chiffrage définitif, qui dépasserait le périmètre de ce rapport, trois postes de coûts structurent 
le budget d'ingénierie du Palier 1 : 

## Page 18

BâtIA, Phase 2, Groupe 6   |   Page 18 
Poste Nature Ordre de grandeur du poids relatif 
Audit et préparation des 
données 
Nettoyage et structuration des données 
GMAO/DPE existantes Poste dominant en Palier 1 
Développement du moteur de 
scoring 
Conception et calibrage du modèle, 
tableau de bord, copilote GenAI 
(section 8.3) 
Poste secondaire, ponctuel 
Conduite du changement et 
formation 
Accompagnement des équipes 
techniques utilisatrices 
Poste récurrent, croissant avec 
chaque palier 
 
Ce classement confirme, sous l'angle budgétaire, la conclusion clé posée en section 7 : l'essentiel de l'effort et 
du coût du projet porte sur la donnée et l'adoption, non sur la sophistication algorithmique elle-même. 
 
11. Plan de management 
11.1 Organisation et ressources nécessaires 
Le déploiement du Palier 1 ne nécessite pas la création d'une équipe de développement interne : il s'appuie sur 
une organisation projet légère associant Guillaume comme porteur en maîtrise d'ouvrage (Responsable RSE & 
Innovation), les équipes techniques et  patrimoniales déjà en place pour l'expertise métier, la fourniture des 
données et la validation du scoring , et le prestataire IA externe (section 9.1) responsable de la maîtrise d'œuvre, 
développement du modèle, implémentation et maintenance technique du tableau de bord. Une part significative 
de l'effort du Palier 1 porte sur la préparation des données en amo nt de l'intervention du prestataire, ce qui 
explique la durée retenue en section 9.2. 
À partir du Palier 2, une gouvernance plus formalisée devient nécessaire : désignation d'un référent data au sein 
des équipes techniques, responsable de la qualité et de la mise à jour des données d'entrée côté In'li, et 
interlocuteur régulier du prestataire externe, condition identifiée en section 9.5 comme facteur clé de succès. 
11.2 Matrice des responsabilités (RACI) 
La matrice ci-dessous clarifie, pour les grandes activités du projet, qui décide (R = Responsable de l'exécution, A = 
Approbateur, C = Consulté, I = Informé), un repère utile dès le Palier 1 pour éviter toute ambiguïté entre In'li Sud-
Ouest et le prestatai re externe sur le partage des rôles. Chaque activité comporte un seul rôle Approbateur (A), 
afin qu'une décision ne puisse jamais rester bloquée entre deux autorités concurrentes. 
Activité Guillaume 
(MOA) 
Équipes 
techniques In'li 
Prestataire IA 
(MOE) 
Direction In'li Sud-
Ouest 
Cadrage du besoin et cahier 
des charges R C C A 
Audit et structuration des 
données A R C I 
Sélection du prestataire R C I A 
Développement et 
calibrage du modèle A C R I 
Validation métier des 
résultats (section 10.5) A R C I 

## Page 19

BâtIA, Phase 2, Groupe 6   |   Page 19 
Activité Guillaume 
(MOA) 
Équipes 
techniques In'li 
Prestataire IA 
(MOE) 
Direction In'li Sud-
Ouest 
Décision finale de 
rénovation (section 12.4) C R I A 
Gouvernance des données 
(section 11.4) A R C I 
 
11.3 Conduite du changement 
Le principal risque de management identifié n'est pas technique mais humain : la perception d'un outil de contrôle 
imposé aux équipes techniques plutôt que d'un outil d'aide à la décision à leur service. La conduite du changement 
retenue s'appuie sur trois leviers : 
● Association précoce des équipes techniques à la définition des critères de scoring, plutôt qu'une 
conception hors sol suivie d'une simple présentation du résultat. 
● Conservation des catégories de travail déjà utilisées (diagnostic énergétique, historique de sinistres, 
planning pluriannuel), pour éviter toute rupture avec les habitudes existantes, principe déjà posé en Phase 
1 (section 6). 
● Communication sur les gains individuels pour les équipes terrain (réduction des interventions d'urgence 
subies dans l'urgence, meilleure anticipation de leur charge de travail), pas uniquement sur les gains 
agrégés pour le bailleur. 
11.4 Gouvernance des données 
La gouvernance des données constitue l'enjeu de management le plus structurant à moyen terme. Elle recouvre 
trois dimensions : la qualité (fiabilité et mise à jour régulière des données d'entrée, condition posée dès la section 
7 comme enseignement clé des cas d'usage étudiés), la propriété (clarification, en particulier au Palier 3, de la 
responsabilité de chaque entité d'Action Logement sur ses propres données patrimoniales, et des clauses 
contractuelles détaillées en section 9.7), et la protection (traité e en détail en section 12.2 et 12.6, au titre des 
considérations éthiques). 
11.5 Indicateurs de suivi du déploiement 
Le pilotage du déploiement s'appuie sur un nombre volontairement restreint d'indicateurs, pour rester lisible par 
une équipe projet légère : 
● Taux de couverture des données : proportion des bâtiments du périmètre pilote disposant de données 
GMAO et DPE suffisamment complètes pour être scorées. 
● Taux de correspondance rétrospective : proportion des pannes historiques que le modèle aurait 
correctement anticipées, mesurée lors de la validation décrite en section 10.5. 
● Taux d'adoption par les équipes techniques : proportion des recommandations de scoring effectivement 
suivies dans les décisions de rénovation, à comparer à la logique d'arbitrage antérieure. 
● Évolution du ratio interventions d'urgence / interventions planifiées, sur le périmètre pilote, avant et après 
déploiement. 
● Stabilité du modèle dans le temps (dérive) : recontrôle périodique, à partir du Palier 2, de la performance 
du scoring pour détecter une dégradation progressive de sa pertinence (section 12.6). 
11.6 Calendrier de management synthétique 

## Page 20

BâtIA, Phase 2, Groupe 6   |   Page 20 
Palier Horizon Jalon de management clé 
Palier 1 — Pilote 6-14 mois 
Audit et structuration des données ; sélection du prestataire ; 
constitution de l'équipe projet légère ; formalisation des clauses 
de propriété et de réversibilité (section 9.7). 
Palier 2 — Extension 
régionale 14-30 mois 
Désignation d'un référent data ; formalisation de la gouvernance 
de mise à jour des données ; premier recontrôle de la dérive du 
modèle. 
Palier 3 — 
Mutualisation groupe 30-54 mois 
Cadre de gouvernance inter-entités ; clarification de la propriété 
des données par filiale ; réplication du modèle contractuel du 
Palier 1. 
 
12. Considérations éthiques et de responsabilité 
12.1 Transparence et explicabilité du scoring 
Le choix, réaffirmé en section 10.3, d'un scoring explicable plutôt qu'un modèle « boîte noire » n'est pas qu'un 
choix technique : c'est une exigence éthique de premier plan. Une décision de rénover un bâtiment avant un autre 
a des conséquences concrètes sur la qualité de vie des locataires ; elle doit pouvoir être justifiée, contestée et 
corrigée par un humain, et non simplement acceptée parce qu'un algorithme l'a produite. 
12.2 Protection des données des locataires 
Bien que le scoring de priorisation repose principalement sur des données patrimoniales (bâtiment, équipements) 
plutôt que sur des données individuelles des locataires, certains signaux d'entrée, historique de réclamations, par 
exemple, peuvent indirectement porter une infor mation sur les occupants. Le projet doit donc appliquer un 
principe de minimisation des données : n'utiliser que les données strictement nécessaires au scoring , et exclure 
explicitement toute donnée individuelle non requise (situation familiale, revenus autres que le critère d'éligibilité 
déjà vérifié à l'entrée dans le logement). 
12.3 Risque de biais dans la priorisation entre bâtiments et territoires 
Un risque éthique spécifique à BâtIA est le biais géographique ou patrimonial : un scoring fondé sur l'historique de 
maintenance pourrait systématiquement désavantager les bâtiments les plus anciens ou les territoires les moins 
bien dotés en données historiques fiables, alors que ce sont potentiellement ceux qui en ont le plus besoin. Ce 
risque doit être surveillé activement, par exemple via un contrôle périodique de la distribution géographique des 
recommandations du modèle. Toute correction du scoring  en réponse à un déséquilibre constaté, qu'il s'agisse 
d'un ajustement de pondération ou d'une autre mesure corrective, ne peut être décidée unilatéralement par un 
utilisateur individuel : elle doit suivre une procédure de gouvernance documentée, associant  les équipes 
techniques et la maîtrise d'ouvrage (section 11.2), et être elle-même tracée et justifiée au même titre que les scores 
qu'elle modifie. Une repondération non gouvernée introduirait en effet un nouveau risque d'arbitraire, symétrique 
à celui qu'elle est censée corriger. 
12.4 Rôle de l'humain dans la décision finale 
Conformément au principe déjà posé en Phase 1 pour le futur chatbot (« l'IA vient en appui des décisions plutôt 
que de s'y substituer »), BâtIA est conçu comme un outil d'aide à la décision et non comme un système de décision 
automatisée : le scoring produit une recommandation argumentée, mais la décision finale de rénovation reste de 
la responsabilité des équipes techniques et de la direction patrimoniale d'In'li Sud -Ouest. Toute décision qui 
s'écarte de la recommandation du scoring est elle-même enregistrée avec sa justification, afin de documenter dans 
la durée les cas où le jugement humain corrige ou nuance la recommandation algorithmique. 
12.5 Synthèse des considérations éthiques 

## Page 21

BâtIA, Phase 2, Groupe 6   |   Page 21 
Enjeu éthique Réponse apportée par la conception de BâtIA 
Explicabilité Scoring multicritère transparent plutôt que modèle boîte noire (section 
10.3) 
Protection des données locataires Principe de minimisation ; exclusion des données individuelles non 
nécessaires au scoring 
Biais géographique ou patrimonial 
Contrôle périodique de la distribution des recommandations ; toute 
correction suit une procédure de gouvernance documentée, non un 
ajustement unilatéral 
Automatisation excessive de la 
décision 
Recommandation argumentée soumise à validation humaine, jamais de 
décision automatisée ; écarts documentés (section 12.4) 
Sécurité et responsabilités 
partagées avec le prestataire 
Accès, conservation et auditabilité encadrés contractuellement (section 
12.6) 
 
12.6 Sécurité des données et responsabilités partagées avec le prestataire 
Au-delà de la protection des données des locataires (section 12.2), l'externalisation du développement à un 
prestataire (section 9.1) crée une responsabilité partagée qui doit être explicitée : 
● Accès et sécurité : le contrat de prestation doit définir précisément quelles données In'li Sud -Ouest 
transmet au prestataire, sous quelle forme, et selon quelles modalités de sécurisation des accès 
(chiffrement, gestion des habilitations), cohérent avec le principe de minimisation posé en section 12.2. 
● Durée de conservation : les données transmises au prestataire, ainsi que les résultats de scoring 
historiques, sont soumis à une durée de conservation définie contractuellement, alignée sur les besoins 
réels de validation rétrospective du modèle (section 10.5) plutôt que conservées indéfiniment par défaut. 
● Auditabilité des recommandations : chaque recommandation de scoring  reste traçable a posteriori, 
quelles données d'entrée, quels critères et quelle pondération ont produit tel classement à telle date, 
condition posée par la couche de restitution (section 10.6) et indispensable pour instruire un désaccord 
ou une contestation d'une équipe technique. 
● Suivi de la dérive du modèle (model drift) : au-delà de la validation initiale (section 10.5), la performance 
du scoring  est recontrôlée périodiquement une fois en production, pour détecter une dégradation 
progressive de sa pertinence à mesure que le parc évolue (rénovations réalisées, nouveaux bâtiments 
intégrés), un contrôle intégré aux indicateurs de suivi à partir du Palier 2 (section 11.5). 
13. Conclusion 
La Phase 2 du projet BâtIA  confirme et approfondit les orientations posées en Phase 1 : le secteur du logement 
intermédiaire présente des défis structurels pour lesquels l'intelligence artificielle offre des leviers d'action 
concrets, sans nécessiter une sophistication technologique hors de portée d'un opérateur comme In'li Sud-Ouest. 
Le choix, assumé, de concentrer le projet sur un bloc non-dissociable, priorisation des rénovations et maintenance 
prédictive, plutôt que de disperser l'effort sur l'ensemble des solutions esquissées en Phase 1, permet une 
profondeur d'analyse cohérente av ec les attentes du barème sur la stratégie, l'ingénierie, le management et 
l'éthique. 
Trois enseignements clés structurent l'ensemble de la proposition : la donnée avant l'algorithme, l'explicabilité 
avant la sophistication, et l'adoption humaine avant le déploiement technique. Le positionnement retenu, In'li Sud-
Ouest en maîtrise d'ouvrage , appuyée sur un prestataire IA externe pour le développement, constitue l'atout 
différenciant principal de cette proposition : il donne à In'li la maîtrise du besoin, la propriété des données et le 
pilotage des équipes internes nécessaires à la réussite d u projet, sans lui imposer une compétence de 
développement IA qu'elle n'a pas à détenir en interne, tout en restant réplicable, à terme, à d'autres filiales d'Action 
Logement. 

## Page 22

BâtIA, Phase 2, Groupe 6   |   Page 22 
Si l'ensemble du projet reste volontairement construit autour du cas français, la comparaison internationale 
esquissée en section 2.3 suggère que certains éléments de BâtIA sont potentiellement transférables, sur le principe, 
au-delà d'In'li Sud-Ouest : le principe d'un scoring explicable fondé sur des données patrimoniales déjà détenues 
par un bailleur n'est pas intrinsèquement lié au cadre réglementaire local, et pourrait plausiblement s'appliquer au 
dispositif marocain de Logement Locatif Intermédiaire ou au logement en copro priété partagée chinois, sous 
réserve d'une adaptation au contexte institutionnel, réglementaire et de données propre à chaque marché, plutôt 
que d'une transposition directe des critères de pondération retenus pour In'li Sud -Ouest. Ce qui ne serait en 
revanche pas transférable sans adaptation profonde est le montage MOA/MOE retenu en section 9.1, propre à 
l'organisation et aux pratiques d'achat d'In'li Sud-Ouest et du groupe Action Logement. 
14. Glossaire 
IA : Intelligence Artificielle : ensemble des techniques permettant à un système informatique d'accomplir des 
tâches associées à l'intelligence humaine. 
ML : Machine Learning (apprentissage automatique) : sous -domaine de l'IA où un système apprend à partir de 
données pour faire des prédictions, sans être explicitement programmé pour chaque règle. 
GenAI : IA générative : technologies capables de générer du texte, des réponses ou des documents, par opposition 
aux modèles purement prédictifs. 
Ancrage (grounding) : Principe consistant à limiter les réponses d'un système de GenAI aux données et documents 
vérifiés d'une organisation, plutôt qu'à sa seule connaissance générale, afin de réduire le risque d'erreur factuelle. 
ODD : Objectif de Développement Durable : cadre de 17 objectifs définis par les Nations Unies pour guider les 
politiques de développement à horizon 2030. 
IoT : Internet des objets : capteurs physiques connectés qui mesurent et transmettent des données en continu. 
ROI : Retour sur investissement : indicateur mesurant le bénéfice financier généré par un investissement, rapporté 
à son coût. 
SaaS : Logiciel en tant que service : modèle économique où un logiciel est loué par abonnement plutôt qu'acheté. 
GMAO : Gestion de Maintenance Assistée par Ordinateur : système utilisé par les bailleurs pour enregistrer et 
suivre les interventions de maintenance. 
LLI : Logement Locatif Intermédiaire : dispositif français de logement à loyers encadrés, entre logement social et 
marché libre. 
USH : Union Sociale pour l'Habitat : fédération française des organismes de logement social. 
DPE : Diagnostic de Performance Énergétique : évaluation réglementaire de la consommation énergétique et de 
l'impact carbone d'un logement en France. 
MOA : Maîtrise d'Ouvrage : entité porteuse du besoin, propriétaire des données et responsable de la validation 
métier d'un projet, par opposition à la maîtrise d'œuvre chargée de la réalisation technique. 
MOE : Maîtrise d'Œuvre : entité, ici un prestataire externe, responsable de la conception et de la réalisation 
technique d'une solution pour le compte de la maîtrise d'ouvrage. 
RACI : Outil de gouvernance de projet identifiant, pour chaque activité, qui est Responsable de l'exécution (R), 
Approbateur (A), Consulté (C) ou Informé (I). 
15. Références 
Action Logement. Communiqué de résultats 2025. groupe.actionlogement.fr. 
Alteva. « Logiciel de GMAO Mission One pour la Maintenance immobilière ». alteva.fr/logiciel -gmao-mission/. 
Consulté en 2026. 

## Page 23

BâtIA, Phase 2, Groupe 6   |   Page 23 
Gartner. « AI Maturity Model and AI Roadmap Toolkit ». gartner.com/en/chief -information-officer/research/ai-
maturity-model-toolkit. Consulté en 2026. 
In'li. Site institutionnel. inli.com. Consulté en 2026. 
In'li Sud-Ouest. Site institutionnel. inli-sudouest.fr. Consulté en 2026. 
Cours OneMBA d'Intelligence Artificielle. Lecture préparatoire sur les modèles de credit scoring (Moody's RiskCalc), 
Prof. Jeunghyun Kim. 
Schneider Electric. « Artificial Intelligence solutions and AI use cases ». se.com, page produit EcoStruxure / IA. 
Consulté en 2026. 
Siveco Group. « Coswin 8i ». siveco.com/coswin-smart-generat/coswin-8i/. Consulté en 2026. 
Union Sociale pour l'Habitat. « Intelligence artificielle (IA) et logement social : les cas d'usages appliqués à la 
maîtrise d'ouvrage et au patrimoine ». Repères n°143, 11 février 2025. 
Nations Unies. The Sustainable Development Goals Report. sdgs.un.org. Consulté en 2026. 