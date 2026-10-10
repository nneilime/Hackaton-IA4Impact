"""Module de cartographie pour la salle de crise Enedis (T4.2).

Fournit les fonctions pour générer la carte interactive Folium (Leaflet)
avec sites opérationnels, incidents colorés par état, équipes interpolées
et lignes de trajet, ainsi que les couches pydeck et plotly.
"""
from __future__ import annotations

import folium
import pandas as pd

COULEURS_ETATS = {
    "en attente": "#d62828",       # rouge
    "en intervention": "#f2a541",  # orange
    "rétabli": "#2a9d8f",          # vert
    "à venir": "#a0a0a0",          # gris
}


def creer_carte_folium(
    inc_t: pd.DataFrame,
    eq_t: pd.DataFrame,
    sites: list | None = None,
    centre: tuple[float, float] = (43.3, 1.2),
    zoom_start: int = 8,
) -> folium.Map:
    """T4.2 — Génère une carte Folium interactive à l'instant t.

    Affiche :
    - Sites opérationnels (icône dépôt/base)
    - Incidents colorés par état (rouge, orange, vert, gris) avec taille ∝ nb_clients
      et contour violet si client sensible
    - Équipes à leur position interpolée à l'instant t
    - Lignes reliant chaque équipe en trajet à son incident cible
    """
    m = folium.Map(
        location=list(centre),
        zoom_start=zoom_start,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    # 1. Sites opérationnels (bases de départ)
    if sites:
        for s in sites:
            lat = getattr(s, "lat", None)
            lon = getattr(s, "lon", None)
            commune = getattr(s, "commune", "")
            id_site = getattr(s, "id_site", "")
            nb_eq = getattr(s, "nb_equipes", "")
            if lat is not None and lon is not None:
                folium.Marker(
                    location=[lat, lon],
                    popup=folium.Popup(f"<b>Base : {id_site}</b><br>{commune}<br>{nb_eq} équipes", max_width=250),
                    tooltip=f"Base Enedis : {commune} ({id_site})",
                    icon=folium.Icon(color="darkblue", icon="home", prefix="fa"),
                ).add_to(m)

    # 2. Lignes de trajet équipe -> incident cible
    trajets = eq_t[eq_t["activite"] == "trajet"]
    for _, r in trajets.iterrows():
        lat_cur = r["lat"]
        lon_cur = r["lon"]
        lat_arr = r.get("lat_cible")
        lon_arr = r.get("lon_cible")
        id_eq = r.get("id_equipe", "Équipe")
        id_inc = r.get("id_incident", "")
        if pd.notna(lat_arr) and pd.notna(lon_arr):
            folium.PolyLine(
                locations=[[lat_cur, lon_cur], [lat_arr, lon_arr]],
                color="#1e5ac8",
                weight=3,
                dash_array="6, 6",
                opacity=0.85,
                tooltip=f"Trajet {id_eq} → {id_inc}",
            ).add_to(m)

    # 3. Incidents à l'instant t
    for _, inc in inc_t.iterrows():
        lat = inc["lat"]
        lon = inc["lon"]
        etat = str(inc.get("etat", "en attente"))
        nb_clients = int(inc.get("nb_clients", 10))
        sensible = bool(inc.get("sensible", False))
        commune = str(inc.get("commune", ""))
        id_inc = str(inc.get("id_incident", ""))
        attente_h = inc.get("attente_h", 0.0)

        # Rayon proportionnel aux clients (min 5, max 20)
        radius = max(5, min(20, int(5 + 0.08 * nb_clients)))
        fill_color = COULEURS_ETATS.get(etat, "#d62828")
        fill_opacity = 0.4 if etat == "à venir" else 0.85

        # Contour violet pour poste sensible, sinon couleur d'état
        border_color = "#800080" if sensible else fill_color
        border_weight = 3 if sensible else 1

        badge_sensible = " <span style='color:purple;font-weight:bold;'>[CLIENT SENSIBLE]</span>" if sensible else ""
        popup_html = (
            f"<b>Incident {id_inc}</b>{badge_sensible}<br>"
            f"<b>Commune :</b> {commune}<br>"
            f"<b>État :</b> {etat}<br>"
            f"<b>Clients :</b> {nb_clients}<br>"
            f"<b>Attente :</b> {attente_h} h"
        )

        folium.CircleMarker(
            location=[lat, lon],
            radius=radius,
            color=border_color,
            weight=border_weight,
            fill=True,
            fill_color=fill_color,
            fill_opacity=fill_opacity,
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"{id_inc} ({commune}) : {etat} — {nb_clients} clients" + (" (sensible)" if sensible else ""),
        ).add_to(m)

    # 4. Équipes à leur position interpolée
    for _, eq in eq_t.iterrows():
        lat = eq["lat"]
        lon = eq["lon"]
        id_eq = str(eq.get("id_equipe", ""))
        act = str(eq.get("activite", "disponible"))

        fill_color_eq = "#1e5ac8"
        if act == "chantier":
            fill_color_eq = "#e67e22"
        elif act in ("repos", "retour"):
            fill_color_eq = "#7f8c8d"
        elif act == "hors_service":
            fill_color_eq = "#2c3e50"

        folium.CircleMarker(
            location=[lat, lon],
            radius=7,
            color="#0b3c94",
            weight=2,
            fill=True,
            fill_color=fill_color_eq,
            fill_opacity=0.9,
            popup=folium.Popup(f"<b>Équipe {id_eq}</b><br>Activité : {act}", max_width=200),
            tooltip=f"Équipe {id_eq} ({act})",
        ).add_to(m)

    # Légende HTML responsive
    legende_html = """
    <div style="
        position: fixed;
        bottom: 25px; right: 25px; width: 200px;
        background-color: #ffffff; border: 2px solid #6c757d; z-index: 9999;
        color: #1a1a1a;
        font-size: 11px; padding: 8px; border-radius: 6px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
        line-height: 1.5;
    ">
    <b>Légende de la crise</b><br>
    <i style="background:#d62828;width:9px;height:9px;display:inline-block;border-radius:50%;margin-right:4px;"></i>
    En attente<br>
    <i style="background:#f2a541;width:9px;height:9px;display:inline-block;border-radius:50%;margin-right:4px;"></i>
    Intervention<br>
    <i style="background:#2a9d8f;width:9px;height:9px;display:inline-block;border-radius:50%;margin-right:4px;"></i>
    Rétabli<br>
    <i style="background:#a0a0a0;width:9px;height:9px;display:inline-block;border-radius:50%;margin-right:4px;"></i>
    À venir<br>
    <span style="border:2px solid #800080;border-radius:50%;width:8px;height:8px;
    display:inline-block;margin-right:4px;"></span>
    Sensible<br>
    <span style="color:#1e5ac8;font-weight:bold;margin-right:4px;">●</span>
    Équipe / Trajet<br>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legende_html))

    return m
