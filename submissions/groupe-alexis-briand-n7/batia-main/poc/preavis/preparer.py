"""Prépare les données de l'application à partir des CSV du kit.

    python3 preparer.py

Lit donnees/kit-batia/donnees/*.csv (sans rien y modifier), calcule le risque
avec moteur/risque.py à la date de référence du 31/12/2025, mesure la
performance dans le passé (moteur/backtest.py) et écrit :
  app/donnees/parc.json     le parc, les équipements suivis, leurs scores et raisons
  app/donnees/journal.json  l'historique des demandes et des interventions
"""

import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

RACINE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RACINE)

from moteur import backtest  # noqa: E402
from moteur.bareme import scorer  # noqa: E402

DONNEES = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(RACINE, "donnees", "kit-batia", "donnees")
SORTIE = os.path.join(RACINE, "app", "donnees")
DATE_REF = "2025-12-31"
NIVEAUX = {"alerte": 2, "vigilance": 1, "calme": 0}


def lire(nom):
    with open(os.path.join(DONNEES, nom), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def nombre(x):
    if x in ("", None):
        return None
    try:
        v = float(x)
    except ValueError:
        return x
    return int(v) if v.is_integer() else v


def main():
    residences = lire("01_residences.csv")
    batiments = lire("02_batiments.csv")
    logements = lire("03_logements.csv")
    equipements = lire("04_equipements.csv")
    demandes = lire("05_demandes_locataires.csv")
    interventions = lire("06_interventions.csv")
    prestataires = {p["prestataire_id"]: p["nom"] for p in lire("09_prestataires.csv")}
    operations = lire("08_plan_investissement.csv")

    perim = [e for e in equipements if e["dans_perimetre_prediction"] == "Oui"]
    scores = scorer(perim, interventions, demandes, logements, DATE_REF, residences=residences)

    # Performance réellement mesurée dans le passé.
    perf = backtest.main()

    # Rangs et niveaux : alerte = 10 % les plus à risque, vigilance = 25 %.
    ordre = sorted(scores, key=lambda k: (-scores[k]["score"], k))
    n = len(ordre)
    n_alerte, n_vigil = round(n * 0.10), round(n * 0.25)
    rang = {k: i + 1 for i, k in enumerate(ordre)}

    def niveau(eid):
        r = rang[eid]
        return "alerte" if r <= n_alerte else ("vigilance" if r <= n_vigil else "calme")

    lgt_par_id = {l["logement_id"]: l for l in logements}
    eq_out = []
    for e in perim:
        eid = e["equipement_id"]
        s = scores[eid]
        eq_out.append({
            "id": eid,
            "fam": e["famille"],
            "lib": e["libelle_famille"],
            "rattachement": e["niveau_rattachement"],
            "res": e["residence_id"],
            "bat": e["batiment_id"],
            "lgt": e["logement_id"] or None,
            "pose": s["pose"],
            "origine_pose": e["origine_date_pose"],
            "age": s["age"],
            "duree_vie": nombre(e["duree_vie_reference_ans"]),
            "contrat": e["sous_contrat_entretien"],
            "visite": e["visite_annuelle_prevue"],
            "presta": e["prestataire_id"],
            "presta_nom": prestataires.get(e["prestataire_id"], ""),
            "score": s["score"],
            "rang": rang[eid],
            "niveau": niveau(eid),
            "raisons": s["raisons"],
        })
    eq_out.sort(key=lambda x: x["rang"])

    # Demandes : index par logement / bâtiment, et 12 / 24 derniers mois.
    dem_lgt, dem_com = defaultdict(list), defaultdict(list)
    for d in demandes:
        ligne = [d["date_creation"], d["objet"], d["motif"], d["texte_demande"], d["priorite"],
                 d["demande_reouverte"], nombre(d["nb_echanges"])]
        if d["logement_id"]:
            dem_lgt[d["logement_id"]].append(ligne)
        if d["parties"] == "Communes" or not d["logement_id"]:
            dem_com[d["batiment_id"] or d["residence_id"]].append(ligne)
    for dico in (dem_lgt, dem_com):
        for v in dico.values():
            v.sort(key=lambda x: x[0])

    eq_par_lgt = defaultdict(list)
    eq_par_bat = defaultdict(list)
    for e in eq_out:
        if e["lgt"]:
            eq_par_lgt[e["lgt"]].append(e)
        else:
            eq_par_bat[e["bat"]].append(e)

    lgt_out = []
    for l in logements:
        lid = l["logement_id"]
        ds = dem_lgt.get(lid, [])
        d12 = [x for x in ds if x[0] >= "2025-01-01"]
        d24 = [x for x in ds if x[0] >= "2024-01-01"]
        rep = Counter(x[1] for x in d24).most_common(1)
        eqs = eq_par_lgt.get(lid, [])
        score = max((e["score"] for e in eqs), default=0)
        niv = max((e["niveau"] for e in eqs), key=lambda v: NIVEAUX[v], default="calme")
        lgt_out.append({
            "id": lid,
            "bat": l["batiment_id"],
            "res": l["residence_id"],
            "typo": l["typologie"],
            "surface": nombre(l["surface_habitable_m2"]),
            "etage": nombre(l["etage"]),
            "dpe": l["dpe_etiquette_globale"],
            "dpe_e": l["dpe_etiquette_energie"],
            "dpe_g": l["dpe_etiquette_ges"],
            "conso": nombre(l["dpe_conso_ep_kwh_m2_an"]),
            "ges": nombre(l["dpe_ges_kgco2_m2_an"]),
            "dpe_date": l["dpe_date"],
            "dpe_methode": l["dpe_methode"],
            "rotations": nombre(l["nb_changements_locataire_2018_2025"]),
            "entree": l["date_entree_locataire_actuel"],
            "statut": l["statut_occupation"],
            "demandes_total": len(ds),
            "demandes_12m": len(d12),
            "demandes_reouvertes": sum(1 for x in ds if x[5] == "Oui"),
            "repetition": {"objet": rep[0][0], "n": rep[0][1]} if rep and rep[0][1] >= 2 else None,
            "score": score,
            "niveau": niv,
            "eq": [e["id"] for e in eqs],
        })

    bat_out = []
    for b in batiments:
        bat_out.append({
            "id": b["batiment_id"],
            "res": b["residence_id"],
            "niveaux": nombre(b["nb_niveaux"]),
            "nb_logements": nombre(b["nb_logements"]),
            "ascenseur": b["ascenseur"],
            "eq": [e["id"] for e in eq_par_bat.get(b["batiment_id"], [])],
        })

    # Arrêts totaux par résidence et par an (tous équipements).
    arrets = defaultdict(Counter)
    for it in interventions:
        if it["type_intervention"] == "Dépannage" and it["gravite"] == "Arrêt total":
            arrets[it["residence_id"]][it["date_intervention"][:4]] += 1
    dem_res_12m = Counter(d["residence_id"] for d in demandes if d["date_creation"] >= "2025-01-01")
    lgt_par_bat = defaultdict(int)
    for b in batiments:
        lgt_par_bat[b["batiment_id"]] = int(b["nb_logements"])

    res_out = []
    for r in residences:
        rid = r["residence_id"]
        eqs = [e for e in eq_out if e["res"] == rid]
        lgts = [l for l in lgt_out if l["res"] == rid]
        bats_alerte_communs = {e["bat"] for e in eqs if e["niveau"] == "alerte" and not e["lgt"]}
        res_out.append({
            "id": rid,
            "lettre": rid.split("-")[1],
            "nom": r["nom"],
            "annee": nombre(r["annee_construction"]),
            "nb_batiments": nombre(r["nb_batiments"]),
            "nb_logements": nombre(r["nb_logements"]),
            "surface": nombre(r["surface_habitable_totale_m2"]),
            "ascenseur": r["ascenseur"],
            "energie": r["energie_chauffage"],
            "chauffage": r["generateur_chauffage"],
            "type_chauffage": r["type_chauffage"],
            "ecs": r["production_ecs"],
            "ventilation": r["ventilation"],
            "dpe_majoritaire": r["etiquette_dpe_majoritaire"],
            "conso_moy": nombre(r["conso_ep_moyenne_kwh_m2_an"]),
            "ges_moy": nombre(r["ges_moyen_kgco2_m2_an"]),
            "eq_suivis": len(eqs),
            "eq_alerte": sum(1 for e in eqs if e["niveau"] == "alerte"),
            "eq_vigilance": sum(1 for e in eqs if e["niveau"] == "vigilance"),
            "lgt_alerte": sum(1 for l in lgts if l["niveau"] == "alerte"),
            "lgt_vigilance": sum(1 for l in lgts if l["niveau"] == "vigilance"),
            "lgt_touches_communs": sum(lgt_par_bat[b] for b in bats_alerte_communs),
            "pannes_par_an": {str(a): arrets[rid].get(str(a), 0) for a in range(2018, 2026)},
            "demandes_12m": dem_res_12m.get(rid, 0),
            "dpe": {c: sum(1 for l in lgts if l["dpe"] == c) for c in "ABCDEFG"},
        })

    ops_out = [{k: nombre(v) if k in ("annee_souhaitee", "cout_estime_ttc", "gain_conso_ep_estime_kwh_m2_an",
                                       "nb_logements_concernes", "rang_actuel_chronologique") else v
                for k, v in o.items()} for o in operations]

    parc = {
        "meta": {
            "date_reference": DATE_REF,
            "horizon_debut": "2026-01-01",
            "horizon_fin": "2026-09-30",
            "genere_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "nb_residences": len(res_out),
            "nb_batiments": len(bat_out),
            "nb_logements": len(lgt_out),
            "nb_equipements_suivis": n,
            "parc_annonce": 6300,
            "seuil_alerte": scores[ordre[n_alerte - 1]]["score"],
            "seuil_vigilance": scores[ordre[n_vigil - 1]]["score"],
            "nb_alerte": n_alerte,
            "nb_vigilance": n_vigil - n_alerte,
        },
        "performance": perf,
        "residences": res_out,
        "batiments": bat_out,
        "logements": lgt_out,
        "equipements": eq_out,
        "operations": ops_out,
    }

    perim_ids = {e["id"] for e in eq_out}
    inter = defaultdict(list)
    for it in interventions:
        if it["equipement_id"] in perim_ids:
            inter[it["equipement_id"]].append([it["date_intervention"], it["type_intervention"], it["symptome"],
                                               it["gravite"], it["resultat"], it["commentaire_technicien"]])
    for v in inter.values():
        v.sort(key=lambda x: x[0])
    journal = {"demandes": dem_lgt, "demandes_communes": dem_com, "interventions": inter}

    os.makedirs(SORTIE, exist_ok=True)
    for nom, obj in (("parc.json", parc), ("journal.json", journal)):
        with open(os.path.join(SORTIE, nom), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        print(f"{nom} : {os.path.getsize(os.path.join(SORTIE, nom)) / 1e6:.2f} Mo")
    print(f"{len(res_out)} résidences · {len(lgt_out)} logements · {n} équipements suivis · "
          f"seuil alerte {parc['meta']['seuil_alerte']} · seuil vigilance {parc['meta']['seuil_vigilance']}")


if __name__ == "__main__":
    main()
