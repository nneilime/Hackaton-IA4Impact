from fastapi.testclient import TestClient

from app.main import app
from app.routing import DATA_DIR, Network, expected_wait, normalize

client = TestClient(app)  # jeu de données par défaut du site : data/train_lio (trains TER liO seulement)


def route(**params):
    return client.get("/route", params=params)


def code(response):
    return response.json()["detail"]["code"]


def test_helpers():
    assert normalize("Saint-Gaudéns") == "SAINT GAUDENS"
    assert expected_wait(16) == 30            # 16 passages sur 16 h -> un par heure -> 30 min d'attente moyenne
    assert expected_wait(0) == 120            # plafonné


def test_route_shape():
    body = route(**{"from": "Toulouse", "to": "Perpignan"}).json()
    assert body["from"] == "Toulouse Matabiau" and body["to"] == "Perpignan"
    legs = body["legs"]
    assert body["transfers"] == len(legs) - 1
    assert all(a["to_id"] == b["from_id"] for a, b in zip(legs, legs[1:]))       # les legs s'enchaînent
    assert all(leg["stops"][0] == leg["from_id"] and leg["stops"][-1] == leg["to_id"] for leg in legs)
    # un temps de passage par arrêt, croissant, le dernier = durée du leg
    assert all(len(l["times"]) == len(l["stops"]) and l["times"] == sorted(l["times"]) for l in legs)
    assert all(abs(l["times"][-1] - l["minutes"]) < 0.2 for l in legs)
    assert legs[0]["wait_minutes"] == 0
    total = body["access_minutes"] + body["egress_minutes"] + sum(l["minutes"] + l["wait_minutes"] for l in legs)
    assert abs(body["minutes"] - total) < 0.5


def test_direct_trains_are_found():
    # Le trou de l'ancienne base : il existe bien des TER directs Toulouse -> Narbonne -> Perpignan
    ter = route(**{"from": "Toulouse", "to": "Perpignan"}).json()
    assert ter["transfers"] == 0 and ter["legs"][0]["mode"] == "Train TER"
    places = {p["id"]: p["name"] for p in client.get("/places").json()["places"]}
    assert "Narbonne" in {places[s] for s in ter["legs"][0]["stops"]}
    assert route(**{"from": "Toulouse", "to": "Narbonne"}).json()["transfers"] == 0


def test_trains_only():
    # Le site ne charge que les trains liO : ni car, ni Intercités, ni TGV
    assert {m["id"] for m in client.get("/modes").json()["modes"]} == {"Train TER"}
    assert client.get("/networks").json()["networks"] == []
    assert {p["network"] for p in client.get("/places").json()["places"]} == {"sncf"}
    r = route(**{"from": "Toulouse", "to": "Lourdes"}).json()
    assert {leg["mode"] for leg in r["legs"]} == {"Train TER"}
    # Ganges n'est desservi que par un car liO
    assert code(route(**{"from": "Montpellier", "to": "Ganges"})) == "unknown_place"


# ── Base complète (data/) : cars liO, marche, réseaux départementaux, Intercités ────────────────────────────
full = Network(DATA_DIR)


def test_full_dataset_is_kept():
    assert {"Car liO", "INTERCITES", "TGV INOUI"} <= {m["id"] for m in full.modes()}
    assert full.route("Toulouse", "Lourdes")["legs"][0]["mode"] == "INTERCITES"


def test_lio_coaches_and_networks():
    # Ganges n'a pas de gare : seul le car liO 608 (réseau liO 34) y va depuis Montpellier
    r = full.route("Montpellier", "Ganges")
    rides = [l for l in r["legs"] if l["mode"] != "Marche"]
    assert [l["mode"] for l in rides] == ["Car liO"] and rides[0]["network"] == "liO 34"
    assert full.route("Montpellier", "Ganges", exclude={"Car liO"}) is None
    nets = {n["id"]: n for n in full.networks()}
    assert nets["liO 34"]["department"] == "Hérault" and "liO TIL" in nets and len(nets) == 14


def test_walk_between_coach_stop_and_station():
    # Le Vigan -> Montpellier sans le 608 : car 140 jusqu'à Nîmes, à pied jusqu'à la gare, puis train
    r = full.route("Le Vigan", "Montpellier Saint-Roch", exclude={"INTERCITES"}, exclude_networks={"liO 34"})
    modes = [l["mode"] for l in r["legs"]]
    assert "Car liO" in modes and "Marche" in modes and modes[-1] != "Car liO"
    walk = next(l for l in r["legs"] if l["mode"] == "Marche")
    assert walk["wait_minutes"] == 0 and walk["trips_per_day"] is None


def test_first_departure_must_run_on_weekdays():
    # Un car qui ne roule pas le jour de référence ne sert qu'en dernier recours
    r = full.route("Montpellier", "Rodez", exclude={"INTERCITES", "INTERCITES de nuit"})
    first_ride = next(leg for leg in r["legs"] if leg["mode"] != "Marche")
    assert first_ride["trips_per_day"] > 0


def test_city_prefers_station_named_after_it():
    r = route(**{"from": "Toulouse", "to": "Tarbes"}).json()
    assert r["from"] == "Toulouse Matabiau" and r["access_minutes"] == 0
    assert route(**{"from": "montpellier", "to": "NIMES"}).status_code == 200


def test_errors():
    assert code(route(**{"from": "Toulouse", "to": "Paris"})) == "unknown_place"
    assert code(route(**{"from": "Toulouse", "to": "Toulouse"})) == "same_place"
    assert code(route(**{"from": "Toulouse", "to": "Tarbes", "exclude": "Avion"})) == "unknown_mode"
    assert code(route(**{"from": "Toulouse", "to": "Tarbes", "exclude_network": "liO 34"})) == "unknown_network"
    every_mode = [m["id"] for m in client.get("/modes").json()["modes"]]
    assert code(route(**{"from": "Toulouse", "to": "Tarbes", "exclude": every_mode})) == "no_route"


def test_places_network_modes_info():
    places = client.get("/places").json()["places"]
    assert len(places) == client.get("/health").json()["stations"]
    toulouse = next(p for p in places if p["name"] == "Toulouse Matabiau")
    assert toulouse["department"] == "Haute-Garonne" and 43 < toulouse["lat"] < 44
    # La gare la plus fréquentée est Toulouse Matabiau, et elle dessert plusieurs lignes
    assert max(places, key=lambda p: p["trips_per_day"])["name"] == "Toulouse Matabiau"
    assert len(toulouse["lines"]) > 1
    ids = {p["id"] for p in places}
    edges = client.get("/network").json()["edges"]
    assert edges and all(e["from_id"] in ids and e["to_id"] in ids for e in edges)
    info = client.get("/info").json()
    assert info["valid_until"] > info["valid_from"]


def test_dijkstra_on_small_network(tmp_path):
    # Trois gares A, B, C et quatre missions
    (tmp_path / "stations_occitanie.csv").write_text(
        "stop_id,name,lat,lon,department,commune\n"
        "1,A,43,1,Aude,A\n2,B,43,2,Aude,B\n3,C,43,3,Aude,C\n", encoding="utf-8")
    header = "mission_id,mode,line,trips,trips_ref_day,stops,arrival_min,departure_min,pickup,dropoff\n"
    missions = [
        "M1,Train TER,lente,10,10,1|2|3,0|30|60,0|31|60,111,111",   # A -> C direct en 60 min
        "M2,Train TER,rapide AB,16,16,1|2,0|20,0|20,11,11",          # A -> B en 20 min
        "M3,Car TER,rapide BC,16,16,2|3,0|10,0|10,11,11",            # B -> C en 10 min, 16/jour -> 30 min d'attente
        "M4,INTERCITES,sans arrêt en B,5,5,1|2|3,0|5|15,0|5|15,101,101",  # passe en B sans prendre ni déposer
    ]
    (tmp_path / "missions_occitanie.csv").write_text(header + "\n".join(missions) + "\n", encoding="utf-8")
    net = Network(tmp_path)

    # Le plus rapide : M4, direct en 15 min
    r = net.route("A", "C")
    assert r["transfers"] == 0 and r["ride_minutes"] == 15 and r["legs"][0]["line"] == "sans arrêt en B"
    # M4 ne dessert pas B : A -> B se fait avec M2
    assert net.route("A", "B")["legs"][0]["line"] == "rapide AB"
    # Sans Intercités : le direct lent (60 min) bat la correspondance 20 + 5 + 30 (attente) + 10 = 65
    r = net.route("A", "C", exclude={"INTERCITES"})
    assert r["transfers"] == 0 and r["legs"][0]["line"] == "lente"
    # Si le direct mettait 70 min, la correspondance (65) gagnerait
    net.rides[("1", "3", "Train TER", "")][0] = 70
    r = net.route("A", "C", exclude={"INTERCITES"})
    assert r["transfers"] == 1 and r["minutes"] == 65 and r["legs"][1]["wait_minutes"] == 35


def test_transcribe_rejects_before_paying():
    # Format inconnu ou enregistrement vide : refusé avant tout appel à OpenAI
    r = client.post("/transcribe", content=b"x" * 2000, headers={"Content-Type": "text/plain"})
    assert r.status_code == 415 and r.json()["detail"]["code"] == "audio_format"
    r = client.post("/transcribe", content=b"x", headers={"Content-Type": "audio/webm;codecs=opus"})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "audio_empty"
