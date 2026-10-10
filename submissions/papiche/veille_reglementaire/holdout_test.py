# SPDX-License-Identifier: AGPL-3.0-or-later
"""Test hors échantillon : le prompt a-t-il appris la tâche, ou seulement nos 197 passages de réglage ?

Même discipline qu'Arbor (jeu « dev » pour explorer, jeu « held-out » jamais vu pour valider) : on tire au hasard des
produits e-Phy qui ne sont PAS dans config/scope.json, donc jamais regardés pendant le réglage du prompt, et on compare
l'extraction aux colonnes structurées d'e-Phy (vérité terrain), exactement comme pour l'évaluation principale.
"""
from __future__ import annotations

import json
import random

from . import config, evaluation, extraction_loop, pipeline
from .sources import ephy


def eligible_product_names() -> list[str]:
    """Produits e-Phy qui ont des usages et qui ne sont pas dans le périmètre de réglage."""
    tuned = {name.casefold() for product in pipeline.scope()["products"] for name in product.get("ephy", [])}
    with_usages = {row["nom produit"] for row in ephy._rows("produits_usages_utf8.csv")}
    return sorted(name for name in with_usages if name.casefold() not in tuned)


def draw_passages(product_count: int, per_product: int, seed: int) -> list:
    names = random.Random(seed).sample(eligible_product_names(), product_count)
    passages = ephy.passages({"products": [{"ephy": [name]} for name in names]})
    by_product: dict[str, list] = {}
    for passage in sorted(passages, key=lambda p: p.passage_id):
        by_product.setdefault(passage.product, []).append(passage)
    return [p for group in by_product.values() for p in group[:per_product]]


def count_dose_errors(traces: list[dict], expected: dict[str, dict]) -> dict:
    """Parmi les passages publiés : dose oubliée (null alors que la source en a une) ou dose différente."""
    omitted = wrong = 0
    for trace in traces:
        gold = expected.get(trace["passage"]["passage_id"])
        if trace["outcome"] != "accepted" or not gold or gold["dose_value"] is None:
            continue
        extracted = trace["record"]["dose_value"]
        omitted += extracted is None
        wrong += extracted is not None and not evaluation.same_value(extracted, gold["dose_value"])
    return {"dose_oubliee": omitted, "dose_differente": wrong}


def run(product_count: int = 40, per_product: int = 4, seed: int = 1) -> dict:
    passages = draw_passages(product_count, per_product, seed)
    print(f"[holdout] {len(passages)} passages de {len({p.product for p in passages})} produits jamais utilisés pour le réglage", flush=True)
    traces = []
    for number, passage in enumerate(passages, 1):
        traces.append(extraction_loop.extract_passage(passage))
        print(f"  {number}/{len(passages)} {passage.product[:28]:28} {traces[-1]['outcome']} essais={len(traces[-1]['attempts'])}", flush=True)

    expected = {p.passage_id: p.gold for p in passages}
    published = [t for t in traces if t["outcome"] == "accepted"]
    report = {
        "model": config.MODEL, "seed": seed, "products": sorted({p.product for p in passages}), "passages": len(passages),
        "published": len(published), "sent_to_expert": len(traces) - len(published),
        "first_try": sum(len(t["attempts"]) == 1 for t in published),
        **evaluation.score_against_source(traces, expected), **count_dose_errors(traces, expected),
        "passages_with_dose": sum(p.gold["dose_value"] is not None for p in passages),
    }
    (config.PROCESSED / "holdout.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    (config.PROCESSED / "holdout_traces.jsonl").write_text("\n".join(json.dumps(t, ensure_ascii=False) for t in traces) + "\n", encoding="utf-8")
    return report
