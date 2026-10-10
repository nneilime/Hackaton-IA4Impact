"""Règles métier R1 à R10, jauge, jour type."""
from app.services import controles, propositions, sites, trains
from etl.commun import minutes_groupe


def test_temps_de_marche_de_groupe():
    assert minutes_groupe(11) == 19   # 11 × 1,3 + 5 = 19,3
    assert minutes_groupe(10) == 18
    assert minutes_groupe(12) == 21


def test_acces_gare_site(conn):
    a = sites.acces(sites.charger_site(conn, "toulouse-saint-sernin"))
    assert (a.mode, a.minutes, a.niveau, a.points) == ("pied", 19, "vert", 15)
    a = sites.acces(sites.charger_site(conn, "carcassonne-cite"))
    assert (a.mode, a.niveau, a.points) == ("urbain", "orange", 10)
    a = sites.acces(sites.charger_site(conn, "tarascon-parc-prehistoire"))
    assert (a.niveau, a.points) == ("rouge", 0)


def test_jauge_option_simulee(conn):
    cache = {}
    e = controles.etat_train(conn, "871605", "2026-11-12", cache)
    assert (e.capacite, e.sous_option, e.disponibles, e.groupes) == (50, 10, 40, 1)
    assert controles.niveau_jauge(40, 46, 1) == "rouge"
    assert controles.niveau_jauge(50, 46, 0) == "orange"   # couvre tout juste (< 10 % de marge)
    assert controles.niveau_jauge(50, 30, 0) == "vert"
    assert controles.niveau_jauge(50, 30, 1) == "orange"   # autre groupe positionné
    e = controles.etat_train(conn, "871605", "2026-11-13", cache)
    assert e.disponibles == 50


def test_jour_type(conn):
    r = trains.resoudre_date(conn, "2026-11-12")
    assert r.jour_type is True
    assert r.ref_date.startswith("2026-0") and "jeudi" in r.message
    from datetime import date
    assert date.fromisoformat(r.ref_date).isoweekday() == 4
    r = trains.resoudre_date(conn, "2026-03-05")
    assert (r.jour_type, r.ref_date) == (False, "2026-03-05")


def test_r1_seuls_les_trains_autorises(conn):
    g = trains.charger_grille(conn, "2026-06-25")
    assert "871605" in g.trains and "871603" not in g.trains  # 871603 : heure de pointe


def test_controles_du_premier_train(conn, demande_scenario):
    ctx = propositions.contexte(demande_scenario)
    r = propositions.planifier(conn, ctx, sites.charger_site(conn, "toulouse-saint-sernin"))
    rouge = r.propositions[0]
    c = {x.regle: x for x in rouge.controles}
    assert list(c) == [f"R{i}" for i in range(1, 11)]
    assert c["R2"].niveau == "rouge" and "40 places" in c["R2"].message
    assert c["R9"].niveau == "orange"           # un autre groupe, jamais son identité
    assert c["R6"].niveau == "orange"           # départ 8h05, avant 9h
    assert c["R10"].niveau == "orange"          # capacité inconnue : à vérifier
    assert rouge.jauge_aller.niveau == "rouge" and rouge.jauge_aller.disponibles == 40
    assert rouge.indice.niveau == "rouge"


def test_r2_effectif_hors_bornes(conn, demande_scenario):
    d = demande_scenario.model_copy(update={"nb_eleves": 52})
    ctx = propositions.contexte(d)
    r = propositions.planifier(conn, ctx, sites.charger_site(conn, "toulouse-saint-sernin"))
    assert r.propositions and all(p.indice.niveau == "rouge" for p in r.propositions)
    assert not any(p.est_alternative for p in r.propositions)


def test_r7_moins_de_21_jours(conn, demande_scenario):
    d = demande_scenario.model_copy(update={"date": "2026-10-20"})
    r = propositions.planifier(conn, propositions.contexte(d), sites.charger_site(conn, "toulouse-saint-sernin"))
    r7 = next(c for c in r.propositions[0].controles if c.regle == "R7")
    assert r7.niveau == "orange"


def test_r5_retour_trop_tard_exclu(conn, demande_scenario):
    d = demande_scenario.model_copy(update={"heure_retour_max": "13:00"})
    r = propositions.planifier(conn, propositions.contexte(d), sites.charger_site(conn, "toulouse-saint-sernin"))
    assert r.propositions == []
