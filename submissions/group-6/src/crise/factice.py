"""Module de jeu de données factice (T2.1).

Fournit 3 équipes et 6 incidents construits à la main selon les contrats §4
pour valider les algorithmes (WSPT, algorithme hongrois, contraintes, explications)
avant le branchement sur le simulateur et le jeu de données complet.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from crise.config import charger_config
from crise.models import (
    Affectation,
    Equipe,
    EtatEquipe,
    EtatIncident,
    EtatSimulation,
    Incident,
    Poste,
    SimResult,
    Site,
)
from crise.trajet import calculer_trajet_min

PARAMETRES_DEFAUT = {
    "amplitude_max_min": 720,      # 12h max
    "repos_min": 660,              # 11h repos obligatoire
    "alpha_sensible": 5.0,         # poste sensible pèse (1 + 5) = 6x
    "beta_attente_par_h": 0.1,     # +10% de poids par heure d'attente
    "coef_detour": 1.3,
    "vitesse_plaine_kmh": 55.0,
    "vitesse_montagne_kmh": 35.0,
    "lat_seuil_montagne": 43.05,
    "anticipation_min": 30,
    "reserve_active": False,
}


def charger_parametres_defaut(config_path: str | Path | None = None) -> dict:
    """Charge les paramètres de simulation depuis config/default.yaml s'il existe, sinon PARAMETRES_DEFAUT."""
    params = dict(PARAMETRES_DEFAUT)
    try:
        data = charger_config(config_path)
        if isinstance(data, dict):
            for sec, vals in data.items():
                if isinstance(vals, dict):
                    params.update(vals)
                else:
                    params[sec] = vals
    except Exception:
        pass
    return params


def calculer_score_wspt(
    equipe: Equipe,
    incident: Incident,
    t: int,
    trajet_func=calculer_trajet_min,
    params: dict | None = None,
) -> float:
    """Calcule le score WSPT score_ij d'un couple (équipe, incident) selon le §5.3.

    score_ij = w_i / (trajet_ij + duree_i)
    w_i = N_i * (1 + alpha * sensible_i) * (1 + beta * attente_i_en_heures)

    Renvoie -inf si l'affectation est infaisable :
    - équipe non DISPONIBLE
    - incident non EN_ATTENTE ou non encore apparu (t_apparition > t)
    - ou trajet + durée > amplitude restante
    """
    if equipe.etat != EtatEquipe.DISPONIBLE:
        return -float("inf")

    if incident.etat != EtatIncident.EN_ATTENTE or incident.t_apparition > t:
        return -float("inf")

    p = dict(PARAMETRES_DEFAUT)
    if params:
        p.update(params)

    trajet = trajet_func(equipe.lat, equipe.lon, incident.lat, incident.lon)
    duree = incident.duree_nominale

    # Faisabilité amplitude restante (§2.3 contrainte 5)
    amplitude_max = p.get("amplitude_max_min", 720)
    amplitude_utilisee = max(0, t - equipe.t_debut_service)
    amplitude_restante = amplitude_max - amplitude_utilisee

    if (trajet + duree) > amplitude_restante:
        return -float("inf")

    # Calcul du poids w_i (§5.3)
    alpha = p.get("alpha_sensible", 5.0)
    beta = p.get("beta_attente_par_h", 0.1)

    attente_min = max(0, t - incident.t_apparition)
    attente_h = attente_min / 60.0

    poids_sensible = (1.0 + alpha) if incident.sensible else 1.0
    poids_attente = 1.0 + beta * attente_h
    w = incident.nb_clients * poids_sensible * poids_attente

    denominateur = trajet + duree
    if denominateur <= 0:
        return float("inf")
    return w / denominateur


def creer_sites_factices() -> list[Site]:
    """Crée les 3 sites opérationnels associés aux équipes factices (§4.1)."""
    return [
        Site(
            id_site="SITE_TOULOUSE",
            commune="Toulouse",
            lat=43.604,
            lon=1.443,
            nb_equipes=1,
        ),
        Site(
            id_site="SITE_MURET",
            commune="Muret",
            lat=43.460,
            lon=1.326,
            nb_equipes=1,
        ),
        Site(
            id_site="SITE_FOIX",
            commune="Foix",
            lat=42.964,
            lon=1.606,
            nb_equipes=1,
        ),
    ]


def creer_postes_factices() -> list[Poste]:
    """Crée les 6 postes électriques associés aux incidents factices (§4.1)."""
    return [
        Poste(
            id_poste="POSTE_TOULOUSE_NORD",
            commune="Toulouse",
            departement="31",
            lat=43.610,
            lon=1.450,
            nb_clients=150,
            sensible=False,
        ),
        Poste(
            id_poste="POSTE_TOULOUSE_CENTRE",
            commune="Toulouse",
            departement="31",
            lat=43.600,
            lon=1.430,
            nb_clients=50,
            sensible=False,
        ),
        Poste(
            id_poste="POSTE_MURET_CLINIQUE",
            commune="Muret",
            departement="31",
            lat=43.450,
            lon=1.330,
            nb_clients=80,
            sensible=True,
        ),
        Poste(
            id_poste="POSTE_COMMINGES_RURAL",
            commune="Saint-Gaudens",
            departement="31",
            lat=43.120,
            lon=0.730,
            nb_clients=30,
            sensible=False,
        ),
        Poste(
            id_poste="POSTE_TARASCON_HOPITAL",
            commune="Tarascon-sur-Ariège",
            departement="09",
            lat=42.840,
            lon=1.600,
            nb_clients=120,
            sensible=True,
        ),
        Poste(
            id_poste="POSTE_AX_MONTAGNE",
            commune="Ax-les-Thermes",
            departement="09",
            lat=42.720,
            lon=1.810,
            nb_clients=25,
            sensible=False,
        ),
    ]


def creer_equipes_factices() -> list[Equipe]:
    """Crée 3 équipes factices sur 3 sites représentatifs de Haute-Garonne et Ariège."""
    return [
        # Équipe 1 : Toulouse (Haute-Garonne, plaine)
        Equipe(
            id_equipe="SITE_TOULOUSE_E1",
            id_site="SITE_TOULOUSE",
            lat=43.604,
            lon=1.443,
            etat=EtatEquipe.DISPONIBLE,
            t_debut_service=0,
            t_libre=0,
            id_incident=None,
        ),
        # Équipe 2 : Muret (Haute-Garonne, plaine)
        Equipe(
            id_equipe="SITE_MURET_E1",
            id_site="SITE_MURET",
            lat=43.460,
            lon=1.326,
            etat=EtatEquipe.DISPONIBLE,
            t_debut_service=0,
            t_libre=0,
            id_incident=None,
        ),
        # Équipe 3 : Foix (Ariège, zone montagne car lat 42.964 < 43.05)
        Equipe(
            id_equipe="SITE_FOIX_E1",
            id_site="SITE_FOIX",
            lat=42.964,
            lon=1.606,
            etat=EtatEquipe.DISPONIBLE,
            t_debut_service=0,
            t_libre=0,
            id_incident=None,
        ),
    ]


def creer_incidents_factices(t: int | None = None) -> list[Incident]:
    """Crée 6 incidents factices calibrés pour tester WSPT, priorités et contraintes.

    Si t est None, les incidents apparus à t=0 sont EN_ATTENTE et les futurs sont NON_APPARU.
    Si t est renseigné, les incidents dont t_apparition <= t sont EN_ATTENTE, sinon NON_APPARU.

    Comprend notamment :
    - INC_001 (A du §5.3) : 150 clients, 8h (480 min), non sensible.
    - INC_002 (B du §5.3) : 50 clients, 2h (120 min), non sensible.
    - INC_003 : 80 clients, 4h (240 min), sensible (clinique, Muret, t=15).
    - INC_004 : 30 clients, 2h (120 min), rural Comminges plaine (t=30).
    - INC_005 : 120 clients, 4h (240 min), sensible en montagne (Tarascon, lat < 43.05, t=0).
    - INC_006 : 25 clients, 8h (480 min), montagne isolée (Ax-les-Thermes, lat < 43.05, t=45).
    """
    definitions = [
        ("INC_001", "POSTE_TOULOUSE_NORD", 0, 480, 480, "tempête", 150, False, 43.610, 1.450),
        ("INC_002", "POSTE_TOULOUSE_CENTRE", 0, 120, 120, "branches", 50, False, 43.600, 1.430),
        ("INC_003", "POSTE_MURET_CLINIQUE", 15, 240, 240, "foudre", 80, True, 43.450, 1.330),
        ("INC_004", "POSTE_COMMINGES_RURAL", 30, 120, 120, "inondation", 30, False, 43.120, 0.730),
        ("INC_005", "POSTE_TARASCON_HOPITAL", 0, 240, 240, "tempête", 120, True, 42.840, 1.600),
        ("INC_006", "POSTE_AX_MONTAGNE", 45, 480, 480, "neige", 25, False, 42.720, 1.810),
    ]

    seuil_t = 0 if t is None else t

    incidents = []
    for inc_id, p_id, t_app, d_nom, d_reel, cause, nb_cli, sens, lat, lon in definitions:
        etat = EtatIncident.EN_ATTENTE if t_app <= seuil_t else EtatIncident.NON_APPARU
        incidents.append(
            Incident(
                id_incident=inc_id,
                id_poste=p_id,
                t_apparition=t_app,
                duree_nominale=d_nom,
                duree_reelle=d_reel,
                cause=cause,
                nb_clients=nb_cli,
                sensible=sens,
                lat=lat,
                lon=lon,
                etat=etat,
            )
        )
    return incidents


def creer_jeu_factice(t: int | None = None) -> tuple[list[Equipe], list[Incident]]:
    """Renvoie (3 équipes, 6 incidents) conformes à T2.1."""
    return creer_equipes_factices(), creer_incidents_factices(t=t)


def creer_jeu_exemple_ab() -> tuple[Equipe, Incident, Incident]:
    """Fixture canonique de l'exemple A/B du §5.3 (1 équipe, 2 incidents, trajet nul).

    - Équipe à Toulouse
    - Incident A : 150 clients, 8h (480 min) -> ratio N/durée = 150/480 = 0.3125
    - Incident B : 50 clients, 2h (120 min) -> ratio N/durée = 50/120 = 0.4167
    Règle de Smith (WSPT) : B doit être ordonnancé avant A.
    """
    equipe = Equipe(
        id_equipe="SITE_TOULOUSE_E1",
        id_site="SITE_TOULOUSE",
        lat=43.604,
        lon=1.443,
        etat=EtatEquipe.DISPONIBLE,
        t_debut_service=0,
        t_libre=0,
    )
    inc_a = Incident(
        id_incident="INC_A_8H",
        id_poste="POSTE_TOULOUSE_A",
        t_apparition=0,
        duree_nominale=480,
        duree_reelle=480,
        cause="tempête",
        nb_clients=150,
        sensible=False,
        lat=43.604,
        lon=1.443,
        etat=EtatIncident.EN_ATTENTE,
    )
    inc_b = Incident(
        id_incident="INC_B_2H",
        id_poste="POSTE_TOULOUSE_B",
        t_apparition=0,
        duree_nominale=120,
        duree_reelle=120,
        cause="branches",
        nb_clients=50,
        sensible=False,
        lat=43.604,
        lon=1.443,
        etat=EtatIncident.EN_ATTENTE,
    )
    return equipe, inc_a, inc_b


def creer_etat_exemple_ab(params: dict | None = None) -> EtatSimulation:
    """Construit un EtatSimulation pour l'exemple canonique A/B à t=0."""
    eq, inc_a, inc_b = creer_jeu_exemple_ab()
    p = dict(PARAMETRES_DEFAUT)
    if params:
        p.update(params)

    return EtatSimulation(
        t=0,
        equipes_disponibles=[deepcopy(eq)],
        incidents_en_attente=[deepcopy(inc_a), deepcopy(inc_b)],
        toutes_equipes=[deepcopy(eq)],
        params=p,
    )


def creer_etat_simulation_factice(
    t: int = 60,
    params: dict | None = None,
) -> EtatSimulation:
    """Construit un EtatSimulation factice à l'instant t avec les paramètres par défaut."""
    equipes = creer_equipes_factices()
    incidents = creer_incidents_factices(t=t)
    p = dict(PARAMETRES_DEFAUT)
    if params:
        p.update(params)

    incidents_en_attente = [
        inc for inc in incidents
        if inc.etat == EtatIncident.EN_ATTENTE
    ]

    return EtatSimulation(
        t=t,
        equipes_disponibles=deepcopy(equipes),
        incidents_en_attente=incidents_en_attente,
        toutes_equipes=deepcopy(equipes),
        params=p,
    )


def creer_etat_simulation_aucun_incident(
    t: int = 60,
    params: dict | None = None,
) -> EtatSimulation:
    """Cas limite : aucune panne en attente à l'instant t."""
    etat = creer_etat_simulation_factice(t=t, params=params)
    etat.incidents_en_attente = []
    return etat


def creer_etat_simulation_amplitude_epuisee(
    t: int = 720,
    params: dict | None = None,
) -> EtatSimulation:
    """Cas limite : toutes les équipes ont épuisé leur amplitude restante (>= 12h de travail)."""
    p = dict(PARAMETRES_DEFAUT)
    if params:
        p.update(params)
    equipes = creer_equipes_factices()
    # A t=720 et t_debut_service=0, temps écoulé = 720 min, amplitude restante = 0 min
    for eq in equipes:
        eq.t_debut_service = 0
    incidents = creer_incidents_factices(t=t)
    incidents_en_attente = [inc for inc in incidents if inc.etat == EtatIncident.EN_ATTENTE]

    return EtatSimulation(
        t=t,
        equipes_disponibles=deepcopy(equipes),
        incidents_en_attente=incidents_en_attente,
        toutes_equipes=deepcopy(equipes),
        params=p,
    )


def creer_etat_simulation_equipes_indisponibles(
    t: int = 60,
    params: dict | None = None,
) -> EtatSimulation:
    """Cas limite : toutes les équipes sont engagées sur un chantier, en repos, ou hors-service."""
    p = dict(PARAMETRES_DEFAUT)
    if params:
        p.update(params)
    equipes = creer_equipes_factices()
    equipes[0].etat = EtatEquipe.CHANTIER
    equipes[0].t_libre = t + 120
    equipes[1].etat = EtatEquipe.REPOS
    equipes[1].t_libre = t + 400
    equipes[2].etat = EtatEquipe.HORS_SERVICE

    incidents = creer_incidents_factices(t=t)
    incidents_en_attente = [inc for inc in incidents if inc.etat == EtatIncident.EN_ATTENTE]

    return EtatSimulation(
        t=t,
        equipes_disponibles=[],  # Aucune équipe libre
        incidents_en_attente=incidents_en_attente,
        toutes_equipes=deepcopy(equipes),
        params=p,
    )


def resoudre_affectation_hongrois(
    etat: EtatSimulation,
    trajet_func=calculer_trajet_min,
) -> list[Affectation]:
    """Résout l'affectation optimale globale équipes <-> incidents par l'algorithme hongrois (§5.3).

    Gère de manière robuste :
    - Les matrices rectangulaires (plus d'équipes que d'incidents ou inversement)
    - Les équipes ou incidents infaisables (-inf) sans lever ValueError de scipy
    - Ne produit aucune affectation pour les couples infaisables
    """
    equipes = [eq for eq in etat.equipes_disponibles if eq.etat == EtatEquipe.DISPONIBLE]
    incidents = [
        inc for inc in etat.incidents_en_attente
        if inc.etat == EtatIncident.EN_ATTENTE and inc.t_apparition <= etat.t
    ]

    if not equipes or not incidents:
        return []

    try:
        import numpy as np
        from scipy.optimize import linear_sum_assignment
    except ImportError:
        affectations = []
        inc_restants = list(incidents)
        for eq in equipes:
            meilleur_score = -float("inf")
            meilleur_inc = None
            for inc in inc_restants:
                s = calculer_score_wspt(eq, inc, etat.t, trajet_func=trajet_func, params=etat.params)
                if s > meilleur_score:
                    meilleur_score = s
                    meilleur_inc = inc
            if meilleur_inc is not None and meilleur_score > -float("inf"):
                affectations.append(
                    Affectation(
                        id_equipe=eq.id_equipe,
                        id_incident=meilleur_inc.id_incident,
                        explication={"score": meilleur_score},
                    )
                )
                inc_restants.remove(meilleur_inc)
        return affectations

    n_eq = len(equipes)
    n_inc = len(incidents)
    S = np.zeros((n_eq, n_inc), dtype=float)

    for i, eq in enumerate(equipes):
        for j, inc in enumerate(incidents):
            S[i, j] = calculer_score_wspt(eq, inc, etat.t, trajet_func=trajet_func, params=etat.params)

    # linear_sum_assignment minimise le coût. Pour maximiser S, le coût est -S.
    # Pour éviter ValueError: cost matrix is infeasible quand des lignes/colonnes sont -inf,
    # on remplace -inf par une pénalité finie élevée (1e9).
    cout = np.where(np.isneginf(S) | np.isnan(S), 1e9, -S)

    row_ind, col_ind = linear_sum_assignment(cout)

    affectations = []
    for r, c in zip(row_ind, col_ind, strict=True):
        score_val = float(S[r, c])
        # Ne retenir que les affectations strictement faisables
        if score_val > -float("inf") and not np.isnan(score_val) and cout[r, c] < 1e8:
            eq = equipes[r]
            inc = incidents[c]
            trajet = trajet_func(eq.lat, eq.lon, inc.lat, inc.lon)
            affectations.append(
                Affectation(
                    id_equipe=eq.id_equipe,
                    id_incident=inc.id_incident,
                    explication={
                        "score": score_val,
                        "trajet_min": trajet,
                        "duree_min": inc.duree_nominale,
                        "nb_clients": inc.nb_clients,
                        "sensible": inc.sensible,
                    },
                )
            )

    return affectations


def creer_scenario_factice(
    n_incidents: int = 30,
    n_equipes: int = 6,
    seed: int = 42,
) -> tuple[list[Site], list[Equipe], list[Incident]]:
    """Génère un scénario factice conforme à T4.1 (30 incidents, 6 équipes).

    Les positions couvrent les 3 départements du défi (Ariège 09, Haute-Garonne 31, Gers 32).
    """
    import numpy as np

    rng = np.random.default_rng(seed)

    sites = [
        Site(id_site="SITE_TOULOUSE", commune="Toulouse", lat=43.604, lon=1.443, nb_equipes=2),
        Site(id_site="SITE_MURET", commune="Muret", lat=43.460, lon=1.326, nb_equipes=2),
        Site(id_site="SITE_FOIX", commune="Foix", lat=42.964, lon=1.606, nb_equipes=2),
    ]

    equipes: list[Equipe] = []
    for k in range(n_equipes):
        site = sites[k % len(sites)]
        num = (k // len(sites)) + 1
        equipes.append(
            Equipe(
                id_equipe=f"{site.id_site}_E{num}",
                id_site=site.id_site,
                lat=site.lat,
                lon=site.lon,
                etat=EtatEquipe.DISPONIBLE,
                t_debut_service=0,
                t_libre=0,
            )
        )

    communes_ref = [
        ("Toulouse", "31", 43.604, 1.443),
        ("Muret", "31", 43.460, 1.326),
        ("Saint-Gaudens", "31", 43.108, 0.723),
        ("Colomiers", "31", 43.614, 1.334),
        ("Foix", "09", 42.964, 1.606),
        ("Pamiers", "09", 43.116, 1.611),
        ("Tarascon-sur-Ariège", "09", 42.846, 1.598),
        ("Ax-les-Thermes", "09", 42.721, 1.815),
        ("Auch", "32", 43.646, 0.587),
        ("Condom", "32", 43.957, 0.372),
        ("Mirande", "32", 43.515, 0.404),
    ]

    causes = ["tempête", "chute d'arbre", "foudre", "inondation", "neige"]

    incidents: list[Incident] = []
    for i in range(n_incidents):
        com, dep, base_lat, base_lon = communes_ref[i % len(communes_ref)]
        lat = round(float(base_lat + rng.uniform(-0.10, 0.10)), 4)
        lon = round(float(base_lon + rng.uniform(-0.12, 0.12)), 4)
        t_app = int(rng.integers(0, 360))
        duree = int(rng.choice([120, 240, 480]))
        nb_clients = int(rng.integers(15, 150))
        sensible = bool(rng.random() < 0.20)
        cause = str(rng.choice(causes))

        incidents.append(
            Incident(
                id_incident=f"INC_FACTICE_{i+1:03d}",
                id_poste=f"POSTE_FACTICE_{i+1:03d}",
                t_apparition=t_app,
                duree_nominale=duree,
                duree_reelle=duree,
                cause=cause,
                nb_clients=nb_clients,
                sensible=sensible,
                lat=lat,
                lon=lon,
                etat=EtatIncident.NON_APPARU,
            )
        )

    incidents.sort(key=lambda x: (x.t_apparition, x.id_incident))
    return sites, equipes, incidents


def generer_sim_result_factice(
    n_incidents: int = 30,
    n_equipes: int = 6,
    seed: int = 42,
    policy=None,
    params: dict | None = None,
) -> SimResult:
    """T4.1 — Génère un SimResult factice complet à partir des contrats §4.4.

    Génère 30 incidents et 6 équipes au hasard sur la zone, simule la crise avec
    la stratégie spécifiée (WSPTHongroisPolicy par défaut), et retourne le SimResult
    avec les 4 tables renseignées (incidents, activites, decisions, serie)
    et les colonnes géographiques (commune, departement).
    """
    from crise.policies.wspt_hongrois import WSPTHongroisPolicy
    from crise.simulateur import parametres_simulation, simuler

    sites, equipes, incidents = creer_scenario_factice(
        n_incidents=n_incidents,
        n_equipes=n_equipes,
        seed=seed,
    )

    pol = policy if policy is not None else WSPTHongroisPolicy()
    if params is not None and "amplitude_max_min" in params:
        p = dict(params)
        p["seed"] = seed
    elif params is not None and "travail" in params:
        p = parametres_simulation(params, seed=seed)
    else:
        p = parametres_simulation(None, seed=seed, **(params or {}))

    communes_ref = [
        ("Toulouse", "31"),
        ("Muret", "31"),
        ("Saint-Gaudens", "31"),
        ("Colomiers", "31"),
        ("Foix", "09"),
        ("Pamiers", "09"),
        ("Tarascon-sur-Ariège", "09"),
        ("Ax-les-Thermes", "09"),
        ("Auch", "32"),
        ("Condom", "32"),
        ("Mirande", "32"),
    ]

    geo_map = {
        inc.id_incident: communes_ref[i % len(communes_ref)]
        for i, inc in enumerate(incidents)
    }

    meta = {
        "crise": "CRISE_FACTICE",
        "strategie": getattr(pol, "nom", str(pol)),
        "seed": seed,
        "params": p,
    }

    res = simuler(sites, equipes, incidents, pol, params=p, meta=meta)

    # Compléter commune et département si absents ou vides
    if "commune" not in res.incidents.columns or res.incidents["commune"].isna().any():
        res.incidents["commune"] = res.incidents["id_incident"].map(
            lambda x: geo_map.get(x, ("Toulouse", "31"))[0]
        )
    if "departement" not in res.incidents.columns or res.incidents["departement"].isna().any():
        res.incidents["departement"] = res.incidents["id_incident"].map(
            lambda x: geo_map.get(x, ("Toulouse", "31"))[1]
        )

    return res
