"""Aide aux arbitrages : faits comptables, tarifs de simulation et plans partagés."""

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
import unicodedata

from fastapi import HTTPException
from scripts.catalog import catalog
from scripts.database import safe

TABLES = [
    "residences",
    "batiments",
    "logements",
    "equipements",
    "prestataires",
    "interventions",
    "commandes",
    "investissements",
    "familles",
    "prix_interventions",
]
DEFAULT_RENOVATION_BUDGET = 1_500_000


def number(value):
    return float(value) if value is not None else None


def normalized(value):
    return "".join(
        c
        for c in unicodedata.normalize("NFD", value.lower())
        if unicodedata.category(c) != "Mn"
    )


def operation_families(label):
    """Rapprochement de sujet, jamais une preuve qu'un appareil est inclus."""
    text = normalized(label)
    result = []
    if "chaufferie" in text:
        result.append("chaufferie_collective")
    elif "chaudiere" in text:
        result.append("chaudiere_gaz_individuelle")
    if "pompe" in text and "chaleur" in text:
        result.append("pompe_a_chaleur")
    if "ballon" in text:
        # Un passage de l'électrique au thermodynamique concerne les appareils existants.
        result.append(
            "ballon_ecs_electrique"
            if "electrique" in text
            else (
                "ballon_thermodynamique"
                if "thermodynamique" in text
                else "ballon_ecs_electrique"
            )
        )
    if "convecteur" in text:
        result.append("convecteurs_electriques")
    if "ascenseur" in text:
        result.append("ascenseur")
    if "vmc" in text:
        result.extend(["caisson_vmc", "bouches_vmc"])
    if "ecs solaire" in text:
        result.append("production_ecs_solaire")
    if "porte de hall" in text:
        result.append("porte_hall_interphonie")
    return result


def operation_buildings(perimeter, buildings):
    """Une résidence entière est connue ; un lot de N logements reste non attribué."""
    if normalized(perimeter) == "residence":
        return None
    matches = [b for b in buildings if b.split("-")[-1] in perimeter.split()]
    # Le kit contient aussi des intervalles explicites de cages : C1-C3.
    if not matches and "-" in perimeter:
        import re

        match = re.search(r"\b([A-Z])(\d+)-\1(\d+)\b", perimeter)
        if match:
            cages = {f"{match[1]}{i}" for i in range(int(match[2]), int(match[3]) + 1)}
            matches = [b for b in buildings if b.split("-")[-1] in cages]
    return set(matches) if matches else set()


def finance_by_location(orders, snapshot):
    recent = snapshot.date() - timedelta(days=365)
    by_residence, by_housing = defaultdict(list), defaultdict(list)
    for row in orders:
        if not row["date_commande"] or row["date_commande"] >= snapshot.date():
            continue
        if "annul" in normalized(row.get("statut") or ""):
            continue
        by_residence[row["residence_id"]].append(row)
        if row["logement_id"]:
            by_housing[row["logement_id"]].append(row)

    def summarize(rows):
        invoices = [
            r
            for r in rows
            if r["date_facture"]
            and recent <= r["date_facture"] < snapshot.date()
            and r["montant_facture_ttc"] is not None
        ]
        outstanding = []
        for r in rows:
            if r["montant_ttc"] is None:
                continue
            billed = (
                r["montant_facture_ttc"]
                if r["date_facture"]
                and r["date_facture"] < snapshot.date()
                and r["montant_facture_ttc"] is not None
                else Decimal(0)
            )
            outstanding.append(
                max(Decimal(0), Decimal(str(r["montant_ttc"])) - Decimal(str(billed)))
            )
        return {
            "billed12m": round(
                sum(float(r["montant_facture_ttc"]) for r in invoices), 2
            ),
            "invoiceCount12m": len(invoices),
            "outstanding": round(sum(outstanding), 2),
            "orderCount": len(rows),
        }

    return (
        {k: summarize(v) for k, v in by_residence.items()},
        {k: summarize(v) for k, v in by_housing.items()},
    )


def overview(rows, snapshot, revision, score_result, symptom_rows):
    cat = catalog(rows, snapshot, revision)
    equipment = cat["equipment"]
    families = {r["famille"]: r for r in rows["familles"]}
    prices = {
        (r["famille"], r["type_intervention"], r["type_panne"]): number(r["prix"])
        for r in rows["prix_interventions"]
    }
    events = defaultdict(list)
    for r in rows["interventions"]:
        if r["date_intervention"] < snapshot:
            events[r["equipement_id"]].append(r)
    scores = score_result["scores"]
    ranks = {
        id_: i + 1
        for i, (id_, _) in enumerate(
            sorted(scores.items(), key=lambda r: (-r[1], r[0]))
        )
    }
    cut = max(1, (len(ranks) + 9) // 10)
    finance, housing_finance = finance_by_location(rows["commandes"], snapshot)
    symptoms = {r["equipement_id"]: r["types_pannes"] for r in symptom_rows}
    operations = []
    for row in rows["investissements"]:
        if (
            row["date_inscription_demande"]
            and row["date_inscription_demande"] >= snapshot.date()
        ):
            continue
        building_ids = [
            b["batiment_id"]
            for b in rows["batiments"]
            if b["residence_id"] == row["residence_id"]
        ]
        scopes = operation_buildings(row["perimetre"] or "", building_ids)
        affected = [
            e
            for e in equipment
            if e["residenceId"] == row["residence_id"]
            and (scopes is None or e["buildingId"] in scopes)
        ]
        priorities = [e for e in affected if ranks.get(e["id"], cut + 1) <= cut]
        count = row["nb_logements_concernes"]
        operations.append(
            {
                "id": row["operation_id"],
                "residenceId": row["residence_id"],
                "label": row["type_operation"],
                "perimeter": row["perimetre"],
                "desiredYear": row["annee_souhaitee"],
                "cost": number(row["cout_estime_ttc"]),
                "energyGain": number(row["gain_conso_ep_estime_kwh_m2_an"]),
                "housingCount": count,
                "costPerHousing": (
                    round(float(row["cout_estime_ttc"]) / count, 2)
                    if count and row["cout_estime_ttc"] is not None
                    else None
                ),
                "reason": row["origine_demande"],
                "status": row["statut"],
                "priorityEquipmentCount": (
                    len(priorities) if scopes is None or scopes else None
                ),
                "families": operation_families(row["type_operation"]),
                "buildingIds": None if scopes is None else sorted(scopes),
                "chronologicalRank": row["rang_actuel_chronologique"],
            }
        )
    comparisons = []
    recent = snapshot - timedelta(days=365)
    for e in equipment:
        start = (
            datetime.fromisoformat(e["cycleStartedAt"]) if e["cycleStartedAt"] else None
        )
        repairs = [
            r
            for r in events[e["id"]]
            if start
            and r["date_intervention"] >= start
            and r["date_intervention"] >= recent
            and r["type_intervention"] == "Dépannage"
        ]
        costs = [
            prices.get((e["family"], "Dépannage", r["symptome"] or "Non renseigné"))
            for r in repairs
        ]
        complete = bool(start) and all(c is not None for c in costs)
        simulated = round(sum(costs), 2) if complete else None
        family = families.get(e["family"], {})
        low, high = (
            number(family.get(k))
            for k in ("cout_remplacement_min_ttc", "cout_remplacement_max_ttc")
        )
        coordinated = [
            o["id"]
            for o in operations
            if o["residenceId"] == e["residenceId"]
            and e["family"] in o["families"]
            and (
                o["buildingIds"] is None
                or not o["buildingIds"]
                or e["buildingId"] in o["buildingIds"]
            )
        ]
        types = symptoms.get(e["id"]) or {}
        comparisons.append(
            {
                "equipmentId": e["id"],
                "label": e["label"],
                "family": e["family"],
                "residenceId": e["residenceId"],
                "housingId": e["housingId"],
                "buildingId": e["buildingId"],
                "providerId": e["providerId"],
                "collective": e["collective"],
                "buildingHousingCount": e["buildingHousingCount"],
                "underContract": e["underContract"],
                "rank": ranks.get(e["id"]),
                "priority": ranks.get(e["id"], cut + 1) <= cut,
                "cycleKnown": bool(start),
                "repairCount12m": len(repairs) if start else None,
                "pricedRepairCount12m": sum(c is not None for c in costs),
                "simulatedRepairCost12m": simulated,
                "replacementMin": low,
                "replacementMax": high,
                "repairReplacementRatioMin": (
                    round(simulated / high, 4)
                    if simulated is not None and high and high > 0
                    else None
                ),
                "repairReplacementRatioMax": (
                    round(simulated / low, 4)
                    if simulated is not None and low and low > 0
                    else None
                ),
                "firstFailureCost": types.get("expected_price_if_failure"),
                "weightedFirstFailureCost": types.get("expected_cost_within_horizon"),
                "financeContext": (
                    housing_finance.get(e["housingId"])
                    if e["housingId"]
                    else finance.get(e["residenceId"])
                ),
                "financeScope": "logement" if e["housingId"] else "résidence",
                "operationIds": coordinated,
            }
        )
    comparisons.sort(
        key=lambda e: (
            -(e["repairCount12m"] or 0),
            e["rank"] or float("inf"),
            e["equipmentId"],
        )
    )
    groups = defaultdict(list)
    for e in comparisons:
        if e["priority"] and e["providerId"]:
            groups[(e["residenceId"], e["providerId"])].append(e["equipmentId"])
    return safe(
        {
            "revision": revision,
            "referenceDate": snapshot.date(),
            "periodStart": recent.date(),
            "result": {k: v for k, v in score_result.items() if k != "scores"},
            "equipment": comparisons,
            "operations": sorted(
                operations, key=lambda o: o["chronologicalRank"] or 9999
            ),
            "residenceFinance": finance,
            "groups": [
                {
                    "residenceId": residence,
                    "providerId": provider,
                    "equipmentIds": ids,
                    "potentialVisitsCombined": len(ids) - 1,
                }
                for (residence, provider), ids in sorted(groups.items())
                if len(ids) > 1
            ],
        }
    )


def load_plan(conn, year):
    row = conn.execute("select * from public.budgets where annee=%s", [year]).fetchone()
    if not row:
        return {
            "year": year,
            "version": 0,
            "renovationBudget": DEFAULT_RENOVATION_BUDGET,
            "maintenanceBudget": None,
            "operationIds": [],
            "isDefault": True,
        }
    return {
        "year": year,
        "version": row["version"],
        "renovationBudget": number(row["renovation"]),
        "maintenanceBudget": number(row["maintenance"]),
        "isDefault": False,
        "operationIds": [
            r["operation_id"]
            for r in conn.execute(
                "select operation_id from public.operations_retenues where annee=%s order by operation_id",
                [year],
            ).fetchall()
        ],
    }


def save_plan(conn, year, plan, user_id):
    # Le même verrou sérialise les imports et les décisions fondées sur ces données.
    conn.execute("select pg_advisory_xact_lock(821906)")
    from scripts.database import revision

    if plan.sourceRevision != revision(conn):
        raise HTTPException(
            409, "Les données ont changé. Rechargez les arbitrages avant d’enregistrer."
        )
    old = conn.execute(
        "select version from public.budgets where annee=%s for update", [year]
    ).fetchone()
    if plan.version != (old["version"] if old else 0):
        raise HTTPException(
            409,
            "Ce budget a été modifié par un autre membre. Rechargez les arbitrages.",
        )
    if len(set(plan.operationIds)) != len(plan.operationIds):
        raise HTTPException(422, "Une opération apparaît plusieurs fois.")
    operations = conn.execute(
        "select operation_id,cout_estime_ttc from public.investissements where operation_id=any(%s)",
        [plan.operationIds],
    ).fetchall()
    if len(operations) != len(plan.operationIds):
        raise HTTPException(422, "Une opération est inconnue.")
    if any(
        r["cout_estime_ttc"] is None or r["cout_estime_ttc"] < 0 for r in operations
    ):
        raise HTTPException(422, "Un coût d’opération manque ou est invalide.")
    total = sum(r["cout_estime_ttc"] for r in operations)
    if total > plan.renovationBudget:
        raise HTTPException(422, "La sélection dépasse l’enveloppe de rénovation.")
    conn.execute(
        "insert into public.budgets(annee,renovation,maintenance,auteur) values(%s,%s,%s,%s) "
        "on conflict(annee) do update set renovation=excluded.renovation,maintenance=excluded.maintenance,auteur=excluded.auteur,version=budgets.version+1,modifie_le=now()",
        [year, plan.renovationBudget, plan.maintenanceBudget, user_id],
    )
    conn.execute("delete from public.operations_retenues where annee=%s", [year])
    for id_ in plan.operationIds:
        conn.execute(
            "insert into public.operations_retenues(annee,operation_id) values(%s,%s)",
            [year, id_],
        )
    return load_plan(conn, year)
