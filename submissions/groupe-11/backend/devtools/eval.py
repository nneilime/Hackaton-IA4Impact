"""Per-zone extraction accuracy against hand-labelled expected.json.

expected.json is a list of documents shaped like extract.py's output: valid against
backend/deserialization/b2.schema.json, plus the `scan` object. Both sides are read the same way.

  uv run python devtools/eval.py   # from backend/, needs the OCR cache (extract.py)
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from extract import SCHEMA, extract  # noqa: E402


def cents(x):
    return None if x is None else round(x * 100)


def read(doc, zone):
    """Value of one zone in a document, normalised for comparison."""
    sc, lot = doc["scan"], doc["lots"][0]
    f = lot["factures"][0]
    return {
        1: lambda: re.sub(r"\D", "", sc["cerfa"] or ""),
        2: lambda: lot["numero_tiers"], 3: lambda: lot["numero_lot"],
        4: lambda: f["numero_facture"], 5: lambda: f["numero_assure"],
        6: lambda: [[r["acte"], r["numero_gh"], cents(r["montant"])] for r in sc["zone6"]],
        7: lambda: [[r["acte"], r["numero_gh"]] for r in sc["zone7"]],
        8: lambda: cents(f["total_prestations"]),
        9: lambda: list(dict.fromkeys(sc["executants"])),
        10: lambda: [a["acte"] or a["details"][0]["code_ccam"] for a in f["actes"]],
        11: lambda: sc["signatures"],
        12: lambda: cents(f["total_honoraires"]),
        13: lambda: cents(sc["total"]),
        14: lambda: sc["signature_directeur"],
        15: lambda: (sc["form_code"] or "").replace(" ", ""),
    }[zone]()


def main():
    validator = Draft202012Validator(SCHEMA)
    ok, total, misses = defaultdict(int), defaultdict(int), []
    for want in json.loads((Path(__file__).parent / "expected.json").read_text()):
        validator.validate(want)
        name = want["source_file"].removesuffix(".jpg")
        got = extract(name)
        if got is None:
            print(f"{name}: no OCR cache, skipped")
            continue
        for zone in range(1, 16):
            total[zone] += 1
            if read(got, zone) == read(want, zone):
                ok[zone] += 1
            else:
                misses.append(f"  {name} zone {zone}: expected {read(want, zone)!r}, got {read(got, zone)!r}")
    for zone in sorted(total):
        print(f"zone {zone:>2}: {ok[zone]}/{total[zone]}")
    print(f"overall: {sum(ok.values())}/{sum(total.values())}")
    print("\n".join(misses) or "no misses")


if __name__ == "__main__":
    main()
