"""Point d'entrée de l'application IA_NEED_IS."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
import yaml

ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.views.jour_j import render_jour_j
from app.views.preparation import render_preparation
from app.views.rejeu import render_rejeu
from app.styles.theme import inject_css
from crise.loaders.loaders import DataLoader


LIBELLES_STRATEGIES = {
    "distance": "Distance minimale",
    "premier_arrive": "Premier arrivé",
    "score_pondere": "Score pondéré",
    "ia_optimale": "IA avancée (ML + Hongrois)",
}

st.set_page_config(
    page_title="IA_NEED_IS — Décision de crise",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)
inject_css()


@st.cache_data
def charger_params() -> dict:
    with (ROOT_DIR / "config" / "params.yaml").open(encoding="utf-8") as fichier:
        return yaml.safe_load(fichier)


@st.cache_data
def charger_donnees() -> tuple:
    return DataLoader(data_dir=str(ROOT_DIR)).load_all()


st.markdown(
    """
    <div class="app-hero">
        <div><span class="app-logo">⚡</span></div>
        <div>
            <div class="app-title">IA_NEED_IS</div>
            <div class="app-subtitle">Aide à la décision pour la gestion de crise électrique</div>
        </div>
        <div class="human-chip">Humain décisionnaire</div>
    </div>
    """,
    unsafe_allow_html=True,
)

try:
    params = charger_params()
    agents_df, postes_df, coupures_df, insee_df = charger_donnees()
except Exception as erreur:
    st.error(f"Impossible de charger les données : {erreur}")
    st.stop()

mode = st.radio(
    "Mode de travail",
    ["Préparation", "Jour J", "Rejeu"],
    horizontal=True,
    label_visibility="collapsed",
    key="mode_principal",
)
st.divider()

if mode == "Préparation":
    render_preparation(agents_df, postes_df, coupures_df, params, LIBELLES_STRATEGIES)
elif mode == "Jour J":
    render_jour_j(agents_df, postes_df, coupures_df, params, LIBELLES_STRATEGIES)
else:
    render_rejeu(agents_df, postes_df, coupures_df, params, LIBELLES_STRATEGIES)
