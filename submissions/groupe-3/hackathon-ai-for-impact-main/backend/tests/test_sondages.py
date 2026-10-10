"""Vote en classe : création, vote et changement d'avis, fermeture, gagnant, erreurs."""
import re

from app.services import sondages

DEMANDE = {"niveau": "5e", "theme": "Moyen Âge", "nb_eleves": 42, "nb_accompagnateurs": 4}


def destination(site_id: str, nom: str, indice: int, niveau: str = "vert") -> dict:
    return {
        "site_id": site_id, "nom": nom, "commune": "Toulouse",
        "gare": {"code_uic": "87611004", "nom": "Toulouse Matabiau", "lat": 43.61, "lon": 1.45},
        "interet_pedagogique": f"Découvrir {nom}.", "activites": [], "themes": ["Moyen Âge"],
        "niveaux": ["5e"], "temps_trajet_min": 60, "correspondances": 0,
        "acces_gare_site": {"mode": "pied", "minutes_groupe": 15, "niveau": "vert", "message": "15 min à pied"},
        "indice_confiance": indice, "niveau": niveau,
    }


DESTINATIONS = [
    destination("saint-sernin", "Basilique Saint-Sernin", 82),
    destination("cite-carcassonne", "Cité de Carcassonne", 91),
    destination("chateau-foix", "Château de Foix", 74, "orange"),
]


def creer(client, destinations=DESTINATIONS) -> dict:
    r = client.post("/api/sondages", json={"demande": DEMANDE, "destinations": destinations})
    assert r.status_code == 200, r.text
    return r.json()


def voter(client, code, site_id, votant):
    return client.post(f"/api/sondages/{code}/votes", json={"site_id": site_id, "votant_id": votant})


def votes(sondage: dict) -> dict:
    return {o["site_id"]: o["votes"] for o in sondage["options"]}


VOTANT_A = "3f2b8c1e-5d6a-4b7c-9e0f-112233445566"
VOTANT_B = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
VOTANT_C = "0f0e0d0c-0b0a-4908-8706-050403020100"


def test_creation(client):
    s = creer(client)
    assert re.fullmatch(r"[A-HJ-NP-Z2-9]{6}", s["code"])
    assert s["titre"] == "Où part la 5e pour le Moyen Âge ?"
    assert s["statut"] == "ouvert"
    assert s["gagnant"] is None and s["total_votes"] == 0
    assert [o["site_id"] for o in s["options"]] == ["saint-sernin", "cite-carcassonne", "chateau-foix"]
    assert s["options"][2] == {"site_id": "chateau-foix", "nom": "Château de Foix", "commune": "Toulouse",
                               "interet_pedagogique": "Découvrir Château de Foix.", "indice_confiance": 74,
                               "niveau": "orange", "votes": 0, "votes_qr": 0, "votes_manuels": 0}
    lu = client.get(f"/api/sondages/{s['code'].lower()}")  # le code est insensible à la casse
    assert lu.status_code == 200 and lu.json() == s


def test_creation_limites(client):
    r = client.post("/api/sondages", json={"demande": DEMANDE, "destinations": DESTINATIONS[:1]})
    assert r.status_code == 422 and "2 destinations" in r.json()["detail"]
    doublons = [DESTINATIONS[0], DESTINATIONS[0]]
    assert client.post("/api/sondages", json={"demande": DEMANDE, "destinations": doublons}).status_code == 422
    cinq = DESTINATIONS + [destination("musee-a", "Musée A", 60), destination("musee-b", "Musée B", 50)]
    assert len(creer(client, cinq)["options"]) == 4


def test_titres():
    from app.schemas import Demande
    assert sondages.titre(Demande()) == "Où part la classe en sortie ?"
    assert sondages.titre(Demande(niveau="CM2", theme="Antiquité")) == "Où part le CM2 pour l'Antiquité ?"
    assert sondages.titre(Demande(theme="Châteaux")) == "Où part la classe pour le thème « Châteaux » ?"


def test_vote_et_changement_de_vote(client):
    code = creer(client)["code"]
    r = voter(client, code, "saint-sernin", VOTANT_A)
    assert r.status_code == 200
    assert votes(r.json()) == {"saint-sernin": 1, "cite-carcassonne": 0, "chateau-foix": 0}
    voter(client, code, "cite-carcassonne", VOTANT_B)
    # Le même élève change d'avis : son vote est remplacé, pas ajouté.
    s = voter(client, code, "cite-carcassonne", VOTANT_A).json()
    assert votes(s) == {"saint-sernin": 0, "cite-carcassonne": 2, "chateau-foix": 0}
    assert s["total_votes"] == 2


def test_votes_anonymes(client, base):
    from app import db
    code = creer(client)["code"]
    voter(client, code, "saint-sernin", VOTANT_A)
    with db.connexion(base) as conn:
        lignes = [dict(r) for r in conn.execute("SELECT * FROM sondage_vote")]
    assert len(lignes) == 1
    assert VOTANT_A not in str(lignes)  # seule une empreinte est conservée


def test_vote_invalide(client):
    code = creer(client)["code"]
    assert voter(client, code, "tour-eiffel", VOTANT_A).status_code == 422
    assert voter(client, code, "saint-sernin", "x").status_code == 422


def test_409_apres_fermeture(client):
    code = creer(client)["code"]
    voter(client, code, "saint-sernin", VOTANT_A)
    assert client.post(f"/api/sondages/{code}/fermer").status_code == 200
    r = voter(client, code, "cite-carcassonne", VOTANT_A)
    assert r.status_code == 409
    assert "terminé" in r.json()["detail"]
    assert votes(client.get(f"/api/sondages/{code}").json())["saint-sernin"] == 1


def test_gagnant_plus_de_votes(client):
    code = creer(client)["code"]
    voter(client, code, "chateau-foix", VOTANT_A)
    voter(client, code, "chateau-foix", VOTANT_B)
    voter(client, code, "cite-carcassonne", VOTANT_C)
    s = client.post(f"/api/sondages/{code}/fermer").json()
    assert s["statut"] == "ferme"
    assert s["gagnant"] == "chateau-foix"  # plus de votes, malgré un indice plus faible
    # Fermer deux fois ne change rien.
    assert client.post(f"/api/sondages/{code}/fermer").json() == s


def test_egalite_departagee_par_indice(client):
    code = creer(client)["code"]
    voter(client, code, "saint-sernin", VOTANT_A)
    voter(client, code, "cite-carcassonne", VOTANT_B)
    s = client.post(f"/api/sondages/{code}/fermer").json()
    assert s["gagnant"] == "cite-carcassonne"  # 1 vote chacun : indice 91 contre 82


def test_404(client):
    assert client.get("/api/sondages/ZZZZZZ").status_code == 404
    r = voter(client, "ZZZZZZ", "saint-sernin", VOTANT_A)
    assert r.status_code == 404 and "ZZZZZZ" in r.json()["detail"]
    assert client.post("/api/sondages/ZZZZZZ/fermer").status_code == 404


def test_reseau(client, monkeypatch):
    r = client.get("/api/reseau")
    assert r.status_code == 200
    ip = r.json()["ip_locale"]
    assert ip is None or (re.fullmatch(r"\d+\.\d+\.\d+\.\d+", ip) and not ip.startswith("127."))

    def sans_reseau(*_args, **_kwargs):
        raise OSError("réseau indisponible")

    monkeypatch.setattr(sondages.socket.socket, "connect", sans_reseau)
    assert client.get("/api/reseau").json() == {"ip_locale": None}


def test_base_anterieure_sans_tables(base):
    """Une base construite avant le vote en classe reçoit ses tables au premier appel."""
    import pytest
    from fastapi import HTTPException
    from app import db
    with db.connexion(base) as conn:
        for table in ("sondage_vote", "sondage_option", "sondage"):
            conn.execute(f"DROP TABLE {table}")
    sondages._bases_pretes.clear()
    with db.connexion(base) as conn:
        with pytest.raises(HTTPException) as e:
            sondages.lire(conn, "ABCDEF")
        assert e.value.status_code == 404


def manuels(client, code, v):
    return client.post(f"/api/sondages/{code}/votes-manuels", json={"votes": v})


def test_votes_manuels_s_additionnent_au_qr(client):
    s = creer(client)
    code = s["code"]
    voter(client, code, "saint-sernin", "eleve-0001-aaaa")
    r = manuels(client, code, {"saint-sernin": 10, "cite-carcassonne": 12})
    assert r.status_code == 200, r.text
    j = r.json()
    o = {x["site_id"]: x for x in j["options"]}
    assert o["saint-sernin"]["votes"] == 11 and o["saint-sernin"]["votes_qr"] == 1
    assert o["saint-sernin"]["votes_manuels"] == 10
    assert j["votes_manuels"] == 22 and j["votes_qr"] == 1 and j["total_votes"] == 23
    assert j["effectif"] == 42
    # la saisie remplace la précédente
    j = manuels(client, code, {"cite-carcassonne": 3}).json()
    assert j["votes_manuels"] == 3 and j["total_votes"] == 4


def test_votes_manuels_validation(client):
    code = creer(client)["code"]
    assert manuels(client, code, {"inconnu": 1}).status_code == 422
    assert manuels(client, code, {"saint-sernin": -1}).status_code == 422
    assert manuels(client, code, {"saint-sernin": 43}).status_code == 422   # > effectif (42)
    voter(client, code, "saint-sernin", "eleve-0001-aaaa")
    assert manuels(client, code, {"saint-sernin": 42}).status_code == 422   # 42 + 1 QR > 42
    assert manuels(client, code, {"saint-sernin": 41}).status_code == 200
    client.post(f"/api/sondages/{code}/fermer")
    assert manuels(client, code, {"saint-sernin": 1}).status_code == 409


def test_gagnant_avec_votes_manuels_egalite_confiance(client):
    code = creer(client)["code"]
    manuels(client, code, {"saint-sernin": 5, "cite-carcassonne": 5})
    assert client.post(f"/api/sondages/{code}/fermer").json()["gagnant"] == "cite-carcassonne"  # indice 91 > 82
