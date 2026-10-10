"""Simulateur à événements discrets — boucle T1→T5, produit un SimResult (§4.4).

Tâche(s) : T1.5 (+ base de T1.7 et T1.8) — propriétaire : P1.
Voir docs/PLAN_EQUIPE_DEFI_ENEDIS.md §5.1.

Utilisation :
    from crise.models import charger_scenario
    from crise.policies.baselines import PlusProcheFCFS
    from crise.simulateur import simuler

    sites, equipes, incidents = charger_scenario(27)
    res = simuler(sites, equipes, incidents, PlusProcheFCFS())
    res.incidents, res.activites, res.decisions, res.serie, res.metadata

Règles simulées (hypothèses H3, H7, H8 du plan) :
    - une équipe = un incident à la fois ; pas de réaffectation en cours de trajet ou de chantier ;
    - un incident est résolu après trajet + dépannage ; l'équipe reste sur place, disponible ;
    - amplitude : une affectation n'est acceptée que si trajet + durée nominale ≤ amplitude restante ;
      quand l'amplitude restante < durée minimale d'un dépannage (2h) ou quand elle est épuisée,
      l'équipe rentre à son site (RETOUR) puis se repose (REPOS, 11h) et repart pour une nouvelle amplitude ;
    - indisponibilités (stress) : l'équipe termine son chantier en cours (sécurité), puis passe HORS_SERVICE ;
    - forcées / interdites (décision humaine, T1.8) : appliquées avant la stratégie ;
    - Monte Carlo (option) : durée réelle et vitesse réelle tirées au hasard, la stratégie ne voit que le nominal.
"""
from __future__ import annotations

import heapq
import json
import logging
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from crise.models import (
    COLONNES_SIMRESULT,
    Affectation,
    Equipe,
    EtatEquipe,
    EtatIncident,
    EtatSimulation,
    Incident,
    SimResult,
    Site,
)
from crise.policies.base import Policy

log = logging.getLogger("crise.simulateur")

TrajetMin = Callable[[float, float, float, float], float]

DUREE_MIN_DEPANNAGE = 120          # 2h : plus petite durée possible → seuil pour partir en repos
HORIZON_MAX_MIN = 14 * 24 * 60     # garde-fou : 14 jours simulés au maximum

# Ordre de traitement des événements simultanés (les plus « libérateurs » d'abord)
_PRIO = {"FIN_CHANTIER": 0, "ARRIVEE": 1, "FIN_RETOUR": 2, "FIN_REPOS": 3, "FIN_HS": 4,
         "INDISPO": 5, "FIN_AMPLITUDE": 6, "APPARITION": 7}


# --------------------------------------------------------------------------- contraintes (pour les stratégies)
def amplitude_restante(equipe: Equipe, t: int, params: dict) -> int:
    """Minutes de travail encore autorisées dans l'amplitude en cours."""
    ampli = int(params["amplitude_max_min"])
    restante = ampli - (t - equipe.t_debut_service)
    if params.get("_roulement_actif"):
        t_fin_shift = ((t // ampli) + 1) * ampli
        restante = min(restante, t_fin_shift - t)
    return restante


def est_faisable(equipe: Equipe, incident: Incident, trajet: float, t: int, params: dict) -> bool:
    """Règle d'amplitude (§2.3) : trajet + durée NOMINALE ≤ amplitude restante,
    et couple (équipe, incident) non interdit par le responsable (params["interdites"])."""
    if (equipe.id_equipe, incident.id_incident) in params.get("interdites", ()):
        return False
    return trajet + incident.duree_nominale <= amplitude_restante(equipe, t, params)


# --------------------------------------------------------------------------- paramètres
def parametres_simulation(cfg: dict | None = None, **surcharges) -> dict:
    """Aplatit la config utile au simulateur et aux stratégies (passée telle quelle dans EtatSimulation.params)."""
    if cfg is None:
        from crise.config import charger_config

        cfg = charger_config()
    p = {
        "amplitude_max_min": int(cfg["travail"]["amplitude_max_min"]),
        "repos_min": int(cfg["travail"]["repos_min"]),
        "roulement_actif": bool(cfg["travail"].get("roulement_actif", True)),
        "pct_premier_roulement": float(cfg["travail"].get("pct_premier_roulement", 0.75)),
        "pas_instantane_min": int(cfg["affichage"]["pas_instantane_min"]),
        "alpha_sensible": float(cfg["score"]["alpha_sensible"]),
        "beta_attente_par_h": float(cfg["score"]["beta_attente_par_h"]),
        "anticipation_min": int(cfg["score"].get("anticipation_min", 30)),
        "reserve_active": bool(cfg["score"].get("reserve_active", False)),
        "monte_carlo": {"actif": False, **cfg.get("monte_carlo", {})},
        "trajet": dict(cfg["trajet"]),
        "seed": int(cfg.get("seed", 42)),
    }
    for k, v in surcharges.items():
        if k == "monte_carlo" and isinstance(v, dict):
            p["monte_carlo"] = {**p["monte_carlo"], **v}
        else:
            p[k] = v
    return p


@dataclass
class Indisponibilite:
    """Équipe hors service de t_debut à t_fin (None = jusqu'à la fin). Elle finit d'abord son chantier en cours."""
    id_equipe: str
    t_debut: int
    t_fin: int | None = None


@dataclass(order=True)
class _Evt:
    t: int
    prio: int
    seq: int
    type: str = field(compare=False)
    cible: str = field(compare=False)       # id_equipe ou id_incident


# --------------------------------------------------------------------------- moteur
class Simulateur:
    def __init__(
        self,
        sites: list[Site],
        equipes: list[Equipe],
        incidents: list[Incident],
        policy: Policy,
        params: dict | None = None,
        trajet_min: TrajetMin | None = None,
        indisponibilites: Iterable[Indisponibilite] = (),
        forcees: dict[str, str] | None = None,
        interdites: Iterable[tuple[str, str]] = (),
        meta: dict | None = None,
    ):
        self.params = dict(params or parametres_simulation())
        if trajet_min is None:
            from crise.trajet import faire_trajet_min

            trajet_min = faire_trajet_min({"trajet": self.params["trajet"]})
        self.trajet_min = trajet_min
        self.policy = policy
        self.sites = {s.id_site: s for s in sites}
        self.equipes = {e.id_equipe: e for e in equipes}
        self.incidents = {i.id_incident: i for i in incidents}
        if len(self.equipes) != len(equipes) or len(self.incidents) != len(incidents):
            raise ValueError("identifiants d'équipes ou d'incidents en double")
        inconnus = {e.id_site for e in equipes} - set(self.sites)
        if inconnus:
            raise ValueError(f"équipes rattachées à des sites inconnus : {sorted(inconnus)}")
        self.forcees = dict(forcees or {})
        self.interdites = set(interdites)
        self.params["interdites"] = frozenset(self.interdites)   # visible des stratégies via est_faisable
        self.indispos = list(indisponibilites)
        self.meta = dict(meta or {})

        self._file: list[_Evt] = []
        self._seq = 0
        self._hs_en_attente: dict[str, int | None] = {}     # équipe → t_fin d'indisponibilité à appliquer
        self._activite_en_cours: dict[str, dict] = {}
        self.activites: list[dict] = []
        self.decisions: list[dict] = []
        self.rejets: list[dict] = []
        self._roulement_actif: bool = False
        self._cohorte: dict[str, int] = {}
        self.rng = np.random.default_rng(self.params.get("seed", 42))
        self._appliquer_monte_carlo_durees()

    # ------------------------------------------------------------------ utilitaires
    def _pousser(self, t: int, type_: str, cible: str) -> None:
        self._seq += 1
        heapq.heappush(self._file, _Evt(int(t), _PRIO[type_], self._seq, type_, cible))

    def _mc(self) -> dict:
        return self.params.get("monte_carlo") or {}

    def _appliquer_monte_carlo_durees(self) -> None:
        mc = self._mc()
        if not mc.get("actif"):
            return
        sigma = float(mc.get("sigma_duree", 0.3))
        for inc in self.incidents.values():
            f = float(np.clip(self.rng.lognormal(0.0, sigma), 0.5, 2.0))
            inc.duree_reelle = int(round(inc.duree_nominale * f))

    def _trajet_reel(self, nominal: float) -> int:
        mc = self._mc()
        if mc.get("actif") and nominal > 0:
            v = float(np.clip(self.rng.normal(1.0, float(mc.get("sigma_vitesse", 0.15))), 0.6, 1.3))
            nominal = nominal / v
        return int(round(nominal))

    def _ouvrir(self, eq: Equipe, type_: str, t: int, fin: int, inc: Incident | None,
                dep: tuple[float, float], arr: tuple[float, float]) -> None:
        a = {"id_equipe": eq.id_equipe, "type": type_, "t_debut": int(t), "t_fin": int(fin),
             "id_incident": inc.id_incident if inc else None,
             "lat_dep": dep[0], "lon_dep": dep[1], "lat_arr": arr[0], "lon_arr": arr[1]}
        self.activites.append(a)
        self._activite_en_cours[eq.id_equipe] = a

    # ------------------------------------------------------------------ transitions d'équipe
    def _liberer(self, eq: Equipe, t: int) -> None:
        """L'équipe vient de finir quelque chose : hors service, repos ou disponible ?"""
        if eq.id_equipe in self._hs_en_attente:
            t_fin = self._hs_en_attente.pop(eq.id_equipe)
            eq.etat = EtatEquipe.HORS_SERVICE
            fin = t_fin if t_fin is not None else HORIZON_MAX_MIN
            eq.t_libre = fin
            self._ouvrir(eq, "hors_service", t, fin, None, (eq.lat, eq.lon), (eq.lat, eq.lon))
            if t_fin is not None:
                self._pousser(t_fin, "FIN_HS", eq.id_equipe)
            return
        if amplitude_restante(eq, t, self.params) < DUREE_MIN_DEPANNAGE:
            self._partir_repos(eq, t)
            return
        eq.etat = EtatEquipe.DISPONIBLE
        eq.t_libre = t
        eq.id_incident = None

    def _calculer_fin_repos(self, eq: Equipe, t: int) -> int:
        repos_min = int(self.params["repos_min"])
        if not getattr(self, "_roulement_actif", False):
            return t + repos_min

        amplitude_max = int(self.params["amplitude_max_min"])
        cohorte = self._cohorte.get(eq.id_equipe, 1)

        t_dispo = t + repos_min
        m = t_dispo // amplitude_max
        is_my_shift = (m % 2 == 0) if (cohorte == 1) else (m % 2 == 1)
        t_fin_shift = (m + 1) * amplitude_max

        # Si l'équipe est reposée pendant son shift et qu'il reste assez de temps pour un dépannage
        if is_my_shift and (t_fin_shift - t_dispo) >= DUREE_MIN_DEPANNAGE:
            return t_dispo

        # Sinon, attendre le début du prochain shift assigné à sa cohorte
        if cohorte == 1:
            m_next = (m + 2) if (m % 2 == 0) else (m + 1)
        else:
            m_next = (m + 1) if (m % 2 == 0) else (m + 2)

        return m_next * amplitude_max

    def _partir_repos(self, eq: Equipe, t: int) -> None:
        site = self.sites[eq.id_site]
        duree = self._trajet_reel(self.trajet_min(eq.lat, eq.lon, site.lat, site.lon))
        eq.etat = EtatEquipe.RETOUR
        eq.id_incident = None
        eq.t_libre = self._calculer_fin_repos(eq, t + duree)
        self._ouvrir(eq, "retour", t, t + duree, None, (eq.lat, eq.lon), (site.lat, site.lon))
        self._pousser(t + duree, "FIN_RETOUR", eq.id_equipe)

    def _nouvelle_amplitude(self, eq: Equipe, t: int) -> None:
        eq.t_debut_service = t
        eq.etat = EtatEquipe.DISPONIBLE
        eq.t_libre = t
        ampli = int(self.params["amplitude_max_min"])
        fin = t + ampli
        if getattr(self, "_roulement_actif", False):
            t_fin_shift = ((t // ampli) + 1) * ampli
            fin = min(fin, t_fin_shift)
        self._pousser(fin, "FIN_AMPLITUDE", eq.id_equipe)

    # ------------------------------------------------------------------ traitement des événements
    def _traiter(self, e: _Evt) -> None:
        t = e.t
        if e.type == "APPARITION":
            inc = self.incidents[e.cible]
            inc.etat = EtatIncident.EN_ATTENTE
            return

        eq = self.equipes[e.cible]
        if e.type == "ARRIVEE":
            inc = self.incidents[eq.id_incident]
            eq.etat = EtatEquipe.CHANTIER
            eq.lat, eq.lon = inc.lat, inc.lon
            inc.etat = EtatIncident.EN_COURS
            inc.t_arrivee = t
            fin = t + int(inc.duree_reelle)
            eq.t_libre = fin
            self._ouvrir(eq, "chantier", t, fin, inc, (inc.lat, inc.lon), (inc.lat, inc.lon))
            self._pousser(fin, "FIN_CHANTIER", eq.id_equipe)
        elif e.type == "FIN_CHANTIER":
            inc = self.incidents[eq.id_incident]
            inc.etat = EtatIncident.RESOLU
            inc.t_resolution = t
            eq.id_incident = None
            self._liberer(eq, t)
        elif e.type == "FIN_RETOUR":
            site = self.sites[eq.id_site]
            eq.lat, eq.lon = site.lat, site.lon
            eq.etat = EtatEquipe.REPOS
            fin = self._calculer_fin_repos(eq, t)
            self._ouvrir(eq, "repos", t, fin, None, (site.lat, site.lon), (site.lat, site.lon))
            self._pousser(fin, "FIN_REPOS", eq.id_equipe)
        elif e.type == "FIN_REPOS":
            if eq.etat is EtatEquipe.REPOS:
                if eq.id_equipe in self._hs_en_attente:
                    self._liberer(eq, t)
                else:
                    self._nouvelle_amplitude(eq, t)
        elif e.type == "FIN_HS":
            if eq.etat is EtatEquipe.HORS_SERVICE:
                if getattr(self, "_roulement_actif", False):
                    ampli = int(self.params["amplitude_max_min"])
                    m = t // ampli
                    active_cohorte = 1 if (m % 2 == 0) else 2
                    if self._cohorte.get(eq.id_equipe, 1) == active_cohorte:
                        self._nouvelle_amplitude(eq, t)
                    else:
                        site = self.sites.get(eq.id_site)
                        coord = (site.lat, site.lon) if site else (eq.lat, eq.lon)
                        eq.etat = EtatEquipe.REPOS
                        fin = self._calculer_fin_repos(eq, t)
                        eq.t_libre = fin
                        self._ouvrir(eq, "repos", t, fin, None, coord, coord)
                        self._pousser(fin, "FIN_REPOS", eq.id_equipe)
                else:
                    self._nouvelle_amplitude(eq, t)       # repart reposée (hypothèse)
        elif e.type == "INDISPO":
            t_fin = self._indispo_fin[e.seq]
            if eq.etat in (EtatEquipe.DISPONIBLE, EtatEquipe.REPOS):
                if eq.etat is EtatEquipe.REPOS:      # on coupe le repos à t
                    self._activite_en_cours[eq.id_equipe]["t_fin"] = t
                self._hs_en_attente[eq.id_equipe] = t_fin
                self._liberer(eq, t)
            else:                                     # trajet / chantier / retour : il finit d'abord
                self._hs_en_attente[eq.id_equipe] = t_fin
        elif e.type == "FIN_AMPLITUDE":
            if eq.etat is EtatEquipe.DISPONIBLE and e.t >= eq.t_debut_service + int(self.params["amplitude_max_min"]):
                self._partir_repos(eq, t)

    # ------------------------------------------------------------------ décision
    def _etat(self, t: int) -> EtatSimulation:
        dispo = [e for e in self.equipes.values() if e.etat is EtatEquipe.DISPONIBLE]
        attente = sorted((i for i in self.incidents.values() if i.etat is EtatIncident.EN_ATTENTE),
                         key=lambda i: (i.t_apparition, i.id_incident))
        return EtatSimulation(t=t, equipes_disponibles=dispo, incidents_en_attente=attente,
                              toutes_equipes=list(self.equipes.values()), params=self.params)

    def _lancer(self, eq: Equipe, inc: Incident, t: int, explication: dict, origine: str) -> None:
        analyse = {}
        if self.params.get("expliquer", True):              # T2.5 : explication calculée pour toute stratégie
            from crise.explication import expliquer

            analyse = expliquer(
                eq, inc, t, self.params, self.trajet_min,
                [i for i in self.incidents.values() if i.etat is EtatIncident.EN_ATTENTE],
                [e for e in self.equipes.values() if e.etat is EtatEquipe.DISPONIBLE],
            )
        nominal = self.trajet_min(eq.lat, eq.lon, inc.lat, inc.lon)
        duree = self._trajet_reel(nominal)
        eq.etat = EtatEquipe.TRAJET
        eq.id_incident = inc.id_incident
        eq.t_libre = t + duree + inc.duree_reelle
        inc.etat = EtatIncident.AFFECTE
        inc.id_equipe = eq.id_equipe
        inc.t_affectation = t
        self._ouvrir(eq, "trajet", t, t + duree, inc, (eq.lat, eq.lon), (inc.lat, inc.lon))
        self._pousser(t + duree, "ARRIVEE", eq.id_equipe)
        self.decisions.append({"t": t, "id_equipe": eq.id_equipe, "id_incident": inc.id_incident,
                               "explication": json.dumps({"origine": origine, **analyse,
                                                          "detail_strategie": explication or {}},
                                                         ensure_ascii=False, default=str)})

    def _valider(self, a: Affectation, t: int, libres: dict, attente: dict) -> str | None:
        if a.id_equipe not in libres:
            return "équipe non disponible"
        if a.id_incident not in attente:
            return "incident non en attente"
        if (a.id_equipe, a.id_incident) in self.interdites:
            return "affectation interdite par le responsable"
        eq, inc = libres[a.id_equipe], attente[a.id_incident]
        if not est_faisable(eq, inc, self.trajet_min(eq.lat, eq.lon, inc.lat, inc.lon), t, self.params):
            return "amplitude insuffisante"
        return None

    def _decider(self, t: int) -> None:
        etat = self._etat(t)
        if not etat.equipes_disponibles or not etat.incidents_en_attente:
            return
        libres = {e.id_equipe: e for e in etat.equipes_disponibles}
        attente = {i.id_incident: i for i in etat.incidents_en_attente}

        # 1) décisions forcées par le responsable (dès que l'équipe et l'incident sont prêts)
        for id_eq, id_inc in list(self.forcees.items()):
            if id_eq in libres and id_inc in attente:
                a = Affectation(id_eq, id_inc, {"forcee": True})
                motif = self._valider(a, t, libres, attente)
                if motif and motif != "affectation interdite par le responsable":
                    self.rejets.append({"t": t, "id_equipe": id_eq, "id_incident": id_inc, "motif": motif})
                    continue
                self._lancer(libres.pop(id_eq), attente.pop(id_inc), t, {"forcee": True}, "humain")
                del self.forcees[id_eq]
        if not libres or not attente:
            return

        # 2) stratégie (elle ne voit ni les équipes déjà parties ni les incidents réservés par une décision forcée)
        reserves = set(self.forcees.values())
        etat.equipes_disponibles = [e for e in etat.equipes_disponibles if e.id_equipe in libres
                                    and e.id_equipe not in self.forcees]
        etat.incidents_en_attente = [i for i in etat.incidents_en_attente if i.id_incident in attente
                                     and i.id_incident not in reserves]
        if not etat.equipes_disponibles or not etat.incidents_en_attente:
            return
        exclues: set[str] = set()
        for _passe in range(3):     # passes 2 et 3 : si la stratégie a proposé un couple interdit
            interdit_vu = False
            for a in self.policy.decide(etat, self.trajet_min) or []:
                motif = self._valider(a, t, libres, attente)
                if motif:
                    self.rejets.append({"t": t, "id_equipe": a.id_equipe, "id_incident": a.id_incident,
                                        "motif": motif})
                    if motif.startswith("affectation interdite"):
                        interdit_vu = True
                        exclues.add(a.id_equipe)
                    continue
                self._lancer(libres.pop(a.id_equipe), attente.pop(a.id_incident), t, a.explication,
                             getattr(self.policy, "nom", type(self.policy).__name__))
            if not interdit_vu:
                break
            etat.equipes_disponibles = [e for e in etat.equipes_disponibles
                                        if e.id_equipe in libres and e.id_equipe not in exclues]
            etat.incidents_en_attente = [i for i in etat.incidents_en_attente if i.id_incident in attente]
            if not etat.equipes_disponibles or not etat.incidents_en_attente:
                break

    # ------------------------------------------------------------------ boucle principale
    def executer(self) -> SimResult:
        debut = time.perf_counter()
        for inc in self.incidents.values():
            inc.etat = EtatIncident.NON_APPARU
            self._pousser(inc.t_apparition, "APPARITION", inc.id_incident)
        roulement = bool(self.params.get("roulement_actif", False))
        pct_premier = float(self.params.get("pct_premier_roulement", 0.75))
        n_equipes = len(self.equipes)

        if roulement and n_equipes >= 3:
            k = max(1, min(n_equipes - 1, int(round(n_equipes * pct_premier))))

            def _cle_equipe(e: Equipe):
                idx = int(e.id_equipe.rsplit("_E", 1)[1]) if "_E" in e.id_equipe else 0
                return (idx, e.id_site, e.id_equipe)

            equipes_triees = sorted(self.equipes.values(), key=_cle_equipe)
            cohorte_1 = set(e.id_equipe for e in equipes_triees[:k])
            self._roulement_actif = True
            self.params["_roulement_actif"] = True
            self._cohorte = {e.id_equipe: (1 if e.id_equipe in cohorte_1 else 2) for e in self.equipes.values()}
        else:
            cohorte_1 = set(self.equipes.keys())
            self._roulement_actif = False
            self.params["_roulement_actif"] = False
            self._cohorte = {e.id_equipe: 1 for e in self.equipes.values()}

        amplitude_max = int(self.params["amplitude_max_min"])
        for eq in self.equipes.values():
            if eq.id_equipe in cohorte_1:
                self._nouvelle_amplitude(eq, eq.t_debut_service)
            else:
                site = self.sites.get(eq.id_site)
                coord = (site.lat, site.lon) if site else (eq.lat, eq.lon)
                eq.etat = EtatEquipe.REPOS
                eq.t_debut_service = amplitude_max
                eq.t_libre = amplitude_max
                self._ouvrir(eq, "repos", 0, amplitude_max, None, coord, coord)
                self._pousser(amplitude_max, "FIN_REPOS", eq.id_equipe)
        self._indispo_fin: dict[int, int | None] = {}
        for d in self.indispos:
            if d.id_equipe not in self.equipes:
                raise ValueError(f"indisponibilité : équipe inconnue {d.id_equipe}")
            self._pousser(d.t_debut, "INDISPO", d.id_equipe)
            self._indispo_fin[self._seq] = d.t_fin

        t = 0
        while self._file:
            t = self._file[0].t
            if t > HORIZON_MAX_MIN:
                log.warning("horizon max atteint (%s min) : simulation arrêtée", HORIZON_MAX_MIN)
                break
            while self._file and self._file[0].t == t:          # T1/T2 : tous les événements de l'instant t
                self._traiter(heapq.heappop(self._file))
            self._decider(t)                                     # T3/T4 : une décision par instant
            if all(i.etat is EtatIncident.RESOLU for i in self.incidents.values()):
                break                                            # T5 : crise terminée

        t_fin = t
        for a in self.activites:                                 # tronquer repos / HS qui dépassent la fin
            a["t_fin"] = min(a["t_fin"], max(t_fin, a["t_debut"]))
        return self._resultat(t_fin, time.perf_counter() - debut)

    # ------------------------------------------------------------------ sorties
    def _resultat(self, t_fin: int, duree_s: float) -> SimResult:
        df_inc = pd.DataFrame([{
            "id_incident": i.id_incident, "id_poste": i.id_poste, "lat": i.lat, "lon": i.lon,
            "nb_clients": i.nb_clients, "sensible": i.sensible, "commune": None, "departement": None,
            "t_apparition": i.t_apparition, "t_affectation": i.t_affectation, "t_arrivee": i.t_arrivee,
            "t_resolution": i.t_resolution, "id_equipe": i.id_equipe, "duree_reelle": i.duree_reelle,
            "duree_nominale": i.duree_nominale, "cause": i.cause,
        } for i in self.incidents.values()])
        df_act = pd.DataFrame(self.activites, columns=COLONNES_SIMRESULT["activites"])
        df_dec = pd.DataFrame(self.decisions, columns=COLONNES_SIMRESULT["decisions"])
        serie = construire_serie(df_inc, df_act, len(self.equipes), t_fin, int(self.params["pas_instantane_min"]))

        non_resolus = int(df_inc["t_resolution"].isna().sum())
        resolus = df_inc.dropna(subset=["t_resolution"])
        sigma_nt = float(((resolus["t_resolution"] - resolus["t_apparition"]) * resolus["nb_clients"]).sum() / 60)
        meta = {
            **self.meta,
            "strategie": getattr(self.policy, "nom", type(self.policy).__name__),
            "nb_equipes": len(self.equipes),
            "nb_incidents": len(self.incidents),
            "non_resolus": non_resolus,
            "t_fin_min": int(t_fin),
            "clients_heures": round(sigma_nt, 1),
            "nb_decisions": len(self.decisions),
            "rejets": self.rejets,
            "monte_carlo": bool(self._mc().get("actif")),
            "seed": self.params.get("seed"),
            "duree_calcul_s": round(duree_s, 3),
            "params": {k: (sorted(v) if isinstance(v, frozenset) else v)
                       for k, v in self.params.items() if k != "trajet"},
        }
        if non_resolus:
            log.warning("%s incidents non résolus (plus aucune équipe ne peut les prendre)", non_resolus)
        return SimResult(incidents=df_inc, activites=df_act, decisions=df_dec, serie=serie, metadata=meta)


def construire_serie(df_inc: pd.DataFrame, df_act: pd.DataFrame, nb_equipes: int, t_fin: int, pas: int) -> pd.DataFrame:
    """Instantanés tous les `pas` minutes (0, pas, 2·pas, …, ≥ t_fin).

    clients_coupes compte chaque POSTE une seule fois (piège P9 : 2 incidents ouverts sur le même poste).
    """
    ts = np.arange(0, t_fin + pas, pas)
    app = df_inc["t_apparition"].to_numpy()
    res = df_inc["t_resolution"].fillna(np.inf).to_numpy(dtype=float)
    aff = df_inc["t_affectation"].fillna(np.inf).to_numpy(dtype=float)
    postes = df_inc["id_poste"].to_numpy()
    clients = df_inc["nb_clients"].to_numpy()

    lignes = []
    for t in ts:
        ouvert = (app <= t) & (res > t)
        vus = dict(zip(postes[ouvert], clients[ouvert], strict=True))
        en_attente = int(((app <= t) & (aff > t)).sum())
        actifs = df_act[(df_act["t_debut"] <= t) & (df_act["t_fin"] > t)]
        occupees = int(actifs["type"].isin(["trajet", "chantier"]).sum())
        repos = int(actifs["type"].isin(["retour", "repos"]).sum())
        hs = int((actifs["type"] == "hors_service").sum())
        lignes.append({"t": int(t), "clients_coupes": int(sum(vus.values())), "incidents_attente": en_attente,
                       "equipes_occupees": occupees, "equipes_repos": repos, "equipes_hs": hs,
                       "equipes_disponibles": nb_equipes - occupees - repos - hs})
    return pd.DataFrame(lignes)


def simuler(
    sites: list[Site],
    equipes: list[Equipe],
    incidents: list[Incident],
    policy: Policy,
    params: dict | None = None,
    trajet_min: TrajetMin | None = None,
    **options,
) -> SimResult:
    """Raccourci : Simulateur(...).executer(). Options : indisponibilites, forcees, interdites, meta."""
    return Simulateur(sites, equipes, incidents, policy, params, trajet_min, **options).executer()


def simuler_crise(numero_crise, policy: Policy, params: dict | None = None, scenario: dict | None = None,
                  trajet_min: TrajetMin | None = None, **options) -> SimResult:
    """Charge la crise (charger_scenario) puis la simule. `scenario` = params de charger_scenario."""
    from crise.models import _dossier_clean, _lire_tables, charger_scenario, normaliser_numero_crise

    sites, equipes, incidents = charger_scenario(numero_crise, scenario)
    meta = {"crise": normaliser_numero_crise(numero_crise), **options.pop("meta", {})}
    res = simuler(sites, equipes, incidents, policy, params, trajet_min, meta=meta, **options)
    # compléter commune / département (utiles pour la carte, le Gini et le point préfecture)
    _, df_all = _lire_tables(str(_dossier_clean(None)))
    geo = df_all.set_index("id_incident")[["commune", "departement"]]
    res.incidents["commune"] = res.incidents["id_incident"].map(geo["commune"])
    res.incidents["departement"] = res.incidents["id_incident"].map(geo["departement"])
    return res
