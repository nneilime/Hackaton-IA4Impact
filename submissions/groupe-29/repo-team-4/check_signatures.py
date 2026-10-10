"""Check zones 9-11 of the scanned bordereaux: signature boxes, who signed them and the totals printed in them.

For each scan:
  1. find the 8 boxes of the signature column and measure the ink in each (signed or empty), see pipeline/signatures.py
  2. with --ocr, read the texts of the boxes with a dedicated OCR pass on the column alone (the full-page OCR misses
     most of them) and cache it as <bordereaux_dir>/<name>/signature_boxes.json, which ingest.py then picks up
  3. print, per box, whether it is signed, what it says and whether its total matches its zone-10 rows

The results are stored in the database by ingest.py (table signature_boxes, checks C18 and X3); run it afterwards.

Usage: python check_signatures.py <images_dir> <bordereaux_dir> [--ocr [--overwrite]] [--only NAME ...]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from pipeline import load_bordereau, signatures
from pipeline.bordereau import clean_text, honoraires_rows, parse_table, segments_from_blocks, table_kind

CACHE = "signature_boxes.json"  # ingest.py reads it from the same place
PADDING = 6  # px kept around the column when cropping it for the OCR


def _block_text(text: str) -> str:
    """A block's text without markup: table cells are joined in reading order."""
    if "<table" in text:
        return " ".join(c for row in parse_table(text) for c in row if c)
    return clean_text(re.sub(r"<[^>]+>", " ", text))


def ocr_boxes(http, image_path: Path, boxes: list[signatures.PxBox], inks: list[float]) -> dict:
    """OCR every box that holds something, one small crop each (a crop of the whole column mixes the boxes up)."""
    import ocr  # the HF Space client; only needed with --ocr

    texts, messages = {}, []
    with Image.open(image_path) as im, tempfile.TemporaryDirectory() as tmp:
        page = im.convert("RGB")
        for n, (box, ink) in enumerate(zip(boxes, inks), 1):
            if ink < signatures.SIGNED_INK_RATIO:
                continue
            x1, y1, x2, y2 = box
            crop = page.crop((x1 + PADDING, y1 + PADDING, x2 - PADDING, y2 - PADDING))
            crop = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)  # small print reads better enlarged
            path = Path(tmp) / f"{image_path.stem}_box{n}.jpg"
            crop.save(path, quality=95)
            value = ocr.run(http, ocr.upload(http, path), path.name, "4B", 1024)
            texts[str(n)] = " ".join(_block_text(b["text"]) for b in value.get("blocks", []) if b["text"].strip())
            messages.append(f"box {n}: {value.get('message')}")
    return {"source": str(image_path), "boxes": texts, "messages": messages}


def zone10(bordereau: dict) -> tuple[list[dict], dict[int, str]]:
    segments = segments_from_blocks(bordereau["blocks"])
    lines, texts = [], {}
    for s in segments:
        if s.is_table and table_kind(s, segments) == "honoraires":
            rows, box_texts = honoraires_rows(s.rows)
            lines += rows
            texts.update(box_texts)
    return lines, texts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("images_dir", type=Path)
    parser.add_argument("bordereaux_dir", type=Path, help="the OCR output folders (<name>/result.json)")
    parser.add_argument("--ocr", action="store_true", help="OCR the signature column of each scan (HF Space)")
    parser.add_argument("--overwrite", action="store_true", help="with --ocr: redo the cached box OCR")
    parser.add_argument("--only", nargs="+", metavar="NAME", help="only these scans (e.g. Facture2_05)")
    args = parser.parse_args()

    images = sorted(p for p in args.images_dir.iterdir() if p.suffix.lower() in (".jpg", ".jpeg"))
    if args.only:
        images = [p for p in images if p.stem in args.only]
    http = None
    if args.ocr:
        import ocr
        http = ocr.client()

    problems = 0
    for image_path in images:
        folder = args.bordereaux_dir / image_path.stem
        result = folder / "result.json"
        if not result.exists():
            print(f"{image_path.stem}: no OCR result in {folder}, skipped", file=sys.stderr)
            continue
        gray = np.asarray(Image.open(image_path).convert("L"))
        boxes = signatures.locate_boxes(gray)
        if not boxes:
            print(f"{image_path.stem}: signature column not found", file=sys.stderr)
            problems += 1
            continue
        cache = folder / CACHE
        if http is not None and (args.overwrite or not cache.exists()):
            try:
                inks = [signatures.box_ink(gray, b) for b in boxes]
                cache.write_text(json.dumps(ocr_boxes(http, image_path, boxes, inks), ensure_ascii=False, indent=2),
                                 encoding="utf-8")
            except Exception as e:
                print(f"{image_path.stem}: box OCR failed: {e}", file=sys.stderr)

        lines, page_texts = zone10(load_bordereau(result))
        texts = {n: (t, "page_ocr") for n, t in page_texts.items()}
        if cache.exists():
            cached = json.loads(cache.read_text(encoding="utf-8"))
            texts |= {int(n): (t, "box_ocr") for n, t in cached["boxes"].items()}
        inks = [signatures.box_ink(gray, b) for b in boxes]
        results = signatures.assess_boxes(lines, texts, (boxes, inks))

        print(image_path.stem)
        for r in results:
            if not (r.signed or r.rows or r.text):
                continue
            amount = "" if r.printed_amount is None else f" printed {r.printed_amount / 100:.2f}"
            computed = "" if r.computed_amount is None else f" rows {r.computed_amount / 100:.2f}"
            state = "signed" if r.signed else "EMPTY"
            print(f"  box {r.box}: {state} (ink {r.ink_ratio:.3f}) {r.rows} rows{amount}{computed}"
                  f" {r.printed_executant or ''} {r.printed_name or ''}".rstrip()
                  + "".join(f"\n    ! {p}" for p in r.problems))
            problems += len(r.problems)
    print(f"{problems} problem(s). Run ingest.py to store the results.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
