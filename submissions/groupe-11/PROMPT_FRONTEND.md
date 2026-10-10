# Frontend brief — keyboard-first review UI (`angular/`)

Full project context: [PROMPT.md](PROMPT.md). This file covers only the Angular app. The Python backend is built in parallel. Code against the **API contract** below, and don't change it without telling the backend team.

## Goal
Billing agents check, invoice after invoice, that a **scanned billing form** matches its **B2 text invoice file**. Today they do it by hand. The backend pre-computes 18 checks (C0–C17) per invoice. The UI lets an agent review the result and **validate or reject each invoice in a few seconds, using only the keyboard**.

The users are **non-technical French billing agents** who work fast, on a production line. The UI is entirely in **French**.

Constraints: hackathon (≤48h), runs locally, working demo over polish.

## Stack (already set up)
- Angular 22 in `angular/`: standalone components, signals, no NgModules. `provideHttpClient(withFetch())` and the router are already configured.
- Run `cd angular && npm install`, then `npm start` (http://localhost:4200). Tests use Vitest via `npm test`.
- `proxy.conf.json` forwards `/api` to FastAPI on port 8000. Always call the API with relative URLs (`/api/...`) so the proxy applies.

## Current state (connected to the backend)
- Routes: `''` → `agent/` (review screen), `/dashboard` → `dashboard/` (supervisor view, `GET /api/stats` through `services/stats.service.ts`).
- `models/invoice.model.ts` holds the contract types below (`FactureResume`, `FactureDetail`, `Check`, `Decision`).
- `services/invoice.service.ts` is the only place that talks to the invoice endpoints:
  - `GET /api/factures` on start, keeping only invoices with `ocr: true`, `traitee: false`, and `nb_ko > 0` or `nb_a_verifier > 0` (KO first, as sorted by the API). When none is left at load time, or once the agent has processed them all, the screen shows the waiting page "Aucune facture disponible" with an "Actualiser" button (there is no end-of-queue summary).
  - While some scans are not OCR'd yet (`ocr: false`), it polls `GET /api/factures` every 15 s and **appends** the newly analysed invoices to the end of the queue, without reloading the page or moving the agent off the current invoice. If the agent was waiting at the end of the queue, the new invoice is shown right away. Polling stops once every scan is analysed. The OCR progress is never shown to the agent.
  - `GET /api/factures/{id}` for the current invoice, and preloads the next one (JSON + image).
  - `POST /api/factures/{id}/decision` on validate/reject (`commentaire: ''`, `overrides: []` for now). It moves to the next invoice only after the `204`; on error it stays and shows a message.
- The agent screen shows the non-OK checks (KO, then À vérifier) with `attendu` vs `lu`, and draws every non-OK check's `boxes` on the scan, converted from image pixels to percentages of `image.largeur` / `image.hauteur`.
- Each card shows **what was read left, in neutral colour** (`lu`: "Image (lu par l'IA)", or "Fichier B2 (constaté)" for C0), and **what it is compared with right, in red** (amber for À vérifier; `attendu`: "Fichier B2 (facture)", or "Attendu (règle du formulaire)" for the form rules C1, C14–C17, "Attendu" for C0). See `comparison()` in `agent/agent.ts`.
- The OCR confidence (`confiance`, shown rounded down: 0.999 → 99 %) is displayed under the value read from the scan, whichever column it is in; the B2 file and form rules are not OCR'd.
- The characters that differ between the two values are highlighted like a `git diff` (`agent/diff.ts`, longest common subsequence): underlined on both sides (in each value's own colour). Nothing is highlighted when a value is missing ("non lu", "scan non traité (OCR)", "—", "aucun") or when the two values share less than 40 % of their characters. No diff on verdict checks (C0, C14, C16: "signature présente" / "signature absente"), where underlining the differing letters would suggest a misread. Signature crops (C14, C16) use a thin margin, since extract.py already widens those zones. When both values are plain integers, the B2 zero padding is dropped before display and diff (`000491917` → `491917`, as the backend checks already do; `trimLeadingZeros()`), so only real differences are highlighted. The highlight styles live in the global `src/styles.css` to stay under the component style budget.
- Shortcuts implemented so far: `V` validate, `R` reject (`services/shortcut.service.ts`).
- Each card shows **crops of the scan** around its boxes (`cropsFor()` in `agent/agent.ts`): touching boxes merged, some context kept, zoomed up to ×1.5 (tall zones shrunk to fit), at most 4 per card, drawn as CSS backgrounds of the already loaded scan (no extra request; styles in `src/styles.css`).
- List checks with `ecarts` show one red line per missing item ("Acte JVRP009 facturé dans le fichier B2, introuvable sur le bordereau"), then the two lists side by side as a **list diff** (`listDiffSegments()` in `agent/diff.ts`): an item present on one side only is underlined as a whole (a character diff would match `PH7` against `PH8`). Only the side the check verifies is marked (`LIST_DIFF_MARKS`): C7 / C9 the scan's items missing from the file, C10b the file's items missing from the scan, C11 both, so e.g. `GHS` (printed in zone 6) is not flagged by C9.
- Clicking a crop shows it large over the page (`openZoom()`; click or Échap closes it). The selected card's outline is drawn inside it (`outline-offset: -2px`): the cards list scrolls and would clip an outer outline.
- Crops include the printed label on the value's row (`contexte` from the API), e.g. "sous-total 4 … 50,48".
- Money cards show the difference in euros (`montantEcart()` in `agent/diff.ts`, e.g. "Écart : 0,01 €"). On C10 / C13, when C15 is OK (the scan's sub-totals add up to its printed total), a note says the scan is self-consistent, so the difference more likely comes from the B2 file.
- Clicking a card (or Enter on it; cards are focusable with Tab) selects it: the scan is centred on its boxes and the other boxes fade out (`select()` in `agent/agent.ts`).
- Badge colours: the difficulty badge is green / amber / red by level, and the À vérifier counter amber. Their rules need **three compound selectors** (`.control-panel .panel-header .anomaly-badge.x`): Angular adds one encapsulation attribute per compound, so a shorter selector loses against `app.css`'s red `.anomaly-badge`.
- Not done yet, compared with this brief: the full keyboard map below, check selection and focus ring, zoom, the reject comment field, overrides, and the queue counters for already decided invoices.
- Tests: `services/invoice.service.spec.ts` covers the API flow with `HttpTestingController` (queue filter, preload, POST then next, error keeps the invoice).
- No UI kit. Add `@angular/cdk` only when it's actually needed (for example `cdk/a11y` focus trapping for the reject dialog, or an overlay for the zoom).

## Screens
**Single review screen**, with a split view:
- **Left — the scan**, fitted to the height. Highlight the boxes of the selected check (`boxes`, in original image pixels; scale them to the displayed size). `Z` zooms onto those boxes, and `Z` or `Échap` zooms back out.
- **Right — the checks list**, in the order C0 to C17. Each row shows:
  - the status badge
  - the French label (`libelle`)
  - `attendu` (fichier) vs `lu` (scan), with the differing characters highlighted on KO
  - a **crop** of the scan around `boxes`, so the agent checks the pixels and not the OCR. Draw the crop yourself, with CSS `background-position`/`background-size` or a `<canvas>`; the backend does not generate crop images.
- **Top bar**:
  - the invoice id
  - the position in the queue (`12 / 55`)
  - counters for KO and À vérifier
- **Footer**: the keyboard shortcuts, always visible.

When the queue is finished, there is **no summary page**: the agent goes straight back to the waiting page ("Aucune facture disponible"), where newly analysed invoices show up on their own.

## Keyboard (no mouse needed, ever)
| Key | Action |
|---|---|
| `Entrée` | Validate the invoice and go to the next one |
| `R` | Reject: opens a comment field, `Entrée` saves the decision and moves on, `Échap` cancels |
| `J` / `↓`, `K` / `↑` | Next / previous check |
| `N` / `P` | Next / previous invoice |
| `Z` | Zoom onto the selected check's zone |
| `Espace` | Override the selected check (mark a KO / À vérifier as accepted by the agent) |
| `?` | Help overlay |

- Handle every shortcut in **one `@HostListener('document:keydown')` in a shortcuts service**. Ignore shortcuts while a text field has focus, except `Entrée` and `Échap`.
- On load, select the first non-OK check automatically.
- **Preload** the next invoice's JSON and image, so moving on feels instant.

## Visual rules
- Large type, with high contrast between the three statuses:
  - KO: red
  - À vérifier: orange/amber
  - OK: green, and visually quiet
- Never rely on colour alone: also show an icon or text for each status.
- A visible focus ring on the selected check.
- One screen and no scrolling of the page itself; only the checks list scrolls.

## API contract (shared with the backend — keep it identical)
All JSON. Field names are in French.

`GET /api/factures`: the queue, already sorted (KO first, then À vérifier, undecided first).
```json
[{ "id": "Facture1_01", "nb_ko": 0, "nb_a_verifier": 1, "traitee": false, "difficulte": 4, "niveau": "Facile" }]
```
- `difficulte` (0–100) + `niveau` (`Facile` … `Très difficile`) estimate review difficulty (see backend brief). `GET /api/factures/{id}` carries the same two fields. The agent screen shows them as a badge and offers a "difficulté max" slider (0–100) that filters the queue client-side; invoices above the max are masked with a count and a reset affordance, never silently dropped.
- `ocr` is `false` until `extract.py` has analysed the scan. Such an invoice has every scan check `A_VERIFIER` ("scan non traité (OCR)") and **must never be shown to the agent**.

`GET /api/factures/{id}`
```json
{
  "id": "Facture1_01",
  "image": { "url": "/api/images/Facture1_01.jpg", "largeur": 1190, "hauteur": 1684 },
  "checks": [
    {
      "code": "C2",
      "libelle": "N° FINESS = NumeroTiers",
      "statut": "OK",
      "attendu": "200200145",
      "lu": "200200145",
      "zones": [2],
      "boxes": [[470, 92, 665, 112]],
      "confiance": 0.99,
      "contexte": [[18, 95, 313, 108]],
      "ecarts": []
    }
  ],
  "traitee": false
}
```
- `ecarts` (list checks C7, C9, C10b, C11, only when KO): one entry per act / prestation found in a single document, `{code, sens: "absent_scan" | "absent_b2", message, boxes}`, e.g. `{"code": "JVRP009", "sens": "absent_scan", "message": "Acte JVRP009 facturé dans le fichier B2, introuvable sur le bordereau"}`. The UI shows one line per entry instead of making the agent compare two full lists. Empty otherwise. `boxes` is where the item is printed, only for `absent_b2` items (from the per-row `box` that extract.py now stores for zones 6, 7 and 10); a KO list check's own `boxes` are the union of its entries' boxes, so an item missing from the scan gets no crop and no highlight: pointing at the items that *are* printed would mislead the agent.
- `statut` is `OK`, `KO` or `A_VERIFIER`.
- `confiance` (0–1 or `null`) is the OCR confidence of the read value (min line score over the check's zones); show it as a percentage on the check card when present.
- `attendu` (from the B2 file) and `lu` (read on the scan) are display strings.
- `boxes` are `[x0, y0, x1, y1]` in **original image pixels**. They can be empty, for example when a value is missing from the scan.
- `traitee` is `true` once the invoice has been validated or rejected (its id is in `backend/traitees.txt`).

`POST /api/factures/{id}/decision`: the body is `{ "statut": "valide" | "rejete", "commentaire": "…", "overrides": ["C1"] }`, and the response is `204`. Only the invoice id is recorded (in `backend/traitees.txt`); the body is not kept.

`GET /api/images/{name}.jpg`: the raw scan.

The backend endpoints are live and the hard-coded mock has been removed: work against the real API (`cd backend && uv run uvicorn main:app --reload`). In unit tests, mock HTTP with `provideHttpClientTesting()`.

## Check labels (for reference — the backend sends `libelle`)
| Code | What is compared |
|---|---|
| C0 | B2 file is well formed. When it's KO (e.g. `Facture2_06`, whose columns are shifted), every other check comes back `A_VERIFIER`, so show C0 prominently at the top. |
| C1 | Cerfa number `12278*0…` |
| C2–C5 | FINESS, lot, invoice and insured numbers |
| C6 | GHS row and its GHS number |
| C7 | Zone 6 prestations exist in the file |
| C8 | GHS number of the type-3 acts |
| C9 | Zone 7 prestations exist in the file |
| C10 | Sous-total 1+2+3 and the type-3 acts on the form |
| C11 | Act codes / CCAM codes, in both directions |
| C12 | GHS number of the 4-S lines |
| C13 | Sous-total 4 |
| C14 | Practitioner signatures |
| C15 | MONTANT TOTAL = sous-total 1+2+3 + sous-total 4 |
| C16 | Establishment signature |
| C17 | Form code `S 3404` |

## Tests
Write one Vitest spec for the shortcuts service: key → action mapping, and keys being ignored while an input has focus. Skip snapshot tests.
