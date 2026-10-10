"""Moteur de la scène : POST /api/scene (parcours, événements invalides, ton, correctifs d'audit)."""
import re
import sqlite3
from datetime import date

import pytest

from app import db
from app.services import comprendre, recommander, scene_llm, themes
from app import schemas

PHRASE = ("Je souhaite travailler avec ma classe de 5e sur le Moyen Âge. Nous sommes 42 élèves et "
          "4 accompagnateurs. Sortie à la journée le 12 novembre, départ le matin et retour avant 19h. "
          "Nous partons du collège de Foix.")
INTERDIT = re.compile(r"\b(réservé|réservée|réservés|réservées|confirmé|confirmée|confirmés)\b", re.I)
HUMEURS = {"repos", "reflexion", "parle", "joie", "inquiete", "salue", "pointe", "loupe", "celebre"}
ANCRES = {"centre", "gauche", "droite", "haut-droite", "bas-droite"}
ICONES = {"chateau", "os", "colonnes", "planete", "feuille", "palette", "ampoule", "pin", "etincelles", "train",
          "qr", "coeur", "oui", "non", "retour", "loupe", "calendrier", "groupe"}


class Scene:
    """Petit pilote de test : garde l'état et vérifie les invariants de CHAQUE réponse."""

    def __init__(self, client):
        self.client = client
        self.etat = None
        self.rep = None
        self.nb = 0

    def post(self, evenement):
        self.nb += 1
        return self.client.post("/api/scene", json={"etat": self.etat, "evenement": evenement})

    def go(self, evenement):
        r = self.post(evenement)
        assert r.status_code == 200, (evenement, r.status_code, r.text)
        j = r.json()
        verifier(j)
        self.etat, self.rep = j["etat"], j
        return j

    def demarrer(self):
        return self.go({"type": "demarrer"})

    def texte(self, t):
        return self.go({"type": "texte", "texte": t})

    def choix(self, id_):
        return self.go({"type": "choix", "id": id_})

    def valeur(self, champ, **v):
        return self.go({"type": "valeur", "champ": champ, "valeur": v})


def verifier(j):
    mots = j["replique"].split()
    assert 1 <= len(mots) <= 25, j["replique"]
    assert not INTERDIT.search(j["replique"]), j["replique"]
    assert j["humeur"] in HUMEURS and j["ancre"] in ANCRES
    assert len(j["cartes"]) <= 4 and sum(c["style"] == "primaire" for c in j["cartes"]) <= 1
    assert all(c["icone"] in ICONES | {None} and 1 <= len(c["titre"].split()) <= 5 for c in j["cartes"])
    assert len(j["badges"]) <= 4 and j["mode"] == "demo"
    assert j["etape"] == j["etat"]["etape"] and len(j["etat"]["carnet"]) <= 30
    assert j["etat"]["carnet"][-1] == {"qui": "tchouette", "texte": j["replique"]}
    for b in j["badges"]:
        assert b["source"] in {"sncf", "datatourisme", "catalogue", "calcul", "demo"}
        assert not (b["source"] == "sncf" and "démo" in b["texte"].lower())
    if j["etape"] in ("destination", "trajet", "vote", "prereservation"):
        assert j["destination"] is not None
    if j["etape"] in ("trajet", "prereservation"):
        assert j["proposition"] is not None
    if j["etape"] not in ("accueil", "theme", "criteres"):
        assert j["manquants"] == []


@pytest.fixture
def sc(client):
    s = Scene(client)
    s.demarrer()
    return s


def par_phrase(sc):
    return sc.texte(PHRASE)


def vers_destination_par_clics(sc, theme="theme:moyen-age"):
    sc.choix("theme")
    sc.choix(theme)
    sc.choix("niveau:5e")
    sc.valeur("effectif", eleves=42, accompagnateurs=4)
    sc.valeur("date", date="2026-11-12")
    return sc.valeur("lieu_depart", libelle="Collège de Foix")


def pre_reserver(sc):
    p = sc.rep["proposition"]
    r = sc.client.post("/api/pre-reservations", json={"proposition_id": p["proposition_id"],
                                                      "email": "prof@college.fr", "demande": sc.etat["demande"]})
    assert r.status_code == 200, r.text
    return r.json()["reference"]


def jusqu_a(sc, etape):
    """Amène la conversation à l'étape voulue (parcours Saint-Sernin, 12 novembre)."""
    if etape == "accueil":
        return
    if etape == "theme":
        sc.choix("theme")
    elif etape == "criteres":
        sc.choix("theme")
        sc.choix("theme:moyen-age")
    else:
        par_phrase(sc)
        if etape == "destination":
            return
        if etape == "vote":
            sc.choix("vote")
            return
        sc.choix("choisir")
        if etape == "trajet":
            return
        sc.choix("reserver")
        if etape == "prereservation":
            return
        sc.go({"type": "prereservation_faite", "reference": pre_reserver(sc)})


# --- Parcours ---------------------------------------------------------------------------------

def test_accueil(sc):
    j = sc.rep
    assert (j["etape"], j["humeur"], j["ancre"]) == ("accueil", "salue", "centre")
    assert [(c["id"], c["titre"], c["icone"]) for c in j["cartes"]] == [
        ("theme", "J'ai un thème", "ampoule"), ("destination", "Je sais où aller", "pin"),
        ("surprise", "Surprenez-moi", "etincelles")]
    assert j["etat"]["tours"] == 1 and j["manquants"]


def test_parcours_par_clics_en_moins_de_10_interactions(sc, client):
    avant = sc.nb
    j = sc.choix("theme")
    assert j["etape"] == "theme" and 1 <= len(j["cartes"]) <= 4
    j = sc.choix("theme:moyen-age")
    assert j["etape"] == "criteres" and [c["id"] for c in j["cartes"]][0].startswith("niveau:")
    j = sc.choix("niveau:5e")
    assert j["saisie"]["type"] == "effectif" and (j["saisie"]["min"], j["saisie"]["max"]) == (6, 50)
    j = sc.valeur("effectif", eleves=42, accompagnateurs=4)
    assert j["saisie"]["type"] == "date" and j["saisie"]["min"] == "2026-10-11"
    j = sc.valeur("date", date="2026-11-12")
    assert j["saisie"]["type"] == "lieu" and len(j["saisie"]["suggestions"]) == 3
    j = sc.valeur("lieu_depart", libelle="Collège de Foix")
    assert j["etape"] == "destination" and j["destination"]["site_id"] == "toulouse-saint-sernin"
    assert j["etat"]["candidats"][0] == "toulouse-saint-sernin" and j["etat"]["rang"] == 0
    assert [c["id"] for c in j["cartes"]] == ["choisir", "autre", "pourquoi", "vote"]
    assert [c["id"] for c in j["cartes"] if c["style"] == "primaire"] == ["choisir"]
    assert j["humeur"] == "pointe"
    assert {p["cle"]: p["valeur"] for p in j["puces"]} == {
        "niveau": "5e", "theme": "Moyen Âge", "effectif": "46", "date": "12 nov.", "depart": "Foix"}
    j = sc.choix("choisir")
    assert j["etape"] == "trajet" and j["etat"]["site_id"] == "toulouse-saint-sernin"
    assert j["proposition"]["date"] == "2026-11-12" and j["proposition"]["indice"]["niveau"] != "rouge"
    assert [c["id"] for c in j["cartes"]] == ["reserver", "autre_train", "pourquoi", "retour"]
    j = sc.choix("reserver")
    assert j["etape"] == "prereservation" and "pré-réservation" in j["replique"].lower() and "SNCF" in j["replique"]
    ref = pre_reserver(sc)
    j = sc.go({"type": "prereservation_faite", "reference": ref})
    assert j["etape"] == "fin" and j["etat"]["dossier_reference"] == ref
    assert "attente" in j["replique"] and ref in j["replique"]
    assert [c["id"] for c in j["cartes"]] == ["retour_experience", "recommencer"]
    assert sc.nb - avant <= 10  # 8 clics + la pré-réservation + l'accusé de réception du front
    j = sc.choix("recommencer")
    assert j["etape"] == "accueil" and j["etat"]["demande"]["niveau"] is None


def test_scenario_de_la_fiche_par_une_phrase(sc):
    j = par_phrase(sc)
    assert j["etape"] == "destination" and j["manquants"] == []
    assert j["destination"]["site_id"] == "toulouse-saint-sernin"
    d = j["etat"]["demande"]
    assert (d["niveau"], d["theme"], d["nb_eleves"], d["nb_accompagnateurs"], d["date"]) == (
        "5e", "Moyen Âge", 42, 4, "2026-11-12")
    assert d["heure_retour_max"] == "19:00" and d["gare_depart"]["nom"] == "Foix"
    assert [p["valeur"] for p in j["puces"][:4]] == ["5e", "Moyen Âge", "46", "12 nov."]
    assert {b["source"] for b in j["badges"]} <= {"demo", "catalogue", "calcul"}
    assert any(b["icone"] == "shield" and b["source"] == "calcul" for b in j["badges"])
    # puis le trajet et la pré-réservation
    j = sc.choix("choisir")
    assert j["etape"] == "trajet" and j["proposition"]["date"] == "2026-11-12"


def test_phrase_incomplete_puis_un_critere_a_la_fois(sc):
    j = sc.texte("Classe de 5e, Moyen Âge, 42 élèves et 4 accompagnateurs, collège de Foix.")
    assert j["etape"] == "criteres" and j["saisie"]["type"] == "date"
    assert j["manquants"] == ["date de la sortie"]
    j = sc.texte("12 novembre")
    assert j["etape"] == "destination"


def test_plusieurs_criteres_d_un_coup_a_l_etape_criteres(sc):
    sc.choix("theme")
    sc.choix("theme:moyen-age")
    j = sc.texte("5e, 30 élèves et 3 accompagnateurs")
    assert j["etape"] == "criteres" and j["saisie"]["type"] == "date"
    assert {p["cle"] for p in j["puces"]} == {"theme", "niveau", "effectif"}


def test_effectif_partiel_puis_complete(sc):
    sc.choix("theme")
    sc.choix("theme:moyen-age")
    sc.choix("niveau:5e")
    j = sc.texte("30 élèves")
    assert j["saisie"] == {"type": "effectif", "min": 6, "max": 50, "eleves": 30, "accompagnateurs": None}
    j = sc.texte("3")
    assert j["saisie"]["type"] == "date"


def test_porte_je_sais_ou_aller(sc):
    j = sc.choix("destination")
    assert j["etape"] == "theme" and all(c["id"].startswith("site:") for c in j["cartes"])
    j = sc.texte("Je voudrais aller à Carcassonne")
    assert j["etape"] == "criteres" and j["etat"]["demande"]["destination_souhaitee"] in ("Carcassonne", "Cité de Carcassonne")
    assert j["puces"][0]["cle"] == "destination" or any(p["cle"] == "destination" for p in j["puces"])
    sc.choix("niveau:5e")
    sc.valeur("effectif", eleves=20, accompagnateurs=3)
    sc.valeur("date", date="2026-11-12")
    j = sc.valeur("lieu_depart", libelle="Collège de Foix")
    assert j["etape"] == "destination" and j["destination"]["site_id"] == "carcassonne-cite"


def test_porte_surprenez_moi(sc):
    j = sc.choix("surprise")
    assert j["etape"] == "criteres" and "theme" not in [p["cle"] for p in j["puces"]]
    sc.choix("niveau:5e")
    sc.valeur("effectif", eleves=30, accompagnateurs=3)
    sc.valeur("date", date="2026-11-12")
    j = sc.valeur("lieu_depart", libelle="Collège de Foix")
    assert j["etape"] == "destination" and j["etat"]["demande"]["theme"] is None


def test_autre_idee_boucle_et_le_dit(sc):
    j = par_phrase(sc)
    n = len(j["etat"]["candidats"])
    assert n >= 2
    vus = [j["destination"]["site_id"]]
    for _ in range(n - 1):
        j = sc.choix("autre")
        assert j["etape"] == "destination"
        vus.append(j["destination"]["site_id"])
    assert vus == j["etat"]["candidats"]
    j = sc.choix("autre")  # plus d'idée : on le dit et on reprend au début
    assert j["destination"]["site_id"] == vus[0] and j["etat"]["rang"] == 0
    assert "dernière" in j["replique"] or "tour" in j["replique"]


def test_pourquoi_ne_change_pas_d_etape(sc):
    avant = par_phrase(sc)
    j = sc.choix("pourquoi")
    assert j["etape"] == "destination" and j["humeur"] == "loupe"
    assert j["etat"]["candidats"] == avant["etat"]["candidats"] and j["etat"]["rang"] == avant["etat"]["rang"]
    libelles = [l["libelle"] for l in j["detail"]["lignes"]]
    assert "Régularité" in libelles and "Accès gare → site" in libelles and "Source des données" in libelles
    assert any(l["niveau"] in ("vert", "orange", "rouge") for l in j["detail"]["lignes"])
    # le détail n'est affiché qu'à la demande
    j = sc.texte("une autre idée")
    assert j["detail"] is None
    sc.choix("choisir")
    j = sc.texte("pourquoi ce train ?")
    assert j["etape"] == "trajet" and j["detail"] is not None


def test_un_autre_train_fait_defiler_les_options(sc):
    par_phrase(sc)
    j = sc.choix("choisir")
    trains = {tuple(s["train"] for s in j["proposition"]["aller"]["segments"])}
    for _ in range(4):
        j = sc.choix("autre_train")
        assert j["etape"] == "trajet" and j["proposition"]["indice"]["niveau"] != "rouge"
        trains.add(tuple(s["train"] for s in j["proposition"]["aller"]["segments"]))
    assert len(trains) >= 2  # plusieurs trains fiables à cette date : on les voit défiler


def test_vote_de_la_classe(sc, client):
    j = par_phrase(sc)
    candidats = j["etat"]["candidats"]
    j = sc.choix("vote")
    assert (j["etape"], j["ancre"]) == ("vote", "droite") and j["etat"]["vote_code"]
    code = j["etat"]["vote_code"]
    sondage = client.get(f"/api/sondages/{code}").json()
    assert [o["site_id"] for o in sondage["options"]] == candidats[:4]
    assert sondage["statut"] == "ouvert"
    gagnant = candidats[-1]
    client.post(f"/api/sondages/{code}/votes", json={"site_id": gagnant, "votant_id": "eleve-0001"})
    assert client.post(f"/api/sondages/{code}/fermer").json()["gagnant"] == gagnant
    j = sc.go({"type": "vote_termine", "site_id": gagnant})
    assert j["etape"] == "trajet" and j["humeur"] in ("celebre", "inquiete")
    assert j["etat"]["site_id"] == gagnant and j["destination"]["site_id"] == gagnant
    assert j["proposition"]["site_id"] == gagnant


def test_vote_annule_par_retour(sc):
    par_phrase(sc)
    sc.choix("vote")
    j = sc.go({"type": "retour"})
    assert j["etape"] == "destination" and j["etat"]["vote_code"] is None


def test_retour_a_chaque_etape(sc):
    par_phrase(sc)
    sc.choix("choisir")
    assert sc.go({"type": "retour"})["etape"] == "destination"
    sc.choix("choisir")
    sc.choix("reserver")
    assert sc.go({"type": "retour"})["etape"] == "trajet"
    sc.go({"type": "retour"})
    j = sc.go({"type": "retour"})  # destination -> on redemande le dernier critère (le lieu)
    assert j["etape"] == "criteres" and j["saisie"]["type"] == "lieu"
    j = sc.go({"type": "retour"})
    assert j["saisie"]["type"] == "date"
    sc.go({"type": "retour"})
    j = sc.go({"type": "retour"})
    assert j["etape"] == "criteres" and [c["id"] for c in j["cartes"]][0].startswith("niveau:")
    j = sc.go({"type": "retour"})
    assert j["etape"] == "theme"
    assert sc.go({"type": "retour"})["etape"] == "accueil"


def test_changer_la_date_redemande_la_date(sc):
    par_phrase(sc)
    j = sc.texte("je voudrais changer la date")
    assert j["etape"] == "criteres" and j["saisie"]["type"] == "date" and j["etat"]["demande"]["date"] is None
    j = sc.texte("le 19 novembre")
    assert j["etape"] == "destination" and j["etat"]["demande"]["date"] == "2026-11-19"


def test_modifier_l_effectif_en_cours_de_route_relance_la_recherche(sc):
    par_phrase(sc)
    j = sc.texte("en fait nous sommes 30 élèves et 3 accompagnateurs")
    assert j["etape"] == "destination" and j["etat"]["demande"]["nb_eleves"] == 30
    assert {p["cle"]: p["valeur"] for p in j["puces"]}["effectif"] == "33"


# --- Garde-fous sur la saisie -----------------------------------------------------------------

def test_effectif_limite_de_50(sc):
    sc.choix("theme")
    sc.choix("theme:moyen-age")
    sc.choix("niveau:5e")
    j = sc.valeur("effectif", eleves=48, accompagnateurs=6)
    assert j["saisie"]["type"] == "effectif" and "50" in j["replique"] and j["humeur"] == "inquiete"
    assert j["saisie"]["eleves"] == 48 and j["etat"]["demande"]["nb_eleves"] is None
    j = sc.valeur("effectif", eleves=3, accompagnateurs=1)
    assert "6" in j["replique"] and j["saisie"]["type"] == "effectif"
    j = sc.valeur("effectif", eleves=45, accompagnateurs=5)
    assert j["saisie"]["type"] == "date"  # 50 pile : accepté


def test_lieu_introuvable_sans_identifiant_technique(sc):
    sc.choix("theme")
    sc.choix("theme:moyen-age")
    sc.choix("niveau:5e")
    sc.valeur("effectif", eleves=20, accompagnateurs=3)
    sc.valeur("date", date="2026-11-12")
    j = sc.valeur("lieu_depart", libelle="Collège de Zorglub-sur-Mer")
    assert j["etape"] == "criteres" and j["saisie"]["type"] == "lieu"
    assert "gare" in j["replique"] and "gare_depart" not in j["replique"] and "Zorglub" in j["replique"]
    assert j["etat"]["demande"]["lieu_depart"] is None
    assert j["manquants"] == ["lieu de départ"]


def test_horaires_par_defaut_jamais_demandes(sc):
    j = par_phrase(sc)
    assert j["etat"]["demande"]["heure_depart_min"] == "08:00"
    s2 = Scene(sc.client)
    s2.demarrer()
    j2 = vers_destination_par_clics(s2)
    assert j2["etat"]["demande"]["heure_retour_max"] == "18:00" and j2["etape"] == "destination"


# --- Correctifs d'audit -----------------------------------------------------------------------

def test_audit1_theme_hors_catalogue_jamais_ramene_a_un_autre(sc):
    sc.choix("theme")
    j = sc.texte("Sciences et espace")
    assert j["etape"] == "theme" and j["etat"]["demande"]["theme"] is None
    assert "Sciences et nature" in j["replique"] and "Espace et astronomie" in j["replique"]
    assert [c["id"] for c in j["cartes"]][:2] == ["theme:sciences-et-nature", "theme:espace-et-astronomie"]
    j = sc.texte("Les volcans")
    assert j["etape"] == "theme" and j["etat"]["demande"]["theme"] is None
    assert "catalogue" in j["replique"] and len(j["cartes"]) == 4
    # dans une phrase aussi
    s2 = Scene(sc.client)
    s2.demarrer()
    j = s2.texte("Classe de 5e sur Sciences et espace, 40 élèves et 3 accompagnateurs, le 12 novembre, collège de Foix")
    assert j["etape"] == "theme" and j["etat"]["demande"]["theme"] is None
    assert j["etat"]["demande"]["nb_eleves"] == 40  # le reste est conservé


def test_audit1_themes_proposes_reellement_disponibles(sc, base):
    sc.choix("theme")
    ids = [c["id"] for c in sc.rep["cartes"]]
    assert 1 <= len(ids) <= 4 and len(set(ids)) == len(ids)
    with db.connexion(base) as c:
        presents = set()
        for r in c.execute("SELECT themes FROM site_culturel"):
            presents |= {t.strip() for t in r["themes"].split(";")}
    for carte in sc.rep["cartes"]:
        assert carte["titre"] in presents and carte["icone"] in ICONES
        assert re.match(r"\d+ sites? au catalogue", carte["sous_titre"])
    assert ids[0] == "theme:moyen-age"  # le mieux couvert d'abord


def test_audit1_canonique_ne_ramene_plus_en_silence():
    assert themes.canonique("Sciences et espace") is None
    assert themes.canonique("Espace et astronomie") == "Espace et astronomie"
    assert themes.canonique("moyen age") == "Moyen Âge" and themes.canonique("art roman") == "Moyen Âge"
    assert themes.themes_ambigus("Sciences et espace") == ["Sciences et nature", "Espace et astronomie"]
    assert themes.themes_ambigus("Moyen Âge") == []


def test_audit1_la_demande_garde_le_theme_tel_quel(conn):
    d = comprendre.completer(conn, schemas.Demande(theme="Sciences et espace"))
    assert d.theme == "Sciences et espace"


def test_audit17_date_passee_refusee(sc, client):
    sc.choix("theme")
    sc.choix("theme:moyen-age")
    sc.choix("niveau:5e")
    sc.valeur("effectif", eleves=20, accompagnateurs=3)
    j = sc.valeur("date", date="2026-09-01")
    assert j["saisie"]["type"] == "date" and "passé" in j["replique"] and j["etat"]["demande"]["date"] is None
    j = sc.texte("le 3 septembre 2026")
    assert "passé" in j["replique"] and j["etat"]["demande"]["date"] is None
    j = sc.valeur("date", date="2026-10-10")  # aujourd'hui : trop tard aussi
    assert "demain" in j["replique"] and j["etat"]["demande"]["date"] is None
    j = sc.valeur("date", date="2026-10-20")  # moins de 21 jours : accepté, mais prévenu
    assert j["etat"]["demande"]["date"] == "2026-10-20" and "21 jours" in j["replique"]
    assert j["saisie"]["type"] == "lieu"


def test_audit17_l_api_refuse_aussi_une_date_passee(client, demande_scenario):
    d = demande_scenario.model_dump()
    d["date"] = "2026-09-01"
    for route, corps in (("/api/destinations", {"demande": d}),
                         ("/api/trajets", {"demande": d, "site_id": "toulouse-saint-sernin"})):
        r = client.post(route, json=corps)
        assert r.status_code == 422 and "déjà passé" in r.json()["detail"]


def candidats_et_indices_api(client, demande):
    out = {}
    for site_id in (x["site_id"] for x in client.post("/api/destinations", json={"demande": demande}).json()["destinations"]):
        props = client.post("/api/trajets", json={"demande": demande, "site_id": site_id}).json()["propositions"]
        du_jour = [p for p in props if p["date"] == demande["date"]]
        ok = [p["indice"]["score"] for p in du_jour if p["indice"]["niveau"] != "rouge"]
        out[site_id] = (max(ok), "non-rouge") if ok else (None, "rouge")
    return out


def test_audit2_indice_de_la_destination_a_la_date_demandee(sc, client):
    j = par_phrase(sc)
    demande = j["etat"]["demande"]
    attendu = candidats_et_indices_api(client, demande)
    assert set(attendu) == set(j["etat"]["candidats"])
    api = {x["site_id"]: x for x in client.post("/api/destinations", json={"demande": demande}).json()["destinations"]}
    for sid, (score, genre) in attendu.items():
        d = api[sid]
        if genre == "rouge":
            assert d["niveau"] == "rouge" and d["indice_confiance"] <= 59
        else:
            assert d["niveau"] != "rouge" and d["indice_confiance"] == score, sid
    # la scène affiche les mêmes valeurs, destination après destination
    for _ in range(len(attendu)):
        dest = sc.rep["destination"]
        assert dest["indice_confiance"] == api[dest["site_id"]]["indice_confiance"]
        assert dest["niveau"] == api[dest["site_id"]]["niveau"]
        sc.choix("autre")


def trouver_destination_rouge(sc):
    for _ in range(len(sc.rep["etat"]["candidats"])):
        if sc.rep["destination"]["niveau"] == "rouge":
            return True
        sc.choix("autre")
    return False


def test_audit345_trajet_bloque_propose_l_alternative_en_disant_que_c_est_un_autre_jour(sc):
    par_phrase(sc)
    if not trouver_destination_rouge(sc):
        pytest.skip("aucune destination bloquée à cette date dans ce jeu de données")
    assert "pas assez fiable" in sc.rep["replique"].lower()
    assert not any(b["icone"] == "shield" for b in sc.rep["badges"])  # pas de score flatteur
    j = sc.choix("choisir")
    p = j["proposition"]
    assert j["etape"] == "trajet" and j["humeur"] == "inquiete"
    assert "pas assez fiable" in j["replique"].lower()
    if p["indice"]["niveau"] != "rouge":  # alternative sur un autre jour : dite clairement
        assert p["date"] != "2026-11-12" and "autre jour" in j["replique"].lower()
        assert "autre jour" in [c["sous_titre"] for c in j["cartes"] if c["id"] == "reserver"][0]
        j2 = sc.choix("reserver")  # accepter l'autre jour change la date de la demande
        assert j2["etape"] == "prereservation" and j2["etat"]["demande"]["date"] == p["date"]
        assert j2["etat"]["proposition_id"] == p["proposition_id"]
    else:
        assert "reserver" not in [c["id"] for c in j["cartes"]]


def test_audit345_trajet_entierement_bloque(client, base):
    with db.connexion(base) as c:
        for k in range(12, 20):
            c.execute("INSERT INTO positionnement (train_numero, date_sortie, nb_places, dossier_reference, est_simule) "
                      "SELECT numero, ?, 50, NULL, 1 FROM train", (f"2026-11-{k}",))
    s = Scene(client)
    s.demarrer()
    par_phrase(s)
    assert s.rep["etape"] == "destination" and s.rep["destination"]["niveau"] == "rouge"
    assert s.rep["destination"]["indice_confiance"] <= 59
    j = s.choix("choisir")
    assert j["etape"] == "trajet" and j["humeur"] == "inquiete"
    assert j["proposition"]["indice"]["niveau"] == "rouge" and j["proposition"]["indice"]["score"] <= 59
    assert "alternative" in j["replique"] and "places" in j["replique"]
    ids = [c["id"] for c in j["cartes"]]
    assert "reserver" not in ids and "retour" in ids
    assert not any(b["icone"] == "shield" for b in j["badges"])
    r = s.post({"type": "choix", "id": "reserver"})
    assert r.status_code == 409 and "fiable" in r.json()["detail"]
    j = s.texte("pré-réserver")  # en texte libre : refus poli, pas d'erreur
    assert j["etape"] == "trajet" and "pas assez fiable" in j["replique"]


def test_audit5_le_score_d_un_trajet_bloque_est_plafonne(client, base):
    with db.connexion(base) as c:
        c.execute("INSERT INTO positionnement (train_numero, date_sortie, nb_places, dossier_reference, est_simule) "
                  "SELECT numero, '2026-11-12', 50, NULL, 1 FROM train")
    demande = Scene(client)
    demande.demarrer()
    d = par_phrase(demande)["etat"]["demande"]
    props = client.post("/api/trajets", json={"demande": d, "site_id": "toulouse-saint-sernin"}).json()["propositions"]
    rouges = [p for p in props if p["indice"]["niveau"] == "rouge"]
    assert rouges and all(p["indice"]["score"] <= 59 for p in rouges)


def test_catalogue_fait_main_avant_les_sites_decouverte(conn):
    """À adéquation égale, un site DATAtourisme (dt-) passe après le catalogue fait main."""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(site_culturel)")]
    liste = ",".join(cols)
    sel = ",".join("'dt-test-copie'" if c == "id" else ("9" if c == "richesse" else c) for c in cols)
    conn.execute(f"INSERT INTO site_culturel ({liste}) SELECT {sel} FROM site_culturel WHERE id = 'toulouse-saint-sernin'")
    d = comprendre.completer(conn, schemas.Demande(
        niveau="5e", theme="Moyen Âge", nb_eleves=42, nb_accompagnateurs=4, date="2026-11-12",
        lieu_depart=schemas.LieuDepart(libelle="Collège de Foix")))
    ids = [x.site_id for x in recommander.recommander(conn, d).destinations]
    assert "dt-test-copie" not in ids[:2] or ids.index("dt-test-copie") > ids.index("toulouse-saint-sernin")
    assert ids[0] == "toulouse-saint-sernin"


# --- Conversation : humour, hors-sujet, aide ---------------------------------------------------

@pytest.mark.parametrize("etape", ["accueil", "theme", "criteres", "destination", "trajet", "vote",
                                   "prereservation", "fin"])
def test_humour_et_hors_sujet_gardent_l_etape(client, etape):
    sc = Scene(client)
    sc.demarrer()
    jusqu_a(sc, etape)
    assert sc.rep["etape"] == etape
    avant = sc.etat
    for phrase in ("raconte-moi une blague", "quelle est la météo demain ?", "merci beaucoup", "bonjour",
                   "tu es nul", "comment ça marche ?", "qui es-tu ?"):
        j = sc.texte(phrase)
        assert j["etape"] == etape, phrase
        for cle in ("candidats", "rang", "site_id", "proposition_id", "vote_code", "dossier_reference"):
            assert j["etat"][cle] == avant[cle], (phrase, cle)
        assert j["etat"]["demande"] == avant["demande"]
    assert sc.rep["etat"]["tours"] == avant["tours"] + 7


def test_humour_ramene_a_la_question_en_cours(sc):
    sc.choix("theme")
    sc.choix("theme:moyen-age")
    j = sc.texte("raconte-moi une blague")
    assert j["humeur"] == "joie" and j["etape"] == "criteres"
    assert [c["id"] for c in j["cartes"]][0].startswith("niveau:")
    j = sc.texte("quelle est la météo ?")
    assert j["humeur"] == "reflexion" and ("sorties" in j["replique"] or "train" in j["replique"])


def test_les_variantes_changent_et_restent_deterministes(client):
    a, b = Scene(client), Scene(client)
    for s in (a, b):
        s.demarrer()
    r1 = [a.texte("merci")["replique"] for _ in range(3)]
    r2 = [b.texte("merci")["replique"] for _ in range(3)]
    assert r1 == r2 and len(set(r1)) > 1  # mêmes entrées, mêmes sorties ; pas de répétition mécanique


def test_incomprehension_au_choix_de_destination(sc):
    par_phrase(sc)
    j = sc.texte("azerty uiop")
    assert j["etape"] == "destination" and "pourquoi" in j["replique"].lower()


def test_texte_libre_designe_les_cartes(sc):
    par_phrase(sc)
    assert sc.texte("une autre idée")["etat"]["rang"] == 1
    assert sc.texte("pourquoi ce choix ?")["detail"] is not None
    assert sc.texte("je veux faire voter les élèves")["etape"] == "vote"
    sc.go({"type": "retour"})
    assert sc.texte("celle-ci !")["etape"] == "trajet"
    assert sc.texte("un autre train")["etape"] == "trajet"
    assert sc.texte("pré-réserver")["etape"] == "prereservation"


def test_carnet_garde_les_30_dernieres_repliques(sc):
    for _ in range(20):
        sc.texte("merci")
    assert len(sc.rep["etat"]["carnet"]) == 30
    assert sc.rep["etat"]["carnet"][-2]["qui"] == "enseignant"


# --- Événements invalides ---------------------------------------------------------------------

def test_evenements_impossibles_renvoient_409(client):
    s = Scene(client)
    assert s.post({"type": "texte", "texte": "bonjour"}).status_code == 409  # pas d'état
    s.demarrer()
    cas = [
        {"type": "vote_termine", "site_id": "toulouse-saint-sernin"},
        {"type": "prereservation_faite", "reference": "LIO-2026-000001"},
        {"type": "valeur", "champ": "date", "valeur": {"date": "2026-11-12"}},
        {"type": "choix", "id": "reserver"},
        {"type": "choix", "id": "carte-inconnue"},
        {"type": "choix", "id": "niveau:5e"},
    ]
    for ev in cas:
        r = s.post(ev)
        assert r.status_code == 409 and isinstance(r.json()["detail"], str) and r.json()["detail"], ev
    par_phrase(s)
    for ev in ({"type": "choix", "id": "reserver"}, {"type": "choix", "id": "autre_train"},
               {"type": "vote_termine", "site_id": "toulouse-saint-sernin"},
               {"type": "prereservation_faite", "reference": "X"},
               {"type": "valeur", "champ": "effectif", "valeur": {"eleves": 10}}):
        assert s.post(ev).status_code == 409, ev
    s.choix("choisir")
    for ev in ({"type": "choix", "id": "vote"}, {"type": "choix", "id": "choisir"},
               {"type": "prereservation_faite", "reference": "X"}):
        assert s.post(ev).status_code == 409, ev
    s.choix("reserver")
    r = s.post({"type": "prereservation_faite", "reference": "LIO-2026-999999"})
    assert r.status_code == 409 and "dossier" in r.json()["detail"]
    ref = pre_reserver(s)
    s.go({"type": "prereservation_faite", "reference": ref})
    r = s.post({"type": "retour"})
    assert r.status_code == 409 and "Nouvelle sortie" in r.json()["detail"]


def test_vote_termine_exige_un_site_du_vote(sc):
    par_phrase(sc)
    sc.choix("vote")
    r = sc.post({"type": "vote_termine", "site_id": "nimes-arenes"})
    assert r.status_code == 409


def test_pre_reservation_d_un_autre_trajet_est_refusee(sc, client):
    jusqu_a(sc, "prereservation")
    autre = Scene(client)
    autre.demarrer()
    jusqu_a(autre, "prereservation")
    ref = pre_reserver(autre)  # dossier d'une autre conversation (autre proposition)
    r = sc.post({"type": "prereservation_faite", "reference": ref})
    assert r.status_code == 409


def test_etat_incoherent_ou_inconnu(client, sc):
    par_phrase(sc)
    base_etat = sc.etat
    for modif in ({"candidats": []}, {"rang": 9}, {"candidats": ["site-fantome"]}):
        r = client.post("/api/scene", json={"etat": {**base_etat, **modif}, "evenement": {"type": "texte", "texte": "ok"}})
        assert r.status_code == 409 and "incohérent" in r.json()["detail"], modif
    r = client.post("/api/scene", json={"etat": {**base_etat, "etape": "trajet", "site_id": None},
                                        "evenement": {"type": "retour"}})
    assert r.status_code == 409
    r = client.post("/api/scene", json={"etat": {**base_etat, "etape": "vote", "vote_code": None},
                                        "evenement": {"type": "retour"}})
    assert r.status_code == 409
    r = client.post("/api/scene", json={"etat": {**base_etat, "etape": "fin"}, "evenement": {"type": "retour"}})
    assert r.status_code == 409


def test_corps_invalides_renvoient_422(client, sc):
    cas = [
        {"etat": None, "evenement": {"type": "danser"}},
        {"etat": None, "evenement": {"type": "demarrer", "en_trop": 1}},
        {"etat": {"etape": "paradis"}, "evenement": {"type": "retour"}},
        {"etat": {**sc.etat, "inconnu": 1}, "evenement": {"type": "retour"}},
        {"etat": None},
        {"etat": None, "evenement": {"type": "texte"}},
        {"etat": None, "evenement": {"type": "valeur", "champ": "poids", "valeur": {}}},
    ]
    for corps in cas:
        r = client.post("/api/scene", json=corps)
        assert r.status_code == 422 and isinstance(r.json()["detail"], str), corps


def test_valeurs_mal_formees_renvoient_422(sc):
    sc.choix("theme")
    sc.choix("theme:moyen-age")
    sc.choix("niveau:5e")
    for champ, v in (("effectif", {"eleves": "beaucoup"}), ("effectif", {}), ("date", {"date": "demain"}),
                     ("lieu_depart", {"libelle": " "})):
        r = sc.post({"type": "valeur", "champ": champ, "valeur": v})
        assert r.status_code == 422 and r.json()["detail"], (champ, v)


# --- Honnêteté --------------------------------------------------------------------------------

def test_jamais_reserve_ni_confirme(client):
    s = Scene(client)
    s.demarrer()
    par_phrase(s)
    textes = [s.rep["replique"]]
    for ev in ("pourquoi", "autre", "choisir", "autre_train", "pourquoi", "reserver"):
        textes.append(s.choix(ev)["replique"])
    textes.append(s.go({"type": "prereservation_faite", "reference": pre_reserver(s)})["replique"])
    assert not any(INTERDIT.search(t) for t in textes)
    assert "SNCF" in textes[-1] and "attente" in textes[-1]
    assert all(INTERDIT.search(e["texte"]) is None for e in s.rep["etat"]["carnet"])


def test_chiffres_des_repliques_viennent_du_calcul(sc):
    par_phrase(sc)
    j = sc.choix("choisir")
    p = j["proposition"]
    horaires = {p["aller"]["depart"], p["retour"]["arrivee"]}
    heures = set(re.findall(r"(\d{1,2})h(\d{2})?", j["replique"]))
    calcul = {(str(int(h[:2])), m if (m := h[3:]) != "00" else "") for h in horaires}
    assert heures <= calcul, (heures, calcul)
    dispo = min(p["jauge_aller"]["disponibles"], p["jauge_retour"]["disponibles"])
    assert str(dispo) in j["replique"] and str(p["jauge_aller"]["besoin"]) in j["replique"]


# --- Crochet LLM ------------------------------------------------------------------------------

def test_hooks_llm_renvoient_none_par_defaut():
    etat = schemas.EtatScene(etape="accueil")
    assert scene_llm.comprendre_texte("bonjour", etat) is None
    assert scene_llm.reformuler("Bonjour.", {}, etat) is None


def test_mode_llm_utilise_les_crochets_et_les_garde_fous(client, monkeypatch):
    from app import llm
    monkeypatch.setattr(llm, "mode", lambda: "llm")
    monkeypatch.setattr(llm, "recommander", lambda *a, **k: None)
    monkeypatch.setattr(llm, "extraire_demande", lambda *a, **k: None)
    monkeypatch.setattr(llm, "expliquer", lambda *a, **k: {})
    s = Scene(client)
    monkeypatch.setattr(scene_llm, "reformuler", lambda r, f, e: None)
    r = client.post("/api/scene", json={"etat": None, "evenement": {"type": "demarrer"}}).json()
    assert r["mode"] == "llm"
    s.etat = r["etat"]
    monkeypatch.setattr(scene_llm, "comprendre_texte", lambda t, e: {"choix": "surprise"} if e.etape == "accueil" else None)
    j = client.post("/api/scene", json={"etat": s.etat, "evenement": {"type": "texte", "texte": "peu importe lequel"}}).json()
    assert j["etape"] == "criteres" and j["etat"]["demande"]["theme"] is None
    # reformulation acceptée si elle ne change aucun chiffre
    monkeypatch.setattr(scene_llm, "reformuler", lambda r, f, e: "Hou-hou, quelle classe ?")
    j = client.post("/api/scene", json={"etat": j["etat"], "evenement": {"type": "texte", "texte": "merci"}}).json()
    assert j["replique"] == "Hou-hou, quelle classe ?"
    # refusée si elle invente un chiffre, dit « réservé », ou dépasse 25 mots
    for mauvais in ("Il reste 99 places pour vous.", "Votre sortie est réservée !", " ".join(["mot"] * 30)):
        monkeypatch.setattr(scene_llm, "reformuler", lambda r, f, e, m=mauvais: m)
        j = client.post("/api/scene", json={"etat": j["etat"], "evenement": {"type": "texte", "texte": "merci"}}).json()
        assert j["replique"] != mauvais and len(j["replique"].split()) <= 25
    # un incident LLM ne casse pas la scène
    def boum(*a, **k):
        raise RuntimeError("panne")
    monkeypatch.setattr(scene_llm, "reformuler", boum)
    monkeypatch.setattr(scene_llm, "comprendre_texte", boum)
    r = client.post("/api/scene", json={"etat": j["etat"], "evenement": {"type": "texte", "texte": "merci"}})
    assert r.status_code == 200


def test_selection_multiple_vote_manuel_puis_trajet(sc, client):
    j = par_phrase(sc)
    cands = [d["site_id"] for d in j["choix_destinations"]]
    assert cands == j["etat"]["candidats"] and len(cands) >= 2
    carte = j["carte"]
    types = {p["type"] for p in carte["points"]}
    assert {"depart", "arrivee", "destination"} <= types
    assert len(carte["centre"]) == 2 and carte["traces"] and 4 <= carte["zoom"] <= 13
    assert sum(1 for p in carte["points"] if p["type"] in ("destination", "candidate")) == len(cands)
    j = sc.go({"type": "soumettre_vote", "ids": cands[:2]})
    assert j["etape"] == "vote" and j["carte"] and j["etat"]["vote_code"]
    code = j["etat"]["vote_code"]
    s = client.get(f"/api/sondages/{code}").json()
    assert [o["site_id"] for o in s["options"]] == cands[:2]
    r = client.post(f"/api/sondages/{code}/votes-manuels", json={"votes": {cands[1]: 30, cands[0]: 12}})
    assert r.status_code == 200 and r.json()["votes_manuels"] == 42
    assert client.post(f"/api/sondages/{code}/votes-manuels", json={"votes": {cands[1]: 43}}).status_code == 422
    g = client.post(f"/api/sondages/{code}/fermer").json()["gagnant"]
    assert g == cands[1]
    j = sc.go({"type": "vote_termine", "site_id": g})
    assert j["etape"] == "trajet" and j["etat"]["site_id"] == g


def test_selection_une_seule_passe_direct(sc):
    j = par_phrase(sc)
    j = sc.go({"type": "soumettre_vote", "ids": [j["etat"]["candidats"][0]]})
    assert j["etape"] == "trajet" and j["etat"]["vote_code"] is None


def test_selection_ids_invalides(sc):
    par_phrase(sc)
    assert sc.post({"type": "soumettre_vote", "ids": ["inconnu", "autre"]}).status_code == 409
    assert sc.post({"type": "soumettre_vote", "ids": []}).status_code == 422
    assert sc.post({"type": "soumettre_vote", "ids": list("abcde")}).status_code == 422


# --- Trajet modifiable et dates proches (agent trajet) ---------------------------------------

def _aller_au_trajet(client):
    s = Scene(client)
    s.demarrer()
    s.texte(PHRASE)
    return s, s.choix("choisir")


def test_changer_aller_et_retour_et_retour_etape(client):
    s, j = _aller_au_trajet(client)
    assert j["etape"] == "trajet" and j["alternatives"]["aller"]
    actuel = [o for o in j["alternatives"]["aller"] if o["actuel"]][0]
    autres = [o for o in j["alternatives"]["aller"] if not o["actuel"]]
    assert autres and all(o["places_disponibles"] <= 50 and o["niveau"] != "rouge" for o in j["alternatives"]["aller"])
    j2 = s.choix("changer_aller:" + autres[0]["id"])
    assert j2["etape"] == "trajet" and j2["proposition"]["aller"]["depart"] == autres[0]["depart"]
    assert j2["proposition"]["aller"]["depart"] != actuel["depart"]
    assert j2["proposition"]["retour"]["arrivee"] <= "19:00"
    retours = [o for o in j2["alternatives"]["retour"] if not o["actuel"]]
    for o in j2["alternatives"]["retour"]:
        assert o["arrivee"] <= "19:00"
    if retours:
        j3 = s.choix("changer_retour:" + retours[0]["id"])
        assert j3["proposition"]["retour"]["depart"] == retours[0]["depart"]
    r = s.post({"type": "choix", "id": "changer_aller:999999"})
    assert r.status_code == 409 and "faisable" in r.json()["detail"]
    jr = s.choix("retour_etape")  # revient à la destination sans perdre l'état
    assert jr["etape"] == "destination" and jr["etat"]["candidats"] and jr["etat"]["demande"]["date"] == "2026-11-12"
    assert s.choix("choisir")["etape"] == "trajet"


def test_changer_aller_hors_trajet_refuse(client):
    s = Scene(client)
    s.demarrer()
    r = s.post({"type": "choix", "id": "changer_aller:871607"})
    assert r.status_code == 409


def test_date_sans_train_propose_les_dates_proches_puis_relance(client, monkeypatch):
    from app.services import propositions
    s = Scene(client)
    s.demarrer()
    s.texte(PHRASE)
    orig = propositions.candidats_du_jour

    def sans_train_le_12(conn, ctx, site, acces, jour):
        res = orig(conn, ctx, site, acces, jour)
        return ([], res[1], res[2]) if jour == "2026-11-12" else res

    monkeypatch.setattr(propositions, "candidats_du_jour", sans_train_le_12)
    r = s.post({"type": "choix", "id": "choisir"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["etape"] == "trajet" and j["proposition"] is None
    assert j["replique"] == "Pas de train fiable le 12 novembre, voici les dates les plus proches."
    props = j["dates_proches"]
    assert 2 <= len(props) <= 3 and all(p["date"] != "2026-11-12" for p in props)
    assert any(p["ecart_jours"] < 0 for p in props) and any(p["ecart_jours"] > 0 for p in props)
    assert all(abs(p["ecart_jours"]) <= 21 and p["date"] > "2026-10-10" for p in props)
    cartes = [c for c in j["cartes"] if c["id"].startswith("choisir_date:")]
    assert len(cartes) == len(props) and "nov." in cartes[0]["titre"] and " j)" in cartes[0]["titre"]
    # une date hors liste est refusée
    r = client.post("/api/scene", json={"etat": j["etat"], "evenement": {"type": "choix", "id": "choisir_date:2026-11-30"}})
    assert r.status_code == 409
    choisie = props[0]["date"]
    r = client.post("/api/scene", json={"etat": j["etat"], "evenement": {"type": "choix", "id": cartes[0]["id"]}})
    j2 = r.json()
    assert r.status_code == 200 and j2["etat"]["demande"]["date"] == choisie
    assert j2["proposition"]["date"] == choisie and j2["etape"] == "trajet"


def test_endpoint_dates_proches(client):
    r = client.post("/api/dates-proches", json={"date": "2026-11-15", "gare_depart": "Foix",
                                                "gare_arrivee": "Toulouse Matabiau", "effectif": 46,
                                                "heure_retour_max": "19:00"})
    assert r.status_code == 200, r.text
    props = r.json()["propositions"]
    assert 1 <= len(props) <= 3 and all(p["date"] != "2026-11-15" for p in props)
    assert client.post("/api/dates-proches", json={"date": "2026-11-15", "gare_depart": "Nulle part",
                                                   "gare_arrivee": "Toulouse Matabiau", "effectif": 46}).status_code == 404
