"""
controle_donnees_reelles.py - Controle du calculateur sur les VRAIS fichiers.
Independant du code d'Antigravity : il n'utilise que le "contrat d'interface" du brief
et recalcule lui-meme quelques valeurs avec pandas pour comparer.

Lancer dans le dossier du projet (environnement active) :
    python controle_donnees_reelles.py
ou, si les noms de fichiers different :
    python controle_donnees_reelles.py "Data_Hackathon.csv" "Detail desserte.csv"
"""

import sys
import unicodedata

import pandas as pd

import indice_confiance as ic

CSV_TRAINS = "Data_Hackathon.csv"
CSV_DESSERTE = "Détail desserte (Liste des trains groupes).csv"
SEUIL_CHRONIQUE = 10.0     # seuil de suppressions chroniques du brief


def normaliser(texte):
    texte = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode()
    return "".join(c if c.isalnum() else "_" for c in texte.lower())


def nombre(serie):
    texte = serie.astype(str).str.replace(",", ".", regex=False).str.replace("%", "", regex=False)
    return pd.to_numeric(texte.str.strip(), errors="coerce")


def main():
    chemin_trains = sys.argv[1] if len(sys.argv) > 1 else CSV_TRAINS
    chemin_desserte = sys.argv[2] if len(sys.argv) > 2 else CSV_DESSERTE
    anomalies = 0

    # ------------------------------------------------------------------
    print("=== 1. Profils des trains ===")
    profils = ic.charger_profils_trains(chemin_trains)
    print(f"{len(profils)} trains charges (attendu : 217)")
    tableau = pd.DataFrame(profils).T[["regularite_pct", "suppression_pct",
                                       "stabilite_pct", "frequentation_percentile"]].astype(float)
    print(tableau.quantile([0, 0.1, 0.25, 0.5, 0.75, 0.9, 1]).round(1).to_string())
    chroniques = int((tableau["suppression_pct"] >= SEUIL_CHRONIQUE).sum())
    print(f"Trains avec suppressions >= {SEUIL_CHRONIQUE} % : {chroniques} "
          f"({100 * chroniques / len(tableau):.0f} %)")

    for nom, bas, haut in [("regularite_pct", 0, 100), ("suppression_pct", 0, 100),
                           ("stabilite_pct", 0, 100), ("frequentation_percentile", 0, 1)]:
        hors = tableau[(tableau[nom] < bas) | (tableau[nom] > haut) | tableau[nom].isna()]
        if len(hors) > 0:
            anomalies += 1
            print(f"ANOMALIE : {len(hors)} trains avec {nom} hors de [{bas}, {haut}] ou vide")

    # ------------------------------------------------------------------
    print("\n=== 2. Controle independant du taux de suppression (piege 'Taux SUPP' vide) ===")
    brut = pd.read_csv(chemin_trains, sep=";", encoding="utf-8-sig")
    brut.columns = [normaliser(c) for c in brut.columns]
    col_train = next(c for c in brut.columns if "train" in c and "taux" not in c and "nombre" not in c)
    col_supp = next(c for c in brut.columns if "nombre" in c and "suppression" in c)
    col_real = next(c for c in brut.columns if "realise" in c)
    brut["_train"] = nombre(brut[col_train])
    brut["_supp"] = nombre(brut[col_supp]).fillna(0)
    brut["_real"] = nombre(brut[col_real]).fillna(0)
    # trains qui ont a la fois des mois sans suppression et des mois avec : les plus pieges
    echantillon = []
    for numero, groupe in brut.groupby("_train"):
        if (groupe["_supp"] == 0).any() and (groupe["_supp"] > 0).any() and groupe["_real"].sum() > 0:
            echantillon.append(numero)
        if len(echantillon) == 5:
            break
    for numero in echantillon:
        groupe = brut[brut["_train"] == numero]
        attendu = min(100.0, 100 * groupe["_supp"].sum() / groupe["_real"].sum())
        obtenu = profils[str(int(numero))]["suppression_pct"]
        etat = "OK" if abs(attendu - obtenu) < 0.01 else "ECART"
        if etat == "ECART":
            anomalies += 1
        print(f"train {int(numero)} : attendu {attendu:.2f} %, obtenu {obtenu:.2f} %  -> {etat}")
    if not echantillon:
        print("(aucun train de ce type trouve)")

    # ------------------------------------------------------------------
    print("\n=== 3. Detail de desserte et trains eligibles ===")
    desserte = ic.charger_desserte(chemin_desserte, trains_utiles=set(profils))
    eligibles = ic.trains_eligibles(desserte)
    absents = sorted(set(profils) - set(eligibles))
    print(f"{len(desserte)} arrets gardes ; {len(eligibles)} trains eligibles sur {len(profils)} "
          f"(attendu : 210 sur 217)")
    print(f"Trains sans desserte ({len(absents)}) : {absents} "
          f"(attendu : 7 trains estivaux, ex. 872826, 876163)")

    # ------------------------------------------------------------------
    print("\n=== 4. Exemple de bout en bout (vrai train, vraie gare, site fictif) ===")
    numero = sorted(eligibles)[0]
    lignes = desserte[desserte["train"] == int(numero)].sort_values(["date", "ordre"])
    jour = lignes["date"].iloc[0]
    arrets = lignes[lignes["date"] == jour]
    derniere_gare = arrets.iloc[-1]["gare"]
    arrivee = ic.heure_arrivee_en_gare(desserte, numero, jour, derniere_gare)
    print(f"Train {numero} le {jour.date()} : arrive a '{derniere_gare}' a {arrivee} min depuis minuit")

    site = {"distance_m": 800, "bus_unique": False, "trottoir_ok": True,
            "pique_nique_couvert": True, "consignes": False, "themes": ["histoire"],
            "note_moyenne": 4.2, "nb_avis": 5}
    for effectif, options, minutes_avant_activite in [(28, 5, 40), (28, 5, 20), (30, 25, 40)]:
        resultat = ic.calculer_indice(profils[numero], site, effectif=effectif,
                                      options_actives=options, theme_projet="histoire",
                                      heure_arrivee_gare=arrivee,
                                      heure_debut_activite=arrivee + minutes_avant_activite)
        print(f"  classe {effectif} + options {options}, activite {minutes_avant_activite} min apres l'arrivee"
              f" -> {resultat['score']}/100 {resultat['couleur']}"
              f"{' BLOQUE' if resultat['bloque'] else ''}")
        print(f"     {resultat['message']}")

    # ------------------------------------------------------------------
    print("\n" + ("Aucune anomalie detectee." if anomalies == 0
                  else f"{anomalies} anomalie(s) : colle-moi tout cet affichage."))


if __name__ == "__main__":
    main()
