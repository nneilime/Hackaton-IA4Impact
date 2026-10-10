# API for the front-end

Start: `pip install -e ".[api]"` then `uvicorn dispatch.api.app:app --reload --app-dir src`.
Interactive docs: http://localhost:8000/docs. CORS is open (hackathon).

All decisions and numbers come from the engine. The front-end displays them and sends the manager's decisions back.
Times are **hours since H0** (the first incident); every time also has a `*_clock` field ("28/05 08:18") where useful.

## 0. Live mode: `/live` (the crisis in real time)

The clock is the real one (H0 = when the crisis is opened). The engine only learns about the world through events sent
by the field (in the demo: `python -m simulator`, a separate process). Nothing is dispatched until the manager validates.

| Call | Body | Returns |
|---|---|---|
| `POST /live/reset` | `{"speed": 1, "label": ""}` | opens a new crisis now; `speed` > 1 runs the clock faster (demo) |
| `GET /live/clock` | – | `start`, `nowHours`, `speed`, `serverTime` |
| `POST /live/events` | one event or a list: `{"type": "incident_reported", "id", "poste_id", "est_duration_h", "cause"?}` · `{"type": "team_on_site", "team", "incident"}` · `{"type": "repair_done", "team", "incident"}` · `{"type": "team_unavailable", "team", "until_h"?, "reason"?}` | `{ok, at_h}` |
| `GET /live/dispatches?after=seq` | – | trips started by the manager's validations (`seq, team, incident, depart_at, travel_h, repair_h`): the field plays them and reports back |
| `GET /live/meta` | – | `CrisisMeta` + `mode: "live"`, `speed`, `roster` (shift groups A/B/C) |
| `GET /live/state?have=n` | – | `version`, `clock`, the current `snapshot` (front-end contract), `history[n:]`, `historyLength` |
| `POST /live/plan/accept` | `{"assignments": [{"incidentId", "teamId", "reason"?}], "reason"?}` | `{dispatched}`: free teams leave now, busy ones take the job next |
| `GET /live/plan/explanation?llm=` · `GET /live/explanation?incident=` · `POST /live/copilot {question, recId?}` | – | as in replay mode, for the plan on screen |
| `GET /live/reinforcement` · `POST /live/refusals` (+ `/{pid}/confirm`) · `GET`/`POST /live/rules` · `DELETE /live/rules/{i}` | – | as in replay mode |

## 1. Start and drive a crisis (replay of a past crisis)

| Call | Body | Returns |
|---|---|---|
| `GET /crises` | – | `["CRISE_001", …]` |
| `POST /sessions` | `{"crisis_id": "CRISE_050", "budget_ms": 50, "teams_fraction": 1.0}` | `session_id` + snapshot |
| `GET /sessions/{id}` | – | snapshot |
| `POST /sessions/{id}/advance` | `{"to_h": 2.5}` or `{}` (next event); `"auto_accept": true` = replay mode | `dispatched` + snapshot |

**Snapshot** (for the map and the panels):
- `kpis`: `now_h`, `now_clock`, `known`, `pending`, `in_progress`, `restored`, `customers_restored`, `customer_hours_so_far`, `finished`
- `teams[]`: `id`, `site`, `lat`, `lon`, `status` (idle / travelling), `on_duty`, `shift {start_h, end_h}`, `current_job`, `next_jobs` (preview of the next 3)
- `incidents[]` (known so far): `id`, `lat`, `lon`, `commune`, `customers`, `sensitive`, `repair_h`, `status` (pending / in_progress / restored), `team`, `restored_h`, `restored_clock`
- `rules[]` (crisis rules confirmed by the manager), `permanent_rules[]` (expert registry), `plan_version`, `plan_score`

## 1b. Map layers: `GET /sessions/{id}/map`
A GeoJSON `FeatureCollection` you can pass straight to Leaflet / Mapbox / deck.gl. Filter on `properties.layer`:

| layer | geometry | what to draw | key properties |
|---|---|---|---|
| `site` | Point | operational bases | `commune`, `teams` |
| `team` | Point | team markers (colour by `status`, grey if not `on_duty`) | `status`, `on_duty`, `current_job` |
| `incident` | Point | outage markers: size by `customers`, colour by `status` (pending / in_progress / restored), ring if `sensitive` | `eta_clock`, `waiting_h`, `score_share`, `remaining_customer_hours` |
| `route` | LineString | **solid** = committed trip (`committed: true`, `phase` travelling / repairing), **dashed** = planned next jobs (`phase: planned`, up to 3) | `team`, `incidents`, `depart_h` |
| `heat` | Point | heatmap of what is still at stake | `weight` = customers × hours still without power |
| `zone` | Point + `radius_km` | circles for operator rules (flooded / forbidden zones) | `rule` |
| `option` | LineString | the 3 best paths for each current recommendation: rank 1 = recommended (#2A9D8F), 2 (#E9C46A), 3 (#E76F51) | `incident`, `rank`, `team`, `restored_clock`, `extra_customer_hours` |

**Why lines and heat follow from the objective:** the score is a sum over incidents, Σ customers × hours without power. Each incident therefore has its own share (`impact_customer_hours`, `score_share`), and the part still to come (`remaining_customer_hours`) is what the heatmap shows. Routes are the plan itself: the order in which teams will take incidents.

## 2. Recommendation cards
`GET /sessions/{id}/recommendations`: one card per idle, on-duty team that should leave now, best first.
```json
{"team": "SITE_01_E2", "incident": "INC_008120", "restored_clock": "10/01 15:18",
 "headline": "Foix → Saint-Jean-de-Verges : 138 clients rétablis vers 15:18",
 "details": "L'équipe SITE_01_E2 (Foix) rend le courant à 138 clients car c'est l'intervention qui rétablit le plus de clients par heure de travail (19 min de route, 2 h de réparation). Confier cette panne à l'équipe SITE_02_E1 coûterait 269 clients-heures sans courant de plus, soit ces 138 clients privés d'électricité 1 h 57 de plus.",
 "text_source": "template",
 "options": [
   {"rank": 1, "team": "SITE_01_E2", "team_site": "Foix", "restored_clock": "15:18", "extra_customer_hours": 0, "recommended": true,
    "travel_min": 19, "path": [[1.606, 42.965], [1.62, 42.93]]},
   {"rank": 2, "team": "SITE_02_E1", "team_site": "Lavelanet", "restored_clock": "15:35", "extra_customer_hours": 269, "recommended": false, "path": [...]},
   {"rank": 3, "team": "SITE_17_E4", "team_site": "Villefranche-de-Lauragais", "restored_clock": "15:55", "extra_customer_hours": 899, "recommended": false, "path": [...]}],
 "facts": {...}, "past_refusals": null}
```
- **headline**: always shown (deterministic, exact, instant).
- **details**: shown when the card is expanded. The template is included right away. For the LLM version, call
  `GET /sessions/{id}/recommendations/{team}/{incident}/explanation`, which returns `{headline, details, source: "llm"|"template"}`
  (≈ 2 s, cached). The LLM text is accepted only if it has ≤ 2 sentences and every number, time and duration is in the facts.
- **options**: the **3 best paths** for this outage, i.e. the recommended team plus the 2 best alternative teams. Each has a
  `path` ([lon, lat] from the team to the outage), its restoration time and its extra cost in customer-hours.
  Draw them with 3 colours, or show them on hover. They are also in the map (`layer: "option"`, with `rank` and `colour`).
- When `past_refusals` is set, show its `question` ("Vous avez déjà refusé 3 fois … Appliquer la même règle ?").

## 3. Manager decisions
| Action | Call |
|---|---|
| Accept | `POST /sessions/{id}/accept {"team", "incident"}`. A different pair than recommended is logged as a *modification*. |
| Refuse | `POST /sessions/{id}/reject {"team", "incident", "reason_code"?, "reason_text"?}`. Reason chips: `GET /reasons`. |
| → if `{"question": …}` | ask the manager, then call `reject` again with the answer in `reason_text` |
| → if `{"proposal_id", "restatement", "cost_delta", "modifiers"}` | show « {restatement} Appliquer ? (coût : {cost_delta} clients·h) » |
| Confirm / cancel | `POST /sessions/{id}/proposals/{pid}/confirm` · `…/cancel` |
| Remove a rule | `DELETE /sessions/{id}/rules/{index}` |
| What-if | `POST /sessions/{id}/what-if {"modifiers": [{"type": "force", "team": "…", "incident": "…"}]}` → `cost_delta` |

Rule types (`modifiers`): `force`, `forbid`, `team_unavailable`, `zone_inaccessible`, `travel_factor`, `duration_update`,
`priority`, `reserve`, `weight`. Invalid rules return HTTP 422 with the reason in French.

## 4. Service target (90 % within 48 h) and reinforcement
`GET /sessions/{id}/service` →
`{"projected_share": 0.86, "target": 0.9, "target_met": false, "reinforcement": {"extra_teams": 6, "by_site": {"Foix": 4, "Muret": 2}, "projected_share_after": 0.91}}`.
It is a check, not part of the objective. Show the alert with the reinforcement request when `target_met` is false.

## 5. Learning loop (expert review)
| Call | Purpose |
|---|---|
| `GET /learning/stats` | decisions logged, refusal rate |
| `GET /learning/candidates` | candidate rules from repeated refusals (evidence, main reason, safety alert) |
| `POST /learning/candidates/backtest {"candidate": {…}}` | replay test: cost in customer-hours, 90 % target still met? |
| `POST /learning/registry/activate {"candidate": {…}, "approved_by": "rôle de l'expert"}` | expert validation → new registry version |
| `GET /learning/registry` | active / retired permanent rules |

Demo data: `python bench/review_refusals.py --simulate CRISE_051 CRISE_046 CRISE_013 CRISE_024` fills the knowledge base
with refusals from a **simulated** manager (flagged `simulated`).

## LLM
Without a key (`MISTRAL_API_KEY`, or `OPENROUTER_API_KEY` for the fallback provider, in `.env`), texts come from
templates and refusal reasons are parsed by rules. Everything works. With a key, the model set in `config/default.yaml`
(`llm`: Mistral first, OpenRouter free models as fallback) writes the expanded details and interprets free-text reasons. Every number
it writes is checked against the engine's facts, and every rule it proposes goes through the validator.
