"""Chemins et paramètres de l'application (aucun secret codé en dur)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("SENTINEL_ROOT", Path(__file__).resolve().parents[2]))
DATA_DIR = Path(os.environ.get("SENTINEL_DATA", ROOT / "data"))
ARCHIVE_PATH = Path(os.environ.get("SENTINEL_ARCHIVE", DATA_DIR / "General-main.zip"))
CORPUS_DIR = DATA_DIR / "corpus"          # extraction en lecture seule de l'archive
CACHE_DIR = DATA_DIR / "cache"            # résultats OCR (reproductibles, régénérables)
OCR_CACHE_DIR = CACHE_DIR / "ocr"
DB_PATH = Path(os.environ.get("SENTINEL_DB", DATA_DIR / "sentinel.db"))
STATIC_DIR = ROOT / "backend" / "static"  # build du frontend

JPG_SUBDIR = "Bordereaux jpg"
TXT_SUBDIR = "Factures txt"

# Paramètres opérationnels PROPOSÉS par l'équipe (pas des normes MSA).
PRIORITY_WEIGHTS = {
    "identification_anomaly": 40,   # anomalie empêchant un rapprochement fiable (R02-R05)
    "act_anomaly": 25,              # prestation / acte présent d'un côté seulement
    "amount_anomaly": 20,           # écart de montant
    "signature_issue": 10,          # signature absente ou non vérifiable
    "per_unverifiable": 3,          # par contrôle non vérifiable
    "per_euro_gap": 0.05,           # par euro d'écart mesuré (plafonné)
    "euro_gap_cap": 30,
}
