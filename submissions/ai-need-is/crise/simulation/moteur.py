"""
Horloge de crise et occupation des équipes.

Les pannes deviennent connues à leur heure. Une équipe affectée reste
occupée le temps du trajet et de la réparation, puis reste sur le poste.

Règle des 12 h / 11 h, en amplitude :
  - Le service commence au départ de la première mission (prise de poste) et dure
    au plus duree_max_h, attente comprise, retour au site compris.
  - Une mission n'est acceptée que si aller + réparation + retour au site tiennent
    dans l'amplitude restante.
  - En fin de service l'équipe passe en ``retour_site``, puis ``au_repos`` à son site
    pendant repos_h heures à partir de son arrivée. Elle repart ensuite de son site.
  - Fin de service anticipée : si une panne attend faute d'amplitude, l'équipe libre
    dont le site est le plus proche rentre se reposer pour pouvoir la prendre ensuite.

Après une réparation, une équipe qui n'a aucune panne à prendre rentre à son site
(``retour_base``) en restant disponible : une nouvelle panne peut la dérouter en route.
Arrivée au site, elle y attend, toujours en service.
"""

from __future__ import annotations

import random
from typing import Any

import pandas as pd

from crise.geo.distance import estimer_temps_trajet
from crise.preparation.jointure import parser_date
from crise.metrics.indicateurs import (
    calculer_temps_coupure_incident,
    evaluer_fonction_objectif,
)
from crise.strategies.allocator import IncidentAllocator, STRATEGIES


def _dates_incident(pannes: pd.DataFrame) -> pd.Series:
    """Retourne la date de chaque panne, à partir de date_incident ou du texte source."""
    if "date_incident" in pannes.columns:
        return pd.to_datetime(pannes["date_incident"], errors="coerce")
    if "dateHeureIncident" in pannes.columns:
        return pannes["dateHeureIncident"].map(parser_date)
    return pd.Series(pd.NaT, index=pannes.index)


def _localisables(pannes: pd.DataFrame) -> pd.Series:
    """Les pannes sans coordonnées restent écartées."""
    if "latitude" not in pannes.columns or "longitude" not in pannes.columns:
        return pd.Series(False, index=pannes.index)
    latitude = pd.to_numeric(pannes["latitude"], errors="coerce")
    longitude = pd.to_numeric(pannes["longitude"], errors="coerce")
    return latitude.notna() & longitude.notna()


def instant_initial(pannes: pd.DataFrame) -> pd.Timestamp:
    """Heure de départ : la première panne datée et localisable de la crise."""
    dates = _dates_incident(pannes)
    exploitables = dates[_localisables(pannes) & dates.notna()]
    if exploitables.empty:
        raise ValueError("Aucune panne datée et localisable pour démarrer l'horloge")
    return pd.Timestamp(exploitables.min())


def pannes_connues(pannes: pd.DataFrame, instant: pd.Timestamp) -> pd.DataFrame:
    """Pannes localisables dont l'heure est déjà atteinte."""
    dates = _dates_incident(pannes)
    masque = _localisables(pannes) & dates.notna() & (dates <= instant)
    return pannes.loc[masque].copy()


def derouler_horloge(
    pannes: pd.DataFrame,
    pas_min: int,
    nb_pas: int,
) -> list[dict[str, Any]]:
    """
    Avance l'horloge pas par pas depuis la première panne.

    Chaque entrée contient l'instant, les pannes déjà connues et celles
    apparues à ce pas-là.
    """
    if nb_pas < 1:
        return []
    if pas_min <= 0:
        raise ValueError("Le pas de temps doit être strictement positif")

    depart = instant_initial(pannes)
    duree_pas = pd.Timedelta(minutes=int(pas_min))
    deja_vues: set[str] = set()
    historique: list[dict[str, Any]] = []

    for indice in range(nb_pas):
        instant = depart + indice * duree_pas
        connues = pannes_connues(pannes, instant)
        identifiants = connues["id_incident"].astype(str).tolist() if not connues.empty else []
        nouvelles = [identifiant for identifiant in identifiants if identifiant not in deja_vues]
        deja_vues.update(identifiants)
        historique.append(
            {
                "pas": indice,
                "instant": instant,
                "ouvertes": identifiants,
                "nouvelles": nouvelles,
            }
        )
    return historique


def _identifiant_equipe(equipe: dict[str, Any]) -> str:
    return str(equipe.get("id_equipe") or equipe.get("id_site") or "EQUIPE")


def _heures(valeur: Any) -> float:
    """Heures travaillées ; une valeur absente ou NaN (colonne partielle) vaut 0."""
    if valeur is None or pd.isna(valeur):
        return 0.0
    return float(valeur)


def initialiser_equipes(
    equipes: pd.DataFrame,
    depart: pd.Timestamp | None = None,
) -> list[dict[str, Any]]:
    """
    Prépare l'état de chaque équipe : libre, à sa position de départ, qui est aussi son site.

    Une équipe qui a déjà ``heures_travaillees`` heures au départ est considérée
    en service depuis ``depart - heures_travaillees``.
    """
    etats: list[dict[str, Any]] = []
    for ligne in equipes.to_dict("records"):
        deja = _heures(ligne.get("heures_travaillees"))
        debut = depart - pd.Timedelta(hours=deja) if depart is not None and deja > 0 else None
        etats.append(
            {
                **ligne,
                "id_equipe": _identifiant_equipe(ligne),
                "etat": str(ligne.get("etat") or "libre"),
                "site_latitude": ligne.get("site_latitude", ligne.get("latitude")),
                "site_longitude": ligne.get("site_longitude", ligne.get("longitude")),
                "debut_service": debut,
                "fin_mission": None,
                "fin_retour": None,
                "fin_repos": None,
                "mission_id_incident": None,
                "relevee_pour": None,
                "libre_depuis": None,
                "depart_retour": None,
                "trajet_en_cours": None,
                "heures_travaillees": deja,
            }
        )
    return etats


def _photo_equipe(equipe: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_equipe": equipe["id_equipe"],
        "etat": equipe["etat"],
        "latitude": equipe.get("latitude"),
        "longitude": equipe.get("longitude"),
        "mission_id_incident": equipe.get("mission_id_incident"),
        "heures_travaillees": equipe.get("heures_travaillees", 0.0),
        "debut_service": equipe.get("debut_service"),
    }


def _connu(*valeurs: Any) -> bool:
    return all(valeur is not None and not pd.isna(valeur) for valeur in valeurs)


def _trajet_h(
    lat: Any, lon: Any, lat_arrivee: Any, lon_arrivee: Any, allocateur: IncidentAllocator
) -> float:
    """Temps de trajet routier estimé ; 0 si une position manque."""
    if not _connu(lat, lon, lat_arrivee, lon_arrivee):
        return 0.0
    return estimer_temps_trajet(
        float(lat),
        float(lon),
        float(lat_arrivee),
        float(lon_arrivee),
        allocateur.coeff_detour,
        allocateur.vitesse_kmh,
    )


def _retour_h(equipe: dict[str, Any], allocateur: IncidentAllocator) -> float:
    """Temps pour rentrer de la position actuelle de l'équipe à son site."""
    return _trajet_h(
        equipe.get("latitude"),
        equipe.get("longitude"),
        equipe.get("site_latitude"),
        equipe.get("site_longitude"),
        allocateur,
    )


def _amplitude_h(equipe: dict[str, Any], instant: pd.Timestamp) -> float:
    """Heures écoulées depuis la prise de poste, attente comprise ; 0 hors service."""
    debut = equipe.get("debut_service")
    if debut is None:
        return 0.0
    return max((instant - debut) / pd.Timedelta(hours=1), 0.0)


def _fin_service(equipe: dict[str, Any], duree_max_h: float) -> pd.Timestamp | None:
    """Heure à laquelle l'équipe doit être rentrée à son site."""
    debut = equipe.get("debut_service")
    return None if debut is None else debut + pd.Timedelta(hours=duree_max_h)


def _noter_trajet(
    trajets: list[dict[str, Any]] | None,
    equipe: dict[str, Any],
    depart: pd.Timestamp,
    arrivee: pd.Timestamp,
    lat_arrivee: Any,
    lon_arrivee: Any,
    destination: str,
    id_incident: str | None = None,
    motif: str | None = None,
) -> dict[str, Any] | None:
    """
    Mémorise un déplacement (pour l'animation de la carte) et le renvoie.
    Ignoré sans positions ou sans durée.
    """
    if trajets is None or arrivee <= depart:
        return None
    if not _connu(equipe.get("latitude"), equipe.get("longitude"), lat_arrivee, lon_arrivee):
        return None
    trajets.append(
        {
            "id_equipe": equipe["id_equipe"],
            "id_site": equipe.get("id_site", equipe["id_equipe"]),
            "destination": destination,
            "id_incident": id_incident,
            "motif": motif,
            "depart": depart,
            "arrivee": arrivee,
            "lat_depart": float(equipe["latitude"]),
            "lon_depart": float(equipe["longitude"]),
            "lat_arrivee": float(lat_arrivee),
            "lon_arrivee": float(lon_arrivee),
            "amplitude_depart_h": _amplitude_h(equipe, depart),
        }
    )
    return trajets[-1]


def _entrer_en_repos(equipe: dict[str, Any], debut_repos: pd.Timestamp, repos_h: float) -> None:
    """L'équipe est à son site et y commence repos_h heures de repos."""
    equipe["etat"] = "au_repos"
    equipe["latitude"] = equipe.get("site_latitude")
    equipe["longitude"] = equipe.get("site_longitude")
    equipe["fin_repos"] = debut_repos + pd.Timedelta(hours=repos_h)
    equipe["debut_service"] = None
    equipe["fin_retour"] = None
    equipe["fin_mission"] = None
    equipe["mission_id_incident"] = None


def _envoyer_au_site(
    equipe: dict[str, Any],
    depart_retour: pd.Timestamp,
    instant: pd.Timestamp,
    allocateur: IncidentAllocator,
    repos_h: float,
    trajets: list[dict[str, Any]] | None = None,
) -> None:
    """
    Fin de service : l'équipe rentre à son site, puis s'y repose.

    Si elle est déjà rentrée à ``instant`` (ou déjà au site), le repos commence
    à son heure d'arrivée.
    """
    arrivee = depart_retour + pd.Timedelta(hours=_retour_h(equipe, allocateur))
    _noter_trajet(
        trajets,
        equipe,
        depart_retour,
        arrivee,
        equipe.get("site_latitude"),
        equipe.get("site_longitude"),
        "site",
        motif="fin_service",
    )
    equipe["libre_depuis"] = None
    if arrivee <= instant:
        _entrer_en_repos(equipe, arrivee, repos_h)
        return
    equipe["etat"] = "retour_site"
    equipe["fin_retour"] = arrivee
    equipe["fin_mission"] = None
    equipe["mission_id_incident"] = None


def _au_site(equipe: dict[str, Any]) -> None:
    equipe["latitude"] = equipe.get("site_latitude")
    equipe["longitude"] = equipe.get("site_longitude")


def _rentrer_disponible(
    equipe: dict[str, Any],
    depart: pd.Timestamp,
    instant: pd.Timestamp,
    allocateur: IncidentAllocator,
    trajets: list[dict[str, Any]] | None = None,
) -> None:
    """
    Plus rien à faire : l'équipe rentre à son site sans finir son service.

    Pendant ce retour (état ``retour_base``) elle reste disponible : une nouvelle panne
    peut la dérouter depuis sa position du moment. Arrivée au site, elle redevient libre.
    """
    arrivee = depart + pd.Timedelta(hours=_retour_h(equipe, allocateur))
    trajet = _noter_trajet(
        trajets,
        equipe,
        depart,
        arrivee,
        equipe.get("site_latitude"),
        equipe.get("site_longitude"),
        "site",
        motif="disponible",
    )
    equipe["libre_depuis"] = None
    if arrivee <= instant:
        _au_site(equipe)
        return
    equipe["etat"] = "retour_base"
    equipe["depart_retour"] = depart
    equipe["fin_retour"] = arrivee
    equipe["trajet_en_cours"] = trajet


def _position_en_route(equipe: dict[str, Any], instant: pd.Timestamp) -> tuple[float, float]:
    """Position d'une équipe en ``retour_base`` à ``instant``, sur la ligne poste → site."""
    lat0, lon0 = float(equipe["latitude"]), float(equipe["longitude"])
    lat1, lon1 = float(equipe["site_latitude"]), float(equipe["site_longitude"])
    duree = (equipe["fin_retour"] - equipe["depart_retour"]) / pd.Timedelta(seconds=1)
    part = 1.0 if duree <= 0 else (instant - equipe["depart_retour"]) / pd.Timedelta(seconds=1) / duree
    part = min(max(part, 0.0), 1.0)
    return lat0 + part * (lat1 - lat0), lon0 + part * (lon1 - lon0)


def _interrompre_retour(equipe: dict[str, Any], instant: pd.Timestamp) -> None:
    """Déroute une équipe en retour : elle repart de sa position du moment."""
    lat, lon = _position_en_route(equipe, instant)
    trajet = equipe.get("trajet_en_cours")
    if trajet is not None:
        trajet["arrivee"] = instant
        trajet["lat_arrivee"], trajet["lon_arrivee"] = lat, lon
    equipe["latitude"], equipe["longitude"] = lat, lon
    equipe["etat"] = "libre"
    equipe["fin_retour"] = None
    equipe["trajet_en_cours"] = None


def arriver_au_site(
    equipes: list[dict[str, Any]],
    instant: pd.Timestamp,
    repos_h: float = 11.0,
) -> None:
    """
    Équipes arrivées à leur site : repos si c'était une fin de service (``retour_site``),
    sinon de nouveau libres au site, toujours en service (``retour_base``).
    """
    for equipe in equipes:
        if equipe["etat"] not in ("retour_site", "retour_base") or equipe.get("fin_retour") is None:
            continue
        if instant < equipe["fin_retour"]:
            continue
        if equipe["etat"] == "retour_site":
            _entrer_en_repos(equipe, equipe["fin_retour"], repos_h)
            continue
        _au_site(equipe)
        equipe["etat"] = "libre"
        equipe["fin_retour"] = None
        equipe["trajet_en_cours"] = None


def cloturer_missions(
    equipes: list[dict[str, Any]],
    pannes_par_id: dict[str, dict[str, Any]],
    instant: pd.Timestamp,
    allocateur: IncidentAllocator,
    duree_max_h: float = 12.0,
    repos_h: float = 11.0,
    resolutions_detail: list[dict[str, Any]] | None = None,
    instant_depart: pd.Timestamp | None = None,
    trajets: list[dict[str, Any]] | None = None,
) -> list[str]:
    """
    Libère les équipes dont la mission est terminée et les place sur le poste réparé.

    Si l'équipe ne pourrait plus rentrer à temps en attendant ce pas, elle repart
    vers son site dès la fin de la réparation.
    """
    terminees: list[str] = []
    for equipe in equipes:
        if equipe["etat"] != "en_mission" or equipe["fin_mission"] is None:
            continue
        if instant < equipe["fin_mission"]:
            continue
        panne = pannes_par_id.get(str(equipe["mission_id_incident"]))
        if panne is not None and _connu(panne.get("latitude"), panne.get("longitude")):
            equipe["latitude"] = float(panne["latitude"])
            equipe["longitude"] = float(panne["longitude"])
        terminees.append(str(equipe["mission_id_incident"]))

        if resolutions_detail is not None and panne is not None:
            date_inc = panne.get("date_incident")
            if pd.isna(date_inc):
                date_inc = instant_depart
            t_aff = equipe.get("mission_instant_affectation") or instant
            route = float(equipe.get("mission_temps_route_h") or 0.0)
            dep = float(equipe.get("mission_temps_depannage_h") or (panne.get("duree_heures") or 0.0))
            attente, route, dep, coupure = calculer_temps_coupure_incident(
                date_inc, t_aff, route, dep
            )
            nb_cl = int(panne.get("nb_clients") or 0)
            resolutions_detail.append(
                {
                    "id_incident": str(equipe["mission_id_incident"]),
                    "id_poste": str(panne.get("id_poste", "N/A")),
                    "id_equipe": str(equipe.get("id_equipe") or equipe.get("id_site", "")),
                    "nb_clients": nb_cl,
                    "date_incident": date_inc,
                    "instant_affectation": t_aff,
                    "instant_resolution": instant,
                    "temps_attente_h": attente,
                    "temps_route_h": route,
                    "temps_depannage_h": dep,
                    "temps_coupure_total_h": coupure,
                    "produit_clients_temps": round(nb_cl * coupure, 2),
                }
            )

        fin_service = _fin_service(equipe, duree_max_h)
        retour = pd.Timedelta(hours=_retour_h(equipe, allocateur))
        if fin_service is not None and instant + retour > fin_service:
            _envoyer_au_site(
                equipe, equipe["fin_mission"], instant, allocateur, repos_h, trajets
            )
        else:
            equipe["etat"] = "libre"
            # Réparation finie entre deux pas : un éventuel retour au site part de cette heure-là.
            equipe["libre_depuis"] = equipe["fin_mission"]
            equipe["fin_mission"] = None
            equipe["mission_id_incident"] = None

    return terminees


def sortir_du_repos(
    equipes: list[dict[str, Any]],
    instant: pd.Timestamp,
) -> None:
    """
    Libère les équipes dont la période de repos obligatoire est terminée.

    Elles sont hors service jusqu'à leur prochaine mission, avec un compteur à zéro.
    """
    for equipe in equipes:
        if equipe["etat"] != "au_repos":
            continue
        fin_repos = equipe.get("fin_repos")
        if fin_repos is None or instant < fin_repos:
            continue
        equipe["etat"] = "libre"
        equipe["fin_repos"] = None
        equipe["debut_service"] = None
        equipe["heures_travaillees"] = 0.0
        equipe["relevee_pour"] = None


def _pannes_a_affecter(
    connues: pd.DataFrame,
    resolues: set[str],
    en_mission: set[str],
) -> pd.DataFrame:
    if connues.empty:
        return connues.copy()
    identifiants = connues["id_incident"].astype(str)
    masque = ~identifiants.isin(resolues | en_mission)
    return connues.loc[masque].copy()


def _mission_acceptable(
    equipe: dict[str, Any],
    instant: pd.Timestamp,
    aller_et_reparation_h: float,
    retour_h: float,
    duree_max_h: float,
) -> bool:
    """
    Vrai si l'équipe peut aller sur la panne, la réparer et rentrer à son site
    avant la fin de son amplitude de service.
    """
    total = _amplitude_h(equipe, instant) + aller_et_reparation_h + retour_h
    return total <= duree_max_h + 1e-9


def _equipe_a_relever(
    panne: dict[str, Any],
    equipes: list[dict[str, Any]],
    allocateur: IncidentAllocator,
    duree_max_h: float,
) -> dict[str, Any] | None:
    """
    Parmi les équipes libres en service, celle dont le site est le plus proche de la panne
    et qui pourrait la traiter après repos (aller depuis le site + réparation + retour).
    Aucune si même une équipe reposée ne le pourrait : c'est alors la distance qui bloque.
    """
    meilleure: dict[str, Any] | None = None
    meilleur_trajet = float("inf")
    for equipe in equipes:
        if equipe["etat"] != "libre" or equipe.get("debut_service") is None:
            continue
        site_lat, site_lon = equipe.get("site_latitude"), equipe.get("site_longitude")
        if not _connu(site_lat, site_lon):
            continue
        aller = _trajet_h(site_lat, site_lon, panne.get("latitude"), panne.get("longitude"), allocateur)
        if 2 * aller + float(panne.get("duree_heures") or 0.0) > duree_max_h + 1e-9:
            continue
        if aller < meilleur_trajet:
            meilleur_trajet = aller
            meilleure = equipe
    return meilleure


def _demarrer_mission(
    equipe: dict[str, Any],
    incident: dict[str, Any],
    instant: pd.Timestamp,
    temps_trajet_h: float,
    trajets: list[dict[str, Any]] | None = None,
    interventions: list[dict[str, Any]] | None = None,
) -> None:
    duree_reparation = float(incident.get("duree_heures") or 0.0)
    duree_totale = float(temps_trajet_h) + duree_reparation
    if equipe.get("debut_service") is None:
        equipe["debut_service"] = instant
    equipe["libre_depuis"] = None
    arrivee = instant + pd.Timedelta(hours=float(temps_trajet_h))
    _noter_trajet(
        trajets,
        equipe,
        instant,
        arrivee,
        incident.get("latitude"),
        incident.get("longitude"),
        "incident",
        str(incident.get("id_incident")),
    )
    if interventions is not None:
        interventions.append(
            {
                "id_incident": str(incident.get("id_incident")),
                "id_equipe": equipe["id_equipe"],
                "arrivee": arrivee,
                "fin": instant + pd.Timedelta(hours=duree_totale),
            }
        )
    equipe["etat"] = "en_mission"
    equipe["mission_id_incident"] = str(incident.get("id_incident"))
    equipe["fin_mission"] = instant + pd.Timedelta(hours=duree_totale)
    equipe["mission_instant_affectation"] = instant
    equipe["mission_temps_route_h"] = float(temps_trajet_h)
    equipe["mission_temps_depannage_h"] = duree_reparation


class SimulationPasAPas:
    """
    Simulation de crise avançant un pas à la fois, pour permettre une validation humaine.

    Chaque pas se joue en deux temps :
      1. ``ouvrir_pas()`` avance l'horloge, clôt les missions terminées et renvoie les
         propositions d'affectation de la stratégie ;
      2. ``appliquer(affectations)`` démarre les affectations retenues (proposées,
         modifiées ou choisies librement), gère les retours et fins de service, puis clôt le pas.

    Entre les deux, ``proposer``, ``decision_pour`` et ``contexte`` permettent de construire
    d'autres propositions (après un refus) ou un choix libre.
    """

    def __init__(
        self,
        pannes: pd.DataFrame,
        equipes: pd.DataFrame,
        strategie: str,
        pas_min: int,
        nb_pas: int,
        coeff_detour: float,
        vitesse_kmh: float,
        poids: dict[str, float] | None = None,
        duree_max_h: float = 12.0,
        repos_h: float = 11.0,
        scenario: str = "nominal",
        alea_declenchement_pct: int = 50,
    ) -> None:
        if nb_pas >= 1 and pas_min <= 0:
            raise ValueError("Le pas de temps doit être strictement positif")
        self.pannes = pannes
        self.nb_equipes = len(equipes)
        self.strategie = strategie
        self.pas_min = pas_min
        self.nb_pas = nb_pas
        self.coeff_detour = coeff_detour
        self.vitesse_kmh = vitesse_kmh
        self.poids = poids
        self.duree_max_h = duree_max_h
        self.repos_h = repos_h
        self.scenario = scenario
        self.alea_declenchement_pct = alea_declenchement_pct

        self.indice = 0
        self.depart = instant_initial(pannes) if nb_pas >= 1 else None
        self.duree_pas = pd.Timedelta(minutes=int(pas_min)) if pas_min > 0 else pd.Timedelta(0)
        self.deja_vues: set[str] = set()
        self.resolues: set[str] = set()
        self.etats = initialiser_equipes(equipes, self.depart)
        self.pannes_par_id = {
            str(ligne["id_incident"]): ligne
            for ligne in pannes.to_dict("records")
            if "id_incident" in ligne
        }
        self.resolutions_detail: list[dict[str, Any]] = []
        # Déplacements et interventions horodatés, pour animer la carte entre deux pas.
        self.trajets: list[dict[str, Any]] = []
        self.interventions: list[dict[str, Any]] = []
        self.historique: list[dict[str, Any]] = []

        # ── MOTEUR D'ALÉAS (Robustesse) ──
        vitesse_effective = vitesse_kmh * 0.7 if scenario == "saturation_trafic" else vitesse_kmh
        self.allocateur = IncidentAllocator(coeff_detour, vitesse_effective, poids)
        self._alea_perte_applique = False
        self._pas_ouvert: dict[str, Any] | None = None

    # ── État ────────────────────────────────────────────────────────────────

    @property
    def termine(self) -> bool:
        return self.indice >= self.nb_pas

    @property
    def instant(self) -> pd.Timestamp | None:
        if self.depart is None:
            return None
        return self.depart + self.indice * self.duree_pas

    def _equipes_par_id(self) -> dict[str, dict[str, Any]]:
        return {_identifiant_equipe(equipe): equipe for equipe in self.etats}

    def contexte(self) -> dict[str, Any]:
        """
        Le pas ouvert : instant, pannes à affecter, équipes disponibles (chacune
        avec sa position du moment et son amplitude restante) et pannes résolues à ce pas.
        """
        if self._pas_ouvert is None:
            raise RuntimeError("Aucun pas ouvert : appeler ouvrir_pas() d'abord")
        return {
            "instant": self._pas_ouvert["instant"],
            "pannes": self._pas_ouvert["a_affecter"],
            "equipes": self._candidates(),
            "terminees": list(self._pas_ouvert["terminees"]),
        }

    # ── Temps 1 : ouvrir le pas ─────────────────────────────────────────────

    def ouvrir_pas(self) -> list[dict[str, Any]]:
        """Avance l'horloge, clôt les missions terminées et renvoie les propositions du pas."""
        if self.termine:
            raise RuntimeError("La simulation est terminée")
        if self._pas_ouvert is not None:
            raise RuntimeError("Le pas précédent n'a pas encore été appliqué")
        instant = self.instant
        etats = self.etats

        # Aléa : Perte d'équipes selon le pourcentage choisi
        if (
            self.scenario == "perte_equipes"
            and not self._alea_perte_applique
            and self.indice >= (self.nb_pas * self.alea_declenchement_pct) / 100
        ):
            self._alea_perte_applique = True
            for equipe in etats:
                if equipe["etat"] in ["libre", "au_repos"] and random.random() < 0.5:
                    equipe["etat"] = "indisponible"

        # 1. Les équipes rentrées au site commencent leur repos ; celles qui ont fini
        #    leur repos redeviennent libres.
        arriver_au_site(etats, instant, self.repos_h)
        sortir_du_repos(etats, instant)

        connues = pannes_connues(self.pannes, instant)
        identifiants = connues["id_incident"].astype(str).tolist() if not connues.empty else []
        nouvelles = [identifiant for identifiant in identifiants if identifiant not in self.deja_vues]
        self.deja_vues.update(identifiants)

        # 2. Clore les missions terminées (peut renvoyer l'équipe à son site).
        terminees = cloturer_missions(
            etats,
            self.pannes_par_id,
            instant,
            self.allocateur,
            self.duree_max_h,
            self.repos_h,
            resolutions_detail=self.resolutions_detail,
            instant_depart=self.depart,
            trajets=self.trajets,
        )
        self.resolues.update(terminees)

        # 3. Pannes en attente d'une équipe.
        en_mission = {
            str(equipe["mission_id_incident"])
            for equipe in etats
            if equipe["etat"] == "en_mission" and equipe.get("mission_id_incident")
        }
        self._pas_ouvert = {
            "instant": instant,
            "identifiants": identifiants,
            "nouvelles": nouvelles,
            "terminees": terminees,
            "a_affecter": _pannes_a_affecter(connues, self.resolues, en_mission),
        }
        return self.proposer()

    def _candidates(self) -> list[dict[str, Any]]:
        """
        Équipes disponibles au pas ouvert, avec leur amplitude restante. Une équipe qui
        rentre à son site sans être en fin de service reste disponible, depuis sa position
        du moment sur le trajet du retour.
        """
        instant = self._pas_ouvert["instant"]
        libres = []
        for equipe in self.etats:
            if equipe["etat"] not in ("libre", "retour_base"):
                continue
            candidate = {
                **equipe,
                "heures_restantes": self.duree_max_h - _amplitude_h(equipe, instant),
            }
            if equipe["etat"] == "retour_base":
                candidate["latitude"], candidate["longitude"] = _position_en_route(equipe, instant)
            libres.append(candidate)
        return libres

    def proposer(
        self,
        equipes_exclues: set[str] | frozenset[str] = frozenset(),
        incidents_exclus: set[str] | frozenset[str] = frozenset(),
        paires_interdites: set[tuple[str, str]] | frozenset[tuple[str, str]] = frozenset(),
    ) -> list[dict[str, Any]]:
        """
        Propositions de la stratégie pour le pas ouvert. L'allocateur reçoit l'amplitude
        restante et le site : aller + réparation + retour doivent tenir.

        Les exclusions servent après une validation partielle : équipes et pannes déjà
        décidées, paires (équipe, panne) refusées par le dispatcheur.
        """
        if self._pas_ouvert is None:
            raise RuntimeError("Aucun pas ouvert : appeler ouvrir_pas() d'abord")
        libres = [c for c in self._candidates() if str(c["id_equipe"]) not in equipes_exclues]
        a_affecter = self._pas_ouvert["a_affecter"]
        if incidents_exclus and not a_affecter.empty:
            a_affecter = a_affecter.loc[~a_affecter["id_incident"].astype(str).isin(incidents_exclus)]
        if not libres or a_affecter.empty:
            return []
        return self.allocateur.affecter_incidents(
            pd.DataFrame(libres), a_affecter, self.strategie, paires_interdites=paires_interdites
        )

    def decision_pour(self, id_equipe: str, id_incident: str) -> dict[str, Any]:
        """Décision au même format que l'allocateur, pour un couple choisi librement."""
        candidate = next(
            (c for c in self._candidates() if str(c["id_equipe"]) == str(id_equipe)), None
        )
        if candidate is None:
            raise ValueError(f"L'équipe {id_equipe} n'est pas disponible à ce pas")
        a_affecter = self._pas_ouvert["a_affecter"]
        lignes = a_affecter.loc[a_affecter["id_incident"].astype(str) == str(id_incident)]
        if lignes.empty:
            raise ValueError(f"La panne {id_incident} n'est pas en attente à ce pas")
        incident = lignes.iloc[0]
        temps = _trajet_h(
            candidate.get("latitude"),
            candidate.get("longitude"),
            incident.get("latitude"),
            incident.get("longitude"),
            self.allocateur,
        )
        return self.allocateur._decision(incident, candidate, self.strategie, temps)

    def mission_faisable(self, id_equipe: str, id_incident: str) -> bool:
        """Vrai si l'équipe peut faire aller + réparation + retour dans son amplitude."""
        decision = self.decision_pour(id_equipe, id_incident)
        equipe = self._equipes_par_id()[str(id_equipe)]
        incident = self.pannes_par_id[str(id_incident)]
        retour = _trajet_h(
            incident.get("latitude"),
            incident.get("longitude"),
            equipe.get("site_latitude"),
            equipe.get("site_longitude"),
            self.allocateur,
        )
        return _mission_acceptable(
            equipe,
            self._pas_ouvert["instant"],
            float(decision["temps_estime_trajet_heures"]) + float(incident.get("duree_heures") or 0.0),
            retour,
            self.duree_max_h,
        )

    # ── Temps 2 : appliquer les affectations retenues ───────────────────────

    def appliquer(self, affectations_retenues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Démarre les affectations retenues, gère retours et fins de service, puis clôt le pas.
        Renvoie les affectations réellement démarrées.
        """
        if self._pas_ouvert is None:
            raise RuntimeError("Aucun pas ouvert : appeler ouvrir_pas() d'abord")
        ouvert = self._pas_ouvert
        instant = ouvert["instant"]
        etats = self.etats
        allocateur = self.allocateur
        duree_max_h, repos_h = self.duree_max_h, self.repos_h
        a_affecter = ouvert["a_affecter"]

        # 4. Démarrer les missions retenues.
        equipes_par_id = self._equipes_par_id()
        affectations: list[dict[str, Any]] = []
        for decision in affectations_retenues:
            equipe = equipes_par_id.get(str(decision["id_equipe"]))
            incident = self.pannes_par_id.get(str(decision["id_incident"]))
            if equipe is None or incident is None or equipe["etat"] not in ("libre", "retour_base"):
                continue
            temps_trajet = float(decision["temps_estime_trajet_heures"])
            duree_rep = float(incident.get("duree_heures") or 0.0)
            retour = _trajet_h(
                incident.get("latitude"),
                incident.get("longitude"),
                equipe.get("site_latitude"),
                equipe.get("site_longitude"),
                allocateur,
            )
            if not _mission_acceptable(
                equipe, instant, temps_trajet + duree_rep, retour, duree_max_h
            ):
                continue
            if equipe["etat"] == "retour_base":
                _interrompre_retour(equipe, instant)
            _demarrer_mission(
                equipe, incident, instant, temps_trajet, self.trajets, self.interventions
            )
            affectations.append(decision)
        demarrees = {str(decision["id_incident"]) for decision in affectations}

        # 5. Fin de service anticipée : pour chaque panne restée sans équipe faute
        #    d'amplitude, l'équipe libre la plus proche rentre se reposer pour pouvoir
        #    la prendre ensuite. Sinon les équipes attendraient sans fin une panne
        #    qu'aucune ne peut plus prendre.
        restantes = (
            [
                self.pannes_par_id[identifiant]
                for identifiant in a_affecter["id_incident"].astype(str)
                if identifiant not in demarrees
            ]
            if not a_affecter.empty
            else []
        )
        deja_relevees = {
            equipe.get("relevee_pour")
            for equipe in etats
            if equipe["etat"] in ("retour_site", "au_repos")
        }
        for panne in restantes:
            if str(panne["id_incident"]) in deja_relevees:
                continue
            equipe = _equipe_a_relever(panne, etats, allocateur, duree_max_h)
            if equipe is not None:
                depart_retour = equipe.get("libre_depuis") or instant
                _envoyer_au_site(equipe, depart_retour, instant, allocateur, repos_h, self.trajets)
                equipe["relevee_pour"] = str(panne["id_incident"])

        # 5 bis. Plus rien à faire : une équipe libre restée hors de son site n'a pu prendre
        #        aucune panne à ce pas. Elle rentre à son site (depuis la fin de sa réparation),
        #        en restant disponible pendant le trajet.
        for equipe in etats:
            if equipe["etat"] != "libre" or equipe.get("debut_service") is None:
                continue
            if _retour_h(equipe, allocateur) <= 0:
                continue
            depart_retour = equipe.get("libre_depuis") or instant
            _rentrer_disponible(equipe, depart_retour, instant, allocateur, self.trajets)

        # 6. Fin de service normale : une équipe qui ne pourrait plus rentrer à temps
        #    si elle attendait le pas suivant part maintenant vers son site.
        for equipe in etats:
            fin_service = _fin_service(equipe, duree_max_h)
            if equipe["etat"] != "libre" or fin_service is None:
                continue
            retour = pd.Timedelta(hours=_retour_h(equipe, allocateur))
            if instant + self.duree_pas + retour > fin_service:
                depart_retour = equipe.get("libre_depuis") or instant
                _envoyer_au_site(equipe, depart_retour, instant, allocateur, repos_h, self.trajets)

        for equipe in etats:
            equipe["heures_travaillees"] = _amplitude_h(equipe, instant)

        self.historique.append(
            {
                "pas": self.indice,
                "instant": instant,
                "ouvertes": ouvert["identifiants"],
                "nouvelles": ouvert["nouvelles"],
                "terminees": ouvert["terminees"],
                "affectations": affectations,
                "equipes": [_photo_equipe(equipe) for equipe in etats],
            }
        )
        self.indice += 1
        self._pas_ouvert = None
        return affectations

    # ── Résultat ─────────────────────────────────────────────────────────────

    def resultat(self) -> dict[str, Any]:
        """Résultat au même format que ``lancer_simulation``."""
        base = {
            "t0": self.depart,
            "strategie": self.strategie,
            "pas_min": self.pas_min,
            "nb_pas": self.nb_pas,
            "coeff_detour": self.coeff_detour,
            "vitesse_kmh": self.vitesse_kmh,
            "poids": self.poids,
            "duree_max_h": self.duree_max_h,
            "repos_h": self.repos_h,
            "nb_equipes": self.nb_equipes,
        }
        if self.nb_pas < 1:
            return {**base, "pas": []}
        return {
            **base,
            "indicateurs": evaluer_fonction_objectif(self.resolutions_detail),
            "resolutions": self.resolutions_detail,
            "trajets": self.trajets,
            "interventions": self.interventions,
            "pas": self.historique,
        }


def lancer_simulation(
    pannes: pd.DataFrame,
    equipes: pd.DataFrame,
    strategie: str,
    pas_min: int,
    nb_pas: int,
    coeff_detour: float,
    vitesse_kmh: float,
    poids: dict[str, float] | None = None,
    duree_max_h: float = 12.0,
    repos_h: float = 11.0,
    scenario: str = "nominal",
    alea_declenchement_pct: int = 50,
) -> dict[str, Any]:
    """
    Fait avancer la crise pas par pas et occupe les équipes affectées, en acceptant
    toutes les propositions de la stratégie (mode automatique).

    Applique la règle 12 h / 11 h en amplitude : chaque équipe doit être rentrée
    à son site au plus tard duree_max_h après sa prise de poste, puis s'y repose
    repos_h heures avant de repartir de son site.
    """
    simulation = SimulationPasAPas(
        pannes,
        equipes,
        strategie,
        pas_min,
        nb_pas,
        coeff_detour,
        vitesse_kmh,
        poids,
        duree_max_h,
        repos_h,
        scenario,
        alea_declenchement_pct,
    )
    while not simulation.termine:
        simulation.appliquer(simulation.ouvrir_pas())
    return simulation.resultat()


def suivre_resolutions(resultat: dict[str, Any], pannes: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Résume chaque pas d'une simulation : pannes en attente, en cours, résolues,
    clients rétablis et clients encore coupés.

    Les pannes résolues sont cumulées d'un pas à l'autre.
    """
    if pannes.empty or "id_incident" not in pannes.columns:
        clients_par_id: dict[str, float] = {}
    else:
        clients = (
            pd.to_numeric(pannes["nb_clients"], errors="coerce").fillna(0.0)
            if "nb_clients" in pannes.columns
            else pd.Series(0.0, index=pannes.index)
        )
        clients_par_id = dict(zip(pannes["id_incident"].astype(str), clients.astype(float)))

    resolues: set[str] = set()
    suivi: list[dict[str, Any]] = []
    for pas in resultat.get("pas", []):
        resolues.update(str(identifiant) for identifiant in pas.get("terminees", []))
        en_cours = {
            str(equipe["mission_id_incident"])
            for equipe in pas.get("equipes", [])
            if equipe["etat"] == "en_mission" and equipe.get("mission_id_incident")
        }
        en_attente = set(pas.get("ouvertes", [])) - resolues - en_cours
        etats_equipes = [equipe["etat"] for equipe in pas.get("equipes", [])]
        suivi.append(
            {
                "pas": pas["pas"],
                "instant": pas["instant"],
                "en_attente": sorted(en_attente),
                "en_cours": sorted(en_cours),
                "resolues": sorted(resolues),
                "clients_retablis": int(sum(clients_par_id.get(i, 0.0) for i in resolues)),
                "clients_coupes": int(
                    sum(clients_par_id.get(i, 0.0) for i in en_attente | en_cours)
                ),
                "equipes_libres": etats_equipes.count("libre"),
                "equipes_en_mission": etats_equipes.count("en_mission"),
                "equipes_en_retour": etats_equipes.count("retour_site")
                + etats_equipes.count("retour_base"),
                "equipes_au_repos": etats_equipes.count("au_repos"),
                "equipes_indisponibles": etats_equipes.count("indisponible"),
            }
        )
    return suivi


def comparer_simulations(
    pannes: pd.DataFrame,
    equipes: pd.DataFrame,
    pas_min: int,
    nb_pas: int,
    coeff_detour: float,
    vitesse_kmh: float,
    poids: dict[str, float] | None = None,
    duree_max_h: float = 12.0,
    repos_h: float = 11.0,
    scenario: str = "nominal",
    alea_declenchement_pct: int = 50,
) -> dict[str, dict[str, Any]]:
    """
    Exécute la simulation complète pour les trois stratégies et retourne leurs historiques.

    Chaque stratégie s'exécute de manière indépendante sur les mêmes données d'entrée.
    Retourne un dictionnaire stratégie -> résultat de lancer_simulation.
    """
    return {
        strategie: lancer_simulation(
            pannes=pannes,
            equipes=equipes,
            strategie=strategie,
            pas_min=pas_min,
            nb_pas=nb_pas,
            coeff_detour=coeff_detour,
            vitesse_kmh=vitesse_kmh,
            poids=poids,
            duree_max_h=duree_max_h,
            repos_h=repos_h,
            scenario=scenario,
            alea_declenchement_pct=alea_declenchement_pct,
        )
        for strategie in STRATEGIES
    }
