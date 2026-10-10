"""
app/components/carte_techniciens.py — Carte animée des interventions.

La chronologie complète est envoyée une seule fois au navigateur, qui anime la carte
lui-même (deck.gl + MapLibre) : le fond de carte reste fixe, seuls les incidents,
les techniciens et leurs trajets sont mis à jour, sans aller-retour avec Python.

Affichage :
  - sites : icône fixe ;
  - incidents connus non résolus : rouge en attente (même équipe en route), orange en réparation ;
  - techniciens en déplacement : icône casquée + pointillés vers la destination.
Un technicien immobile (sur un poste ou à son site) n'est pas affiché.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit.components.v1 as components

from crise.simulation.carte import chronologie_carte

_GABARIT = Path(__file__).with_name("carte_animee.html")
HAUTEUR = 700

_SVG_TECHNICIEN = """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
<circle cx="32" cy="32" r="29" fill="#005EB8" stroke="#FFFFFF" stroke-width="3"/>
<path d="M15 54 C15 42 23 38 32 38 C41 38 49 42 49 54 Z" fill="#FFFFFF"/>
<circle cx="32" cy="30" r="8" fill="#F5C9A0"/>
<path d="M22 27 C22 17 42 17 42 27 Z" fill="#FFC107"/>
<rect x="19" y="25.5" width="26" height="3.5" rx="1.5" fill="#FFC107"/>
<rect x="30.5" y="17" width="3" height="8" rx="1.5" fill="#E0A800"/>
</svg>"""

_SVG_SITE = """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
<rect x="6" y="6" width="52" height="52" rx="10" fill="#FFFFFF" stroke="#005EB8" stroke-width="4"/>
<path d="M14 32 L32 16 L50 32 V50 H38 V38 H26 V50 H14 Z" fill="#005EB8"/>
</svg>"""


def _icone(svg: str, identifiant: str) -> dict[str, Any]:
    url = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return {"url": url, "width": 64, "height": 64, "anchorY": 32, "id": identifiant}


def _json(valeur: Any) -> str:
    """JSON sûr à insérer dans une balise <script>."""
    return json.dumps(valeur, ensure_ascii=False).replace("</", "<\\/")


def _ms(instant: pd.Timestamp) -> int:
    return int(pd.Timestamp(instant).value // 1_000_000)


def page_carte(
    pannes: pd.DataFrame,
    resultat: dict[str, Any],
    sites: pd.DataFrame | None,
    fenetre: tuple[pd.Timestamp, pd.Timestamp] | None = None,
    propositions: list[dict[str, Any]] | None = None,
) -> str:
    """
    Page HTML autonome de la carte animée.

    Vitesse de lecture : un pas de temps de la simulation par seconde
    (pas de 30 min → la carte avance de 30 min par seconde).

    ``fenetre`` restreint la lecture à un intervalle (pilotage : du pas précédent au pas
    en cours). ``propositions`` (n°, équipe, panne, positions) sont tracées en vert.
    """
    donnees = chronologie_carte(pannes, resultat, sites)
    if fenetre is not None:
        donnees["debut"], donnees["fin"] = _ms(fenetre[0]), _ms(fenetre[1])
    return (
        _GABARIT.read_text(encoding="utf-8")
        .replace("__DONNEES__", _json(donnees))
        .replace("__PROPOSITIONS__", _json(propositions or []))
        .replace("__ICONE_TECH__", _json(_icone(_SVG_TECHNICIEN, "technicien")))
        .replace("__ICONE_SITE__", _json(_icone(_SVG_SITE, "site")))
    )


def render_carte_animee(
    simulation: dict[str, Any],
    resultat: dict[str, Any],
    fenetre: tuple[pd.Timestamp, pd.Timestamp] | None = None,
    propositions: list[dict[str, Any]] | None = None,
) -> None:
    """
    Affiche la carte animée. Tant que la simulation ne change pas, le HTML est identique
    d'une exécution à l'autre : Streamlit garde la carte telle quelle.
    """
    components.html(
        page_carte(simulation["pannes"], resultat, simulation.get("sites"), fenetre, propositions),
        height=HAUTEUR,
    )
