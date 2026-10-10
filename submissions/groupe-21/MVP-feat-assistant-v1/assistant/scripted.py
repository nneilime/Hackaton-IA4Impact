"""Réponses pré-rédigées aux questions simples (data/reponses_scriptees.json) : servies SANS appel au modèle.

Une question qui contient des montants, des durées ou une demande de prévision ou de comparaison chiffrée est
laissée au modèle, qui dispose des outils de calcul. Les variables {taux:…}, {plafond:…}, {tarif:…}, {usure:…},
{offre:…} et {carte:…} sont remplies depuis la base fictive data/finance.db au moment de la réponse.
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from finance import engine

PATH = Path(__file__).resolve().parents[1] / "data" / "reponses_scriptees.json"
MAX_LENGTH = 160
# Questions à laisser au modèle : chiffres, prévisions, comparaisons ou situation personnelle détaillée.
COMPLEX = re.compile(r"\d|prevision|prevoir|futur|evolu|dans (un|deux|trois|quelques) ans?|l an prochain|"
                     r"compar|pourquoi|vaut.il mieux|que me conseill|conseillez.moi|capacite|simul|calcul|"
                     r"si je |mon projet|ma situation")
_VAR = re.compile(r"\{(taux|plafond|tarif|usure|offre|carte):([^}]+)\}")
STATUS_TITLES = {
    "constat": "Réponse pré-rédigée : information générale (réglementation, fonctionnement)",
    "hypothese": "Réponse pré-rédigée du prototype : chiffres issus de la base fictive, à valider avec BPCE",
    "exemple": "Réponse pré-rédigée : lien ou contenu à brancher",
}


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[’'`]", " ", t)).strip()


@lru_cache(maxsize=1)
def entries() -> list[dict]:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    out = []
    for e in data["reponses"]:
        out.append({**e, "_rx": [re.compile(p) for p in e["declencheurs"]]})
    return out


def _fill(match: re.Match) -> str:
    kind, key = match.group(1), match.group(2).strip()
    try:
        if kind == "taux":
            return engine.pct(engine.value_at(key, engine.ref_month()))
        if kind == "plafond":
            row = engine._q("SELECT plafond FROM produits_epargne WHERE code=?", key)
            return engine.eur(row[0]["plafond"]) if row and row[0]["plafond"] else "aucun plafond"
        if kind == "usure":
            return engine.pct(engine._q("SELECT taux_max_pct FROM taux_usure WHERE categorie=?", key)[0]["taux_max_pct"])
        if kind == "offre":
            return engine.eur(engine._q("SELECT cotisation_mensuelle FROM offres_compte WHERE code=?", key)[0]
                              ["cotisation_mensuelle"], 2)
        if kind == "carte":
            r = engine._q("SELECT * FROM cartes WHERE code=?", key)[0]
            return (f"{engine.eur(r['cotisation_annuelle'])} par an, paiements jusqu'à {engine.eur(r['plafond_paiement_30j'])} "
                    f"sur 30 jours, retraits jusqu'à {engine.eur(r['plafond_retrait_7j'])} sur 7 jours")
        if kind == "tarif":
            for r in engine._q("SELECT * FROM tarifs"):
                if normalize(key) in normalize(r["service"]):
                    if r["prix"] == 0:
                        return "gratuit"
                    price = f"{r['prix']:.2f}".replace(".", ",").removesuffix(",00")
                    remark = r["remarque"].rstrip(".")
                    return f"{price} {r['unite']}" + (f" ({remark[0].lower()}{remark[1:]})" if remark else "")
    except (IndexError, KeyError, engine.FinanceError):
        pass
    return "(valeur indisponible)"


def match(text: str) -> dict | None:
    """Entrée correspondant à une question simple, ou None si la question doit aller au modèle."""
    t = normalize(text)
    if not t or len(t) > MAX_LENGTH or COMPLEX.search(t):
        return None
    best, best_len = None, 0
    for e in entries():
        for rx in e["_rx"]:
            m = rx.search(t)
            if m and len(m.group(0)) > best_len:   # le déclencheur le plus précis l'emporte
                best, best_len = e, len(m.group(0))
    return best


def reply(entry: dict) -> dict:
    """Réponse au format du front : blocs + meta (0 jeton consommé)."""
    blocks = [{"type": "text", "text": _VAR.sub(_fill, entry["reponse"])}]
    if entry.get("suggestions"):
        blocks.append({"type": "chips", "items": [{"label": s, "action": {"type": "ask", "text": s}}
                                                  for s in entry["suggestions"]]})
    status = entry.get("statut", "hypothese")
    blocks.append({"type": "sources", "items": [{"title": STATUS_TITLES[status], "status": status}]})
    return {"blocks": blocks, "meta": {"kind": "script", "intent": f"faq:{entry['id']}", "model": "script",
                                        "usage": {"input_tokens": 0, "output_tokens": 0}}}
