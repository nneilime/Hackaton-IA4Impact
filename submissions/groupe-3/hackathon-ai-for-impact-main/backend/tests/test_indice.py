"""Indice Confiance Voyageur Scolaire (cahier des charges §5)."""
from app.services import confiance, propositions, sites

CRITERES = ["Capacité et confort", "Régularité", "Risque de suppression", "Faisabilité des horaires",
            "Accès gare → site", "Adéquation pédagogique", "Satisfaction et coup de cœur"]


def test_seuils():
    assert confiance.niveau_score(80) == "vert"
    assert confiance.niveau_score(79) == "orange"
    assert confiance.niveau_score(60) == "orange"
    assert confiance.niveau_score(59) == "rouge"
    assert confiance.niveau_score(95, bloquant=True) == "rouge"


def test_satisfaction_neutre_sans_retour():
    pts, txt = confiance.points_satisfaction(None, 0, 0, 0)
    assert pts == 5 and "pas encore de retours" in txt
    assert confiance.points_satisfaction(4.5, 2, 1, 0)[0] == 9
    assert confiance.points_satisfaction(5, 1, 1, 0)[0] == 10


def test_indice_de_l_alternative_du_scenario(conn, demande_scenario):
    ctx = propositions.contexte(demande_scenario)
    r = propositions.planifier(conn, ctx, sites.charger_site(conn, "toulouse-saint-sernin"))
    alt = r.propositions[1]
    assert alt.est_alternative
    d = {c.critere: c for c in alt.indice.details}
    assert [c.critere for c in alt.indice.details] == CRITERES
    assert [c.max for c in alt.indice.details] == [20, 15, 10, 15, 15, 15, 10]
    # 46 voyageurs pour 50 places : couvert tout juste (6) + 8 × 96 % d'emport
    assert d["Capacité et confort"].points == 14
    # régularité 95,8 % : plafonnée à 15 (barème 70 % → 0, 95 % → 15)
    assert d["Régularité"].points == 15
    # suppressions 0,9 % : 10 × (1 − 0,9 / 15) = 9,4
    assert d["Risque de suppression"].points == 9
    assert d["Faisabilité des horaires"].points == 15
    assert d["Accès gare → site"].points == 15
    assert d["Adéquation pédagogique"].points == 15
    assert d["Satisfaction et coup de cœur"].points == 5
    assert "pas encore de retours" in d["Satisfaction et coup de cœur"].explication
    assert alt.indice.score == sum(c.points for c in alt.indice.details) == 88
    assert alt.indice.niveau == "vert"


def test_formules_regularite_et_suppression(conn, demande_scenario, monkeypatch):
    ctx = propositions.contexte(demande_scenario)
    site = sites.charger_site(conn, "toulouse-saint-sernin")
    conn.execute("UPDATE fiabilite_train SET taux_regularite = 98.5, taux_suppression = 0, "
                 "taux_respect_emport = 100")
    r = propositions.planifier(conn, ctx, site)
    d = {c.critere: c.points for c in r.propositions[1].indice.details}
    assert d["Régularité"] == 15 and d["Risque de suppression"] == 10 and d["Capacité et confort"] == 14
    conn.execute("UPDATE fiabilite_train SET taux_regularite = 65, taux_suppression = 15")
    r = propositions.planifier(conn, propositions.contexte(demande_scenario), site)
    d = {c.critere: c.points for c in r.propositions[-1].indice.details}
    assert d["Régularité"] == 0 and d["Risque de suppression"] == 0


def test_garde_fou_des_explications_llm():
    from app import llm

    faits = "aller train 871607 Foix 09:00 -> Toulouse Matabiau 10:11 | places: besoin 46, disponibles 50"
    assert llm.explication_valide("Départ de Foix à 9h, arrivée à 10h11 : 50 places pour vos 46 voyageurs.", faits)
    assert not llm.explication_valide("Départ à 9h20.", faits)               # horaire inventé
    assert not llm.explication_valide("Il reste 48 places.", faits)          # nombre inventé
    assert not llm.explication_valide("Votre sortie est confirmée.", faits)  # jamais « confirmé »
