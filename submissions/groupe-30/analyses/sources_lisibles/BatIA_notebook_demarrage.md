# Source : DATA 2 _le kit étudiants\BatIA_Kit_Hackathon\BatIA_notebook_demarrage.ipynb

## Cellule 1 (markdown)

# BâtIA — Notebook de démarrage
**Hackathon IA for Impact 2026 · Défi In'li Sud-Ouest « Hacker le bâtiment avant qu'il ne casse »**

Ce notebook vous fait gagner la première heure : chargement des tables, liens entre elles, un premier coup d'œil, puis **une baseline volontairement simple** pour chacun des deux défis et le **format de soumission** attendu par le jury.

> Toutes les données sont **fictives** (calibrées sur des statistiques réelles agrégées). Ne cherchez pas à les rattacher à des résidences réelles.

Prérequis : `pandas`, `scikit-learn`, `matplotlib`. Placez ce notebook à côté du dossier `donnees/`.

## Cellule 2 (code)

```python
import pandas as pd, numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

DOSSIER = 'donnees/'
residences   = pd.read_csv(DOSSIER + '01_residences.csv')
batiments    = pd.read_csv(DOSSIER + '02_batiments.csv')
logements    = pd.read_csv(DOSSIER + '03_logements.csv')
equipements  = pd.read_csv(DOSSIER + '04_equipements.csv', parse_dates=['date_pose'])
demandes     = pd.read_csv(DOSSIER + '05_demandes_locataires.csv', parse_dates=['date_creation', 'date_cloture'])
interventions= pd.read_csv(DOSSIER + '06_interventions.csv', parse_dates=['date_intervention'])
commandes    = pd.read_csv(DOSSIER + '07_commandes.csv', parse_dates=['date_commande', 'date_facture'])
plan         = pd.read_csv(DOSSIER + '08_plan_investissement.csv')
ref_familles = pd.read_csv(DOSSIER + '10_ref_familles_equipements.csv')

for nom, df in [('residences', residences), ('batiments', batiments), ('logements', logements), ('equipements', equipements),
                ('demandes', demandes), ('interventions', interventions), ('commandes', commandes), ('plan', plan)]:
    print(f'{nom:<14} {df.shape[0]:>7} lignes  {df.shape[1]:>3} colonnes')
```

## Cellule 3 (markdown)

## 1. Comment les tables se relient
```
residences ─< batiments ─< logements ─< equipements ─< interventions
                                │                         │
                                ├─< demandes  (logement_id) ┘ (demande_id_liee)
                                └─< commandes (logement_id ; vide = parties communes)
```
Un **équipement** est un *emplacement fonctionnel* : quand une chaudière est remplacée, l'`equipement_id` reste le même et `date_pose` change.

## Cellule 4 (code)

```python
residences[['residence_id', 'annee_construction', 'nb_logements', 'energie_chauffage', 'type_chauffage', 'etiquette_dpe_majoritaire', 'conso_ep_moyenne_kwh_m2_an']]
```

## Cellule 5 (code)

```python
# Interventions par année et par type
interventions.groupby([interventions.date_intervention.dt.year, 'type_intervention']).size().unstack().plot(kind='bar', stacked=True, figsize=(9, 4), title='Interventions par année')
plt.tight_layout(); plt.show()
```

## Cellule 6 (markdown)

## 2. Défi « détection précoce de panne »
**Question posée :** pour chaque équipement où `dans_perimetre_prediction == 'Oui'`, quel est le risque d'une **panne bloquante** (dépannage de gravité « Arrêt total ») entre le **01/01/2026 et le 30/09/2026** ?

Le jury détient la réponse. Vous n'avez que l'historique jusqu'au 31/12/2025 : il faut donc **valider votre approche dans le passé**. Exemple ci-dessous : on se place au 31/12/2024, on calcule des variables avec l'historique disponible à cette date, et on regarde si l'équipement est tombé en panne entre janvier et septembre 2025.

## Cellule 7 (code)

```python
PERIMETRE = equipements[equipements.dans_perimetre_prediction == 'Oui'].copy()

def variables(date_ref):
    """Variables calculées UNIQUEMENT avec l'historique antérieur à date_ref (pas de fuite d'information)."""
    date_ref = pd.Timestamp(date_ref)
    h = interventions[interventions.date_intervention <= date_ref]
    X = PERIMETRE[['equipement_id', 'famille', 'duree_vie_reference_ans']].copy()
    # date de pose connue à date_ref : dernier remplacement avant date_ref, sinon pose d'origine
    rempl = h[h.type_intervention == 'Remplacement'].groupby('equipement_id').date_intervention.max()
    pose = PERIMETRE.set_index('equipement_id').date_pose
    pose_prec = pd.to_datetime(PERIMETRE.set_index('equipement_id').date_pose_precedente)
    pose_ref = np.where(pose <= date_ref, pose, pose_prec)        # si remplacé après date_ref, on reprend la pose précédente
    pose_ref = pd.Series(pd.to_datetime(pose_ref), index=pose.index).fillna(pose)
    pose_ref = pd.concat([pose_ref, rempl], axis=1).max(axis=1)
    X['age_ans'] = ((date_ref - X.equipement_id.map(pose_ref)).dt.days / 365.25).values
    X['age_relatif'] = X.age_ans / X.duree_vie_reference_ans
    dep = h[(h.type_intervention == 'Dépannage') & (h.date_intervention > date_ref - pd.Timedelta(days=365))]
    X['nb_depannages_12m'] = X.equipement_id.map(dep.groupby('equipement_id').size()).fillna(0)
    return X

def cible(debut, fin):
    p = interventions[(interventions.type_intervention == 'Dépannage') & (interventions.gravite == 'Arrêt total') &
                      (interventions.date_intervention >= debut) & (interventions.date_intervention <= fin)]
    return PERIMETRE.equipement_id.isin(p.equipement_id).astype(int).values

X24 = variables('2024-12-31'); y25 = cible('2025-01-01', '2025-09-30')
print(f"Pannes bloquantes janv.-sept. 2025 : {y25.sum()} sur {len(y25)} équipements ({y25.mean():.1%})")
```

## Cellule 8 (code)

```python
# Baseline 1 : l'âge relatif seul (âge / durée de vie de référence)
print('AUC baseline âge :', round(roc_auc_score(y25, X24.age_relatif), 3))

# Baseline 2 : régression logistique sur 2 variables, entraînée au 31/12/2023 et testée au 31/12/2024
X23 = variables('2023-12-31'); y24 = cible('2024-01-01', '2024-09-30')
cols = ['age_relatif', 'nb_depannages_12m']
modele = LogisticRegression(max_iter=1000).fit(X23[cols], y24)
print('AUC baseline logistique :', round(roc_auc_score(y25, modele.predict_proba(X24[cols])[:, 1]), 3))
```

## Cellule 9 (markdown)

### À vous de jouer
La baseline n'utilise que l'âge et le nombre de dépannages. Pistes à explorer (liste non exhaustive) :
- les **visites d'entretien** : absences répétées, anomalies constatées ;
- les **symptômes**, la **gravité** et les **commentaires des techniciens** (texte libre) ;
- les **demandes des locataires** (texte libre, motifs, réitérations) ;
- les **rapports prestataire PDF** (dossier `rapports_prestataire/`) : un copilote GenAI peut-il en extraire des alertes ?
- l'**explicabilité** : le jury attend un score que l'on peut expliquer à une équipe non technique (pas de boîte noire).

## Cellule 10 (markdown)

### Format de soumission
Un fichier CSV avec **une ligne par équipement du périmètre** et deux colonnes : `equipement_id`, `score_risque` (plus le score est élevé, plus la panne est probable). Le jury mesure : la **capacité à classer** (AUC) et la **précision sur les 10 % d'équipements jugés les plus à risque** (combien de vraies pannes on aurait anticipées en inspectant ces équipements).

## Cellule 11 (code)

```python
X25 = variables('2025-12-31')
modele_final = LogisticRegression(max_iter=1000).fit(X24[cols], y25)
soumission = pd.DataFrame({'equipement_id': X25.equipement_id, 'score_risque': modele_final.predict_proba(X25[cols])[:, 1].round(4)})
soumission.to_csv('soumission_EQUIPE_X.csv', index=False)
soumission.sort_values('score_risque', ascending=False).head(10)
```

## Cellule 12 (markdown)

## 3. Défi « priorisation des rénovations »
La table `08_plan_investissement` (**hypothétique**) liste 29 opérations. Aujourd'hui, elles sont traitées par ordre d'inscription (`rang_actuel_chronologique`). L'enveloppe annuelle est plafonnée à **1,5 M€ (hypothèse)**.

Exemple naïf ci-dessous : coût par kWh économisé. À vous de construire un **scoring multicritère explicable** (énergie, DPE, pannes, coûts de maintenance, confort des locataires, calendrier réglementaire…).

## Cellule 13 (code)

```python
p = plan.merge(residences[['residence_id', 'surface_habitable_totale_m2', 'etiquette_dpe_majoritaire']], on='residence_id')
p['kwh_economises_an'] = p.gain_conso_ep_estime_kwh_m2_an * p.surface_habitable_totale_m2 * p.nb_logements_concernes / p.groupby('residence_id').nb_logements_concernes.transform('max')
p['euros_par_kwh_an'] = (p.cout_estime_ttc / p.kwh_economises_an).replace(np.inf, np.nan)
p[['operation_id', 'residence_id', 'type_operation', 'cout_estime_ttc', 'etiquette_dpe_majoritaire', 'euros_par_kwh_an', 'rang_actuel_chronologique']].sort_values('euros_par_kwh_an').head(10)
```

## Cellule 14 (code)

```python
# Coût de maintenance corrective par résidence (commandes 2018-2025) : un autre critère possible
cout = commandes.groupby('residence_id').montant_ttc.sum() / residences.set_index('residence_id').nb_logements
cout.sort_values().plot(kind='barh', title='Commandes 2018-2025 par logement (€ TTC)', figsize=(7, 3.5)); plt.tight_layout(); plt.show()
```

## Cellule 15 (markdown)

---
*Rappel des contraintes du défi : RGPD, scoring explicable, « l'IA recommande, l'humain décide ». Bon hackathon !*