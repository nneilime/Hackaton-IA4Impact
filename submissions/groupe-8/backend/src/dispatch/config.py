"""Load config/default.yaml into attribute-access objects (cfg.roster.work_h)."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "default.yaml"


def _to_ns(value):
    if isinstance(value, dict):
        return SimpleNamespace(**{k: _to_ns(v) for k, v in value.items()})
    return value


def load_config(path: str | Path = DEFAULT_CONFIG, **overrides) -> SimpleNamespace:
    """Read the YAML config. `overrides` replace top-level sections, e.g. objective={...}."""
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    for section, values in overrides.items():
        raw.setdefault(section, {}).update(values)
    return _to_ns(raw)
