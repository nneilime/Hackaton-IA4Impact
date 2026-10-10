import sys
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

f2 = "Détail desserte (Liste des trains groupes).csv"
df2 = pd.read_csv(f2, sep=';', encoding='utf-8-sig', low_memory=False)

print("Colonnes exactes :", df2.columns.tolist())
print("Nombre de lignes :", len(df2))
print("Nombre de circulations uniques :", df2['Numéro de circulation'].nunique())
print("\nÉchantillon de lignes :")
print(df2.head(5))

# Vérifier si une colonne mentionne groupe, scolaire, capacité, etc.
for c in df2.columns:
    print(f"Colonne '{c}': {df2[c].dtype}, unique count: {df2[c].nunique()}")

# Vérifier la liaison avec Data_Hackathon.csv
f1 = "Data_Hackathon.csv"
df1 = pd.read_csv(f1, sep=';', encoding='utf-8-sig')
t1_unique = set(df1['N° Train'])
t2_unique = set(df2['Numéro de circulation'])

trains_manquants = t1_unique - t2_unique
print(f"\nNombre de trains uniques dans Data_Hackathon : {len(t1_unique)}")
print(f"Nombre de trains de Data_Hackathon absents de df2 : {len(trains_manquants)}")
print(f"Liste des trains de Data_Hackathon absents : {sorted(list(trains_manquants))}")
