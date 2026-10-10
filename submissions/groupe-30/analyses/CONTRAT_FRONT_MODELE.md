# Contrat proposé entre le front et le modèle

Proposition du 10 octobre 2026 pour permettre un développement indépendant. Ce contrat décrit les échanges à implémenter ; il n'existe pas encore d'API ni de fichier de modèle final.

## 1. Quatre objets distincts

| Objet | Responsable proposé | Contenu |
| --- | --- | --- |
| Inventaire | Adaptateur des données du kit, puis des outils métier | Identité, localisation, famille, contrat, prestataire, vie de l'appareil |
| Résultat de scoring | Collègue chargé du modèle | Score, horizon, version et explications disponibles |
| Preuves | Préparation des données / extraction | Faits, sources, dates, rattachements et qualité |
| Dossier d'action | Application | Décision, responsable, rendez-vous, constat et historique |

Un nouveau score actualise l'information prédictive. Il n'efface pas un dossier d'action et ne déclenche pas une nouvelle inspection sans décision humaine. Prévoir au maximum un dossier ouvert par équipement pour le parcours simple, avec possibilité de lui associer plusieurs actions. La règle exacte sera validée avec le métier.

## 2. Échange minimal pour débloquer le front

Le fichier du collègue peut reprendre le format officiel :

```csv
equipement_id,score_risque
```

L'en-tête ci-dessus est une description du format, pas un résultat de prédiction. Une ligne par équipement du périmètre est attendue. Le front fait la jointure sur `equipement_id` avec l'inventaire, pas sur un nom de logement ou une position de ligne.

Accompagner ce fichier de métadonnées : identifiant/version du résultat ; identifiant/version du modèle ; date du calcul ; date de référence des données ; début et fin exclusive de l'horizon ; nature du score ; statut de calibration ; origine du résultat, réelle ou démonstration.

Dans le scénario du kit : état fin 2025, `horizon_start = 2026-01-01`, `horizon_end_exclusive = 2026-10-01`. La date du calcul peut être en octobre 2026 ; elle ne change pas la date de référence du scénario.

Le kit impose un classement croissant avec le risque. Il ne fixe pas une échelle universelle. Un score numérique fini n'est donc pas automatiquement un pourcentage. Réserver l'affichage d'une probabilité aux sorties explicitement identifiées comme probabilités calibrées ; alors, vérifier aussi l'intervalle `[0, 1]`.

## 3. Explications : extension recommandée

Pour chaque équipement, proposer au maximum trois facteurs principaux avec : code de variable, libellé métier, valeur observée et fenêtre temporelle, sens de contribution au score, méthode d'explication et références des preuves associées lorsqu'elles existent.

Une valeur de contribution est facultative. Si elle est fournie, préciser son unité et l'espace de calcul, par exemple log-odds. Le front ne convertit pas une contribution SHAP ou EBM en points de probabilité par une simple multiplication.

Les faits disponibles peuvent être montrés même sans attribution du modèle. Ils portent alors le libellé « Historique disponible ». Une explication absente reste absente. Le front n'invente ni intervalle de confiance ni diagnostic.

## 4. Preuves et vie de l'appareil

Champs recommandés : `evidence_id`, type de source, référence de l'événement ou chemin du document, page PDF éventuelle, date d'événement si connue, date de disponibilité si connue, extrait ou fait structuré, identifiant équipement si confirmé, vie de l'appareil si reconstructible, niveau de rattachement.

Les rattachements peuvent être explicites, déduits ou à confirmer. Les preuves qui décrivent le même épisode sont regroupées lorsque le rapprochement est justifié. Une preuve antérieure au remplacement ne devient pas un incident du matériel actuel.

Le front utilise les libellés métier du [dictionnaire du kit](sources_lisibles/xlsx_DICTIONNAIRE.csv) et respecte les règles du [guide de données](GUIDE_DONNEES.md). Les coordonnées locataires, adresses précises et disponibilités des techniciens ne sont pas présentes.

## 5. Dossier d'action : stockage séparé

Champs proposés : identifiant du dossier ; équipement ; version de score examinée lors de la décision ; vie de l'appareil si connue ; décision et motif ; responsable ; prestataire proposé ; statut ; date souhaitée ; date confirmée éventuelle ; date de réexamen ; référence d'une action externe éventuelle ; événements de décision et constats datés.

Les identifiants utilisateurs et disponibilités sont des données à ajouter à l'application. Ils ne sont pas fournis par le modèle ou le kit. La persistance locale d'un prototype est suffisante pour une démonstration individuelle mais ne constitue pas un stockage partagé entre collègues ou prestataires.

Une modification de source importée, un retour de terrain et une nouvelle prédiction sont trois événements différents. Un retour métier ne sert pas directement de cible d'entraînement sans contrôle : une intervention peut modifier le risque observé ensuite.

## 6. Contrôles d'import et comportements du front

- Identifiants connus, une seule ligne par équipement et score numérique fini. Une ligne non valide est signalée.
- Aucun mélange silencieux de modèles, dates de référence ou horizons différents dans un classement.
- Un résultat partiel peut être consulté avec sa couverture ; les absents restent « Non scoré », jamais 0.
- L'export officiel est disponible seulement si les 1 285 équipements du périmètre sont présents une fois, avec des scores valides.
- La soumission contient uniquement `equipement_id,score_risque` ; l'export de préparation des inspections est un fichier distinct.
- Le rang est calculé sur le résultat complet. Un filtre de résidence réduit la liste affichée sans changer son sens. L'arrondi du top 10 % et les ex aequo sont documentés.
- Une erreur de chargement conserve explicitement le dernier résultat valide disponible et sa date ; elle ne simule pas un score actualisé.
- Un changement de vie d'appareil appelle une révision du dossier métier. Il ne supprime pas son historique.

## 7. Démonstration avant réception du modèle

Utiliser un résultat de référence clairement identifié, par exemple le classement par âge audité. Les faits peuvent provenir du kit ; les actions ajoutées pour illustrer le parcours doivent être signalées comme simulées. La suppression de ces actions ne modifie ni les sources ni le score officiel reçu du collègue.

Le front reste ainsi indépendant du choix EBM / CatBoost et d'un éventuel passage du fichier à une API.
