# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tableau comparatif produit × pays × usage, avec retour à la source (URL + date de collecte)."""
from __future__ import annotations
import csv, io
from collections import defaultdict

COLS = ["product", "country", "authorization_status", "crop_original", "crop_eppo", "target_original", "target_eppo",
        "dose_original", "dose_norm_value", "dose_norm_unit", "max_applications", "pre_harvest_interval_days",
        "validation_status", "source_id", "source_url", "collected_at", "quote"]


def flat(r: dict) -> dict:
    c = r["citation"]
    d = {k: r.get(k) for k in COLS if k not in ("source_id", "source_url", "collected_at", "quote")}
    d.update(source_id=c["source_id"], source_url=c["source_url"], collected_at=c["collected_at"], quote=c["quote"])
    return d


def table(records: list[dict], product: str | None = None, countries: list[str] | None = None,
          crop: str | None = None, target: str | None = None) -> list[dict]:
    def keep(r):
        if product and product.casefold() not in r["product"].casefold():
            return False
        if countries and r["country"] not in countries:
            return False
        if crop and crop.casefold() not in f"{r.get('crop_original') or ''} {r.get('crop_eppo') or ''}".casefold():
            return False
        if target and target.casefold() not in f"{r.get('target_original') or ''} {r.get('target_eppo') or ''}".casefold():
            return False
        return True
    rows = [flat(r) for r in records if keep(r)]
    return sorted(rows, key=lambda x: (x["product"], x["country"], x["crop_original"] or "", x["target_original"] or ""))


def footprint(records: list[dict]) -> list[dict]:
    """Empreinte réglementaire : par produit et pays, statut et nombre d'usages documentés."""
    agg = defaultdict(lambda: {"usages": 0, "with_dose": 0, "status": set(), "validated": 0})
    for r in records:
        a = agg[(r["product"], r["country"])]
        a["usages"] += 1
        a["with_dose"] += r.get("dose_value") is not None
        a["status"].add(r.get("authorization_status_original") or "?")
        a["validated"] += r["validation_status"] == "verifie_auto"
    return [{"product": p, "country": c, "usages": a["usages"], "with_dose": a["with_dose"],
             "statuses": sorted(a["status"]), "verifie_auto": a["validated"]}
            for (p, c), a in sorted(agg.items())]


def to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLS, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()
