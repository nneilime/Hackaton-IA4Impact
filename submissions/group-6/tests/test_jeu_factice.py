import pytest

from crise.factice import creer_etat_simulation_factice, creer_jeu_factice
from crise.models import (
    Affectation,
    Equipe,
    EtatEquipe,
    EtatIncident,
    EtatSimulation,
    Incident,
)


def test_models_enums_and_dataclasses():
    """Vérifie la conformité stricte des Enums et dataclasses avec les contrats §4."""
    assert EtatEquipe.DISPONIBLE.value == "disponible"
    assert EtatEquipe.TRAJET.value == "trajet"
    assert EtatEquipe.CHANTIER.value == "chantier"
    assert EtatEquipe.RETOUR.value == "retour"
    assert EtatEquipe.REPOS.value == "repos"
    assert EtatEquipe.HORS_SERVICE.value == "hors_service"

    assert EtatIncident.NON_APPARU.value == "non_apparu"
    assert EtatIncident.EN_ATTENTE.value == "en_attente"
    assert EtatIncident.AFFECTE.value == "affecte"
    assert EtatIncident.EN_COURS.value == "en_cours"
    assert EtatIncident.RESOLU.value == "resolu"

    aff = Affectation(id_equipe="E1", id_incident="I1")
    assert aff.explication == {}


def test_jeu_factice_structure(jeu_factice):
    """Vérifie que le jeu factice T2.1 comporte exactement 3 équipes et 6 incidents."""
    equipes, incidents = jeu_factice
    assert len(equipes) == 3, f"Attendu 3 équipes, obtenu {len(equipes)}"
    assert len(incidents) == 6, f"Attendu 6 incidents, obtenu {len(incidents)}"

    # Vérification des équipes
    ids_equipes = {eq.id_equipe for eq in equipes}
    assert len(ids_equipes) == 3
    for eq in equipes:
        assert isinstance(eq, Equipe)
        assert eq.etat == EtatEquipe.DISPONIBLE
        assert eq.t_debut_service == 0
        assert eq.t_libre == 0
        assert isinstance(eq.lat, float)
        assert isinstance(eq.lon, float)

    # Vérification des incidents
    ids_incidents = {inc.id_incident for inc in incidents}
    assert len(ids_incidents) == 6
    for inc in incidents:
        assert isinstance(inc, Incident)
        assert inc.etat == EtatIncident.EN_ATTENTE
        assert inc.duree_nominale in (120, 240, 480)
        assert inc.duree_reelle > 0
        assert inc.nb_clients > 0
        assert isinstance(inc.sensible, bool)
        assert isinstance(inc.lat, float)
        assert isinstance(inc.lon, float)


def test_jeu_factice_metier_properties(jeu_factice):
    """Vérifie la diversité métier du jeu factice (durées, sensibles, montagne/plaine, exemple A/B §5.3)."""
    equipes, incidents = jeu_factice

    durations = {inc.duree_nominale for inc in incidents}
    assert {120, 240, 480}.issubset(durations), (
        "Toutes les durées nominales (2h, 4h, 8h) doivent être représentées"
    )

    sensibles = [inc for inc in incidents if inc.sensible]
    assert len(sensibles) >= 1, "Au moins un incident doit être sensible"
    non_sensibles = [inc for inc in incidents if not inc.sensible]
    assert len(non_sensibles) >= 1, "Au moins un incident doit être non-sensible"

    # Vérification zone montagne (lat < 43.05 selon H1 / §5.2) vs plaine (lat >= 43.05)
    montagne = [inc for inc in incidents if inc.lat < 43.05]
    plaine = [inc for inc in incidents if inc.lat >= 43.05]
    assert len(montagne) >= 1, "Au moins un incident en zone montagne (lat < 43.05)"
    assert len(plaine) >= 1, "Au moins un incident en plaine (lat >= 43.05)"

    # Présence de l'exemple A/B du §5.3 (pour préparer T2.2)
    # Incident A: 150 clients, 8h (480 min)
    # Incident B: 50 clients, 2h (120 min)
    inc_a = next((i for i in incidents if i.nb_clients == 150 and i.duree_nominale == 480), None)
    inc_b = next((i for i in incidents if i.nb_clients == 50 and i.duree_nominale == 120), None)
    assert inc_a is not None, "L'incident A (150 clients, 8h) de l'exemple §5.3 doit être présent"
    assert inc_b is not None, "L'incident B (50 clients, 2h) de l'exemple §5.3 doit être présent"


def test_etat_simulation_factice():
    """Vérifie la création d'un EtatSimulation complet utilisable par Policy.decide."""
    etat = creer_etat_simulation_factice(t=60)
    assert isinstance(etat, EtatSimulation)
    assert etat.t == 60
    assert len(etat.equipes_disponibles) == 3
    assert len(etat.incidents_en_attente) == 6
    assert len(etat.toutes_equipes) == 3
    assert "alpha_sensible" in etat.params
    assert "beta_attente_par_h" in etat.params
    assert "amplitude_max_min" in etat.params
    assert "repos_min" in etat.params


def test_etat_simulation_factice_t_zero():
    """À t=0, seuls les incidents avec t_apparition == 0 doivent être en attente."""
    etat = creer_etat_simulation_factice(t=0)
    assert etat.t == 0
    assert len(etat.incidents_en_attente) == 3
    for inc in etat.incidents_en_attente:
        assert inc.t_apparition == 0


def test_etat_simulation_factice_custom_params():
    """Vérifie la personnalisation des paramètres sans effet de bord."""
    custom = {"alpha_sensible": 10.0, "beta_attente_par_h": 0.2}
    etat = creer_etat_simulation_factice(t=60, params=custom)
    assert etat.params["alpha_sensible"] == 10.0
    assert etat.params["beta_attente_par_h"] == 0.2

    # Vérifie que les appels suivants conservent les paramètres par défaut
    etat_defaut = creer_etat_simulation_factice(t=60)
    assert etat_defaut.params["alpha_sensible"] == 5.0


def test_jeu_factice_isolation():
    """Vérifie que la modification d'un jeu factice n'affecte pas les créations suivantes."""
    eqs1, incs1 = creer_jeu_factice()
    eqs1[0].lat = 99.9
    incs1[0].nb_clients = 9999

    eqs2, incs2 = creer_jeu_factice()
    assert eqs2[0].lat != 99.9
    assert incs2[0].nb_clients != 9999


def test_import_crise_package_directly():
    """Vérifie que crise est importable directement sans préfixe src."""
    from crise.policies import Policy, WSPTHongroisPolicy
    assert hasattr(Policy, "decide")
    assert issubclass(WSPTHongroisPolicy, Policy)


def test_postes_and_sites_factices():
    """Vérifie l'existence et la cohérence des Postes et Sites factices (§4.1)."""
    from crise.factice import creer_postes_factices, creer_sites_factices

    postes = creer_postes_factices()
    sites = creer_sites_factices()
    assert len(postes) == 6
    assert len(sites) == 3

    # Cohérence avec les équipes
    eqs, incs = creer_jeu_factice(t=60)
    site_ids = {s.id_site for s in sites}
    for eq in eqs:
        assert eq.id_site in site_ids

    # Cohérence avec les incidents
    poste_ids = {p.id_poste for p in postes}
    for inc in incs:
        assert inc.id_poste in poste_ids


def test_incidents_lifecycle_and_appearance():
    """Vérifie le cycle de vie des incidents selon t_apparition et t."""
    from crise.factice import creer_incidents_factices

    # À t=0, les incidents avec t_apparition > 0 doivent avoir etat NON_APPARU
    incs_t0 = creer_incidents_factices(t=0)
    apparus = [inc for inc in incs_t0 if inc.t_apparition == 0]
    futurs = [inc for inc in incs_t0 if inc.t_apparition > 0]
    assert len(apparus) == 3
    assert len(futurs) == 3
    for inc in apparus:
        assert inc.etat == EtatIncident.EN_ATTENTE
    for inc in futurs:
        assert inc.etat == EtatIncident.NON_APPARU

    # À t=60, tous ont apparu et sont EN_ATTENTE
    incs_t60 = creer_incidents_factices(t=60)
    assert all(inc.etat == EtatIncident.EN_ATTENTE for inc in incs_t60)


def test_trajet_min_calcul():
    """Vérifie le calcul conforme aux règles métier du §5.2."""
    from crise.trajet import calculer_trajet_min

    # Même point -> durée nulle
    assert calculer_trajet_min(43.604, 1.443, 43.604, 1.443) == pytest.approx(0.0)

    # Foix (42.964, 1.606) -> Toulouse (43.604, 1.443, destination en plaine lat >= 43.05, 55 km/h)
    # Vol d'oiseau ≈ 72.4 km -> routier ≈ 94.1 km -> ≈ 102.6 min (≈ 1h42)
    t_foix_tlse = calculer_trajet_min(42.964, 1.606, 43.604, 1.443)
    assert 98.0 <= t_foix_tlse <= 106.0

    # Toulouse -> Ax-les-Thermes (lat 42.720 < 43.05, destination en montagne, 35 km/h)
    t_tlse_ax = calculer_trajet_min(43.604, 1.443, 42.720, 1.810)
    assert t_tlse_ax > t_foix_tlse


def test_exemple_ab_smith_rule_fixture():
    """Vérifie la fixture dédiée à l'exemple A/B du §5.3 (1 équipe, 2 incidents, trajet nul)."""
    from crise.factice import creer_etat_exemple_ab, creer_jeu_exemple_ab

    eq, inc_a, inc_b = creer_jeu_exemple_ab()
    assert eq.lat == inc_a.lat == inc_b.lat
    assert eq.lon == inc_a.lon == inc_b.lon
    assert inc_a.nb_clients == 150 and inc_a.duree_nominale == 480
    assert inc_b.nb_clients == 50 and inc_b.duree_nominale == 120

    # Règle de Smith (WSPT) : ratio N / duree
    ratio_a = inc_a.nb_clients / inc_a.duree_nominale  # 150 / 480 = 0.3125
    ratio_b = inc_b.nb_clients / inc_b.duree_nominale  # 50 / 120 = 0.4167
    assert ratio_b > ratio_a, "La règle de Smith exige que B soit traité avant A"

    # Calcul Σ N*T
    # Ordre A puis B : 150*8 + 50*10 = 1700
    # Ordre B puis A : 50*2 + 150*10 = 1600
    cout_ab = 150 * 8 + 50 * (8 + 2)
    cout_ba = 50 * 2 + 150 * (2 + 8)
    assert cout_ab == 1700
    assert cout_ba == 1600

    etat_ab = creer_etat_exemple_ab()
    assert len(etat_ab.equipes_disponibles) == 1
    assert len(etat_ab.incidents_en_attente) == 2


def test_edge_cases_fixtures():
    """Vérifie les états limites (amplitude épuisée, aucun incident, équipes occupées)."""
    from crise.factice import (
        creer_etat_simulation_amplitude_epuisee,
        creer_etat_simulation_aucun_incident,
        creer_etat_simulation_equipes_indisponibles,
    )

    etat_vide = creer_etat_simulation_aucun_incident(t=60)
    assert len(etat_vide.incidents_en_attente) == 0
    assert len(etat_vide.equipes_disponibles) == 3

    etat_epuise = creer_etat_simulation_amplitude_epuisee(t=720)
    assert etat_epuise.t == 720
    for eq in etat_epuise.equipes_disponibles:
        amplitude_restante = etat_epuise.params["amplitude_max_min"] - (etat_epuise.t - eq.t_debut_service)
        assert amplitude_restante <= 0

    etat_indispo = creer_etat_simulation_equipes_indisponibles()
    assert len(etat_indispo.equipes_disponibles) == 0
    assert len(etat_indispo.toutes_equipes) == 3
    for eq in etat_indispo.toutes_equipes:
        assert eq.etat in (EtatEquipe.CHANTIER, EtatEquipe.REPOS, EtatEquipe.HORS_SERVICE)


def test_policy_decide_abstract_contract():
    """Vérifie que Policy peut être sous-classée et exécutée avec decide(etat, trajet_min)."""
    from crise.factice import calculer_trajet_min
    from crise.models import Affectation
    from crise.policies.base import Policy

    class DummyPolicy(Policy):
        nom = "dummy"

        def decide(self, etat, trajet_min):
            res = []
            if etat.equipes_disponibles and etat.incidents_en_attente:
                res.append(Affectation(
                    id_equipe=etat.equipes_disponibles[0].id_equipe,
                    id_incident=etat.incidents_en_attente[0].id_incident,
                    explication={"score": 1.0},
                ))
            return res

    p = DummyPolicy()
    etat = creer_etat_simulation_factice(t=60)
    affs = p.decide(etat, calculer_trajet_min)
    assert len(affs) == 1
    assert affs[0].id_equipe == "SITE_TOULOUSE_E1"
    assert affs[0].id_incident == "INC_001"


def test_charger_parametres_defaut():
    """Vérifie le chargement des paramètres depuis config/default.yaml."""
    from crise.factice import charger_parametres_defaut

    params = charger_parametres_defaut()
    assert params["alpha_sensible"] == 5.0
    assert params["beta_attente_par_h"] == 0.1
    assert params["amplitude_max_min"] == 720
    assert params["vitesse_plaine_kmh"] == 55.0
    assert params["vitesse_montagne_kmh"] == 35.0
    assert params["coef_detour"] == 1.3


def test_calculer_score_wspt_properties():
    """Vérifie les propriétés mathématiques et contraintes du score WSPT (§5.3)."""
    from crise.factice import (
        calculer_score_wspt,
        creer_incidents_factices,
        creer_jeu_exemple_ab,
    )

    eq, inc_a, inc_b = creer_jeu_exemple_ab()

    # Score A/B avec trajet nul
    score_a = calculer_score_wspt(eq, inc_a, t=0, trajet_func=lambda *args: 0.0)
    score_b = calculer_score_wspt(eq, inc_b, t=0, trajet_func=lambda *args: 0.0)

    assert score_a == pytest.approx(150.0 / 480.0)  # 0.3125
    assert score_b == pytest.approx(50.0 / 120.0)   # 0.41667
    assert score_b > score_a, (
        "Le score de B (50 clients / 2h) doit être strictement supérieur à celui de A (150 clients / 8h)"
    )

    # Boost client sensible (alpha = 5.0 -> poids multiplié par 6)
    incs = creer_incidents_factices(t=60)
    inc_sensible = next(i for i in incs if i.sensible)  # Muret clinique (80 clients, 240 min)

    score_sens = calculer_score_wspt(eq, inc_sensible, t=15, trajet_func=lambda *args: 0.0)
    # w = 80 * (1 + 5) = 480 -> 480 / 240 = 2.0
    assert score_sens == pytest.approx(480.0 / 240.0)

    # Infaisabilité : amplitude restante dépassée -> -inf
    # Si t=660, amplitude restante = 720 - 660 = 60 min. Pour inc_b (120 min), 120 > 60
    score_infaisable = calculer_score_wspt(eq, inc_b, t=660, trajet_func=lambda *args: 0.0)
    assert score_infaisable == -float("inf")

    # Infaisabilité : équipe non disponible (en chantier) -> -inf
    eq.etat = EtatEquipe.CHANTIER
    score_occupe = calculer_score_wspt(eq, inc_b, t=0, trajet_func=lambda *args: 0.0)
    assert score_occupe == -float("inf")


def test_affectation_hongrois_sur_jeu_factice():
    """Valide la résolution hongroise scipy sur le jeu factice à t=0 pour préparer T2.2."""
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    from crise.factice import calculer_score_wspt, creer_etat_simulation_factice

    etat = creer_etat_simulation_factice(t=0)
    equipes = etat.equipes_disponibles
    incidents = etat.incidents_en_attente

    assert len(equipes) == 3
    assert len(incidents) == 3

    # Matrice des scores (3 équipes x 3 incidents)
    S = np.zeros((len(equipes), len(incidents)))
    for i, eq in enumerate(equipes):
        for j, inc in enumerate(incidents):
            S[i, j] = calculer_score_wspt(eq, inc, t=0)

    # linear_sum_assignment minimise, donc on passe -S pour maximiser la somme des scores
    row_ind, col_ind = linear_sum_assignment(-S)

    affectations = {
        equipes[r].id_equipe: incidents[c].id_incident
        for r, c in zip(row_ind, col_ind, strict=True)
    }

    # Toulouse prend INC_002 (ratio WSPT élevé : 50 clients / 2h)
    assert affectations["SITE_TOULOUSE_E1"] == "INC_002"
    # Muret prend INC_001 (150 clients / 8h)
    assert affectations["SITE_MURET_E1"] == "INC_001"
    # Foix prend INC_005 (Tarascon hôpital, sensible, proximité immédiate en Ariège)
    assert affectations["SITE_FOIX_E1"] == "INC_005"


def test_calculer_score_wspt_non_en_attente_or_futur():
    """Vérifie que les incidents non EN_ATTENTE ou futurs sont strictement rejetés (-inf)."""
    from copy import deepcopy

    from crise.factice import calculer_score_wspt, creer_jeu_factice

    equipes, incidents = creer_jeu_factice(t=60)
    eq = equipes[0]
    inc = deepcopy(incidents[0])

    etats_invalides = (
        EtatIncident.RESOLU,
        EtatIncident.AFFECTE,
        EtatIncident.EN_COURS,
        EtatIncident.NON_APPARU,
    )
    for etat_invalide in etats_invalides:
        inc.etat = etat_invalide
        score = calculer_score_wspt(eq, inc, t=60)
        assert score == -float("inf"), f"L'état {etat_invalide} doit donner un score de -inf"

    # Incident futur (t_apparition > t)
    inc.etat = EtatIncident.EN_ATTENTE
    inc.t_apparition = 100
    score_futur = calculer_score_wspt(eq, inc, t=60)
    assert score_futur == -float("inf"), "Un incident futur (t_apparition > t) doit donner -inf"


def test_calculer_trajet_min_multiplicateur_invalide():
    """Vérifie que multiplicateur_zone <= 0 lève une ValueError explicite."""
    from crise.trajet import calculer_trajet_min

    with pytest.raises(ValueError, match="multiplicateur_zone doit être strictement positif"):
        calculer_trajet_min(43.604, 1.443, 43.460, 1.326, multiplicateur_zone=0.0)

    with pytest.raises(ValueError, match="multiplicateur_zone doit être strictement positif"):
        calculer_trajet_min(43.604, 1.443, 43.460, 1.326, multiplicateur_zone=-1.5)


def test_distance_haversine_km_proprietes():
    """Vérifie les propriétés géométriques fondamentales de distance_haversine_km."""
    from crise.trajet import distance_haversine_km

    # Symétrie d(A, B) == d(B, A)
    d_ab = distance_haversine_km(43.604, 1.443, 42.964, 1.606)
    d_ba = distance_haversine_km(42.964, 1.606, 43.604, 1.443)
    assert d_ab == pytest.approx(d_ba)
    assert 71.0 <= d_ab <= 74.0

    # Inégalité triangulaire d(A, C) <= d(A, B) + d(B, C)
    lat_c, lon_c = 43.460, 1.326
    d_ac = distance_haversine_km(43.604, 1.443, lat_c, lon_c)
    d_cb = distance_haversine_km(lat_c, lon_c, 42.964, 1.606)
    assert d_ab <= (d_ac + d_cb) + 1e-6


def test_matrice_trajet_and_vectorisation():
    """Vérifie la concordance entre matrice_trajet et la version vectorisée numpy (§5.2)."""
    import numpy as np

    from crise.factice import creer_equipes_factices, creer_incidents_factices
    from crise.trajet import matrice_trajet, matrice_trajet_vectorisee

    equipes = creer_equipes_factices()
    incidents = creer_incidents_factices(t=60)

    m_standard = matrice_trajet(equipes, incidents)
    m_vectorisee = matrice_trajet_vectorisee(equipes, incidents)

    assert isinstance(m_vectorisee, np.ndarray)
    assert m_vectorisee.shape == (3, 6)
    assert np.allclose(m_standard, m_vectorisee, atol=1e-5)

    # Cas limites séquences vides
    assert matrice_trajet([], incidents) == []
    assert matrice_trajet_vectorisee([], incidents).shape == (0, 6)
    assert matrice_trajet(equipes, []) == [[], [], []]
    assert matrice_trajet_vectorisee(equipes, []).shape == (3, 0)


def test_resoudre_affectation_hongrois_rectangulaire_et_faisabilite():
    """Vérifie la robustesse de resoudre_affectation_hongrois sur matrices rectangulaires et infaisables."""
    from crise.factice import (
        creer_etat_simulation_amplitude_epuisee,
        creer_etat_simulation_factice,
        resoudre_affectation_hongrois,
    )

    # Cas 1 : Plus d'incidents que d'équipes (3 équipes, 6 incidents à t=60)
    etat_rect = creer_etat_simulation_factice(t=60)
    affs_rect = resoudre_affectation_hongrois(etat_rect)
    assert len(affs_rect) == 3
    equipes_assignees = {a.id_equipe for a in affs_rect}
    assert len(equipes_assignees) == 3  # Chaque équipe a 1 incident distinct

    # Cas 2 : Plus d'équipes que d'incidents (3 équipes, 1 incident en attente)
    etat_mono = creer_etat_simulation_factice(t=60)
    etat_mono.incidents_en_attente = [etat_mono.incidents_en_attente[0]]
    affs_mono = resoudre_affectation_hongrois(etat_mono)
    assert len(affs_mono) == 1
    assert affs_mono[0].id_incident == "INC_001"

    # Cas 3 : Une équipe avec amplitude épuisée (ne doit pas lever de ValueError dans linear_sum_assignment)
    etat_mixte = creer_etat_simulation_factice(t=0)
    # On épuise l'amplitude de l'équipe 0
    etat_mixte.equipes_disponibles[0].t_debut_service = -720
    etat_mixte.t = 0
    affs_mixte = resoudre_affectation_hongrois(etat_mixte)
    # L'équipe 0 ne doit pas être affectée
    ids_assignees = {a.id_equipe for a in affs_mixte}
    assert etat_mixte.equipes_disponibles[0].id_equipe not in ids_assignees

    # Cas 4 : Toutes amplitudes épuisées -> 0 affectation sans crash
    etat_epuise = creer_etat_simulation_amplitude_epuisee(t=720)
    affs_epuise = resoudre_affectation_hongrois(etat_epuise)
    assert affs_epuise == []


def test_wspt_hongrois_policy_decide():
    """Vérifie que WSPTHongroisPolicy implémente l'interface Policy et produit des Affectations valides."""
    from crise.factice import creer_etat_simulation_factice
    from crise.policies import WSPTHongroisPolicy
    from crise.trajet import calculer_trajet_min

    policy = WSPTHongroisPolicy()
    assert policy.nom == "wspt_hongrois"

    etat = creer_etat_simulation_factice(t=0)
    affectations = policy.decide(etat, calculer_trajet_min)
    assert len(affectations) == 3
    for aff in affectations:
        assert aff.id_equipe.startswith("SITE_")
        assert aff.id_incident.startswith("INC_")
        assert "score" in aff.explication





