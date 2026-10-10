"""
app/components/sidebar.py — Panneau de contrôle latéral.

Regroupe tous les widgets de paramétrage de la simulation.
Retourne un dict de paramètres pour découpler la logique de l'affichage.
"""

from __future__ import annotations

import streamlit as st

from app.styles.theme import ENEDIS_VERT


def render_sidebar(
    params: dict,
    crises: list,
    strategies: tuple,
    libelles_strategies: dict,
    data_ok: bool,
) -> dict:
    """
    Affiche la sidebar de contrôle et retourne les paramètres sélectionnés.

    Retourne un dict avec les clés :
        pas_de_temps, nb_pas, coeff_detour, numero_crise,
        strategie, duree_max_h, repos_h, lancer
    """
    with st.sidebar:
        # En-tête de marque
        st.markdown(
            f"""
            <div style="text-align:center; padding: 0.5rem 0 1rem;">
                <span style="font-size:2rem;">⚡</span>
                <div style="font-size:1.05rem; font-weight:700; letter-spacing:-0.01em;">
                    IA_NEED_IS
                </div>
                <div style="font-size:0.72rem; opacity:0.75; margin-top:0.1rem;">
                    Gestion de Crise Électrique
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("**📋 Sélection de la crise**")
        numero_crise = None
        if data_ok and crises:
            numero_crise = st.selectbox(
                "Crise à simuler",
                options=crises,
                label_visibility="collapsed",
            )
        elif not data_ok:
            st.caption("⚠️ Données non chargées")

        st.divider()
        st.markdown("**🎛️ Paramètres de simulation**")

        pas_de_temps = st.select_slider(
            "Pas de temps",
            options=[15, 30, 45, 60],
            value=params["simulation"]["pas_de_temps_min"],
            format_func=lambda v: f"{v} min",
        )

        nb_pas = st.slider(
            "Nombre de pas",
            min_value=4,
            max_value=params["simulation"]["nb_pas_max"],
            value=10,
            help=f"Durée totale simulée : {nb_pas_to_h(10, params['simulation']['pas_de_temps_min'])} avec les valeurs par défaut",
        )

        coeff_detour = st.number_input(
            "Coefficient de détour",
            min_value=1.0,
            max_value=2.0,
            value=float(params["geo"]["coeff_detour"]),
            step=0.05,
            help="Facteur correctif distance à vol d'oiseau → route réelle (1.3 = +30 %)",
        )

        st.divider()
        st.markdown("**📊 Stratégie analysée**")
        strategie = st.selectbox(
            "Stratégie (déroulé et détail)",
            options=list(strategies),
            format_func=lambda cle: libelles_strategies[cle],
            label_visibility="collapsed",
        )

        st.divider()
        st.markdown("**🛡️ Robustesse (Aléas)**")
        scenario = st.selectbox(
            "Scénario d'aléa",
            options=["nominal", "perte_equipes", "saturation_trafic", "double_crise"],
            format_func=lambda s: {
                "nominal": "Conditions normales",
                "perte_equipes": "Perte d'effectifs (50%)",
                "saturation_trafic": "Saturation trafic (-30% vitesse)",
                "double_crise": "Double Crise (Réplique à mi-parcours)",
            }[s],
        )

        alea_declenchement_pct = 50
        if scenario == "perte_equipes":
            alea_declenchement_pct = st.slider(
                "Déclenchement de l'aléa (% temps)",
                min_value=10,
                max_value=90,
                value=50,
                step=5,
                help="À quel moment de la crise l'effectif sera amputé de moitié."
            )

        duree_max_h = float(params["agents"]["duree_max_travail_h"])
        repos_h = float(params["agents"]["duree_min_repos_h"])

        st.divider()
        st.markdown(
            f"""
            <div style="font-size:0.78rem; opacity:0.85; line-height:1.6;">
                ⚠️ <strong>Règle fatigue :</strong><br>
                Max <strong>{int(duree_max_h)} h</strong> d'amplitude<br>
                → <strong>{int(repos_h)} h</strong> de repos au site
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)
        lancer = st.button(
            "▶️ Lancer la simulation",
            type="primary",
            use_container_width=True,
        )

    return {
        "pas_de_temps": pas_de_temps,
        "nb_pas": nb_pas,
        "coeff_detour": coeff_detour,
        "numero_crise": numero_crise,
        "strategie": strategie,
        "duree_max_h": duree_max_h,
        "repos_h": repos_h,
        "lancer": lancer,
        "scenario": scenario,
        "alea_declenchement_pct": alea_declenchement_pct,
    }


def nb_pas_to_h(nb_pas: int, pas_min: int) -> str:
    """Convertit un nombre de pas en durée lisible."""
    total_min = nb_pas * pas_min
    h = total_min // 60
    m = total_min % 60
    return f"{h}h{m:02d}" if m else f"{h}h"
