"""
Tests du calculateur d'indice de confiance.
Lancer :  pytest -v
Ces tests verifient les REGLES DU CADRAGE et le FORMAT REEL des fichiers
(separateur ';', taux en '63,20%', 'Taux SUPP' vide quand 0 suppression, colonne parasite).
Si Antigravity produit un code qui les fait echouer, c'est le code qui a tort
(ou une regle a rediscuter avec l'equipe).
"""

import itertools
import json

import indice_confiance as ic

TRAIN_PARFAIT = {"regularite_pct": 97, "suppression_pct": 0.0, "stabilite_pct": 100,
                 "frequentation_percentile": 0.1}
TRAIN_MOYEN = {"regularite_pct": 90, "suppression_pct": 2.0, "stabilite_pct": 96,
               "frequentation_percentile": 0.5}
SITE_PROCHE = {"distance_m": 500, "bus_unique": False, "trottoir_ok": True,
               "pique_nique_couvert": True, "consignes": True, "themes": ["histoire"],
               "note_moyenne": 4.8, "nb_avis": 10}


def site(**changements):
    """Copie de SITE_PROCHE avec quelques champs modifies."""
    s = dict(SITE_PROCHE)
    s.update(changements)
    return s


# ---------- Configuration ----------

def test_poids_piliers_somment_a_un_et_conformes_au_cadrage():
    assert abs(sum(ic.POIDS.values()) - 1.0) < 1e-9
    # repartition validee par l'enseignant : capacite 40, fiabilite 30, faisabilite 20, pairs 10
    assert ic.POIDS == {"fiabilite": 0.30, "faisabilite": 0.20, "capacite": 0.40, "pairs": 0.10}


def test_poids_des_sous_criteres_somment_a_un():
    for poids in (ic.POIDS_FIABILITE, ic.POIDS_FAISABILITE, ic.POIDS_PAIRS):
        assert abs(sum(poids.values()) - 1.0) < 1e-9


def test_capacite_et_seuils_du_cadrage():
    assert ic.CAPACITE_MAX == 50
    assert ic.SEUIL_VERT == 85 and ic.SEUIL_ORANGE == 65
    assert ic.SEUIL_MARCHE_MIN == 20
    assert ic.MARGE_MINIMALE_MIN == 15 and ic.MARGE_CONFORT_MIN == 20   # "15 a 20 minutes"
    assert 2.5 <= ic.VITESSE_MARCHE_KMH <= 3.0


# ---------- Seuils et couleurs ----------

def test_cas_ideal_est_vert():
    r = ic.calculer_indice(TRAIN_PARFAIT, SITE_PROCHE, effectif=25, options_actives=0,
                           theme_projet="histoire")
    assert r["couleur"] == "vert" and r["score"] >= 85 and not r["bloque"]
    assert r["badge_coup_de_coeur"] is True


def test_bus_necessaire_donne_alerte_sans_blocage():
    s = site(distance_m=2500, bus_unique=True)
    r = ic.calculer_indice(TRAIN_MOYEN, s, effectif=30, options_actives=5)
    assert not r["bloque"]
    assert r["couleur"] in ("orange", "vert")
    assert any("bus" in a.lower() for a in r["alertes"])


def test_frontieres_des_couleurs():
    assert ic.couleur_depuis_score(85, False) == "vert"
    assert ic.couleur_depuis_score(84, False) == "orange"
    assert ic.couleur_depuis_score(65, False) == "orange"
    assert ic.couleur_depuis_score(64, False) == "rouge"
    assert ic.couleur_depuis_score(99, True) == "rouge"   # un veto force le rouge


# ---------- Regle d'or n.2 : 50 voyageurs max ----------

def test_capacite_depassee_bloque_et_rouge():
    r = ic.calculer_indice(TRAIN_PARFAIT, SITE_PROCHE, effectif=35, options_actives=20)
    assert r["bloque"] and r["couleur"] == "rouge" and r["score"] < 65
    assert any("capacite" in v.lower() for v in r["vetos"])


def test_capacite_exactement_50_n_est_pas_bloquee():
    r = ic.calculer_indice(TRAIN_PARFAIT, SITE_PROCHE, effectif=30, options_actives=20)
    assert not any("capacite" in v.lower() for v in r["vetos"])


def test_capacite_51_bloque():
    r = ic.calculer_indice(TRAIN_PARFAIT, SITE_PROCHE, effectif=30, options_actives=21)
    assert r["bloque"]


# ---------- Faisabilite : dernier kilometre ----------

def test_conversion_marche():
    assert abs(ic.minutes_de_marche(1000, 3.0) - 20.0) < 1e-9


def test_marche_longue_sans_bus_est_un_veto():
    r = ic.calculer_indice(TRAIN_PARFAIT, site(distance_m=3000), effectif=25, options_actives=0)
    assert r["bloque"] and r["couleur"] == "rouge"


def test_marche_longue_avec_bus_applique_une_decote_sans_veto():
    _, details, _, vetos = ic.score_faisabilite(site(distance_m=3000, bus_unique=True))
    assert vetos == []
    assert details["accessibilite"] == 100 - ic.DECOTE_BUS


def test_absence_de_trottoir_est_un_veto():
    _, _, _, vetos = ic.score_faisabilite(site(trottoir_ok=False))
    assert len(vetos) == 1


def test_trottoir_inconnu_n_est_pas_un_veto_mais_une_alerte():
    _, details, alertes, vetos = ic.score_faisabilite(site(trottoir_ok=None))
    assert vetos == [] and details["securite"] is None
    assert any("securite" in a.lower() for a in alertes)


# ---------- Faisabilite : marge horaire ----------

def test_heure_en_minutes():
    assert ic.heure_en_minutes("12:04:00") == 724
    assert ic.heure_en_minutes("12:04") == 724
    assert ic.heure_en_minutes(725) == 725
    assert ic.heure_en_minutes(None) is None
    assert ic.heure_en_minutes("abc") is None
    assert ic.heure_en_minutes(float("nan")) is None


def test_marge_confortable():
    _, details, _, vetos = ic.score_faisabilite(SITE_PROCHE, "10:00", "11:00")
    assert details["marge"] == 100.0 and vetos == []


def test_marge_insuffisante_est_un_veto():
    # 500 m = ~11 min de marche : arrivee 10:00, debut 10:15 => ~4 min de marge
    _, details, _, vetos = ic.score_faisabilite(SITE_PROCHE, "10:00", "10:15")
    assert details["marge"] == 0.0 and len(vetos) == 1


def test_marge_de_12_minutes_est_deja_trop_courte():
    # l'enseignant exige 15 a 20 min : recompter les eleves, toilettes, sacs
    _, _, _, vetos = ic.score_faisabilite(SITE_PROCHE, "10:00", "10:23")   # ~12 min de marge
    assert len(vetos) == 1


def test_la_capacite_pese_plus_que_tout_le_reste():
    assert ic.POIDS["capacite"] == max(ic.POIDS.values())


def test_marge_serree_donne_une_alerte_sans_veto():
    # arrivee 10:00 + ~10.9 min de marche, debut 10:28 => ~17 min de marge (entre 15 et 20)
    _, details, alertes, vetos = ic.score_faisabilite(SITE_PROCHE, "10:00", "10:28")
    assert vetos == [] and 60 <= details["marge"] < 100
    assert any("marge" in a.lower() for a in alertes)


def test_sans_horaires_la_marge_n_est_pas_evaluee_et_les_poids_sont_repartis():
    note, details, _, _ = ic.score_faisabilite(SITE_PROCHE)
    assert details["marge"] is None
    assert abs(note - 100.0) < 1e-9     # acces 100 + securite 100, marge ignoree


def test_moyenne_ponderee_ignore_les_none():
    assert ic.moyenne_ponderee([(100, 0.5), (None, 0.5)]) == 100
    assert ic.moyenne_ponderee([(None, 1.0)]) is None
    assert abs(ic.moyenne_ponderee([(100, 0.5), (0, 0.5)]) - 50) < 1e-9


# ---------- Fiabilite ----------

def test_suppressions_chroniques_sont_un_veto():
    train = dict(TRAIN_PARFAIT, suppression_pct=12.0)
    r = ic.calculer_indice(train, SITE_PROCHE, effectif=25, options_actives=0)
    assert r["bloque"] and r["couleur"] == "rouge"


def test_train_instable_ou_de_pointe_donne_des_alertes():
    train = dict(TRAIN_MOYEN, stabilite_pct=80, frequentation_percentile=0.9)
    _, _, alertes, vetos = ic.score_fiabilite(train)
    assert vetos == [] and len(alertes) >= 2


# ---------- Pairs ----------

def test_badge_coup_de_coeur():
    assert ic.score_pairs(site(note_moyenne=4.8, nb_avis=5))[4] is True
    assert ic.score_pairs(site(note_moyenne=4.8, nb_avis=1))[4] is False   # pas assez d'avis
    assert ic.score_pairs(site(note_moyenne=3.5, nb_avis=20))[4] is False  # pas assez bien note


def test_absence_d_avis_donne_note_neutre():
    note, details, alertes, vetos, badge = ic.score_pairs(site(note_moyenne=None, nb_avis=0))
    assert details["avis"] == ic.NOTE_PAIRS_NEUTRE and badge is False and vetos == []


def test_logistique_de_survie():
    assert ic.score_pairs(site(pique_nique_couvert=None, consignes=None))[1]["logistique"] is None
    assert ic.score_pairs(site(pique_nique_couvert=True, consignes=False))[1]["logistique"] == 60
    assert ic.score_pairs(site(pique_nique_couvert=True, consignes=True))[1]["logistique"] == 100


def test_adequation_pedagogique():
    assert ic.score_pairs(site(themes=["histoire"]), "Histoire")[1]["adequation"] == 100
    assert ic.score_pairs(site(themes="art;science"), "histoire")[1]["adequation"] == ic.NOTE_HORS_THEME
    assert ic.score_pairs(site(themes=["histoire"]), None)[1]["adequation"] is None


# ---------- Proprietes generales ----------

def test_score_toujours_entre_0_et_100():
    for effectif, options, dist, bus in itertools.product(
            [1, 25, 50], [0, 10, 30], [100, 1500, 4000], [False, True]):
        r = ic.calculer_indice(TRAIN_MOYEN, site(distance_m=dist, bus_unique=bus),
                               effectif, options)
        assert 0 <= r["score"] <= 100


def test_un_veto_ne_donne_jamais_orange_ou_vert():
    r = ic.calculer_indice(TRAIN_PARFAIT, SITE_PROCHE, effectif=60, options_actives=0)
    assert r["bloque"] and r["couleur"] == "rouge" and r["score"] <= ic.PLAFOND_SI_VETO


def test_plus_d_options_ne_peut_pas_ameliorer_le_score():
    scores = [ic.calculer_indice(TRAIN_PARFAIT, SITE_PROCHE, 25, opt)["score"]
              for opt in range(0, 30, 5)]
    assert scores == sorted(scores, reverse=True)


def test_resultat_serialisable_en_json_avec_les_bonnes_cles():
    r = ic.calculer_indice(TRAIN_MOYEN, SITE_PROCHE, 25, 0)
    json.dumps(r)   # ne doit pas lever d'erreur
    for cle in ("score", "couleur", "bloque", "vetos", "alertes", "message",
                "composantes", "point_faible", "badge_coup_de_coeur"):
        assert cle in r
    assert set(r["composantes"]) == {"fiabilite", "faisabilite", "capacite", "pairs"}
    for pilier in r["composantes"].values():
        assert {"note", "poids", "points", "details"} <= set(pilier)


def test_les_points_des_piliers_somment_au_score():
    r = ic.calculer_indice(TRAIN_MOYEN, SITE_PROCHE, 25, 0, theme_projet="histoire")
    total = sum(c["points"] for c in r["composantes"].values())
    assert abs(total - r["score"]) <= 1.0   # tolerance d'arrondi


def test_le_message_explique_un_blocage():
    r = ic.calculer_indice(TRAIN_PARFAIT, SITE_PROCHE, effectif=35, options_actives=20)
    assert r["message"].startswith("Trajet bloque")
    assert "55" in r["message"]     # 35 + 20 voyageurs, annonces clairement


def test_aucun_detail_d_options_des_autres_ecoles():
    r = ic.calculer_indice(TRAIN_PARFAIT, SITE_PROCHE, effectif=25, options_actives=10)
    assert "ecole" not in json.dumps(r, ensure_ascii=False).lower()


# ---------- Chargement Data_Hackathon.csv (format reel) ----------

ENTETE = ("Année;Mois;N° Train;Axe;Origine / Destination;Circ Prévues Théorique;"
          "Circ Prévues réalisé;Frequentation;Nombre de retards PFP;Taux régularité du train;"
          "Nombre de suppressions;Taux SUPP;Taux de respect de l'emport;"
          "Nombre d'incidents générés;Nombre de trains impactés;Nombre de ventes;"
          "Minutes perdues;\n")


def ecrire_csv_reel(tmp_path):
    chemin = tmp_path / "Data_Hackathon.csv"
    chemin.write_text(
        ENTETE
        # train 8601 : mois 1 sans suppression (Taux SUPP vide), mois 2 avec 10 suppressions
        + "2026;janvier;8601;TOULOUSE - ALBI;TOULOUSE MATABIAU / ALBI;20;20;120,5;0;95,00%;0;;89,50%;0;0;10;0;\n"
        + "2026;février;8601;TOULOUSE - ALBI;TOULOUSE MATABIAU / ALBI;120;100;140;5;85,00%;10;10,00%;90,00%;0;0;;0;\n"
        # train 8777 : calme et parfait
        + "2026;janvier;8777;TOULOUSE - FOIX;TOULOUSE MATABIAU / FOIX;10;10;40;0;98,00%;0;;95,00%;0;0;3;0;\n"
        # train 8888 : 22 suppressions pour 20 circulations realisees => 110 % dans le fichier
        + "2026;mars;8888;TOULOUSE - LUCHON;TOULOUSE MATABIAU / LUCHON;42;20;50;0;80,00%;22;110,00%;70,00%;0;0;;0;\n",
        encoding="utf-8-sig")
    return str(chemin)


def test_chargement_format_reel_trois_trains(tmp_path):
    profils = ic.charger_profils_trains(ecrire_csv_reel(tmp_path))
    assert set(profils) == {"8601", "8777", "8888"}


def test_regularite_ponderee_par_les_circulations_realisees(tmp_path):
    p = ic.charger_profils_trains(ecrire_csv_reel(tmp_path))["8601"]
    attendu = (95 * 20 + 85 * 100) / 120
    assert abs(p["regularite_pct"] - attendu) < 1e-6      # et non (95+85)/2 = 90


def test_taux_de_suppression_calcule_sur_les_compteurs_pas_sur_la_colonne_vide(tmp_path):
    p = ic.charger_profils_trains(ecrire_csv_reel(tmp_path))["8601"]
    # 10 suppressions / 120 circulations realisees = 8.33 %
    # (une moyenne de 'Taux SUPP' ignorerait le mois vide et donnerait 10 %)
    assert abs(p["suppression_pct"] - 100 * 10 / 120) < 1e-6


def test_taux_de_suppression_superieur_a_100_est_plafonne(tmp_path):
    p = ic.charger_profils_trains(ecrire_csv_reel(tmp_path))["8888"]
    assert p["suppression_pct"] == 100.0


def test_train_sans_suppression_a_un_taux_nul(tmp_path):
    assert ic.charger_profils_trains(ecrire_csv_reel(tmp_path))["8777"]["suppression_pct"] == 0.0


def test_stabilite_de_l_offre(tmp_path):
    p = ic.charger_profils_trains(ecrire_csv_reel(tmp_path))["8601"]
    assert abs(p["stabilite_pct"] - 100 * 120 / 140) < 1e-6


def test_percentile_de_frequentation(tmp_path):
    profils = ic.charger_profils_trains(ecrire_csv_reel(tmp_path))
    assert profils["8601"]["frequentation_percentile"] > profils["8777"]["frequentation_percentile"]
    assert all(0 <= p["frequentation_percentile"] <= 1 for p in profils.values())


def test_colonne_parasite_finale_ne_gene_pas_et_l_axe_est_conserve(tmp_path):
    p = ic.charger_profils_trains(ecrire_csv_reel(tmp_path))["8601"]
    assert p["axe"] == "TOULOUSE - ALBI" and p["nb_mois"] == 2


def test_variante_du_symbole_numero_et_taux_en_fraction(tmp_path):
    chemin = tmp_path / "data.csv"
    chemin.write_text(
        "Nº Train;Circ Prévues Théorique;Circ Prévues réalisé;Frequentation;"
        "Taux régularité du train;Nombre de suppressions\n"
        "1;10;10;10;0,95;1\n",
        encoding="utf-8")
    p = ic.charger_profils_trains(str(chemin))["1"]
    assert abs(p["regularite_pct"] - 95.0) < 1e-9
    assert abs(p["suppression_pct"] - 10.0) < 1e-9


def test_un_profil_charge_alimente_le_calcul(tmp_path):
    profil = ic.charger_profils_trains(ecrire_csv_reel(tmp_path))["8777"]
    r = ic.calculer_indice(profil, SITE_PROCHE, effectif=25, options_actives=0)
    assert r["couleur"] in ("vert", "orange")


# ---------- Chargement du detail de desserte ----------

def ecrire_desserte(tmp_path):
    chemin = tmp_path / "desserte.csv"
    chemin.write_text(
        "Date;Numéro de circulation;Heure d'arrivée;Heure de départ;Libellé arrêt;Code arrêt;Ordre desserte\n"
        "30/4/2026;872605;12:00:00;12:00:00;Toulouse Matabiau;StopPoint:OCETrain TER-87611004;0\n"
        "30/4/2026;872605;12:04:00;12:06:00;Saint-Agne;StopPoint:OCETrain TER-87611301;1\n"
        "30/4/2026;872605;12:20:00;12:20:00;Muret;StopPoint:OCETrain TER-87611038;3\n"
        "1/5/2026;872605;13:20:00;13:20:00;Muret;StopPoint:OCETrain TER-87611038;3\n"
        "30/4/2026;111;09:00:00;09:00:00;Albi Ville;StopPoint:OCETrain TER-1;0\n",
        encoding="utf-8-sig")
    return str(chemin)


def test_chargement_desserte_et_heure_d_arrivee(tmp_path):
    d = ic.charger_desserte(ecrire_desserte(tmp_path))
    assert ic.heure_arrivee_en_gare(d, 872605, "2026-04-30", "Muret") == 12 * 60 + 20
    assert ic.heure_arrivee_en_gare(d, 872605, "2026-05-01", "MURET") == 13 * 60 + 20
    assert ic.heure_arrivee_en_gare(d, "872605", "2026-04-30", "Saint Agne") == 12 * 60 + 4


def test_heure_d_arrivee_introuvable_renvoie_none(tmp_path):
    d = ic.charger_desserte(ecrire_desserte(tmp_path))
    assert ic.heure_arrivee_en_gare(d, 872605, "2026-04-30", "Gare inconnue") is None
    assert ic.heure_arrivee_en_gare(d, 999999, "2026-04-30", "Muret") is None
    assert ic.heure_arrivee_en_gare(d, 872605, "2026-06-01", "Muret") is None


def test_trains_eligibles_et_filtre(tmp_path):
    chemin = ecrire_desserte(tmp_path)
    assert ic.trains_eligibles(ic.charger_desserte(chemin)) == {"872605", "111"}
    seul = ic.charger_desserte(chemin, trains_utiles={"872605"})
    assert ic.trains_eligibles(seul) == {"872605"}


def test_horaire_de_la_desserte_alimente_la_marge(tmp_path):
    d = ic.charger_desserte(ecrire_desserte(tmp_path))
    arrivee = ic.heure_arrivee_en_gare(d, 872605, "2026-04-30", "Muret")
    r = ic.calculer_indice(TRAIN_PARFAIT, SITE_PROCHE, 25, 0,
                           heure_arrivee_gare=arrivee, heure_debut_activite="13:30")
    assert not r["bloque"]
    r2 = ic.calculer_indice(TRAIN_PARFAIT, SITE_PROCHE, 25, 0,
                            heure_arrivee_gare=arrivee, heure_debut_activite="12:25")
    assert r2["bloque"]
