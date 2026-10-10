"""Score de priorisation des opérations du plan d'investissement (multicritère, explicable)."""

import pandas as pd
from batia import config as C

CRITERES = {
    "c_etat": "État technique / risque de panne",
    "c_energie": "Impact énergétique",
    "c_cout": "Coût (sobriété)",
    "c_urgence": "Urgence sociale / réglementaire",
}
POIDS_DEFAUT = {
    "c_etat": 40,
    "c_energie": 30,
    "c_cout": 20,
    "c_urgence": 10,
}  # pondération de départ du rapport phase 2
FAMILLE_PAR_MOT = [
    ("chaufferie", "chaufferie_collective"),
    ("ascenseur", "ascenseur"),
    ("chaudi", "chaudiere_gaz_individuelle"),
    ("pompes à chaleur", "pompe_a_chaleur"),
    ("thermodynamique", "ballon_thermodynamique"),
    ("ballons", "ballon_ecs_electrique"),
    ("convecteurs", "convecteurs_electriques"),
    ("vmc", "caisson_vmc"),
]


def _norm(s: pd.Series) -> pd.Series:
    return (s - s.min()) / (s.max() - s.min() + 1e-9)


def build_scores(
    plan: pd.DataFrame, res: pd.DataFrame, logements: pd.DataFrame, equip: pd.DataFrame
) -> pd.DataFrame:
    p = plan.merge(
        res[["residence_id", "surface_habitable_totale_m2"]], on="residence_id"
    )
    etat = []
    for _, r in p.iterrows():
        e = equip[equip.residence_id == r.residence_id]
        fam = next(
            (f for k, f in FAMILLE_PAR_MOT if k in r.type_operation.lower()), None
        )
        sub = e[e.famille == fam] if fam else e
        etat.append(
            float((sub.risque_pondere >= C.SEUIL_ORANGE).mean()) if len(sub) else 0.0
        )
    p["c_etat"] = _norm(pd.Series(etat, index=p.index))
    p["c_energie"] = _norm(
        p.gain_conso_ep_estime_kwh_m2_an * p.surface_habitable_totale_m2
    )
    p["c_cout"] = 1 - _norm(p.cout_estime_ttc)
    fg = (
        logements.assign(fg=logements.dpe_etiquette_globale.isin(["F", "G"]))
        .groupby("residence_id")
        .fg.mean()
    )
    flag = p.origine_demande.str.contains("DPE|Interdiction|Pannes", case=False).astype(
        float
    )
    p["c_urgence"] = 0.5 * _norm(p.residence_id.map(fg)) + 0.5 * flag
    return p


def apply_weights(p: pd.DataFrame, w: dict, budget: float) -> pd.DataFrame:
    p = p.copy()
    tot = sum(w.values()) or 1
    for k in CRITERES:
        p[f"p_{k}"] = w[k] / tot * p[k]
    p["score"] = p[[f"p_{k}" for k in CRITERES]].sum(axis=1)
    p = p.sort_values("score", ascending=False).reset_index(drop=True)
    p["rang_score"] = p.index + 1
    reste, retenue = budget, []
    for c in p.cout_estime_ttc:
        ok = c <= reste
        retenue.append(ok)
        if ok:
            reste -= c
    p["retenue"] = retenue
    return p
