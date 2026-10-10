"""Run a flow on every (facture, bordereau) pair of two folders and store the results.

Usage: python ingest.py <factures_dir> <bordereaux_dir> [--images DIR] [--db invoices.db] [--flow facture_bordereau]
                        [--only NAME ...] [--new]

Pairs are matched by name: <factures_dir>/Facture1_01.txt (or the .json written by parse_factures_txt.py) with
<bordereaux_dir>/Facture1_01/result.json (or <bordereaux_dir>/Facture1_01.json). The scanned form is looked up as
<images>/Facture1_01.jpg, else at the "source" recorded in blocks.json. An existing pair with the same name is
refreshed in place: its review ticket and history are kept. The signature boxes (zone 11) are analysed on the scan,
with the box texts cached by check_signatures.py --ocr when present.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from pipeline import DEFAULT_FLOW, find_pairs, get_flow, load_bordereau, load_facture, store

SIGNATURE_CACHE = "signature_boxes.json"  # written next to result.json by check_signatures.py --ocr


def find_image(name: str, bordereau_path: Path, images: Path | None) -> str | None:
    candidates = [images / f"{name}.jpg", images / f"{name}.jpeg"] if images else []
    blocks = bordereau_path.with_name("blocks.json")
    if blocks.exists():
        source = Path(json.loads(blocks.read_text(encoding="utf-8")).get("source", ""))
        candidates.append(source if source.is_absolute() else blocks.parent / source)
    return next((str(c.resolve()) for c in candidates if c.is_file()), None)


def facture_raw(facture: dict) -> str | None:
    if "lines" in facture:
        return "\n".join(facture["lines"])
    lignes = facture["parsed"].get("Lignes")
    return "\n".join(l["Brut"] for l in lignes if l.get("Brut")) if lignes else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("factures_dir", type=Path)
    parser.add_argument("bordereaux_dir", type=Path)
    parser.add_argument("--db", type=Path, default=store.DEFAULT_DB, help="database file (default: %(default)s)")
    parser.add_argument("--flow", default=DEFAULT_FLOW)
    parser.add_argument("--images", type=Path, help="folder of the scanned bordereaux (<name>.jpg)")
    parser.add_argument("--only", nargs="+", metavar="NAME", help="only these pairs (e.g. Facture4_01)")
    parser.add_argument("--new", action="store_true", help="only the pairs not in the database yet")
    args = parser.parse_args()

    if not args.db.exists():
        parser.error(f"{args.db} does not exist, run create_db.py first")
    flow = get_flow(args.flow)
    counts, verdicts = {"ok": 0, "warning": 0, "error": 0, "skipped": 0}, Counter()
    with store.connect(args.db) as conn:
        store.create_schema(conn)  # adds tables / columns introduced since the database was created
        known = {r["name"] for r in conn.execute("SELECT name FROM pairs")} if args.new else set()
        for name, facture_path, bordereau_path in find_pairs(args.factures_dir, args.bordereaux_dir):
            if (args.only and name not in args.only) or name in known:
                continue
            if bordereau_path is None:
                print(f"{name}: no bordereau found, skipped", file=sys.stderr)
                counts["skipped"] += 1
                continue
            facture, bordereau = load_facture(facture_path), load_bordereau(bordereau_path)
            docs = store.Documents(str(facture_path), str(bordereau_path), find_image(name, bordereau_path, args.images),
                                   facture_raw(facture), bordereau.get("raw"))
            if docs.image_path is None:  # a refresh without --images still analyses the scan stored last time
                docs.image_path = conn.execute("SELECT image_path FROM pairs WHERE name = ?", (name,)).fetchone()
                docs.image_path = docs.image_path["image_path"] if docs.image_path else None
            cache = bordereau_path.with_name(SIGNATURE_CACHE)
            assets = {"image_path": docs.image_path,
                      "signature_boxes_ocr": json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else None}
            ctx = flow.run(facture, bordereau, assets)
            store.save(conn, name, flow.name, ctx, docs)
            counts[ctx.status] += 1
            a = ctx.record.get("assessment") or {}
            verdicts[a.get("verdict")] += 1
            failed = f" failed {','.join(a['failed'])}" if a.get("failed") else ""
            print(f"{name}: {a.get('verdict')} (risk {a.get('risk_score')}){failed} [extraction {ctx.status}]"
                  + ("" if docs.image_path else " [no image]"))
    print("extraction: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    print("verdicts: " + ", ".join(f"{k} {v}" for k, v in verdicts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
