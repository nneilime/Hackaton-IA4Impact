# SPDX-License-Identifier: AGPL-3.0-or-later
"""Exports pour l'écosystème Microsoft 365 : contrat OpenAPI (connecteur Power Platform / Copilot Studio),
schéma de table Dataverse et CSV comparatif (import SharePoint / Excel)."""
from __future__ import annotations
import csv, json
from . import comparison_table, config, pipeline
from .models import Record

OUT = config.ROOT / "m365"

DATAVERSE_TYPES = {"string": "Texte (une ligne)", "number": "Nombre décimal", "integer": "Nombre entier", "array": "Texte multiligne (JSON)",
                   "object": "Texte multiligne (JSON)", "boolean": "Oui/Non"}


def export():
    OUT.mkdir(exist_ok=True)
    from .api import app
    (OUT / "openapi.json").write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=1), encoding="utf-8")
    rows = comparison_table.table(pipeline.load("records.jsonl"))
    (OUT / "comparatif_produit_pays_usage.csv").write_text(comparison_table.to_csv(rows), encoding="utf-8-sig")  # BOM : Excel FR
    props = Record.model_json_schema()["properties"]
    with open(OUT / "dataverse_table_lpc_record.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Nom logique", "Type Dataverse suggéré", "Description"])
        for k, v in props.items():
            t = v.get("type") or next((a.get("type") for a in v.get("anyOf", []) if a.get("type") != "null"), "string")
            w.writerow([f"lpc_{k}", DATAVERSE_TYPES.get(t, "Texte (une ligne)"), v.get("title", k)])
    print(f"m365/ : openapi.json, comparatif ({len(rows)} lignes), dataverse_table_lpc_record.csv")
