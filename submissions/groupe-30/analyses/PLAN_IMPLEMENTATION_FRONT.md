# Plan de réalisation du front

Version du 10 octobre 2026. Périmètre accepté : prévention des pannes. Le collègue développe le modèle ; ce plan concerne l'interface, son adaptateur de données et les dossiers d'action. Le prototype local est maintenant implémenté dans `front/` ; son [README](../front/README.md) précise le lancement, les fonctions disponibles et les validations.

La [spécification métier](SPEC_FRONT_PREVENTION.md), la [direction artistique](DA_FRONT.md) et le [contrat front / modèle](CONTRAT_FRONT_MODELE.md) constituent les références. La préférence utilisateur est intégrée : identité Action Logement et interface agréable, sans en-tête « mode hackathon ».

## Architecture de départ

Proposition : **React + TypeScript + Vite**, React Router pour les vues et liens directs, CSS avec variables de design centralisées. Le [guide officiel Vite](https://vite.dev/guide/) propose un modèle React TypeScript ; [React Router](https://reactrouter.com/start/declarative/installation) documente la navigation déclarative. Les versions seront fixées dans un fichier de verrouillage à l'initialisation.

Cette architecture convient à une application interactive servie localement, avec un import de résultats puis une connexion éventuelle à une API Python. Les composants partagés couvrent boutons, champs, badges, listes, tableaux, dialogues et messages. Ajouter des bibliothèques spécialisées seulement lorsqu'un besoin concret le justifie.

Créer le projet dans un sous-dossier `front/` pour préserver les sources et analyses. Les chemins ci-dessous décrivent l'organisation future, pas des fichiers déjà présents :

```text
front/
  public/brand/                  logo fourni, copie inchangée
  src/app/                      navigation et structure des pages
  src/features/review/           file À examiner
  src/features/equipment/        inventaire, fiche et chronologie
  src/features/actions/          préparation et suivi des inspections
  src/data/                     adaptateurs de fichiers puis d'API
  src/domain/                   types métier et règles de validation
  src/ui/                       composants partagés
  src/styles/                   couleurs, typographie et espacements
```

Les faits, scores et dossiers d'action restent trois ensembles séparés. Le résultat du modèle n'est pas recalculé dans les composants d'affichage. Une mise à jour de score ne réinitialise pas le suivi métier.

## Lots et critères de fin

| Lot | Travail | Dépendance | Résultat vérifiable |
| --- | --- | --- | --- |
| **1. Socle et identité visuelle** | Initialiser le front ; intégrer le logo et les variables de style ; créer navigation, structure des pages et composants essentiels | Aucun modèle requis | Les vues sont navigables, la présentation suit la DA et fonctionne sur ordinateur et téléphone |
| **2. Données et contrats** | Lire l'inventaire ; préparer les rattachements, événements et frontières de remplacement ; créer un adaptateur de résultats et les états manquants | Fichiers du kit et contrat proposé | Références correctes, aucune ligne multipliée, vie de l'appareil et origine des informations préservées |
| **3. Liste et fiche** | Recherche, filtres, pagination, tri, ouverture d'une fiche, preuves et chronologie ; conserver le contexte au retour | Lots 1-2 | Un équipement est retrouvable par logement ou référence et ses indices sont consultables sans lire les CSV |
| **4. Parcours d'inspection** | Préparer un dossier ; responsable et dates ; rattacher une action existante ; réexaminer ; enregistrer un retour et une conclusion | Lot 3 | Parcours complet de la décision au constat, avec historique et persistance |
| **5. Résultat du collègue et exports** | Brancher le fichier de scores ; gérer métadonnées et facteurs ; contrôler la couverture ; produire les exports adaptés | Résultat du modèle lorsqu'il est disponible | Classement cohérent, provenance consultable, export officiel valide et dossier d'inspection distinct |
| **6. Vérification et finition** | Contrôles métier, clavier, responsive, chargement, erreurs et cohérence graphique ; corriger les défauts | Parcours principal terminé | Build valide, scénarios centraux vérifiés et états dégradés compréhensibles |

Le lot 5 peut commencer dès réception du fichier de scores, pendant le lot 3 ou 4. En attendant, le front utilise un résultat de référence dont la méthode est consultable dans « Données », ou un état non scoré. Il ne doit pas afficher de facteurs attribués à un modèle non disponible.

## Détail du MVP

### À examiner

- Recherche équipement/logement/bâtiment, filtres résidence, famille, prestataire, individuel/collectif et prise en charge.
- Tableau lisible, rang sur le périmètre complet, indice disponible et accès à la fiche.
- Retour à la liste avec filtres, tri et pagination conservés.
- Accès discret aux dates, couverture et provenance du classement.
- États de chargement, liste vide après filtre, score absent et dernier résultat disponible.

### Fiche équipement

- Identité et localisation fiables, contrat et prestataire, date de pose avec son origine.
- Risque et horizon séparés des faits observés et des décisions humaines.
- Facteurs du modèle lorsqu'ils existent ; sinon historique présenté comme tel.
- Chronologie avec frontière de remplacement et preuves datées.
- Rattachements incertains visibles et feedback enregistré séparément des données originales.
- Préparation d'inspection, action existante et réexamen accessibles depuis la fiche.

### Actions

- Dossier unitaire, responsable, motif et dates distinctes pour demande et confirmation du rendez-vous.
- États à préparer, planifiée, réalisée, clôturée et à réexaminer.
- Référence externe si une action est déjà suivie ailleurs.
- Retour terrain structuré et commentaire, suivi des modifications et export d'un dossier.
- Persistance locale pour le prototype, avec sauvegarde/export possible. Cette étape ne fournit pas une synchronisation entre plusieurs utilisateurs ; un stockage partagé est un chantier séparé.

### Équipements

- Recherche dans l'inventaire avec indication du périmètre scoré.
- Réutilisation de la fiche et distinction entre collectif, individuel, non scoré et hors périmètre.

## Répartition avec le collègue

| Front | Modèle et préparation prédictive |
| --- | --- |
| Navigation, affichage et actions métier | Construction des variables et entraînement |
| Jointure d'affichage sur `equipement_id` | Fichier des scores et métadonnées cohérentes |
| Consultation des preuves et de leur provenance | Facteurs de score et méthode d'explication lorsqu'ils sont disponibles |
| États de données manquantes et contrôles d'import | Validation historique et statut de calibration |
| Dossiers d'inspection et retours terrain | Recalcul des scores selon les données disponibles |

L'adaptateur de consultation des événements peut être préparé côté front à partir du kit. Une donnée dérivée fournie aussi par le modèle doit avoir une définition commune, notamment la fenêtre de comptage et la séparation des vies d'appareil.

Le CSV minimal du collègue permet de brancher le classement sans attendre une API. Les explications restent une extension indépendante. Aucun endpoint ne doit être inventé puis présenté comme disponible.

## Validations prévues

Les contrôles automatisés portent sur les règles qui risquent de produire une mauvaise décision : import et couverture des scores, clés de jointure, absence de doublons, rang indépendant des filtres, séparation des vies d'appareil, transitions des dossiers et conservation après rechargement.

Vérifier les parcours dans un navigateur : retrouver un équipement, consulter une preuve, préparer une inspection, enregistrer un constat ; traiter aussi un collectif, un remplacement récent et un non-scoré. Tester au clavier et à des largeurs représentatives, par exemple 1440, 1024 et 390 px. Contrôler que les actions restent compréhensibles sans dépendre uniquement de la couleur.

Avant livraison du front : compilation TypeScript, build, validations métier pertinentes et contrôle visuel des vues centrales. Une vérification des documents de planification ne vaut pas une validation d'une interface encore non implémentée.

## Après le MVP

Sélection en lot et regroupement résidence/prestataire ; recherches enregistrées ; confort mobile et réexamen ; synthèse opérationnelle. Les connecteurs aux outils métier et le planning avec disponibilités réelles viennent après confirmation des accès et de l'organisation.

Le parcours unitaire est implémenté, avec l'import du CSV minimal et la référence par âge en attendant le modèle. Les facteurs structurés du modèle, les actions en lot, le stockage partagé et les connecteurs restent des extensions. Les fonctions réellement disponibles et leurs limites sont documentées dans le [README du front](../front/README.md).
