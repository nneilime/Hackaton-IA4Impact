"""
app/components/kpi_panel.py — Panneau KPI + engagement 48h (Zone 1).

Affiche les métriques clés en haut de page selon la structure :
  [ Clients rétablis % ] [ Temps 90 % ] [ Engagement 48h ] [ Score objectif ] [ Repos déclenchés ]
UX : information décisionnelle immédiate, sans scroll.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from app.styles.theme import COLOR_SUCCESS, COLOR_DANGER, COLOR_WARNING, COLOR_INFO, ENEDIS_BLEU


def render_kpi_panel(simulation: dict[str, Any], strategies: tuple, libelles: dict) -> None:
    """
    Ligne de KPIs comparatifs pour toutes les stratégies simulées.

    Structure : une colonne par stratégie + une colonne récapitulatif global.
    """
    from crise.metrics.indicateurs import evaluer_objectif_48h

    resultats = simulation.get("resultats_temporels", {})
    pannes = simulation.get("pannes")
    nb_pannes = simulation.get("nb_pannes", 0)

    total_clients = (
        int(pannes["nb_clients"].sum())
        if pannes is not None and not pannes.empty and "nb_clients" in pannes.columns
        else 0
    )

    st.subheader("📊 KPIs — Comparaison des stratégies")

    cols = st.columns(len(strategies))
    for col, strat in zip(cols, strategies):
        res = resultats.get(strat, {})
        if not res:
            continue
        libelle = libelles.get(strat, strat)
        resolutions = res.get("resolutions", [])
        t0 = res.get("t0")
        indic = res.get("indicateurs", {})
        perf = evaluer_objectif_48h(total_clients, resolutions, instant_t0=t0)

        cl_retablis = sum(r.get("nb_clients", 0) for r in resolutions)
        pct = cl_retablis / total_clients * 100 if total_clients > 0 else 0

        t90 = perf.get("t90_heures")
        t90_txt = f"{t90:.1f} h" if t90 is not None else "> 48 h"
        atteint = perf.get("objectif_atteint", False)
        score_obj = indic.get("score_objectif", 0.0)
        t_moy = indic.get("temps_moyen_coupure_h", 0.0)

        # Couleur de la card selon performance
        if atteint and pct >= 90:
            variante = "success"
        elif pct >= 50:
            variante = "warning"
        else:
            variante = "danger"

        with col:
            _render_strategy_kpi_card(
                libelle=libelle,
                cl_retablis=cl_retablis,
                pct=pct,
                t90_txt=t90_txt,
                atteint=atteint,
                score_obj=score_obj,
                t_moy=t_moy,
                variante=variante,
                strat=strat,
            )


def _render_strategy_kpi_card(
    libelle: str,
    cl_retablis: int,
    pct: float,
    t90_txt: str,
    atteint: bool,
    score_obj: float,
    t_moy: float,
    variante: str,
    strat: str,
) -> None:
    """Affiche la card KPI d'une stratégie."""
    engagement_badge = (
        '<span class="badge badge-success">✅ 48h respecté</span>'
        if atteint
        else '<span class="badge badge-warning">⏳ Non atteint</span>'
    )

    st.markdown(
        f"""
        <div class="card card-{variante}" style="min-height:160px;">
            <div style="font-weight:700; font-size:0.88rem; color:#475569;
                        text-transform:uppercase; letter-spacing:0.05em; margin-bottom:0.6rem;">
                {libelle}
            </div>
            <div style="font-size:1.75rem; font-weight:800; line-height:1.1; color:#1A202C;">
                {cl_retablis:,}
                <span style="font-size:1rem; font-weight:600; color:#64748B;">clients</span>
            </div>
            <div style="font-size:0.9rem; font-weight:600; color:#475569; margin:0.25rem 0;">
                {pct:.1f} % rétablis
            </div>
            <div style="margin: 0.4rem 0 0.3rem;">
                {engagement_badge}
            </div>
            <div style="font-size:0.8rem; color:#64748B; line-height:1.7;">
                ⏱ T90 : <strong>{t90_txt}</strong><br>
                📉 Coupure moy. : <strong>{t_moy:.2f} h</strong><br>
                🎯 Score obj. : <strong>{score_obj:.1f}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
