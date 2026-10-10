"""Déduplique les prix du catalogue du modèle et les importe par la transaction commune."""

import argparse
import csv
import hashlib
import io
import json
from decimal import Decimal
from pathlib import Path

from psycopg.types.json import Jsonb
from scripts.predict_equipment import DEFAULT_PRICE_CATALOG


def price_lot(path=DEFAULT_PRICE_CATALOG):
    from scripts.import_csv import parse_files

    path = Path(path)
    payload = path.read_bytes()
    rows = {}
    for row in csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))):
        key = tuple(row[k] for k in ("famille", "type_intervention", "type_panne"))
        price = Decimal(row["prix"])
        if key in rows and Decimal(rows[key]["prix"]) != price:
            raise ValueError(f"Prix contradictoires pour {key}.")
        rows[key] = dict(
            zip(
                ("famille", "type_intervention", "type_panne", "prix"),
                (*key, row["prix"]),
            )
        )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=["famille", "type_intervention", "type_panne", "prix"]
    )
    writer.writeheader()
    writer.writerows(rows.values())
    parsed = parse_files(
        [("prix_interventions.csv", stream.getvalue().encode("utf-8"))]
    )
    if parsed["errors"]:
        raise ValueError(parsed["errors"])
    parsed["files"][0].update(
        {"source": str(path.name), "sourceSha256": hashlib.sha256(payload).hexdigest()}
    )
    return parsed


def main():
    from scripts.database import connection, revision, source_rows
    from scripts.import_csv import preview

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_PRICE_CATALOG)
    parser.add_argument(
        "--output", type=Path, help="Écrit le CSV normalisé, importable depuis l'app."
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    parsed = price_lot(args.input)
    if args.output:
        with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=["famille", "type_intervention", "type_panne", "prix"],
            )
            writer.writeheader()
            writer.writerows(parsed["lot"]["prix_interventions"])
    with connection() as conn:
        report = preview(parsed, source_rows(conn))
        if report["errors"]:
            raise ValueError(report["errors"])
        if args.apply:
            report["result"] = conn.execute(
                "select public.importer_lot(%s,%s,%s) as result",
                [Jsonb(parsed["lot"]), revision(conn), Jsonb(report["files"])],
            ).fetchone()["result"]
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
