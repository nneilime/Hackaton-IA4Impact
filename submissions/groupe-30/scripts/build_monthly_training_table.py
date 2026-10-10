"""Build leakage-safe monthly snapshots for equipment failure prediction."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

if __package__ in (None, ""):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DEFAULT_DATA_DIR = (
    Path(__file__).resolve().parents[1]
    / "DATA 2 _le kit étudiants"
    / "BatIA_Kit_Hackathon"
    / "donnees"
)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FAILURE_TYPES = {"Dépannage", "Remplacement"}


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def parse_date(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def month_starts(start: datetime, end: datetime) -> Iterable[datetime]:
    current = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    while current <= last:
        yield current
        current = (
            current.replace(year=current.year + 1, month=1)
            if current.month == 12
            else current.replace(month=current.month + 1)
        )


def count_events(events: list[dict[str, str]], start: datetime, end: datetime) -> int:
    return sum(start <= event["_timestamp"] < end for event in events)


def count_matching(
    events: list[dict[str, str]],
    start: datetime,
    end: datetime,
    field: str,
    values: set[str],
) -> int:
    return sum(
        start <= event["_timestamp"] < end and event[field] in values
        for event in events
    )


def most_recent(
    events: list[dict[str, str]], snapshot: datetime
) -> dict[str, str] | None:
    historical = [event for event in events if event["_timestamp"] < snapshot]
    return historical[-1] if historical else None


def days_since(event: dict[str, str] | None, snapshot: datetime) -> int | None:
    return (snapshot - event["_timestamp"]).days if event else None


def age_days_as_of(
    equipment: dict[str, str],
    events: list[dict[str, str]],
    snapshot: datetime,
) -> int | None:
    """Return age only when the installation date was known at the snapshot."""
    replacement_dates = [
        event["_timestamp"].date()
        for event in events
        if event["_timestamp"] < snapshot
        and event["type_intervention"] == "Remplacement"
    ]
    known_pose_date = max(replacement_dates, default=None)

    recorded_pose_date = parse_date(equipment["date_pose"])
    if recorded_pose_date and recorded_pose_date <= snapshot.date():
        known_pose_date = max(
            [
                candidate
                for candidate in (known_pose_date, recorded_pose_date)
                if candidate
            ]
        )

    return (snapshot.date() - known_pose_date).days if known_pose_date else None


def failure_after(
    events: list[dict[str, str]], snapshot: datetime, horizon: timedelta
) -> dict[str, str] | None:
    deadline = snapshot + horizon
    return next(
        (
            event
            for event in events
            if snapshot <= event["_timestamp"] < deadline
            and event["type_intervention"] in FAILURE_TYPES
        ),
        None,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the monthly equipment training table for failure prediction."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing the source CSV files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Destination CSV. Defaults to a horizon-specific file in the project root.",
    )
    parser.add_argument(
        "--horizon-days",
        type=int,
        default=90,
        help="Prediction horizon for the failure target (default: 90).",
    )
    args = parser.parse_args()

    if args.horizon_days <= 0:
        raise ValueError("--horizon-days must be positive.")

    data_dir = args.data_dir.resolve()
    output = args.output or (
        PROJECT_ROOT / "table_apprentissage_mensuelle_90.csv"
        if args.horizon_days == 90
        else PROJECT_ROOT / f"table_apprentissage_mensuelle_{args.horizon_days}j.csv"
    )
    metadata_output = output.with_suffix(".metadata.json")

    equipment = read_csv(data_dir / "04_equipements.csv")
    interventions = read_csv(data_dir / "06_interventions.csv")
    tenant_requests = read_csv(data_dir / "05_demandes_locataires.csv")

    scoped_equipment = {
        row["equipement_id"]: row
        for row in equipment
        if row["dans_perimetre_prediction"].strip().lower() == "oui"
    }
    if not scoped_equipment:
        raise ValueError("No equipment has dans_perimetre_prediction set to 'Oui'.")

    events_by_equipment: dict[str, list[dict[str, str]]] = defaultdict(list)
    request_to_equipment: dict[str, set[str]] = defaultdict(set)
    for intervention in interventions:
        equipment_id = intervention["equipement_id"]
        if equipment_id not in scoped_equipment:
            continue
        intervention["_timestamp"] = parse_timestamp(intervention["date_intervention"])
        events_by_equipment[equipment_id].append(intervention)
        if intervention["demande_id_liee"]:
            request_to_equipment[intervention["demande_id_liee"]].add(equipment_id)

    for events in events_by_equipment.values():
        events.sort(key=lambda event: event["_timestamp"])

    requests_by_equipment: dict[str, list[dict[str, str]]] = defaultdict(list)
    for request in tenant_requests:
        if request["demande_id"] not in request_to_equipment:
            continue
        request["_timestamp"] = parse_timestamp(request["date_creation"])
        for equipment_id in request_to_equipment[request["demande_id"]]:
            requests_by_equipment[equipment_id].append(request)

    for requests in requests_by_equipment.values():
        requests.sort(key=lambda request: request["_timestamp"])

    all_event_dates = [
        event["_timestamp"]
        for events in events_by_equipment.values()
        for event in events
    ]
    if not all_event_dates:
        raise ValueError("No interventions are linked to in-scope equipment.")

    horizon = timedelta(days=args.horizon_days)
    snapshots = list(month_starts(min(all_event_dates), max(all_event_dates) - horizon))
    from scripts.predict_equipment import build_feature_row

    output.parent.mkdir(parents=True, exist_ok=True)

    columns = [
        "snapshot_date",
        "equipment_id",
        "residence_id",
        "batiment_id",
        "logement_id",
        "famille",
        "libelle_famille",
        "niveau_rattachement",
        "duree_vie_reference_ans",
        "equipment_age_days",
        "equipment_age_ratio_reference",
        "interventions_30d",
        "interventions_90d",
        "interventions_180d",
        "interventions_365d",
        "depannages_30d",
        "depannages_90d",
        "depannages_365d",
        "preventive_maintenance_365d",
        "replacements_365d",
        "critical_interventions_365d",
        "anomalies_365d",
        "uncompleted_visits_365d",
        "days_since_last_intervention",
        "days_since_last_failure",
        "days_since_last_preventive_maintenance",
        "last_intervention_type",
        "last_intervention_result",
        "last_intervention_gravity",
        "last_symptome",
        "linked_tenant_requests_90d",
        "reopened_tenant_requests_365d",
        "target_failure_within_horizon",
        "target_critical_failure_within_horizon",
        "target_failure_symptom",
        "target_failure_intervention",
        "days_to_next_failure",
    ]

    target_count = 0
    critical_target_count = 0
    with output.open("w", encoding="utf-8-sig", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=columns)
        writer.writeheader()
        for snapshot in snapshots:
            for equipment_id, item in scoped_equipment.items():
                events = events_by_equipment[equipment_id]
                requests = requests_by_equipment[equipment_id]
                next_failure = failure_after(events, snapshot, horizon)
                target_failure = int(next_failure is not None)
                target_critical = int(
                    next_failure is not None
                    and (
                        next_failure["gravite"] == "Arrêt total"
                        or next_failure["type_intervention"] == "Remplacement"
                    )
                )
                target_count += target_failure
                critical_target_count += target_critical

                writer.writerow(
                    {
                        "snapshot_date": snapshot.date().isoformat(),
                        "equipment_id": equipment_id,
                        "residence_id": item["residence_id"],
                        "batiment_id": item["batiment_id"],
                        "logement_id": item["logement_id"],
                        **build_feature_row(item, events, requests, snapshot),
                        "target_failure_within_horizon": target_failure,
                        "target_critical_failure_within_horizon": target_critical,
                        "target_failure_symptom": (
                            (next_failure["symptome"].strip() or "Non renseigné")
                            if next_failure
                            else ""
                        ),
                        "target_failure_intervention": (
                            next_failure["type_intervention"] if next_failure else ""
                        ),
                        "days_to_next_failure": (
                            (next_failure["_timestamp"] - snapshot).days
                            if next_failure
                            else ""
                        ),
                    }
                )

    metadata = {
        "source_directory": str(data_dir),
        "scope_filter": "04_equipements.csv.dans_perimetre_prediction == 'Oui'",
        "prediction_horizon_days": args.horizon_days,
        "target_definition": "At least one Dépannage or Remplacement in the prediction horizon.",
        "critical_target_definition": (
            "The first future failure is an Arrêt total or a Remplacement."
        ),
        "snapshot_count": len(snapshots),
        "snapshot_start": snapshots[0].date().isoformat(),
        "snapshot_end": snapshots[-1].date().isoformat(),
        "equipment_count": len(scoped_equipment),
        "row_count": len(snapshots) * len(scoped_equipment),
        "positive_target_count": target_count,
        "critical_target_count": critical_target_count,
        "leakage_controls": [
            "Only interventions and linked tenant requests strictly before each snapshot are features.",
            "The target uses only failures from the following prediction horizon.",
            "Current cumulative replacement counts are excluded.",
            "Equipment age is blank until its recorded installation date is known at the snapshot.",
        ],
    }
    metadata_output.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"Created {output}: {metadata['row_count']:,} rows, "
        f"{target_count:,} positive targets."
    )


if __name__ == "__main__":
    main()
