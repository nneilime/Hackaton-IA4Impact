#!/usr/bin/env python3
"""Self-test for parse_b2, plus a pretty-printer for any receipt.

Run from backend/:
  uv run python devtools/test_parse_b2.py                     # asserts
  uv run python devtools/test_parse_b2.py ../receipts/X.txt   # print JSON
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from deserialization.parse_b2 import parse_file  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def test():
    # Values cross-checked against images/Facture1_01.jpg
    d = parse_file(ROOT / "receipts" / "Facture1_01.txt")
    assert d["errors"] == [], d["errors"]
    lot = d["lots"][0]
    assert (lot["numero_tiers"], lot["numero_lot"]) == ("200200145", "574")
    f = lot["factures"][0]
    assert f["numero_assure"] == "2520299007001"
    assert f["numero_facture"] == "260800001"
    assert [p["acte"] for p in f["prestations_hospitalieres"]] == ["GHS", "PH8", "EMI"]
    assert {p["numero_gh"] for p in f["prestations_hospitalieres"]} == {"9606"}
    assert [a["acte"] for a in f["actes"]] == ["K"]
    assert round(f["total_prestations"] * 100) == 81897
    assert round(f["total_honoraires"] * 100) == 2880

    # Malformed on purpose: extra space at pos 12 shifts every field
    d = parse_file(ROOT / "receipts" / "Facture2_06.txt")
    assert any("column shift" in e["message"] for e in d["errors"]), d["errors"]
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(json.dumps(parse_file(sys.argv[1]), indent=2, ensure_ascii=False))
    else:
        test()
