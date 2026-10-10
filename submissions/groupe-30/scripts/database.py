"""Accès serveur Supabase : une identité vérifiée par transaction, aucun secret front."""

from __future__ import annotations
import os
import json
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from dotenv import load_dotenv

from scripts.schema import ROOT, TABLES

load_dotenv(ROOT / ".env")


def safe(value):
    if isinstance(value, dict):
        return {k: safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    return value


@contextmanager
def connection(user_id: str | None = None, *, snapshot=False):
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL doit être renseignée dans le .env serveur.")
    with psycopg.connect(
        url, row_factory=dict_row, connect_timeout=15, sslmode="require"
    ) as conn:
        with conn.transaction():
            if snapshot:
                conn.execute(
                    "set transaction isolation level repeatable read read only"
                )
            if user_id:
                conn.execute("set local role batia_api")
                conn.execute(
                    "select set_config('request.jwt.claims',%s,true)",
                    [json.dumps({"sub": str(UUID(user_id)), "role": "authenticated"})],
                )
            yield conn


def revision(conn):
    return conn.execute(
        "select coalesce(max(id),0) as revision from public.imports where statut='applique' and nb_ajouts+nb_modifications>0"
    ).fetchone()["revision"]


def source_rows(conn, tables=None):
    return {
        t: conn.execute(f"select * from public.{t}").fetchall()
        for t in (tables or TABLES)
    }


def model_record(row):
    return {
        k: (
            ("Oui" if v else "Non")
            if isinstance(v, bool)
            else (
                ""
                if v is None
                else (
                    v.isoformat(sep=" ")
                    if isinstance(v, datetime)
                    else v.isoformat() if isinstance(v, date) else str(v)
                )
            )
        )
        for k, v in row.items()
    }


def model_history(rows, equipment_id):
    from scripts.build_monthly_training_table import parse_timestamp

    item = next(
        (
            model_record(r)
            for r in rows["equipements"]
            if r["equipement_id"] == equipment_id
        ),
        None,
    )
    if item is None:
        raise ValueError(f"Unknown equipment_id: {equipment_id}.")
    if item["dans_perimetre_prediction"] != "Oui":
        raise ValueError(
            f"{equipment_id} is excluded because dans_perimetre_prediction is not 'Oui'."
        )
    events = [
        model_record(r)
        for r in rows["interventions"]
        if r["equipement_id"] == equipment_id
    ]
    ids = {r["demande_id_liee"] for r in events if r["demande_id_liee"]}
    requests = [model_record(r) for r in rows["demandes"] if r["demande_id"] in ids]
    for series, field in ((events, "date_intervention"), (requests, "date_creation")):
        for r in series:
            r["_timestamp"] = parse_timestamp(r[field])
        series.sort(key=lambda r: r["_timestamp"])
    return item, events, requests


def export_snapshot(folder: Path, user_id=None):
    import csv, json
    from scripts.schema import IMPORT_SOURCES

    with connection(user_id, snapshot=True) as conn:
        data = source_rows(
            conn, ["equipements", "interventions", "demandes", "prix_interventions"]
        )
        rev = revision(conn)
    folder.mkdir(parents=True, exist_ok=True)
    for table, rows in data.items():
        filename, _, cols = IMPORT_SOURCES[table]
        with (folder / filename).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=cols.split())
            writer.writeheader()
            writer.writerows(model_record(r) for r in rows)
    (folder / "snapshot.json").write_text(
        json.dumps({"revision": rev, "rows": {t: len(r) for t, r in data.items()}}),
        encoding="utf-8",
    )
    return rev
