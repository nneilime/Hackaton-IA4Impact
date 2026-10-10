"""Accès aux données (cache Streamlit) et enrichissements communs à toutes les pages."""

import pandas as pd
import streamlit as st
from batia import config as C
from batia.io import read_table
from batia.services import status as S

RECO_FORTES = {"Remplacement à étudier", "Nous recommandons un diagnostic approfondi"}


@st.cache_data(show_spinner=False)
def raw(name: str, **kw) -> pd.DataFrame:
    return pd.read_csv(C.RAW / name, **kw)


@st.cache_data(show_spinner=False)
def table(name: str) -> pd.DataFrame:
    return read_table(name)


@st.cache_data(show_spinner=False)
def equipements() -> pd.DataFrame:
    """Équipements scorés + signal des rapports prestataire (T2-T4 2025) + statut."""
    a = table("alerts_equipements").copy()
    try:
        obs = table("rapports_observations")
    except Exception:
        obs = pd.DataFrame(
            columns=[
                "equipement_id",
                "trimestre",
                "nb_arrets_totaux",
                "recommandation",
                "constat",
            ]
        )
    if len(obs):
        obs = obs.sort_values("trimestre")
        g = (
            obs.groupby("equipement_id")
            .agg(
                n_trimestres=("trimestre", "nunique"),
                max_arrets_rapport=("nb_arrets_totaux", "max"),
                reco_rapport=("recommandation", "last"),
                constat_rapport=("constat", "last"),
            )
            .reset_index()
        )
        a = a.merge(g, on="equipement_id", how="left")
    else:
        (
            a["n_trimestres"],
            a["max_arrets_rapport"],
            a["reco_rapport"],
            a["constat_rapport"],
        ) = 0, 0, None, None
    a["n_trimestres"] = a.n_trimestres.fillna(0).astype(int)
    a["max_arrets_rapport"] = a.max_arrets_rapport.fillna(0).astype(int)
    a["signal_rapport"] = a.n_trimestres > 0
    a["risque_modele"] = a.risque_pondere
    # un signal fort du technicien remonte l'équipement au moins en orange
    fort = a.signal_rapport & (
        a.reco_rapport.isin(RECO_FORTES) | (a.max_arrets_rapport >= 2)
    )
    a.loc[fort & (a.risque_pondere < C.SEUIL_ORANGE), "risque_pondere"] = C.SEUIL_ORANGE
    a["remonte_par_rapport"] = fort & (a.risque_modele < C.SEUIL_ORANGE)
    return S.add_equip_status(a)


@st.cache_data(show_spinner=False)
def batiments() -> pd.DataFrame:
    b = S.building_status(equipements())
    g = table("geo_batiments")[
        [
            "batiment_id",
            "lat",
            "lon",
            "secteur_fictif",
            "nb_niveaux",
            "nb_logements",
            "ascenseur",
        ]
    ]
    return b.merge(g, on="batiment_id", how="left")


@st.cache_data(show_spinner=False)
def logements() -> pd.DataFrame:
    l = S.logement_status(equipements())
    out = table("geo_logements").merge(
        l[["logement_id", "statut", "risque_max", "equip_critique"]],
        on="logement_id",
        how="left",
    )
    out["statut"] = out.statut.fillna("non suivi")
    return out


@st.cache_data(show_spinner=False)
def interventions() -> pd.DataFrame:
    iv = raw("06_interventions.csv", parse_dates=["date_intervention"])
    iv["mois"] = iv.date_intervention.dt.to_period("M").dt.to_timestamp()
    return iv


@st.cache_data(show_spinner=False)
def demandes() -> pd.DataFrame:
    d = raw("05_demandes_locataires.csv", parse_dates=["date_creation"])
    d["mois"] = d.date_creation.dt.to_period("M").dt.to_timestamp()
    return d


@st.cache_data(show_spinner=False)
def metriques() -> dict:
    try:
        return table("metriques_modele").iloc[0].to_dict()
    except Exception:
        return {}
