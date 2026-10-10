# Lecture et cadrage du kit BatIA

Le périmètre de travail est uniquement la prévention des pannes.

- [Cadrage du besoin et pièges du hackathon](CADRAGE_PREVENTION_PANNES.md) : document principal.
- [Guide des données et des jointures](GUIDE_DONNEES.md) : point de départ pour préparer les variables.
- [Audit chiffré](AUDIT_DONNEES.md) : constats calculés et limites du notebook.
- [Choix du modèle et protocole d'entraînement](RECOMMANDATION_MODELE_IA.md) : recherche technique sourcée, comparaison EBM / CatBoost et validation temporelle proposée.
- [Besoin métier et spécification du front](SPEC_FRONT_PREVENTION.md) : parcours, écrans, priorités UI/UX et limites à respecter.
- [Contrat front / modèle](CONTRAT_FRONT_MODELE.md) : échanges proposés pour développer l'interface sans attendre l'entraînement.
- [Plan de réalisation du front](PLAN_IMPLEMENTATION_FRONT.md) : architecture proposée, lots et critères de validation.
- [Direction artistique Action Logement](DA_FRONT.md) : palette tirée du logo fourni et principes de présentation.
- [Application de prévention implémentée](../front/README.md) : lancement local, parcours disponibles, import du modèle et validations.
- [Sources rendues lisibles](sources_lisibles/) : huit PDF en Markdown paginé, PowerPoint et notebook en texte, trois onglets documentaires en CSV.

Les CSV originaux sont déjà directement exploitables en UTF-8, séparateur virgule. Les dates peuvent porter des heures. Les exports CSV et les 13 onglets de données Excel ont été comparés cellule par cellule après normalisation des nombres.

Les sources originales ont été préservées. Le fichier temporaire Excel déjà présent, `~$BatIA_Hackathon_Donnees_Fictives.xlsx`, est exclu de l'analyse.

## Reproduire l'analyse

Python avec `pandas`, `numpy`, `pypdf` et `openpyxl` suffit pour les deux scripts. Aucune API externe n'est appelée.

```powershell
python analyses/scripts/extract_sources.py
python analyses/scripts/audit_sources.py
```

Le premier script extrait les textes, le dictionnaire et les hypothèses, puis profile les tables. Le second contrôle les identifiants et rattachements, compare Excel et CSV, audite les bornes temporelles et calcule la baseline d'âge. La régression logistique du notebook n'a pas été exécutée : `scikit-learn` est absent du runtime utilisé pour ce cadrage.

`audit_resultats.json`, `profil_donnees.json` et `profil_classeur.json` contiennent les résultats structurés. `inventaire_sources.json` fournit les chemins, tailles et empreintes SHA-256 des 24 sources, hors fichier temporaire Excel. Ces fichiers facilitent la suite du travail sans relire les binaires.

Les rendus des trois pages clés contrôlées visuellement se trouvent dans `verification_visuelle/`. Les autres PDF ont été lus par extraction de texte. Un schéma ou une illustration absents du texte doivent être revus dans le PDF original si leur détail devient nécessaire.
