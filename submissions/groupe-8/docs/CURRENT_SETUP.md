# Enedis crisis dispatch: current setup, algorithm and results

> **Purpose:** a self-contained snapshot of where the project stands (problem, model, algorithm, results, open points).
> **Date:** 10 October 2026 (Hackathon La Mêlée, Défi Enedis, 9–10 Oct 2026).
> **Status:** model and algorithm are decided; results come from a Python **prototype** on the real data. The production engine in the repo (`github.com/manticore999/hackatoun`) is still a skeleton.

---

## 1. The problem

During a climate crisis (storm, lightning, strong wind), many power outages happen at once. Enedis has a fixed number of field teams based at operational sites. We build a **real-time decision-support system** that recommends **which team goes to which incident, in what order**, so that power comes back as fast as possible for as many customers as possible, with priority for sensitive customers. **A human crisis manager validates every recommendation.**

- It is a **dispatch / scheduling** problem, not a prediction problem: outages are not forecast.
- It is **online**: incidents arrive over time, and the engine only knows incidents already reported.
- Two layers are strictly separated:
  1. **Optimisation engine:** the only source of decisions and numbers.
  2. **LLM layer:** explains the engine's output, answers questions, translates the manager's objections into structured rules. It never decides and never computes.

## 2. Data (provided by the organisers; example scenarios, not training data)

| File | Rows | Content |
|---|---|---|
| `poste_v2.csv` | 33,288 | Substations in Ariège, Haute-Garonne, Gers: position, `nb_clients` (5–150, synthetic), `poste_avec_client_sensible` (0/1, 5% of substations) |
| `coupures_v2_100_crises.csv` | 15,681 | Incidents in **100 historical crises** (2016–2018): substation, cause, report time, repair time **2 h / 4 h / 8 h** |
| `agents_v2.csv` | 18 sites | **63 teams** in total (1–6 per site) |
| `insee_v2.csv` | 1,365 | Communes |

Key facts:
- 50–250 incidents per crisis (median ≈ 165). They arrive within the first **4–8 h**, in bursts.
- Total repair work per crisis: median **11.6 h per team**, max 18.5 h (travel excluded).
- Median distance from an incident to the nearest site is about 11 km, so trips take ~15–30 min. **Repair time dominates travel.**
- Repair duration does not depend on the cause.
- Customer share by department: incidents 56% Haute-Garonne / 32% Gers / 12% Ariège; teams 56% / 22% / 22%.
- Data glitches: 5 incidents reference unknown substations (dropped); 43 repeated substations within a crisis (kept as separate incidents); Ariège INSEE codes lost their leading zero in `poste_v2.csv` (use `zfill(5)` before joining to `insee`).

## 3. Objective function

```
minimise  J = Σ_i  w_i · T_i      (+ λ_stab · number of changes to teams' next job)

w_i = N_i · (1 + β · s_i)          N_i = customers cut off, s_i = sensitive flag (0/1)
T_i = C_i − r_i                     outage duration = waiting + travel + repair
C_i = time repair of i ends         r_i = time incident i is reported
```

- **Official mode** β = 0, λ_stab = 0: exactly the organisers' indicator Σ N_i·T_i ("customer-hours without power"). Used for every benchmark.
- **Operational mode** β ≈ 3 (sensitive customers count more), λ_stab > 0 (avoid reshuffling plans).
- The README says "maximiser Σ N × T". Taken literally that rewards long outages. Since Σ N_i(H − C_i) = constant − Σ N_i T_i, maximising "customers restored as early as possible" **equals minimising Σ N·T**, so we minimise.
- **Intuition:** the area under the curve "customers without power over time". We make that area as small as possible.

### Service target: a check, NOT part of the objective
Global target: **≥ 90% of incidents fixed within 48 h** of the crisis start. It is **not** in the objective function. The engine optimises J, then **checks** whether the target is met:
- a permanent indicator: projected % fixed at H+48;
- an early alert when the projection drops below 90%;
- **a reinforcement recommendation when the target is out of reach.** The engine re-simulates the rest of the crisis with +1, +2, … extra teams (bisection) until the projection reaches 90%. It then recommends asking **other regions / the FIRE** for that number of teams, at the sites where they help most (each candidate site is tested by simulation). Real example from the engine (CRISE_082, scenario with only 50% of teams): *"Projection: 85.1% at H+48. To reach 90%, request **+6 teams** from other regions: 4 at Foix, 2 at Muret." → 90.9%.* (Implemented: `sim/whatif.py`, `python bench/reinforcement.py --crisis CRISE_082 --teams-fraction 0.5`.)
- other on-demand what-ifs ("what would a deadline-focused plan cost?"). **The manager decides.**

Config: `service_target: {share: 0.90, deadline_h: 48, basis: incidents}`. Whether it counts incidents or customers is still to confirm.

## 4. Constraints

| # | Rule | Enforced by |
|---|---|---|
| C1 | Each incident is handled by `q_i` teams (today q = 1, configurable) | representation |
| C2 | A team does one job at a time, in sequence, with travel in between | decoder |
| C3 | No anticipation: a team cannot leave for an incident that is not yet reported | state |
| C4 | A started repair is never interrupted | decoder |
| C5 | Travel + repair must fit **entirely inside the team's scheduled shift** | decoder |
| C6 | Teams rest on site and restart from there (configurable) | decoder |
| C7 | Jobs in progress are locked; operator rules force / forbid assignments | move filter |
| C8 | Team unavailability windows (stress tests, operator) | decoder |

**Well-being rules (shift schedule):** shifts ≤ 12 h; rest **12 h** between shifts (above the 11 h legal minimum); a fixed rotation known in advance.

## 5. The model: two stages

### Stage 1, at initialisation: the shift schedule (fixed once, never changed during the crisis)
- Each team belongs to group A (first shift starts at H0) or group B (first shift starts at H0 + b).
- Rotation: 12 h on / 12 h off.
- The schedule is chosen **once, before or at the start of the crisis**, because outages cannot be predicted. It is optimised on historical crises: we simulate the dispatch engine on past crises and minimise the mean J (sample average).
- **Search:** offset b ∈ {1,…,12} h × number of B teams per site (coordinate descent). Optimised on 50 crises (odd numbers), evaluated on the other 50 (even numbers, never seen).

### Stage 2, in real time: the dispatch engine ("RSLS", Rolling-horizon Smith + Local Search)
Run at **every event** (new incident, repair finished, team late or unavailable, manager decision).

**Representation.** A plan = one **ordered list of incidents per team**. Times are not decision variables.

**Decoder** (computes times and applies the rules; every plan it outputs is feasible by construction):
```
decode(team k, list π):
  t ← time k is free ; here ← k's position ; cost ← 0
  for i in π:
      d ← τ(here, i)                          # travel time
      t_go ← max(t, r_i)                       # never before the incident exists
      (s, e) ← k's scheduled shift containing t_go, or the next one
      t_go ← max(t_go, s)
      if t_go + d + p_i > e: move to the next shift (s', e'); t_go ← s'
      C_i ← t_go + d + p_i ; cost += w_i · (C_i − r_i)
      t ← C_i ; here ← i
  return cost, timetable
```

**Travel time:** `τ = straight-line distance (km) × 1.3 / 50 km/h`. Configurable, replaceable by a road-time matrix.

**Step 1, construction (Smith list scheduling, a few ms):**
```
while known unassigned incidents remain:
    k  ← team that becomes free first (within its shift)
    i* ← argmax over incidents that fit k's shift of   ρ = w_i / (τ(k, i) + p_i)
    append i* to π_k
```
ρ = **customers restored per hour of team time**. For one team without travel this is Smith's rule, which is provably optimal. On parallel machines with arrivals, rules of this family have proven worst-case guarantees (Megow & Schulz 2004; Tan et al. for post-disaster repairs). Those guarantees hold for simplified models; our rule is grounded in them, not guaranteed by them.

**Step 2, improvement (iterated local search, 200–500 ms):**
- Moves:
  - relocate an incident to another team or position;
  - swap two incidents between teams;
  - reorder within a team.
- Every few hundred moves, ruin & recreate: remove 10–20% of incidents and reinsert them by regret.
- Accept a move only if ΔJ < 0, or by late acceptance. Only the 1–2 changed teams are re-decoded, so evaluation is cheap.
- Always returns the best feasible plan found (anytime). Seeded, so deterministic.

**Step 3, robust selection (< 20 ms):** re-decode the ~5 best plans on ~30 random repair-time scenarios (lognormal around the estimate) and keep the best expected J. This also gives a P10–P90 restoration window per incident.

**Step 4, real-time policy:**
- Warm start from the previous plan.
- **Only each idle team's next job** becomes a recommendation; the next 2 jobs are a provisional preview.
- A new plan is published only if it beats the current one by a threshold, or if an event forces it.
- λ_stab penalises changing a team's next job.

**Option (proposed, not yet implemented): en-route diversion.** A team travelling to B is no longer locked. At each event, its position is estimated by linear interpolation, it is treated as free there, and B is put back at the head of its list. It is diverted to C only if the gain exceeds λ_stab plus the publication threshold.

Safeguards:
- no diversion if less than X min of travel remain;
- at most 1 diversion per trip, plus a cooldown;
- the diversion is a recommendation the manager must validate, with a short validity.

Its gain is to be measured; travel is short compared with repairs, so the gain may be small. Config: `diversion.enabled`, `min_remaining_min`, `max_per_trip`, `cooldown_min`, `recommendation_ttl_min`.

**Offline reference (not in the live loop):** an OR-Tools routing model with a long time limit, to measure the gap between our heuristic and the best known solution.

## 6. Decision layers and improvement loop

```
 INPUTS:  objective function  +  set of constraints (versioned registry)
                         │
                         ▼
          ┌───────────────────────────────┐
          │ OPTIMISATION UNIT (RO)        │──► decision (team → incident, order) + WHY (structured facts)
          └───────────────────────────────┘
                         │
                         ▼
          ┌───────────────────────────────┐
          │ LLM                           │──► explains the decision in plain language (numbers from the engine only)
          └───────────────────────────────┘
                         │
                         ▼
          ┌───────────────────────────────┐
          │ ADMINISTRATOR validates or    │
          │ refuses (refusal = reason)    │
          └───────────────────────────────┘
             │ validated            │ refused (+ reason)
             ▼                      ▼
     plan executed          KNOWLEDGE BASE (every refusal: context, recommendation, reason, chosen alternative, cost)
                                    │  every month / every X refusals
                                    ▼
                    EXPERT SYSTEM + HUMAN EXPERTS analyse recurring refusals
                                    │  candidate constraint, replay-tested on past crises (cost + refusals avoided)
                                    ▼
                    new version of the constraint registry ──► back to the RO inputs
```

- **During the crisis:** on a refusal, the engine immediately re-plans around the administrator's choice and shows what the choice costs. A safety-related reason applies at once.
- **After the crisis:** refusals accumulate in the knowledge base. The expert system groups recurring patterns (same zone, same team, same type of job) and proposes **candidate constraints**. Human experts decide to add them (as a hard constraint or a softer penalty) or not, after a replay test on the historical crises.
- **The LLM never creates or changes a constraint.** It explains decisions, and it can summarise the refusal reasons for the experts.
- Every decision records the version of the constraint registry that produced it (traceability, rollback).

Status: the engine part (decision + why, operator rules, override cost) is **implemented**; the knowledge base, expert system and constraint registry are **designed, not yet implemented**.

### 6.1 Explainability (computed by the engine, written by the LLM)
For each recommendation the engine outputs facts. The LLM may only state numbers found in them.

| Fact | How it is computed |
|---|---|
| Priority index | ρ = w / (τ + p) and its rank |
| Cost breakdown | customer-hours split into waiting, travel and repair |
| Contrastive Δ | force the best alternative team or incident, short re-search, compare J |
| Binding constraint | decoder trace (end of shift, lock, operator rule) |
| Tipping point | bisection on p_i or τ until the decision flips |
| Uncertainty | P10–P90 restoration time over the scenarios |
| Override cost | re-plan with the manager's choice locked, compare J |

When the manager rejects a recommendation, the LLM translates the reason into **modifiers from a fixed catalogue**:
- force / forbid;
- team unavailable;
- zone inaccessible until t;
- travel factor;
- duration update;
- priority;
- reserve;
- weight change.

A validator checks each modifier, the engine re-plans and shows the cost of the rule, and the manager confirms. Learning loops act only on data the model reads (estimates, weights, rule registry), never on solver code.

## 7. Results (real data, official indicator Σ N·T, lower = better)

### 7.0 Real engine in the repo: all 100 crises (`python bench/run_benchmark.py --crises all --budget-ms 50`)
Optimised shift schedule. Travel model calibrated on 3,718 real OSRM trips (mean error 8.3 min). Event-driven simulator. The engine never sees future incidents. Local search budget 50 ms per re-plan.

| Strategy | Mean customer-hours | Incidents fixed by H+48 | Crises meeting 90% | Time per crisis |
|---|---|---|---|---|
| First come first served | 166,264 | 98.9% | 100/100 | 0.26 s |
| Nearest team | 145,953 | 99.3% | 100/100 | 0.23 s |
| Most customers first | 133,404 | 98.9% | 100/100 | 0.27 s |
| Smith rule alone | 133,186 | 99.0% | 100/100 | 0.25 s |
| **Optimised engine (RSLS)** | **112,198** | **99.8%** | **100/100** | 6.8 s |

The optimised engine, compared crisis by crisis:

| vs | Mean gain | Range | Better on |
|---|---|---|---|
| First come first served | **−27.7%** | −39.1% … −7.5% | 100/100 |
| Nearest team | **−20.1%** | −29.6% … −6.6% | 100/100 |
| Most customers first | **−15.7%** | −22.4% … −7.3% | 100/100 |
| Smith rule alone | **−16.5%** | −27.9% … −7.4% | 100/100 |

### 7.0b Robustness scenarios (CRISE_051, the heaviest; `python bench/scenarios.py --budget-ms 30`)
| Scenario | Optimised vs Smith | H+48 (optimised) | 90% target |
|---|---|---|---|
| Normal | −7.7% | 96.8% | met |
| Flood: Ariège cut until H+12, then travel ×1.5 | −10.2% | 96.0% | met |
| Storm: every trip ×1.5 | −6.6% | 95.6% | met |
| Repair durations uncertain (lognormal, σ 0.3) | −9.2% | 99.2% | met |
| 50% of teams lost at H+12 | −11.1% | 80.6% | missed → reinforcement |
| Two crises 24 h apart (497 incidents) | −11.8% | 58.8% | missed → reinforcement |
| Only 50% / 25% of teams | −2.4% / −0.4% | 64.9% / 37.1% | missed: capacity problem, not dispatch |

Under extreme saturation the engine starts from the better of its previous plan and a fresh Smith plan, so it is never worse than the Smith rule.

The sections below are the earlier prototype measurements that led to the design.

### 7.1 Construction rules alone (100 crises; flexible rest rule, all teams start at H0)
| Rule | Mean customer-hours per crisis |
|---|---|
| First come first served | 169,419 |
| Nearest team | 149,300 |
| Most customers first (sensitive first) | 146,543 |
| Smith without travel (w / p) | 149,110 |
| **Smith with travel (w / (τ + p))** | **137,820** |

Smith with travel vs the others: −13.9% vs FIFO (better on 99/100), −5.3% vs nearest (81/100), −4.5% vs most customers (92/100), −5.5% vs Smith without travel (97/100). Mean wait per customer ≈ 10.4 h.

### 7.2 Full engine: re-planning at every decision + local search (50 ms per decision), no knowledge of future incidents (20 crises, every 5th)
| Full engine vs | Mean | Range | Better on |
|---|---|---|---|
| First come first served | **−27.6%** | −17.4% … −37.9% | 20/20 |
| Nearest team | **−20.1%** | −12.8% … −27.6% | 20/20 |
| Most customers first | **−18.9%** | −13.4% … −24.0% | 20/20 |
| Smith rule alone | **−14.6%** | −7.2% … −20.8% | 20/20 |

- Local search with **perfect foresight** (all incidents known in advance) gains 17.7% over the Smith rule. Online we capture **≈ 83%** of that.
- Re-planning **without** local search gains almost nothing. The gain comes from the search.
- Compute: ~50 ms per decision; 0.3–8.8 s per whole crisis in pure Python.

### 7.3 Shift schedule (stage 1; 12 h on / 12 h off; test set = 50 crises never used for tuning; Smith rule as dispatcher)
| Schedule | Mean customer-hours |
|---|---|
| Everyone starts at H0, fixed 12/12 | 144,489 |
| Half of each site starts at H0 + 12 h (continuous coverage) | 155,582 (+7.7%, worse) |
| Flexible rule (rest whenever the next job no longer fits; not a fixed schedule) | 129,839 |
| **Optimised fixed schedule: group B starts at H0 + 2 h** | **127,774** |

- The optimised schedule cuts customer-hours by **11.6%** in total vs everyone at H0 (mean per-crisis gain 12.4%, better on 49/50 crises).
- It is also 1.7% better than the flexible rule (33/50), while giving **12 h rests and hours known in advance**.
- Group A has 28 teams, group B 35.
- Split by site (A/B): Foix 0/5, Lavelanet 1/3, Ax-les-Thermes 1/0, Laurencin 2/4, Balma 4/1, Decroutte 2/1, Muret 4/1, Auch 2/1, Fleurance 2/1, Gimont 2/1, Mirande 2/1, Eauze 0/2, Saint-Gaudens 0/4, Saint-Girons 1/3, Boussens 0/3, Grenade 3/1, Villefranche 2/2, Luchon 0/1. The robust message is "≈ 45% at H0, ≈ 55% at H0 + 2 h", not each site's exact number.
- **Why only 2 h:** demand is front-loaded (all incidents arrive within ~6 h), so it pays to put almost every team in at the start. A day/night split halves the force when it matters most. The 2 h offset staggers the ends of shifts.
- ⚠️ **Nobody is on duty between H+14 and H+24.** Fine for these non-overlapping crises, risky for night-time incidents or a second crisis. A **minimum-coverage rule** (e.g. ≥ 15% of teams on duty at all times) is proposed.
- Hours worked per team per crisis: mean 13.6 h, P90 20.6 h, max 33.1 h. A cap per team is proposed.

### 7.4 Service target check: ≥ 90% of incidents fixed by H+48 (Smith rule as dispatcher)
| Scenario | Incidents fixed by H+48 (mean) | Worst crisis | Crises meeting 90% | Customers restored by H+48 |
|---|---|---|---|---|
| 63 teams, everyone at H0 | 97.7% | 86.3% | 95/100 | 99.0% |
| **63 teams, optimised schedule** | **98.9%** | **91.8%** | **100/100** | 99.7% |
| 50% of teams, optimised schedule | 83.8% | 63.4% | 35/100 | 89.6% |
| 33% of teams, optimised schedule | 70.0% | 47.2% | 20/100 | 78.4% |
| 25% of teams, optimised schedule | 59.9% | 37.8% | 4/100 | 69.9% |

In normal conditions the target is always met. With reduced teams it fails because of **capacity**, not dispatch, which is where the early alert and the "extra teams needed" what-if come in.

### 7.5 Reinforcement what-if: teams needed to reach 90% at H+48 (scenario with 50% of teams, optimised schedule)
- 65/100 crises miss the target with half the teams. On a sample of 22 of them, extra teams were added one by one at the site that raises the H+48 share the most, until 90% was reached.
- **Extra teams needed:** median **19**, mean 16.4, from **1** (a crisis at 88.4%) to **31**.
- Most requested sites: Foix (by far), then Laurencin (Toulouse), Lavelanet, Auch, Ax-les-Thermes, i.e. mostly Ariège.
- Examples:
  - CRISE_063, 88.4% → **+1** team (Ax-les-Thermes);
  - CRISE_082, 85.1% → **+6** (Foix 4, Saint-Gaudens 1, Gimont 1);
  - CRISE_066, 64.8% → **+31**.
- Caveats:
  - reinforcements are assumed available from H0; in reality they arrive after a delay of several hours, so more would be needed;
  - the site choice is greedy;
  - the dispatcher is the Smith rule only.

### 7.6 Earlier lever test (flexible rest rule): staggering part of the teams
The best tested setting was +5.0% (1/3 of teams delayed by 4 h). A badly chosen one cost up to −20% on average. So staggering must be optimised, not set by hand.

## 8. Assumptions (all configurable)
- **Objective:** minimise Σ N·T. Customers get power back only when the repair ends (no temporary restoration). The outage clock starts at the report time. Sensitivity is yes/no per substation.
- **No grid topology:** each incident restores only its own substation.
- **Repair durations are known estimates** (2, 4 or 8 h). The truth is revealed when the repair ends (the simulator can add noise).
- **Teams:** 63 interchangeable teams, no skills, one team per incident, no external reinforcements.
- **Travel:** straight line × 1.3 at 50 km/h, deterministic, no roads cut unless the operator says so.
- **Decisions:** validated instantly, no communication delay.
- **Safety** is modelled through the rules only (shifts, rest, no interruption, operator rules).

## 9. Limits of the current results
- Prototype only. The local search is minimal (relocate moves only). No stability penalty yet, which will give back part of the gain in exchange for calmer plans. No duration noise yet.
- The full engine was measured on 20 crises only. The shift schedule and the H+48 check used the Smith rule as dispatcher, not the full engine.
- The gap to the true optimum is unknown (the offline OR-Tools reference is not built yet).
- Customer counts are synthetic, so these are relative gains between methods, not real-world restoration figures.
- Several literature references were read as abstracts only.

## 10. Open questions (to confirm with the organisers)
1. Can a repair cross the end of a shift? Does travel count as work time?
2. Is the objective Σ N·T to be minimised (README says "maximiser")?
3. Does "90% within 48 h" count incidents or customers, and where is it defined?
4. Do all teams start at the alert, or can some start later?
5. One team per incident? Will skills data come?
6. Is temporary restoration (partial power back) expected?

## 11. Next steps
1. Implement the RSLS engine in the repo (decoder → baselines → construction → local search → warm start, stability, modifiers → counterfactuals and explanation facts).
2. Re-run every result on all 100 crises with the full engine, the stability penalty and duration noise.
3. Re-optimise the shift schedule with minimum coverage and a cap on hours per team.
4. Build the OR-Tools offline reference to measure the gap to the best known solution.
5. Measure en-route diversion and decide its default setting.
6. Implement the H+48 service check, the early alert and the reinforcement recommendation (number of teams from other regions, and where).
7. Implement the knowledge base of refusals and the periodic review (expert system + experts → new constraints in the versioned registry). For the demo, use a simulated refusal log, clearly marked as such.
