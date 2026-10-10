"""Inspections partagées avec verrou optimiste et historique append-only."""

from datetime import date, datetime
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from scripts.database import safe

FIELDS = {
    "equipmentId": "equipement_id",
    "status": "statut",
    "owner": "responsable",
    "providerId": "prestataire_id",
    "objective": "objectif",
    "desiredDate": "date_souhaitee",
    "confirmedDate": "date_confirmee",
    "reviewDate": "date_reexamen",
    "visitedDate": "date_visite",
    "outcome": "resultat",
    "note": "note",
    "conclusion": "conclusion",
    "externalReference": "reference_externe",
    "cycleStartedAt": "debut_cycle",
    "scoreVersion": "version_score",
    "createdAt": "cree_le",
    "updatedAt": "modifie_le",
    "version": "version",
}
DATE_FIELDS = {"desiredDate", "confirmedDate", "reviewDate", "visitedDate"}
EMPTY_FIELDS = DATE_FIELDS | {"cycleStartedAt", "providerId"}
STATUSES = {
    "preparing": "À préparer",
    "planned": "Planifiée",
    "completed": "Réalisée",
    "closed": "Clôturée",
    "review": "À réexaminer",
}


def load_workspace(conn):
    rows = conn.execute(
        "select * from public.inspections order by cree_le,id"
    ).fetchall()
    events = conn.execute(
        "select * from public.historique_inspections order by date_evenement,id"
    ).fetchall()
    inspections = []
    for row in rows:
        item = {"id": row["id"], **{field: row[col] for field, col in FIELDS.items()}}
        for field in DATE_FIELDS | {"providerId"}:
            item[field] = item[field] or ""
        item["history"] = [
            {
                "date": e["date_evenement"],
                "label": e["libelle"],
                "note": e["note"],
                "status": e["statut"],
                "outcome": e["resultat"],
            }
            for e in events
            if e["inspection_id"] == row["id"]
        ]
        inspections.append(item)
    feedback = [
        {
            "id": r["id"],
            "equipmentId": r["equipement_id"],
            "subject": r["sujet"],
            "comment": r["commentaire"],
            "author": r["auteur_nom"],
            "createdAt": r["cree_le"],
        }
        for r in conn.execute(
            "select * from public.signalements order by cree_le,id"
        ).fetchall()
    ]
    return safe({"actions": inspections, "feedback": feedback})


def validate_action(action):
    if action.get("status") not in STATUSES:
        raise HTTPException(422, "État de dossier inconnu.")
    for field in ("id", "equipmentId", "owner", "objective"):
        if not isinstance(action.get(field), str) or not action[field].strip():
            raise HTTPException(422, f"{field} est obligatoire.")
    status = action["status"]
    if status == "planned" and not action.get("confirmedDate"):
        raise HTTPException(422, "Une date confirmée est nécessaire.")
    if status in ("completed", "closed") and (
        not action.get("visitedDate") or not action.get("outcome", "").strip()
    ):
        raise HTTPException(422, "Renseignez le passage et son résultat.")
    if status == "closed" and not action.get("conclusion", "").strip():
        raise HTTPException(422, "Une conclusion est nécessaire.")
    if status == "review" and not action.get("reviewDate"):
        raise HTTPException(422, "Une date de réexamen est nécessaire.")
    for field in DATE_FIELDS:
        if action.get(field):
            try:
                parsed = date.fromisoformat(action[field])
                if parsed.isoformat() != action[field]:
                    raise ValueError()
            except (ValueError, TypeError):
                raise HTTPException(422, f"{field} : date invalide.")
    if (
        action.get("visitedDate")
        and date.fromisoformat(action["visitedDate"])
        > datetime.now(ZoneInfo("Europe/Paris")).date()
    ):
        raise HTTPException(422, "Une visite réalisée ne peut pas être dans le futur.")


def save_action(conn, action, user_id, *, recover=False):
    validate_action(action)
    old = conn.execute(
        "select * from public.inspections where id=%s for update", [action["id"]]
    ).fetchone()
    if recover and old:
        return False
    if old and action.get("version") != old["version"]:
        raise HTTPException(
            409, "Ce dossier a changé. Rechargez les données avant de l’enregistrer."
        )
    if not old and not recover and action.get("version") not in (None, 0):
        raise HTTPException(409, "Ce dossier a été supprimé. Rechargez les données.")
    columns = []
    values = []
    for field, column in FIELDS.items():
        if field in ("createdAt", "updatedAt", "version"):
            continue
        value = action.get(field)
        if value in ("", None) and field in EMPTY_FIELDS:
            value = None
        if value is None and field not in EMPTY_FIELDS:
            value = ""
        columns.append(column)
        values.append(value)
    if old:
        conn.execute(
            "update public.inspections set "
            + ",".join(f"{c}=%s" for c in columns)
            + ",version=version+1,modifie_le=now() where id=%s",
            [*values, action["id"]],
        )
    else:
        if recover:
            for field, column in [
                ("createdAt", "cree_le"),
                ("updatedAt", "modifie_le"),
            ]:
                if action.get(field):
                    columns.append(column)
                    values.append(action[field])
        conn.execute(
            "insert into public.inspections(id,"
            + ",".join(columns)
            + ",auteur) values("
            + ",".join(["%s"] * (len(columns) + 2))
            + ")",
            [action["id"], *values, user_id],
        )
    if recover:
        for event in action.get("history", []):
            conn.execute(
                "insert into public.historique_inspections(inspection_id,date_evenement,libelle,note,statut,resultat,auteur) values(%s,%s,%s,%s,%s,%s,%s)",
                [
                    action["id"],
                    event["date"],
                    event["label"],
                    event.get("note", ""),
                    event.get("status"),
                    event.get("outcome"),
                    user_id,
                ],
            )
    conn.execute(
        "insert into public.historique_inspections(inspection_id,libelle,note,statut,resultat,auteur) values(%s,%s,%s,%s,%s,%s)",
        [
            action["id"],
            (
                "Données locales récupérées"
                if recover
                else "Décision enregistrée" if old else "Dossier créé"
            )
            + " · "
            + STATUSES[action["status"]],
            action.get("note") or action.get("conclusion") or action["objective"],
            action["status"],
            action.get("outcome", ""),
            user_id,
        ],
    )
    return True


def validate_feedback(item):
    for field in ("id", "equipmentId", "subject", "comment", "author"):
        if not isinstance(item.get(field), str) or not item[field].strip():
            raise HTTPException(422, f"{field} est obligatoire.")


def save_feedback(conn, item, user_id, *, recover=False):
    validate_feedback(item)
    if recover and item.get("createdAt"):
        conn.execute(
            "insert into public.signalements(id,equipement_id,sujet,commentaire,auteur_nom,auteur,cree_le) values(%s,%s,%s,%s,%s,%s,%s) on conflict(id) do nothing",
            [
                item["id"],
                item["equipmentId"],
                item["subject"],
                item["comment"],
                item["author"],
                user_id,
                item["createdAt"],
            ],
        )
    else:
        conn.execute(
            "insert into public.signalements(id,equipement_id,sujet,commentaire,auteur_nom,auteur) values(%s,%s,%s,%s,%s,%s) on conflict(id) do nothing",
            [
                item["id"],
                item["equipmentId"],
                item["subject"],
                item["comment"],
                item["author"],
                user_id,
            ],
        )
