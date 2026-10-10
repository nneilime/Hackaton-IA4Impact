#!/usr/bin/env python3
"""Deserialize B2-style receipt files in receipts/ to readable JSON.

Spec (positions are 1-indexed inclusive, as in French Norme B2):
  Record code = 1st char of each line: 0 header, 1 debut lot, 2 debut
  facture, 3 prestations hospitalieres, 4 actes, 5 fin facture, 6 fin lot.
  Subtypes:
    2-S if pos39 == 'S' (else new facture)
    3-S if pos39 == 'S'; elif 3-H if pos36 == 'H'; else new acte
    4-S / 4-M / 4-B if pos36 in (S, M, B); else new acte
  Fields:
    T1: numero_tiers 2-10, numero_lot 20-22
    T2: numero_assure 12-24, numero_facture 30-38
    T3: acte 56-60, numero_gh 110-113
    T4: acte 76-80; 4S: numero_gh 120-123; 4M: code_ccam 43-55
    T5: total_prestations 42-49 (6+2)N, total_honoraires 58-65 (6+2)N

Usage:
  python3 parse_b2.py --input receipts --output parsed_json
  python3 parse_b2.py --input receipts/Facture1_01.txt --output parsed_json
"""

import argparse
import json
import os
import sys


def field(line, start, end):
    """Extract 1-indexed inclusive slice; return '' if out of range."""
    if len(line) < start:
        return ""
    return line[start - 1:min(end, len(line))]


def char_at(line, pos):
    """1-indexed char or '' if short."""
    if len(line) < pos:
        return ""
    return line[pos - 1]


def parse_amount(raw):
    """Decode (6+2)N fixed-point: '00081897' -> 818.97. Blank/invalid -> None."""
    s = (raw or "").strip()
    if not s:
        return None
    # keep only digits (tolerate spaces); reject non-numeric
    if not s.isdigit():
        return None
    try:
        return int(s) / 100.0
    except ValueError:
        return None


def classify(line):
    """Return (code, subtype). Subtype like '2', '2-S', '3', '3-S', '3-H',
    '4', '4-S', '4-M', '4-B', '0', '1', '5', '6'."""
    if not line:
        return "", ""
    code = line[0]
    if code == "2":
        return code, "2-S" if char_at(line, 39) == "S" else "2"
    if code == "3":
        if char_at(line, 39) == "S":
            return code, "3-S"
        if char_at(line, 36) == "H":
            return code, "3-H"
        return code, "3"
    if code == "4":
        c36 = char_at(line, 36)
        if c36 == "S":
            return code, "4-S"
        if c36 == "M":
            return code, "4-M"
        if c36 == "B":
            return code, "4-B"
        return code, "4"
    return code, code


# First data position of each record type: always non-blank in a well-formed
# file. A blank there means the line is shifted (e.g. Facture2_06: extra space
# at pos 12 moves every field one column right).
FIRST_DATA_POS = {"1": 17, "2": 12, "3": 12, "4": 12, "5": 12, "6": 11}


def parse_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        raw_lines = [ln.rstrip("\n") for ln in f]

    result = {
        "source_file": os.path.basename(path),
        "header": None,       # type 0 if present
        "lots": [],
        "errors": [],
    }
    current_lot = None
    current_facture = None

    def err(line_no, msg):
        result["errors"].append({"line": line_no, "message": msg})

    def ensure_lot(line_no):
        nonlocal current_lot
        if current_lot is None:
            err(line_no, "orphan line outside lot (auto-created lot)")
            current_lot = {"numero_tiers": None, "numero_lot": None,
                           "factures": []}
            result["lots"].append(current_lot)
        return current_lot

    def ensure_facture(line_no):
        nonlocal current_facture
        lot = ensure_lot(line_no)
        if current_facture is None:
            err(line_no, "orphan line outside facture (auto-created facture)")
            current_facture = {"numero_assure": None, "numero_facture": None,
                               "complements_2S": [],
                               "prestations_hospitalieres": [], "actes": [],
                               "total_prestations": None,
                               "total_honoraires": None}
            lot["factures"].append(current_facture)
        return current_facture

    for idx, line in enumerate(raw_lines, start=1):
        if not line.strip():
            continue
        code, subtype = classify(line)
        pos = FIRST_DATA_POS.get(code)
        if pos and char_at(line, pos) in ("", " "):
            err(idx, f"column shift: pos {pos} is blank for record type "
                     f"{code}, fields are misaligned")

        if code == "0":
            result["header"] = {"subtype": "0"}
        elif code == "1":
            current_facture = None
            current_lot = {
                "numero_tiers": field(line, 2, 10).strip() or None,
                "numero_lot": field(line, 20, 22).strip() or None,
                "factures": [],
            }
            result["lots"].append(current_lot)
        elif code == "2":
            lot = ensure_lot(idx)
            if subtype == "2-S":
                fac = ensure_facture(idx)
                fac["complements_2S"].append({"subtype": subtype})
            else:
                current_facture = {
                    "numero_assure": field(line, 12, 24).strip() or None,
                    "numero_facture": field(line, 30, 38).strip() or None,
                    "complements_2S": [],
                    "prestations_hospitalieres": [],
                    "actes": [],
                    "total_prestations": None,
                    "total_honoraires": None,
                }
                lot["factures"].append(current_facture)
        elif code == "3":
            fac = ensure_facture(idx)
            if subtype == "3":
                fac["prestations_hospitalieres"].append({
                    "acte": field(line, 56, 60).strip() or None,
                    "numero_gh": field(line, 110, 113).strip() or None,
                    "details": [],
                })
            else:  # 3-S / 3-H nested under last acte
                if not fac["prestations_hospitalieres"]:
                    err(idx, f"{subtype} without parent acte "
                             "(auto-created parent)")
                    fac["prestations_hospitalieres"].append({
                        "acte": None, "numero_gh": None,
                        "details": []})
                fac["prestations_hospitalieres"][-1]["details"].append(
                    {"subtype": subtype})
        elif code == "4":
            fac = ensure_facture(idx)
            if subtype == "4":
                fac["actes"].append({
                    "acte": field(line, 76, 80).strip() or None,
                    "details": [],
                })
            else:
                if not fac["actes"]:
                    err(idx, f"{subtype} without parent acte "
                             "(auto-created parent)")
                    fac["actes"].append({"acte": None,
                                         "details": []})
                detail = {"subtype": subtype}
                if subtype == "4-S":
                    detail["numero_gh"] = (
                        field(line, 120, 123).strip() or None)
                elif subtype == "4-M":
                    detail["code_ccam"] = (
                        field(line, 43, 55).strip() or None)
                # 4-B: no extra field per spec extract
                fac["actes"][-1]["details"].append(detail)
        elif code == "5":
            fac = ensure_facture(idx)
            tp_raw = field(line, 42, 49)
            th_raw = field(line, 58, 65)
            fac["total_prestations"] = parse_amount(tp_raw)
            fac["total_honoraires"] = parse_amount(th_raw)
            if fac["total_prestations"] is None and tp_raw.strip():
                err(idx, f"unparsable total_prestations {tp_raw!r}")
            if fac["total_honoraires"] is None and th_raw.strip():
                err(idx, f"unparsable total_honoraires {th_raw!r}")
            current_facture = None  # facture closed; next acte lines open new one only via type 2
            # Note: keep current_lot open for multi-facture lots
            # Re-arm: set a flag so following 3/4 without 2 auto-create facture (handled by ensure_facture)
        elif code == "6":
            lot = ensure_lot(idx)
            current_lot = None
            current_facture = None
        else:
            err(idx, f"unknown record code {code!r}")

    return result


def parse_text(content, source_name="input.txt"):
    """Parse B2 content from a string. Returns the same dict as parse_file.

    Useful for the backend when the file content is already in memory.
    """
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                     encoding="utf-8") as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        data = parse_file(tmp_path)
        data["source_file"] = source_name
        return data
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def parse_to_json(path, pretty=True):
    """Function-style API for the backend: file path in -> JSON string out."""
    return json.dumps(parse_file(path), indent=2 if pretty else None,
                      ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser(description="Deserialize B2 receipts to JSON")
    ap.add_argument("--input", required=True,
                    help="Input .txt file or directory (receipts/)")
    ap.add_argument("--output", default="-",
                    help="Output .json file, directory, or '-' for stdout "
                         "(default: stdout when input is a single file)")
    ap.add_argument("--pretty", action="store_true", default=True,
                    help="Pretty-print JSON (default on)")
    ap.add_argument("--no-pretty", dest="pretty", action="store_false")
    args = ap.parse_args()

    if os.path.isdir(args.input):
        files = sorted(f for f in os.listdir(args.input)
                       if f.endswith(".txt"))
        if not files:
            print(f"No .txt files in {args.input}", file=sys.stderr)
            sys.exit(1)
        if args.output in ("-", ""):
            print("Directory input requires --output <dir>",
                  file=sys.stderr)
            sys.exit(2)
        os.makedirs(args.output, exist_ok=True)
        for fn in files:
            src = os.path.join(args.input, fn)
            data = parse_file(src)
            dst = os.path.join(args.output, fn[:-4] + ".json")
            with open(dst, "w", encoding="utf-8") as out:
                json.dump(data, out, indent=2 if args.pretty else None,
                          ensure_ascii=False)
            nerr = len(data["errors"])
            print(f"{fn} -> {os.path.basename(dst)} "
                  f"({len(data['lots'])} lots, errors={nerr})",
                  file=sys.stderr)
    else:
        # Single file -> JSON to caller (stdout by default, file if --output given)
        data = parse_file(args.input)
        payload = json.dumps(data, indent=2 if args.pretty else None,
                             ensure_ascii=False)
        if args.output in ("-", ""):
            print(payload)
        else:
            out_path = args.output
            if os.path.isdir(out_path):
                out_path = os.path.join(
                    out_path,
                    os.path.basename(args.input)[:-4] + ".json")
            with open(out_path, "w", encoding="utf-8") as out:
                out.write(payload)
            print(f"{args.input} -> {out_path} "
                  f"(errors={len(data['errors'])})", file=sys.stderr)


if __name__ == "__main__":
    main()
