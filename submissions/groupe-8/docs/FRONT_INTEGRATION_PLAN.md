# EnedisPO front-end ↔ RSLS engine: compatibility analysis and integration plan

Front-end analysed: `enedispo-main` (React + TypeScript + Vite, MapLibre + deck.gl, zustand). It was read, not run.
Its single swap point is `src/data/source.ts` (`CrisisSource`). The contract is `src/data/contract.ts`, and the proposed
API is in `src/data/api/apiSource.ts`. Goal: **implement the front-end's API on the backend**, so the front-end only needs `VITE_DATA_SOURCE=api`.

## 1. The two models

| | Front-end (as designed) | Our backend (today) |
|---|---|---|
| Time | discrete **30-min steps of crisis time** (computed in seconds, played back like a video), full crisis pre-computed | event-driven, live session advancing step by step |
| What the UI loads | **full timelines**: one `Snapshot` per step from start to end, for `ours` and `reference`; the user scrubs past/future freely | one snapshot at "now" |
| Decisions | `POST decisions` with `(step, incident, team, kind, reason)` → **whole timelines re-simulated** | accept / reject → re-plan from now |
| Untouched recommendation | executed automatically at its step (playback runs on its own) | waits for the manager |
| Refusal | only "Changer d'équipe" (override with a reason label) | reject → reason → LLM rule → validator → priced → confirm |

**Consequence:** we need an adapter, a *timeline runner* that replays the crisis in 30-min steps with our engine, applies the
manager's decisions at their step, auto-accepts the others, and returns the full snapshot lists. The engine itself is unchanged.

## 2. Compatibility, field by field

| Contract field | Status | Source in our engine |
|---|---|---|
| `CrisisMeta` (crisisId, start ISO, stepMinutes, sites, strategies) | ✅ | loaders, t0, config |
| `Incident` (id, posteId, lon/lat, commune, clients, sensitive, cause, repairHours, reportedAt) | ✅ | `Incident` |
| `Incident.status` waiting / enroute / repairing / restored, `teamId` | ✅ map | pending / in progress (split by arrival time) / restored |
| `Team` (id, siteName, lon/lat, incidentId) | ✅ | `Team` |
| `Team.label` ("Muret-3") | ✅ derive | site commune + index |
| `Team.status` available / travelling / repairing / **resting** | ✅ derive | resting = off duty in the fixed roster |
| `Team.lon/lat` while moving | ⚙️ add | interpolate between trip origin and incident |
| `Team.shiftHoursLeft` | ✅ derive | current shift end − now |
| `Recommendation` (teamId, incidentId, eta, travelMinutes, factors) | ✅ | plan + explanation facts |
| `Recommendation.priority` (higher = more impactful) | ✅ | priority index (customers per hour of work) |
| `Recommendation.note` | ✅ reuse | headline, or past-refusal hint |
| `Alternative` (teamId, deltaScore, travelMinutes, eta, shiftHoursLeftAfter) | ✅ better | our Δ is a real re-insertion, not the mock's first-order estimate |
| `Alternative.feasible`, `reason` | ⚙️ add | today we drop infeasible teams; keep them with the decoder's reason ("fin de poste", "au repos", "zone fermée") |
| `Alternative.recommendedFor` | ⚙️ add | other teams' first jobs in the plan |
| `alternatives` list size | ⚙️ add | today top 2; the "Changer d'équipe" drawer needs ~8–10 |
| `Kpis` clientsCut, clientsRestored, incidentsWaiting, teamsAvailable / Busy / Resting | ✅ derive | session state |
| `Kpis.score` (customer-hours so far) | ✅ | Σ customers × (min(now, restored) − reported) |
| `Kpis.scoreBaseline` | ⚙️ add | reference timeline (see §3) |
| `Kpis.restore90Hours` (until 90 % of customers cut so far are restored, per plan; `null` if never) | ✅ derive | projected restoration (`service`) on a customers basis |
| `Decision` echo (incident, team, kind, recommendedTeamId, reason) | ✅ | session log |
| `whatIfTeams(share)` → {score, baseline} | ✅ | simulator with a share of teams |
| `explainRecommendation()` → {paragraphs[], limits} | ✅ replace | our headline + 2-sentence details (LLM or template) + our limits text |
| `answerQuestion()` (copilot chat) | ⚙️ new endpoint | LLM over engine data; template fallback |

## 3. Not compatible / not in the UI: resolve or mock

| Topic | Gap | Proposal |
|---|---|---|
| **Reference strategy** | front: "first reported incident first, nearest feasible team" (incident-centric); ours: team-centric FIFO | add that exact rule as a `reference` policy (small) |
| **Recompute cost** | every decision re-simulates the whole crisis (~80–120 steps) | checkpoint the state at every step and replay only from the decision step. Smaller search budget for future steps (projection) than for the current step. Target ≤ 5 s per decision |
| **Initial team state** | mock: 1 team in 5 starts off duty, others 3–12 h left | ours: optimised fixed roster (group A at H0, B at H0+2 h). The UI shows it as is, no change |
| **Refusal with a rule** (flooded zone, team down) | no UI for it (only "Changer d'équipe") | phase 3: through the copilot chat ("Muret inondé jusqu'à 18 h" → rule → priced → applied), new endpoint `POST /crises/{id}/rules` |
| **Learning loop** (knowledge base, review, registry) | no UI | **build the UI** (phase 3): refusal dialog with reason → rule popup, past-refusal banner on the card, expert review popup |
| **Our 3 best paths** | not drawn | **build the UI** (phase 3): 3 coloured routes on the map + comparison popup |
| **Reinforcement (+N teams)** | the UI shows the FIRE flag above 48 h, no count | **build the UI** (phase 3): reinforcement popup when the 90 % target is missed |
| **`?equipes=50`** | mock only | accept `?team_share=` on `/timelines` and `/meta` (one-line change in `apiSource.ts`) |
| **Our GeoJSON map layers** | the front-end builds its own map from snapshots | not needed (keep for other clients) |
| **Event-driven vs 30-min steps** | dispatch only at step boundaries in timeline mode (≤ 30 min idle) | accepted for the demo; live mode stays event-driven |
| Repo layout | the front-end sits untracked inside the backend folder | keep it as its own repo, or move it to `frontend/` (team decision) |

## 4. Implementation plan

**Phase 1: the contract (front-end runs on the real engine, no front-end change)** ≈ 4–6 h
1. `src/dispatch/adapters/timeline.py`: `TimelineRunner(crisis, decisions, team_share)`.
   - 30-min steps; at each step: arrivals and completions, re-plan, recommendations, apply decisions (accept / override = Force), auto-accept the rest, snapshot.
   - Checkpoint per step to resume from a decision.
2. `adapters/contract.py`: map our objects to `Snapshot`, `Kpis`, `Incident`, `Team`, `Recommendation`, `Alternative`, `Decision`, `CrisisMeta` (camelCase, ISO times).
3. Extend `explain()`: up to 10 alternatives, infeasible ones with reason, `recommendedFor`, `shiftHoursLeftAfter`.
4. `reference` policy (first reported, nearest feasible team) and its timeline, cached per crisis.
5. FastAPI routes exactly as `apiSource.ts`: `GET /crises/{id}/meta`, `GET /crises/{id}/timelines`, `POST|DELETE /crises/{id}/decisions`, `GET /crises/{id}/what-if?team_share=`. Overrides are logged in the knowledge base with their reason.
6. Contract tests: validate our JSON against the TypeScript types (generated JSON schema), same snapshot count for both strategies, idempotent decisions.

**Phase 2: LLM in the UI (two one-function swaps in the front-end)** ≈ 2–3 h
7. `GET /crises/{id}/explanation?step=&incident=` → `{paragraphs, limits}`: headline + details (OpenRouter, checked) + limits.
8. `POST /crises/{id}/copilot {question, step, focusRecId}` → text. Intent routing ("pourquoi", "et si 50 %", "sensibles", "saturation", "renforts"). Numbers from the engine, wording by the LLM, template fallback.

**Phase 3: our features in the interface (backend routes + React components)** ≈ 5–7 h
9. **3 best paths.** Backend: `options` (rank 1–3, path, restoration time, extra customer-hours) in each recommendation.
   UI: the focused recommendation shows 3 routes on the map (green = recommended, yellow, orange). Hovering a route or a row
   highlights it. A "Comparer les 3 options" popup shows a small table (team, route, restoration time, extra cost) with
   "Choisir" on each line (→ override).
10. **Reinforcement.** Backend: `kpis.reinforcement {extraTeams, bySite, projectedAfter}`, computed when the 90 % estimate
    goes above 48 h. UI: popup "Objectif 90 % à 48 h hors d'atteinte — demander +6 équipes : Foix 4, Muret 2 → 91 %",
    opened from the FIRE flag, plus a map highlight of the requested sites.
11. **Learning loop.**
    - **Refusal dialog** on "Refuser": reason chips + free text → backend (`POST /crises/{id}/refusals`) → LLM rule →
      popup « Compris : Muret inaccessible jusqu'à 18 h. Appliquer ? (coût +2 830 clients·h) » → confirm → timelines recomputed.
      The question case ("Jusqu'à quelle heure ?") is shown in the same popup.
    - **Past-refusal banner** on the card: « Vous avez déjà refusé 3 fois Foix → Lavelanet (motif : …). Appliquer la même règle ? »
    - **Expert review popup** ("Retour d'expérience" button): candidate rules from repeated refusals, evidence, replay test
      (cost, 90 % target held), "Valider" (→ registry, new version) / "Écarter". Demo data from the simulated manager,
      labelled as simulated.
    - **Active rules list** (small panel): crisis rules + permanent rules, each removable.
12. **Network layer** (optional): all 33,288 substations as light dots, outages highlighted (`GET /postes` GeoJSON).
13. `team_share` passthrough for the stress demo.

**Decisions needed from the team**
- OK to adapt the backend to the front-end's API as is (recommended: zero front-end change for phase 1)?
- Phase 3 UI: built by us in the front-end repo, following its design rules (tokens.css, pills for actions, French, transitions < 200 ms)?
- Default demo crisis: the front-end uses CRISE_027, our benchmarks use CRISE_051 (the heaviest).
- Where the front-end lives: its own repo, or `frontend/` in this repo.
