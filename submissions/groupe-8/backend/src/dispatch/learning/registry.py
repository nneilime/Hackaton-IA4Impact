"""Versioned registry of permanent constraints (config/constraint_registry.yaml).

Constraints are DATA the engine reads, not code. Entries are added only by the expert review (learning/review.py)
after a replay test; each has an id, a description, a status (active / retired), its origin and version.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from dispatch.config import ROOT
from dispatch.engine.modifiers import Modifier, from_dict

DEFAULT_PATH = ROOT / "config" / "constraint_registry.yaml"


def read(path: Path = DEFAULT_PATH) -> dict:
    if not Path(path).exists():
        return {"version": 0, "constraints": []}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"version": 0, "constraints": []}


def load_registry(cfg=None, path: Path = DEFAULT_PATH) -> list[Modifier]:
    reg = read(path)
    if cfg is not None:
        cfg._registry_version = reg.get("version", 0)
    return [from_dict(dict(c["modifier"], reason=c.get("description", ""), scope="permanent"))
            for c in reg.get("constraints", []) if c.get("status") == "active"]


def activate(candidate: dict, approved_by: str, path: Path = DEFAULT_PATH) -> dict:
    """Add a validated candidate as an active constraint; bumps the registry version."""
    reg = read(path)
    reg["version"] = reg.get("version", 0) + 1
    entry = {"id": f"C{len(reg['constraints']) + 1:03d}", "description": candidate["description"],
             "modifier": candidate["modifier"], "status": "active", "origin": candidate.get("origin", "expert review"),
             "evidence": candidate.get("evidence", {}), "approved_by": approved_by,
             "activated_on": date.today().isoformat(), "registry_version": reg["version"]}
    reg["constraints"].append(entry)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(reg, f, allow_unicode=True, sort_keys=False)
    return entry


def retire(constraint_id: str, path: Path = DEFAULT_PATH) -> None:
    reg = read(path)
    reg["version"] = reg.get("version", 0) + 1
    for c in reg["constraints"]:
        if c["id"] == constraint_id:
            c["status"] = "retired"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(reg, f, allow_unicode=True, sort_keys=False)
