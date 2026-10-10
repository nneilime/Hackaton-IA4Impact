"""Scénario de démonstration complet, de bout en bout, via l'API (TestClient)."""
from .conftest import SCENARIO

MESSAGE_PRE = "Demande de pré-réservation transmise — confirmation en attente"


def test_scenario_complet(client):
    # 0. État de l'API : honnête sur les données et le mode
    sante = client.get("/api/sante").json()
    assert (sante["ok"], sante["mode"], sante["donnees"]) == (True, "demo", "demo")
    assert sante["source"] == "Démonstration" and sante["hypotheses"] == []

    # 1. Le prof décrit son projet : 7 champs extraits, gare de Foix trouvée seule, la date est demandée
    msgs = [{"role": "user", "content": SCENARIO}]
    r = client.post("/api/chat", json={"messages": msgs, "demande": None}).json()
    d = r["demande"]
    assert (d["niveau"], d["theme"], d["nb_eleves"], d["nb_accompagnateurs"]) == ("5e", "Moyen Âge", 42, 4)
    assert (d["duree"], d["heure_retour_max"]) == ("journee", "19:00")
    assert d["gare_depart"]["nom"] == "Foix"
    assert r["complete"] is False and d["champs_manquants"] == ["date"]
    assert any("12 novembre" in s for s in r["suggestions"])

    msgs += [{"role": "assistant", "content": r["reponse"]}, {"role": "user", "content": "Jeudi 12 novembre 2026"}]
    r = client.post("/api/chat", json={"messages": msgs, "demande": d}).json()
    assert r["complete"] is True and r["demande"]["date"] == "2026-11-12"
    demande = r["demande"]

    # 2. Trois destinations Moyen Âge, toutes du catalogue, hors commune de départ
    r = client.post("/api/destinations", json={"demande": demande})
    assert r.status_code == 200
    rep = r.json()
    dest = {x["commune"]: x for x in rep["destinations"]}
    assert set(dest) == {"Toulouse", "Carcassonne", "Albi"}
    assert dest["Toulouse"]["site_id"] in ("toulouse-saint-sernin", "toulouse-jacobins")
    assert dest["Carcassonne"]["site_id"] == "carcassonne-cite"
    assert dest["Albi"]["site_id"] == "albi-cite-episcopale"
    assert all(x["site_id"] != "foix-chateau" for x in rep["destinations"])
    assert "Château de Foix" in rep["message"]
    assert "type" in rep["message"]  # date hors grille : jour type annoncé
    # 3. Toulouse : direct, à pied, vert
    t = dest["Toulouse"]
    assert t["correspondances"] == 0 and t["acces_gare_site"]["mode"] == "pied"
    assert t["acces_gare_site"]["niveau"] == "vert" and t["niveau"] == "vert"
    # 4. Carcassonne : via Toulouse, gare loin de la Cité, bus urbain, orange
    c = dest["Carcassonne"]
    assert c["correspondances"] == 1
    assert c["acces_gare_site"]["mode"] == "urbain" and c["acces_gare_site"]["niveau"] == "orange"
    # Audit n°2 : le 12/11 le trajet de Carcassonne est bloqué (places) ; l'alternative d'un autre jour
    # ne doit plus relever l'indice affiché de la destination.
    assert c["niveau"] == "rouge" and c["indice_confiance"] <= 59
    assert dest["Albi"]["correspondances"] == 1

    # 5. Le premier train du matin est rouge (option d'un autre groupe), suivi de son alternative
    r = client.post("/api/trajets", json={"demande": demande, "site_id": "toulouse-saint-sernin"})
    assert r.status_code == 200
    props = r.json()["propositions"]
    rouge, alt = props[0], props[1]
    assert rouge["aller"]["segments"][0]["train"] == "871605" and rouge["aller"]["depart"] == "08:05"
    assert rouge["jauge_aller"] == {"capacite": 50, "sous_option": 10, "disponibles": 40,
                                    "groupes_positionnes": 1, "besoin": 46, "niveau": "rouge"}
    assert rouge["indice"]["niveau"] == "rouge" and rouge["est_alternative"] is False
    assert "Pas assez fiable" in rouge["explication_ia"]
    assert alt["est_alternative"] is True and alt["remplace"] == rouge["proposition_id"]
    assert alt["aller"]["segments"][0]["train"] == "871607"
    assert alt["indice"]["niveau"] == "vert" and alt["indice"]["score"] == 88
    assert alt["jauge_aller"]["disponibles"] == 50
    assert all(p["date"] == "2026-11-12" for p in props)

    # 6. Pré-réservation : jamais « confirmé » à ce stade
    r = client.post("/api/pre-reservations", json={"proposition_id": alt["proposition_id"],
                                                   "email": "enseignant@ac-toulouse.fr", "demande": demande})
    assert r.status_code == 200
    dossier = r.json()
    assert dossier["reference"] == "LIO-2026-000001"
    assert dossier["statut"] == "PRE_RESERVATION" and dossier["message"] == MESSAGE_PRE
    assert [e["statut"] for e in dossier["historique"]] == ["OPTION", "PRE_RESERVATION"]
    assert dossier["site"]["site_id"] == "toulouse-saint-sernin"
    assert dossier["proposition"]["proposition_id"] == alt["proposition_id"]
    assert "confirmé" not in dossier["message"].lower()
    assert client.get("/api/pre-reservations/LIO-2026-000001").json()["statut"] == "PRE_RESERVATION"

    # La pré-réservation pose une option : la jauge diminue pour les recherches suivantes
    r = client.post("/api/trajets", json={"demande": demande, "site_id": "toulouse-saint-sernin"}).json()
    j = {p["aller"]["segments"][0]["train"]: p["jauge_aller"] for p in r["propositions"]
         if p["date"] == "2026-11-12"}
    assert j["871607"]["disponibles"] == 4 and j["871607"]["groupes_positionnes"] == 1
    assert j["871607"]["niveau"] == "rouge"
    # Une autre pré-réservation reçoit la référence suivante
    autre = next(p for p in r["propositions"] if p["indice"]["niveau"] != "rouge")
    r2 = client.post("/api/pre-reservations", json={"proposition_id": autre["proposition_id"],
                                                    "email": "collegue@ac-toulouse.fr", "demande": demande})
    assert r2.status_code == 200 and r2.json()["reference"] == "LIO-2026-000002"
    # Une proposition rouge ne peut pas être pré-réservée
    rouge2 = next(p for p in r["propositions"] if p["indice"]["niveau"] == "rouge")
    r3 = client.post("/api/pre-reservations", json={"proposition_id": rouge2["proposition_id"],
                                                    "email": "x@y.fr", "demande": demande})
    assert r3.status_code == 409 and isinstance(r3.json()["detail"], str)

    # Réponse simulée du chargé de clientèle : seul chemin vers CONFIRMATION
    r = client.post("/api/pre-reservations/LIO-2026-000001/simuler-reponse", json={"decision": "confirmer"})
    assert r.json()["statut"] == "CONFIRMATION"
    r = client.post("/api/pre-reservations/LIO-2026-000001/simuler-reponse", json={"decision": "confirmer"})
    assert r.status_code == 409
    r = client.post("/api/pre-reservations/LIO-2026-000002/simuler-reponse",
                    json={"decision": "contre-proposition"})
    assert r.json()["statut"] == "CONTRE_PROPOSITION"

    # 7. Retour d'expérience : le critère satisfaction change, l'indice avec
    r = client.post("/api/retours", json={"reference": "LIO-2026-000001", "satisfaction": 5,
                                          "adaptation_train": 4, "acces_gare_site": 5, "confiance": 5,
                                          "recommande": True, "commentaire": "Trajet simple, élèves ravis."})
    assert r.status_code == 200
    ret = r.json()
    assert ret["ok"] is True and ret["indice_avant"] == 88 and ret["indice_apres"] == 93
    r = client.post("/api/trajets", json={"demande": demande, "site_id": "toulouse-saint-sernin"}).json()
    sat = next(c for c in r["propositions"][0]["indice"]["details"] if c["critere"] == "Satisfaction et coup de cœur")
    assert sat["points"] == 10 and "pas encore de retours" not in sat["explication"]


def test_alternative_autre_date_pour_carcassonne(client, demande_scenario):
    r = client.post("/api/trajets", json={"demande": demande_scenario.model_dump(), "site_id": "carcassonne-cite"})
    props = r.json()["propositions"]
    assert props[0]["indice"]["niveau"] == "rouge"
    assert props[1]["est_alternative"] and props[1]["date"] == "2026-11-13"
    assert "13 novembre" in props[1]["explication_ia"]


def test_erreurs_lisibles(client, demande_scenario):
    r = client.post("/api/retours", json={"reference": "LIO-2026-000001", "satisfaction": 6,
                                          "adaptation_train": 4, "acces_gare_site": 5, "confiance": 5,
                                          "recommande": True, "commentaire": ""})
    assert r.status_code == 422 and "satisfaction" in r.json()["detail"]
    r = client.get("/api/pre-reservations/LIO-2026-999999")
    assert r.status_code == 404 and "introuvable" in r.json()["detail"]
    r = client.post("/api/trajets", json={"demande": demande_scenario.model_dump(), "site_id": "inconnu"})
    assert r.status_code == 404
    r = client.post("/api/destinations", json={"demande": {"niveau": "5e"}})
    assert r.status_code == 422 and "nombre d'élèves" in r.json()["detail"]
    r = client.post("/api/pre-reservations", json={"proposition_id": "P-X", "email": "pas-un-email"})
    assert r.status_code == 422


def test_destination_souhaitee_en_premier(client, demande_scenario):
    d = demande_scenario.model_dump()
    d["destination_souhaitee"] = "Cité de Carcassonne"
    r = client.post("/api/destinations", json={"demande": d}).json()
    assert r["destinations"][0]["site_id"] == "carcassonne-cite"
