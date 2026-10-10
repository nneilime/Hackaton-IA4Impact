"""Import DATAtourisme, testé sur un mini CSV de 14 lignes au même format que le vrai fichier."""
import csv
import sqlite3

import pytest

from app import db
from app.services import geo
from app.services.texte import arrondi
from etl import import_datatourisme as dt

ONT = "https://www.datatourisme.fr/ontology/core#"
COLONNES = ["Nom_du_POI", "Categories_de_POI", "Latitude", "Longitude", "Adresse_postale",
            "Code_postal_et_commune", "Periodes_regroupees", "Covid19_mesures_specifiques",
            "Createur_de_la_donnee", "SIT_diffuseur", "Date_de_mise_a_jour", "Contacts_du_POI",
            "Classements_du_POI", "Description", "URI_ID_du_POI"]

# Gares du test (toutes dans l'emprise Occitanie). B est à ~3,3 km au nord de A.
GARE_A = ("87000001", "Gare A", 42.9700, 1.6000)
GARE_B = ("87000002", "Gare B", 42.9900, 1.6000)
GARE_C = ("87000003", "Gare C", 43.2200, 2.3500)

EMAIL = "marie.dupont@exemple-contact.fr"
TELEPHONE = "05 61 02 03 04"
CONTACT = "Marie Dupont"


def uri(n: int) -> str:
    return f"https://data.datatourisme.fr/32/00000000-0000-0000-0000-{n:012d}"


def ligne(n, nom, types, lat, lon, commune, description="", classements="", contacts=""):
    cats = "|".join(ONT + t for t in types) + "|" + ONT + "PointOfInterest"
    return {
        "Nom_du_POI": nom, "Categories_de_POI": cats, "Latitude": lat, "Longitude": lon,
        "Adresse_postale": "1 rue du Test", "Code_postal_et_commune": f"09000#{commune}",
        "Periodes_regroupees": "", "Covid19_mesures_specifiques": "",
        "Createur_de_la_donnee": "OT test", "SIT_diffuseur": "SIT test",
        "Date_de_mise_a_jour": "2026-09-01", "Contacts_du_POI": contacts,
        "Classements_du_POI": classements, "Description": description, "URI_ID_du_POI": uri(n),
    }


DESC_ABBAYE = ("Abbaye bénédictine fondée au XIe siècle.\nElle conserve un cloître roman et "
               "des remparts médiévaux, \"joyau\" de la ville ; visite pour les scolaires.\n\n"
               f"Renseignements : {TELEPHONE}. Écrivez à {EMAIL}. Contactez {CONTACT} pour réserver.")
CONTACTS_ABBAYE = f"{CONTACT}#{EMAIL}|{CONTACT}#{TELEPHONE}|Abbaye#https://abbaye-test.example/"


def lignes():
    return [
        # 1. valide : abbaye médiévale près de la gare A (~800 m), description multi-lignes
        ligne(1, "ABBAYE SAINTE-TEST", ["CulturalSite", "ReligiousSite", "Abbey"], 42.9772, 1.6000,
              "Foix", DESC_ABBAYE, "Monument Historique#Ministère de la Culture", CONTACTS_ABBAYE),
        # 2. événement éphémère
        ligne(2, "Fête médiévale du château", ["EntertainmentAndEvent", "Event", "CulturalEvent"],
              42.9705, 1.6005, "Foix", "Grande fête médiévale."),
        # 3. hébergement
        ligne(3, "Gîte du château médiéval", ["Accommodation", "LodgingBusiness", "CulturalSite"],
              42.9710, 1.6010, "Foix", "Gîte dans un château médiéval."),
        # 4. commerce / dégustation
        ligne(4, "Cave du château", ["CulturalSite", "LocalBusiness", "TastingProvider", "Producer",
                                     "Store"], 42.9715, 1.6015, "Foix", "Cave dans un château médiéval."),
        # 5. restaurant
        ligne(5, "Restaurant de l'abbaye", ["FoodEstablishment", "Restaurant", "CulturalSite"],
              42.9720, 1.6020, "Foix", "Table dans une abbaye."),
        # 6 et 7. deux fiches du même musée, à ~45 m ; la 7 est la mieux documentée
        ligne(6, "Musée de la préhistoire", ["CulturalSite", "Museum", "LocalBusiness"],
              43.2205, 2.3500, "Carcassonne", "Collections préhistoriques."),
        ligne(7, "MUSÉE DE LA PRÉHISTOIRE", ["CulturalSite", "Museum", "LocalBusiness"],
              43.2209, 2.3500, "Carcassonne",
              "Le musée présente des outils paléolithiques et des peintures de grottes. "
              "Un parcours est consacré à la vie des hommes préhistoriques.",
              "Musée de France#Ministère de la Culture"),
        # 8. aucun thème détecté
        ligne(8, "Annexe administrative", ["CulturalSite", "RemarkableBuilding"], 43.2215, 2.3510,
              "Carcassonne", "Bureaux et salles de réunion."),
        # 9. thème médiéval mais loin de toute gare
        ligne(9, "Château fort des Landes", ["CulturalSite", "Castle"], 43.5500, 0.9000, "Loin",
              "Château fort médiéval."),
        # 10. musée portant le type LocalBusiness (c'est le cas de tous les musées du vrai fichier)
        ligne(10, "Musée d'art contemporain", ["CulturalSite", "Museum", "LocalBusiness"], 43.2190,
              2.3520, "Carcassonne", "Exposition d'art contemporain, peinture et sculpture."),
        # 11. plus proche de la gare B (~780 m) que de la gare A (~1,45 km)
        ligne(11, "Château de Test", ["CulturalSite", "Castle"], 42.9830, 1.6000, "Foix",
              "Château fort du XIIIe siècle."),
        # 12. déjà présent dans le catalogue fait main (voir test_pas_de_doublon_du_catalogue)
        ligne(12, "Basilique Saint-Exemple", ["CulturalSite", "ReligiousSite"], 43.2195, 2.3490,
              "Carcassonne", "Basilique romane médiévale."),
        # 13. coordonnées hors Occitanie
        ligne(13, "Abbaye de Paris", ["CulturalSite", "Abbey"], 48.85, 2.35, "Paris",
              "Abbaye médiévale."),
        # 14. itinéraire
        ligne(14, "Circuit des châteaux cathares", ["Tour", "WalkingTour", "CulturalSite"], 42.97,
              1.60, "Foix", "Circuit médiéval."),
    ]


@pytest.fixture
def csv_test(tmp_path):
    chemin = tmp_path / "dt.csv"
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLONNES)
        w.writeheader()
        w.writerows(lignes())
    return chemin


@pytest.fixture
def base_gares(tmp_path):
    """Base minimale : schéma réel + 3 gares, sans desserte (toutes les gares sont alors candidates)."""
    chemin = tmp_path / "mini.db"
    with db.connexion(chemin) as c:
        db.creer_schema(c)
        for uic, nom, lat, lon in (GARE_A, GARE_B, GARE_C):
            c.execute("INSERT INTO gare (code_uic, nom, lat, lon, commune) VALUES (?,?,?,?,?)",
                      (uic, nom, lat, lon, nom))
        c.execute("""INSERT INTO site_culturel (id, nom, commune, lat, lon, gare_uic, minutes_pied,
                       minutes_pied_groupe, themes, niveaux, activites, interet_pedagogique,
                       richesse, horaires, source_url) VALUES
                     ('catalogue-basilique', 'Basilique Saint-Exemple', 'Carcassonne', 43.2196,
                      2.3491, ?, 5, 12, 'Moyen Âge', '5e', '[]', 'Fait main', 3, 'x', 'u')""",
                  (GARE_C[0],))
    with db.connexion(chemin) as c:
        yield c


def sites_dt(conn):
    return {r["nom"]: r for r in conn.execute("SELECT * FROM site_culturel WHERE id LIKE 'dt-%'")}


def test_filtres_evenement_hebergement_commerce_restaurant(base_gares, csv_test):
    bilan = dt.importer(base_gares, csv_test)
    noms = sites_dt(base_gares)
    for exclu in ("Fête médiévale du château", "Gîte du château médiéval", "Cave du château",
                  "Restaurant de l'abbaye", "Circuit des châteaux cathares", "Abbaye de Paris"):
        assert exclu not in noms
    assert bilan.lus == 14
    assert bilan.exclus["evenement"] == 1
    assert bilan.exclus["hebergement"] == 1
    assert bilan.exclus["commerce_ou_producteur"] == 1
    assert bilan.exclus["restauration"] == 1
    assert bilan.exclus["itineraire"] == 1
    assert bilan.exclus["hors_occitanie"] == 1


def test_un_musee_localbusiness_est_garde(base_gares, csv_test):
    dt.importer(base_gares, csv_test)
    assert "Musée d'art contemporain" in sites_dt(base_gares)


def test_lieu_sans_theme_et_lieu_loin_de_toute_gare_ne_sont_pas_importes(base_gares, csv_test):
    bilan = dt.importer(base_gares, csv_test)
    noms = sites_dt(base_gares)
    assert "Annexe administrative" not in noms
    assert "Château fort des Landes" not in noms
    assert bilan.exclus["sans_theme_pedagogique"] == 1
    assert bilan.exclus["aucune_gare_a_moins_de_3_km"] == 1


def test_deduplication_garde_la_meilleure_fiche(base_gares, csv_test):
    bilan = dt.importer(base_gares, csv_test)
    musees = [n for n in sites_dt(base_gares) if "réhistoire" in n]
    assert musees == ["Musée de la Préhistoire"]  # majuscules adoucies, une seule fiche
    s = sites_dt(base_gares)["Musée de la Préhistoire"]
    assert "paléolithiques" in s["interet_pedagogique"]  # c'est la fiche détaillée qui a gagné
    assert s["richesse"] == 3                             # label Musée de France + description
    assert bilan.doublons == 1


def test_pas_de_doublon_du_catalogue_fait_main(base_gares, csv_test):
    bilan = dt.importer(base_gares, csv_test)
    assert "Basilique Saint-Exemple" not in sites_dt(base_gares)
    assert bilan.deja_catalogue == 1
    # le site du catalogue est intact
    cat = base_gares.execute("SELECT * FROM site_culturel WHERE id = 'catalogue-basilique'").fetchone()
    assert cat["interet_pedagogique"] == "Fait main"


def test_gare_la_plus_proche(base_gares, csv_test):
    dt.importer(base_gares, csv_test)
    noms = sites_dt(base_gares)
    assert noms["Château de Test"]["gare_uic"] == GARE_B[0]      # 780 m de B, 1,45 km de A
    assert noms["Abbaye Sainte-Test"]["gare_uic"] == GARE_A[0]   # 800 m de A, 1,4 km de B
    assert noms["Musée de la Préhistoire"]["gare_uic"] == GARE_C[0]


def test_marche_individuelle_et_de_groupe(base_gares, csv_test):
    dt.importer(base_gares, csv_test)
    s = sites_dt(base_gares)["Abbaye Sainte-Test"]
    gare = base_gares.execute("SELECT * FROM gare WHERE code_uic = ?", (s["gare_uic"],)).fetchone()
    d = geo.distance_m(s["lat"], s["lon"], gare["lat"], gare["lon"])
    individuel = arrondi(d / 80)
    assert s["minutes_pied"] == individuel
    assert s["minutes_pied_groupe"] == arrondi(individuel * 1.3 + 5)
    # Abbaye à ~0,8 km de la gare A : environ 10 min seul, 18 min en groupe (10 × 1,3 + 5)
    assert s["minutes_pied"] == 10 and s["minutes_pied_groupe"] == 18


def test_themes_et_niveaux(base_gares, csv_test):
    dt.importer(base_gares, csv_test)
    noms = sites_dt(base_gares)
    assert noms["Abbaye Sainte-Test"]["themes"].split(";")[0] == "Moyen Âge"
    assert "5e" in noms["Abbaye Sainte-Test"]["niveaux"].split(";")
    assert noms["Musée de la Préhistoire"]["themes"].split(";")[0] == "Préhistoire"
    assert noms["Musée d'art contemporain"]["themes"].split(";")[0] == "Arts"
    assert noms["Château de Test"]["themes"] == "Moyen Âge"
    # niveaux : toujours dans le vocabulaire des classes
    from etl.catalogue import TOUS
    for s in noms.values():
        assert s["niveaux"] and set(s["niveaux"].split(";")) <= set(TOUS)


def test_plafond_total_et_par_gare(base_gares, csv_test):
    bilan = dt.importer(base_gares, csv_test, max_total=2)
    assert bilan.importes == 2 and len(sites_dt(base_gares)) == 2
    assert bilan.exclus["plafond_total"] >= 1
    # les mieux notés d'abord : l'abbaye (Monument historique) et le musée (Musée de France)
    assert set(sites_dt(base_gares)) == {"Abbaye Sainte-Test", "Musée de la Préhistoire"}

    bilan = dt.importer(base_gares, csv_test, max_par_gare=1)
    assert max(bilan.par_gare.values()) == 1
    assert bilan.exclus["plafond_par_gare"] >= 1


def test_aucune_donnee_de_contact_en_base(base_gares, csv_test):
    dt.importer(base_gares, csv_test)
    texte = " ".join(
        str(v) for table in ("site_culturel", "meta")
        for row in base_gares.execute(f"SELECT * FROM {table}") for v in tuple(row) if v is not None)
    for interdit in (EMAIL, "05 61 02 03 04", CONTACT, "Dupont", "abbaye-test.example", "@"):
        assert interdit not in texte
    s = sites_dt(base_gares)["Abbaye Sainte-Test"]
    assert "Renseignements" not in s["interet_pedagogique"]


def test_champs_sans_invention(base_gares, csv_test):
    dt.importer(base_gares, csv_test)
    for s in sites_dt(base_gares).values():
        assert s["horaires"] == "À vérifier auprès du site"
        assert s["capacite_accueil"] is None
        assert s["heure_ouverture"] is None and s["duree_visite_min"] is None
        assert s["est_simule"] == 0
        assert 1 <= s["richesse"] <= 3
        assert len(s["interet_pedagogique"]) <= 200
        assert "<" not in s["interet_pedagogique"]
        assert 42.3 <= s["lat"] <= 45.1 and -0.4 <= s["lon"] <= 4.9


def test_id_stable_source_url_et_idempotence(base_gares, csv_test):
    dt.importer(base_gares, csv_test)
    s = sites_dt(base_gares)["Abbaye Sainte-Test"]
    assert s["source_url"] == uri(1)
    assert s["id"] == dt.identifiant(uri(1)) and s["id"].startswith("dt-") and len(s["id"]) == 13
    avant = {r["id"] for r in base_gares.execute("SELECT id FROM site_culturel")}
    dt.importer(base_gares, csv_test)  # relance : mêmes ids, pas de doublon
    assert {r["id"] for r in base_gares.execute("SELECT id FROM site_culturel")} == avant
    assert base_gares.execute("SELECT COUNT(*) FROM site_culturel WHERE id = ?", (s["id"],)).fetchone()[0] == 1


def test_source_citee_dans_meta(base_gares, csv_test):
    dt.importer(base_gares, csv_test)
    assert "Etalab" in db.meta_get(base_gares, "source_datatourisme")


def test_resume_coupe_a_la_phrase_sans_balises_ni_contacts():
    desc = ("<p>Un <b>très beau</b> musée.</p> Il présente des collections variées sur deux étages. "
            "Appelez le 05 61 02 03 04 pour réserver. " + "Une dernière phrase beaucoup trop longue. " * 10)
    r = dt.resume(desc)
    assert len(r) <= 200
    assert r.startswith("Un très beau musée. Il présente")
    assert "05 61" not in r and "<" not in r
    assert r.endswith(".")
    long = "Un très long segment sans point " * 20
    assert len(dt.resume(long)) <= 200 and dt.resume(long).endswith("…")
    assert dt.resume("Écrivez à contact@exemple.fr ou visitez https://exemple.fr.") == ""


def test_lecture_csv_par_parseur_descriptions_multilignes(base_gares, csv_test):
    """Le CSV a plus de lignes physiques que de lieux (descriptions multi-lignes)."""
    assert len(csv_test.read_text(encoding="utf-8").splitlines()) > 15
    assert dt.importer(base_gares, csv_test).lus == 14


def test_branchement_dans_seed_demo(tmp_path, monkeypatch, csv_test):
    from etl import seed_demo

    monkeypatch.setenv("LIO_DATA_DIR", str(tmp_path))
    (tmp_path / dt.NOM_FICHIER).write_bytes(csv_test.read_bytes())

    monkeypatch.setenv("LIO_DATATOURISME", "0")
    sans = tmp_path / "sans.db"
    seed_demo.semer(sans)
    with db.connexion(sans) as c:
        assert c.execute("SELECT COUNT(*) FROM site_culturel WHERE id LIKE 'dt-%'").fetchone()[0] == 0

    monkeypatch.setenv("LIO_DATATOURISME", "1")
    avec = tmp_path / "avec.db"
    seed_demo.semer(avec)
    with db.connexion(avec) as c:
        # les 24 sites du catalogue fait main sont toujours là ; ceux de DATAtourisme s'ajoutent
        assert c.execute("SELECT COUNT(*) FROM site_culturel WHERE id NOT LIKE 'dt-%'").fetchone()[0] > 20
        assert c.execute("SELECT COUNT(*) FROM site_culturel WHERE id LIKE 'dt-%'").fetchone()[0] >= 2
        assert db.meta_get(c, "source_datatourisme")
