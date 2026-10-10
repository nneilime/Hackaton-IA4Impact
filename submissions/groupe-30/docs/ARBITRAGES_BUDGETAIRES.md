# Prévention et arbitrages budgétaires

La fiche équipement commence par la décision à préparer et les points à vérifier. Les trois symptômes proposés restent des hypothèses pour la première panne éventuelle. Les deux scores techniques et le coût pondéré sont disponibles dans « Comprendre le résultat du modèle ». Le modèle prédit les dépannages ou remplacements, pas uniquement les arrêts totaux ; ses scores ne sont pas des probabilités calibrées.

## Indicateurs et sources

- **Réparations répétées** : au moins deux dépannages documentés sur les 365 jours précédant la référence, depuis la pose de l’appareil actuel. Source : `interventions`. Un cycle inconnu reste inconnu. Ce seuil propose une comparaison de devis, jamais un remplacement automatique.
- **Coût des dépannages simulé** : somme des tarifs fictifs `prix_interventions` correspondant aux symptômes réellement observés. Un tarif manquant empêche le total. Ce montant n’est pas une dépense facturée.
- **Remplacement indicatif** : fourchette TTC du référentiel `familles`, distincte d’un devis. Le ratio dépenses simulées / fourchette de remplacement donne deux bornes. Les dépenses passées ne constituent pas des économies futures.
- **Factures et commandes** : source `commandes`, agrégée par logement ou résidence. Les factures sont datées sur les 12 mois antérieurs à la référence. Le solde d’une commande soustrait seulement les factures connues à la référence, sans double comptage. Les commandes annulées et futures sont exclues. Aucune facture n’est attribuée directement à un équipement ; la couverture de maintenance est partielle, notamment sous contrat. Les statuts des CSV sont des états sans historique complet.
- **Tournées communes** : équipements des 10 % prioritaires du classement complet, regroupés par résidence et prestataire. Compatibilité des contrôles, disponibilité et prise en charge à confirmer. Le nombre de déplacements à regrouper suppose des visites distinctes ; aucune remise ni économie financière n’est inventée.
- **Coordination avec une rénovation** : rapprochement de la famille, de la résidence et des bâtiments explicitement identifiables dans `investissements`. Une opération portant sur un lot non identifié de logements reste un rapprochement à confirmer. Les opérations du kit sont proposées, pas engagées.

## Enveloppes partagées

Dans **Arbitrages budgétaires**, sélectionner l’année et les opérations proposées. Le budget de rénovation initial de 1,5 M€ vient de l’hypothèse du kit ; le budget de maintenance est indépendant et reste vide avant saisie. Le total comprend toutes les opérations retenues, même masquées par un filtre. Coût par logement et gain énergétique EP/m²/an restent séparés : les gains d’opérations superposées ne sont pas additionnés ni convertis arbitrairement en euros.

« Partager la sélection » conserve les enveloppes et les identifiants dans `budgets` et `operations_retenues`. Cela ne crée aucune commande et ne modifie pas le plan d’investissement source. Les membres accèdent par l’API ; RLS protège les tables. Le serveur vérifie la version du budget, la révision d’import, les identifiants, les coûts et l’enveloppe dans une transaction. Une modification concurrente conserve le brouillon à l’écran et exige un rechargement explicite. Les imports actualisent les coûts ; une sélection devenue trop coûteuse doit être réexaminée.

## Simulation de prévention

Renseigner le coût supplémentaire du contrôle, une probabilité supposée, la part des pannes évitables et la dépense réellement évitable par panne. Le gain net simulé est `probabilité × efficacité × dépense évitable − coût du contrôle`. L’équilibre et les scénarios négatifs restent visibles. Aucun score non calibré n’est repris automatiquement comme probabilité. La simulation ne prouve ni l’efficacité du contrôle ni des économies réalisées ; les dépenses déjà couvertes par contrat doivent être distinguées des coûts supplémentaires.

« Préparer la comparaison de devis » ouvre le dossier partagé avec un objectif proposé. Les objectifs peuvent être adaptés pour contrôler, obtenir un devis, comparer réparation/remplacement, coordonner des travaux ou surveiller. L’enregistrement conserve les validations et l’historique existants, avec un seul dossier ouvert par équipement.

## API et validations

`GET /api/economies`, `GET /api/equipements/{id}/economie` et `PUT /api/budgets/{annee}` exigent un membre identifié. Les lectures utilisent un instantané PostgreSQL cohérent. Les coûts de la première panne éventuelle proviennent de `POST /api/predict` et des résultats publiés ; l’app conserve le même corps de requête. Les coûts de contrôle et les hypothèses d’efficacité du simulateur sont saisis séparément.

Les tests ciblés vérifient le grain des factures, les bornes temporelles, les remplacements, les tarifs manquants, l’absence de double comptage, les budgets, les conflits, RLS, les calculs de scénario et les parcours desktop/mobile. Les tests PostgreSQL annulent leurs écritures ; Playwright simule Auth/API.
