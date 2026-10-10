import sys
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

df1 = pd.read_csv("Data_Hackathon.csv", sep=';', encoding='utf-8-sig')
df2 = pd.read_csv("Détail desserte (Liste des trains groupes).csv", sep=';', encoding='utf-8-sig', low_memory=False)

print("--- Data_Hackathon Dates / Mois / Années ---")
print("Années df1 :", df1['Année'].value_counts().to_dict())
print("Mois df1 :", df1['Mois'].value_counts().to_dict())

print("\n--- Détail desserte Dates ---")
print("Exemples de dates df2 :", df2['Date'].head(10).tolist())
# Convertir un échantillon pour voir les années dans df2
df2_dates = pd.to_datetime(df2['Date'], format='%d/%m/%Y', errors='coerce')
print("Années dans df2 :", df2_dates.dt.year.value_counts().to_dict())
print("Mois dans df2 :", df2_dates.dt.month.value_counts().to_dict())

print("\n--- Analyse des suppressions et Taux SUPP ---")
zero_supp = df1[df1['Nombre de suppressions'] == 0]
print(f"Lignes avec 0 suppressions : {len(zero_supp)}")
print(f"Lignes avec 0 suppressions et Taux SUPP NaN : {zero_supp['Taux SUPP'].isna().sum()}")

# Inspecter le max de Taux SUPP (110% ?)
t_supp_clean = df1['Taux SUPP'].dropna().str.replace('%', '').str.replace(',', '.').astype(float)
idx_max = t_supp_clean.idxmax()
print(f"Ligne max Taux SUPP :")
print(df1.loc[idx_max, ['Année', 'Mois', 'N° Train', 'Circ Prévues Théorique', 'Circ Prévues réalisé', 'Nombre de suppressions', 'Taux SUPP']])

# Inspecter le train 872605 pour la question 4
ex_train = 872605
df2_ex = df2[(df2['Numéro de circulation'] == ex_train) & (df2['Date'] == '30/4/2026')].sort_values('Ordre desserte')
print("\n--- Arrêts du train 872605 le 30/4/2026 ---")
print(df2_ex[['Ordre desserte', 'Code arrêt', 'Libellé arrêt', "Heure d'arrivée", "Heure de départ"]].to_string(index=False))

# Regarder les 7 trains de df1 absents de df2
t1_not_in_t2 = set(df1['N° Train']) - set(df2['Numéro de circulation'])
print(f"\nTrains de df1 absents de df2 ({len(t1_not_in_t2)}) :", t1_not_in_t2)
print("Détail de ces trains dans df1 :")
print(df1[df1['N° Train'].isin(t1_not_in_t2)][['N° Train', 'Axe', 'Origine / Destination', 'Année', 'Mois']].drop_duplicates())

