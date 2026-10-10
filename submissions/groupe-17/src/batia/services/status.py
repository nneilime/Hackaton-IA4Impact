"""Signal rouge / orange / vert par bâtiment et par logement, selon la nature des équipements."""

import pandas as pd
from batia import config as C


def equip_status(risque_pondere: float, famille: str) -> str:
    if risque_pondere >= C.SEUIL_ROUGE:
        return "rouge"
    if risque_pondere >= C.SEUIL_ORANGE:
        return "orange"
    return "vert"


def add_equip_status(a: pd.DataFrame) -> pd.DataFrame:
    a = a.copy()
    a["statut_equip"] = [
        equip_status(r, f) for r, f in zip(a.risque_pondere, a.famille)
    ]
    return a


def _bat_status(g: pd.DataFrame) -> pd.Series:
    n_r = int((g.risque_pondere >= C.SEUIL_ROUGE).sum())
    n_o = int((g.risque_pondere >= C.SEUIL_ORANGE).sum())
    danger_r = int(
        ((g.risque_pondere >= C.SEUIL_ROUGE) & g.famille.isin(C.FAMILLES_DANGER)).sum()
    )
    if danger_r >= 1 or n_r >= C.NB_ROUGE:
        s = "rouge"
        why = (
            f"{danger_r} équipement(s) de sécurité en danger"
            if danger_r
            else f"{n_r} équipements à risque élevé"
        )
    elif n_o >= C.NB_ORANGE or n_r >= 1:
        s, why = "orange", f"{n_o} équipement(s) à surveiller"
    else:
        s, why = "vert", "Aucun signal marquant"
    top = g.sort_values("risque_pondere", ascending=False).iloc[0]
    return pd.Series(
        {
            "statut": s,
            "motif": why,
            "n_rouge": n_r,
            "n_orange": n_o,
            "risque_max": top.risque_pondere,
            "equip_critique": top.libelle_famille,
            "risque_moyen": g.proba.mean(),
            "cout_expose": g.loc[
                g.risque_pondere >= C.SEUIL_ORANGE, "cout_remplacement"
            ].sum(),
        }
    )


def building_status(a: pd.DataFrame) -> pd.DataFrame:
    return (
        a.groupby(["residence_id", "batiment_id"])
        .apply(_bat_status, include_groups=False)
        .reset_index()
    )


def logement_status(a: pd.DataFrame) -> pd.DataFrame:
    a = a[a.logement_id.notna()]

    def f(g):
        m = g.risque_pondere.max()
        return pd.Series(
            {
                "statut": "rouge"
                if m >= C.SEUIL_ROUGE
                else "orange"
                if m >= C.SEUIL_ORANGE
                else "vert",
                "risque_max": m,
                "equip_critique": g.sort_values("risque_pondere")
                .iloc[-1]
                .libelle_famille,
            }
        )

    return (
        a.groupby(["residence_id", "batiment_id", "logement_id"])
        .apply(f, include_groups=False)
        .reset_index()
    )
