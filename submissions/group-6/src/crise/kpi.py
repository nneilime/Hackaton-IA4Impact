"""Indicateurs à partir d'un SimResult : Σ N·T, Gini, saturation, etc. (plan §10).

Tâche(s) : T3.1, T3.2 — propriétaire : P3 (version express écrite par P1 pour débloquer le banc d'essai).

    from crise.kpi import calculer_kpi, courbe_clients_coupes
    k = calculer_kpi(res)          # dict prêt pour un DataFrame / st.metric
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from crise.models import SimResult


def gini_pondere(valeurs, poids=None) -> float:
    """Coefficient de Gini pondéré (0 = égalité parfaite, 1 = inégalité maximale)."""
    x = np.asarray(valeurs, dtype=float)
    w = np.ones_like(x) if poids is None else np.asarray(poids, dtype=float)
    garde = ~np.isnan(x) & (w > 0)
    x, w = x[garde], w[garde]
    if len(x) == 0 or x.sum() == 0:
        return 0.0
    ordre = np.argsort(x)
    x, w = x[ordre], w[ordre]
    p = w / w.sum()                                   # part de population
    lorenz = np.cumsum(x * w) / np.sum(x * w)         # part cumulée de la « grandeur »
    lorenz_prec = np.concatenate([[0.0], lorenz[:-1]])
    return float(1 - np.sum(p * (lorenz + lorenz_prec)))


def courbe_clients_coupes(res: SimResult) -> pd.DataFrame:
    """t (heures) → clients coupés, pour la courbe phare du pitch."""
    s = res.serie[["t", "clients_coupes"]].copy()
    s["t_h"] = s["t"] / 60
    return s


def depassements_amplitude(res: SimResult) -> int:
    """Nombre d'activités de travail qui finissent après la fin de l'amplitude (doit valoir 0 en nominal)."""
    amplitude = int(res.metadata.get("params", {}).get("amplitude_max_min", 720))
    act = res.activites.sort_values(["id_equipe", "t_debut"])
    n = 0
    for _, g in act.groupby("id_equipe"):
        debut_service = 0
        for r in g.itertuples():
            if r.type in ("repos", "hors_service"):
                debut_service = r.t_fin
            elif r.type in ("trajet", "chantier") and r.t_fin - debut_service > amplitude:
                n += 1
    return n


def calculer_kpi(res: SimResult) -> dict:
    inc = res.incidents.copy()
    resolus = inc.dropna(subset=["t_resolution"])
    T = (resolus["t_resolution"] - resolus["t_apparition"]) / 60          # heures de coupure par incident
    N = resolus["nb_clients"]
    attente_h = (inc["t_affectation"] - inc["t_apparition"]) / 60
    sens = inc["sensible"].astype(bool)

    def pct_retablis(h):
        return float(100 * N[T <= h].sum() / N.sum()) if N.sum() else 0.0

    # Gini des temps de coupure moyens par commune (pondéré par les clients)
    if "commune" in resolus and resolus["commune"].notna().any():
        par_commune = resolus.assign(T=T, NT=T * N).groupby("commune").agg(NT=("NT", "sum"), N=("nb_clients", "sum"))
        gini = gini_pondere(par_commune["NT"] / par_commune["N"], par_commune["N"])
    else:
        gini = float("nan")

    serie = res.serie
    sature = (serie["equipes_disponibles"] == 0) & (serie["incidents_attente"] > 0)
    act = res.activites
    temps_chantier = (act.loc[act["type"] == "chantier", "t_fin"] - act.loc[act["type"] == "chantier", "t_debut"]).sum()
    temps_trajet = (act.loc[act["type"] == "trajet", "t_fin"] - act.loc[act["type"] == "trajet", "t_debut"]).sum()

    return {
        "crise": res.metadata.get("crise"),
        "strategie": res.metadata.get("strategie"),
        "seed": res.metadata.get("seed"),
        "monte_carlo": res.metadata.get("monte_carlo"),
        "clients_heures": float((T * N).sum()),
        "clients_heures_sensibles": float((T * N)[resolus["sensible"].astype(bool)].sum()),
        "pct_clients_retablis_2h": pct_retablis(2),
        "pct_clients_retablis_4h": pct_retablis(4),
        "pct_clients_retablis_8h": pct_retablis(8),
        "attente_moy_h": float(attente_h.mean()),
        "attente_max_h": float(attente_h.max()),
        "attente_max_sensible_h": float(attente_h[sens].max()) if sens.any() else 0.0,
        "attente_moy_sensible_h": float(attente_h[sens].mean()) if sens.any() else 0.0,
        "gini_communes": gini,
        "saturation_pct": float(100 * sature.mean()),
        "pic_clients_coupes": int(serie["clients_coupes"].max()),
        "fin_crise_h": float(res.metadata.get("t_fin_min", serie["t"].max()) / 60),
        "part_trajet_pct": float(100 * temps_trajet / (temps_trajet + temps_chantier)) if temps_chantier else 0.0,
        "depassements_amplitude": depassements_amplitude(res),
        "non_resolus": int(res.metadata.get("non_resolus", 0)),
        "nb_incidents": int(len(inc)),
    }


def separer_apprentissage_test(crises: list[str], n_apprentissage: int = 80) -> tuple[list[str], list[str]]:
    """Crises 1..80 = apprentissage (réglage α, β, prépositionnement), 81..100 = test (§5.6)."""
    crises = sorted(crises)
    return crises[:n_apprentissage], crises[n_apprentissage:]
