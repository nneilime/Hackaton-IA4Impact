"""Adaptateur métier de la base vers les types existants du front."""

from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta
from scripts.database import safe

# Coordonnées de démonstration existantes, distinctes des données sources.
GEO = {
    "RES-A": (43.5615, 1.4642, "Toulouse - Rangueil / Pech-David"),
    "RES-B": (43.6348, 1.3862, "Blagnac - Grand Noble"),
    "RES-C": (43.5746, 1.4021, "Toulouse - Reynerie / Mirail"),
    "RES-D": (43.6264, 1.4883, "Balma - Gramont"),
    "RES-E": (43.5992, 1.4115, "Toulouse - La Cartoucherie"),
    "RES-F": (43.6118, 1.3347, "Colomiers - Centre"),
    "RES-G": (43.5828, 1.4446, "Toulouse - Saint-Agne / Empalot"),
    "RES-H": (43.5442, 1.4745, "Ramonville-Saint-Agne"),
}


def catalog(rows, snapshot: datetime, rev):
    events = defaultdict(list)
    for r in rows["interventions"]:
        if r["date_intervention"] < snapshot:
            events[r["equipement_id"]].append(r)
    buildings = {r["batiment_id"]: r for r in rows["batiments"]}
    housing = {r["logement_id"]: r for r in rows["logements"]}
    equipment = []
    for r in rows["equipements"]:
        history = sorted(
            events[r["equipement_id"]],
            key=lambda e: (e["date_intervention"], e["intervention_id"]),
            reverse=True,
        )
        pose = r["date_pose"]
        replacements = [
            e
            for e in history
            if e["type_intervention"] == "Remplacement"
            and e["date_intervention"].date() == pose
        ]
        start = (
            replacements[0]["date_intervention"]
            if replacements
            else (
                datetime.combine(pose, datetime.min.time())
                if pose and pose < snapshot.date()
                else None
            )
        )
        recent = [
            e
            for e in history
            if start
            and e["date_intervention"] >= start
            and e["date_intervention"] >= snapshot - timedelta(days=365)
        ]
        age = (
            (
                snapshot
                - timedelta(microseconds=1)
                - datetime.combine(pose, datetime.min.time())
            ).total_seconds()
            / (365.25 * 86400)
            if pose and pose < snapshot.date()
            else None
        )
        note = next(
            (e for e in recent if e["commentaire_technicien"] or e["symptome"]), None
        )
        equipment.append(
            {
                "id": r["equipement_id"],
                "family": r["famille"],
                "label": r["libelle_famille"],
                "residenceId": r["residence_id"],
                "buildingId": r["batiment_id"],
                "housingId": r["logement_id"],
                "collective": r["niveau_rattachement"] == "Bâtiment (parties communes)",
                "installedAt": pose,
                "installationOrigin": r["origine_date_pose"],
                "cycleStartedAt": start,
                "ageYears": age,
                "referenceLifeYears": r["duree_vie_reference_ans"],
                "underContract": r["sous_contrat_entretien"],
                "annualVisit": r["visite_annuelle_prevue"],
                "providerId": r["prestataire_id"] or "",
                "inScope": r["dans_perimetre_prediction"],
                "buildingHousingCount": buildings[r["batiment_id"]]["nb_logements"],
                "recentRepairCount": sum(
                    e["type_intervention"] == "Dépannage" for e in recent
                ),
                "recentAnomalyCount": sum(
                    e["resultat"] == "Anomalie constatée" for e in recent
                ),
                "latestObservation": (
                    {
                        "id": note["intervention_id"],
                        "text": note["commentaire_technicien"] or note["symptome"],
                        "date": note["date_intervention"],
                    }
                    if note
                    else None
                ),
                "needsVerification": age is None
                or "hypoth" in (r["origine_date_pose"] or "").lower(),
                "housingDpe": housing.get(r["logement_id"], {}).get(
                    "dpe_etiquette_globale"
                ),
            }
        )
    residences = []
    for r in rows["residences"]:
        lat, lng, district = GEO.get(r["residence_id"], (None, None, None))
        residences.append(
            {
                "id": r["residence_id"],
                "name": r["nom"],
                "housingCount": r["nb_logements"],
                "buildingCount": r["nb_batiments"],
                "constructionYear": r["annee_construction"],
                "energyHeating": r["energie_chauffage"],
                "heatingType": r["type_chauffage"],
                "heatingGenerator": r["generateur_chauffage"],
                "ecsProduction": r["production_ecs"],
                "ventilation": r["ventilation"],
                "dpeTag": r["etiquette_dpe_majoritaire"],
                "consoEp": float(r["conso_ep_moyenne_kwh_m2_an"] or 0),
                "ges": float(r["ges_moyen_kgco2_m2_an"] or 0),
                "lat": lat,
                "lng": lng,
                "district": district,
            }
        )
    housings = []
    for h in rows["logements"]:
        housings.append(
            {
                "id": h["logement_id"],
                "buildingId": h["batiment_id"],
                "residenceId": h["residence_id"],
                "typology": h["typologie"],
                "area": float(h["surface_habitable_m2"] or 0),
                "floor": h["etage"],
                "dpeEnergy": h["dpe_etiquette_energie"],
                "dpeGes": h["dpe_etiquette_ges"],
                "dpeGlobal": h["dpe_etiquette_globale"],
                "consoEp": float(h["dpe_conso_ep_kwh_m2_an"] or 0),
                "ges": float(h["dpe_ges_kgco2_m2_an"] or 0),
                "tenantTurnover": h["nb_changements_locataire_2018_2025"],
                "occupancyStatus": h["statut_occupation"],
            }
        )
    return safe(
        {
            "snapshotDate": (snapshot - timedelta(days=1)).date(),
            "revision": rev,
            "equipment": equipment,
            "residences": residences,
            "housings": housings,
            "providers": [
                {"id": r["prestataire_id"], "name": r["nom"], "domain": r["domaine"]}
                for r in rows["prestataires"]
            ],
            "baselineScores": {},
        }
    )


def history(conn, equipment_id, snapshot):
    item = conn.execute(
        "select * from public.equipements where equipement_id=%s", [equipment_id]
    ).fetchone()
    if not item:
        raise KeyError("Équipement introuvable.")
    events = conn.execute(
        "select * from public.interventions where equipement_id=%s and date_intervention<%s order by date_intervention,intervention_id",
        [equipment_id, snapshot],
    ).fetchall()
    linked = [e["demande_id_liee"] for e in events if e["demande_id_liee"]]
    requests = conn.execute(
        "select * from public.demandes where date_creation<%s and (demande_id=any(%s) or (logement_id=%s and parties='Privatives') or (batiment_id=%s and parties='Communes'))",
        [snapshot, linked, item["logement_id"], item["batiment_id"]],
    ).fetchall()
    observations = conn.execute(
        "select * from public.observations where equipement_id=%s", [equipment_id]
    ).fetchall()
    observations = [
        r
        for r in observations
        if datetime(r["annee"], r["trimestre"] * 3, 28) < snapshot
    ]
    return safe(
        {
            "events": {
                equipment_id: [
                    {
                        "id": e["intervention_id"],
                        "date": e["date_intervention"],
                        "type": e["type_intervention"],
                        "symptom": e["symptome"] or "",
                        "severity": e["gravite"] or "",
                        "result": e["resultat"] or "",
                        "comment": e["commentaire_technicien"] or "",
                        "providerId": e["prestataire_id"],
                        "requestId": e["demande_id_liee"],
                    }
                    for e in events
                ]
            },
            "requests": [
                {
                    "id": r["demande_id"],
                    "date": r["date_creation"],
                    "closedAt": (
                        r["date_cloture"]
                        if r["date_cloture"] and r["date_cloture"] < snapshot
                        else None
                    ),
                    "housingId": r["logement_id"],
                    "buildingId": r["batiment_id"],
                    "parts": r["parties"],
                    "motif": r["motif"],
                    "subject": r["objet"],
                    "text": r["texte_demande"],
                }
                for r in requests
            ],
            "reports": {
                equipment_id: [
                    {
                        "id": r["id"],
                        "quarter": r["trimestre"],
                        "year": r["annee"],
                        "page": r["page"],
                        "text": r["texte"],
                        "url": r["url"],
                    }
                    for r in observations
                ]
            },
        }
    )
