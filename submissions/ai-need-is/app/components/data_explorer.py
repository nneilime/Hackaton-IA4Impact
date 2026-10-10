"""
app/components/data_explorer.py — Exploration des données source (Zone 4).

UX : section collapsée en bas de page — usage occasionnel uniquement.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd


def render_data_explorer(
    coupures_df: pd.DataFrame,
    agents_df: pd.DataFrame,
    postes_df: pd.DataFrame,
    insee_df: pd.DataFrame,
) -> None:
    """Onglets de données brutes dans un expander fermé par défaut."""
    with st.expander("🔍 Exploration des données source", expanded=False):
        tab_coupures, tab_agents, tab_postes, tab_insee = st.tabs(
            [
                "🚨 Coupures (Crises)",
                "👥 Agents & Sites",
                "📍 Postes Électriques",
                "🏘️ Communes INSEE",
            ]
        )
        with tab_coupures:
            st.caption(f"{len(coupures_df)} incidents chargés.")
            st.dataframe(coupures_df.head(200), use_container_width=True, hide_index=True)
        with tab_agents:
            st.caption(f"{len(agents_df)} agents / sites.")
            st.dataframe(agents_df, use_container_width=True, hide_index=True)
        with tab_postes:
            st.caption(f"{len(postes_df)} postes électriques.")
            st.dataframe(postes_df.head(200), use_container_width=True, hide_index=True)
        with tab_insee:
            st.caption(f"{len(insee_df)} communes.")
            st.dataframe(insee_df.head(200), use_container_width=True, hide_index=True)
