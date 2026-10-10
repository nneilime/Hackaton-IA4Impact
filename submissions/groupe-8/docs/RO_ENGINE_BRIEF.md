# Optimisation engine (RO): brief for the engine owner

> **Défi Enedis · Hackathon La Mêlée · 9–10 October 2026**
> You own the **optimisation engine**: the component that decides which team goes to which incident, in what order.
> It is the **only source of decisions and numbers** in the product. The LLM explains its output and the interface displays it,
> but neither of them ever computes a plan or a score.
>
> Companion files in `docs/`: `Enedis_Hackathon_Team_Brief.pdf` (full context), `architecture.png`, `decision_loop.png`.

---

## 1. The problem in one paragraph

During a climate crisis, incidents (a substation, or *poste*, losing power) appear over a few hours. A fixed set of field teams,
starting from known operational sites, must be sent to them. Each incident needs **one team** (configurable), which
travels there and repairs it. Customers stay without power until the repair ends. We want to **minimise the total
weighted customer-hours without power**, while respecting a **work/rest rule (12 h work, then 11 h rest)**. The system is
**real-time**: every new event (new incident, repair finished, team unavailable, operator decision) triggers a re-plan, and
the engine must answer in well under a second.

This is **not an ML problem**. The CSV files are example scenarios used to feed a live event stream and to benchmark
strategies. The engine must work with any incidents and any teams, not with "the dataset".

---

## 2. What the data looks like (for intuition and testing)

All files are in `data/raw/`, semicolon-separated, UTF-8 with BOM (`encoding="utf-8-sig"`, `sep=";"`).
The data owner provides loaders. **Do not read the CSVs inside the engine.** The engine only sees the objects in §5.

| File | Rows | Columns used |
|---|---|---|
| `poste_v2.csv` | 33,288 substations | `id_poste, latitude, longitude, nb_clients` (5–150), `poste_avec_client_sensible` (0/1), `departement` |
| `coupures_v2_100_crises.csv` | 15,681 incidents in 100 crises | `numero_crise, id_incident, id_poste, dateHeureIncident` (dd/mm/yyyy HH:MM), `dureeDepannage` (`2h`/`4h`/`8h`), `causeInterruption` |
| `agents_v2.csv` | 18 sites, **63 teams** | `id_site, latitude, longitude, nb_equipes` |

Facts that shape the algorithm:

| Fact | Consequence |
|---|---|
| A crisis has 50–250 incidents (median 165), arriving over 4–8 h | Problem size: n ≤ ~250 incidents, m = 63 teams |
| Total repair work per crisis: median **11.6 h per team**, max **18.5 h**; 48 crises exceed 12 h per team | Teams saturate; the **12 h / 11 h rule really binds**; a queue forms |
| Repairs: 2, 4 or 8 h. Median distance to the nearest site is about 11 km (90% under 22 km) | Repair time dominates travel, so **order matters more than distance** |
| Duration is independent of the cause | Cause is just a label |
| ~5% of substations are flagged sensitive | Weighted via β (see §3) |
| Routes are short: about 3–4 incidents per team per shift | Evaluating one route is very cheap, so local search can try many moves |

Known glitches (handled upstream by the loaders): 5 incidents reference a missing substation and are dropped; there are 43 repeated
substations within a crisis, which are kept as separate incidents.

---

## 3. Objective function

```
minimise   Σ_i  w_i · (C_i − r_i)                                    main term: weighted outage time
         + λ_stab · (# teams whose NEXT job differs from the last recommendation)
         + λ_trav · Σ travel time                                     tie-breaker / safety
         + λ_eq   · max_i (C_i − r_i)                                 fairness: no forgotten incident

w_i = n_i · (1 + β · s_i)          n_i = customers, s_i = sensitive flag (0/1)
C_i = end of repair of incident i   r_i = time incident i appeared
C_i − r_i = waiting + travel + repair
```

- The README writes "maximiser Σ N × T". That is a typo: we **minimise** it, and we document this reading.
- **Everything is a config parameter** (`config/default.yaml`), with these defaults: `β = 3`, `λ_stab` moderate, `λ_trav` small, `λ_eq` small.
- **Unweighted customer-hours** (Σ n_i·(C_i − r_i)) must also be reported, because it is the README's N×T indicator used by the jury.

**Key intuition (Smith's rule):** for one team with no travel, ordering jobs by decreasing `w_i / p_i` is **optimal** for
Σ w·C. Toy check you can use as a unit test (one team, all incidents at t = 0, no travel):

| Order | Completion times | Score |
|---|---|---|
| A(150 cust., 8 h), C(100, 4 h), B(60, 2 h): biggest first | 8, 12, 14 | 150·8 + 100·12 + 60·14 = **3,240** |
| B, C, A: Smith (30/h, 25/h, 18.75/h) | 2, 6, 14 | 60·2 + 100·6 + 150·14 = **2,820** (optimal) |

---

## 4. Constraints

| # | Constraint | Rule | Config (default) |
|---|---|---|---|
| C1 | Every incident is served | exactly `q_i` teams; **MVP: q_i = 1** (keep the field, assert = 1 for now) | `teams_per_incident: 1` |
| C2 | One job at a time, in sequence | next start ≥ previous end + travel; the first trip starts from the team's current position | fixed |
| C3 | No anticipation | the engine only sees incidents that have already arrived | fixed (the simulator enforces it) |
| C4 | No interruption | a started repair runs to the end | fixed |
| C5 | Work window | at most 12 h of work in a row, then 11 h of rest. **Travel + repair must fit entirely inside the window**: never start a job that cannot be finished | `shift_h: 12`, `rest_h: 11`, `travel_counts_as_work: true`, `allow_split: false` |
| C6 | Where the team rests | on site, and it restarts from there | `rest_at: site` (or `base`) |
| C7 | Locks | jobs in progress (travelling or repairing) are fixed; operator rules force or forbid assignments | from the modifier store |
| C8 | Unavailability | team k is unavailable from time t (stress test: 50% of teams after 48 h) | from events |
| C9 | (optional) Sensitive deadline | a sensitive incident starts within D hours | `sensitive_deadline_h: null` |

⚠️ **Shift trap:** if all teams start working at t = 0, they all rest at the same time (hours 12–23) and nobody is in the field.
The MVP accepts this, but the code must allow a **mobilisation time per team** (`team.shift_start`), so that staggered shifts can be tested later.

---

## 5. Contract with the rest of the system

Time unit inside the engine: **hours as float** from the crisis start `t0`. Convert to integer minutes only for OR-Tools.

```python
# engine/types.py  (proposal: adjust together with the simulator owner)
from dataclasses import dataclass, field
from enum import Enum

class TeamStatus(Enum):
    IDLE = "idle"; TRAVELLING = "travelling"; REPAIRING = "repairing"; RESTING = "resting"; UNAVAILABLE = "unavailable"

@dataclass(frozen=True)
class Incident:
    id: str
    lat: float
    lon: float
    customers: int              # n_i
    sensitive: bool             # s_i
    reported_at: float          # r_i (h)
    est_duration: float         # p̂_i (h), an ESTIMATE; reality may differ
    accessible_from: float = 0  # set by modifiers ("zone flooded until 18h")
    teams_required: int = 1     # C1, assert == 1 for MVP

@dataclass
class Team:
    id: str
    home_site: str
    lat: float                  # position when it becomes free
    lon: float
    free_at: float              # now if idle, else end of current job / rest
    shift_end: float            # end of its current 12 h window
    status: TeamStatus
    current_job: str | None = None   # locked (C7)

@dataclass
class State:
    now: float
    teams: list[Team]
    pending: list[Incident]          # arrived, not yet started (C3)
    locks: "Modifiers"               # forced / forbidden pairs, reserves, zone rules, weights
    previous_plan: "Plan | None"     # for warm start + stability

@dataclass
class Plan:
    routes: dict[str, list[str]]     # team_id -> ordered incident ids (first = next job)
    score: "ScoreBreakdown"          # total + each term + KPIs
    schedule: dict[str, tuple[float, float, float]]  # incident_id -> (depart, start_repair, end_repair)
```

**Functions you expose:**

```python
plan(state: State, cfg: Config, budget_ms: int = 300) -> Plan            # main entry, real-time
evaluate_route(team: Team, route: list[Incident], cfg) -> RouteEval      # cost + timings, or INFEASIBLE
score(plan: Plan, state: State, cfg) -> ScoreBreakdown
explain(plan: Plan, state: State, cfg) -> list[ExplanationFacts]         # for the LLM, see §8
counterfactual(state, forced: list[Modifier], cfg) -> tuple[Plan, float] # new plan + Δscore
baseline(name: str) -> Policy                                            # "fifo" | "nearest" | "max_customers"
```

**What the engine does NOT do:** read files, keep a clock, dispatch teams, talk to the LLM. The simulator calls
`plan()` at each event, and the interface calls `counterfactual()` when the operator overrides.

**Travel time** (shared helper, can live in `engine/travel.py`):
`τ(a, b) = haversine_km(a, b) × 1.3 / speed_kmh`, with `speed_kmh = 50` (config), and an optional slower factor for
mountain zones. Precompute a small numpy matrix per `plan()` call: (teams + pending) × pending, at most ~313 × 250.

---

## 6. The algorithm (what to build, in order)

### 6.1 `evaluate_route`: the core building block
Everything else calls it. Make it correct first, then fast.

```python
def evaluate_route(team, route, cfg):
    t, pos, shift_end = team.free_at, (team.lat, team.lon), team.shift_end
    cost, timings = 0.0, []
    for inc in route:
        travel = tau(pos, inc)
        if t + travel + inc.est_duration > shift_end:      # C5: does not fit in this shift
            t = t + cfg.rest_h                              # rest starts now (configurable: or at shift_end)
            shift_end = t + cfg.shift_h
            if t + travel + inc.est_duration > shift_end:
                return INFEASIBLE                           # job longer than a whole shift
        depart = t
        start = max(t + travel, inc.accessible_from)
        t = start + inc.est_duration                        # C_i
        cost += w(inc, cfg) * (t - inc.reported_at)
        timings.append((inc.id, depart, start, t))
        pos = (inc.lat, inc.lon)
    return RouteEval(cost, timings, end_time=t)
```
Route length is about 3–4, so this is a few dozen operations. Total plan cost = Σ routes + penalty terms.

### 6.2 Baselines (required by the README; also your test oracles)
Implement them as policies over the same `State`, so that they run through the same simulator:
- `fifo`: the oldest pending incident gets the team that can **reach it earliest**.
- `nearest`: each team, when it becomes free, takes the **nearest** pending incident.
- `max_customers`: the incident with the most customers (sensitive first) gets the earliest-arriving team.

### 6.3 Construction: list scheduling with the Smith index (target < 10 ms)
```
heap of teams keyed by free_at
while pending not empty:
    k  = pop team with earliest free_at
    i* = argmax over feasible i (C5, C7, accessible) of  w_i / (τ(pos_k, i) + p_i)
    append i* to route_k; update free_at, pos, shift_end of k via the evaluate_route step; push k back
```
This is easy to explain ("the first free team takes the incident that brings back the most customers per hour of its time").
Its weakness is short-sightedness, and local search fixes that.

### 6.4 Improvement: local search, then ALNS (target 200–500 ms total)
Neighbourhood moves, each touching only 1–2 routes, so only those routes are re-evaluated:

| Move | Description |
|---|---|
| relocate | move incident i from route A (any position) to route B (any position) |
| swap | exchange incident i (route A) and j (route B) |
| reorder (or-opt) | move i to another position inside its own route |

- Accept a move if Δ(total objective) < 0. Simulated-annealing acceptance is optional, to escape local minima.
- **ALNS layer:** every N iterations, *destroy* 10–20% of incidents (random / geographic cluster / costliest) and *repair* them by
  regret-2 insertion (insert first the incident whose best and second-best insertion costs differ most).
- Stop on the time budget (`budget_ms`). Always return the best feasible plan found.
- Use a seeded RNG (`cfg.seed`), so the same input gives the same plan. This is needed for the demo and for tests.

Literature pointer: this is a **multiple traveling repairman / minimum-latency** problem with weights, service times and
work windows. Greedy + local search / ALNS is the standard, well-performing approach for this family.

### 6.5 Real-time behaviour
- **Warm start:** start from `previous_plan` (remove completed jobs, insert new incidents at their cheapest position), then
  run local search. Never rebuild from scratch unless there is no previous plan.
- **Locks:** jobs in progress are never moved. Operator modifiers are hard constraints during search.
- **Stability:** `λ_stab` penalises changing a team's *next* job relative to the last recommendation.
- The simulator groups events arriving within the same second, so you will not be called 10 times in a row.

### 6.6 Reference solver (offline, phase 2+): OR-Tools Routing
The same model maps directly to OR-Tools. Use it to **validate the quality** of your heuristic, and to compute a
"hindsight" bound when all incidents are known in advance.
- vehicles = teams, start = current position, end = free (dummy depot)
- time dimension: transit(i → j) = `p_i + τ(i, j)` (integer minutes), slack allowed
- objective Σ w·C: `routing.GetDimensionOrDie("time").SetCumulVarSoftUpperBound(index_i, 0, w_i)`, which gives a cost w_i·arrival_i (+ a constant)
- shifts: `SetBreakIntervalsOfVehicle` (11 h break after 12 h)
- forced / forbidden: `SetAllowedVehiclesForIndex`; accessible-from: `CumulVar(i).SetMin(t)`
- metaheuristic `GUIDED_LOCAL_SEARCH`, time limit of a few seconds to a minute (offline only)

---

## 7. Modifiers: the operator's rules arrive as structured input

When the manager rejects a recommendation, the LLM turns the reason into JSON **from a fixed catalogue**, and the validator
checks it. You receive validated modifiers in `state.locks` and must honour them:

| Modifier | Effect in the engine |
|---|---|
| `force(team, incident)` | that pair is fixed as the team's next job |
| `forbid(team or site, incident or zone)` | pair excluded from every move |
| `team_unavailable(team, from, until)` | team cannot work in that window |
| `zone_inaccessible(zone, until)` | `accessible_from = until` for incidents in the zone |
| `travel_factor(zone, factor)` | τ × factor for trips into the zone |
| `duration_update(incident, hours)` | new `est_duration` |
| `priority(incident, factor or sensitive=True)` | changes w_i |
| `reserve(site, n, until)` | n teams of that site are excluded until t |
| `weight(name, value)` | changes β / λ for this crisis |

`counterfactual(state, [modifier])` must return the new plan **and the Δscore** ("this rule costs +320 customer·h"). It is
the same `plan()` with the extra modifier, warm-started from the current plan.

---

## 8. Explanation facts: what the LLM needs from you

For each recommended next job, return a JSON-serialisable object. The LLM may only state numbers that appear here.

```json
{
  "team": "T07", "incident": "INC_000042", "rank_in_plan": 1,
  "factors": {"customers": 120, "sensitive": false, "weight": 120,
              "travel_min": 25, "repair_h": 4, "shift_left_h": 6.1, "priority_index": 27.0},
  "best_alternative_team": {"team": "T04", "delta_score": 410},
  "best_alternative_incident_for_team": {"incident": "INC_000051", "delta_score": 180},
  "binding_constraint": null,
  "tipping_point": "if repair > 5.2 h, T09 becomes better"
}
```
Compute Δ by local re-insertion (cheap). The tipping point is a stretch goal: try a few values of `p_i`.

---

## 9. Acceptance tests (definition of done)

| # | Test |
|---|---|
| T1 | `evaluate_route` reproduces the toy table in §3 (3,240 vs 2,820) |
| T2 | One team, no travel: construction returns Smith order |
| T3 | No job crosses a shift end; no team does two jobs at once; every pending incident is assigned (or reported as unassignable) |
| T4 | Locks and modifiers are respected (property test with random forced/forbidden pairs) |
| T5 | Same input + same seed gives the same plan |
| T6 | **Speed:** `CRISE_051` (249 incidents, the heaviest) gets a full plan in < 1 s; greedy alone in < 50 ms |
| T7 | Warm start: adding 1 incident to an existing plan changes the next job of at most a few teams |
| T8 | `counterfactual` with the already-recommended assignment returns Δ = 0 |
| T9 | Through the simulator, averaged over the 100 crises: **ours < every baseline** on the weighted score |
| T10 | (phase 2) On small crises, the OR-Tools offline bound ≤ our score, and we report the gap |

Use pytest. Build a tiny synthetic scenario (3 teams, 8 incidents) for fast unit tests, independent of the CSVs.

---

## 10. Milestones

| When | Deliverable |
|---|---|
| H0–H1 | Agree on §5 types with the simulator, LLM and interface owners. Create `engine/` with stubs. |
| H1–H4 | `evaluate_route` + `score` + 3 baselines + T1–T3 |
| H4–H8 | Greedy construction + local search + T4–T6. **MVP milestone: one crisis replayed, our score vs baselines printed.** |
| H8–H16 | Warm start, stability, modifiers, `counterfactual`, `explain` + T7–T9 |
| H16+ | ALNS, OR-Tools bound (T10), staggered mobilisation experiment, calibration hook (`est_duration` updated from observed actuals) |

## 11. Open points (defaults chosen; change them via config, not code)

- Travel counts as work time: **yes**. A job may not cross a shift end: **yes**. Rest location: **on site**.
- Rest starts **when the next job does not fit** (current choice), or at shift end. To confirm with the team.
- Idle teams repositioning towards busy areas: not in MVP.
- `teams_per_incident > 1`: data model ready; algorithm support later.
- All teams start their shift at t0 in the MVP. `shift_start` per team must exist for the staggered-shift experiment.

## 12. Do / don't

- ✅ Every rule and weight in config; every number traceable to `score()`.
- ✅ Deterministic, time-budgeted, always returns a feasible plan.
- ✅ Code against the §5 types, not against CSV columns.
- ❌ No hard-coded "1 team per incident", "12 h", "β = 3", or file paths in the engine.
- ❌ Do not optimise on information the engine should not have (future incidents, true durations).
- ❌ Do not let the LLM, or anything other than the engine, produce a plan or a score.
