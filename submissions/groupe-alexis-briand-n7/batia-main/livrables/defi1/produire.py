"""Produit le livrable du défi 1 : un CSV `equipement_id, score_risque` au 31/12/2025.

    python3 livrables/defi1/produire.py          (depuis la racine du dépôt)

Le score est la probabilité d'un dépannage « Arrêt total » entre janvier et
septembre 2026, calculée par le barème `poc/preavis/moteur/bareme.py` avec
l'historique antérieur au 31/12/2025 seulement.
"""

import csv
import json
import os
import re
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RACINE, "poc", "preavis"))

from moteur import backtest
from moteur.bareme import scorer

DATE_REF = "2025-12-31"
PART_BUDGET = 0.10
MOTIF_RN = re.compile(r"^Remplacement déjà jugé nécessaire le (.+)$")


def main():
    data = backtest.charger()
    perim = [e for e in data["equipements"] if e["dans_perimetre_prediction"] == "Oui"]
    res = scorer(perim, data["interventions"], data["demandes"], data["logements"], DATE_REF)
    lignes = sorted(((k, v["score"] / 100.0, v["points"]) for k, v in res.items()), key=lambda x: (-x[1], x[0]))
    dossier = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(dossier, "score_risque_2026.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["equipement_id", "score_risque"])
        for k, p, _ in lignes:
            w.writerow([k, f"{p:.4f}"])
    with open(os.path.join(dossier, "detail_2026.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rang", "equipement_id", "score_risque", "points", "bande", "pannes_observees_2025", "raisons", "autres_situations"])
        for i, (k, p, pts) in enumerate(lignes, 1):
            w.writerow([i, k, f"{p:.4f}", pts, res[k]["bande"]["nom"], res[k]["bande"]["neuf_mois"], " ; ".join(f"{r['texte']} ({r['points']:+d})" for r in res[k]["raisons"]), " ; ".join(f"{r['texte']} ({r['points']:+d})" for r in res[k]["autres"])])
    nb_budget = round(len(lignes) * PART_BUDGET)
    seuil = lignes[nb_budget - 1][2]
    equipements = []
    for i, (k, p, pts) in enumerate(lignes, 1):
        r = res[k]
        rn = next((MOTIF_RN.match(x["texte"]).group(1) for x in r["raisons"] if MOTIF_RN.match(x["texte"])), None)
        equipements.append({
            "rang": i,
            "equipement_id": k,
            "points": pts,
            "bande": r["bande"],
            "raisons": r["raisons"],
            "autres_situations": r["autres"],
            "remplacement_juge_necessaire_le": rn,
            "dans_budget": i <= nb_budget,
            "age_ans": r["age"],
            "pose": r["pose"],
            "probabilite_pct": r["score"],
        })
    contrat = {
        "date_reference": DATE_REF,
        "horizon": "janvier à septembre 2026",
        "nb_equipements": len(lignes),
        "budget": {"part": PART_BUDGET, "nb": nb_budget, "seuil_points": seuil, "nb_au_seuil_ou_plus": sum(1 for x in lignes if x[2] >= seuil)},
        "source": "poc/preavis/moteur/bareme.py",
        "equipements": equipements,
    }
    with open(os.path.join(dossier, "detail_2026.json"), "w", encoding="utf-8") as f:
        json.dump(contrat, f, ensure_ascii=False, indent=1)
    print(f"{len(lignes)} équipements écrits ; seuil des 10 % les plus à risque : {seuil} points ({contrat['budget']['nb_au_seuil_ou_plus']} à ce seuil ou plus pour {nb_budget} visites)")


if __name__ == "__main__":
    main()
