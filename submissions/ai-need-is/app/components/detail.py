"""
app/components/detail.py — Détail des affectations + XAI SHAP (Zone 3d).

UX : accordéon fermé par défaut — section expert.
Deux onglets : résolutions détaillées | explicabilité SHAP.
"""

from __future__ import annotations

from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from app.styles.theme import ENEDIS_BLEU, ENEDIS_VERT


def render_detail(
    simulation: dict[str, Any],
    strategie: str,
    libelles: dict,
) -> None:
    """Section détail dans un expander fermé par défaut."""
    libelle = libelles.get(strategie, strategie)
    with st.expander(f"🔎 Détail & Explicabilité — {libelle}", expanded=False):
        _render_detail_content(simulation, strategie)


def _render_detail_content(simulation: dict[str, Any], strategie: str) -> None:
    res = simulation.get("resultats_temporels", {}).get(strategie, {})
    if not res:
        st.info("Aucune donnée pour cette stratégie.")
        return

    tab_res, tab_aff, tab_shap = st.tabs([
        "📋 Décomposition des coupures",
        "📌 Historique des affectations",
        "🧠 Explicabilité XAI (SHAP)",
    ])

    with tab_res:
        _render_resolutions(res)

    with tab_aff:
        _render_affectations(res)

    with tab_shap:
        _render_shap(res)


def _render_resolutions(res: dict[str, Any]) -> None:
    """Tableau de décomposition : attente + route + dépannage = temps total de coupure."""
    resolutions = res.get("resolutions", [])
    if not resolutions:
        st.info("Aucune résolution enregistrée.")
        return

    st.markdown(
        "Décomposition : $T_{\\text{coupure}} = T_{\\text{attente}} + T_{\\text{route}} + T_{\\text{dépannage}}$"
    )
    df = pd.DataFrame(resolutions)
    cols = [
        c for c in [
            "id_incident", "id_equipe", "nb_clients",
            "temps_attente_h", "temps_route_h", "temps_depannage_h",
            "temps_coupure_total_h", "produit_clients_temps",
        ]
        if c in df.columns
    ]
    st.dataframe(
        df[cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "temps_coupure_total_h": st.column_config.NumberColumn(
                "Coupure totale (h)", format="%.2f h"
            ),
            "nb_clients": st.column_config.NumberColumn("Clients", format="%d 👥"),
        },
    )


def _render_affectations(res: dict[str, Any]) -> None:
    """Tableau de toutes les affectations réalisées au fil des pas."""
    toutes = [
        aff
        for pas in res.get("pas", [])
        for aff in pas.get("affectations", [])
    ]
    if not toutes:
        st.info("Aucune affectation pour cette stratégie.")
        return

    st.caption(f"{len(toutes)} affectation(s) effectuée(s) sur l'ensemble de la simulation.")
    df = pd.DataFrame([{k: v for k, v in a.items() if k not in ("shap_valeurs",)} for a in toutes])
    cols = [
        c for c in [
            "id_incident", "id_poste", "id_equipe", "id_site",
            "nb_clients", "temps_estime_trajet_heures", "explication",
        ]
        if c in df.columns
    ]
    st.dataframe(
        df[cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "nb_clients": st.column_config.NumberColumn("Clients", format="%d 👥"),
            "temps_estime_trajet_heures": st.column_config.NumberColumn(
                "Trajet estimé (h)", format="%.2f h"
            ),
        },
    )


def _render_shap(res: dict[str, Any]) -> None:
    """Section XAI / SHAP — transparence algorithmique (stratégie IA uniquement)."""
    toutes = [
        aff
        for pas in res.get("pas", [])
        for aff in pas.get("affectations", [])
    ]
    aff_shap = [
        a for a in toutes
        if isinstance(a.get("shap_valeurs"), dict) and a["shap_valeurs"]
    ]

    if not aff_shap:
        st.info(
            "Les valeurs SHAP ne sont disponibles que pour la stratégie **🤖 IA Optimale**. "
            "Sélectionnez-la dans la sidebar pour visualiser l'explicabilité algorithmique."
        )
        return

    st.markdown(
        """
        > **Transparence & Auditabilité (AI Act) :** chaque décision ML est décomposée
        > en contributions de Shapley (**TreeSHAP**) — vous voyez *pourquoi* l'algorithme
        > a choisi cette équipe.
        """
    )

    # ── Sélecteur d'affectation ──
    def _label(i: int) -> str:
        a = aff_shap[i]
        sens = "🚨 Sensible" if a.get("poste_sensible") else "Standard"
        return (
            f"#{i + 1} — Incident {a.get('id_incident')} ← Équipe {a.get('id_equipe')} "
            f"| {a.get('nb_clients', 0)} clients | {sens}"
        )

    idx = st.selectbox(
        "Affectation à auditer :",
        options=list(range(len(aff_shap))),
        format_func=_label,
        key="shap_select",
    )
    decision = aff_shap[idx]
    shap_vals = decision["shap_valeurs"]
    score_ia  = decision.get("score_ia", 0.0)
    score_base = decision.get("score_base_ia", 0.0)

    # ── 3 métriques clés ──
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Score ML", f"{score_ia:.1f} pts", delta=f"{score_ia - score_base:+.1f} vs moy.")
    with c2:
        top_pos = max(shap_vals.items(), key=lambda x: x[1])
        st.metric("Facteur accélérateur", top_pos[0], f"+{top_pos[1]:.1f} pts")
    with c3:
        top_neg = min(shap_vals.items(), key=lambda x: x[1])
        st.metric("Facteur frein", top_neg[0], f"{top_neg[1]:.1f} pts")

    # ── Waterfall SHAP ──
    lignes = [
        {
            "Critère": k,
            "Contribution SHAP": v,
            "Effet": "Favorise (+)" if v >= 0 else "Pénalise (−)",
        }
        for k, v in shap_vals.items()
    ]
    df_chart = pd.DataFrame(lignes)

    chart = (
        alt.Chart(df_chart)
        .mark_bar(cornerRadius=4)
        .encode(
            x=alt.X("Contribution SHAP:Q", title="Impact sur le score (pts SHAP)"),
            y=alt.Y("Critère:N", sort="-x", title=""),
            color=alt.Color(
                "Effet:N",
                scale=alt.Scale(
                    domain=["Favorise (+)", "Pénalise (−)"],
                    range=[ENEDIS_VERT, "#E05252"],
                ),
                legend=alt.Legend(title="Effet"),
            ),
            tooltip=["Critère:N", "Contribution SHAP:Q", "Effet:N"],
        )
        .properties(height=220)
    )
    st.altair_chart(chart, use_container_width=True)
    st.caption(f"ℹ️ {decision.get('explication', '')}")

    # ── Importance globale ──
    st.markdown("**📊 Importance globale des critères (|SHAP| moyen sur la crise)**")
    cumul: dict[str, list[float]] = {}
    for a in aff_shap:
        for k, v in a["shap_valeurs"].items():
            cumul.setdefault(k, []).append(abs(v))

    df_glob = pd.DataFrame([
        {"Critère": k, "Importance (|SHAP|)": round(sum(v) / len(v), 2)}
        for k, v in cumul.items()
    ]).sort_values("Importance (|SHAP|)", ascending=False)

    chart_glob = (
        alt.Chart(df_glob)
        .mark_bar(cornerRadius=4, color=ENEDIS_BLEU)
        .encode(
            x=alt.X("Importance (|SHAP|):Q"),
            y=alt.Y("Critère:N", sort="-x"),
            tooltip=["Critère:N", "Importance (|SHAP|):Q"],
        )
        .properties(height=200)
    )
    st.altair_chart(chart_glob, use_container_width=True)
