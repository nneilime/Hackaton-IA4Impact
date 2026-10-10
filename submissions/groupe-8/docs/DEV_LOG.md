# Development log and working context (read this first when resuming)

Last update: 10 October 2026, during the hackathon (Défi Enedis, La Mêlée, 9–10 Oct 2026).
Repo: `C:\Users\HAMZA\Desktop\enedis-hackathon` → GitHub `manticore999/hackatoun`. Work branch **`feat/engine-rsls`**
(local, NOT committed / pushed yet; `main` = skeleton commit `6907cde`).

## 1. What we are building
Real-time decision support for dispatching Enedis repair teams during a storm. The **engine decides and computes**, the
**LLM explains and translates**, and the **manager validates**. The objective is to minimise Σ customers × hours without power
(official N×T indicator; the README's "maximiser" is a typo). The **90 % of incidents within 48 h** target is a **check, not part of the
objective**. When it fails, the system recommends reinforcement (+N teams from other regions, per site).

## 2. Decisions taken (do not undo without asking the user)
- **Engine = RSLS** (Rolling-horizon Smith + Local Search): Smith-rule construction w/(travel+repair) → local search
  (relocate / swap / ruin & recreate, prefix-cached + lower-bound pruning) → re-plan at every event, commit only the next job.
  Decoder enforces the rules. See `docs/CURRENT_SETUP.md`, `docs/Compute_Engine_Model_Decision.pdf`.
- **Shifts fixed once at initialisation** (not re-optimised during the crisis): 12 h work / 12 h rest. Group A starts at H0,
  group B at H0+2 h (per-site split in `config/default.yaml` → `roster`), optimised on 50 crises, tested on 50 others.
- **Travel**: offline model calibrated on 3,718 real OSRM trips (MAE 8.3 min, 12.5 %), `travel.mode: simulated`. OSRM live mode
  available (cache `data/cache/osrm.json`, needs certifi). Waze has no public routing API.
- **LLM = OpenRouter**, key in `.env` (`OPENROUTER_API_KEY`, gitignored; the user should rotate it after the hackathon).
  Model `nvidia/nemotron-3-super-120b-a12b:free` (reasoning disabled), fallbacks Gemma 4 31B/26B. **Not** `openrouter/free`:
  it routed to a safety classifier. Gemma is often rate-limited (429).
- **Card text**: deterministic **headline** + expandable **2-sentence details** (template instantly, LLM on expand).
  LLM text accepted only if ≤ 2 sentences and every number/time/duration is in the facts. The same goes for refusal → rule:
  LLM JSON → normalised → validator → if rejected, fall back to the rule parser.
- **3 best paths** per recommendation (recommended team + 2 best alternatives) must be **visible in the UI** (map colours + popup).
- **Reinforcement count** and the **learning loop** (refusal dialog, past refusals, expert review, rule registry) must be
  **visible in the UI** (popups), not only in the backend.
- **Live by default** (2026-10-10): the dashboard opens on the crisis in real time (H0 = now, Paris clock). In live
  mode the backend never simulates the field: it only receives events (`POST /live/events`) from an external system,
  in the demo the separate `simulator/` process. Nothing is dispatched before the manager validates. The accelerated
  replay of a past crisis is a secondary view (« Revoir une crise passée », `?mode=replay&crise=`).
- **Front-end** = teammate's EnedisPO (React/TS/Vite, MapLibre + deck.gl, zustand), copied into **`frontend/`**. We build
  everything in this repo. Its UI conventions: French, colours only from `src/styles/tokens.css`, pills for actions, square data
  containers, borders not shadows, transitions < 200 ms, Outfit for figures / Public Sans for text.
- Demo crisis: to decide later (front-end default CRISE_027; our benchmarks use CRISE_051, the heaviest).
- Environment: do NOT let pip upgrade numpy (scipy/numba need numpy 2.1.0). Use `pip install --user --dry-run` first.
  `ortools` and `uvicorn` are installed in the user site.

## 3. Architecture (backend `src/dispatch/`)
| Path | Role |
|---|---|
| `engine/` | types, modifiers (operator rules), context (applies rules), evaluate (decoder + incremental eval), construct (Smith list scheduling, insertion, warm start), local_search, planner, baselines (incl. `ReferencePolicy` = front-end reference), counterfactual, explain (facts + up to 10 alternatives with feasibility / reason / recommended_for), service (48 h check), reference_ortools, shifts |
| `session.py` | `LiveSession`: one crisis step by step (accept/reject/confirm, what-if, service + reinforcement, GeoJSON map, explanations, options = 3 best paths, past-refusal hints, `_commit` batch dispatch, `position()` interpolation) |
| `adapters/timeline.py`, `adapters/contract.py` | **EnedisPO timeline mode**: the crisis replayed in 30-min steps of crisis time; snapshots in the front-end contract (camelCase, ISO with Paris offset); checkpoints per step (decision replay ≈ 2.6 s); projection steps use a 25 ms search budget |
| `api/app.py` | FastAPI: live-session routes (`/sessions/...`), learning routes (`/learning/...`), GZip; mounts `api/frontend.py` |
| `api/frontend.py` | EnedisPO routes: `GET /crises/{id}/meta`, `GET /timelines`, `POST/DELETE /decisions`, `GET /what-if`; overrides logged in the knowledge base |
| `copilot/` | `client.py` (OpenRouter), `explain.py` (headline/details, grounding check), `translate.py` (reason → rules), `validator.py` |
| `learning/` | `memory.py` (SQLite decision log `data/decisions.sqlite`), `review.py` (candidates + replay test), `registry.py` (`config/constraint_registry.yaml`), `simulated.py` (simulated manager for demo data) |
| `sim/` | simulator (event-driven benchmark), scenarios (stress, flood, storm, two crises, noise, teams lost), whatif (reinforcement) |

## 4. How to run
```bash
# backend (from the repo root)
python -m uvicorn dispatch.api.app:app --app-dir src --port 8000 --reload --reload-dir src
# front-end on the real engine (opens in live mode)
cd frontend && VITE_DATA_SOURCE=api VITE_API_URL=http://localhost:8000 npm run dev -- --port 5173 --strictPort
# the field for the live mode (separate process): alerts of a past crisis from now + team reports; --speed 1 = real time
python -m simulator --crisis CRISE_027 --speed 60
# tests (global pytest plugins break without this env var)
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
```
Tests stub the LLM (`tests/conftest.py`). Benchmarks: `bench/run_benchmark.py`, `bench/scenarios.py`, `bench/gap_vs_ortools.py`,
`bench/calibrate_travel.py`, `bench/review_refusals.py`, `bench/reinforcement.py`, `bench/optimise_roster.py`.

## 5. Key results (for the pitch)
- 100 crises: optimised engine −27.7 % vs FIFO, −20.1 % vs nearest, −15.7 % vs most customers, −16.5 % vs the Smith rule; better on 100/100.
- Quality: the 3 s plan is +2.3 % from OR-Tools (started from our plan, 60 s), on saturated snapshots.
- Front-end crisis CRISE_027: ours 252,882 vs their reference 400,832 customer-hours (−37 %).
- 90 % within 48 h: met in 100/100 crises with all teams (optimised roster); missed under heavy stress → reinforcement.

## 6. Status / progress
- [x] Phase 1: front-end ↔ engine contract (timeline mode), verified in the browser (recommendations, accept, recompute 2.6 s).
- [x] Phase 2 (verified 2026-10-10 in the browser): "Pourquoi ?" → `/explanation` (headline + 2 sentences + limits, tag
      "Connecté au moteur"), copilot questions → `/copilot` (incl. "Faut-il des renforts ?").
- [x] Phase 3 (verified 2026-10-10 in the browser, all through the real backend):
  - 3 best options: "Comparer les 3 meilleures options" → side popup (no scrim) + map zooms to them, routes in green/yellow/orange
    on real roads (OSRM via `POST /routes`, cached in `frontend/src/components/map/roads.ts`), hover a row → route highlighted.
  - Refusal → rule: "Refuser…" → reason chips + free text → LLM rule → validated → costed ("Compris : Équipe Balma-3
    indisponible jusqu'à 03h39 (lundi)", +651 clients·h) → "Appliquer la règle" → replan + toast; header "Règles actives (n)"
    popup lists / removes rules. Past-refusal banner on the focus card with "Appliquer la même règle".
  - Reinforcement: FIRE pill (shown when 90 % > 48 h) → popup; `?equipes=25` at 03h39: 55 % → +25 teams → 91 %, per site,
    green rings on the map. "Préparer la demande" = toast only (no external send).
  - Expert review ("Retour d'expérience"): stats, "Générer des refus simulés" (CRISE_051/046, ~1 min) → candidate "Balma
    (Toulouse) → Ariège" → "Tester (rejeu)" (+0.1 %, 10/10 crises keep 90 %/48 h) → "Valider" (registry C001, replan) → "Retirer".
  - Fixes found while testing: copilot dock covered the whole screen (`.side` had no positioning context); `#root` scrolled
    sideways (closed dock off-screen → `overflow: clip`); road fetch never fired under StrictMode (side effect inside
    `useMemo` → the memo now returns the wanted pairs); rule texts showed ids / "H0 + x h" → `describe_rule(m, rule_names)`
    gives team labels + clock times, the refusal restatement is rebuilt from the validated rules (not the LLM's wording);
    candidate descriptions use site names.
  - Demo notes: a new `?equipes=` share is computed cold (~1 min) → open it once before the demo. The test left simulated
    refusals in `data/decisions.sqlite` (gitignored, flagged "simulés") — the candidate is therefore ready for a review demo;
    `config/constraint_registry.yaml` was reset to empty. `uvicorn --reload` sometimes kept a stale process: restart without
    `--reload` if new routes 404.
- [x] UI fix (2026-10-10, user: "not interactive at all, some boxes ugly/buggy"; their real viewport ≈ 1240×600 CSS px
      because of Windows display scaling). Verified at 1240×600 and 1920×1080:
  - Root cause of "not interactive": `<StrictMode>` (main.tsx) double-mounted the deck.gl `MapboxOverlay` → an orphan
    overlay canvas drew the markers while the live one got the mouse → hover/click on the map mostly hit nothing.
    StrictMode removed (dev-only anyway). Note for testing in the hidden browser pane: deck.gl initialises in
    requestAnimationFrame, so a pane that is not painting shows a 300×150 deck with 0 layers — take a screenshot first.
  - Layout: `.app` min-width 1280 → 1024 (the right panel was clipped), columns `1fr | clamp(380px, 38%, 720px)`, band
    `clamp(190px, 26vh, 248px)`, compact header (stacked small action pills), side panel scrolls instead of the focus card
    spilling over the timeline, media queries for width ≤ 1500/1250 and height ≤ 820/700 (comparison bars hidden < 700).
  - Map: fit padding proportional to the map size and territory re-framed on resize until the user moves the map
    (it opened on Spain); routes drawn under the markers; click a cluster → zoom in, click a site → zoom ≥ 10, click an
    incident/team/site → its card stays pinned (follows the map, closed by empty click / Esc / next step); cards are
    measured and kept inside the map.
  - Timeline: milestone labels placed by priority (48 h target, 90 %, peak, end, 50 %) and dropped instead of overlapping;
    y-axis labels thinned on short bands.
- [x] Dashboard re-layout (2026-10-10, user: "polluting / a little bit of a mess", keep all content): header = brand ·
      clock · 3 KPI cards + the 90 %/48 h KPI card (gauge + FIRE inside) · icon tool group (copilote, règles n,
      retour d'expérience; labels from 1600 px); map as rounded hero card; right column of cards that scrolls
      ("À décider" focus + "Ensuite" queue, "Décisions prises" collapsible with count); slim timeline card
      `clamp(150px, 21vh, 196px)` with a compact geometry (< 150 px: one milestone row, y ticks 0/max, one "équipes" strip
      label); site squares small and without numbers below zoom 8.5; card tokens `--radius/--radius-sm/--elev` in
      tokens.css; hover/active feedback on all controls. CSS: "Dashboard layout" section at the end of app.css.
      Checked at 1490×700 (screenshot). NOT yet re-checked after the re-layout: 1240×600, 1920×1080, real-click tests of
      accept → "Décisions prises" card, cluster click, pinned card.
- [x] Whole-plan validation + play button (2026-10-10, user: "an ensemble of routes as a solution … the simulation start
      button should work"). Verified in the browser (real clicks):
  - Right panel = "Plan proposé" as ONE unit: help sentence, summary (clients rétablis, arrival range, last restoration,
    sensitive customers), primary "Valider le plan (N affectations)" → `POST /crises/{id}/plan/accept` (source
    `acceptPlan`, store `acceptPlan()`, toast "Plan validé : N affectations"); then the lines (click one to open it:
    Pourquoi / Changer d'équipe / Refuser / 3 options; "Valider cette ligne seule" is secondary). After validation:
    "Plan validé" card + "Continuer la simulation"; "Décisions prises (n)" collapsible card.
  - Contract fix in `apiSource.ts` (`pendingOnly`): the engine's snapshot keeps a step's recommendations computed
    before the decisions at that step; the front now drops those whose incident/team was decided (as the mock does) —
    without it, a validated plan still showed as pending.
  - Play: it worked but crawled (each frame advanced ≤ 0.1 s of real time while the map rebuilt every frame). The clock
    now updates the store ≤ 20×/s with real elapsed time (cap 0.5 s); the button is a labelled pill (Lecture / Pause /
    Rejouer). Checked: 00h39 → 05h25 in a few seconds at ×60, stops at the end with "Rejouer".
  - The backend process on :8000 had to be restarted to serve `/plan/accept` (code unchanged).
- [x] 48 h target in the header (2026-10-10, user: the "90 % … dans ≈ 5 h" box was read as "incidents over 48 h"): shown
      only when it fails. Met → small green chip "✓ Objectif 48 h tenu" (tooltip: 90 % des incidents signalés réparés
      avant 48 h, prévu …, marge); "marge faible" badge above 42 h. Missed (> 48 h, or no estimate while incidents are
      open) → red alert card "Objectif 48 h menacé : 90 % des incidents réparés seulement dimanche vers 6 h (+105 h)" with
      "Chiffrer les renforts" (reinforcement popup). Wording switched to incidents (restore90Hours is now on the
      incidents basis): header, timeline milestone/summary ("90 % des incidents réparés prévus …"), 50 % milestone now
      counted in incidents; the reinforcement popup words its figures from the endpoint's `basis` field. Timeline axis
      ticks adapt (6/12/24 h) on long crises. Verified: CRISE_027 step 6 (met, 28.6 h) and ?equipes=25 step 12 (missed).
      OPEN (backend): `/reinforcement` still forces `basis = "customers"` (frontend.py:277) → the popup says
      "55 % des clients coupés" while the header counts incidents; switch it to the config basis (incidents).
- [x] Presentable dashboard pass (2026-10-10, user: "still not interactive, zoom in then out → totally cramped, not
      visually pleasing"; guidance from the ui-ux-pro-max skill: data-dense dashboard, reflow under zoom, labelled
      controls, visible feedback). Tested in a real headless Chrome (playwright-core in the scratchpad driving the
      installed Chrome: screenshots + real mouse; the in-app browser pane stalls on screenshots):
  - Zoom bug found and fixed: after the window shrinks (browser zoom = smaller CSS viewport) the layout kept its old
    width (1458 px inside a 1000 px window) because `.app` had an auto column sized by pixel-sized content (timeline
    SVG, map canvas). `src/styles/shell.css` (last CSS layer): `grid-template-columns: minmax(0, 1fr)`, `min-width: 0`
    on the grid children, page allowed to scroll (min-height 640 px) instead of crushing the map; < 1100 px the map and
    the panel stack. Verified 1490×700 → 1240×600 → 1000×520 → back.
  - Right column = one panel with tabs `Plan (n) · Copilote · Journal (n)` (`SidePanel.tsx`); the copilot lives in its
    tab (kept mounted), decisions moved to "Journal" (`Journal` in RecPanel.tsx); header copilot button removed, header
    tools always labelled (icons only < 1280 px).
  - The plan as an ensemble on the map: every proposed route drawn (alpha 170, focus 255) with a numbered pin
    ("1"…"n", TextLayer with background) matching the numbered lines of the panel; badge hover/click = line hover/focus.
    Markers smaller until zoom 8 (DETAIL_ZOOM) so the territory view is less cluttered.
  - Real-click checks: map hover card + cluster click zoom (7.0 → 9.6), Plan/Copilote/Journal tabs, "Valider le plan"
    (5 decisions, "Plan validé" card, server ≈ 5 s with "Validation…" feedback), Journal list, Lecture (00h39 → 03h31 in
    4 s at ×60). Test decisions reset afterwards. NOTE: `config/constraint_registry.yaml` has C001 active (Balma →
    Ariège), left by the UI session's tests.
- [x] Demo flow + plan justification + Mistral (2026-10-10, user's plan):
  - Flow: a historical crisis of the dataset (CRISE_027) replayed as if live, 30-min steps, the engine only knows the
    incidents reported so far. DECISION GATE: "Lecture" is blocked while a plan waits ("Décision requise" + the decision
    buttons flash); during playback the clock stops at each step with a new plan ("Nouveau plan proposé à …").
    "Valider le plan et continuer" = `/plan/accept` then play. One option only: the 3-options comparison, the 2nd-choice
    bars and "valider cette ligne seule" are gone from the panel (options popup code kept but unreachable).
  - "Pourquoi ce plan ?" (`GET /crises/{id}/plan/explanation?step&llm`, `copilot/plan_explain.py`): facts of the WHOLE
    plan (lines, cost of the next-best team as "N clients X longer without power", what still waits, 48 h check,
    whole-crisis average outage per customer vs the reference strategy) → template (instant) → LLM rewrite (system
    prompt explains the goal N×T, Smith order, shifts, 48 h check) kept only if every figure is grounded. Copilot
    question "Pourquoi ce plan ?" answers with it; copilot system prompt now explains how the system works.
  - Refuse → why → save: "Refuser…" on the plan opens the refusal popup with a line selector; reason → LLM rule →
    validated, priced → "Appliquer la règle" → replan at the same step (new plan to decide) + knowledge-base entry
    (verified: Fleurance-2 rule +36 clients·h, removed from the plan, KB rejected 9 → 10).
  - LLM: provider `mistral` (`MISTRAL_API_KEY` in .env, mistral-medium-latest → mistral-small-2603), fallback provider
    OpenRouter, then templates. The given Mistral key answers 429 with `x-ratelimit-limit-req-minute: 0` (workspace
    without an active plan): activate a plan on console.mistral.ai; meanwhile the OpenRouter fallback answers.
  - `/reinforcement` now uses the config basis (incidents), consistent with the header.
- [x] Learning loop reframed (2026-10-10, user: "we don't have permanent rules: a database of the manager's remarks;
      the AI learns patterns and proposes changes to the function's variables; clear, explainable"). Registry reset
      (C001 removed). `review.candidates` now returns observed / proposal / variable / before → after: terrain or access
      patterns → travel factor towards the zone (×1.3, ×1.5 for access), priority/safety on sensitive customers →
      sensitive weight ×4. New `GET /learning/remarks` (latest remarks, site names). "Retour d'expérience" popup: 3 steps
      (remarques · tendances · ajustements adoptés), cards Observé / Exemple / Proposé / variable before → after / Effet
      (replay of 10 past crises) / Adopter · Ignorer, adopted adjustments (Annuler), latest remarks. User asked to stop
      running full test suites each time: check only what changed.
- [x] Professional theme (2026-10-10, user: "kids-made navbar, remove Maquette hackathon, childish style", reference:
      dark-rail ops dashboard). Logo `docs/LogoEnedispo.png` → `frontend/public/logo-enedispo.png` (cropped,
      transparent). Layout `.app.pro`: white top bar (logo · "Pilotage de crise" · crisis replayed · engine status),
      navy left rail `Rail` in TopBar.tsx (clock, Situation figures, Objectif de service, Apprentissage: Consignes de la
      crise / Retour d'expérience), content = map + panel + timeline. `styles/pro.css` (last layer): neutral greys,
      Public Sans everywhere, 6-10 px radii, underlined tabs, white popup headers; < 1100 px the rail becomes a strip.
- [x] Proposal made readable (2026-10-10): plan card = kicker "Proposition du moteur · heure · décision requise" /
      "Envoyer N équipes maintenant" / "→ X clients retrouvent l'électricité d'ici HH" / POURQUOI CE PLAN as labelled
      lines computed client-side (Priorité, Gain vs habitual strategy from final scores, Objectif 48 h, Sensibles) +
      folded "Explication détaillée (IA)" / Valider · Refuser / table of assignments. Left rail switched to the light
      palette; right panel clamp(400px, 37%, 560px). Demo framing: accelerated replay of a real 2016 crisis, engine only
      knows reported incidents; in production it re-plans in real time at every event (< 3 s).
- [x] Demo-proof flow (2026-10-10, user: "plans not synchronised with time, team trips not visible, anything that works
      for the demo"). Root cause: validating a plan replayed the whole crisis on the server (13 s for the first plan,
      ~6 s after) while the clock waited, then swapped the timeline. Now validating the ENGINE'S OWN plan is applied
      locally at once (store.acceptPlan: step's recommendations → decisions) and only recorded server-side
      (`POST /plan/accept?replay=false`: journal + knowledge base, no recomputation) — the precomputed timeline already
      assumes those dispatches. Refusals / team changes still replay (that is when the projection changes).
      Map: pending plan = bold violet routes + numbered badges, map framed on the plan; validated plans = one colour per
      plan (sky, emerald, amber, pink, teal, indigo), each team keeps its full road route from its start point until it
      arrives; département borders grey. Default speed ×10. Verified in Chrome: 21h39 validate → 22h09 (26-team plan)
      → validate → teams on the road in green → stops at 22h39.
- [x] Demo preparation (2026-10-10). Roster: relief group C (+12 h) with a 20 % on-duty floor (config roster.c_*,
      min_on_duty; bench/optimise_roster.py; tests/test_roster.py): test crises -3.0 % vs everyone at H0 (old A/B -5.3 %
      but 0 % on duty H+14..H+24), 90 %/48 h met 100/100 (worst 92.8 %); demo crisis now >= 13 teams on duty at every
      hour, 276 470 vs reference 393 883 customer-h (-30 %). Sora font everywhere (incl. map labels). Bugs found by a
      full demo run in Chrome and fixed: "Pourquoi ce plan" 500 for figures >= 1 000 (narrow-space parsing); numbers
      without thousands separator (Sora lacks U+202F -> U+00A0); map buttons under the markers (z-index); KPI tile
      wrapping; long tags in "Changer d'équipe"; Enter validated one line (slow replay) -> validates the plan; plans
      validated in the browser lost after a refusal replay (store.withLocal re-applies them); journal now lists every
      plan validated so far; each page load = fresh demo (reset is instant unless a replay modified the timeline).
- [x] Live mode + decoupled field simulator + teams panel (2026-10-10, user: "le système doit fonctionner en temps
      réel, en attente des problèmes ; découpler la génération des alertes du back ; vue 'revoir une crise passée' en
      accéléré ; l'heure du système = maintenant ; liste des équipes et explication des postes dans le dashboard").
  - Backend `dispatch/live/service.py` (`LiveCrisis`): H0 = opening time on the real clock, `speed` for demos; the
    world is known only through field events (incident_reported, team_on_site, repair_done, team_unavailable); a
    ticker thread (1 s) re-plans once per tick when something changed (bursts of alerts coalesced) or a planned
    departure / shift change is due; NOTHING is dispatched until the manager validates (`POST /live/plan/accept`);
    dispatches are published (`GET /live/dispatches`) for the field to play; history snapshots every
    `live.history_minutes` of crisis time + one after each decision (timeline, journal). `LiveSession` gained
    `external_field` (no simulated arrivals / completions; `report / arrived / repaired`; a repair that overruns its
    estimate keeps the team busy until the field says done). Routes in `api/live.py`: same features as the replay
    (plan / line explanations, copilot, refusal → rule, rules, reinforcement). Config section `live`.
  - `simulator/` (separate process, HTTP only, `python -m simulator --crisis CRISE_027 --speed 60`): replays a past
    crisis shifted to now and plays the field teams (on-site / repair-done reports, optional lognormal noise on travel
    and repair times). Replaces the alert / completion simulation that used to live inside the backend for the UI.
  - Front-end: `data/live/liveSource.ts` (polls `/live/state` every second, backend clock), `source.ts` picks live
    (default with the API) or replay (`?mode=replay`, `?crise=`); top-bar switch « Revoir une crise passée » /
    « Revenir au direct »; live = no playback, no reset, timeline runs to now, « en veille » states while no alert.
    New **Équipes** tab (`TeamsPanel.tsx`): every team by status (filters) with its shift end / return time and group,
    and the roster explained for the manager (12 h / 12 h, groups A/B/C on a 48 h band with "now"). Contract:
    `Team.group / shiftStart / shiftEnd`, `CrisisMeta.mode / speed / roster` (also returned by the replay `meta`).
  - Copilot question routing shared by both modes (`copilot/answers.answer`, word-based: "150 clients" no longer
    triggers the 50 % what-if; the reinforcement answer follows the config basis — it said "clients" for incidents).
  - Removed the Streamlit app (`app/`, `app` extra): the React front-end is the only UI.
  - Known limits: the live lock is held while a refusal is priced (≤ 1 s re-plan; the LLM translation runs outside
    it); a team late on its estimated travel sits at the outage on the map until the field reports it on site.
- [x] Demo scenario CRISE_DEMO (2026-10-10, user: "starts simple, gets harder, more outages than teams, must fail the
      90 % so the alert shows"). `bench/make_demo_scenario.py` (seeded) builds 331 outages from real substations,
      durations and causes into `data/scenarios/scenarios.csv` (kept apart from the 100 historical crises:
      `list_scenarios`, loaders fall back to it). Ramp 1 outage / 30 min -> peak ~11 / 30 min, storm moving Gers ->
      Haute-Garonne -> Ariège. Engine replay: plans of 1, 1, 1, 5, 5, 2, 3, 10, 8, 9 teams at the start; the 48 h alert
      appears at 09h56 the next day (15 h in) and stays; final 410 520 vs reference 613 860 customer-h (-33 %).
      Default crisis of the API warm-up and of the front (VITE_CRISIS). Routes: the front never caches a straight
      fallback any more (asked again later); the server prefetches every proposed route of the warmed crisis into
      data/cache/routes.json at start-up (331/331 cached). Reinforcement popup shows one decimal rounded down.
- [ ] NEXT FEATURE (user idea, not started): accept a whole PLAN instead of route by route — the engine proposes up to 3
      alternative plans (or one when only one is sensible), each with its N×T, 90 %/48 h check and the main differences;
      the manager accepts one plan.
- [ ] Commit + push branch, PR (waiting for the user's go).
Front-end integration details: `docs/FRONT_INTEGRATION_PLAN.md`. API: `docs/API.md`. Pipeline: `docs/PIPELINE.md`.
