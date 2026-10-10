# SPDX-License-Identifier: AGPL-3.0-or-later
"""Crée le squelette d'une nouvelle source à partir du modèle `sources/_template.py`."""
from __future__ import annotations

import re

from . import config

SOURCES_FOLDER = config.ROOT / "veille_reglementaire" / "sources"


def create_source(source_id: str, name: str, country_code: str, country: str, region: str,
                  data_format: str = "CSV", language: str = "EN") -> str:
    """Écrit sources/<id>.py et retourne son chemin. Refuse un identifiant invalide ou déjà pris."""
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,30}", source_id):
        raise ValueError("identifiant : minuscules, chiffres et _ (2 à 31 caractères), commençant par une lettre")
    target = SOURCES_FOLDER / f"{source_id}.py"
    if target.exists():
        raise FileExistsError(f"la source « {source_id} » existe déjà : {target}")
    text = (SOURCES_FOLDER / "_template.py").read_text(encoding="utf-8")
    for placeholder, value in {"__ID__": source_id, "__NAME__": name, "__COUNTRY_CODE__": country_code.upper(),
                               "__COUNTRY__": country, "__REGION__": region, "__FORMAT__": data_format,
                               "__LANG__": language.upper()}.items():
        text = text.replace(placeholder, value)
    target.write_text(text, encoding="utf-8")
    return str(target.relative_to(config.ROOT))


NEXT_STEPS = """Prochaines étapes :
  1. Éditer {path} : DATASET_URL, puis passages() (voir les TODO).
  2. config/scope.json : ajouter la clé "{source_id}": ["NOM DU PRODUIT"] aux produits concernés.
  3. ./veille collect --only {source_id}   puis   ./veille index --only {source_id}
  4. ./veille extract --source {source_id} --per-product 3      (essai rapide)
  5. ./veille review                                           (documents en erreur à relire)
  6. ./veille eval                                             (si la source a des colonnes structurées : gold)
Guide complet : docs/AJOUTER_UNE_SOURCE.md"""
