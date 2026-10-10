"""Rejeu de 2025 : ce que le barème voyait au 1er janvier 2025, et ce qui est arrivé ensuite.

    python3 rejeu/preparer.py          (depuis la racine du projet)

Écrit `rejeu/donnees/rejeu-2025.json`, lu par `rejeu/rejeu.mjs`. Tout est recalculé
ici à partir des CSV du kit (données fictives), avec le barème de `moteur/` :

- la date de référence est le 31/12/2024 : le barème ne lit que les lignes
  antérieures au 1er janvier 2025 (même règle que `moteur/backtest.py`) ;
- les 128 visites sont les 10 % du périmètre (1 285 équipements) aux scores les
  plus hauts, ex aequo départagés par identifiant, comme `backtest.top10` ;
- le choix par l'âge prend les 128 équipements dont l'âge rapporté à la durée de
  vie de référence est le plus haut, même départage ;
- une panne bloquante est un dépannage de gravité « Arrêt total » entre le
  1er janvier et le 30 septembre 2025 ; un équipement compte une fois, à la date
  de sa première panne de la période (les compteurs comptent des équipements,
  comme `BAREME.md`).

Le script s'arrête en erreur si ses comptes diffèrent de ceux de
`moteur.backtest.evaluer` : l'écran ne montre que des chiffres recalculés.
"""

import json
import os
import sys
from collections import Counter

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from moteur.backtest import charger, evaluer  # noqa: E402
from moteur.bareme import scorer  # noqa: E402

REFERENCE = "2024-12-31"
DEBUT, FIN = "2025-01-01", "2025-09-30"
SORTIE = os.path.join(RACINE, "rejeu", "donnees", "rejeu-2025.json")

# Positions fictives des secteurs de résidence, celles de la carte de BâtIA (carte/demo/residences.mjs).
POSITIONS = {
    "RES-A": [43.646, 1.392], "RES-B": [43.668, 1.447], "RES-C": [43.618, 1.486], "RES-D": [43.566, 1.398],
    "RES-E": [43.584, 1.522], "RES-F": [43.652, 1.503], "RES-G": [43.574, 1.452], "RES-H": [43.617, 1.346],
}


def premiers(scores, n):
    return sorted(scores, key=lambda k: (-scores[k], k))[:n]


def main():
    data = charger()
    perim = [e for e in data["equipements"] if e["dans_perimetre_prediction"] == "Oui"]
    res = scorer(perim, data["interventions"], data["demandes"], data["logements"], REFERENCE,
                 residences=data["residences"])
    duree = {e["equipement_id"]: float(e["duree_vie_reference_ans"]) for e in perim}
    s_bareme = {k: v["score"] for k, v in res.items()}
    s_age = {k: v["age"] / duree[k] for k, v in res.items()}
    n = round(len(res) * 0.10)
    visites = set(premiers(s_bareme, n))
    plus_vieux = set(premiers(s_age, n))

    # Pannes bloquantes de la période : la première de chaque équipement du périmètre.
    pannes = {}
    evenements = 0
    for it in data["interventions"]:
        if it["type_intervention"] != "Dépannage" or it["gravite"] != "Arrêt total":
            continue
        jour = it["date_intervention"][:10]
        eid = it["equipement_id"]
        if not (DEBUT <= jour <= FIN) or eid not in res:
            continue
        evenements += 1
        if eid not in pannes or jour < pannes[eid]:
            pannes[eid] = jour

    vues = sum(1 for k in pannes if k in visites)
    vues_age = sum(1 for k in pannes if k in plus_vieux)

    # Contrôle : les mêmes comptes que le test du moteur.
    m = evaluer(data, REFERENCE, DEBUT, FIN)
    attendu = (m["nb_equipements"], m["nb_pannes"], m["taille_top10"], m["pannes_captees_top10"], m["pannes_captees_top10_age_seul"])
    obtenu = (len(res), len(pannes), n, vues, vues_age)
    if attendu != obtenu:
        sys.exit(f"Écart avec moteur.backtest : attendu {attendu}, obtenu {obtenu}")

    eq = {e["equipement_id"]: e for e in perim}
    ordre_res = sorted(POSITIONS)
    # Dans chaque résidence, les équipements sont rangés par score au 1er janvier 2025 :
    # les 128 visités forment la base de chaque brique, comme la base de la brique de BâtIA.
    lignes = sorted(res, key=lambda k: (eq[k]["residence_id"], -s_bareme[k], k))
    equipements = [{
        "id": k,
        "r": eq[k]["residence_id"],
        "famille": eq[k]["libelle_famille"],
        "points": res[k]["points"],
        "visite": k in visites,
        "plusVieux": k in plus_vieux,
        "panne": pannes.get(k),
    } for k in lignes]

    par_mois = Counter(j[:7] for j in pannes.values())
    sortie = {
        "titre": "Rejeu de 2025, données fictives du kit BâtIA",
        "reference": REFERENCE,
        "debut": DEBUT,
        "fin": FIN,
        "equipements": len(res),
        "visites": n,
        "pannes": len(pannes),
        "evenements": evenements,
        "vues": vues,
        "vuesAge": vues_age,
        "auc": m["auc"],
        "aucAge": m["auc_age_seul"],
        "pannesParMois": dict(sorted(par_mois.items())),
        "residences": [{
            "id": r, "lettre": r.replace("RES-", ""), "position": POSITIONS[r],
            "equipements": sum(1 for k in res if eq[k]["residence_id"] == r),
            "visites": sum(1 for k in visites if eq[k]["residence_id"] == r),
            "pannes": sum(1 for k in pannes if eq[k]["residence_id"] == r),
        } for r in ordre_res],
        "liste": equipements,
        "verification": {
            "moteur": "moteur.backtest.evaluer, référence 31/12/2024, test janvier-septembre 2025",
            "bareme_md": {"equipements": 1285, "pannes": 76, "visites": 128, "vues": 43, "vuesAge": 16},
            "calcule": {"equipements": len(res), "pannes": len(pannes), "visites": n, "vues": vues, "vuesAge": vues_age},
        },
    }
    os.makedirs(os.path.dirname(SORTIE), exist_ok=True)
    with open(SORTIE, "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(res)} équipements · {n} visites au 1er janvier 2025 · {len(pannes)} pannes bloquantes "
          f"({evenements} dépannages « Arrêt total ») de janvier à septembre 2025")
    print(f"Méthode de l'équipe : {vues} sur {len(pannes)} · les {n} plus vieux : {vues_age} sur {len(pannes)}")
    print("Par mois :", ", ".join(f"{k} {v}" for k, v in sorted(par_mois.items())))
    print("Par résidence :", ", ".join(f"{x['lettre']} {x['equipements']} équip. {x['visites']} visites {x['pannes']} pannes" for x in sortie["residences"]))
    print("Écrit :", os.path.relpath(SORTIE, RACINE))


if __name__ == "__main__":
    main()
