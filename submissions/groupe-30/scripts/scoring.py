"""Calculs CatBoost par lot et publication atomique du classement."""

from __future__ import annotations
import hashlib
import json
import logging
import os
import threading
from collections import defaultdict
from datetime import datetime
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

from catboost import CatBoostClassifier
from psycopg.types.json import Jsonb
from scripts.database import connection, revision, source_rows, model_record
from scripts.predict_equipment import (
    build_feature_row,
    risk_level,
    recommended_action,
    prediction_frame,
    summarize_failure_types,
    unavailable_failure_types,
)
from scripts.schema import ROOT

HORIZONS = (90, 180, 365, 730)
MODEL_TABLES = ["equipements", "interventions", "demandes", "prix_interventions"]
LOCK = threading.Lock()


def artifacts_dir():
    return Path(os.getenv("PREDICTION_ARTIFACTS_DIR", str(ROOT / "artifacts")))


def model_version():
    digest = hashlib.sha256()
    for horizon in HORIZONS:
        for file in (f"catboost_failure_{horizon}d.cbm", "metrics.json"):
            digest.update((artifacts_dir() / f"{horizon}d" / file).read_bytes())
        folder = artifacts_dir() / f"{horizon}d" / "failure_types"
        manifest = folder / "manifest.json"
        if manifest.exists():
            digest.update(manifest.read_bytes())
            entries = json.loads(manifest.read_text(encoding="utf-8"))["families"]
            for file in sorted(
                {
                    e["model_file"]
                    for e in entries.values()
                    if e.get("status") == "trained" and "model_file" in e
                }
            ):
                digest.update(file.encode("utf-8"))
                digest.update((folder / file).read_bytes())
        else:
            digest.update(f"failure_types_{horizon}:unavailable".encode())
    return digest.hexdigest()[:20]


@lru_cache(maxsize=2)
def models(version):
    if model_version() != version:
        raise ValueError("Les artefacts ont changé depuis le lancement du calcul.")
    loaded = {}
    for horizon in HORIZONS:
        folder = artifacts_dir() / f"{horizon}d"
        model = CatBoostClassifier()
        model.load_model(folder / f"catboost_failure_{horizon}d.cbm")
        metrics = json.loads((folder / "metrics.json").read_text(encoding="utf-8"))
        loaded[horizon] = (model, float(metrics["selected_alert_threshold"]))
    if model_version() != version:
        raise ValueError("Les artefacts ont changé pendant leur chargement.")
    return loaded


@lru_cache(maxsize=2)
def failure_models(version):
    if model_version() != version:
        raise ValueError("Les artefacts ont changé depuis le lancement du calcul.")
    loaded = {}
    for horizon in HORIZONS:
        folder = artifacts_dir() / f"{horizon}d" / "failure_types"
        try:
            manifest = json.loads(
                (folder / "manifest.json").read_text(encoding="utf-8")
            )
        except FileNotFoundError:
            loaded[horizon] = {}
            continue
        families = {}
        for family, entry in manifest["families"].items():
            if entry["status"] != "trained":
                continue
            model = None
            if "constant_label" not in entry:
                model = CatBoostClassifier()
                model.load_model(folder / entry["model_file"])
            families[family] = (entry, model)
        loaded[horizon] = families
    if model_version() != version:
        raise ValueError("Les artefacts ont changé pendant leur chargement.")
    return loaded


def predict_rows(rows, snapshot, version=None, progress=lambda _: None):
    version = version or model_version()
    by_equipment = defaultdict(list)
    linked = defaultdict(set)
    requests = defaultdict(list)
    for raw in rows["interventions"]:
        e = model_record(raw)
        e["_timestamp"] = datetime.fromisoformat(e["date_intervention"])
        by_equipment[e["equipement_id"]].append(e)
        if e["demande_id_liee"]:
            linked[e["demande_id_liee"]].add(e["equipement_id"])
    for raw in rows["demandes"]:
        r = model_record(raw)
        r["_timestamp"] = datetime.fromisoformat(r["date_creation"])
        for equipment_id in linked[r["demande_id"]]:
            requests[equipment_id].append(r)
    for series in (by_equipment, requests):
        for events in series.values():
            events.sort(key=lambda e: e["_timestamp"])
    items = [
        model_record(r) for r in rows["equipements"] if r["dans_perimetre_prediction"]
    ]
    if not items:
        raise ValueError("Aucun équipement dans le périmètre.")
    features = [
        build_feature_row(
            i, by_equipment[i["equipement_id"]], requests[i["equipement_id"]], snapshot
        )
        for i in items
    ]
    prices = {
        (r["famille"], r["type_intervention"], r["type_panne"]): float(r["prix"])
        for r in rows.get("prix_interventions", [])
    }
    family_indices = defaultdict(list)
    for index, item in enumerate(items):
        family_indices[item["famille"]].append(index)
    symptoms = failure_models(version)
    result = [
        {
            "equipment_id": i["equipement_id"],
            "as_of_date": snapshot.date().isoformat(),
            "residence_id": i["residence_id"],
            "batiment_id": i["batiment_id"],
            "libelle_famille": i["libelle_famille"],
        }
        for i in items
    ]
    for index, (horizon, (model, threshold)) in enumerate(models(version).items()):
        probabilities = model.predict_proba(prediction_frame(model, features))[:, 1]
        for item, probability in zip(result, probabilities):
            score = round(float(probability), 6)
            item.update(
                {
                    f"failure_probability_{horizon}d": score,
                    f"alert_threshold_{horizon}d": threshold,
                    f"predicted_alert_{horizon}d": float(probability) >= threshold,
                    f"risk_level_{horizon}d": risk_level(float(probability), threshold),
                }
            )
            item[f"failure_types_{horizon}d"] = unavailable_failure_types()
        for family, indices in family_indices.items():
            if family not in symptoms[horizon]:
                continue
            entry, symptom_model = symptoms[horizon][family]
            if "constant_label" in entry:
                distributions = [[(entry["constant_label"], 1.0)] for _ in indices]
            else:
                conditional = symptom_model.predict_proba(
                    prediction_frame(symptom_model, [features[i] for i in indices])
                )
                labels = [json.loads(label) for label in symptom_model.classes_]
                distributions = [
                    list(zip(labels, map(float, values))) for values in conditional
                ]
            for i, distribution in zip(indices, distributions):
                result[i][f"failure_types_{horizon}d"] = summarize_failure_types(
                    distribution, family, float(probabilities[i]), prices
                )
        progress(25 + (index + 1) * 15)
    for item in result:
        item["recommended_action"] = recommended_action(
            *(item[f"predicted_alert_{h}d"] for h in HORIZONS)
        )
    return result


def schedule(user_id, date_reference):
    version = model_version()
    with connection(user_id) as conn:
        rev = revision(conn)
        existing = conn.execute(
            "select * from public.calculs where date_reference=%s and revision=%s and version_modele=%s and statut in ('en_attente','en_cours')",
            [date_reference, rev, version],
        ).fetchone()
        if existing:
            return str(existing["id"]), False
        run = conn.execute(
            "insert into public.calculs(auteur,date_reference,revision,version_modele,statut) values(%s,%s,%s,%s,'en_attente') on conflict do nothing returning id",
            [user_id, date_reference, rev, version],
        ).fetchone()
        if not run:
            run = conn.execute(
                "select id from public.calculs where date_reference=%s and revision=%s and version_modele=%s and statut in ('en_attente','en_cours')",
                [date_reference, rev, version],
            ).fetchone()
            return str(run["id"]), False
        return str(run["id"]), True


def run_job(run_id, user_id):
    # Un seul calcul actif par processus ; la base évite les doublons de requêtes.
    with LOCK:
        try:
            with connection(user_id) as conn:
                run = conn.execute(
                    "update public.calculs set statut='en_cours',progression=5 where id=%s and statut='en_attente' returning *",
                    [run_id],
                ).fetchone()
            if not run:
                return
            with connection(user_id, snapshot=True) as conn:
                rev = revision(conn)
                data = source_rows(conn, MODEL_TABLES)
            if rev != run["revision"]:
                with connection(user_id) as conn:
                    conn.execute(
                        "update public.calculs set statut='depasse',termine_le=now() where id=%s",
                        [run_id],
                    )
                next_id, created = schedule(user_id, run["date_reference"])
                if created:
                    threading.Thread(
                        target=run_job, args=(next_id, user_id), daemon=True
                    ).start()
                return

            def progress(value):
                with connection(user_id) as conn:
                    conn.execute(
                        "update public.calculs set progression=%s where id=%s",
                        [value, run_id],
                    )

            scores = predict_rows(
                data,
                datetime.combine(run["date_reference"], datetime.min.time()),
                run["version_modele"],
                progress,
            )
            with connection(user_id) as conn:
                conn.execute("select pg_advisory_xact_lock(821906)")
                stale = revision(conn) != rev
                with conn.cursor() as cursor:
                    cursor.executemany(
                        "insert into public.predictions(calcul_id,equipement_id,horizon_jours,score,seuil,alerte,niveau_risque,action_recommandee,types_pannes) values(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        [
                            (
                                run_id,
                                s["equipment_id"],
                                h,
                                s[f"failure_probability_{h}d"],
                                s[f"alert_threshold_{h}d"],
                                s[f"predicted_alert_{h}d"],
                                s[f"risk_level_{h}d"],
                                s["recommended_action"],
                                Jsonb(s[f"failure_types_{h}d"]),
                            )
                            for s in scores
                            for h in HORIZONS
                        ],
                    )
                conn.execute(
                    "update public.calculs set statut=%s,progression=100,nb_equipements=%s,termine_le=now() where id=%s",
                    ["depasse" if stale else "termine", len(scores), run_id],
                )
            if stale:
                next_id, created = schedule(user_id, run["date_reference"])
                if created:
                    threading.Thread(
                        target=run_job, args=(next_id, user_id), daemon=True
                    ).start()
        except Exception:
            logging.exception("Échec du calcul %s", run_id)
            try:
                with connection(user_id) as conn:
                    conn.execute(
                        "update public.calculs set statut='echec',erreur='Calcul interrompu ou modèles indisponibles. Relancez le calcul.',termine_le=now() where id=%s",
                        [run_id],
                    )
            except Exception:
                logging.exception("Impossible de journaliser le calcul")


def latest_result(conn, horizon, date_reference):
    rev = revision(conn)
    run = conn.execute(
        "select * from public.calculs where statut in ('termine','depasse') and date_reference=%s order by termine_le desc limit 1",
        [date_reference],
    ).fetchone()
    if not run:
        return {
            "scores": {},
            "metadata": {
                "label": "Aucun calcul disponible",
                "modelVersion": "indisponible",
                "referenceDate": date_reference.isoformat(),
                "horizonStart": date_reference.isoformat(),
                "horizonEndExclusive": (
                    date_reference + timedelta(days=horizon)
                ).isoformat(),
                "kind": "ranking_score",
                "importedAt": None,
            },
            "stale": False,
        }
    scores = conn.execute(
        "select equipement_id,score from public.predictions where calcul_id=%s and horizon_jours=%s",
        [run["id"], horizon],
    ).fetchall()
    return {
        "scores": {s["equipement_id"]: s["score"] for s in scores},
        "metadata": {
            "label": f"CatBoost · {horizon} jours",
            "modelVersion": run["version_modele"],
            "referenceDate": run["date_reference"].isoformat(),
            "horizonStart": run["date_reference"].isoformat(),
            "horizonEndExclusive": (
                run["date_reference"] + timedelta(days=horizon)
            ).isoformat(),
            "kind": "ranking_score",
            "importedAt": run["termine_le"].isoformat(),
        },
        "runId": str(run["id"]),
        "revision": run["revision"],
        "stale": run["revision"] != rev or run["statut"] == "depasse",
    }
