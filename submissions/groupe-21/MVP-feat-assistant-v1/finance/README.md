# Base de données financière FICTIVE (`data/finance.db`)

Base SQLite utilisée par l’assistant pour tout ce qui est chiffré : taux actuels et futurs, simulations de crédit,
capacité d’emprunt, projections d’épargne, tarifs, cartes, offres de compte et délais.

**Toutes les valeurs sont inventées** (ordres de grandeur plausibles du marché français 2016-2026) pour un prototype
de hackathon : ni offre, ni information officielle de la Caisse d’Épargne ou de BPCE.

```sh
.venv/bin/python -m finance.build_db      # régénère data/finance.db (déterministe, bibliothèque standard)
sqlite3 data/finance.db ".tables"
```

## Contenu

| Table | Contenu |
|---|---|
| `meta` | mois de référence (2026-09), fin des prévisions (2028-12), méthode, avertissement |
| `series`, `observations` | 16 séries mensuelles : BCE, Euribor 3 mois, OAT 10 ans, inflation, crédit immobilier 15/20/25 ans, prêt personnel, Livret A/LDDS, LEP, CEL, PEL, Livret Jeune, Livret B, compte à terme, fonds euros. Historique 2016-01 → 2026-09 (`scenario = 'reel'`), prévisions 2026-10 → 2028-12 en trois scénarios `bas`, `central`, `haut` |
| `produits_credit` | 13 crédits : immobilier taux fixe et modulable, PTZ, PAS, relais, éco-PTZ, travaux, personnel, auto neuf, occasion, véhicule propre, étudiant, renouvelable (montants, durées, frais, garantie, assurance, conditions) |
| `grille_taux_credit` | taux nominaux actuels par produit, tranche de durée et profil (`excellent`, `standard`, `fragile`) |
| `assurance_emprunteur` | taux annuels en % du capital, par tranche d’âge et tabagisme |
| `taux_usure` | seuils légaux par catégorie de crédit |
| `produits_epargne` | 14 placements : livrets réglementés, Livret B, CEL, PEL, compte à terme, assurance vie (fonds euros, gestion prudente, équilibrée, dynamique), PER, PEA ; plafonds, fiscalité, risque, frais |
| `rendements_annuels`, `hypotheses_rendement` | rendements passés 2016-2025 et rendement attendu / volatilité des supports non garantis |
| `cartes`, `offres_compte` | 4 cartes (cotisation, plafonds, assurances) et 5 offres (Initial, Confort Classic, Confort Premier, 18-25 ans, clientèle fragile) |
| `tarifs` | 39 lignes de brochure tarifaire (compte, virements, cartes, chèques, incidents, découvert, crédit, succession) |
| `delais` | 20 délais (réclamation, fraude, carte, virement, crédit, épargne, conseiller) |

## Méthode des prévisions

- Taux BCE, OAT 10 ans et inflation : trois trajectoires d’hypothèse jusqu’à fin 2028.
- Crédit immobilier : taux actuel + 0,8 × variation de l’OAT + 0,2 × variation de la BCE.
- Prêt personnel : taux actuel + 0,6 × variation de l’Euribor.
- Livret A : formule réglementaire simplifiée (moyenne de l’inflation et du taux interbancaire, arrondie au dixième,
  0,5 % au minimum), révisée en février et en août ; LEP, CEL, Livret Jeune et Livret B en découlent.

## Moteur de calcul (`finance/engine.py`)

| Fonction | Outil du modèle | Calcul |
|---|---|---|
| `simulate_loan` | `simuler_credit` | mensualité (annuité), assurance, frais, garantie, TAEG actuariel, coût total, endettement, taux d’usure ; démarrage futur → taux prévu dans les 3 scénarios |
| `borrowing_capacity` | `capacite_emprunt` | capital maximal pour 35 % d’endettement assurance comprise, budget d’achat (ancien, neuf) |
| `forecast` | `prevoir_taux` | historique de fin d’année et prévisions trimestrielles |
| `project_savings` | `simuler_epargne` | capital final selon les 3 scénarios, plafonds, frais, fiscalité estimée |
| `catalogue` | `catalogue` | listes filtrables de toutes les tables de référence |

`to_text()` met chaque résultat en forme pour le modèle, avec tous les chiffres déjà calculés et arrondis : le
serveur refuse toute réponse dont un nombre n’y figure pas.
