"""
app/components/timeline.py — Déroulé de la crise (Zone 3a).

  - Carte animée : jouée dans le navigateur (fond fixe, seules les icônes bougent),
    avec ses propres compteurs, horloge, lecture/pause et frise temporelle.
  - Détail d'un pas : courbes, état des équipes et journal, choisis avec un curseur.
UX : accordéon fermé par défaut, ouvert après « Lancer la simulation ».
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from app.components.carte_techniciens import render_carte_animee
from app.styles.theme import ENEDIS_VERT, COLOR_DANGER, COLOR_WARNING, COLOR_SUCCESS


def render_timeline(
    simulation: dict[str, Any],
    strategie: str,
    libelles: dict,
    animer: bool,
) -> None:
    """
    Section déroulé dans un expander : carte animée, puis détail du pas choisi au curseur.

    ``animer`` ouvre l'accordéon au lancement. La carte avance d'un pas de temps par seconde.
    """
    from crise.simulation.moteur import suivre_resolutions

    libelle = libelles.get(strategie, strategie)
    res = simulation.get("resultats_temporels", {}).get(strategie, {})
    pannes = simulation.get("pannes")
    if not res or pannes is None:
        return

    suivi = suivre_resolutions(res, pannes)
    if not suivi:
        return

    # L'accordéon reste ouvert après un lancement, même quand on bouge le curseur ensuite.
    if animer:
        st.session_state["deroule_ouvert"] = True

    with st.expander(
        f"⏱️ Déroulé en temps réel — {libelle} ({len(suivi)} pas)",
        expanded=st.session_state.get("deroule_ouvert", False),
    ):
        render_carte_animee(simulation, res)

        st.markdown("##### 🔍 Détail d'un pas")
        if animer or not 1 <= st.session_state.get("pas_affiche", 0) <= len(suivi):
            st.session_state["pas_affiche"] = len(suivi)
        indice = (
            st.slider(
                "Pas affiché",
                min_value=1,
                max_value=len(suivi),
                key="pas_affiche",
                help="Courbes, équipes et journal à ce pas. La carte a sa propre frise temporelle.",
            )
            - 1
        )
        _render_pas(suivi, indice, res)


def _render_pas(
    suivi: list[dict[str, Any]],
    indice: int,
    res: dict[str, Any],
) -> None:
    """Détail d'un pas : horloge, état des équipes, courbes jusqu'à ce pas, journal."""
    etat = suivi[indice]
    pas = res["pas"][indice]

    st.markdown(
        f"**🕒 {etat['instant']:%d/%m/%Y %H:%M}** "
        f"<span style='color:#64748B; font-size:0.85rem;'>— pas {indice + 1} / {len(suivi)}</span>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div style="display:flex; gap:0.75rem; margin: 0.25rem 0 0.75rem; flex-wrap:wrap;">
            <span class="badge badge-info">🔵 {etat['equipes_libres']} libres</span>
            <span class="badge badge-warning">🟠 {etat['equipes_en_mission']} en mission</span>
            <span class="badge badge-neutral">🚐 {etat.get('equipes_en_retour', 0)} en retour au site</span>
            <span class="badge badge-neutral">💤 {etat['equipes_au_repos']} au repos</span>
            {f'<span class="badge badge-error" style="background:#FEE2E2;color:#DC2626;">❌ {etat.get("equipes_indisponibles", 0)} indispo</span>' if etat.get("equipes_indisponibles", 0) > 0 else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_pannes, col_clients = st.columns(2)
    historique = pd.DataFrame(
        {
            "En attente": [len(e["en_attente"]) for e in suivi[: indice + 1]],
            "En cours":   [len(e["en_cours"])   for e in suivi[: indice + 1]],
            "Résolues":   [len(e["resolues"])   for e in suivi[: indice + 1]],
        },
        index=[e["instant"] for e in suivi[: indice + 1]],
    )
    with col_pannes:
        st.line_chart(
            historique,
            color=[COLOR_DANGER, COLOR_WARNING, COLOR_SUCCESS],
            height=180,
        )
    with col_clients:
        st.area_chart(
            pd.DataFrame(
                {"Clients rétablis": [e["clients_retablis"] for e in suivi[: indice + 1]]},
                index=historique.index,
            ),
            color=ENEDIS_VERT,
            height=180,
        )

    # ── Journal des événements ──
    affectations = pas.get("affectations", [])
    terminees    = pas.get("terminees",    [])
    journal = (
        [f"✅ Panne <b>{i}</b> résolue" for i in terminees]
        + [
            f"🚚 Équipe <b>{a['id_equipe']}</b> → panne <b>{a['id_incident']}</b> "
            f"({a.get('nb_clients',0)} clients)"
            for a in affectations
        ]
    )
    timestamp_label = f"{etat['instant']:%d/%m à %H:%M}"
    st.markdown(f"<div style='color: black;'><b>📋 Journal — {timestamp_label} ({len(journal)} évènement(s))</b></div>", unsafe_allow_html=True)
    if journal:
        journal_html = "<br>".join(f"• {ligne}" for ligne in journal)
        st.markdown(f"<div style='color: black;'>{journal_html}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div style='color: black; opacity: 0.7; font-size: 0.9em;'>Aucun évènement à ce pas.</div>", unsafe_allow_html=True)
