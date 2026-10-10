"""Mode Preparation : construire et valider un plan avant la crise."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd
import streamlit as st

from crise.preparation.jointure import (
    construire_points_preparation,
    derouler_equipes,
    preparer_pannes,
)
from crise.preparation.prepositionnement import (
    calculer_barycentre_incidents,
    recommander_prepositionnement,
)
from crise.strategies.allocator import IncidentAllocator


# ── Utilitaires de coloration ────────────────────────────────────────────────

def _couleur_hex_gravite(nb_clients: int, seuil_rouge: int, seuil_orange: int) -> str:
    """Couleur hexadécimale selon la gravité de l'incident."""
    if nb_clients >= seuil_rouge:
        return "#d62728"   # rouge
    if nb_clients >= seuil_orange:
        return "#ff7f0e"   # orange
    return "#2ca02c"       # vert


def _construire_points_carte_colores(
    incidents_previsionnels: pd.DataFrame,
    agents_df: pd.DataFrame,
    barycentre_lat: float,
    barycentre_lon: float,
    afficher_agents: bool,
    afficher_zone: bool,
    seuil_rouge: int,
    seuil_orange: int,
) -> pd.DataFrame:
    """
    Construit un DataFrame compatible st.map avec coloration par gravité.
    Colonnes : latitude, longitude, color, size.
    """
    blocs: list[pd.DataFrame] = []

    # Incidents prévisionnels colorés par gravité
    if afficher_zone and not incidents_previsionnels.empty:
        df = incidents_previsionnels.copy()
        df["latitude"]   = pd.to_numeric(df["latitude"],  errors="coerce")
        df["longitude"]  = pd.to_numeric(df["longitude"], errors="coerce")
        df["nb_clients"] = pd.to_numeric(df.get("nb_clients", 0), errors="coerce").fillna(0).astype(int)
        df = df.dropna(subset=["latitude", "longitude"])
        if not df.empty:
            df["color"] = df["nb_clients"].apply(
                lambda c: _couleur_hex_gravite(int(c), seuil_rouge, seuil_orange)
            )
            df["size"] = 80
            blocs.append(df[["latitude", "longitude", "color", "size"]].copy())

    # Sites d'agents
    if afficher_agents and not agents_df.empty:
        df_a = agents_df.copy()
        df_a["latitude"]  = pd.to_numeric(df_a["latitude"],  errors="coerce")
        df_a["longitude"] = pd.to_numeric(df_a["longitude"], errors="coerce")
        df_a = df_a.dropna(subset=["latitude", "longitude"])
        if not df_a.empty:
            df_a["color"] = "#1f77b4"
            df_a["size"]  = 200
            blocs.append(df_a[["latitude", "longitude", "color", "size"]].copy())

    # Barycentre (point de repli)
    if not (math.isnan(barycentre_lat) or math.isnan(barycentre_lon)):
        blocs.append(pd.DataFrame({
            "latitude":  [barycentre_lat],
            "longitude": [barycentre_lon],
            "color":     ["#9467bd"],
            "size":      [500],
        }))

    if not blocs:
        return pd.DataFrame(columns=["latitude", "longitude", "color", "size"])
    return pd.concat(blocs, ignore_index=True).dropna(subset=["latitude", "longitude"])


# ─────────────────────────────────────────────────────────────────────────────


def render_preparation(
    agents_df: pd.DataFrame,
    postes_df: pd.DataFrame,
    coupures_df: pd.DataFrame,
    params: dict[str, Any],
    libelles: dict[str, str],
) -> None:
    st.header("⚡ Préparer la réponse avant la crise")

    # ── Ligne 1 : sélecteurs + bouton ────────────────────────────────────────
    crises = sorted(coupures_df["numero_crise"].dropna().unique().tolist())
    col_a, col_b, col_c, col_btn = st.columns([3, 1, 2, 2])
    numero    = col_a.selectbox("Scénario de crise", crises, key="prep_crise")
    horizon   = col_b.selectbox("Horizon", [1, 2, 4, 8], index=2, format_func=lambda h: f"{h} h")
    strategie = col_c.selectbox(
        "Méthode", list(libelles), format_func=lambda k: libelles[k], index=2, key="prep_strategie"
    )
    generer = col_btn.button("▶ Générer le plan", type="primary", use_container_width=True)

    if generer:
        with st.spinner("Calcul du plan en cours…"):
            pannes, nb_ecartes, nb_illisible = preparer_pannes(coupures_df, postes_df, numero)
            equipes = derouler_equipes(agents_df)
            t0 = pannes["date_incident"].min()
            previsionnelles = pannes.loc[
                pannes["date_incident"] <= t0 + pd.Timedelta(hours=horizon)
            ].copy()

            allocateur = IncidentAllocator(
                float(params["geo"]["coeff_detour"]),
                float(params["geo"]["vitesse_moyenne_kmh"]),
                params["priorite"],
            )
            decisions = allocateur.affecter_incidents(equipes, previsionnelles, strategie)
            prepositionnements = recommander_prepositionnement(
                equipes, previsionnelles,
                float(params["geo"]["coeff_detour"]),
                float(params["geo"]["vitesse_moyenne_kmh"]),
            )
            barycentre = calculer_barycentre_incidents(previsionnelles)

            st.session_state["brouillon_preparation"] = {
                "numero_crise":           numero,
                "horizon_h":              horizon,
                "strategie":              strategie,
                "pannes":                 pannes,
                "pannes_previsionnelles": previsionnelles,
                "equipes":                equipes,
                "decisions":              decisions,
                "prepositionnements":     prepositionnements,
                "barycentre":             barycentre,
                "nb_ecartes":             nb_ecartes,
                "nb_illisible":           nb_illisible,
                "statut":                 "PROPOSE_PAR_LE_SYSTEME",
            }

    plan = st.session_state.get("brouillon_preparation")
    if not plan:
        st.info("Sélectionnez un scénario et cliquez sur **▶ Générer le plan** pour démarrer.")
        return

    # Garde le plan affiché même si le scénario sélectionné change
    decisions          = plan["decisions"]
    prepositionnements = plan.get("prepositionnements", [])
    lat_b, lon_b       = plan.get("barycentre", (float("nan"), float("nan")))

    # ── Bandeau informatif ───────────────────────────────────────────────────
    st.markdown(
        f'<div class="card card-info" style="margin:0.4rem 0 0.8rem 0">'
        f'<strong>Plan proposé — Crise {plan["numero_crise"]}</strong> · '
        f'Horizon {plan["horizon_h"]} h · Stratégie : {libelles.get(plan["strategie"], plan["strategie"])}'
        f'<br><small>Aucune proposition n\'est engagée tant que le plan n\'a pas été validé.</small></div>',
        unsafe_allow_html=True,
    )

    # ── KPIs ─────────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Incidents anticipés",    len(plan["pannes_previsionnelles"]))
    k2.metric("Affectations proposées", len(decisions))
    k3.metric("Prépositionnements",     len(prepositionnements))
    k4.metric("Équipes disponibles",    len(plan["equipes"]))

    st.divider()

    # ── Seuils de coloration + filtres carte ─────────────────────────────────
    # Les valeurs de session_state sont toujours disponibles même quand
    # l'expander est fermé, car les widgets ont des keys persistantes.
    with st.expander("🗺️ Options de la carte", expanded=False):
        opt1, opt2, opt3, opt4, opt5 = st.columns([2, 2, 1, 1, 1])
        opt1.slider("🔴 Seuil grave (clients ≥)",  1, 5000, 500,  10, key="prep_seuil_rouge")
        opt2.slider("🟠 Seuil modéré (clients ≥)", 1, 5000, 100,  10, key="prep_seuil_orange")
        opt3.checkbox("Incidents",    value=True,  key="prep_map_zone")
        opt4.checkbox("Sites agents", value=True,  key="prep_map_agents")
        opt5.checkbox("Point repli",  value=True,  key="prep_map_repli")

    seuil_rouge  = st.session_state.get("prep_seuil_rouge",  500)
    seuil_orange = st.session_state.get("prep_seuil_orange", 100)
    if seuil_orange >= seuil_rouge:
        seuil_orange = max(1, seuil_rouge - 10)
    afficher_zone   = st.session_state.get("prep_map_zone",   True)
    afficher_agents = st.session_state.get("prep_map_agents", True)
    afficher_repli  = st.session_state.get("prep_map_repli",  True)

    # ── Carte (pleine largeur) ───────────────────────────────────────────────
    st.subheader("Vue territoriale")

    _lat_b_carte = lat_b if afficher_repli else float("nan")
    _lon_b_carte = lon_b if afficher_repli else float("nan")

    points_carte = _construire_points_carte_colores(
        plan["pannes_previsionnelles"],
        agents_df,
        _lat_b_carte,
        _lon_b_carte,
        afficher_agents=afficher_agents,
        afficher_zone=afficher_zone,
        seuil_rouge=seuil_rouge,
        seuil_orange=seuil_orange,
    )

    if points_carte.empty:
        st.info("Aucun point à afficher. Activez les couches dans les options de carte.")
    else:
        st.map(points_carte, latitude="latitude", longitude="longitude",
               color="color", size="size", use_container_width=True)

    # Légende inline
    items_legende = []
    if afficher_zone:
        items_legende += [
            f"🔴 Grave ≥{seuil_rouge}",
            f"🟠 Modéré ≥{seuil_orange}",
            "🟢 Faible",
        ]
    if afficher_agents:
        items_legende.append("🔵 Site agents")
    if afficher_repli and not (math.isnan(lat_b) or math.isnan(lon_b)):
        items_legende.append(f"🟣 Point de repli ({lat_b:.3f}°N, {lon_b:.3f}°E)")
    if items_legende:
        st.caption("  ·  ".join(items_legende))

    st.divider()

    # ── Arbitrage en onglets ──────────────────────────────────────────────────
    tab_aff, tab_prepos, tab_validation = st.tabs([
        f"📋 Affectations ({len(decisions)})",
        f"📍 Prépositionnements ({len(prepositionnements)})",
        "✅ Validation",
    ])

    # ── Onglet 1 : Affectations ───────────────────────────────────────────────
    with tab_aff:
        st.caption(
            "Cochez les affectations à retenir. Les équipes en réserve (onglet Validation) "
            "seront automatiquement exclues."
        )
        if decisions:
            tableau_aff = pd.DataFrame(decisions)
            aff_display = pd.DataFrame({
                "Retenir":    True,
                "Incident":   tableau_aff["id_incident"].astype(str),
                "Équipe":     tableau_aff["id_equipe"].astype(str),
                "Clients":    tableau_aff["nb_clients"].astype(int),
                "Trajet (h)": tableau_aff["temps_estime_trajet_heures"].round(2),
            })
            edite_aff = st.data_editor(
                aff_display,
                hide_index=True,
                use_container_width=True,
                disabled=["Incident", "Équipe", "Clients", "Trajet (h)"],
                key="prep_editor",
            )
        else:
            edite_aff = pd.DataFrame()
            st.warning("Aucune affectation prévisionnelle calculée.")

    # ── Onglet 2 : Prépositionnements ─────────────────────────────────────────
    with tab_prepos:
        if not (math.isnan(lat_b) or math.isnan(lon_b)):
            st.info(
                f"**Point de repli optimal** : {lat_b:.4f}°N, {lon_b:.4f}°E  \n"
                "Barycentre pondéré par le nombre de clients des incidents prévisionnels. "
                "Les équipes les plus proches apparaissent en premier."
            )
        if prepositionnements:
            prepos_df = pd.DataFrame(prepositionnements)
            prepos_display = pd.DataFrame({
                "Retenir":       True,
                "Équipe":        prepos_df["id_equipe"].astype(str),
                "Commune":       prepos_df["commune"].astype(str),
                "Trajet (h)":    prepos_df["temps_deplacement_h"].round(2),
                "Distance (km)": prepos_df["distance_km"].round(1),
            })
            edite_prepos = st.data_editor(
                prepos_display,
                hide_index=True,
                use_container_width=True,
                disabled=["Équipe", "Commune", "Trajet (h)", "Distance (km)"],
                key="prep_prepos_editor",
            )
        else:
            edite_prepos = pd.DataFrame()
            st.info("Aucun prépositionnement calculé (pas d'incidents localisables sur cet horizon).")

    # ── Onglet 3 : Validation ─────────────────────────────────────────────────
    with tab_validation:
        st.caption("Désignez les équipes en réserve, ajoutez un commentaire, puis validez le plan.")

        equipes_ids = plan["equipes"]["id_equipe"].astype(str).tolist()
        reserve = st.multiselect(
            "Équipes à maintenir en réserve",
            equipes_ids,
            help="Ces équipes seront exclues des affectations et des prépositionnements retenus.",
        )
        commentaire = st.text_area(
            "Commentaire du responsable",
            placeholder="Hypothèses, consignes locales, limites du plan…",
        )

        col_val, col_info = st.columns([1, 2])
        with col_val:
            valider = st.button("✅ Valider le plan", type="primary", use_container_width=True)
        with col_info:
            plan_valide = st.session_state.get("plan_preparation")
            if plan_valide and plan_valide.get("numero_crise") == plan["numero_crise"]:
                st.success("Plan validé — disponible pour le mode Jour J.")

        if valider:
            # Récupérer edite_aff / edite_prepos depuis session si onglet inactif
            _edite_aff    = st.session_state.get("prep_editor")
            _edite_prepos = st.session_state.get("prep_prepos_editor")

            # Affectations retenues
            retenues: list[dict] = []
            if decisions:
                # Utiliser la variable locale si disponible (onglet actif), sinon session
                try:
                    _aff_df = edite_aff if not edite_aff.empty else pd.DataFrame()
                except NameError:
                    _aff_df = pd.DataFrame(_edite_aff) if _edite_aff is not None else pd.DataFrame()
                if not _aff_df.empty and "Retenir" in _aff_df.columns:
                    ids_retenus = set(_aff_df.loc[_aff_df["Retenir"], "Incident"].astype(str))
                else:
                    ids_retenus = {str(d["id_incident"]) for d in decisions}
                retenues = [
                    d for d in decisions
                    if str(d["id_incident"]) in ids_retenus
                    and str(d["id_equipe"]) not in reserve
                ]

            # Prépositionnements retenus
            prepos_retenus: list[dict] = []
            if prepositionnements:
                try:
                    _prep_df = edite_prepos if not edite_prepos.empty else pd.DataFrame()
                except NameError:
                    _prep_df = pd.DataFrame(_edite_prepos) if _edite_prepos is not None else pd.DataFrame()
                if not _prep_df.empty and "Retenir" in _prep_df.columns:
                    ids_prepos_ok = set(_prep_df.loc[_prep_df["Retenir"], "Équipe"].astype(str))
                else:
                    ids_prepos_ok = {str(p["id_equipe"]) for p in prepositionnements}
                prepos_retenus = [
                    p for p in prepositionnements
                    if str(p["id_equipe"]) in ids_prepos_ok
                    and str(p["id_equipe"]) not in reserve
                ]

            valide_dict = {
                **plan,
                "decisions":                 retenues,
                "equipes_en_reserve":        reserve,
                "commentaire_humain":        commentaire.strip(),
                "prepositionnements_retenus": prepos_retenus,
                "statut":                    "VALIDE_PAR_L_HUMAIN",
            }
            st.session_state["plan_preparation"] = valide_dict
            st.success(
                f"✅ Plan validé : **{len(retenues)}** affectation(s), "
                f"**{len(prepos_retenus)}** prépositionnement(s), "
                f"**{len(reserve)}** équipe(s) en réserve."
            )
