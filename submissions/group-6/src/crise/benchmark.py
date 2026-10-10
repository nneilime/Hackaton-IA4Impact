"""Banc d'essai : crises × stratégies (× graines Monte Carlo), en parallèle si joblib est installé.

Tâche(s) : T3.5, T3.7 — propriétaire : P3 (version express écrite par P1).

Ligne de commande :
    python -m crise.benchmark                              # 100 crises, R1 + R2 + WSPT (si trouvée)
    python -m crise.benchmark --crises 1-20 --strategies R1,R2
    python -m crise.benchmark --monte-carlo 5              # 5 tirages par crise et par stratégie
    python -m crise.benchmark --strategies R2,crise.policies.wspt_hongrois:MaClasse

Sorties (outputs/) :
    benchmark_kpi.csv / .parquet   une ligne par (crise, stratégie, graine)
    benchmark_series.parquet       courbes clients coupés (t, clients_coupes) pour l'interface
    benchmark_resume.csv           moyenne par stratégie + gain vs références (chiffres du pitch)
"""
from __future__ import annotations

import argparse
import importlib
import inspect
import logging
import time
from pathlib import Path

import pandas as pd

from crise.config import charger_config, chemin_projet
from crise.kpi import calculer_kpi
from crise.policies.base import Policy
from crise.policies.baselines import PlusDeClients, PlusProcheFCFS

log = logging.getLogger("crise.benchmark")


# --------------------------------------------------------------------------- stratégies
def trouver_wspt() -> type[Policy] | None:
    """Cherche la stratégie de P2 dans crise.policies.wspt_hongrois (première sous-classe de Policy instanciable)."""
    try:
        mod = importlib.import_module("crise.policies.wspt_hongrois")
    except Exception as e:                                   # noqa: BLE001
        log.warning("wspt_hongrois non importable : %s", e)
        return None
    for _, cls in inspect.getmembers(mod, inspect.isclass):
        if issubclass(cls, Policy) and cls is not Policy and cls.__module__ == mod.__name__:
            try:
                cls()
                return cls
            except TypeError:
                continue
    log.warning("aucune classe Policy sans argument trouvée dans crise.policies.wspt_hongrois")
    return None


def resoudre_strategie(nom: str) -> type[Policy]:
    """'R1', 'R2', 'WSPT' (P2, sinon express), 'WSPTX' (express) ou 'module:Classe'."""
    nom = nom.strip()
    if nom.upper() == "R1":
        return PlusProcheFCFS
    if nom.upper() == "R2":
        return PlusDeClients
    if nom.upper() == "WSPT":                    # celle de P2 si elle se branche, sinon la version express
        cls = trouver_wspt()
        if cls is None:
            from crise.policies.wspt_express import WSPTExpress

            log.warning("WSPT de P2 introuvable : utilisation de WSPTExpress")
            return WSPTExpress
        return cls
    if nom.upper() in ("WSPTX", "WSPT_EXPRESS"):
        from crise.policies.wspt_express import WSPTExpress

        return WSPTExpress
    if ":" in nom:
        module, classe = nom.split(":", 1)
        return getattr(importlib.import_module(module), classe)
    raise ValueError(f"stratégie inconnue : {nom}")


def parser_crises(spec: str) -> list[int]:
    """'1-100', '27', '1,5,27-30'."""
    out: list[int] = []
    for morceau in spec.split(","):
        if "-" in morceau:
            a, b = morceau.split("-")
            out.extend(range(int(a), int(b) + 1))
        elif morceau.strip():
            out.append(int(morceau))
    return out


# --------------------------------------------------------------------------- exécution
def _une_simulation(crise: int, nom_strat: str, cls: type[Policy], params: dict, seed: int | None,
                    scenario: dict | None, options: dict | None) -> tuple[dict, pd.DataFrame]:
    from crise.simulateur import simuler_crise

    p = dict(params)
    p.setdefault("expliquer", False)             # explications inutiles pour le banc d'essai (×10 plus rapide)
    if seed is not None:
        p["seed"] = seed
        p["monte_carlo"] = {**p.get("monte_carlo", {}), "actif": True}
    res = simuler_crise(crise, cls(), p, scenario=scenario, **(options or {}))
    k = calculer_kpi(res)
    k["strategie"] = nom_strat
    k["seed"] = seed
    k["duree_calcul_s"] = res.metadata["duree_calcul_s"]
    serie = res.serie[["t", "clients_coupes", "equipes_disponibles", "incidents_attente"]].copy()
    serie["crise"], serie["strategie"], serie["seed"] = k["crise"], nom_strat, seed if seed is not None else -1
    return k, serie


def lancer(
    crises: list[int],
    strategies: dict[str, type[Policy]],
    params: dict | None = None,
    seeds: list[int | None] | None = None,
    scenario: dict | None = None,
    options: dict | None = None,
    n_jobs: int = -1,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Renvoie (kpi, series). seeds=None → une simulation nominale (sans Monte Carlo)."""
    from crise.simulateur import parametres_simulation

    params = params or parametres_simulation()
    seeds = seeds or [None]
    # pré-vol : une stratégie qui plante sur la 1re crise est écartée au lieu de faire tomber tout le banc
    valides = {}
    for nom, cls in strategies.items():
        try:
            _une_simulation(crises[0], nom, cls, params, None, scenario, options)
            valides[nom] = cls
        except Exception as e:                               # noqa: BLE001
            log.error("stratégie %s écartée (erreur sur la crise %s) : %r", nom, crises[0], e)
    strategies = valides
    taches = [(c, n, cls, params, s, scenario, options) for c in crises for n, cls in strategies.items() for s in seeds]
    debut = time.perf_counter()
    try:
        from joblib import Parallel, delayed

        resultats = Parallel(n_jobs=n_jobs)(delayed(_une_simulation)(*t) for t in taches)
    except ImportError:
        resultats = [_une_simulation(*t) for t in taches]
    log.info("%s simulations en %.1f s", len(taches), time.perf_counter() - debut)
    kpi = pd.DataFrame([r[0] for r in resultats])
    series = pd.concat([r[1] for r in resultats], ignore_index=True)
    return kpi, series


def resumer(kpi: pd.DataFrame) -> pd.DataFrame:
    """Moyennes par stratégie + gain en % de clients·heures vs chaque référence + nb de crises gagnées."""
    cols = ["clients_heures", "pct_clients_retablis_4h", "attente_moy_sensible_h", "attente_max_sensible_h",
            "gini_communes", "saturation_pct", "fin_crise_h", "depassements_amplitude"]
    resume = kpi.groupby("strategie")[cols].mean()
    par_crise = kpi.groupby(["crise", "strategie"])["clients_heures"].mean().unstack()
    for ref in [c for c in par_crise.columns if c in ("R1", "R2")]:
        resume[f"gain_vs_{ref}_pct"] = [
            float(100 * (1 - par_crise[s] / par_crise[ref]).mean()) for s in resume.index]
        resume[f"crises_gagnees_vs_{ref}"] = [int((par_crise[s] < par_crise[ref]).sum()) for s in resume.index]
    return resume.round(2)


def sauvegarder(kpi: pd.DataFrame, series: pd.DataFrame, dossier: Path, suffixe: str = "") -> pd.DataFrame:
    dossier.mkdir(parents=True, exist_ok=True)
    kpi.to_csv(dossier / f"benchmark_kpi{suffixe}.csv", index=False)
    resume = resumer(kpi)
    resume.to_csv(dossier / f"benchmark_resume{suffixe}.csv")
    try:
        kpi.to_parquet(dossier / f"benchmark_kpi{suffixe}.parquet", index=False)
        series.to_parquet(dossier / f"benchmark_series{suffixe}.parquet", index=False)
    except ImportError:
        series.to_csv(dossier / f"benchmark_series{suffixe}.csv", index=False)
    return resume


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Banc d'essai des stratégies sur les crises")
    ap.add_argument("--crises", default="1-100")
    ap.add_argument("--strategies", default="R1,R2,WSPT")
    ap.add_argument("--monte-carlo", type=int, default=0, help="nombre de tirages (0 = nominal)")
    ap.add_argument("--jobs", type=int, default=-1)
    ap.add_argument("--suffixe", default="")
    ap.add_argument("--stress", action="store_true", help="lance également les stress tests S1 à S5")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("crise.simulateur").setLevel(logging.ERROR)

    strategies: dict[str, type[Policy]] = {}
    for nom in args.strategies.split(","):
        try:
            strategies[nom.split(":")[-1]] = resoudre_strategie(nom)
        except ValueError as e:
            log.warning("%s — ignorée", e)
    seeds = list(range(1, args.monte_carlo + 1)) if args.monte_carlo else None
    kpi, series = lancer(parser_crises(args.crises), strategies, seeds=seeds, n_jobs=args.jobs)
    dossier = chemin_projet(charger_config()["chemins"]["outputs"])
    resume = sauvegarder(kpi, series, dossier, args.suffixe)
    print("\n=== Résumé (moyennes par stratégie) ===")
    print(resume.T.to_string())
    print(f"\nFichiers écrits dans {dossier}")
    if args.stress:
        from crise.scenarios import evaluer_scenarios

        print("\n=== Lancement des stress tests S1 à S5 ===")
        _, stress_resume = evaluer_scenarios(
            crises=parser_crises(args.crises),
            strategies=strategies,
            n_jobs=args.jobs,
        )
        print(stress_resume.to_string(index=False))


if __name__ == "__main__":
    main()
