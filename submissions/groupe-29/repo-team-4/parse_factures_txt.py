"""Parse the B2 fixed-width invoice files ("Factures txt") into JSON.

The parsing itself lives in pipeline/b2.py (the pipeline uses it too); see that module for the output format.
The JSON files written here can be fed to the pipeline as the facture side (ingest.py, POST /pairs).

Usage:
    python parse_factures_txt.py ["Factures txt"] [-o factures_txt_json]
"""

import argparse
import json
from pathlib import Path

from pipeline.b2 import parse_file


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", nargs="?", default="Factures txt",
                        help="a B2 .txt file or a directory of them")
    parser.add_argument("-o", "--output", default="factures_txt_json",
                        help="directory receiving one <name>.json per .txt file")
    args = parser.parse_args()

    src = Path(args.input)
    files = sorted(src.glob("*.txt")) if src.is_dir() else [src]
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        out = out_dir / f"{f.stem}.json"
        out.write_text(json.dumps(parse_file(f), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(files)} file(s) written to {out_dir}/")


if __name__ == "__main__":
    main()
