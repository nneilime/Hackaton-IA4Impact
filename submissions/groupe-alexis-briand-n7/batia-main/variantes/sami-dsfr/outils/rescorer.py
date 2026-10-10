import csv
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(ICI))

from moteur.bareme import scorer


def lire(dossier, nom):
    with open(os.path.join(dossier, nom), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main(dossier, date_ref, sortie):
    equipements = lire(dossier, "04_equipements.csv")
    perimetre = [e for e in equipements if e.get("dans_perimetre_prediction", "Oui") in ("Oui", "")]
    res = scorer(perimetre, lire(dossier, "06_interventions.csv"), lire(dossier, "05_demandes_locataires.csv"), lire(dossier, "03_logements.csv"), date_ref)
    lignes = sorted(((k, v["score"] / 100.0, v["points"]) for k, v in res.items()), key=lambda x: (-x[1], x[0]))
    os.makedirs(os.path.dirname(sortie), exist_ok=True)
    with open(sortie, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rang", "equipement_id", "score_risque", "points", "bande", "pannes_observees_2025", "raisons", "autres_situations"])
        for i, (k, p, pts) in enumerate(lignes, 1):
            v = res[k]
            w.writerow([i, k, f"{p:.4f}", pts, v["bande"]["nom"], v["bande"]["neuf_mois"],
                        " ; ".join(f"{r['texte']} ({r['points']:+d})" for r in v["raisons"]),
                        " ; ".join(f"{r['texte']} ({r['points']:+d})" for r in v.get("autres", []))])
    print(len(lignes))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
