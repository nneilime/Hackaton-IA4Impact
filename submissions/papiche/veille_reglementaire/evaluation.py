# SPDX-License-Identifier: AGPL-3.0-or-later
"""Évaluation : compare l'extraction de l'IA aux colonnes STRUCTURÉES de la source (vérité terrain e-Phy).

Ce que le jury peut vérifier : exactitude champ par champ, taux de rejet, nombre d'essais, valeurs inventées.
- PMRA ne publie pas de dose : on mesure surtout que l'IA répond bien « null ».
- EPA (étiquettes PDF) n'a pas de vérité structurée : contrôle manuel par échantillon (voir README).
"""
from __future__ import annotations

from collections import Counter

from . import qdrant_store

FIELDS_COMPARED = ["dose_value", "dose_unit", "max_applications", "pre_harvest_interval_days", "min_interval_days"]


def same_value(extracted, expected) -> bool:
    """Deux valeurs sont identiques si elles sont toutes deux vides, ou égales (nombres : tolérance 1e-9)."""
    if extracted is None or expected is None:
        return extracted is None and expected is None
    if isinstance(extracted, float) or isinstance(expected, float):
        return abs(extracted - expected) < 1e-9
    return extracted == expected


def score_against_source(traces: list[dict], expected_by_passage: dict[str, dict]) -> dict:
    """Pour chaque passage accepté qui a une vérité terrain, compare les champs extraits aux champs attendus."""
    correct = {field: 0 for field in FIELDS_COMPARED}
    total = {field: 0 for field in FIELDS_COMPARED}
    invented_values = 0          # valeur publiée alors que la source n'en contient pas
    compared_records = 0

    for trace in traces:
        passage_id = trace["passage"]["passage_id"]
        if trace["outcome"] != "accepted" or passage_id not in expected_by_passage:
            continue
        compared_records += 1
        record, expected = trace["record"], expected_by_passage[passage_id]
        for field in FIELDS_COMPARED:
            total[field] += 1
            correct[field] += same_value(record.get(field), expected.get(field))
            if record.get(field) is not None and expected.get(field) is None:
                invented_values += 1

    return {
        "records_evalues": compared_records,
        "exactitude_par_champ": {f: round(correct[f] / total[f], 3) if total[f] else None for f in FIELDS_COMPARED},
        "valeurs_inventees_publiees": invented_values,
    }


def run(traces: list[dict]) -> dict:
    expected = {p.passage_id: p.gold for p in qdrant_store.all_passages() if p.gold}
    result = score_against_source(traces, expected)
    attempts_per_passage = Counter(len(t["attempts"]) for t in traces)
    outcome_per_source = Counter((t["passage"]["source_id"], t["outcome"]) for t in traces)
    result["essais_par_passage"] = dict(sorted(attempts_per_passage.items()))
    result["issues"] = {f"{source}:{outcome}": n for (source, outcome), n in sorted(outcome_per_source.items())}
    return result
