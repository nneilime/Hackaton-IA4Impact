"""Parseur français (mode démo) et normalisation de la demande."""
from datetime import date

from app import schemas
from app.services import comprendre

from .conftest import SCENARIO

AUJ = date(2026, 10, 10)


def test_message_du_scenario():
    ex = comprendre.extraire(SCENARIO, AUJ)
    assert ex["niveau"] == "5e"
    assert ex["theme"] == "Moyen Âge"
    assert ex["nb_eleves"] == 42
    assert ex["nb_accompagnateurs"] == 4
    assert ex["duree"] == "journee"
    assert ex["heure_depart_min"] == "08:00"
    assert ex["heure_retour_max"] == "19:00"
    assert ex["lieu_depart"]["libelle"] == "Collège de Foix"
    assert ex["lieu_depart"]["commune"] == "Foix"
    assert "date" not in ex


def test_version_longue_du_scenario():
    texte = ("Je souhaite travailler avec ma classe de 5e sur le Moyen Âge. Nous sommes 42 élèves et "
             "4 accompagnateurs. Nous souhaitons faire une sortie sur une journée, en train liO, avec "
             "un départ le matin et un retour avant 19h. Nous partons du collège de Foix.")
    ex = comprendre.extraire(texte, AUJ)
    assert (ex["niveau"], ex["nb_eleves"], ex["nb_accompagnateurs"], ex["heure_retour_max"]) == \
        ("5e", 42, 4, "19:00")


def test_gare_de_foix_trouvee_seule(conn):
    d = comprendre.fusionner(schemas.Demande(), comprendre.extraire(SCENARIO, AUJ))
    d = comprendre.completer(conn, d)
    assert d.gare_depart is not None and d.gare_depart.nom == "Foix"
    assert d.gare_depart.distance_m is not None and d.gare_depart.distance_m < 2000
    assert d.champs_manquants == ["date"]


def test_dates_en_francais_et_iso():
    for texte in ("le jeudi 12 novembre", "12 novembre 2026", "2026-11-12", "12/11", "12/11/2026"):
        assert comprendre.extraire_date(texte, AUJ) == "2026-11-12", texte
    assert comprendre.extraire_date("1er décembre", AUJ) == "2026-12-01"
    assert comprendre.extraire_date("15 mars", AUJ) == "2027-03-15"  # prochaine occurrence


def test_niveaux_et_nombres_en_lettres():
    ex = comprendre.extraire("quarante-deux élèves de CM2 et trois adultes, Antiquité", AUJ)
    assert (ex["niveau"], ex["nb_eleves"], ex["nb_accompagnateurs"], ex["theme"]) == ("CM2", 42, 3, "Antiquité")
    assert comprendre.extraire("une classe de seconde", AUJ)["niveau"] == "2de"
    ex = comprendre.extraire("classe de première, thème la Première Guerre mondiale", AUJ)
    assert (ex["niveau"], ex["theme"]) == ("1re", "Première Guerre mondiale")


def test_destination_souhaitee():
    cat = [("Cité de Carcassonne", "Carcassonne"), ("Basilique Saint-Sernin", "Toulouse")]
    ex = comprendre.extraire("Nous voulons visiter la Cité de Carcassonne, lycée de Toulouse", AUJ, catalogue=cat)
    assert ex["destination_souhaitee"] == "Cité de Carcassonne"
    assert ex["lieu_depart"]["commune"] == "Toulouse"


def test_reponse_courte_a_la_question_posee():
    assert comprendre.extraire("4", AUJ, champ_attendu="nb_accompagnateurs") == {"nb_accompagnateurs": 4}


def test_une_seule_question_si_accompagnateurs_manquent(client):
    texte = SCENARIO.replace(" et 4 accompagnateurs", "") + " Sortie le 12 novembre."
    r = client.post("/api/chat", json={"messages": [{"role": "user", "content": texte}], "demande": None})
    assert r.status_code == 200
    data = r.json()
    assert data["demande"]["champs_manquants"] == ["nb_accompagnateurs"]
    assert data["reponse"].count("?") == 1 and "accompagnateurs" in data["reponse"]
    assert 2 <= len(data["suggestions"]) <= 4
    assert data["complete"] is False and data["mode"] == "demo"


def test_gare_saisie_par_son_nom(client):
    """Chemin formulaire : gare tapée à la main, code UIC vide."""
    def valider(nom, lieu=None):
        d = {"gare_depart": {"code_uic": "", "nom": nom, "lat": 0, "lon": 0, "distance_m": None}}
        if lieu:
            d["lieu_depart"] = {"libelle": lieu, "lat": None, "lon": None}
        r = client.post("/api/demande/valider", json={"demande": d})
        assert r.status_code == 200
        return r.json()

    assert valider("Foix")["gare_depart"]["nom"] == "Foix"
    assert valider("foix")["gare_depart"]["code_uic"] == "87611301"
    assert valider("toulouse")["gare_depart"]["nom"] == "Toulouse Matabiau"
    assert valider("NIMES")["gare_depart"]["nom"] == "Nîmes"
    # gare inconnue : on repasse par le géocodage du lieu de départ
    assert valider("Gotham City", lieu="Collège de Foix")["gare_depart"]["nom"] == "Foix"
    # gare inconnue et pas de lieu : pas de gare
    assert valider("Gotham City")["gare_depart"] is None


def test_gare_par_nom_dans_les_autres_routes(client):
    d = {"niveau": "5e", "theme": "Moyen Âge", "nb_eleves": 42, "nb_accompagnateurs": 4,
         "date": "2026-11-12", "lieu_depart": {"libelle": "Collège de Foix", "lat": None, "lon": None},
         "gare_depart": {"code_uic": "", "nom": "foix", "lat": 0, "lon": 0, "distance_m": None}}
    r = client.post("/api/destinations", json={"demande": d})
    assert r.status_code == 200 and len(r.json()["destinations"]) == 3
    r = client.post("/api/trajets", json={"demande": d, "site_id": "toulouse-saint-sernin"})
    assert r.status_code == 200 and r.json()["propositions"]
    r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "Bonjour"}], "demande": d})
    assert r.json()["demande"]["gare_depart"]["nom"] == "Foix"
