"""
Stratégies d'affectation des équipes aux incidents de crise.

Règle commune à toutes les stratégies : priorité absolue aux lieux sensibles
(``poste_avec_client_sensible``). Un incident sensible en attente reçoit une équipe avant
tout incident non sensible ; chaque stratégie garde sa logique à l'intérieur de chaque groupe.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from crise.geo.distance import calculer_distance_haversine, estimer_temps_trajet
from crise.preparation.jointure import parser_date
from crise.strategies.ia_optimizer import IAOptimizer

STRATEGIES = ("distance", "premier_arrive", "score_pondere", "ia_optimale")

POIDS_DEFAUT: dict[str, float] = {
    "poids_clients_impactes": 0.40,
    "poids_clients_sensibles": 0.35,
    "poids_duree_depannage": 0.15,
    "poids_distance": 0.10,
}


def _normaliser(serie: pd.Series) -> pd.Series:
    """Ramène une série entre 0 et 1. Une série constante devient 0."""
    valeurs = pd.to_numeric(serie, errors="coerce").replace(
        [float("inf"), float("-inf")], pd.NA
    ).astype(float)
    if valeurs.notna().sum() == 0:
        return pd.Series(0.0, index=serie.index)
    bas = float(valeurs.min())
    haut = float(valeurs.max())
    if haut == bas:
        return pd.Series(0.0, index=serie.index)
    return (valeurs.fillna(bas) - bas) / (haut - bas)


def _equipe_peut_finir(equipe: dict[str, Any], temps_trajet: float, duree_reparation: float) -> bool:
    """
    Sans heures_restantes, l'équipe peut partir. Sinon le trajet et la réparation doivent tenir
    (le trajet passé ici inclut le retour au site quand le site est connu).
    """
    if "heures_restantes" not in equipe:
        return True
    reste = equipe.get("heures_restantes")
    if reste is None or pd.isna(reste):
        return True
    return temps_trajet + duree_reparation <= float(reste) + 1e-9


def est_sensible(incidents: pd.DataFrame) -> pd.Series:
    """Vrai pour les incidents sur un poste avec clients sensibles (hôpital, EHPAD…)."""
    if "poste_avec_client_sensible" not in incidents.columns:
        return pd.Series(False, index=incidents.index)
    valeurs = pd.to_numeric(incidents["poste_avec_client_sensible"], errors="coerce")
    return valeurs.fillna(0) > 0


def _nombre(valeur: Any, defaut: float = 0.0) -> float:
    if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
        return defaut
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return defaut


class IncidentAllocator:
    def __init__(
        self,
        coeff_detour: float = 1.25,
        vitesse_kmh: float = 60.0,
        poids: dict[str, float] | None = None,
    ) -> None:
        self.coeff_detour = coeff_detour
        self.vitesse_kmh = vitesse_kmh
        self.poids = {**POIDS_DEFAUT, **(poids or {})}
        self.ia_optimizer = IAOptimizer(self.coeff_detour, self.vitesse_kmh)

    def affecter_incidents(
        self,
        equipes_df: pd.DataFrame,
        incidents_df: pd.DataFrame,
        strategie: str = "distance",
        paires_interdites: set[tuple[str, str]] | frozenset[tuple[str, str]] = frozenset(),
    ) -> list[dict[str, Any]]:
        """
        Associe des équipes disponibles aux incidents selon la stratégie choisie.
        Retourne une liste de décisions d'affectation.

        ``paires_interdites`` : couples (id_equipe, id_incident) refusés par le dispatcheur.
        """
        equipes_libres = self._equipes_libres(equipes_df)
        if not equipes_libres or incidents_df.empty:
            return []

        if strategie == "ia_optimale":
            return self._affecter_ia(equipes_libres, incidents_df, paires_interdites)

        incidents_tries = self._trier(incidents_df, equipes_libres, strategie)
        decisions: list[dict[str, Any]] = []

        for _, incident in incidents_tries.iterrows():
            if not equipes_libres:
                break
            temps, index_equipe, equipe = self._plus_proche(
                incident, equipes_libres, paires_interdites
            )
            if equipe is None or index_equipe < 0:
                continue
            decisions.append(self._decision(incident, equipe, strategie, temps))
            equipes_libres.pop(index_equipe)

        return decisions

    def _affecter_ia(
        self,
        equipes_libres: list[dict[str, Any]],
        incidents_df: pd.DataFrame,
        paires_interdites: set[tuple[str, str]] | frozenset[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        """
        IA avec les refus du dispatcheur. L'optimiseur ne connaît pas les paires refusées :
        une affectation refusée est retirée, puis son incident est réoptimisé avec les
        équipes encore libres, sans celles qui l'ont refusé.
        """
        def identifiant(equipe: dict[str, Any]) -> str:
            return str(equipe.get("id_equipe") or equipe.get("id_site") or "EQUIPE")

        decisions = self._affecter_ia_sensibles_d_abord(equipes_libres, incidents_df)
        if not paires_interdites:
            return decisions
        gardees = [
            d for d in decisions
            if (str(d["id_equipe"]), str(d["id_incident"])) not in paires_interdites
        ]
        ecartes = {str(d["id_incident"]) for d in decisions} - {str(d["id_incident"]) for d in gardees}
        if not ecartes:
            return gardees
        prises = {str(d["id_equipe"]) for d in gardees}
        refusantes = {equipe for equipe, incident in paires_interdites if incident in ecartes}
        restantes = [e for e in equipes_libres if identifiant(e) not in prises | refusantes]
        if restantes:
            a_refaire = incidents_df.loc[incidents_df["id_incident"].astype(str).isin(ecartes)]
            gardees += self._affecter_ia_sensibles_d_abord(restantes, a_refaire)
        return gardees

    def _affecter_ia_sensibles_d_abord(
        self,
        equipes_libres: list[dict[str, Any]],
        incidents_df: pd.DataFrame,
    ) -> list[dict[str, Any]]:
        """
        IA en deux passes : d'abord les incidents sensibles avec toutes les équipes libres,
        puis les autres avec les équipes restantes. L'optimisation reste globale dans chaque groupe.
        """
        sensibles = est_sensible(incidents_df)
        decisions: list[dict[str, Any]] = []
        restantes = equipes_libres
        for groupe in (incidents_df.loc[sensibles], incidents_df.loc[~sensibles]):
            if groupe.empty or not restantes:
                continue
            passe = self.ia_optimizer.affecter(restantes, groupe)
            decisions.extend(passe)
            prises = {str(d["id_equipe"]) for d in passe}
            restantes = [
                e for e in restantes
                if str(e.get("id_equipe") or e.get("id_site") or "EQUIPE") not in prises
            ]
        return decisions

    def _equipes_libres(self, equipes_df: pd.DataFrame) -> list[dict[str, Any]]:
        """
        Garde les lignes dont l'équipe est disponible et non au repos.

        Sans colonne ``disponible``, toutes les équipes sont considérées disponibles.
        Les équipes dont l'état est ``au_repos`` ou ``en_mission`` sont exclues.
        """
        travail = equipes_df.copy()
        if "disponible" not in travail.columns:
            travail["disponible"] = True
        masque_disponible = travail["disponible"].fillna(False).astype(bool)
        if "etat" in travail.columns:
            masque_etat = ~travail["etat"].isin(["au_repos", "en_mission"])
            masque = masque_disponible & masque_etat
        else:
            masque = masque_disponible
        return travail.loc[masque].to_dict("records")

    def _trier(
        self,
        incidents_df: pd.DataFrame,
        equipes_libres: list[dict[str, Any]],
        strategie: str,
    ) -> pd.DataFrame:
        """
        Ordre de traitement : l'ordre de la stratégie, puis priorité absolue aux lieux
        sensibles par un tri stable (chaque groupe garde l'ordre de la stratégie).
        """
        tries = self._trier_selon_strategie(incidents_df, equipes_libres, strategie)
        return tries.iloc[(~est_sensible(tries)).to_numpy().argsort(kind="mergesort")]

    def _trier_selon_strategie(
        self,
        incidents_df: pd.DataFrame,
        equipes_libres: list[dict[str, Any]],
        strategie: str,
    ) -> pd.DataFrame:
        incidents = incidents_df.copy()
        if strategie == "premier_arrive":
            return self._trier_par_date(incidents)
        if strategie == "score_pondere":
            incidents["score_priorite"] = self._scores(incidents, equipes_libres)
            return incidents.sort_values("score_priorite", ascending=False, kind="mergesort")
        if "nb_clients" in incidents.columns:
            return incidents.sort_values("nb_clients", ascending=False, kind="mergesort")
        return incidents

    def _trier_par_date(self, incidents: pd.DataFrame) -> pd.DataFrame:
        if "date_incident" in incidents.columns:
            cle = incidents["date_incident"]
        elif "dateHeureIncident" in incidents.columns:
            cle = incidents["dateHeureIncident"].map(parser_date)
        else:
            return incidents
        tries = incidents.copy()
        tries["_date_tri"] = cle
        return tries.sort_values("_date_tri", ascending=True, na_position="last", kind="mergesort")

    def _scores(
        self,
        incidents: pd.DataFrame,
        equipes_libres: list[dict[str, Any]],
    ) -> pd.Series:
        """
        Score entre 0 et 1 : clients, clients sensibles, durée, et proximité.

        La distance est celle vers l'équipe libre la plus proche, en kilomètres routiers,
        avant toute affectation. Une distance plus courte augmente le score.
        """
        parts = self.composantes_score(incidents, equipes_libres)
        return parts["clients"] + parts["sensibles"] + parts["duree"] + parts["proximite"]

    def composantes_score(
        self,
        incidents: pd.DataFrame,
        equipes_libres: list[dict[str, Any]],
    ) -> pd.DataFrame:
        """Les quatre composantes pondérées du score (leur somme est le score), pour l'explication."""
        clients = (
            incidents["nb_clients"]
            if "nb_clients" in incidents.columns
            else pd.Series(0.0, index=incidents.index)
        )
        sensibles = (
            incidents["poste_avec_client_sensible"]
            if "poste_avec_client_sensible" in incidents.columns
            else pd.Series(0.0, index=incidents.index)
        )
        durees = (
            incidents["duree_heures"]
            if "duree_heures" in incidents.columns
            else pd.Series(0.0, index=incidents.index)
        )
        distances = pd.Series(
            [self._distance_min_km(incident, equipes_libres) for _, incident in incidents.iterrows()],
            index=incidents.index,
        )
        return pd.DataFrame(
            {
                "clients": self.poids["poids_clients_impactes"] * _normaliser(clients),
                "sensibles": self.poids["poids_clients_sensibles"] * _normaliser(sensibles),
                "duree": self.poids["poids_duree_depannage"] * _normaliser(durees),
                "proximite": self.poids["poids_distance"] * (1.0 - _normaliser(distances)),
            },
            index=incidents.index,
        )

    def _distance_min_km(self, incident: pd.Series, equipes: list[dict[str, Any]]) -> float:
        lat = incident.get("latitude")
        lon = incident.get("longitude")
        if pd.isna(lat) or pd.isna(lon):
            return float("inf")
        meilleure = float("inf")
        for equipe in equipes:
            eq_lat = equipe.get("latitude")
            eq_lon = equipe.get("longitude")
            if pd.isna(eq_lat) or pd.isna(eq_lon):
                continue
            distance = calculer_distance_haversine(float(eq_lat), float(eq_lon), float(lat), float(lon))
            distance *= self.coeff_detour
            if distance < meilleure:
                meilleure = distance
        return meilleure

    def _plus_proche(
        self,
        incident: pd.Series,
        equipes: list[dict[str, Any]],
        paires_interdites: set[tuple[str, str]] | frozenset[tuple[str, str]] = frozenset(),
    ) -> tuple[float, int, dict[str, Any] | None]:
        lat = incident.get("latitude")
        lon = incident.get("longitude")
        if pd.isna(lat) or pd.isna(lon):
            return float("inf"), -1, None
        id_incident = str(incident.get("id_incident"))
        meilleur_temps = float("inf")
        meilleur_index = -1
        meilleure_equipe: dict[str, Any] | None = None
        for index, equipe in enumerate(equipes):
            if paires_interdites and (
                str(equipe.get("id_equipe") or equipe.get("id_site")), id_incident
            ) in paires_interdites:
                continue
            eq_lat = equipe.get("latitude")
            eq_lon = equipe.get("longitude")
            if pd.isna(eq_lat) or pd.isna(eq_lon):
                continue
            temps = estimer_temps_trajet(
                float(eq_lat),
                float(eq_lon),
                float(lat),
                float(lon),
                self.coeff_detour,
                self.vitesse_kmh,
            )
            retour = self._temps_retour_site(float(lat), float(lon), equipe)
            if not _equipe_peut_finir(
                equipe, temps + retour, _nombre(incident.get("duree_heures"), 0.0)
            ):
                continue
            if temps < meilleur_temps:
                meilleur_temps = temps
                meilleur_index = index
                meilleure_equipe = equipe
        return meilleur_temps, meilleur_index, meilleure_equipe

    def _temps_retour_site(self, lat: float, lon: float, equipe: dict[str, Any]) -> float:
        """Temps pour rentrer du poste au site de l'équipe ; 0 si le site n'est pas connu."""
        site_lat = equipe.get("site_latitude")
        site_lon = equipe.get("site_longitude")
        if site_lat is None or site_lon is None or pd.isna(site_lat) or pd.isna(site_lon):
            return 0.0
        return estimer_temps_trajet(
            lat, lon, float(site_lat), float(site_lon), self.coeff_detour, self.vitesse_kmh
        )

    def _decision(
        self,
        incident: pd.Series,
        equipe: dict[str, Any],
        strategie: str,
        temps: float,
    ) -> dict[str, Any]:
        identifiant_equipe = equipe.get("id_equipe") or equipe.get("id_site", "EQUIPE")
        clients = int(_nombre(incident.get("nb_clients"), 0))
        minutes = round(temps * 60)
        commune = equipe.get("commune", "Site")
        return {
            "id_incident": incident.get("id_incident"),
            "id_poste": incident.get("id_poste", "N/A"),
            "id_equipe": identifiant_equipe,
            "id_site": equipe.get("id_site", identifiant_equipe),
            "strategie": strategie,
            "temps_estime_trajet_heures": round(temps, 2),
            "nb_clients": clients,
            "latitude": float(incident.get("latitude")),
            "longitude": float(incident.get("longitude")),
            "explication": (
                f"Affectation de l'équipe la plus proche ({commune}) "
                f"via la stratégie '{strategie}' (Trajet estimé : {minutes} min)."
            ),
        }


def compter_pannes_localisables(incidents_df: pd.DataFrame) -> int:
    """Compte les pannes qui ont une latitude et une longitude."""
    if incidents_df.empty or "latitude" not in incidents_df.columns or "longitude" not in incidents_df.columns:
        return 0
    masque = incidents_df["latitude"].notna() & incidents_df["longitude"].notna()
    return int(masque.sum())


def comparer_strategies(
    equipes_df: pd.DataFrame,
    incidents_df: pd.DataFrame,
    coeff_detour: float,
    vitesse_kmh: float,
    poids: dict[str, float] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], int]:
    """
    Lance les trois stratégies sur les mêmes pannes et les mêmes équipes.

    Retourne le dictionnaire stratégie -> décisions, et le nombre de pannes localisables.
    """
    allocateur = IncidentAllocator(coeff_detour, vitesse_kmh, poids)
    resultats = {
        strategie: allocateur.affecter_incidents(equipes_df, incidents_df, strategie)
        for strategie in STRATEGIES
    }
    return resultats, compter_pannes_localisables(incidents_df)


def resumer_affectations(decisions: list[dict[str, Any]], nb_pannes: int) -> dict[str, float]:
    """Résume une stratégie : couverture, clients et temps de trajet total."""
    clients = sum(int(_nombre(decision.get("nb_clients"), 0)) for decision in decisions)
    temps = sum(_nombre(decision.get("temps_estime_trajet_heures"), 0.0) for decision in decisions)
    return {
        "pannes_affectees": float(len(decisions)),
        "pannes_sans_equipe": float(max(nb_pannes - len(decisions), 0)),
        "clients": float(clients),
        "temps_trajet_h": round(temps, 2),
    }
