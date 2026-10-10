"""Validation dans le passé, selon la méthode de la notice du kit.

On se place à une date de référence, on calcule les scores avec l'historique
antérieur uniquement, puis on regarde quels équipements ont réellement eu un
dépannage « Arrêt total » dans les neuf mois suivants.

    python3 -m moteur.backtest      (depuis la racine du projet)

Réglage des poids : référence 31/12/2023, test janvier-septembre 2024.
Mesure publiée : référence 31/12/2024, test janvier-septembre 2025.
"""

import csv
import json
import os
from datetime import date

from moteur.bareme import scorer
from moteur.risque import _d

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DONNEES = os.path.join(RACINE, "donnees", "kit-batia", "donnees")


def lire(nom):
    with open(os.path.join(DONNEES, nom), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def charger():
    return {
        "residences": lire("01_residences.csv"),
        "logements": lire("03_logements.csv"),
        "equipements": lire("04_equipements.csv"),
        "demandes": lire("05_demandes_locataires.csv"),
        "interventions": lire("06_interventions.csv"),
    }


def cible(interventions, debut, fin):
    debut, fin = _d(debut), _d(fin)
    touches = set()
    for it in interventions:
        if it["type_intervention"] == "Dépannage" and it["gravite"] == "Arrêt total":
            d = _d(it["date_intervention"])
            if debut <= d <= fin:
                touches.add(it["equipement_id"])
    return touches


def auc(scores, positifs):
    """AUC de Mann-Whitney ; les ex aequo comptent pour moitié."""
    items = sorted(scores.items(), key=lambda kv: kv[1])
    rangs = {}
    i = 0
    while i < len(items):
        j = i
        while j + 1 < len(items) and items[j + 1][1] == items[i][1]:
            j += 1
        rang_moyen = (i + j) / 2 + 1
        for k in range(i, j + 1):
            rangs[items[k][0]] = rang_moyen
        i = j + 1
    n_pos = sum(1 for k in scores if k in positifs)
    n_neg = len(scores) - n_pos
    somme = sum(rangs[k] for k in scores if k in positifs)
    return (somme - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def top10(scores, positifs):
    n = round(len(scores) * 0.10)
    # Ex aequo départagés par identifiant, de façon déterministe.
    ordre = sorted(scores, key=lambda k: (-scores[k], k))[:n]
    captees = sum(1 for k in ordre if k in positifs)
    return n, captees


def evaluer(data, date_ref, debut, fin):
    perim = [e for e in data["equipements"] if e["dans_perimetre_prediction"] == "Oui"]
    res = scorer(perim, data["interventions"], data["demandes"], data["logements"],
                 date_ref, residences=data["residences"])
    positifs = cible(data["interventions"], debut, fin) & set(res)
    duree = {e["equipement_id"]: float(e["duree_vie_reference_ans"]) for e in perim}
    s_modele = {k: v["score"] for k, v in res.items()}
    s_age = {k: v["age"] / duree[k] for k, v in res.items()}
    n, capt_m = top10(s_modele, positifs)
    _, capt_a = top10(s_age, positifs)
    return {
        "date_reference": date_ref,
        "periode_test_debut": debut,
        "periode_test_fin": fin,
        "nb_equipements": len(res),
        "nb_pannes": len(positifs),
        "taux_base": round(len(positifs) / len(res), 4),
        "taille_top10": n,
        "auc": round(auc(s_modele, positifs), 3),
        "precision_top10": round(capt_m / n, 3),
        "pannes_captees_top10": capt_m,
        "auc_age_seul": round(auc(s_age, positifs), 3),
        "precision_top10_age_seul": round(capt_a / n, 3),
        "pannes_captees_top10_age_seul": capt_a,
        "baseline": "âge relatif seul (âge à la date de référence / durée de vie de référence), comme le notebook du kit",
    }


def main():
    data = charger()
    reglage = evaluer(data, "2023-12-31", "2024-01-01", "2024-09-30")
    mesure = evaluer(data, "2024-12-31", "2025-01-01", "2025-09-30")
    sortie = dict(mesure)
    sortie["reglage"] = reglage
    with open(os.path.join(RACINE, "moteur", "performance.json"), "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, indent=2)
    for nom, m in (("Réglage 2024", reglage), ("Mesure 2025", mesure)):
        print(f"{nom} : AUC {m['auc']} (âge seul {m['auc_age_seul']}) · "
              f"top 10 % {m['pannes_captees_top10']}/{m['taille_top10']} = {m['precision_top10']} "
              f"(âge seul {m['pannes_captees_top10_age_seul']} = {m['precision_top10_age_seul']}) · "
              f"pannes {m['nb_pannes']}/{m['nb_equipements']}")
    return sortie


if __name__ == "__main__":
    main()
