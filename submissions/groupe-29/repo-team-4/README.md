# Contrôle des factures — CERFA 12278 vs flux B2

Health-insurance billing control for private hospitals. Each invoice exists twice:

- the **facture**: a fixed-width **B2** text file (`Factures txt/*.txt`) sent electronically;
- the **bordereau**: the scanned paper form **CERFA 12278** (`Bordereaux jpg/*.jpg`) that should say the same thing.

The project reads the scan with an OCR model, extracts the fields of both documents, runs the controls that compare
them (C1–C22 from the specification, plus extra fraud signals), and gives every pair an automatic guess, **CORRECT** or
**ISSUES**. Agents then review each pair as a ticket in a web app and give the final word; managers follow statistics
per clinic and region, answer agents' questions and report clinics to the fraud-control service.

The rules (the 15 zones of the form, the B2 record layout, the 22 controls) are in **[CONTEXT.md](CONTEXT.md)**: read it
first.

---

## Quick start

Requirements: Python ≥ 3.10 with [uv](https://docs.astral.sh/uv/), Node 22 with pnpm, and the data folder
`~/Downloads/General-main/` (with `Factures txt/` and `Bordereaux jpg/`).

```sh
./dev.sh
```

On the first run it creates `.venv`, installs the web dependencies, builds `invoices.db` from the documents and creates
the demo accounts. Then it starts:

| | URL |
|---|---|
| Web app | http://localhost:8443 |
| API (and its interactive docs) | http://localhost:8000/docs |

Sign in with one of the placeholder accounts (the login page has one-click buttons for them):

| Account | Role | Sees |
|---|---|---|
| `agent` / `agent` | agent (`reviewer`) | the ticket queue and the review screen |
| `admin` / `admin` | manager (`admin`) | everything: dashboard, clinics, map, regional funds, escalated tickets |

Security is deliberately minimal (unsalted hashes, token in image URLs, CORS open): **this project only runs
locally**.

To start over: `./reset.sh` (see [Resetting](#resetting)).

---

## How it works

```
 Bordereaux jpg/*.jpg ──ocr.py──▶ factures/<name>/result.json ─┐
        │                          (LightOnOCR-3, HF Space)     │
        └──check_signatures.py --ocr──▶ factures/<name>/signature_boxes.json
                                                                │
 Factures txt/*.txt ────────────────────────────────────────────┤
                                                                ▼
                                    ingest.py ──▶ pipeline (flow of steps) ──▶ invoices.db (SQLite)
                                                                                  │
                                                       api.py (FastAPI :8000) ◀───┘
                                                                ▲
                                                 web/ (React, Vite :8443, /api proxy)
```

### 1. OCR of the scans — `ocr.py`

Sends each JPG to the **LightOnOCR-3** Hugging Face Space (grounding mode) and writes, per image, a folder
`factures/<name>/` with `result.json` (everything returned), `blocks.json` (layout blocks with their bounding boxes),
`raw.txt`, `result.md` and `annotated.jpg`.

```sh
python ocr.py ~/Downloads/General-main/"Bordereaux jpg" --out factures              # new images only
python ocr.py ~/Downloads/General-main/"Bordereaux jpg" --out factures --redo-truncated
```

- The output budget is `--max-tokens` (default 12,288, the Space's maximum). A run that uses it all was cut off before
  the end of the page (the totals, the CERFA code...): `--redo-truncated` redoes those. The first run used 6,144 and
  truncated 24 of 55 forms; all 55 are now complete.
- An `HF_TOKEN` in `.env` is used if present.

### 2. The B2 file — `pipeline/b2.py`, `parse_factures_txt.py`

Slices the fixed-width records strictly by position (CONTEXT.md §2.3): tiers, lot, insured, invoice number, acts of
types 3 and 4 with their GH numbers and CCAM codes, totals, plus the clinic name, the file date and the fund code. The
output is the JSON of `parse_factures_txt.py` (which uses the same code) with `Lignes`, the records in file order, used
to tie each type-4 act to its 4-M CCAM complement.

```sh
python parse_factures_txt.py ~/Downloads/General-main/"Factures txt" -o factures_txt_json
```

### 3. The pipeline — `pipeline/`

A **flow** is a class listing **steps**; registering it makes it available by name to the CLI and the API.

```python
@register_flow
class FactureBordereauFlow(Flow):          # pipeline/flows.py
    name = "facture_bordereau"
    steps = [NormalizeB2Lines(), FilterB2Records(), ParseB2(), CheckB2Layout(), CheckFacture(),
             CleanupOcrBlocks(), FilterOcrBlocks(), ExtractBordereauFields(), ExtractBordereauTables(),
             CheckSignatureBoxes(), CheckOcrComplete(), CheckBordereauSums(), CompareDocuments(), IdentifyClinic()]
```

Every step subclasses `Cleanup`, `Filter`, `Transform` or `Validate` (`pipeline/core.py`), works on a shared `Context`
(the two inputs, `assets` such as the scan path, a `record` it builds, and `issues` it reports) and can raise
info / warning / error issues. A crashing step stops the flow and is recorded.

| Module | Role |
|---|---|
| `core.py` | `Step`, `Flow`, `Context`, flow registry |
| `inputs.py` | loads a facture (B2 `.txt`, its lines, or `parse_factures_txt.py` JSON) and a bordereau (OCR `result.json`) |
| `b2.py` | B2 parser (shared with `parse_factures_txt.py`) |
| `bordereau.py` | reads the OCR output: text blocks and HTML tables, amounts, labelled fields |
| `signatures.py` | zones 9–11 on the scan: finds the 8 signature boxes, measures their ink, reads what they print |
| `steps.py` | the steps of the flow |
| `compare.py` | the controls and the automatic verdict |
| `geo.py` | department → region, fund code → fund name, city coordinates |
| `store.py`, `schema.sql` | SQLite storage, migrations |
| `review.py` | users, sessions, ticket workflow |
| `stats.py` | figures for the manager screens |

**Reading the form.** The OCR output is not a clean form: values sit in the same block as their label, in a table row,
or in a separate block next to or under it; table cells shift or merge (`GHS 9603`, `9606K`); neighbouring columns
bleed into amounts (`sous-total 4 1 50,48`). `bordereau.py` therefore looks a field up three ways (same block → same
table row → nearest block on the same line or just below) and reads table rows from the content of their cells (the
prestation code, the dates, the GHS number) rather than from their column index. Every value keeps its provenance (raw
text, strategy, bounding box), which the web app uses to highlight it on the scan.

**Signatures (zones 9–11).** The OCR does not see signatures. `signatures.py` finds the box grid from the scan's ruling
lines (a regular 8-box grid is fitted, so a faint line does not shift it), decides "signed / empty" from the ink inside
each box, and reads the stamped boxes (executant, name, total) with a dedicated OCR pass per box
(`check_signatures.py --ocr`, cached in `factures/<name>/signature_boxes.json`). Each box is tied to the zone-10 acts of
its executant, and its printed total is checked against their fees.

### 4. The controls and the verdict — `pipeline/compare.py`

Each control returns **PASS**, **FAIL** or **UNVERIFIABLE** (a side is missing, usually because the OCR did not read
it) with a **reference** value and the value **read**, each tagged with its source: the B2 file, the form, a CERFA rule
(C1 `12278*0x`, C22 `S3404`...), a calculation on the form (C20) or the scan analysis (C18, X3). Each control also has a
risk: **fraud** (money or identity moved), **error** (clerical / coding) or **compliance** (formalities).

| Codes | What |
|---|---|
| C1, C22 | the form is a genuine CERFA 12278 / S3404 |
| C2–C5 | FINESS, lot, invoice number, insured number match the B2 file |
| C6–C13 | prestations (zones 6–8): GHS, GH numbers, every billed prestation on both sides, sub-total 1+2+3 |
| C14–C19 | fees (zones 9–12): NGAP / CCAM acts on both sides, GH numbers, sub-total 4, practitioners' signatures |
| C20, C21 | the form's total adds up; the director signed |
| X1 | the B2 file's layout is consistent (tiers on every line, no shifted fields) |
| X2 | no act billed more often in the file than shown on the form |
| X3 | each signature box's printed total equals its executant's fees |

- A failure whose two values differ only by characters the OCR often confuses (`8/B`, `0/O`, `1/I`...) is flagged
  *OCR suspect*, and codes that match only after that correction pass with a note (`PHB` read for `PH8`).
- **Verdict:** **CORRECT** only if nothing failed and every non-visual control could be verified; otherwise **ISSUES**.
  C18, C21 and X3 do not block a CORRECT on their own: the reviewer looks at the scan anyway.
- **Risk score:** orders the review queue; failed fraud-risk controls weigh most.

On the 55 sample pairs: 46 ISSUES, 9 CORRECT. The dataset is seeded with anomalies (wrong CERFA codes, totals off by a
cent, swapped act codes, a shifted B2 file, missing signatures...), which is why so many fail.

### 5. The database — `invoices.db`

One row per pair in `pairs`; the rest hangs off it. Amounts are integer cents; `NULL` means unknown, never zero.

| Tables | Content |
|---|---|
| `factures`, `facture_lines` | the B2 side |
| `bordereaux`, `bordereau_lines`, `signature_boxes` | the form side (with each field's provenance) |
| `checks`, `issues` | the controls and what the steps reported |
| `clinics`, `clinic_reports` | establishments (created from the documents, editable) and fraud reports |
| `users`, `sessions` | accounts and web logins |
| `tickets`, `ticket_events`, `check_reviews` | the review workflow and its history |

Re-ingesting a pair updates it in place: its ticket and history stay, a change of automatic verdict is logged. A
database created by an older version is migrated automatically (`store.create_schema`, run by `ingest.py`, the API and
`users.py`).

### 6. The review workflow — `pipeline/review.py`

```
open ──request / claim next──▶ assigned ──resolve──▶ resolved
  ▲                              │   │                  │
  └──────── release ─────────────┘   └─ escalate ─▶ open, reserved to managers
  └──────────────────── reopen (manager) ───────────────┘
```

- An agent requests a ticket (or "the next one", highest risk first) and gets it at once, up to 5 at a time
  (`REVIEW_MAX_ACTIVE`).
- The final word is **CORRECT** (`none` or `ocr_error`) or **ISSUES** (`billing_error` or `suspected_fraud`); a comment
  is required when it contradicts the automatic verdict. The agent can also confirm or dismiss each control.
- "Demander à un manager" sends the ticket back to the queue, reserved to managers, with the agent's question.
- Managers can assign tickets, reopen resolved ones and deactivate accounts (their tickets return to the queue).

### 7. The API — `api.py`

FastAPI on port 8000; interactive docs at http://localhost:8000/docs. Authenticate with
`Authorization: Bearer <token>`:

```sh
TOKEN=$(curl -s -X POST localhost:8000/auth/login -H 'content-type: application/json' \
  -d '{"username":"admin","password":"admin"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -s localhost:8000/me -H "Authorization: Bearer $TOKEN"
```

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/login`, `POST /auth/logout`, `GET /me` |
| Tickets | `GET /tickets`, `POST /tickets/claim-next`, `GET /tickets/{id}`, `POST /tickets/{id}/request` · `release` · `escalate` · `resolve` · `assign` · `reopen`, `PUT /tickets/{id}/checks/{code}` |
| Pairs | `GET /pairs`, `GET /pairs/{id}`, `GET /pairs/by-name/{name}`, `GET /pairs/{id}/documents/{facture,ocr,image}`, `POST /pairs` (run the flow on two posted documents), `DELETE /pairs/{id}` |
| Managers | `GET /stats/overview`, `GET /clinics`, `GET /clinics/{id}`, `GET /clinics/{id}/invoices`, `PATCH /clinics/{id}`, `POST /clinics/{id}/reports`, `GET /reports`, `GET/POST /users`, `PATCH /users/{id}` |

The scan endpoint also accepts `?token=` because an `<img>` cannot send headers.

### 8. The web app — `web/`

React 19 + Vite + Tailwind 4 (originally a Figma Make design). Vite proxies `/api` to the backend
(`vite.config.ts`, override the target with `API_URL`).

| Page | Who | Content |
|---|---|---|
| Comparaison | everyone | queue, then the review screen: controls (value read / reference and their sources), the scan zoomed onto the checked area, the OCR text, the B2 file, the ticket history, the decision buttons |
| Tableau de bord | managers | KPIs, agents' questions, most frequent anomalies, clinics |
| Cliniques | managers | a clinic's invoices and figures, "Signaler" (fraud report), "Gérer" (correct its details) |
| Carte, Caisses régionales | managers | non-compliance by region and fund |

| File | Role |
|---|---|
| `src/api/client.ts`, `types.ts` | typed API client and the backend's shapes |
| `src/auth.tsx` | session handling (token in localStorage) |
| `src/components/ComparePage.tsx`, `DocumentPanel.tsx` | queue, review screen, scan viewer |
| `src/lib/checks.ts` | French labels of the controls and where to highlight them on the scan |

---

## Working on the project

### Day-to-day commands

```sh
./dev.sh                                       # run everything
./reset.sh                                     # reset the review workflow (see below)
./add_bills.sh                                 # run the whole pipeline on new bills (see below)

# re-run the pipeline after changing it (tickets and history are kept)
.venv/bin/python ingest.py ~/Downloads/General-main/"Factures txt" factures --images ~/Downloads/General-main/"Bordereaux jpg"

# accounts
.venv/bin/python users.py list
.venv/bin/python users.py add alice --password secret [--admin]
.venv/bin/python users.py password alice newpass
.venv/bin/python users.py demo                 # recreate agent/agent and admin/admin

# signature boxes: report per scan; --ocr reads the stamped boxes (HF Space) and caches the result
.venv/bin/python check_signatures.py ~/Downloads/General-main/"Bordereaux jpg" factures [--ocr]

# web
cd web && npx tsc --noEmit -p . && npx vite build
```

Run the API alone with `.venv/bin/uvicorn api:app --reload --port 8000`. `INVOICES_DB` selects another database file:
test on a copy (`cp invoices.db /tmp/test.db; INVOICES_DB=/tmp/test.db ...`) to keep your tickets.

### Adding new bills

Put the B2 file and its scan in the data folders under the same name (`Factures txt/Facture4_01.txt` and
`Bordereaux jpg/Facture4_01.jpg`), then:

```sh
./add_bills.sh -n        # list the bills not in the database yet
./add_bills.sh           # OCR their scans, read their signature boxes, ingest them
./add_bills.sh NAME ...  # process given bills (an existing pair is refreshed, its ticket kept)
```

Only the new pairs are processed; each gets its automatic verdict and an open ticket in the agents' queue (a new FINESS
creates its clinic). OCR results and signature-box readings already on disk are reused, so the script can simply be
run again after a failure (an OCR run cut off at the token limit is reported; retry it with
`python ocr.py ... --redo-truncated --only NAME`). A B2 file without its scan is skipped and reported.

### Resetting

| Command | Effect |
|---|---|
| `./reset.sh` | every ticket back to open and untreated; deletes decisions, check reviews, manager requests, fraud reports and ticket history. Keeps documents, checks, clinics (and their corrections), accounts |
| `./reset.sh --sessions` | same, and signs everyone out |
| `./reset.sh --full` | deletes the database and rebuilds it from the documents with the demo accounts |

Add `-y` to skip the confirmation. Each run first saves `invoices.db.bak` (`mv invoices.db.bak invoices.db` to undo).

### Adding a control

1. Write a function in `pipeline/compare.py` and register it:
   ```python
   @check("X4", "What it checks", "amounts", "fraud", expected_from="b2", found_from="form")
   def _x4(s: Sides) -> tuple:
       ...
       return FAIL, expected_value, found_value, "explication en français"   # or PASS / UNVERIFIABLE
   ```
   `Sides` gives the facture record (`s.f`), the bordereau record (`s.b`), `s.zone(n)` for the form's lines and
   `s.file_main("3"|"4")` for the B2 acts. Details are shown as they are to the agents: write them in French.
2. Describe it for the web app in `web/src/lib/checks.ts` (`CHECK_INFO`: field label, zone, where to highlight it).
3. Re-ingest.

### Adding a step or a flow

Subclass `Cleanup` / `Filter` / `Transform` / `Validate` in `pipeline/steps.py`, implement `run(ctx)`, and add an
instance to a flow's `steps` in `pipeline/flows.py`. A new flow is a new `@register_flow` class with its own `name`;
pass `--flow <name>` to `ingest.py` or `"flow"` to `POST /pairs`.

### Changing the database

Edit `pipeline/schema.sql`. A new **table** is created on existing databases automatically. A new **column** on an
existing table must also be listed in `ADDED_COLUMNS` in `pipeline/store.py`, so older databases get it.

### Data and generated files

| Path | In git | What |
|---|---|---|
| `factures/<name>/` | yes | OCR outputs (`result.json`, `blocks.json`...) and the signature-box cache |
| `invoices.db`, `invoices.db.bak` | no | the database |
| `.venv/`, `web/node_modules/`, `web/dist/` | no | environments and builds |
| `~/Downloads/General-main/` | no | the source documents (B2 files, scans, the controls specification) |

---

## Known limitations

- **OCR misreads remain.** Some table rows lose or shift cells (e.g. the last row of zone 10 attributed to the
  previous executant), a few tables come back empty (Facture3_05, 3_11, 3_15), some sub-totals are not read. These
  surface as UNVERIFIABLE controls, *OCR suspect* flags or warnings rather than silent errors: the agent decides on
  the scan.
- **The director's signature (zone 14)** is only detected from a "signé numériquement" mention; otherwise it stays to
  be checked on the image.
- **Clinic details** come from the documents: the Nantes clinic's name reads "E C H O PAV MONTFORT" from the B2 file
  (fix it with "Gérer"), and only a few cities have coordinates (others are placed in their region).
- **Facture2_06's B2 file is shifted** (an extra space after the tiers number): its file values are meaningless, which
  X1 reports; amounts shown for it come from the form.
