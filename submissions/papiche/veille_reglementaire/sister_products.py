# SPDX-License-Identifier: AGPL-3.0-or-later
"""Détection de produits sœurs : mêmes souche et substance active sous des noms commerciaux différents.

Score DÉTERMINISTE et lisible (somme pondérée de critères observables) ; la justification énumère les critères
vérifiés. Une correspondance reste toujours « a_confirmer » : seule l'équipe Regulatory peut la valider.
"""
from __future__ import annotations
import json, re
from itertools import combinations
from . import config
from .eppo_codes import fold
from .models import SisterHypothesis

W = {"meme_souche": 0.5, "meme_espece": 0.2, "meme_titulaire": 0.1, "meme_formulation": 0.1,
     "meme_famille_marque": 0.05, "noms_proches": 0.05}
STRAIN = re.compile(r"(?:souche|strain|stam)\s*:?\s*([A-Za-z0-9][A-Za-z0-9/\-. ]{1,18}?)(?=[\s(),;]|$)", re.I)
FORM = re.compile(r"\b(WG|WP|OD|GR|SC|EC|WS|SL|DP)\b")


def canon(name: str) -> str:
    """'BOTANIGARD 22WP' == 'Botanigard 22 WP' == 'PRESTOP (WG)' == 'PRESTOP WG'."""
    return re.sub(r"[^a-z0-9]", "", fold(name))


def _syn() -> dict:
    d = json.loads((config.CONFIG / "taxon_synonyms.json").read_text())
    return {k: v for k, v in d.items() if not k.startswith("_")}


def profile(product: str, ai: str, holder: str) -> dict:
    a = fold(ai)
    species = None
    m = re.match(r"([a-z]+ [a-z]+)", a)
    if m:
        species = m.group(1)
        if species.split(" ")[1] in ("souche", "strain", "stam", "k61"):     # espèce non nommée : genre seul
            species = species.split(" ")[0] + " sp"
    species = _syn().get(species, species)
    strain = None
    for m in STRAIN.finditer(ai or ""):
        strain = fold(m.group(1)).replace(" ", "")
        if strain:
            break
    form = FORM.search(product.upper())
    return {"species": species, "strain": strain, "formulation": form.group(1) if form else None,
            "holder": fold(holder), "brand": fold(product).split(" ")[0]}


def detect(passages_meta: list[dict], threshold: float = 0.55) -> list[dict]:
    """passages_meta : [{product, country, ai, holder}] dédoublonnés par (product, country)."""
    uniq = {}
    for p in passages_meta:
        uniq.setdefault((p["product"], p["country"]), p)
    profs = {k: profile(v["product"], v["ai"], v["holder"]) for k, v in uniq.items()}
    out = []
    for (ka, pa), (kb, pb) in combinations(profs.items(), 2):
        if canon(ka[0]) == canon(kb[0]):
            continue                               # même produit (orthographe près) : pas une hypothèse
        f = {
            "meme_souche": bool(pa["strain"] and pa["strain"] == pb["strain"]),
            "meme_espece": bool(pa["species"] and pa["species"] == pb["species"]),
            "meme_titulaire": bool(pa["holder"] and pa["holder"].split(" ")[0] == pb["holder"].split(" ")[0]),
            "meme_formulation": bool(pa["formulation"] and pa["formulation"] == pb["formulation"]),
            "meme_famille_marque": pa["brand"] == pb["brand"],
            "noms_proches": fold(ka[0]) in fold(kb[0]) or fold(kb[0]) in fold(ka[0]),
        }
        if not f["meme_espece"]:
            continue
        score = round(sum(W[k] for k, v in f.items() if v), 2)
        if score < threshold:
            continue
        why = [k.replace("_", " ") for k, v in f.items() if v]
        out.append(SisterHypothesis(
            product_a=ka[0], country_a=ka[1], product_b=kb[0], country_b=kb[1], confidence=score, features=f,
            justification=(f"{ka[0]} ({ka[1]}) et {kb[0]} ({kb[1]}) : critères vérifiés dans les sources — "
                           + ", ".join(why) + f". Souche lue : {pa['strain'] or 'n/a'} / {pb['strain'] or 'n/a'}. "
                           "Hypothèse à confirmer par Regulatory (composition et formulation exactes non comparées).")
        ).model_dump())
    return sorted(out, key=lambda x: -x["confidence"])
