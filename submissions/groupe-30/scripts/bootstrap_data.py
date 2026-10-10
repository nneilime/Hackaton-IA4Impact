"""Valide le kit et initialise uniquement une base vide, dans une transaction."""

import argparse
import json
from psycopg.types.json import Jsonb
from scripts.database import connection, revision, source_rows
from scripts.import_csv import initial_lot, preview
from scripts.schema import ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply", action="store_true", help="Initialiser une base vide avec le kit."
    )
    args = parser.parse_args()
    parsed = initial_lot()
    checked = preview(parsed, {})
    if checked["errors"]:
        raise ValueError(checked["errors"])
    reports = json.loads(
        (ROOT / "front" / "tests" / "fixtures" / "history.json").read_text(
            encoding="utf-8"
        )
    )["reports"]
    observations = [
        {
            "id": r["id"],
            "equipement_id": equipment_id,
            "trimestre": r["quarter"],
            "annee": r.get("year", 2025),
            "page": r["page"],
            "texte": r["text"],
            "url": r["url"],
        }
        for equipment_id, items in reports.items()
        for r in items
    ]
    if args.apply:
        with connection() as conn:
            if revision(conn) != 0 or any(source_rows(conn).values()):
                raise ValueError(
                    "La base contient déjà des données. Utilisez les imports de l’app pour les actualiser."
                )
            result = conn.execute(
                "select public.importer_lot(%s,0,%s) result",
                [Jsonb(parsed["lot"]), Jsonb(checked["files"])],
            ).fetchone()["result"]
            conn.execute(
                "insert into public.observations select * from jsonb_populate_recordset(null::public.observations,%s)",
                [Jsonb(observations)],
            )
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(
            json.dumps(
                {
                    "counts": {t: len(rows) for t, rows in parsed["lot"].items()},
                    "observations": len(observations),
                    "valid": True,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
