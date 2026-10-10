"""
app/components/comparison.py — Totaux comparatifs + courbes temporelles (Zone 3b).

UX : section ouverte par défaut après simulation — premier résultat visible.
Tableau + métriques par stratégie + 3 courbes d'évolution.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from app.styles.theme import ENEDIS_BLEU, ENEDIS_VERT, COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER


def render_comparison(
    simulation: dict[str, Any],
    strategies: tuple,
    libelles: dict,
    extraire_totaux_fn,
    extraire_series_fn,
) -> None:
    """
    Section comparaison des stratégies dans un expander ouvert par défaut.
    """
    with st.expander("📊 Comparaison des stratégies", expanded=True):
        _render_totaux(simulation, strategies, libelles, extraire_totaux_fn)
        st.markdown("---")
        _render_courbes(simulation, extraire_series_fn)


def _render_totaux(
    simulation: dict[str, Any],
    strategies: tuple,
    libelles: dict,
    extraire_totaux_fn,
) -> None:
    df = extraire_totaux_fn(simulation["resultats_temporels"], simulation["nb_pannes"])

    # Tableau récapitulatif — sans matplotlib (background_gradient supprimé)
    st.markdown("**Tableau récapitulatif — fin de simulation**")
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "Pannes traitées": st.column_config.NumberColumn(
                "✅ Pannes traitées", format="%d"
            ),
            "Pannes non traitées": st.column_config.NumberColumn(
                "🔴 Non traitées", format="%d"
            ),
            "Clients remis (aff.)": st.column_config.NumberColumn(
                "👥 Clients remis", format="%d"
            ),
            "Repos déclenchés": st.column_config.NumberColumn(
                "💤 Repos", format="%d"
            ),
        },
    )

    # Métriques visuelles par stratégie
    cols = st.columns(len(strategies))
    for col, strat in zip(cols, strategies):
        libelle = libelles.get(strat, strat)
        if libelle not in df.index:
            continue
        row = df.loc[libelle]
        nb_pannes = simulation["nb_pannes"]
        traitees = int(row["Pannes traitées"])
        pct = traitees / nb_pannes * 100 if nb_pannes > 0 else 0

        with col:
            # Couleur de la card selon couverture
            variante = "success" if pct >= 80 else ("warning" if pct >= 50 else "danger")
            st.markdown(
                f"""
                <div class="card card-{variante}" style="padding:0.9rem 1rem;">
                    <div style="font-weight:700; font-size:0.8rem; color:#475569;
                                text-transform:uppercase; letter-spacing:0.05em;">
                        {libelle}
                    </div>
                    <div style="font-size:1.5rem; font-weight:800; margin:0.3rem 0;">
                        {pct:.0f}%
                    </div>
                    <div style="font-size:0.82rem; color:#64748B; line-height:1.8;">
                        🟢 {int(row['Pannes traitées'])} traitées<br>
                        🔴 {int(row['Pannes non traitées'])} restantes<br>
                        👥 {int(row['Clients remis (aff.)'])} clients<br>
                        💤 {int(row['Repos déclenchés'])} repos
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Graphique à barres comparatif
    index = [libelles.get(s, s) for s in strategies]
    df_bar = pd.DataFrame(
        {
            "Pannes traitées":     [df.loc[libelles.get(s,s), "Pannes traitées"]     if libelles.get(s,s) in df.index else 0 for s in strategies],
            "Pannes non traitées": [df.loc[libelles.get(s,s), "Pannes non traitées"] if libelles.get(s,s) in df.index else 0 for s in strategies],
        },
        index=index,
    )
    st.bar_chart(df_bar, use_container_width=True, color=[COLOR_SUCCESS, COLOR_DANGER])


def _render_courbes(simulation: dict[str, Any], extraire_series_fn) -> None:
    """Trois courbes temporelles : pannes résolues, équipes en mission, équipes au repos."""
    df_series = extraire_series_fn(simulation["resultats_temporels"])
    if df_series.empty:
        st.info("Aucune donnée temporelle disponible.")
        return

    tab_resolues, tab_mission, tab_repos = st.tabs([
        "📈 Pannes résolues",
        "🚛 Équipes en mission",
        "💤 Équipes au repos (12h/11h)",
    ])

    with tab_resolues:
        st.caption("Progression cumulée des pannes résolues par stratégie.")
        df = df_series.pivot(index="pas", columns="strategie", values="pannes_resolues_cumulees")
        st.line_chart(df, use_container_width=True, height=240)

    with tab_mission:
        st.caption("Nombre d'équipes simultanément en intervention à chaque pas.")
        df = df_series.pivot(index="pas", columns="strategie", values="equipes_en_mission")
        st.line_chart(df, use_container_width=True, height=240)

    with tab_repos:
        st.caption("Équipes en repos obligatoire (règle 12h/11h) — indicateur de sur-sollicitation.")
        df = df_series.pivot(index="pas", columns="strategie", values="equipes_au_repos")
        st.line_chart(df, use_container_width=True, height=240)
