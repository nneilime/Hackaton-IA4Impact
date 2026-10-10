#!/usr/bin/env python3
"""Load the starter reference data into an EXISTING database, safely.

- Never drops, deletes or overwrites anything: rows that already exist are skipped.
- Safe on a shared server and safe to run many times.

  python backend/etl/adapters/canada/scripts/seed_reference.py
"""
import csv, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))   # backend/, the folder that contains etl/
from etl.adapters.base import project_root
from etl.adapters.canada.loader import connect

ROOT = project_root()
TABLES = [("source_registry", "source_id"), ("products", "product_id"),
          ("product_name_mapping", "mapping_id"), ("active_entity_mapping", "mapping_id"),
          ("eppo_crop_mapping", "concept_id"), ("eppo_pest_mapping", "concept_id")]


def main():
    with connect() as conn:
        for table, pk in TABLES:
            with (ROOT / "data" / f"{table}.csv").open(encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            if table == "products":   # starter products only; adapter products come from the adapters
                rows = [r for r in rows if r["product_id"].startswith(("P-LPC-", "P-DEMO-"))]
            if not rows:
                continue
            cols = list(rows[0].keys())
            sql = (f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "
                   f"ON CONFLICT ({pk}) DO NOTHING")
            before = conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
            with conn.cursor() as cur:
                cur.executemany(sql, [tuple(r[c] if r[c] != "" else None for c in cols) for r in rows])
            after = conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
            print(f"{table}: {after - before} added, {len(rows) - (after - before)} already there")
        conn.commit()
    print("Reference data ready.")


if __name__ == "__main__":
    main()