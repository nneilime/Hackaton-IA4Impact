"""
app/components/status_bar.py — Barre de statut persistante (Zone 0).

Affiche en haut de page le nom de la crise, le statut global,
les compteurs de pannes et l'état du pool d'équipes.
UX : visible sans scroll, premier point de lecture du manager.
"""

from __future__ import annotations

from typing import Any

import streamlit as st


def render_status_bar(simulation: dict[str, Any], strategie: str, libelles: dict) -> None:
    """
    Barre de statut collée en haut du contenu principal.

    Affiche : crise | statut global | pannes (attente / cours / résolues) | équipes
    """
    suivi = _dernier_etat(simulation, strategie)
    numero = simulation.get("numero_crise", "—")
    nb_pannes = simulation.get("nb_pannes", 0)
    nb_ecartes = simulation.get("nb_ecartes", 0)
    nb_illisible = simulation.get("nb_illisible", 0)

    en_attente = len(suivi["en_attente"]) if suivi else nb_pannes
    en_cours   = len(suivi["en_cours"])   if suivi else 0
    resolues   = len(suivi["resolues"])   if suivi else 0

    eq_libres   = suivi.get("equipes_libres",   "—") if suivi else "—"
    eq_mission  = suivi.get("equipes_en_mission","—") if suivi else "—"
    eq_repos    = suivi.get("equipes_au_repos",  "—") if suivi else "—"

    pct = f"{resolues / nb_pannes * 100:.0f} %" if nb_pannes > 0 else "—"

    # Statut global
    if resolues == nb_pannes and nb_pannes > 0:
        statut_html = '<span class="status-pill resolue">✅ CRISE TERMINÉE</span>'
    elif en_cours > 0 or resolues > 0:
        statut_html = '<span class="status-pill en-cours">🟠 EN COURS</span>'
    else:
        statut_html = '<span class="status-pill en-attente">🔴 EN ATTENTE</span>'

    # Stratégie sélectionnée
    libelle_strat = libelles.get(strategie, strategie)

    html = f"""
    <div class="status-bar">
        <span style="font-weight:700; font-size:0.95rem;">
            ⚡ Crise <strong>{numero}</strong>
        </span>
        {statut_html}
        <span class="status-pill en-attente">🔴 {en_attente} en attente</span>
        <span class="status-pill en-cours">🟠 {en_cours} en cours</span>
        <span class="status-pill resolue">🟢 {resolues} résolues ({pct})</span>
        <span class="status-pill equipes">
            🔵 Équipes : {eq_libres} libres · {eq_mission} en mission · {eq_repos} au repos
        </span>
        <span style="margin-left:auto; font-size:0.78rem; color:#64748B;">
            Stratégie : <strong>{libelle_strat}</strong>
        </span>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

    # Avertissements qualité données (discrets mais visibles)
    if nb_ecartes:
        st.caption(f"ℹ️ {nb_ecartes} panne(s) écartée(s) : poste introuvable ou coordonnées manquantes.")
    if nb_illisible:
        st.caption(f"ℹ️ {nb_illisible} durée(s) illisible(s), comptées comme 0 h.")


def _dernier_etat(simulation: dict[str, Any], strategie: str) -> dict[str, Any] | None:
    """Retourne le dernier état du suivi pour la stratégie donnée, ou None."""
    from crise.simulation.moteur import suivre_resolutions
    res = simulation.get("resultats_temporels", {}).get(strategie, {})
    pannes = simulation.get("pannes")
    if not res or pannes is None:
        return None
    suivi = suivre_resolutions(res, pannes)
    return suivi[-1] if suivi else None
