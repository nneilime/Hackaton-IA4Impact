"""Génère connector/power-platform.swagger.json à partir du YAML (le fichier à importer dans Power Platform).

Usage :
    python scripts/build_connector.py                      # hôte du YAML
    python scripts/build_connector.py --host xxx.trycloudflare.com   # autre hôte (plan B tunnel)
"""
import argparse
import json
from pathlib import Path

import yaml

CONNECTOR_DIR = Path(__file__).resolve().parent.parent / "connector"
SOURCE = CONNECTOR_DIR / "power-platform.swagger.yaml"
TARGET = CONNECTOR_DIR / "power-platform.swagger.json"


def build(host=None):
    """Lit le YAML, remplace éventuellement l'hôte, écrit le JSON. Retourne le dictionnaire écrit."""
    swagger = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    if host:
        swagger["host"] = host
    TARGET.write_text(json.dumps(swagger, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return swagger


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", help="remplace `host` (domaine seul, sans https://)")
    args = parser.parse_args()
    result = build(args.host)
    print(f"{TARGET.name} écrit — hôte : {result['host']}, {len(result['paths'])} chemins")
