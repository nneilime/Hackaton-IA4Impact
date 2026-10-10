import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
import streamlit as st
from batia.ui.theme import apply_theme

st.set_page_config(page_title="BâtIA · Action Logement", page_icon="🏢", layout="wide")
apply_theme()
if st.sidebar.button("🔄 Recharger les données"):
    st.cache_data.clear()
    st.rerun()

pages = [
    st.Page("views/1_Vue_ensemble.py", title="Vue d'ensemble", icon="📊", default=True),
    st.Page("views/2_Carte.py", title="Carte du patrimoine", icon="🗺️"),
    st.Page("views/3_Alertes.py", title="Alertes équipements", icon="🚨"),
    st.Page("views/4_Priorisation.py", title="Priorisation rénovations", icon="🏗️"),
    st.Page("views/5_Rapports.py", title="Rapports & locataires", icon="📑"),
    st.Page("views/6_Decision.py", title="Décision proposée", icon="✅"),
]
st.navigation(pages).run()
