# Prépositionnement et Carte de Risque (T3.3, T3.4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement weighted risk heat map (KDE/K-Means) and capacitated p-median MILP team pre-positioning with OR-Tools, benchmark on test crises 81–100, and generate all output artifacts.

**Architecture:** 
1. `carte_risque`: Aggregates training incidents (crises 1–80) weighted by $N_i \times (1 + \alpha \cdot s_i)$ into 200 demand zones using weighted K-Means, with KDE / Folium heat map export.
2. `positions_pmediane`: Formulates and solves a capacitated p-median MILP using OR-Tools SCIP solver over 38 candidates (18 sites + 20 high-risk zones) to place 63 teams (max 8/point, capacity $\sum w / 63 \times 1.2$), then optimally matches teams to points by site proximity.
3. `positions_kmeans`: 63-center K-Means baseline.
4. Evaluation pipeline: Benchmarks the 3 configurations (Sites, K-Means, p-médiane) with WSPT on test crises 81–100 and exports `carte_risque.csv`, `positions_pmediane.csv`, and `prepositionnement.csv`.

**Tech Stack:** Python 3.11, OR-Tools (SCIP), scikit-learn (KMeans, KernelDensity), pandas, numpy, scipy (linear_sum_assignment), folium.

**Spec:** `docs/PLAN_EQUIPE_DEFI_ENEDIS.md` (§5.6) & `docs/TACHES_RESTANTES.md` (Fiche F).

## Global Constraints

- Crises 1 to 80 strictly reserved for training (learning risk / positions); crises 81 to 100 strictly reserved for testing.
- Exactly 63 teams assigned across 18 operational sites.
- Max teams per candidate point $n_k \le 8$.
- Capacity per team: $capa = (\sum w_d / 63) \times 1.2$.
- Solve time under 60 seconds.
- All code formatted and tested with pytest.

## Review Focus

1. Team IDs validation: all 63 team IDs in `positions_initiales` match `SITE_xx_Ek` format and belong to valid sites.
2. Handling edge cases where OR-Tools is interrupted or fails: greedy heuristic fallback guarantee.
3. Exact coordinate match and column naming in `outputs/carte_risque.csv` (`lat`, `lon`, `poids`).
4. Total team sum constraint: $\sum n_k = 63$ strictly enforced in integer variables.
5. Verification that `positions_initiales` properly integrates with `charger_scenario` and `simuler_crise`.

---

### Task 1: TDD for `carte_risque` and demand zones (T3.3)

**Files:**
- Create: `tests/test_prepositionnement.py`
- Modify: `src/crise/prepositionnement.py`

**Interfaces:**
- Produces: `carte_risque(crises=None, clean_dir=None, alpha=5.0, n_clusters=200, random_state=42) -> pd.DataFrame`
  Output DataFrame has columns `["lat", "lon", "poids"]` with exactly `n_clusters` rows.

- [x] **Step 1: Write failing test in `tests/test_prepositionnement.py`**
- [x] **Step 2: Run test to verify failure**
- [x] **Step 3: Implement `carte_risque` and heat map export in `src/crise/prepositionnement.py`**
- [x] **Step 4: Run test to verify it passes**

---

### Task 2: TDD for Candidates & Capacitated p-Median MILP (T3.4)

**Files:**
- Modify: `tests/test_prepositionnement.py`
- Modify: `src/crise/prepositionnement.py`

**Interfaces:**
- Produces: 
  - `selectionner_candidats(zones: pd.DataFrame, sites: list[Site], n_avances: int = 20) -> list[tuple[float, float]]`
  - `resoudre_pmediane_milp(zones: pd.DataFrame, candidats: list[tuple[float, float]], n_equipes: int = 63, max_par_point: int = 8, time_limit_s: float = 60.0) -> list[int]`
  - `positions_pmediane(zones: pd.DataFrame, sites: list[Site], n_equipes: int = 63, n_avances: int = 20, max_par_point: int = 8) -> dict[str, tuple[float, float]]`
  - `positions_kmeans(zones_or_incidents, sites: list[Site], n_equipes: int = 63) -> dict[str, tuple[float, float]]`

- [x] **Step 1: Write failing tests for candidate selection, MILP solving, team assignment, and kmeans reference**
- [x] **Step 2: Run test to verify failure**
- [x] **Step 3: Implement MILP, matching with `linear_sum_assignment`, and `positions_kmeans`**
- [x] **Step 4: Run tests to verify they pass**

---

### Task 3: CLI & Evaluation Pipeline on Crises 81–100

**Files:**
- Modify: `src/crise/prepositionnement.py`
- Test: `tests/test_prepositionnement.py`

**Interfaces:**
- Produces:
  - `evaluer_prepositionnement(crises_test=None, n_jobs=-1) -> pd.DataFrame`
  - CLI `python -m crise.prepositionnement` saving `outputs/carte_risque.csv`, `outputs/carte_chaleur.html`, `outputs/positions_pmediane.csv`, `outputs/prepositionnement.csv`.

- [x] **Step 1: Write test for evaluation pipeline on a subset of test crises**
- [x] **Step 2: Implement `evaluer_prepositionnement` and `main()` CLI**
- [x] **Step 3: Run full tests to verify PASS**
- [x] **Step 4: Run the CLI `python -m crise.prepositionnement` to generate actual output artifacts**
- [x] **Step 5: Verify output files exist and contain valid data**

