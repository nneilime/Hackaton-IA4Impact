# Handover — EnedisPO frontend

State on 2026-10-10. Read this first, then `README.md` (how to run, data layer, map details).

## What this is

The frontend of a crisis-dispatch decision tool built for the Enedis hackathon (La Mêlée 2026).
During a storm, it recommends which field team goes to which incident, explains each
recommendation, and lets the crisis manager accept or override it. The human always decides.
It is shown live to a jury on a 1920×1080 projector: polish on the main screen matters more
than breadth.

The optimisation engine (Python, another team) is **not connected yet**. Everything runs on a
mock engine in the browser (`src/data/mock/`), behind one swap point, `src/data/source.ts`.

## Run it

```bash
npm install        # Node ≥ 20 (here it was installed with nvm: source ~/.nvm/nvm.sh)
npm run dev        # http://localhost:5173 — full screen at 1920×1080 for the real layout
npm run build      # type-check + production build
```

Useful URLs: `?equipes=50` (half the teams → 90 % estimate above 48 h, FIRE flag),
`?r90=30|45|54|null` (force the 90 % estimate to check its display states).
Keyboard: Space play/pause, ← → step 30 min, ↑ ↓ move the focus in the queue,
Entrée accept, C change team, Échap close panels.

## Screen, top to bottom

- **Header** (`TopBar.tsx`, `Wordmark.tsx`): EnedisPO wordmark + "Maquette hackathon" tag, crisis
  clock, three grouped figures, "Demander au copilote", and on the right the dominant
  **90 % block** (estimate, date, gauge vs the 48 h target, margin, FIRE flag above 48 h).
- **Map** (`MapView.tsx`, `map/territory.ts`, `map/labels.ts`): OpenFreeMap "liberty" basemap,
  the three departments highlighted, incidents (clustered per commune at low zoom), team sites
  as squares with available counts, moving teams as diamonds, recommendation routes (focused one
  at full strength, accepted ones in the blue/green/teal/yellow segmented style).
- **Recommendations** (`RecPanel.tsx`): one recommendation in focus with the only action buttons,
  the queue underneath as one-line rows. "Changer d'équipe" opens `OverrideDrawer.tsx`.
  The copilot (`CopilotDock.tsx`, `Copilot.tsx`) slides over this column.
- **Crisis timeline** (`CrisisTimeline.tsx`): past solid / projection light-dashed, incident and
  team-capacity strips, milestones on the axis, draggable cursor, one-line summary, playback.

Screenshots of the current state: `docs/screenshots/` (`header.png`, `timeline-*.png`,
`after-*.png`).

## Code map

| Area | Files |
|---|---|
| Engine ↔ UI contract | `src/data/contract.ts` (fields marked `ADDED` are ours) |
| Swap point mock / API | `src/data/source.ts`, `src/data/api/apiSource.ts` (routes proposed, never run against a live service) |
| Mock engine | `src/data/mock/engine.ts` (greedy, 30-min steps, 12 h shift / 11 h rest), `mockSource.ts` |
| Mock data | `scripts/generate-mock.ts` → `public/mock/crise_027/scenario.json` (from `data/*.csv`) |
| Geography | `scripts/build-geo.mjs` → `public/geo/territory.json` (france-geojson, committed) |
| State | `src/state/store.ts` (zustand: clock, focus, decisions, copilot), `src/state/clock.ts` (playback + keys) |
| Explanations / copilot | `src/copilot/explain.ts`, `src/copilot/answers.ts` — templates, to be replaced by an LLM |
| Design tokens | `src/styles/tokens.css` (colours, 5 type sizes, spacing scale); `src/styles/app.css` |
| Dev-only capture | `src/dev/capture.ts` (`window.__page(name)`, `window.__element(sel, name)` → `.shots/`) |

## Decisions already taken (don't undo without asking)

- Interface text in French, domain vocabulary (poste, équipe, clients coupés, réalimentation).
- Enedis colours from `tokens.css` only; contrast-adjusted text variants (`--green-text`,
  `--waiting-text`, `--blue-muted`). Outfit (tabular figures) for figures and titles, Public Sans
  for everything else. Poppins was dropped: no tabular figures.
- The 90 % estimate covers **customers cut so far** following the current plan; the mock takes
  restoration times from its own simulation. The timeline milestones use the same basis.
- Alternative cost (`deltaScore`) is a first-order estimate; the full re-simulation was too noisy
  with the greedy mock to show.
- The reference strategy is computed (contract field `scoreBaseline`) but **not displayed** in
  the bottom band (kept for the pitch slides). The reference map view still exists in code but
  nothing switches to it now.
- Pills only for actions, square data containers, borders not shadows, transitions < 200 ms.

## Open items

1. **Header logo — blocked.** The latest brief asks to show the official Enedis logo from
   `src/assets/enedis-logo.svg`, untouched, followed by a green "PO" matching its letters, and to
   remove the "Maquette hackathon" tag. The file was never provided, so this was **not done**
   (do not recreate the logo). Once the file exists: compare Outfit / Sora / Lexend for "PO",
   sample the green from the SVG, match cap height and letter gap at 200 %.
2. Wire the real engine: implement / adjust `src/data/api/apiSource.ts`, set `VITE_DATA_SOURCE=api`.
3. Replace the copilot and "Pourquoi ?" templates with real LLM calls (single functions).
4. Basemap and relief need internet (OpenFreeMap, AWS terrain tiles). Fallback style noted in
   `territory.ts` (CARTO Voyager, untested).
5. Wordmark green "PO" on the pale background is low contrast (~1.8:1); fine at 32 px, check on
   the projector.

## Data

`data/` holds the hackathon CSVs (substations, incidents of 100 crises, sites). They are needed
only to regenerate the mock (`npm run generate`); the generated scenario is committed. The
hackathon brief documents (`Hackathon_2026_*.docx/.pptx`) are kept out of git.
