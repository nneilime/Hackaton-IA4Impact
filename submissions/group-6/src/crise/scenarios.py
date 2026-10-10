"""Scénarios de stress tests (T3.6) : S1 à S5 et 2e vague.

Tâche(s) : T1.8, T3.6, T3.7 — propriétaire : P1, P3.
Voir docs/PLAN_EQUIPE_DEFI_ENEDIS.md §5.5 et docs/TACHES_RESTANTES.md (Fiche D).

Scénarios implémentés :
- S1 : Routes coupées en montagne (vitesse ÷ 3 en zone montagne)
- S2 : −30 % d'équipes hors service à H+3 (t = 180 min, 1 équipe sur 3)
- S3 : 2e vague à H+6 (crise n+1 décalée de +6h = 360 min)
- S4 : 2 crises successives (décalage 24h = 1440 min) + 50 % d'équipes indisponibles après 48h (t = 2880 min)
- S5 : Effectif d'urgence (20 équipes seulement)
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from pathlib import Path

import pandas as pd

from crise.config import charger_config, chemin_projet
from crise.kpi import calculer_kpi
from crise.models import (
    Equipe,
    Incident,
    Site,
    _dossier_clean,
    _lire_tables,
    charger_scenario,
    normaliser_numero_crise,
)
from crise.policies.base import Policy
from crise.policies.baselines import PlusDeClients, PlusProcheFCFS
from crise.simulateur import (
    Indisponibilite,
    SimResult,
    TrajetMin,
    parametres_simulation,
    simuler,
)
from crise.trajet import ZONE_MONTAGNE, faire_trajet_min

log = logging.getLogger("crise.scenarios")

SCENARIOS_CATALOGUE: dict[str, str] = {
    "S1": "S1 : Routes coupées (montagne)",
    "S2": "S2 : −30% équipes à H+3",
    "S3": "S3 : 2e vague à H+6",
    "S4": "S4 : 2 crises + −50% éq. (48h)",
    "S5": "S5 : 20 équipes (ressource rare)",
}


def normaliser_nom_scenario(nom: str) -> tuple[str, str]:
    """Renvoie (code, label) ex: ('S1', 'S1 : Routes coupées (montagne)')."""
    nom_propre = nom.strip()
    nom_upper = nom_propre.upper()
    if nom_upper in ("NOMINAL", "S0", "BASE", "STANDARD"):
        return "S0", "Nominal (standard)"
    for code, label in SCENARIOS_CATALOGUE.items():
        if nom_upper == code or nom_propre.startswith(code) or code in nom_upper:
            return code, label
    if "ROUTE" in nom_upper or "MONTAGNE" in nom_upper:
        return "S1", SCENARIOS_CATALOGUE["S1"]
    if "30" in nom_upper or "H+3" in nom_upper or "HS" in nom_upper:
        return "S2", SCENARIOS_CATALOGUE["S2"]
    if "VAGUE" in nom_upper or "H+6" in nom_upper:
        return "S3", SCENARIOS_CATALOGUE["S3"]
    if "48H" in nom_upper or "50" in nom_upper or "CUMUL" in nom_upper:
        return "S4", SCENARIOS_CATALOGUE["S4"]
    if "20" in nom_upper or "PEU" in nom_upper or "RARE" in nom_upper:
        return "S5", SCENARIOS_CATALOGUE["S5"]
    return nom_propre, nom_propre


def _extraire_numero_crise(crise: int | str) -> int:
    """Extrait l'entier d'un numéro de crise (1 à 100)."""
    if isinstance(crise, int):
        return crise
    s = str(crise).strip().upper()
    m = re.search(r"(\d+)", s)
    if m:
        return int(m.group(1))
    raise ValueError(f"Numéro de crise invalide : {crise}")


def deuxieme_vague(
    numero_crise: int | str,
    decalage_min: int = 360,
    clean_dir: str | Path | None = None,
) -> tuple[list[Site], list[Equipe], list[Incident]]:
    """T1.8, T3.6 — Génère un scénario combiné de 2 crises (2e vague).

    Incidents de la crise n + incidents de la crise n+1 (crise 1 si n=100)
    avec t_apparition += decalage_min et id_incident préfixé par 'V2_'.
    """
    n = _extraire_numero_crise(numero_crise)
    suivante = 1 if n >= 100 else n + 1

    sites, equipes, inc_v1 = charger_scenario(n, clean_dir=clean_dir)
    _, _, inc_v2_bruts = charger_scenario(suivante, clean_dir=clean_dir)

    inc_v2 = [
        Incident(
            id_incident=f"V2_{inc.id_incident}",
            id_poste=inc.id_poste,
            t_apparition=int(inc.t_apparition + decalage_min),
            duree_nominale=int(inc.duree_nominale),
            duree_reelle=int(inc.duree_reelle),
            cause=inc.cause,
            nb_clients=int(inc.nb_clients),
            sensible=bool(inc.sensible),
            lat=float(inc.lat),
            lon=float(inc.lon),
        )
        for inc in inc_v2_bruts
    ]

    tous_incidents = sorted(inc_v1 + inc_v2, key=lambda i: (i.t_apparition, i.id_incident))
    return sites, equipes, tous_incidents


def construire(
    nom: str,
    numero_crise: int | str,
    cfg: dict | None = None,
    clean_dir: str | Path | None = None,
) -> dict:
    """Construit la configuration complète d'un scénario de stress test.

    Renvoie un dictionnaire avec :
    - 'code' : code du scénario ('S1' à 'S5' ou 'S0')
    - 'label' : libellé lisible du scénario
    - 'sites' : liste des sites
    - 'equipes' : liste des équipes
    - 'incidents' : liste des incidents
    - 'trajet_min' : fonction de calcul de trajet
    - 'options' : options pour simuler (ex. indisponibilites)
    """
    if cfg is None:
        cfg = charger_config()

    code, label = normaliser_nom_scenario(nom)
    options: dict = {}
    trajet_min: TrajetMin = faire_trajet_min(cfg)

    if code == "S0":
        sites, equipes, incidents = charger_scenario(numero_crise, clean_dir=clean_dir)

    elif code == "S1":
        # S1 : Routes coupées en montagne (vitesse divisée par 3 en zone pyrénéenne)
        sites, equipes, incidents = charger_scenario(numero_crise, clean_dir=clean_dir)
        trajet_min = faire_trajet_min(cfg, zones=[ZONE_MONTAGNE])

    elif code == "S2":
        # S2 : −30 % d'équipes hors service à H+3 (t = 180 min, 1 équipe sur 3)
        sites, equipes, incidents = charger_scenario(numero_crise, clean_dir=clean_dir)
        # 1 équipe sur 3 devient hors service à H+3
        options["indisponibilites"] = [
            Indisponibilite(id_equipe=e.id_equipe, t_debut=180)
            for e in equipes[::3]
        ]

    elif code == "S3":
        # S3 : 2e vague à H+6 (360 min)
        sites, equipes, incidents = deuxieme_vague(numero_crise, decalage_min=360, clean_dir=clean_dir)

    elif code == "S4":
        # S4 : 2 crises successives (décalage 24h = 1440 min) + 50 % indisponibles après 48h (2880 min)
        sites, equipes, incidents = deuxieme_vague(numero_crise, decalage_min=1440, clean_dir=clean_dir)
        # 1 équipe sur 2 indisponible après 48h (critère du jury pour fatigue extrême)
        options["indisponibilites"] = [
            Indisponibilite(id_equipe=e.id_equipe, t_debut=2880)
            for e in equipes[::2]
        ]

    elif code == "S5":
        # S5 : 20 équipes seulement (mobilisation minimale d'urgence)
        sites, equipes, incidents = charger_scenario(
            numero_crise, params={"nb_equipes_max": 20}, clean_dir=clean_dir
        )

    else:
        # Fallback nominal
        sites, equipes, incidents = charger_scenario(numero_crise, clean_dir=clean_dir)

    return {
        "code": code,
        "label": label,
        "sites": sites,
        "equipes": equipes,
        "incidents": incidents,
        "trajet_min": trajet_min,
        "options": options,
    }


def simuler_scenario(
    nom: str,
    numero_crise: int | str,
    policy: Policy,
    params: dict | None = None,
    cfg: dict | None = None,
    clean_dir: str | Path | None = None,
    **surcharges_options,
) -> SimResult:
    """Simule un scénario de stress et renvoie le SimResult enrichi."""
    spec = construire(nom, numero_crise, cfg=cfg, clean_dir=clean_dir)
    p = dict(params or parametres_simulation(cfg))
    p.setdefault("expliquer", False)

    options = {**spec["options"], **surcharges_options}
    meta = {
        "scenario_code": spec["code"],
        "scenario_label": spec["label"],
        "crise": normaliser_numero_crise(numero_crise),
        **options.pop("meta", {}),
    }

    res = simuler(
        sites=spec["sites"],
        equipes=spec["equipes"],
        incidents=spec["incidents"],
        policy=policy,
        params=p,
        trajet_min=spec["trajet_min"],
        meta=meta,
        **options,
    )

    # Compléter géographie (commune, département) pour les analyses & cartes
    try:
        _, df_all = _lire_tables(str(_dossier_clean(clean_dir)))
        geo_commune = dict(zip(df_all["id_incident"], df_all["commune"], strict=False))
        geo_dept = dict(zip(df_all["id_incident"], df_all["departement"], strict=False))
        res.incidents["commune"] = res.incidents["id_incident"].apply(
            lambda x: geo_commune.get(x.removeprefix("V2_"), "")
        )
        res.incidents["departement"] = res.incidents["id_incident"].apply(
            lambda x: geo_dept.get(x.removeprefix("V2_"), "")
        )
    except Exception as e:
        log.debug("Impossible d'enrichir la géographie : %s", e)

    return res


def _evaluer_une_combinaison(
    code_scenar: str,
    crise: int,
    nom_strat: str,
    cls_strat: type[Policy],
    params: dict,
    cfg: dict | None,
    clean_dir: str | Path | None,
) -> dict:
    """Exécute un stress test (scénario, crise, stratégie) et calcule les KPI."""
    policy = cls_strat()
    res = simuler_scenario(
        code_scenar,
        crise,
        policy,
        params=dict(params),
        cfg=cfg,
        clean_dir=clean_dir,
    )
    k = calculer_kpi(res)
    _, label = normaliser_nom_scenario(code_scenar)
    k["scenario"] = label
    k["scenario_code"] = code_scenar
    k["strategie"] = nom_strat
    k["crise"] = normaliser_numero_crise(crise)
    k["duree_calcul_s"] = res.metadata.get("duree_calcul_s", 0.0)
    return k


def evaluer_scenarios(
    crises: list[int] | None = None,
    strategies: dict[str, type[Policy]] | None = None,
    scenarios: list[str] | None = None,
    cfg: dict | None = None,
    clean_dir: str | Path | None = None,
    n_jobs: int = -1,
    dossier_sortie: str | Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """T3.6 / T3.7 — Lance les stress tests S1 à S5 (et optionnellement Nominal).

    Sauvegarde outputs/stress_kpi.csv et outputs/stress_resume.csv.
    Renvoie (df_kpi_detaille, df_resume).
    """
    from crise.benchmark import resoudre_strategie

    if cfg is None:
        cfg = charger_config()
    if crises is None:
        crises = list(range(81, 101))  # Crises de test 81 à 100 par défaut
    if strategies is None:
        strategies = {
            "R1": PlusProcheFCFS,
            "R2": PlusDeClients,
            "WSPT": resoudre_strategie("WSPT"),
        }
    if scenarios is None:
        scenarios = ["Nominal", "S1", "S2", "S3", "S4", "S5"]

    params = parametres_simulation(cfg, expliquer=False)
    taches = [
        (sc, c, nom_strat, cls_strat, params, cfg, clean_dir)
        for sc in scenarios
        for c in crises
        for nom_strat, cls_strat in strategies.items()
    ]

    debut = time.perf_counter()
    try:
        from joblib import Parallel, delayed

        resultats = Parallel(n_jobs=n_jobs)(
            delayed(_evaluer_une_combinaison)(*t) for t in taches
        )
    except ImportError:
        resultats = [_evaluer_une_combinaison(*t) for t in taches]

    log.info("%d simulations de stress exécutées en %.1f s", len(taches), time.perf_counter() - debut)
    df_kpi = pd.DataFrame(resultats)

    # Construction du résumé par scénario et stratégie
    colonnes_num = [
        "clients_heures",
        "attente_max_sensible_h",
        "attente_moy_sensible_h",
        "pct_clients_retablis_4h",
        "depassements_amplitude",
        "non_resolus",
        "fin_crise_h",
    ]
    df_resume = df_kpi.groupby(["scenario", "strategie"])[colonnes_num].mean().reset_index()

    # Sauvegarde des fichiers de sortie
    dossier = Path(dossier_sortie or chemin_projet(cfg["chemins"]["outputs"]))
    dossier.mkdir(parents=True, exist_ok=True)

    df_kpi.to_csv(dossier / "stress_kpi.csv", index=False)
    try:
        df_kpi.to_parquet(dossier / "stress_kpi.parquet", index=False)
    except Exception:
        pass

    df_resume.to_csv(dossier / "stress_resume.csv", index=False)

    return df_kpi, df_resume


def main(argv: list[str] | None = None) -> None:
    from crise.benchmark import parser_crises, resoudre_strategie

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    ap = argparse.ArgumentParser(description="Stress tests de robustesse S1 à S5")
    ap.add_argument("--crises", default="81-100", help="Plage de crises (ex: 81-100 ou 1-5)")
    ap.add_argument("--strategies", default="R1,R2,WSPT", help="Stratégies à comparer (R1,R2,WSPT)")
    ap.add_argument("--scenarios", default="Nominal,S1,S2,S3,S4,S5", help="Scénarios (Nominal,S1,S2,S3,S4,S5)")
    ap.add_argument("--jobs", type=int, default=-1, help="Nombre de workers parallèles (-1 = tous les cœurs)")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("crise.simulateur").setLevel(logging.ERROR)

    crises = parser_crises(args.crises)
    strats = {}
    for nom in args.strategies.split(","):
        nom = nom.strip()
        if nom:
            strats[nom] = resoudre_strategie(nom)

    scenarios = [s.strip() for s in args.scenarios.split(",") if s.strip()]

    print(
        f"\n[STRESS TESTS] Lancement : {len(crises)} crises x {len(strats)} strats x {len(scenarios)} scenarios..."
    )
    df_kpi, df_resume = evaluer_scenarios(
        crises=crises,
        strategies=strats,
        scenarios=scenarios,
        n_jobs=args.jobs,
    )

    print("\n=== Synthese des Stress Tests (Moyennes) ===")
    print(df_resume.to_string(index=False))
    print(f"\n[OK] Resultats sauvegardes dans {chemin_projet('outputs')}/stress_kpi.csv\n")


if __name__ == "__main__":
    main()
