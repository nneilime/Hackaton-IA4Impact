"""Carte de risque (KDE / K-Means) + p-médiane capacitaire (OR-Tools).

Tâche(s) : T3.3, T3.4 — propriétaire : P3.
Voir docs/PLAN_EQUIPE_DEFI_ENEDIS.md §5.6 et docs/TACHES_RESTANTES.md (Fiche F).
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans

from crise.config import charger_config, chemin_projet
from crise.models import (
    Site,
    _dossier_clean,
    _lire_tables,
    charger_scenario,
    normaliser_numero_crise,
)
from crise.trajet import distance_haversine_km, faire_trajet_min

if TYPE_CHECKING:
    import folium

log = logging.getLogger("crise.prepositionnement")


def carte_risque(
    crises: list[int | str] | None = None,
    clean_dir: str | Path | None = None,
    alpha: float = 5.0,
    n_clusters: int = 200,
    random_state: int = 42,
) -> pd.DataFrame:
    """T3.3 — Calcule la carte de risque spatiale sur les crises d'apprentissage.

    Pondère chaque incident par :
        poids = nb_clients * (1 + alpha * sensible)
    Puis agrège en n_clusters zones de demande via KMeans pondéré.

    Renvoie un DataFrame avec colonnes : ["lat", "lon", "poids"].
    """
    if crises is None:
        crises = list(range(1, 81))  # Crises 1 à 80 par défaut (ensemble d'apprentissage)

    dossier = _dossier_clean(clean_dir)
    _, df_inc = _lire_tables(str(dossier))

    crises_set = {normaliser_numero_crise(c) for c in crises}
    sel = df_inc[df_inc["numero_crise"].isin(crises_set)].copy()
    if sel.empty:
        raise ValueError(f"Aucun incident trouvé pour les crises spécifiées : {crises[:5]}")

    poids = sel["nb_clients"].to_numpy(dtype=float) * (1.0 + alpha * sel["sensible"].astype(float).to_numpy())
    coords = sel[["lat", "lon"]].to_numpy(dtype=float)

    n_centres = min(n_clusters, len(sel))
    km = KMeans(n_clusters=n_centres, random_state=random_state, n_init="auto")
    km.fit(coords, sample_weight=poids)

    centres = km.cluster_centers_
    poids_totaux = np.bincount(km.labels_, weights=poids, minlength=n_centres)

    res = pd.DataFrame({
        "lat": np.round(centres[:, 0], 6),
        "lon": np.round(centres[:, 1], 6),
        "poids": np.round(poids_totaux, 2),
    })
    return res.sort_values("poids", ascending=False).reset_index(drop=True)


def exporter_carte_chaleur_folium(
    zones_ou_incidents: pd.DataFrame,
    chemin_sortie: str | Path | None = None,
    centre: tuple[float, float] = (43.3, 1.2),
    zoom_start: int = 8,
) -> folium.Map:
    """T3.3 — Génère une carte de chaleur Folium (Leaflet) du risque et l'enregistre en HTML."""
    import folium
    from folium.plugins import HeatMap

    m = folium.Map(location=list(centre), zoom_start=zoom_start, tiles="OpenStreetMap")

    # Normalisation des poids pour le gradient Folium
    df = zones_ou_incidents.copy()
    p_max = df["poids"].max() if "poids" in df.columns and df["poids"].max() > 0 else 1.0
    data = [
        [row["lat"], row["lon"], float(row["poids"]) / float(p_max)]
        for _, row in df.iterrows()
    ]
    HeatMap(data, radius=18, blur=14, max_zoom=10).add_to(m)

    if chemin_sortie is not None:
        p = Path(chemin_sortie)
        p.parent.mkdir(parents=True, exist_ok=True)
        m.save(str(p))
        log.info("Carte de chaleur enregistrée : %s", p)

    return m


def selectionner_candidats(
    zones: pd.DataFrame,
    sites: list[Site],
    n_avances: int = 20,
) -> list[tuple[float, float]]:
    """T3.4 — Sélectionne les points candidats pour le prépositionnement :
    les coordonnées des sites opérationnels, suivis des n_avances centres de zones
    de plus fort poids.
    """
    candidats: list[tuple[float, float]] = [(float(s.lat), float(s.lon)) for s in sites]
    if n_avances > 0 and not zones.empty:
        zones_triees = zones.sort_values("poids", ascending=False)
        for _, row in zones_triees.head(n_avances).iterrows():
            candidats.append((float(row["lat"]), float(row["lon"])))
    return candidats


def _resoudre_milp_or_tools(
    w_d: np.ndarray,
    cout: np.ndarray,
    n_equipes: int,
    max_par_point: int,
    time_limit_s: float,
) -> list[int] | None:
    """Résout le MILP p-médiane avec capacité via OR-Tools SCIP."""
    try:
        from ortools.linear_solver import pywraplp

        solver = pywraplp.Solver.CreateSolver("SCIP")
        if solver is None:
            solver = pywraplp.Solver.CreateSolver("CBC")
        if solver is None:
            return None

        D, K = cout.shape
        w_total = float(w_d.sum())
        capa = max((w_total / n_equipes) * 1.25, float(np.max(w_d)) * 1.05) if w_total > 0 else 1e9

        n_vars = [solver.IntVar(0, max_par_point, f"n_{k}") for k in range(K)]
        x_vars = {}
        for d in range(D):
            for k in range(K):
                x_vars[d, k] = solver.NumVar(0.0, 1.0, f"x_{d}_{k}")

        # Total équipes
        solver.Add(solver.Sum(n_vars) == n_equipes)

        # Chaque zone d est entièrement desservie
        for d in range(D):
            solver.Add(solver.Sum([x_vars[d, k] for k in range(K)]) == 1.0)

        # Capacité par point candidat
        for k in range(K):
            solver.Add(solver.Sum([w_d[d] * x_vars[d, k] for d in range(D)]) <= capa * n_vars[k])

        # Objectif min sum w_d * cout_dk * x_dk
        objective = solver.Objective()
        for d in range(D):
            for k in range(K):
                objective.SetCoefficient(x_vars[d, k], float(w_d[d] * cout[d, k]))
        objective.SetMinimization()

        solver.SetTimeLimit(int(time_limit_s * 1000))
        status = solver.Solve()

        if status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
            res = [int(round(v.solution_value())) for v in n_vars]
            # Ajustement si léger écart d'arrondi
            diff = n_equipes - sum(res)
            if diff != 0:
                for k in range(K):
                    if diff > 0 and res[k] < max_par_point:
                        res[k] += 1
                        diff -= 1
                    elif diff < 0 and res[k] > 0:
                        res[k] -= 1
                        diff += 1
                    if diff == 0:
                        break
            if sum(res) == n_equipes:
                return res
    except Exception as e:
        log.warning("Erreur OR-Tools MILP : %s", e)
    return None


def positions_pmediane(
    zones: pd.DataFrame,
    sites: list[Site],
    n_equipes: int = 63,
    n_avances: int = 20,
    max_par_point: int = 8,
    time_limit_s: float = 60.0,
) -> dict[str, tuple[float, float]]:
    """T3.4 — Prépositionnement p-médiane capacitaire sous OR-Tools.

    Renvoie un dictionnaire {id_equipe: (lat, lon)} pour n_equipes équipes.
    """
    candidats = selectionner_candidats(zones, sites, n_avances=n_avances)
    K = len(candidats)
    D = len(zones)

    cfg = charger_config()
    trajet_fn = faire_trajet_min(cfg)

    # Matrice de coût zone d -> candidat k
    z_coords = zones[["lat", "lon"]].to_numpy(dtype=float)
    c_coords = np.array(candidats, dtype=float)
    cout = np.zeros((D, K), dtype=float)
    for d in range(D):
        for k in range(K):
            cout[d, k] = trajet_fn(z_coords[d, 0], z_coords[d, 1], c_coords[k, 0], c_coords[k, 1])

    w_d = zones["poids"].to_numpy(dtype=float) if "poids" in zones.columns else np.ones(D, dtype=float)

    n_assign = _resoudre_milp_or_tools(w_d, cout, n_equipes, max_par_point, time_limit_s)
    if n_assign is None:
        # Repli glouton : affectation proportionnelle aux zones les plus lourdes
        log.warning("Repli sur heuristique gloutonne pour le prépositionnement.")
        poids_candidats = np.zeros(K)
        for d in range(D):
            plus_proche = int(np.argmin(cout[d]))
            poids_candidats[plus_proche] += w_d[d]
        ordre = np.argsort(-poids_candidats)
        n_assign = [0] * K
        restant = n_equipes
        for k in ordre:
            attrib = min(restant, max_par_point)
            n_assign[k] = attrib
            restant -= attrib
            if restant <= 0:
                break

    # Construction de la liste des créneaux
    slots: list[tuple[float, float]] = []
    for k, nb in enumerate(n_assign):
        for _ in range(nb):
            slots.append(candidats[k])

    # Équipes et appariement optimal avec linear_sum_assignment
    all_teams: list[str] = []
    team_site_coords: dict[str, tuple[float, float]] = {}
    for s in sites:
        for k in range(1, s.nb_equipes + 1):
            eq_id = f"{s.id_site}_E{k}"
            all_teams.append(eq_id)
            team_site_coords[eq_id] = (float(s.lat), float(s.lon))
    all_teams = all_teams[:n_equipes]

    cost_matrix = np.zeros((len(all_teams), len(slots)), dtype=float)
    for i, eq in enumerate(all_teams):
        h_lat, h_lon = team_site_coords[eq]
        for j, (s_lat, s_lon) in enumerate(slots):
            cost_matrix[i, j] = trajet_fn(h_lat, h_lon, s_lat, s_lon)

    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    return {all_teams[r]: slots[c] for r, c in zip(row_ind, col_ind, strict=False)}


def positions_kmeans(
    zones: pd.DataFrame,
    sites: list[Site],
    n_equipes: int = 63,
    random_state: int = 42,
) -> dict[str, tuple[float, float]]:
    """T3.4 — Prépositionnement de référence par K-Means à n_equipes centres."""
    coords = zones[["lat", "lon"]].to_numpy(dtype=float)
    weights = zones["poids"].to_numpy(dtype=float) if "poids" in zones.columns else None

    n_centres = min(n_equipes, len(coords))
    km = KMeans(n_clusters=n_centres, random_state=random_state, n_init="auto")
    km.fit(coords, sample_weight=weights)

    centres = [(float(c[0]), float(c[1])) for c in km.cluster_centers_]
    # Si moins de centres que d'équipes, compléter avec les sites
    slots: list[tuple[float, float]] = list(centres)
    idx_site = 0
    while len(slots) < n_equipes:
        s = sites[idx_site % len(sites)]
        slots.append((float(s.lat), float(s.lon)))
        idx_site += 1

    all_teams: list[str] = []
    team_site_coords: dict[str, tuple[float, float]] = {}
    for s in sites:
        for k in range(1, s.nb_equipes + 1):
            eq_id = f"{s.id_site}_E{k}"
            all_teams.append(eq_id)
            team_site_coords[eq_id] = (float(s.lat), float(s.lon))
    all_teams = all_teams[:n_equipes]

    cfg = charger_config()
    trajet_fn = faire_trajet_min(cfg)
    cost_matrix = np.zeros((len(all_teams), len(slots)), dtype=float)
    for i, eq in enumerate(all_teams):
        h_lat, h_lon = team_site_coords[eq]
        for j, (s_lat, s_lon) in enumerate(slots):
            cost_matrix[i, j] = trajet_fn(h_lat, h_lon, s_lat, s_lon)

    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    return {all_teams[r]: slots[c] for r, c in zip(row_ind, col_ind, strict=False)}


def evaluer_prepositionnement(
    crises_apprentissage: list[int | str] | None = None,
    crises_test: list[int | str] | None = None,
    clean_dir: str | Path | None = None,
    n_clusters: int = 200,
    n_avances: int = 20,
    max_par_point: int = 8,
    n_jobs: int = -1,
    dossier_sortie: str | Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """T3.4 — Évalue les 3 configurations (Sites de base, K-Means, p-médiane) sur les crises de test."""
    from crise.benchmark import lancer, resoudre_strategie
    from crise.config import charger_config

    dossier = Path(dossier_sortie or chemin_projet(charger_config()["chemins"]["outputs"]))
    dossier.mkdir(parents=True, exist_ok=True)

    crises_app = [int(c) for c in (crises_apprentissage if crises_apprentissage is not None else range(1, 81))]
    crises_tst = [int(c) for c in (crises_test if crises_test is not None else range(81, 101))]

    # 1. Carte de risque
    zones = carte_risque(crises=crises_app, clean_dir=clean_dir, n_clusters=n_clusters)
    zones.to_csv(dossier / "carte_risque.csv", index=False)
    exporter_carte_chaleur_folium(zones, chemin_sortie=dossier / "carte_chaleur.html")
    exporter_carte_chaleur_folium(zones, chemin_sortie=dossier / "carte_chaleur_risque.html")

    # 2. Sites & calcul des positions
    sites, _, _ = charger_scenario(crises_app[0], clean_dir=clean_dir)
    pos_pmed = positions_pmediane(
        zones, sites, n_equipes=63, n_avances=n_avances, max_par_point=max_par_point
    )
    sites_dict = {s.id_site: s for s in sites}
    lignes_pos = []
    for eq_id, (lat_init, lon_init) in pos_pmed.items():
        site_id = eq_id.rsplit("_E", 1)[0]
        s = sites_dict[site_id]
        d_km = distance_haversine_km(lat_init, lon_init, s.lat, s.lon)
        lignes_pos.append({
            "id_equipe": eq_id,
            "id_site": site_id,
            "commune_site": s.commune,
            "lat_site": s.lat,
            "lon_site": s.lon,
            "lat_initiale": lat_init,
            "lon_initiale": lon_init,
            "deplace": bool(d_km > 0.1),
            "distance_km": round(float(d_km), 2),
        })
    df_pmed = pd.DataFrame(lignes_pos).sort_values("id_equipe")
    df_pmed.to_csv(dossier / "positions_pmediane.csv", index=False)

    pos_km = positions_kmeans(zones, sites, n_equipes=63)

    # 3. Évaluation sur les crises de test avec WSPT
    strat = resoudre_strategie("WSPT")
    opts = {"clean_dir": clean_dir} if clean_dir else None

    kpi_base, _ = lancer(crises_tst, {"WSPT": strat}, scenario=None, options=opts, n_jobs=n_jobs)
    kpi_base["configuration"] = "Sites (base)"

    kpi_km, _ = lancer(
        crises_tst, {"WSPT": strat}, scenario={"positions_initiales": pos_km}, options=opts, n_jobs=n_jobs
    )
    kpi_km["configuration"] = "K-Means (63 centres)"

    kpi_pmed, _ = lancer(
        crises_tst, {"WSPT": strat}, scenario={"positions_initiales": pos_pmed}, options=opts, n_jobs=n_jobs
    )
    kpi_pmed["configuration"] = "p-médiane (MILP)"

    details = pd.concat([kpi_base, kpi_km, kpi_pmed], ignore_index=True)
    details.to_csv(dossier / "prepositionnement.csv", index=False)

    kpi_cols = [
        c for c in [
            "clients_heures",
            "pct_clients_retablis_4h",
            "attente_moy_sensible_h",
            "attente_max_sensible_h",
            "gini_communes",
            "saturation_pct",
            "fin_crise_h",
        ] if c in details.columns
    ]
    resume = details.groupby("configuration")[kpi_cols].mean()
    resume = resume.reindex(["Sites (base)", "K-Means (63 centres)", "p-médiane (MILP)"])

    piv = details.pivot(index="crise", columns="configuration", values="clients_heures")
    if "Sites (base)" in piv.columns:
        ref = piv["Sites (base)"]
        for var in resume.index:
            gain_pct = float(100.0 * (1.0 - piv[var] / ref).mean())
            gagnees = int((piv[var] < ref).sum())
            resume.loc[var, "gain_vs_sites_pct"] = round(gain_pct, 2)
            resume.loc[var, "crises_gagnees_vs_sites"] = gagnees

    resume = resume.round(2)
    resume.to_csv(dossier / "prepositionnement_resume.csv")
    return resume, details


def main(argv: list[str] | None = None) -> None:

    parser = argparse.ArgumentParser(description="Carte de risque et prépositionnement p-médiane.")
    parser.add_argument("--crises-train", default="1-80", help="Crises d'apprentissage (défaut : 1-80).")
    parser.add_argument("--crises-test", default="81-100", help="Crises de test (défaut : 81-100).")
    parser.add_argument("--clusters", type=int, default=200, help="Nombre de zones de demande (défaut : 200).")
    parser.add_argument("--avances", type=int, default=20, help="Nombre de points candidats avancés (défaut : 20).")
    parser.add_argument("--jobs", type=int, default=2, help="Parallélisme (-1 pour tous les cœurs).")
    args = parser.parse_args(argv)

    from crise.benchmark import parser_crises

    crises_trn = parser_crises(args.crises_train)
    crises_tst = parser_crises(args.crises_test)
    resume, _ = evaluer_prepositionnement(
        crises_apprentissage=crises_trn,
        crises_test=crises_tst,
        n_clusters=args.clusters,
        n_avances=args.avances,
        n_jobs=args.jobs,
    )
    print("\n=== Résumé Prépositionnement ===")
    print(resume.to_string())


if __name__ == "__main__":
    main()

