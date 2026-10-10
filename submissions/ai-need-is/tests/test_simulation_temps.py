import pandas as pd
import pytest

from crise.preparation.jointure import construire_points_pas
from crise.simulation.moteur import (
    comparer_simulations,
    derouler_horloge,
    lancer_simulation,
    suivre_resolutions,
)


def _pannes() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id_incident": "TOT",
                "latitude": 43.6,
                "longitude": 1.44,
                "date_incident": pd.Timestamp("2016-01-09 14:00"),
            },
            {
                "id_incident": "PLUS_TARD",
                "latitude": 43.7,
                "longitude": 1.50,
                "date_incident": pd.Timestamp("2016-01-09 14:45"),
            },
            {
                "id_incident": "SANS_LIEU",
                "latitude": None,
                "longitude": None,
                "date_incident": pd.Timestamp("2016-01-09 14:00"),
            },
        ]
    )


def test_panne_plus_tardive_absente_au_premier_pas() -> None:
    historique = derouler_horloge(_pannes(), pas_min=30, nb_pas=3)

    assert historique[0]["ouvertes"] == ["TOT"]
    assert "PLUS_TARD" not in historique[0]["ouvertes"]
    assert "PLUS_TARD" not in historique[1]["ouvertes"]
    assert "PLUS_TARD" in historique[2]["ouvertes"]
    assert historique[2]["nouvelles"] == ["PLUS_TARD"]


def test_panne_sans_coordonnees_n_apparait_pas() -> None:
    historique = derouler_horloge(_pannes(), pas_min=30, nb_pas=1)

    assert "SANS_LIEU" not in historique[0]["ouvertes"]


def test_lancer_simulation_conserve_l_historique() -> None:
    equipes = pd.DataFrame([{"id_equipe": "SITE_01_1"}])
    resultat = lancer_simulation(
        _pannes(),
        equipes,
        strategie="distance",
        pas_min=30,
        nb_pas=2,
        coeff_detour=1.3,
        vitesse_kmh=60,
    )

    assert len(resultat["pas"]) == 2
    assert resultat["pas"][0]["ouvertes"] == ["TOT"]
    assert resultat["nb_equipes"] == 1


def test_equipe_en_reparation_n_est_pas_renvoyee() -> None:
    pannes = pd.DataFrame(
        [
            {
                "id_incident": "A",
                "latitude": 43.6,
                "longitude": 1.44,
                "nb_clients": 50,
                "duree_heures": 1.0,
                "date_incident": pd.Timestamp("2016-01-09 14:00"),
            },
            {
                "id_incident": "B",
                "latitude": 44.0,
                "longitude": 1.0,
                "nb_clients": 5,
                "duree_heures": 1.0,
                "date_incident": pd.Timestamp("2016-01-09 14:00"),
            },
        ]
    )
    equipes = pd.DataFrame(
        [
            {
                "id_equipe": "E1",
                "id_site": "S1",
                "commune": "Depart",
                "latitude": 40.0,
                "longitude": 0.0,
                "disponible": True,
            }
        ]
    )
    resultat = lancer_simulation(
        pannes,
        equipes,
        strategie="distance",
        pas_min=30,
        nb_pas=3,
        coeff_detour=1.0,
        vitesse_kmh=1_000_000,
    )

    assert resultat["pas"][0]["affectations"][0]["id_incident"] == "A"
    assert resultat["pas"][0]["equipes"][0]["etat"] == "en_mission"
    assert resultat["pas"][1]["affectations"] == []
    assert resultat["pas"][1]["equipes"][0]["mission_id_incident"] == "A"
    assert resultat["pas"][2]["equipes"][0]["latitude"] == 43.6
    assert resultat["pas"][2]["equipes"][0]["longitude"] == 1.44


# ---------------------------------------------------------------------------
# Tests Feature 3 — Règle 12 h / 11 h
# ---------------------------------------------------------------------------

def _equipe_proche() -> pd.DataFrame:
    """Équipe positionnée au même endroit que les incidents (trajet ≈ 0 h)."""
    return pd.DataFrame(
        [
            {
                "id_equipe": "E1",
                "id_site": "S1",
                "commune": "Local",
                "latitude": 43.6,
                "longitude": 1.44,
                "disponible": True,
            }
        ]
    )


def test_mission_depassant_limite_travail_refusee() -> None:
    """Une mission dont trajet + réparation > heures restantes est refusée."""
    # L'équipe a déjà 11 h travaillées ; la prochaine mission dure 2 h → refus.
    pannes = pd.DataFrame(
        [
            {
                "id_incident": "X",
                "latitude": 43.6,
                "longitude": 1.44,
                "nb_clients": 10,
                "duree_heures": 2.0,
                "date_incident": pd.Timestamp("2016-01-09 14:00"),
            }
        ]
    )
    equipes = pd.DataFrame(
        [
            {
                "id_equipe": "E1",
                "id_site": "S1",
                "commune": "Local",
                "latitude": 43.6,
                "longitude": 1.44,
                "disponible": True,
                # 11 h déjà travaillées ; limite = 12 h → mission de 2 h refusée
                "heures_travaillees": 11.0,
            }
        ]
    )
    resultat = lancer_simulation(
        pannes,
        equipes,
        strategie="distance",
        pas_min=30,
        nb_pas=2,
        coeff_detour=1.0,
        vitesse_kmh=1_000_000,
        duree_max_h=12.0,
        repos_h=11.0,
    )

    # L'équipe ne doit pas avoir démarré de mission
    for pas in resultat["pas"]:
        assert pas["equipes"][0]["etat"] != "en_mission", (
            f"L'équipe ne devrait pas être en mission au pas {pas['pas']}"
        )


def test_equipe_passe_au_repos_apres_12h_puis_revient_libre() -> None:
    """
    Scénario :
      - L'équipe a déjà 10 h travaillées.
      - Une mission de 2 h est acceptée (10 + 2 = 12 h, exactement la limite).
      - Dès la fin de la mission l'équipe passe en ``au_repos`` pour 11 h.
      - Après 11 h elle redevient ``libre`` avec compteur remis à zéro.

    Pas de 60 min, vitesse très élevée pour que le trajet soit négligeable.
    T0 = 14h00 | mission assignée à T0, durée 2 h → fin à 16h00 (pas 2).
    Repos 11 h → fin à 03h00 (pas 13). Pas 14 → libre.
    """
    pannes = pd.DataFrame(
        [
            {
                "id_incident": "Y",
                "latitude": 43.6,
                "longitude": 1.44,
                "nb_clients": 5,
                "duree_heures": 2.0,
                "date_incident": pd.Timestamp("2016-01-09 14:00"),
            }
        ]
    )
    equipes = pd.DataFrame(
        [
            {
                "id_equipe": "E1",
                "id_site": "S1",
                "commune": "Local",
                "latitude": 43.6,
                "longitude": 1.44,
                "disponible": True,
                "heures_travaillees": 10.0,
            }
        ]
    )
    # 26 pas de 60 min = 26 h depuis T0 (14h00 → 16h00 le lendemain)
    resultat = lancer_simulation(
        pannes,
        equipes,
        strategie="distance",
        pas_min=60,
        nb_pas=26,
        coeff_detour=1.0,
        vitesse_kmh=1_000_000,
        duree_max_h=12.0,
        repos_h=11.0,
    )

    # Pas 0 : la mission est assignée
    assert resultat["pas"][0]["equipes"][0]["etat"] == "en_mission"

    # Trouver le pas où la mission se termine (l'équipe passe au_repos)
    repos_pas = None
    for pas in resultat["pas"]:
        if pas["equipes"][0]["etat"] == "au_repos":
            repos_pas = pas["pas"]
            break
    assert repos_pas is not None, "L'équipe aurait dû passer en au_repos"

    # Trouver le premier pas où l'équipe est de nouveau libre
    libre_pas = None
    for pas in resultat["pas"]:
        if pas["pas"] > repos_pas and pas["equipes"][0]["etat"] == "libre":
            libre_pas = pas["pas"]
            break
    assert libre_pas is not None, "L'équipe aurait dû redevenir libre après le repos"

    # Le repos doit durer au moins 11 h (en pas de 60 min = 11 pas)
    assert libre_pas - repos_pas >= 11, (
        f"Durée de repos trop courte : {libre_pas - repos_pas} pas au lieu de ≥ 11"
    )

    # Le compteur doit être remis à zéro
    assert resultat["pas"][libre_pas]["equipes"][0]["heures_travaillees"] == 0.0


def test_panne_longue_confiee_a_une_equipe_qui_peut_la_finir() -> None:
    """
    L'équipe la plus proche a trop travaillé pour une réparation de 8 h.
    La panne doit partir vers une équipe plus lointaine mais reposée,
    au lieu d'être proposée sans fin à l'équipe fatiguée.
    """
    pannes = pd.DataFrame(
        [
            {
                "id_incident": "LONGUE",
                "latitude": 43.6,
                "longitude": 1.44,
                "nb_clients": 100,
                "duree_heures": 8.0,
                "date_incident": pd.Timestamp("2016-01-09 14:00"),
            }
        ]
    )
    equipes = pd.DataFrame(
        [
            {
                "id_equipe": "FATIGUEE",
                "latitude": 43.6,
                "longitude": 1.44,
                "disponible": True,
                "heures_travaillees": 5.0,
            },
            {
                "id_equipe": "REPOSEE",
                "latitude": 43.7,
                "longitude": 1.50,
                "disponible": True,
            },
        ]
    )
    resultat = lancer_simulation(
        pannes,
        equipes,
        strategie="distance",
        pas_min=45,
        nb_pas=2,
        coeff_detour=1.0,
        vitesse_kmh=60.0,
    )

    assert resultat["pas"][0]["affectations"][0]["id_equipe"] == "REPOSEE"
    etats = {e["id_equipe"]: e["etat"] for e in resultat["pas"][0]["equipes"]}
    assert etats == {"FATIGUEE": "libre", "REPOSEE": "en_mission"}


def test_equipes_sans_assez_d_heures_partent_en_repos_puis_reparent() -> None:
    """
    Toutes les équipes ont trop travaillé pour une panne de 8 h, sans atteindre 12 h.
    Elles doivent partir en repos, puis la panne doit être réparée après le repos.
    """
    pannes = pd.DataFrame(
        [
            {
                "id_incident": "LONGUE",
                "latitude": 43.6,
                "longitude": 1.44,
                "nb_clients": 100,
                "duree_heures": 8.0,
                "date_incident": pd.Timestamp("2016-01-09 14:00"),
            }
        ]
    )
    equipes = pd.DataFrame(
        [
            {
                "id_equipe": "E1",
                "latitude": 43.6,
                "longitude": 1.44,
                "disponible": True,
                "heures_travaillees": 6.0,
            }
        ]
    )
    resultat = lancer_simulation(
        pannes,
        equipes,
        strategie="distance",
        pas_min=60,
        nb_pas=22,
        coeff_detour=1.0,
        vitesse_kmh=1_000_000,
        duree_max_h=12.0,
        repos_h=11.0,
    )

    assert resultat["pas"][0]["equipes"][0]["etat"] == "au_repos"
    assert resultat["pas"][11]["equipes"][0]["etat"] == "en_mission"
    suivi = suivre_resolutions(resultat, pannes)
    assert suivi[-1]["resolues"] == ["LONGUE"]


def test_panne_trop_loin_pour_tous_n_envoie_personne_au_repos() -> None:
    """Si même une équipe reposée ne peut pas finir la panne, le repos ne sert à rien."""
    pannes = pd.DataFrame(
        [
            {
                "id_incident": "LOINTAINE",
                "latitude": 43.6,
                "longitude": 1.44,
                "duree_heures": 8.0,
                "date_incident": pd.Timestamp("2016-01-09 14:00"),
            }
        ]
    )
    equipes = pd.DataFrame(
        [
            {
                "id_equipe": "E1",
                "latitude": 48.85,
                "longitude": 2.35,
                "disponible": True,
                "heures_travaillees": 1.0,
            }
        ]
    )
    resultat = lancer_simulation(
        pannes,
        equipes,
        strategie="distance",
        pas_min=60,
        nb_pas=2,
        coeff_detour=1.3,
        vitesse_kmh=60.0,
    )

    assert resultat["pas"][-1]["equipes"][0]["etat"] == "libre"


# ---------------------------------------------------------------------------
# Règle 12 h / 11 h en amplitude, avec retour obligatoire au site
# ---------------------------------------------------------------------------

SITE = (43.0, 1.0)
POSTE = (43.5, 1.0)


def _vitesse_une_heure() -> float:
    """Vitesse pour que le trajet site → poste dure exactement 1 h (sans détour)."""
    from crise.geo.distance import calculer_distance_haversine

    return calculer_distance_haversine(*SITE, *POSTE)


def _panne_au_poste(duree_h: float, date: str = "2016-01-09 14:00") -> dict:
    return {
        "id_incident": "P",
        "latitude": POSTE[0],
        "longitude": POSTE[1],
        "nb_clients": 10,
        "duree_heures": duree_h,
        "date_incident": pd.Timestamp(date),
    }


def _equipe_au_site(heures: float = 0.0) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id_equipe": "E1",
                "latitude": SITE[0],
                "longitude": SITE[1],
                "disponible": True,
                "heures_travaillees": heures,
            }
        ]
    )


def test_le_retour_au_site_compte_dans_les_12h() -> None:
    """2 h déjà faites + 1 h aller + 8 h réparation + 1 h retour = 12 h : acceptée.
    Avec 2,5 h déjà faites, le retour ferait dépasser 12 h : refusée."""
    for heures, acceptee in ((2.0, True), (2.5, False)):
        resultat = lancer_simulation(
            pd.DataFrame([_panne_au_poste(8.0)]),
            _equipe_au_site(heures),
            strategie="distance",
            pas_min=30,
            nb_pas=1,
            coeff_detour=1.0,
            vitesse_kmh=_vitesse_une_heure(),
        )
        en_mission = resultat["pas"][0]["equipes"][0]["etat"] == "en_mission"
        assert en_mission == acceptee, f"{heures} h déjà faites"


def test_equipe_rentre_au_site_apres_reparation_puis_s_y_repose() -> None:
    """
    Mission de 2 h à 1 h du site (14 h → 17 h). Plus rien à faire : l'équipe rentre
    aussitôt au site (17 h → 18 h) en restant disponible, y attend, s'y repose avant
    12 h d'amplitude, puis est de nouveau libre au site après 11 h de repos.
    """
    resultat = lancer_simulation(
        pd.DataFrame([_panne_au_poste(2.0)]),
        _equipe_au_site(),
        strategie="distance",
        pas_min=30,
        nb_pas=60,
        coeff_detour=1.0,
        vitesse_kmh=_vitesse_une_heure(),
    )
    t0 = resultat["t0"]
    etats = [(pas["instant"], pas["equipes"][0]) for pas in resultat["pas"]]

    # Jamais plus de 12 h d'amplitude.
    assert all(equipe["heures_travaillees"] <= 12.0 + 1e-9 for _, equipe in etats)

    # Retour au site dès la fin de la réparation, sans attendre sur le poste.
    retours = [t for t in resultat["trajets"] if t["destination"] == "site"]
    assert len(retours) == 1
    assert retours[0]["motif"] == "disponible"
    assert retours[0]["depart"] == t0 + pd.Timedelta(hours=3)
    assert retours[0]["arrivee"] == t0 + pd.Timedelta(hours=4)
    etat_5h = next(equipe for instant, equipe in etats if instant == t0 + pd.Timedelta(hours=5))
    assert etat_5h["etat"] == "libre"
    assert (etat_5h["latitude"], etat_5h["longitude"]) == SITE

    repos = next(
        (instant, equipe) for instant, equipe in etats if equipe["etat"] == "au_repos"
    )
    assert repos[0] <= t0 + pd.Timedelta(hours=12)
    assert (repos[1]["latitude"], repos[1]["longitude"]) == SITE

    libre_apres = [
        (instant, equipe)
        for instant, equipe in etats
        if instant > repos[0] and equipe["etat"] == "libre"
    ]
    assert libre_apres, "L'équipe aurait dû redevenir libre après le repos"
    instant_libre, equipe_libre = libre_apres[0]
    assert instant_libre - repos[0] >= pd.Timedelta(hours=11) - pd.Timedelta(minutes=30)
    assert (equipe_libre["latitude"], equipe_libre["longitude"]) == SITE
    assert equipe_libre["heures_travaillees"] == 0.0


def test_equipe_en_retour_deroutee_vers_une_nouvelle_panne() -> None:
    """
    Après la réparation de P (fin à 16 h), l'équipe rentre au site (16 h → 17 h).
    À 16 h 30 une panne Q apparaît : l'équipe est déroutée depuis le milieu de son retour.
    """
    premiere = _panne_au_poste(1.0)
    milieu = ((SITE[0] + POSTE[0]) / 2, SITE[1])
    nouvelle = {
        **_panne_au_poste(1.0, "2016-01-09 16:30"),
        "id_incident": "Q",
        "latitude": milieu[0],
        "longitude": milieu[1] + 0.1,
    }
    resultat = lancer_simulation(
        pd.DataFrame([premiere, nouvelle]),
        _equipe_au_site(),
        strategie="distance",
        pas_min=30,
        nb_pas=8,
        coeff_detour=1.0,
        vitesse_kmh=_vitesse_une_heure(),
    )
    seize_h_30 = pd.Timestamp("2016-01-09 16:30")

    retour, vers_q = [t for t in resultat["trajets"] if t["depart"] >= pd.Timestamp("2016-01-09 16:00")]
    assert retour["destination"] == "site"
    assert retour["arrivee"] == seize_h_30
    assert retour["lat_arrivee"] == pytest.approx(milieu[0])
    assert vers_q["id_incident"] == "Q"
    assert vers_q["depart"] == seize_h_30
    assert vers_q["lat_depart"] == pytest.approx(milieu[0])


def test_l_attente_compte_dans_l_amplitude() -> None:
    """
    Première mission à 14 h, puis une panne de 4 h qui apparaît à 23 h.
    Après 9 h d'amplitude, aller + 4 h + retour dépasse 12 h : l'équipe ne la prend pas.
    """
    premiere = _panne_au_poste(1.0)
    tardive = {**_panne_au_poste(4.0, "2016-01-09 23:00"), "id_incident": "TARDIVE"}
    resultat = lancer_simulation(
        pd.DataFrame([premiere, tardive]),
        _equipe_au_site(),
        strategie="distance",
        pas_min=60,
        nb_pas=11,
        coeff_detour=1.0,
        vitesse_kmh=_vitesse_une_heure(),
    )

    affectees = [
        decision["id_incident"] for pas in resultat["pas"] for decision in pas["affectations"]
    ]
    assert affectees == ["P"]


# ---------------------------------------------------------------------------
# Tests Feature 4 — Exécution comparative des trois stratégies
# ---------------------------------------------------------------------------

def _pannes_multi() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id_incident": f"INC_{i}",
                "latitude": 43.6 + i * 0.1,
                "longitude": 1.44 + i * 0.05,
                "nb_clients": 10 * (i + 1),
                "duree_heures": 1.0,
                "date_incident": pd.Timestamp("2016-01-09 14:00"),
            }
            for i in range(4)
        ]
    )


def _equipes_multi() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id_equipe": f"EQ_{j}",
                "id_site": f"S_{j}",
                "commune": f"Ville_{j}",
                "latitude": 43.5 + j * 0.2,
                "longitude": 1.3 + j * 0.1,
                "disponible": True,
            }
            for j in range(3)
        ]
    )


def test_comparer_simulations_retourne_trois_historiques_distincts() -> None:
    """comparer_simulations retourne un résultat pour chaque stratégie."""
    resultats = comparer_simulations(
        pannes=_pannes_multi(),
        equipes=_equipes_multi(),
        pas_min=30,
        nb_pas=6,
        coeff_detour=1.3,
        vitesse_kmh=60.0,
        duree_max_h=12.0,
        repos_h=11.0,
    )

    assert set(resultats.keys()) == {"distance", "premier_arrive", "score_pondere", "ia_optimale"}
    for strategie, res in resultats.items():
        assert res["strategie"] == strategie
        assert len(res["pas"]) == 6
        assert res["nb_equipes"] == 3


def test_suivre_resolutions_passe_de_en_cours_a_resolue() -> None:
    """Une panne affectée est en cours, puis résolue ; ses clients sont alors rétablis."""
    pannes = pd.DataFrame(
        [
            {
                "id_incident": "Z",
                "latitude": 43.6,
                "longitude": 1.44,
                "nb_clients": 40,
                "duree_heures": 1.0,
                "date_incident": pd.Timestamp("2016-01-09 14:00"),
            }
        ]
    )
    resultat = lancer_simulation(
        pannes,
        _equipe_proche(),
        strategie="distance",
        pas_min=30,
        nb_pas=4,
        coeff_detour=1.0,
        vitesse_kmh=1_000_000,
    )

    suivi = suivre_resolutions(resultat, pannes)

    assert suivi[0]["en_cours"] == ["Z"]
    assert suivi[0]["clients_coupes"] == 40
    assert suivi[0]["clients_retablis"] == 0
    assert suivi[2]["resolues"] == ["Z"]
    assert suivi[2]["en_attente"] == [] and suivi[2]["en_cours"] == []
    assert suivi[2]["clients_retablis"] == 40
    assert suivi[3]["clients_retablis"] == 40


def test_construire_points_pas_colore_selon_le_statut() -> None:
    pannes = _pannes_multi()
    points = construire_points_pas(
        pannes,
        en_attente=["INC_0"],
        en_cours=["INC_1"],
        resolues=["INC_2"],
        equipes=[{"id_equipe": "EQ_0", "latitude": 43.5, "longitude": 1.3}],
    )

    statuts = dict(zip(points["libelle"], points["type"]))
    assert statuts == {
        "INC_0": "en attente",
        "INC_1": "en cours",
        "INC_2": "résolue",
        "EQ_0": "équipe",
    }


def test_comparer_simulations_historiques_coherents() -> None:
    """Chaque historique doit contenir uniquement les pannes localisables."""
    resultats = comparer_simulations(
        pannes=_pannes_multi(),
        equipes=_equipes_multi(),
        pas_min=30,
        nb_pas=4,
        coeff_detour=1.3,
        vitesse_kmh=60.0,
    )

    for strategie, res in resultats.items():
        for pas in res["pas"]:
            # Toutes les pannes ouvertes doivent être des identifiants valides
            ids_valides = {f"INC_{i}" for i in range(4)}
            assert set(pas["ouvertes"]).issubset(ids_valides), (
                f"Stratégie {strategie} : identifiant inconnu dans ouvertes"
            )
