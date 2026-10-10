# SPDX-License-Identifier: AGPL-3.0-or-later
from dataclasses import dataclass, field


@dataclass
class Passage:
    """Un fragment de texte source, conservé tel quel (langue d'origine). Unité de preuve."""
    passage_id: str
    source_id: str          # ephy | pmra | epa
    country: str
    region: str
    product: str
    reg_number: str
    holder: str
    status_original: str
    status: str             # autorise | retire | autre (normalisé par code depuis les métadonnées)
    text: str
    source_url: str
    dataset_url: str
    collected_at: str       # ISO date
    kind: str = "usage"     # usage | product
    ai: str = ""            # substance(s) active(s) telle(s) qu'écrite(s) dans la source (produits sœurs)
    gold: dict = field(default_factory=dict)   # valeurs lues dans les colonnes structurées (évaluation)


# ── Contrat d'une source ─────────────────────────────────────────────────────
# Une source = un module de ce dossier (nom sans « _ » initial) qui définit :
#   INFO                     dict : id, name, country_code, country, region, format, lang
#   collect(scope=None)      télécharge les données brutes (via polite_http), retourne un petit compte rendu
#   passages(scope)          retourne la liste des Passage (texte source tel quel, une unité de preuve chacun)
# Le module est découvert automatiquement : aucune autre ligne à modifier dans le code.
# Modèle prêt à copier : _template.py ; guide complet : docs/AJOUTER_UNE_SOURCE.md.

def discover_sources() -> dict:
    """Retourne {id: module} pour toutes les sources valides du dossier."""
    import importlib
    import pkgutil
    found = {}
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        if all(hasattr(module, attribute) for attribute in ("INFO", "collect", "passages")):
            found[module.INFO["id"]] = module
    return dict(sorted(found.items()))
