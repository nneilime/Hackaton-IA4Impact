"""Lecture stricte des CSV, aperçu et import transactionnel réutilisable."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from scripts.schema import (
    TABLES,
    SOURCES,
    IMPORT_SOURCES,
    BOOLS,
    INTS,
    NUMBERS,
    DATES,
    TIMESTAMPS,
    REQUIRED,
    RELATIONS,
)


def convert(column: str, raw: str):
    value = raw.strip()
    if value == "":
        return None
    if column in BOOLS:
        if value.lower() not in ("oui", "non"):
            raise ValueError("valeur attendue : Oui ou Non")
        return value.lower() == "oui"
    if column in INTS:
        return int(value)
    if column in NUMBERS:
        number = Decimal(value.replace(",", "."))
        if not number.is_finite():
            raise ValueError("nombre fini attendu")
        return str(number)
    if column in DATES:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError("date attendue : AAAA-MM-JJ")
        return value
    if column in TIMESTAMPS:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None:
            raise ValueError("heure locale sans fuseau attendue")
        return parsed.isoformat()
    return raw  # Conserver les textes métier sans réécriture.


def parse_files(files: list[tuple[str, bytes]]) -> dict:
    lot, reports, errors, locations = {}, [], [], {}
    seen = {}
    for name, payload in files:
        report = {
            "file": name,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "rows": 0,
        }
        reports.append(report)
        try:
            text = payload.decode("utf-8-sig")
            try:
                delimiter = csv.Sniffer().sniff(text[:8192], delimiters=",;").delimiter
            except csv.Error:
                delimiter = ","
            reader = csv.DictReader(
                io.StringIO(text, newline=""), delimiter=delimiter, strict=True
            )
            headers = [h.strip() for h in (reader.fieldnames or [])]
            matches = [
                table
                for table, (_, _, cols) in IMPORT_SOURCES.items()
                if set(headers) == set(cols.split())
            ]
            if len(headers) != len(set(headers)) or len(matches) != 1:
                nearest = max(
                    IMPORT_SOURCES, key=lambda t: len(set(headers) & set(TABLES[t][1]))
                )
                unknown = sorted(set(headers) - set(TABLES[nearest][1]))
                missing = sorted(set(TABLES[nearest][1]) - set(headers))
                raise ValueError(
                    f"Colonnes incompatibles avec {nearest} ; inconnues : {unknown}, manquantes : {missing}, ou en-têtes répétés."
                )
            table = matches[0]
            reader.fieldnames = headers
            report["table"] = table
            lot.setdefault(table, [])
            for raw in reader:
                if all(v is None or v == "" for v in raw.values()):
                    continue
                report["rows"] += 1
                line = reader.line_num
                try:
                    if None in raw or any(v is None for v in raw.values()):
                        raise ValueError("nombre de colonnes incorrect")
                    row = {col: convert(col, raw[col]) for col in headers}
                    keys = TABLES[table][0]
                    for col in set(keys) | REQUIRED.get(table, set()):
                        if row[col] is None:
                            raise ValueError(f"{col} est obligatoire")
                    if table == "equipements" and row["duree_vie_reference_ans"] <= 0:
                        raise ValueError("durée de vie strictement positive attendue")
                    if table == "prix_interventions" and Decimal(row["prix"]) < 0:
                        raise ValueError("prix positif ou nul attendu")
                    key = tuple(row[col] for col in keys)
                    if key in seen.setdefault(table, set()):
                        raise ValueError(f"identifiant répété : {key}")
                    seen[table].add(key)
                    lot[table].append(row)
                    locations.setdefault(table, []).append({"file": name, "line": line})
                except (ValueError, InvalidOperation) as error:
                    errors.append({"file": name, "line": line, "message": str(error)})
        except (UnicodeError, csv.Error, ValueError) as error:
            errors.append({"file": name, "line": 1, "message": str(error)})
    if not files:
        errors.append({"file": "", "line": 1, "message": "Choisissez au moins un CSV."})
    if not any(report["rows"] for report in reports) and not errors:
        errors.append(
            {"file": "", "line": 2, "message": "Le lot ne contient aucune donnée."}
        )
    return {"lot": lot, "files": reports, "errors": errors, "locations": locations}


def canonical(row: dict) -> dict:
    def value(col, val):
        if val is None:
            return None
        if col in NUMBERS:
            return Decimal(str(val))
        if isinstance(val, (date, datetime)):
            return val.isoformat()
        return val

    return {col: value(col, val) for col, val in row.items()}


def preview(parsed: dict, existing: dict[str, list[dict]]) -> dict:
    errors = list(parsed["errors"])
    merged = {}
    stats = {}
    for table, (keys, _) in TABLES.items():
        old = {tuple(r[k] for k in keys): canonical(r) for r in existing.get(table, [])}
        merged[table] = {k: dict(v) for k, v in old.items()}
        added = updated = unchanged = 0
        for row in parsed["lot"].get(table, []):
            row = canonical(row)
            key = tuple(row[k] for k in keys)
            if key not in old:
                added += 1
            elif old[key] != row:
                updated += 1
            else:
                unchanged += 1
            merged[table][key] = row
        stats[table] = {"added": added, "updated": updated, "unchanged": unchanged}
    supplied = {}
    for table, rows in parsed["lot"].items():
        for index, row in enumerate(rows):
            locations = parsed.get("locations", {}).get(table, [])
            supplied[table, tuple(row[k] for k in TABLES[table][0])] = (
                locations[index]
                if len(locations) > index
                else {"file": table, "line": index + 2}
            )
    for table, rows in merged.items():
        for row_key, row in rows.items():
            source = supplied.get((table, row_key), {"file": table, "line": None})

            # Vérifier aussi les enfants existants lors du déplacement d'un parent.
            def add_error(message, parent=None, parent_key=None):
                origin = (
                    source
                    if source["line"] is not None
                    else supplied.get((parent, parent_key), source)
                )
                errors.append({**origin, "message": f"{table} {row_key} : {message}"})

            for col, parent, key in RELATIONS.get(table, []):
                if row[col] is not None and (row[col],) not in merged[parent]:
                    add_error(
                        f"{col} : référence absente {row[col]} ({parent})",
                        parent,
                        (row[col],),
                    )
            for col, parent, key in [
                ("batiment_id", "batiments", "batiment_id"),
                ("logement_id", "logements", "logement_id"),
                ("equipement_id", "equipements", "equipement_id"),
            ]:
                if parent == table or not row.get(col):
                    continue
                target = merged[parent].get((row[col],))
                if target:
                    for place in ("residence_id", "batiment_id", "logement_id"):
                        if (
                            place in row
                            and place in target
                            and row[place] != target[place]
                        ):
                            add_error(
                                f"rattachement {place} incompatible avec {col}",
                                parent,
                                (row[col],),
                            )
            if (
                table == "demandes"
                and (row["motif"], row["parties"]) not in merged["motifs"]
            ):
                add_error("couple motif/parties absent du référentiel")
    file_reports = [
        {**f, "added": 0, "updated": 0, "unchanged": 0} for f in parsed["files"]
    ]
    for table, rows in parsed["lot"].items():
        keys = TABLES[table][0]
        old = {tuple(r[k] for k in keys): canonical(r) for r in existing.get(table, [])}
        for index, row in enumerate(rows):
            location = parsed.get("locations", {}).get(table, [])
            if index >= len(location):
                continue
            key = tuple(row[k] for k in keys)
            kind = (
                "added"
                if key not in old
                else "unchanged" if old[key] == canonical(row) else "updated"
            )
            next(f for f in file_reports if f["file"] == location[index]["file"])[
                kind
            ] += 1
    return {
        "files": file_reports,
        "tables": {t: stats[t] for t in parsed["lot"]},
        "errors": errors,
    }


def initial_lot() -> dict:
    from scripts.schema import DATA, ROOT

    result = parse_files(
        [(name, (DATA / name).read_bytes()) for name, _, _ in SOURCES.values()]
    )
    if result["errors"]:
        raise ValueError(result["errors"])
    from scripts.import_price_catalog import price_lot

    prices = price_lot()
    result["lot"].update(prices["lot"])
    result["locations"].update(prices["locations"])
    result["files"].extend(prices["files"])
    folder = ROOT / "analyses" / "sources_lisibles"
    with (folder / "xlsx_DICTIONNAIRE.csv").open(encoding="utf-8-sig", newline="") as f:
        result["lot"]["dictionnaire"] = [
            {
                "table_source": r[0],
                "colonne": r[1],
                "type": r[2],
                "description": r[3],
                "equivalent_reel": r[4],
            }
            for r in list(csv.reader(f))[1:]
        ]
    with (folder / "xlsx_HYPOTHESES.csv").open(encoding="utf-8-sig", newline="") as f:
        result["lot"]["hypotheses"] = [
            {
                "numero_ligne": i,
                "theme": r[0],
                "regle": r[1],
                "niveau_preuve": r[2],
                "source": r[3],
            }
            for i, r in enumerate(list(csv.reader(f))[1:], 2)
        ]
    with (folder / "xlsx_LISEZMOI.csv").open(encoding="utf-8-sig", newline="") as f:
        result["lot"]["documentation"] = [
            {"numero_ligne": i, **{f"colonne_{j+1}": v for j, v in enumerate(r)}}
            for i, r in enumerate(csv.reader(f), 1)
        ]
    for table, name, first_line in [
        ("dictionnaire", "xlsx_DICTIONNAIRE.csv", 2),
        ("hypotheses", "xlsx_HYPOTHESES.csv", 2),
        ("documentation", "xlsx_LISEZMOI.csv", 1),
    ]:
        result["files"].append(
            {
                "file": name,
                "table": table,
                "sha256": hashlib.sha256((folder / name).read_bytes()).hexdigest(),
                "rows": len(result["lot"][table]),
            }
        )
        result["locations"][table] = [
            {"file": name, "line": i + first_line}
            for i in range(len(result["lot"][table]))
        ]
    return result
