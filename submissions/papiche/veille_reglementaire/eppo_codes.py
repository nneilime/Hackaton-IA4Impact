# SPDX-License-Identifier: AGPL-3.0-or-later
"""Normalisation EPPO : le LLM propose, la table confirme. Code inconnu -> null, jamais deviné.

config/eppo_seed.csv est une AMORCE de codes vérifiés à la main ; LPC la remplace par son jeu EPPO officiel
(même format : code,kind,names). La valeur originale reste toujours conservée à côté du code.
"""
from __future__ import annotations
import csv, difflib, functools, json, re, unicodedata
from . import config, llm
from .models import EppoChoice

URL_FICHE_EPPO = "https://gd.eppo.int/taxon/{code}"
URL_RECHERCHE_EPPO = "https://gd.eppo.int/search?k={nom}"
FICHIERS_CODES = ("eppo_seed.csv", "eppo_officiel.csv")   # le second, fourni par LPC, complète l'amorce
SUFFIXES_SANS_SENS = re.compile(r"\b(spp?|ssp|var|cv|l|sensu lato)\b\.?")


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    return re.sub(r"\s+", " ", s).strip()


def lien_eppo(code: str) -> str:
    """Fiche officielle du code sur gd.eppo.int : chaque association reste vérifiable en un clic."""
    return URL_FICHE_EPPO.format(code=code)


def nettoyer_nom(nom: str) -> str:
    """Retire ce qui n'identifie pas l'espèce : parenthèses, « spp. », « var. », auteurs en fin de nom."""
    nom = re.sub(r"\([^)]*\)", " ", fold(nom))
    nom = SUFFIXES_SANS_SENS.sub(" ", nom)
    return re.sub(r"\s+", " ", nom).strip(" .-")


def singulier(nom: str) -> str:
    """Pluriels simples : « vignes » -> « vigne », « choux » inchangé grâce à la table des noms."""
    return " ".join(mot[:-1] if len(mot) > 4 and mot.endswith("s") else mot for mot in nom.split())


@functools.lru_cache(maxsize=1)
def table() -> dict[str, list[tuple[str, str]]]:
    """kind -> [(nom_normalisé, code)]"""
    t: dict[str, list[tuple[str, str]]] = {"crop": [], "pest": []}
    for fichier in FICHIERS_CODES:
        chemin = config.CONFIG / fichier
        if not chemin.exists():
            continue
        with open(chemin, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                for n in r["names"].split("|"):
                    t[r["kind"]].append((fold(n), r["code"]))
    return t


def _parts(original: str) -> list[str]:
    return [p.strip() for p in re.split(r"\s+-\s+|,|;|/|\s+et\s+|\s+and\s+", original) if p.strip()]


def _note(recherche: str, nom_table: str) -> float:
    """1.0 = même nom (après nettoyage et singulier) ; 0.9 = mêmes mots dans un autre ordre ; sinon ressemblance."""
    if nom_table == recherche or singulier(nom_table) == singulier(recherche):
        return 1.0
    if set(nom_table.split()) == set(recherche.split()):
        return 0.9
    note = difflib.SequenceMatcher(None, recherche, nom_table).ratio()
    if len(nom_table) > 3 and (nom_table in recherche or recherche in nom_table):
        note = max(note, 0.8)
    return note


def candidates(name: str, kind: str, n: int = 5) -> list[tuple[str, str, float]]:
    f = nettoyer_nom(name)
    scored = {}
    for nm, code in table()[kind]:
        r = _note(f, nettoyer_nom(nm))
        if code not in scored or r > scored[code][1]:
            scored[code] = (nm, r)
    top = sorted(((c, nm, r) for c, (nm, r) in scored.items()), key=lambda x: -x[2])[:n]
    return [(c, nm, r) for c, nm, r in top if r >= 0.6]


def normalize(original: str | None, kind: str) -> dict:
    """Retourne {"eppo": "A;B"|None, "method": ..., "steps": [...]} (steps = trace pédagogique)."""
    if not original:
        return {"eppo": None, "method": "absent", "steps": []}
    codes, steps = [], []
    for part in _parts(original):
        cands = candidates(part, kind)
        exact = [c for c, nm, r in cands if r == 1.0]
        if exact:
            codes.append(exact[0]); steps.append({"part": part, "method": "table", "code": exact[0], "candidates": [c for c, *_ in cands]})
            continue
        if not cands:
            steps.append({"part": part, "method": "aucun_candidat", "code": None, "candidates": []})
            return {"eppo": None, "method": "non_confirme", "steps": steps}
        listing = "\n".join(f"- {c} ({nm})" for c, nm, _ in cands)
        res = llm.chat_json(config.PROMPTS.joinpath("eppo.system.md").read_text(),
                            f"Nom à normaliser : « {part} »\nCandidats :\n{listing}", num_predict=60)
        code = None
        try:
            code = EppoChoice.model_validate(json.loads(res["text"] or "{}")).eppo
        except Exception:
            pass
        ok = code in {c for c, *_ in cands}      # le LLM ne peut choisir que dans la liste
        steps.append({"part": part, "method": "llm_parmi_candidats", "code": code if ok else None,
                      "candidates": [c for c, *_ in cands], "llm_raw": res["text"]})
        if not ok or code is None:
            return {"eppo": None, "method": "non_confirme", "steps": steps}
        codes.append(code)
    return {"eppo": ";".join(dict.fromkeys(codes)) or None, "method": "confirme", "steps": steps}
