# SPDX-License-Identifier: AGPL-3.0-or-later
"""Source 2 — Santé Canada / PMRA, Pesticide Product Information Database (open data, CSV, sans clé).

Le registre public ne publie pas la dose dans ce jeu : l'IA doit répondre null plutôt qu'inventer.
"""
from __future__ import annotations
import csv, hashlib, json
from datetime import date
from .. import config, polite_http
from . import Passage

API = "https://pest-control.canada.ca/pesticide-registry-api/api/extract"


INFO = {"id": "pmra", "name": "PMRA / Santé Canada", "country_code": "CA", "country": "Canada",
        "region": "Amérique du Nord", "format": "CSV (API ouverte)", "lang": "EN"}


def collect(scope: dict | None = None) -> dict:
    """Télécharge le registre PMRA (un seul fichier CSV) : 1 requête, et 0 octet si rien n'a changé."""
    folder = config.RAW / "pmra"
    result = polite_http.download(f"{API}/product", folder / "product.csv")
    (folder / "_meta.json").write_text(json.dumps({"url": f"{API}/product", "collected_at": date.today().isoformat()}))
    return {"source": "pmra", "url": f"{API}/product", "changed": result["changed"]}


def _split(v: str) -> list[str]:
    return [x.strip() for x in (v or "").split(";") if x.strip()]


def passages(scope: dict) -> list[Passage]:
    wanted = {n.casefold() for p in scope["products"] for n in p.get("pmra", [])}
    meta = json.loads((config.RAW / "pmra" / "_meta.json").read_text())
    out: list[Passage] = []
    with open(config.RAW / "pmra" / "product.csv", encoding="cp1252", errors="replace", newline="") as f:
        for r in csv.DictReader(f):
            name = r["Product name - English"]
            if name.casefold() not in wanted:
                continue
            reg = r["Registration number"]
            status = r["Registration Status"]
            pests = _split(r["Pests"]) or [""]
            for pest in pests:
                parts = [f"Registration number: {reg}", f"Product: {name}", f"Registration status: {status}",
                         f"Expiry date: {r['Expiry date']}", f"Registrant: {r['Registrant name']}",
                         f"Product type: {r['Product Type']}", f"Use site category: {r['Use Site Category']}"]
                if r["Sites of Use"]:
                    parts.append(f"Sites of use: {r['Sites of Use'][:400]}")
                parts.append(f"Pest: {pest}" if pest else "Pest: (none listed)")
                out.append(Passage(
                    passage_id=f"pmra:{reg}:{hashlib.sha1(pest.encode()).hexdigest()[:8]}",
                    source_id="pmra", country="CA", region="Amérique du Nord", product=name, reg_number=reg,
                    holder=r["Registrant name"], status_original=status,
                    status="autorise" if status.startswith(("Full", "Conditional")) else "autre",
                    ai=r["Active ingredients - English"], text=" | ".join(parts), source_url=f"{API}/product/{reg}", dataset_url=meta["url"],
                    collected_at=meta["collected_at"],
                    gold={"dose_value": None, "dose_unit": None, "max_applications": None,
                          "pre_harvest_interval_days": None, "min_interval_days": None}))
    return out
