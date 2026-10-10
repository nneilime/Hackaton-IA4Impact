import sys
import os
import csv
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

def detect_bom_and_encoding(filepath):
    with open(filepath, 'rb') as f:
        raw_header = f.read(4)
    if raw_header.startswith(b'\xef\xbb\xbf'):
        bom = "UTF-8 BOM detected (\ufeff)"
        enc = "utf-8-sig"
    elif raw_header.startswith(b'\xff\xfe') or raw_header.startswith(b'\xfe\xff'):
        bom = "UTF-16 BOM detected"
        enc = "utf-16"
    else:
        bom = "No BOM detected"
        # Try full decode
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                f.read()
            enc = "utf-8"
        except UnicodeDecodeError:
            try:
                with open(filepath, 'r', encoding='cp1252') as f:
                    f.read()
                enc = "cp1252"
            except UnicodeDecodeError:
                enc = "latin-1"
    return enc, bom

def detect_delimiter(filepath, encoding):
    with open(filepath, 'r', encoding=encoding) as f:
        sample = "".join([f.readline() for _ in range(50)])
    lines = [l for l in sample.splitlines() if l.strip()]
    header = lines[0] if lines else ""
    counts = {',': header.count(','), ';': header.count(';'), '\t': header.count('\t'), '|': header.count('|')}
    return max(counts, key=counts.get), counts

f1 = "Data_Hackathon.csv"
f2 = "Détail desserte (Liste des trains groupes).csv"

enc1, bom1 = detect_bom_and_encoding(f1)
sep1, counts1 = detect_delimiter(f1, enc1)

enc2, bom2 = detect_bom_and_encoding(f2)
sep2, counts2 = detect_delimiter(f2, enc2)

print("="*60)
print("ENCODAGE ET SÉPARATEUR :")
print(f"Fichier 1 : {f1}")
print(f"  Encodage : {enc1} ({bom1})")
print(f"  Séparateur : {repr(sep1)} (occurrences première ligne: {counts1})")
print(f"Fichier 2 : {f2}")
print(f"  Encodage : {enc2} ({bom2})")
print(f"  Séparateur : {repr(sep2)} (occurrences première ligne: {counts2})")
print("="*60)

# Charger les données avec pandas
df1 = pd.read_csv(f1, sep=sep1, encoding=enc1)
df2 = pd.read_csv(f2, sep=sep2, encoding=enc2, low_memory=False)

print("\n" + "="*60)
print("QUESTION 1 : COLONNES ET TYPES")
print("="*60)
print(f"\n--- Data_Hackathon.csv ({df1.shape[0]} lignes, {df1.shape[1]} colonnes) ---")
for col in df1.columns:
    print(f"  - '{col}': {df1[col].dtype} (non-null: {df1[col].count()}/{len(df1)})")

print(f"\n--- 'Détail desserte (Liste des trains groupes).csv' ({df2.shape[0]} lignes, {df2.shape[1]} colonnes) ---")
for col in df2.columns:
    print(f"  - '{col}': {df2[col].dtype} (non-null: {df2[col].count()}/{len(df2)})")

print("\n" + "="*60)
print("QUESTION 2 : NUMÉROS DE TRAIN ET CORRESPONDANCE")
print("="*60)

# Colonne train dans df1
col_t1 = [c for c in df1.columns if "train" in c.lower()][0]
# Colonne train dans df2
col_t2_candidates = [c for c in df2.columns if "circulation" in c.lower() or "train" in c.lower()]
col_t2 = [c for c in df2.columns if "circulation" in c.lower()][0] if any("circulation" in c.lower() for c in df2.columns) else col_t2_candidates[0]

print(f"Colonne identifiée df1 : '{col_t1}'")
print(f"Colonne identifiée df2 : '{col_t2}'")

# Analyser les formats bruts
sample1_raw = df1[col_t1].dropna().head(10).tolist()
sample2_raw = df2[col_t2].dropna().head(10).tolist()
print(f"Échantillon brut df1['{col_t1}']: {sample1_raw[:5]}")
print(f"Échantillon brut df2['{col_t2}']: {sample2_raw[:5]}")

print(f"Type df1['{col_t1}']: {df1[col_t1].dtype}")
print(f"Type df2['{col_t2}']: {df2[col_t2].dtype}")

# Vérifions les valeurs uniques et les types
t1_unique = df1[col_t1].dropna().unique()
t2_unique = df2[col_t2].dropna().unique()
print(f"Nb de valeurs uniques {col_t1} dans df1 : {len(t1_unique)}")
print(f"Nb de valeurs uniques {col_t2} dans df2 : {len(t2_unique)}")

# Comparaison brute directe (sans conversion)
communs_brut = set(t1_unique).intersection(set(t2_unique))
print(f"Communs bruts (types originaux) : {len(communs_brut)}")

# Comparaison après conversion en string standardisé (strip, formatage int si float)
def standardize_train_no(val):
    if pd.isna(val):
        return None
    s = str(val).strip()
    # si s se termine par .0 (float converti)
    if s.endswith('.0'):
        s = s[:-2]
    # enlever les zéros non significatifs à gauche ou garder ?
    return s

t1_std = set(df1[col_t1].dropna().map(standardize_train_no))
t2_std = set(df2[col_t2].dropna().map(standardize_train_no))

communs_std = t1_std.intersection(t2_std)
pct_t1_dans_t2 = (len(communs_std) / len(t1_std)) * 100 if t1_std else 0

print(f"Nb uniques t1 (standardisé) : {len(t1_std)}")
print(f"Nb uniques t2 (standardisé) : {len(t2_std)}")
print(f"Nb de N° Train de df1 présents dans df2 : {len(communs_std)} sur {len(t1_std)} ({pct_t1_dans_t2:.2f}%)")

# Aussi en terme de lignes dans df1
df1_t_std = df1[col_t1].map(standardize_train_no)
nb_lignes_df1_match = df1_t_std.isin(t2_std).sum()
pct_lignes_df1 = (nb_lignes_df1_match / len(df1)) * 100
print(f"En lignes de df1 : {nb_lignes_df1_match} / {len(df1)} ({pct_lignes_df1:.2f}%)")

print("5 exemples de N° Train dans df1 :", list(t1_std)[:5])
print("5 exemples de Numéro de circulation dans df2 :", list(t2_std)[:5])
print("5 exemples de trains communs :", list(communs_std)[:5])

# Vérification formats : espaces, zéros initiaux, types
has_spaces_1 = any(" " in str(x) for x in t1_std)
has_spaces_2 = any(" " in str(x) for x in t2_std)
has_leading_zero_1 = any(str(x).startswith("0") for x in t1_std)
has_leading_zero_2 = any(str(x).startswith("0") for x in t2_std)
print(f"Espaces dans df1 : {has_spaces_1}, dans df2 : {has_spaces_2}")
print(f"Zéros au début dans df1 : {has_leading_zero_1}, dans df2 : {has_leading_zero_2}")

print("\n" + "="*60)
print("QUESTION 3 : MIN/MAX RÉGULARITÉ & SUPPRESSIONS ET VALEURS MANQUANTES")
print("="*60)

# Cherchons les colonnes relatives à régularité et suppressions dans df1 et df2
print("Colonnes potentielles dans df1 :")
for c in df1.columns:
    if any(k in c.lower() for k in ['reg', 'sup', 'taux', 'ponct', 'retard', 'annul']):
        print(f"  {c}: {df1[c].head(3).tolist()}")

print("\nColonnes potentielles dans df2 :")
for c in df2.columns:
    if any(k in c.lower() for k in ['reg', 'sup', 'taux', 'ponct', 'retard', 'annul']):
        print(f"  {c}: {df2[c].head(3).tolist()}")

# Statistiques détaillées sur df1 pour ces colonnes
print("\nStatistiques sur les colonnes cibles de df1 :")
reg_cols = [c for c in df1.columns if any(k in c.lower() for k in ['reg', 'rég'])]
sup_cols = [c for c in df1.columns if any(k in c.lower() for k in ['sup', 'annul'])]

for c in reg_cols + sup_cols:
    s = df1[c]
    # check if string with commas or percent
    print(f"Colonne: {c}")
    print(f"  Type initial: {s.dtype}")
    print(f"  Valeurs manquantes: {s.isna().sum()} ({s.isna().mean():.2%})")
    print(f"  Échantillon: {s.dropna().head(5).tolist()}")
    if pd.api.types.is_numeric_dtype(s):
        print(f"  Min: {s.min()}, Max: {s.max()}")
    else:
        # essayer conversion float
        try:
            s_clean = s.astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
            s_num = pd.to_numeric(s_clean, errors='coerce')
            print(f"  Converti en numérique -> Min: {s_num.min()}, Max: {s_num.max()}")
        except Exception as e:
            print(f"  Erreur conversion: {e}")

print("\nNombre de valeurs manquantes par colonne dans df1 :")
for col in df1.columns:
    print(f"  {col}: {df1[col].isna().sum()} / {len(df1)} ({df1[col].isna().mean():.2%})")

print("\nNombre de valeurs manquantes par colonne dans df2 :")
for col in df2.columns:
    print(f"  {col}: {df2[col].isna().sum()} / {len(df2)} ({df2[col].isna().mean():.2%})")

print("\n" + "="*60)
print("QUESTION 4 : ARRÊTS D'UN TRAIN COMMUN DANS L'ORDRE POUR UNE DATE")
print("="*60)
if len(communs_std) > 0:
    example_train = list(communs_std)[0]
    # Trouver une date pour ce train dans df2
    df2_ex = df2[df2[col_t2].map(standardize_train_no) == example_train]
    print(f"Train sélectionné : {example_train}")
    print(f"Nombre de lignes dans df2 pour ce train : {len(df2_ex)}")
    date_cols = [c for c in df2.columns if 'date' in c.lower() or 'jour' in c.lower()]
    print(f"Colonnes de date candidates dans df2 : {date_cols}")
    if date_cols:
        dcol = date_cols[0]
        dates_dispos = df2_ex[dcol].dropna().unique()
        print(f"Exemples de dates disponibles pour ce train : {dates_dispos[:5]}")
        selected_date = dates_dispos[0]
        df2_course = df2_ex[df2_ex[dcol] == selected_date]
        print(f"\nCourse pour la date : {selected_date}")
        print(f"Colonnes de df2_course : {df2_course.columns.tolist()}")
        print(df2_course.head(15))
    else:
        print(df2_ex.head(10))
else:
    print("Aucun train commun trouvé !")

