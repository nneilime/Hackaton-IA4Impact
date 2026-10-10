import pandas as pd

print("=== SITES.CSV ===")
df_sites = pd.read_csv("donnees_simulees/sites.csv", sep=";", encoding="utf-8-sig")
print("Colonnes :", df_sites.columns.tolist())
print("Nb lignes :", len(df_sites))
print(df_sites.head(5))

print("\n=== AVIS.CSV ===")
df_avis = pd.read_csv("donnees_simulees/avis.csv", sep=";", encoding="utf-8-sig")
print("Colonnes :", df_avis.columns.tolist())
print("Nb lignes :", len(df_avis))
print(df_avis.head(5))
print("Piège sans avis :")
print(df_avis[df_avis['nb_avis'] == 0])

print("\n=== OPTIONS.CSV ===")
df_options = pd.read_csv("donnees_simulees/options.csv", sep=";", encoding="utf-8-sig")
print("Colonnes :", df_options.columns.tolist())
print("Nb lignes :", len(df_options))
print("Nb trains distincts :", df_options['n_train'].nunique())
print(df_options.head(5))
print("Piège presque plein :")
print(df_options[df_options['places_prises'] >= 40])
print("Max places prises :", df_options['places_prises'].max())
print("Min places prises :", df_options['places_prises'].min())
print("Vérification absence de nom d'école :", any('ecole' in c.lower() or 'etablissement' in c.lower() for c in df_options.columns))

# Vérification pièges sites
print("\n=== PIÈGES SITES ===")
print("Site à 35 min sans bus (>20 min sans bus) :")
print(df_sites[df_sites['distance_m'] >= 1600])

print("\nSite trottoir_ok == False :")
print(df_sites[df_sites['trottoir_ok'] == False])

# Vérifier correspondance des gares avec la desserte
df_desserte = pd.read_csv("Détail desserte (Liste des trains groupes).csv", sep=";", encoding="utf-8-sig", usecols=['Libellé arrêt'])
gares_desserte = set(df_desserte['Libellé arrêt'].dropna().unique())
gares_sites = set(df_sites['gare_proche'])
gares_inconnues = gares_sites - gares_desserte
print(f"\nGares des sites absentes de la desserte : {gares_inconnues} (doit être vide)")
