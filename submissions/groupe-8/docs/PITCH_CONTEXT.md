# Pitch context: crisis dispatch copilot (Défi Enedis, La Mêlée, 9–10 Oct 2026)

> Background material for preparing the pitch: what we built, why, how it works, the numbers, and what is real versus
> simulated or still a vision. Numbers come from `docs/CURRENT_SETUP.md` and `docs/DEV_LOG.md` (benchmarks on the
> organisers' data).

---

## 1. The one-liner

**During a storm, our system tells the crisis manager which repair team to send to which outage, and in what order, so
that power comes back for as many customers as possible, as fast as possible.** An optimisation engine decides, an LLM
explains, and the manager stays in control. Every refusal makes the system better.

French version for the stage:
> *« Pendant une tempête, notre copilote dit au responsable de crise quelle équipe envoyer sur quel incident, et dans quel
> ordre, pour rétablir le plus de clients le plus vite possible. Le moteur d'optimisation décide, l'IA explique, l'humain
> valide, et chaque refus rend le système plus intelligent. »*

---

## 2. The problem

- A storm causes **50 to 250 outages in a few hours** over Ariège, Haute-Garonne and Gers. There are **63 teams** at
  **18 sites**.
- Today the order of interventions is decided by hand, under pressure, with incomplete information.
- **What it costs:** the official indicator is **customers × hours without power** (Σ N × T): the area under the curve
  "customers cut off over time". Every hour of delay on a large substation costs a lot.
- **Constraints:**
  - teams work 12 h shifts;
  - a repair cannot be interrupted;
  - incidents arrive over time and are not known in advance;
  - sensitive customers (medical equipment) need priority.
- **Service target:** at least **90 % of incidents fixed within 48 h**.

**Why it is hard:** it is not a prediction problem. Outages cannot be forecast. It is an online scheduling problem:
decide now, with what is known now, and re-decide at every new event. A good order beats a fast reaction.

---

## 3. The solution in one picture

```
   Incidents + teams + shifts ──►  OPTIMISATION ENGINE (RO)  ──►  plan + facts (why)
                                          ▲                            │
                                          │                            ▼
                         rules (constraint registry)          LLM: explains in 2 sentences,
                                          ▲                   answers questions
                                          │                            │
                          experts validate │                            ▼
                          new rules        │                   CRISIS MANAGER: accept / refuse (+ reason)
                                          │                            │ refusal
                                          │                            ▼
                         EXPERT REVIEW ◄── KNOWLEDGE BASE ◄── LLM turns the reason into a rule,
                         (recurring refusals,                 engine prices it, manager confirms
                          replay test)
```

**Three roles, strictly separated:**
1. **Engine (operations research):** the only source of decisions and numbers.
2. **LLM:** explains, translates and answers. It **never decides and never computes.** Any number it writes must come
   from the engine's facts, or the text is rejected.
3. **Human:** validates every recommendation. Refusals are information, not failures.

---

## 4. The optimisation engine (the core)

### 4.1 Objective
Minimise **Σ customers × hours without power** (the official indicator). An outage lasts waiting time + travel + repair.
The **90 %-in-48 h target is a check, not part of the objective**. We optimise customer-hours, then check the target. If
the target is out of reach, we recommend reinforcement (§4.4). The README says "maximiser Σ N×T". Taken literally that
rewards long outages, so we minimise; the two readings are mathematically equivalent if read as "restore customers as
early as possible".

### 4.2 Stage 1, before the crisis: the shift roster (fixed once)
- **12 h on / 12 h off** for every team. The rest is longer than the 11 h legal minimum, and the hours are known in advance
  (human well-being).
- Two groups: **A starts at H0, B starts at H0 + 2 h**, with a per-site split, about 45 % / 55 %.
- It is set **once, at initialisation**, because outages cannot be predicted. It is optimised by simulating the engine on
  **50 past crises** and tested on **50 others** it never saw.
- **Result:** −11.6 % customer-hours compared with "everyone starts at H0". It is also better than a flexible rest rule,
  while keeping fixed, predictable hours.
- **Why only 2 h?** Outages arrive in the first ~6 h. A day/night split would halve the workforce exactly when it is needed.

### 4.3 Stage 2, during the crisis: the dispatch engine "RSLS" (Rolling-horizon Smith + Local Search)
It runs again at every event (new incident, repair finished, manager decision):
1. **Construction (a few ms):** Smith's rule. Give each free team the incident with the best
   *customers restored per hour of team time* = customers / (travel + repair). This rule is provably optimal for a single
   machine and backed by the scheduling literature for the general case.
2. **Improvement (anytime, about 0.5–3 s):** iterated local search:
   - move an incident to another team or position;
   - swap incidents between teams;
   - "ruin & recreate" (remove 10–20 % of the plan and rebuild it).

   Incremental evaluation with pruning makes thousands of moves per second possible.
3. **A decoder guarantees feasibility:**
   - one job at a time;
   - no departure before the incident is reported;
   - no interrupted repair;
   - travel + repair fit inside the team's shift;
   - operator rules (forbidden zone, unavailable team, …) are respected.
4. **Stability:**
   - warm start from the previous plan;
   - only each free team's next job is recommended;
   - a new plan is published only if it is clearly better.

**Travel times:**
- a terrain model (urban / plain / mountain, local vs main roads) calibrated on **3,718 real OSRM road trips** (mean error
  8.3 min);
- live OSRM routing is available;
- the map draws the real road route.

### 4.4 The 48 h check and reinforcement
- The engine continuously projects the share of customers restored by H+48.
- If the projection is below 90 %, it simulates +1, +2, … extra teams. For each one it tests the site where the team helps
  most, until the projection reaches 90 %.
- **Output:** "Request **+N teams** from other regions / the FIRE: 5 at Laurencin, 4 at Foix, …".
- **Example in the app:** with 25 % of the teams at 03h39, the projection is 55 %. **+25 teams** brings it to 91 %, with the
  split per site and the sites highlighted on the map.
- The manager decides. The engine gives the number and the place.

---

## 5. The LLM layer (explain, translate, answer)

- **Model:** a free OpenRouter model (`nvidia/nemotron-3-super-120b-a12b:free`, reasoning disabled), with Gemma fallbacks.
- **Explain:**
  - each recommendation has a short **headline** (e.g. "Grenade-2 → Fronton: 27 clients rétablis vers 02:00") plus
    **2 business sentences** on demand ("why this team");
  - **grounding check:** every number, time and duration in the LLM's text must exist in the engine's facts. Otherwise we
    show a deterministic template. No hallucinated figures reach the manager.
- **Translate (refusal → rule):**
  - the manager refuses with a reason chip plus free text, e.g. "le camion de Balma-3 est en panne pendant 3 h";
  - the LLM turns it into a structured rule from a fixed catalogue (team unavailable, zone inaccessible until…, travel
    factor, forbid/force, duration update, priority, reserve);
  - a **validator** checks it, and the **engine prices it** ("Équipe Balma-3 indisponible jusqu'à 03h39: +651 clients·h");
  - the manager confirms, and the plan is recomputed;
  - if the LLM fails, a rule parser takes over.
- **Answer (copilot chat):**
  - "Pourquoi cette équipe ?";
  - "Et si je perds 50 % des équipes ?" (engine what-if);
  - "Quels clients sensibles attendent ?";
  - "Où est la saturation ?";
  - "Faut-il des renforts ?".

  The answers come from the engine's data; the LLM only writes them.

---

## 6. The self-improving loop

**Important framing:** the system improves by learning **rules** from human refusals, validated by experts. It does not
retrain the LLM or let the AI change itself. That is a deliberate safety choice for a critical infrastructure. The LLM never
creates a permanent constraint on its own.

### 6.1 During the crisis (implemented, works live in the app)
Refusal + reason → LLM → rule → validated → priced → confirmed → the engine re-plans immediately around it. Every decision
(accepted, overridden, refused) is stored in a **knowledge base**: the context, the recommendation, the reason, the chosen
alternative and the cost.

When a similar case comes back, the card shows **"Déjà refusé N fois dans ce cas"** with **"Appliquer la même règle"**.

### 6.2 After the crisis: expert review (implemented as a prototype)
1. **Expert system:**
   - groups recurring refusals by pattern (site → commune, site → département; threshold of 3 refusals);
   - each group becomes a **candidate constraint**;
   - safety reasons raise an immediate alert.
2. **Replay test:** the candidate is replayed on 10 historical crises. Example: "No team from Balma (Toulouse) to Ariège
   (terrain knowledge)" costs **+0.1 % customer-hours** and keeps the 90 %/48 h target in **10/10** crises.
3. **Human experts** validate (or reject). The rule enters a **versioned constraint registry** (id, evidence, approver,
   date, version) and becomes an input of the engine for every future crisis. It can be retired at any time. Every decision
   records the registry version that produced it (traceability, rollback).

### 6.3 What is real and what is simulated (be honest if asked)
| Part | Status |
|---|---|
| Refusal → LLM rule → validation → cost → re-plan | **Implemented and live in the UI** |
| Knowledge base (SQLite decision log), "already refused" hint | **Implemented** |
| Expert system (pattern statistics), replay test, versioned registry, validate/retire UI | **Implemented (prototype)** |
| Refusal data used in the demo | **Simulated**: a scripted "manager" refuses Toulouse teams sent to Ariège; flagged "simulés" in the UI. No real Enedis refusal history exists yet. |
| Smarter expert system (clustering reasons, LLM summary of refusals for experts, soft penalties instead of hard rules) | **Vision / next step** |
| Learning repair-duration and travel estimates from field feedback | **Vision**: the loop only updates data the model reads, never solver code |

**Pitch line:** *"The AI doesn't learn by itself in the dark. It learns from your experts, under your experts' control,
and every new rule is tested on past crises before it goes live."*

---

## 7. The demo (front-end = EnedisPO, connected to the real engine)

- **Map** of the 3 départements:
  - incidents (size = customers, red = sensitive), teams, sites with the number of available teams;
  - routes drawn on real roads;
  - saturation layer.
- **Panel "À décider":** the recommendation in focus, with Accepter / Changer d'équipe / Refuser… / Pourquoi ?, plus
  **"Comparer les 3 meilleures options"** (3 routes in colour on the map, the cost of each alternative in customer-hours).
- **Header:**
  - clock and key figures;
  - **90 % gauge vs the 48 h target**, with a **FIRE** button when the target is missed (reinforcement popup);
  - "Règles actives", "Retour d'expérience" (expert review).
- **Timeline:** the whole crisis replayed. Customers cut off over time (past solid, projection dashed), incident arrivals,
  teams working / resting.
- **Reference strategy** view to compare our plan with a classic dispatch.

**Suggested demo flow (3–4 min):**
1. Start the crisis and press play. Incidents appear.
2. Click "Pourquoi ?". A short answer in plain French, with numbers from the engine.
3. Compare the 3 options on the map, then accept.
4. Refuse one ("camion en panne 3 h"). Show "Compris: … +651 clients·h", apply it, and the plan updates.
5. Switch to 25 % of the teams (stress test). The gauge turns red; FIRE gives "+25 équipes, ici, ici, ici".
6. "Retour d'expérience": the recurring refusal becomes a candidate rule; test it on 10 past crises (+0.1 %, target held);
   validate it.
7. Close on the numbers (§8).

Prepare before the demo: open the 25 % scenario once (first computation ≈ 1 min), and check the OpenRouter quota.

---

## 8. Results (organisers' data, official indicator Σ N × T, lower is better)

**All 100 historical crises**, real engine, no knowledge of future incidents:

| Strategy | Customer-hours (mean) | Gain of our engine | Better on |
|---|---|---|---|
| First come, first served | 166,264 | **−27.7 %** | 100/100 |
| Nearest team | 145,953 | **−20.1 %** | 100/100 |
| Most customers first | 133,404 | **−15.7 %** | 100/100 |
| Smith rule alone | 133,186 | **−16.5 %** | 100/100 |
| **Our engine (RSLS)** | **112,198** | n/a | n/a |

- **Quality:** our 3-second plan is within **2.3 %** of OR-Tools (an industrial solver, given 60 s and our plan as a start).
- **Demo crisis CRISE_027:** 252,882 vs 400,832 customer-hours for the front-end's reference strategy (**−37 %**).
- **90 % within 48 h:** met in **100/100** crises with all teams and the optimised roster. Under heavy stress (half the
  teams lost, two crises in a row) it is missed because of **capacity, not dispatch**, and the engine computes how many
  reinforcement teams are needed and where.
- **Robustness (heaviest crisis):** better than the Smith rule in every scenario tested: normal, flood (Ariège cut 12 h),
  storm (all trips ×1.5), uncertain repair times, team loss, two crises.
- **Speed:** a re-plan takes < 3 s; replaying a decision on the whole crisis takes ≈ 2.6 s.

**Translate for the jury:** about **20–28 % fewer customer-hours without power** than classic dispatch rules. On a crisis
with 100,000+ customer-hours, that is tens of thousands of customer-hours saved.

---

## 9. Why us (differentiators)

1. **A real optimiser, not a chatbot.** Decisions come from operations research with measurable gains on 100 real crises.
   The LLM is a translator, so no invented numbers.
2. **The human is in control, and their refusals improve the system.** Every refusal is priced, explained, stored, and
   can become a rule after expert validation.
3. **It respects people:** fixed 12 h / 12 h shifts known in advance, chosen once, never reshuffled mid-crisis.
4. **It answers the operational question nobody else answers:** *"How many teams do I need from other regions, and where?"*
5. **Explainable and auditable:** a headline plus 2 sentences, the 3 best options with their cost, the cost of every human
   override, versioned rules.
6. **It works end to end:** real data, a real map with real roads, a working UI connected to the engine.

---

## 10. Limits and next steps (say them before the jury does)

- **Synthetic data:** customer counts and repair times (2/4/8 h) come from the organisers' examples. The method doesn't
  depend on them.
- **Travel times** are a calibrated model. Live OSRM routing is possible; a production version would use Enedis's road data
  and real-time traffic and closures.
- **One team per incident.** Multi-team jobs are configurable but not tested.
- **No en-route diversion yet** (a team travelling is locked). Designed as an option; the expected gain is small because
  repairs dominate travel.
- **Robust selection over uncertain repair times** (P10–P90 windows) is designed, not implemented. Robustness was tested by
  simulation instead.
- **Coverage gap:** with the optimised roster, nobody is on duty between H+14 and H+24. Fine for these crises; a
  minimum-coverage rule is proposed for night or back-to-back crises.
- **The learning loop is fed by simulated refusals** for the demo. It needs real field use to prove itself.
- **Next feature (from the team):** propose **a whole plan** (and up to 3 alternative plans) for validation, instead of
  validating route by route.

---

## 11. Likely jury questions and answers

- **"Why not just use an LLM to decide?"** LLMs can't guarantee feasibility or optimality and can invent numbers. Ours
  explains decisions it didn't make, and its numbers are checked against the engine.
- **"Why not a commercial solver (OR-Tools, Gurobi)?"** We measured it: OR-Tools with 60 s is only ~2.3 % better than our
  3 s plan. Ours re-plans at every event, is deterministic, explainable (Smith's rule = customers per hour), and runs
  without a licence.
- **"What if the manager disagrees?"** They refuse with a reason. The system turns it into a rule, shows what it costs,
  re-plans, and remembers.
- **"Could the system learn something dangerous?"**
  - No rule becomes permanent without a replay test and expert validation;
  - safety reasons raise an alert;
  - rules are versioned and can be retired.
- **"How do you handle uncertainty?"**
  - Re-planning at every event;
  - stress scenarios (floods, storms, uncertain durations, team loss);
  - the 48 h projection with an early alert.
- **"Does it scale?"** One crisis = 50–250 incidents, 63 teams, re-plan < 3 s in Python. Larger regions: same algorithm,
  with a bigger time budget or a compiled core.
- **"What about the teams' well-being?"** Fixed rotation, 12 h max, 12 h rest, hours known in advance; repairs never cross
  the end of a shift.
- **"Why minimise when the README says maximise?"** Maximising Σ N×T literally rewards long outages. Maximising
  "customers restored early" is mathematically the same as minimising Σ N×T, the official indicator.

---

## 12. Key numbers cheat sheet

| | |
|---|---|
| Crises in the data | 100 (2016–2018), 15,681 incidents |
| Territory | Ariège, Haute-Garonne, Gers: 33,288 substations, 18 sites, 63 teams |
| Gain vs classic rules | **−16 % to −28 %** customer-hours, better on **100/100** crises |
| Gap to OR-Tools | **2.3 %** (3 s vs 60 s) |
| Demo crisis vs reference | **−37 %** |
| 90 % in 48 h | **100/100** crises with all teams |
| Roster | 12 h / 12 h, A at H0, B at H0+2h, **−11.6 %** customer-hours |
| Travel model | 3,718 real road trips, 8.3 min mean error |
| Re-plan time | < 3 s; explanation: headline + 2 sentences |
| Stress example | 25 % of teams: 55 % → **+25 teams** → 91 % |
| Learned rule example | Balma → Ariège: +0.1 %, target held 10/10, validated by an expert |
