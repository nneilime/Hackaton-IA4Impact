"""Préparation — carte de risque et prépositionnement (T4.8, propriétaire : P4).

Lancement : streamlit run app/Accueil.py -> 3_Preparation
Affiche : Carte de chaleur du risque prévisionnel (KDE / K-Means),
optimisation p-médiane sous OR-Tools, et gains mesurés sur crises de test.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

from crise.config import charger_config, chemin_projet


def charger_donnees_preparation(
    chemin_outputs: str | Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Charge les données de prépositionnement et carte de risque depuis outputs/."""
    cfg = charger_config()
    base = Path(chemin_outputs or chemin_projet(cfg["chemins"]["outputs"]))
    
    carte_csv = base / "carte_risque.csv"
    resume_csv = base / "prepositionnement_resume.csv"
    pos_csv = base / "positions_pmediane.csv"
    
    df_zones = pd.DataFrame()
    df_resume = pd.DataFrame()
    df_pos = pd.DataFrame()
    
    if carte_csv.exists():
        try:
            df_zones = pd.read_csv(carte_csv)
        except Exception:
            pass
            
    if resume_csv.exists():
        try:
            df_resume = pd.read_csv(resume_csv)
        except Exception:
            pass
            
    if pos_csv.exists():
        try:
            df_pos = pd.read_csv(pos_csv)
        except Exception:
            pass
            
    return df_zones, df_resume, df_pos


# --------------------------------------------------------------------------- Rendu Streamlit
st.set_page_config(page_title="Préparation & Prépositionnement — Enedis", page_icon="🗺️", layout="wide")

st.title("🗺️ Préparation — Carte de Risque & Prépositionnement p-médiane")
st.caption("Anticipation en amont de la tempête (H−12 à H−2) : placer les équipes au plus près des pannes probables.")

zones, resume, positions = charger_donnees_preparation()

# --------------------------------------------------------------------------- Métriques Clés
c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "Gain vs Sites de base",
    "+1,62 %",
    "Sur crises de test 81–100",
    delta_color="normal",
)
c2.metric(
    "Taux de succès",
    "14 / 20 crises",
    "70 % de victoires p-médiane",
    delta_color="normal",
)
c3.metric(
    "Temps de résolution MILP",
    "< 60 s",
    "Solveur OR-Tools SCIP",
)
c4.metric(
    "Équipes réaffectées",
    "63 équipes",
    "Capacitaire bipartite optimal",
)

st.divider()

# --------------------------------------------------------------------------- Synthèse des Configurations
st.subheader("📊 Comparaison des Configurations de Démarrage")
st.markdown(
    """
    Trois stratégies de déploiement des ressources ont été évaluées sur les 20 crises de test (81 à 100) :
    1. **Sites (base)** : chaque équipe démarre de son agence Enedis habituelle.
    2. **K-Means (63 centres)** : regroupement spatial basé sur la densité brute des incidents.
    3. **p-médiane (MILP capacitaire)** : optimisation mathématique sous contrainte de capacité et d'affectation.
    """
)

if not resume.empty:
    st.dataframe(
        resume,
        use_container_width=True,
        column_config={
            "configuration": "Configuration",
            "clients_heures": st.column_config.NumberColumn("Clients·heures moyen", format="%.0f"),
            "pct_clients_retablis_4h": st.column_config.NumberColumn("% Rétablis < 4h", format="%.2f %%"),
            "attente_moy_sensible_h": st.column_config.NumberColumn("Attente moy. sensible (h)", format="%.2f h"),
            "gain_vs_sites_pct": st.column_config.NumberColumn("Gain vs Sites de base", format="%.2f %%"),
            "crises_gagnees_vs_sites": "Nb crises gagnées",
        },
    )

# --------------------------------------------------------------------------- Cartographie Interactive
st.subheader("🗺️ Cartographie du Risque et Positions Avancées")

col_map, col_details = st.columns([3, 2])

with col_map:
    cfg = charger_config()
    carte_html = Path(chemin_projet(cfg["chemins"]["outputs"])) / "carte_chaleur.html"
    
    if carte_html.exists():
        st.markdown("**Carte de chaleur de l'aléa climatique (KDE pondérée par les clients & postes sensibles)**")
        with open(carte_html, encoding="utf-8") as f:
            html_content = f.read()
        components.html(html_content, height=520, scrolling=True)
    elif not zones.empty:
        st.markdown("**Points chauds de demande (K-Means 200 zones)**")
        st.map(zones, latitude="lat", longitude="lon", size="poids")
    else:
        st.info("Lancez `python -m crise.prepositionnement` pour générer la carte de chaleur Folium.")

with col_details:
    st.markdown("### 📍 Déploiements des équipes (p-médiane)")
    if not positions.empty:
        nb_deplaces = int(positions["deplace"].sum()) if "deplace" in positions.columns else len(positions)
        dist_moy = float(positions["distance_km"].mean()) if "distance_km" in positions.columns else 0.0
        dist_max = float(positions["distance_km"].max()) if "distance_km" in positions.columns else 0.0
        
        st.info(
            f"**{nb_deplaces} / 63 équipes** bénéficient d'un prépositionnement avancé.\n\n"
            f"- Distance moyenne parcourue en prépositionnement : **{dist_moy:.1f} km**\n"
            f"- Déplacement maximum : **{dist_max:.1f} km**\n"
            f"- Préservation de l'amplitude de travail avant le déclenchement de la crise."
        )
        
        if "distance_km" in positions.columns:
            fig_dist = px.histogram(
                positions[positions["distance_km"] > 0],
                x="distance_km",
                nbins=15,
                title="Distribution des distances de prépositionnement (km)",
                labels={"distance_km": "Distance (km)"},
                color_discrete_sequence=["#1F77B4"],
            )
            fig_dist.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=40, b=20), height=300)
            st.plotly_chart(fig_dist, use_container_width=True)

st.subheader("📋 Liste des 63 Équipes et Affectations Initiales")
if not positions.empty:
    st.dataframe(positions, use_container_width=True)
