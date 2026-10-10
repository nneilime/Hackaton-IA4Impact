# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Hackathon project (Défi Enedis, La Mêlée, 9–10 Oct 2026): real-time decision support for dispatching field repair teams during a storm.
Two parts in one repo:

- **Python backend** (`src/dispatch/`, package `enedis-crisis-dispatch`): optimisation engine, simulator, LLM copilot, learning loop, FastAPI.
- **React front-end** (`frontend/`, "EnedisPO"): React 19 + TypeScript + Vite, MapLibre + deck.gl, zustand. Shown to a jury on a projector.

Core principle, enforced everywhere: **the engine decides and computes · the LLM only words/translates · the manager validates.** Never let the UI or the LLM produce decisions or numbers.

Read first when resuming work: `docs/DEV_LOG.md` (decisions taken, status), `frontend/HANDOFF.md` (front-end decisions, open items). Deeper references: `docs/PIPELINE.md` (engine → LLM → front-end), `docs/API.md`, `docs/FRONT_INTEGRATION_PLAN.md`, `docs/RO_ENGINE_BRIEF.md`, `docs/CURRENT_SETUP.md`.

## Commands

Backend (Python ≥ 3.11, from repo root):

```bash
pip install -e ".[all]"                    # extras: api, llm, bench, dev
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q          # global pytest plugins break without the env var
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_engine.py::test_name -q
ruff check src tests && ruff format src tests                 # line length 110
python -m uvicorn dispatch.api.app:app --app-dir src --port 8000 --reload --reload-dir src   # docs at /docs
python -m simulator --crisis CRISE_027 --speed 60             # live mode's field (separate process): alerts from now + team reports; --speed 1 = real time
python bench/run_benchmark.py --crises all --budget-ms 50     # see README for the other bench/ scripts
```

Don't let pip upgrade numpy (other packages pin numpy 2.1.0); use `--dry-run` first. If new routes 404 under `uvicorn --reload`, a stale process is running: restart without `--reload`.

Front-end (Node ≥ 20; on this machine Node comes from nvm: `source ~/.nvm/nvm.sh` first):

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, mock engine in the browser (default)
VITE_DATA_SOURCE=api VITE_API_URL=http://localhost:8000 npm run dev -- --port 5173 --strictPort   # real engine: opens in live mode
npm run build      # tsc type-check + vite build (this is the only "lint"/check; there are no front-end tests)
npm run generate   # force-regenerate public/mock/crise_027/scenario.json from data/raw/*.csv
```

`predev`/`prebuild` copy the MapLibre worker and regenerate the mock only if stale. Useful URL params: `?mode=replay` (« Revoir une crise passée », accelerated replay instead of live; `?crise=CRISE_051` picks it), `?equipes=50` (replay: keep 50 % of teams, stress test; with the API, a new share is computed cold in ~1 min), `?r90=30|45|54|null` (mock only, force the 90 % estimate display). Dev-only screenshot helpers: `window.__page('name')` → `.shots/` via the `/__shot` Vite middleware. Headless check without Chrome (this machine has Firefox only): `firefox --headless --no-remote --profile "$HOME/.cache/ffshot" --window-size=1600,900 --screenshot out.png 'http://localhost:5173/__frame?ms=12000&tab=Équipes'` — `/__frame` (dev only) shows the app in an iframe, optionally clicks a side-panel tab (`tab=`) and scrolls an element into view (`scroll=.roster`), and holds the page's load event for `ms` so the capture shows the rendered dashboard (`q=%3Fmode%3Dreplay` for the replay view; snap Firefox needs the profile under `$HOME`; the map stays blank headless, no WebGL).

## Architecture

### Engine (`src/dispatch/engine/`) — "RSLS"
Rolling-horizon Smith rule + Local Search. At every event: greedy list scheduling (priority = weighted customers / (travel + repair)) in `construct.py` → local search (relocate / swap / ruin & recreate) in `local_search.py`, orchestrated by `planner.py`; only the next job per team is committed. `evaluate.py` is the decoder: it enforces all hard rules (shift windows, no anticipation, no interruption, operator rules). `explain.py` + `counterfactual.py` produce `ExplanationFacts` and priced alternatives. `service.py` is the "90 % within 48 h" **check** (not part of the objective); `sim/whatif.py` computes reinforcement (+N teams per site) when it fails.

- Objective: minimise Σ customers × hours without power (customer-hours). The README's "maximiser" is a known typo.
- Shift roster (12 h on / 12 h off, groups A at H0, B at H0+2 h, C the relief at H0+12 h) is fixed once at initialisation (`engine/shifts.py`, `config roster`); the dashboard's Équipes tab explains it to the manager from `CrisisMeta.roster`.
- **Shared contract**: `engine/types.py` and `engine/modifiers.py` (operator-rule catalogue). Change them together.
- `engine/baselines.py` has `ReferencePolicy` = the front-end's "reference" strategy (first reported first, nearest team).

### Session, live mode, replay mode
- `session.py` `LiveSession`: one crisis managed step by step (accept / reject / confirm rule, what-if, service check, explanations, 3 best options, past-refusal hints). With `external_field=True` (live mode) it simulates nothing: arrivals and completions come in as field events (`report / arrived / repaired`); a repair that overruns its estimate keeps the team busy until the field says done.
- **Live mode** — the dashboard's default (`live/service.py` `LiveCrisis`, routes `api/live.py` under `/live`, config `live`). H0 = the moment the crisis is opened, on the real clock (`speed` > 1 only for demos). The world enters only through `POST /live/events` (incident_reported, team_on_site, repair_done, team_unavailable); a ticker thread re-plans once per tick when something changed or a planned departure / shift change is due; **nothing is dispatched until the manager validates** (`POST /live/plan/accept`); dispatches are published to the field (`GET /live/dispatches`). History snapshots (every `live.history_minutes` of crisis time + one after each decision) feed the timeline and the journal. The field is played by `simulator/`, a separate process that only talks HTTP (`python -m simulator`: a past crisis shifted to now + on-site / repair-done reports). Never put alert or completion simulation back into the backend.
- **Replay mode** — « Revoir une crise passée » (`adapters/timeline.py` `TimelineRunner`, routes `api/frontend.py` under `/crises/{id}`): the whole crisis replayed in 30-min steps of crisis time, one `Snapshot` per step, for `ours` and `reference`; untouched recommendations auto-executed; a checkpoint per step lets a new decision replay only from its step (~2.6 s). The default replay crisis (`timeline.default_crisis`, CRISE_027) is precomputed at startup.
- `adapters/contract.py` converts engine objects to the front-end contract (camelCase, ISO times with Paris offset) for both modes; `api/app.py` mounts everything (`/live`, `/crises/...`, `/routes`, `/learning/...`, and the older `/sessions/...` step-by-step routes used by tests only), with GZip (replay timelines are ~17 MB JSON).
- Copilot questions of both modes go through `copilot/answers.answer()` (intent routing on whole words, every figure from the engine, LLM only for free questions).

### LLM layer (`src/dispatch/copilot/`)
`client.py` calls an OpenAI-compatible endpoint: provider and models come from `config/default.yaml` → `llm` (currently Mistral, `MISTRAL_API_KEY`, with OpenRouter free models as fallback, `OPENROUTER_API_KEY`; keys in `.env`). Some docs still say OpenRouter-only; the config is authoritative. Everything must work with **no key**: templates for explanations, a rule parser for refusal reasons. LLM text is accepted only if it has ≤ 2 sentences and every number appears in the engine's facts; refusal → rule JSON always goes through `validator.py`, then the engine prices it before the manager confirms. Tests stub the LLM out (`tests/conftest.py`) — never make tests depend on the network.

### Learning loop (`src/dispatch/learning/`)
Decision log in SQLite (`data/decisions.sqlite`, gitignored, may contain simulated refusals flagged as such) → `review.py` turns repeated refusals into candidate rules → replay backtest → `registry.py` writes the versioned `config/constraint_registry.yaml`. All proposals, never silent.

### Front-end (`frontend/src/`)
- **Single swap point**: `data/source.ts` (`CrisisSource`, plus `mode` = `'live' | 'replay'`). `VITE_DATA_SOURCE=mock` (default) uses `data/mock/` (a deliberately naive greedy engine running in the browser on the generated scenario, replay only); `api` uses `data/live/liveSource.ts` (live: polls `/live/state` every second, clock = the backend's) or, with `?mode=replay`, `data/api/apiSource.ts`. Nothing else in the UI knows where data comes from. Optional `CrisisSource` methods (explain, refuse, rules, reinforcement, learning, `live`…) exist only with the API; the UI hides those features when undefined. In live mode the store's playback / reset / step actions are no-ops and `stepOf()` is always the last snapshot.
- Types: `data/contract.ts` (fields marked `ADDED` extend the original contract). Backend and front-end contracts must stay in sync (`adapters/contract.py` ↔ `contract.ts`).
- State: `state/store.ts` (zustand), `state/clock.ts` (playback loop + keyboard shortcuts, replay only).
- Main screen: `TopBar` (title per mode, live badge, mode switch) + `Rail` (clock, figures, 48 h target), `MapView` (+ `components/map/`), `SidePanel` with tabs Plan (`RecPanel`) / Équipes (`TeamsPanel`: teams by status + roster explained) / Copilote (`Copilot`) / Journal, `OverrideDrawer`, `Modals` (refusal, reinforcement, rules, expert review), `CrisisTimeline` (snapshots placed by their own time: regular in replay, irregular in live). `CopilotDock.tsx` and `Wordmark.tsx` are unused.
- Don't re-add `<StrictMode>` in `main.tsx`: it double-mounts the deck.gl overlay and breaks map interaction.

## Conventions

- Branches `feat/<workstream>-<topic>`, small PRs to `main`, pytest green before merging.
- **No CSV access outside `src/dispatch/data/loaders.py`.** No magic numbers outside `config/default.yaml` (weights, rules, solver budgets, LLM models). `data/raw/` holds the organisers' files and is never edited; the front-end mock generator reads it too.
- Front-end UI: French text with domain vocabulary (poste, équipe, clients coupés, réalimentation); colours/fonts/spacing only from `src/styles/tokens.css`; pills only for actions, square data containers, borders not shadows, transitions < 200 ms; Outfit (tabular figures) for figures and titles, Public Sans for everything else. Must work from ~1240×600 up to 1920×1080.
- Don't recreate the Enedis logo (see open item in `frontend/HANDOFF.md`).
- Decisions listed in `docs/DEV_LOG.md` §2 and `frontend/HANDOFF.md` ("Decisions already taken") should not be undone without asking.
