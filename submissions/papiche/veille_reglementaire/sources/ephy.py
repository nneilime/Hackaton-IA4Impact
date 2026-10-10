# SPDX-License-Identifier: AGPL-3.0-or-later
"""Source 1 — e-Phy (ANSES, France / Europe). Open data data.gouv.fr, licence ouverte, CSV.

Collecte : on résout dynamiquement la dernière version via l'API data.gouv.fr (aucune clé).
"""
from __future__ import annotations
import csv, hashlib, json, re, zipfile
from datetime import date
from .. import config, polite_http
from . import Passage

DATASET_API = ("https://www.data.gouv.fr/api/1/datasets/"
               "donnees-ouvertes-du-catalogue-e-phy-des-produits-phytopharmaceutiques-matieres-fertilisantes-"
               "et-supports-de-culture-adjuvants-produits-mixtes-et-melanges/")
DATASET_PAGE = "https://www.data.gouv.fr/datasets/donnees-ouvertes-du-catalogue-e-phy-des-produits-phytopharmaceutiques-matieres-fertilisantes-et-supports-de-culture-adjuvants-produits-mixtes-et-melanges/"
WANTED = ("produits_utf8.csv", "produits_usages_utf8.csv")


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


INFO = {"id": "ephy", "name": "e-Phy (ANSES)", "country_code": "FR", "country": "France", "region": "Europe",
        "format": "CSV (data.gouv.fr)", "lang": "FR"}


def collect(scope: dict | None = None) -> dict:
    """Télécharge le jeu e-Phy (CSV UTF-8) dans data/raw/ephy : 2 requêtes, et 0 octet si rien n'a changé."""
    folder = config.RAW / "ephy"
    dataset = polite_http.get_json(DATASET_API)
    resource = next(r for r in dataset["resources"] if "csv" in r["title"].lower() and "utf8" in r["title"].lower())
    archive = folder / "ephy_csv_utf8.zip"
    result = polite_http.download(resource["url"], archive)
    if result["changed"] or not all((folder / name).exists() for name in WANTED):
        with zipfile.ZipFile(archive) as zipped:
            for name in WANTED:
                (folder / name).write_bytes(zipped.read(name))
    (folder / "_meta.json").write_text(json.dumps(
        {"resource": resource["title"], "url": resource["url"], "collected_at": date.today().isoformat()}))
    return {"source": "ephy", "resource": resource["title"], "url": resource["url"], "changed": result["changed"]}


def _rows(name: str):
    with open(config.RAW / "ephy" / name, encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f, delimiter=";")


def _num(v: str):
    try:
        return float(v.replace(",", "."))
    except (ValueError, AttributeError):
        return None


def _int(v: str):
    n = _num(v)
    return int(n) if n is not None else None


def passages(scope: dict) -> list[Passage]:
    wanted = {n.casefold() for p in scope["products"] for n in p.get("ephy", [])}
    products = {}
    for r in _rows("produits_utf8.csv"):
        if r["nom produit"].casefold() in wanted:
            products[r["numero AMM"]] = r
    collected = date.today().isoformat()
    try:
        import json
        collected = json.loads((config.RAW / "ephy" / "_meta.json").read_text())["collected_at"]
        dataset_url = json.loads((config.RAW / "ephy" / "_meta.json").read_text())["url"]
    except Exception:
        dataset_url = DATASET_PAGE
    out: list[Passage] = []
    for r in _rows("produits_usages_utf8.csv"):
        amm = r["numero AMM"]
        if amm not in products:
            continue
        p = products[amm]
        etat = p["Etat d’autorisation"]
        parts = [f"Produit: {r['nom produit']} (AMM {amm})", f"Titulaire: {p['titulaire']}",
                 f"Usage: {r['identifiant usage']}", f"Etat de l'usage: {r['etat usage']}"]
        if r["dose retenue"]:
            parts.append(f"Dose retenue: {r['dose retenue']} {r['dose retenue unite']}".rstrip())
        if r["nombre max d'application"]:
            parts.append(f"Nombre max d'applications: {r['nombre max d\'application']}")
        if r["delai avant recolte jour"]:
            parts.append(f"Delai avant recolte (jours): {r['delai avant recolte jour']}")
        if r["intervalle minimum entre applications (jour)"]:
            parts.append(f"Intervalle minimum entre applications (jours): {r['intervalle minimum entre applications (jour)']}")
        for col, lab in (("ZNT aquatique (en m)", "ZNT aquatique (m)"),):
            if r[col]:
                parts.append(f"{lab}: {r[col]}")
        if r["condition emploi"]:
            parts.append(f"Condition d'emploi: {r['condition emploi'][:500]}")
        text = " | ".join(parts)
        pid = f"ephy:{amm}:{hashlib.sha1(r['identifiant usage'].encode()).hexdigest()[:8]}:{r['dose retenue']}"
        out.append(Passage(
            passage_id=pid, source_id="ephy", country="FR", region="Europe", product=r["nom produit"],
            reg_number=amm, holder=p["titulaire"], status_original=etat,
            status={"AUTORISE": "autorise", "RETIRE": "retire"}.get(etat.upper(), "autre"),
            ai=p["Substances actives"], text=text, source_url=f"https://ephy.anses.fr/ppp/{slug(r['nom produit'])}",
            dataset_url=dataset_url, collected_at=collected,
            gold={"dose_value": _num(r["dose retenue"]), "dose_unit": r["dose retenue unite"] or None,
                  "max_applications": _int(r["nombre max d'application"]),
                  "pre_harvest_interval_days": _int(r["delai avant recolte jour"]),
                  "min_interval_days": _int(r["intervalle minimum entre applications (jour)"])}))
    return out
