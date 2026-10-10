"""Turn files or already-decoded JSON into the input shapes the flows expect.

facture:   {"lines": [<B2 record>, ...]}       from a B2 .txt file, its text, or a JSON object/list of lines
           {"parsed": {...}}                    from the JSON written by parse_factures_txt.py
bordereau: the OCR result ({"blocks": [...], "message": ..., ...}) from result.json / blocks.json or a JSON object
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


PARSED_KEYS = {"NumeroTiers", "NumeroLot", "NumeroAssure", "NumeroFacture", "Acte_Type3", "NumeroGH_Type3",
               "Acte_Type4", "NumeroGH_Type4S", "CodeCCAM_Type4M", "TotalPrestations", "TotalHonoraires"}


def load_facture(source: str | Path | dict | list) -> dict:
    if isinstance(source, Path):
        if source.suffix.lower() == ".json":
            return load_facture(json.loads(source.read_text(encoding="utf-8")))
        return {"lines": source.read_text(encoding="latin-1").splitlines(), "name": source.stem}
    if isinstance(source, str):
        return {"lines": source.splitlines()}
    if isinstance(source, list):
        return {"lines": [str(line) for line in source]}
    if isinstance(source, dict) and isinstance(source.get("lines"), list):
        return {**source, "lines": [str(line) for line in source["lines"]]}
    if isinstance(source, dict) and PARSED_KEYS <= source.keys():
        return {"parsed": copy.deepcopy(source)}
    raise ValueError("a facture is B2 text, a list of B2 lines, {'lines': [...]}, or parse_factures_txt.py JSON")


def load_bordereau(source: Path | dict) -> dict:
    if isinstance(source, Path):
        return load_bordereau(json.loads(source.read_text(encoding="utf-8")))
    if isinstance(source, dict) and isinstance(source.get("blocks"), list):
        for b in source["blocks"]:
            if not {"label", "bbox", "text"} <= b.keys():
                raise ValueError("every bordereau block needs label, bbox and text")
        return copy.deepcopy(source)  # the steps mutate their input
    raise ValueError("a bordereau is an OCR result object with a 'blocks' list")


def find_pairs(factures_dir: Path, bordereaux_dir: Path) -> list[tuple[str, Path, Path | None]]:
    """Match <name>.txt|.json in factures_dir with <name>/result.json or <name>.json in bordereaux_dir."""
    pairs: list[tuple[str, Path, Any]] = []
    for f in sorted(factures_dir.iterdir()):
        if f.suffix.lower() not in (".txt", ".json"):
            continue
        candidates = [bordereaux_dir / f.stem / "result.json", bordereaux_dir / f"{f.stem}.json"]
        pairs.append((f.stem, f, next((c for c in candidates if c.exists()), None)))
    return pairs
