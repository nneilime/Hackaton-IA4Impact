# Backend brief — OCR + checks API (`backend/`)

Full project context: [PROMPT.md](PROMPT.md). This file covers only the Python backend. The Angular frontend is built in parallel against the **API contract** below. Don't change the contract without telling the frontend team.

## Goal
Billing agents compare a **scanned billing form** (cerfa n° 12278*01, form S 3404) against the **B2 text invoice file** for the same invoice. The backend must:
1. Read every scan once with local OCR, as a batch job.
2. Parse the B2 file.
3. Run checks C1–C17.
4. Serve the results, plus the scan images, to the Angular review UI.
5. Record the agent's decisions.

Constraints: hackathon (≤48h), runs locally, **no data leaves the machine** (health data), working demo over polish.

## Stack (already set up)
- Python 3.13 managed by `uv`: run `cd backend && uv sync`, then `uv run uvicorn main:app --reload` (port 8000).
- FastAPI and RapidOCR + OpenVINO (PP-OCRv6 medium, French; CPU or Intel iGPU). RapidOCR brings OpenCV (`opencv-python-headless`). **Do not add another opencv package**: two packages fight over `cv2`.
- `main.py` currently only has `GET /api/health`.

## Inputs (repo root)
- `receipts/FactureX_NN.txt`: one invoice per file, fixed-width B2 records.
- `images/FactureX_NN.jpg`: the matching scan. Files are paired by basename. 55 pairs: Facture1 ×20, Facture2 ×20, Facture3 ×15.
  - Scans are **not pixel-identical across sets**. Facture1 and Facture2 are about 1190×1684 px, Facture3 is 1684×2382 px with a slightly different rendering.
  - Amounts appear as `,` or `.`, sometimes without trailing zeros (`398,3`, `448.78`).
  - Facture3's establishment signature is a digital stamp that sits partly outside its box.
- There is no ground truth. The set probably contains injected discrepancies.

## B2 text file — what to parse
The first character of each line is the record type. Positions are **1-based and inclusive**. Numeric fields are zero-padded on the left, alphanumeric fields are space-padded on the right, and **the last 2 digits of an amount are cents**.

| Type | Meaning | Sub-type rule |
|---|---|---|
| 0 | File header | |
| 1 | Batch start | |
| 2 | Invoice start | `2-S` if pos 39 = `S` |
| 3 | Hospital services | `3-S` if pos 39 = `S`; `3-H` if pos 36 = `H`; otherwise a base line (new act) |
| 4 | Medical acts | `4-S` / `4-M` / `4-B` if pos 36 = `S`/`M`/`B`; otherwise a base line (new act) |
| 5 | Invoice end | |
| 6 | Batch end | |

| Field | Record | Pos | Notes |
|---|---|---|---|
| NumeroTiers | 1 | 2–10 | FINESS number |
| NumeroLot | 1 | 20–22 | |
| NumeroAssure | 2 | 12–24 | 13 chars |
| NumeroFacture | 2 | 30–38 | |
| Acte | 3 (base) | 56–60 | code, trim spaces (e.g. `GHS`, `PH8`, `EMI`) |
| Acte | 4 (base) | 76–80 | code (e.g. `K`, `ADC`, `B`) |
| NumeroGH | 3 (base) | 110–113 | GHS number |
| NumeroGH | 4-S | 120–123 | |
| CodeCCAM | 4-M | 43–55 | 7 useful chars, left-aligned |
| TotalPrestations | 5 | 42–49 | amount (6+2) |
| TotalHonoraires | 5 | 58–65 | amount (6+2) |

Verified on `Facture1_01`: Tiers `200200145`, Lot `574`, Assuré `2520299007001`, Facture `260800001`, TotalPrestations `818,97`, TotalHonoraires `28,80`, all matching the scan.

### The B2 parser already exists — `backend/deserialization/` (by RaphxelS)
**Reuse it, and do not write another one.**
- **`parse_b2.py`** implements the table above:
  - `parse_file(path) -> dict`, `parse_text(content, source_name) -> dict`, `parse_to_json(path) -> str`.
  - A CLI: `python3 backend/deserialization/parse_b2.py --input receipts --output parsed_json`.
- Output shape (`b2.schema.json`):
  ```
  { source_file, header, errors[{line, message}],
    lots[{ numero_tiers, numero_lot,
           factures[{ numero_assure, numero_facture, complements_2S[],
                      prestations_hospitalieres[{ acte, numero_gh, details[{subtype}] }],   # 3-S / 3-H nested under their base line
                      actes[{ acte, details[{subtype, numero_gh?, code_ccam?}] }],          # 4-S / 4-M / 4-B nested under their base line
                      total_prestations, total_honoraires }] }] }
  ```
  - Strings are stripped, and empty strings become `null`.
  - **Amounts are float euros** (`818.97`). Convert them with `round(x * 100)` before any comparison, and never compare floats directly.
  - Leading zeros are kept (`numero_facture: "000491901"`), so strip them only when comparing.
  - The 4-S `numero_gh` (for C12) and the 4-M `code_ccam` (for C11) sit in `actes[i].details`. This nesting gives C11 its "Acte **or** its CCAM code" pairing for free.
- **`b2.schema.json` is the contract** for both sides: the parser output and the OCR output, with `source_file: "FactureX_NN.jpg"`, **must both validate against it**. All 55 parser outputs already do.
  - Validate the OCR output with `jsonschema` (`uv add jsonschema`; use `Draft202012Validator`) in `extract.py` and in the self-test.
  - The schema does not forbid extra keys, so the `scan` object described below still validates.
  - The OCR fills the same fields wherever both sides have them. The mapping is:
  - zone 2 → `numero_tiers`
  - zone 3 → `numero_lot`
  - zone 4 → `numero_facture`
  - zone 5 → `numero_assure`
  - zones 6 and 7 → `prestations_hospitalieres`
  - zone 10 codes of ≤4 characters → `actes[].acte`; 7-character codes → `actes[].details[{subtype: "4-M", code_ccam}]`
  - zone 8 → `total_prestations`
  - zone 12 → `total_honoraires`
  - Low-confidence fields go into `errors`.

  The scan also has **fields the B2 has no slot for**, and they go in an extra top-level `scan` object, outside the schema:
  - zone 1 cerfa number
  - zone 6 billed amounts
  - zone 9 executors
  - zone 11 signature boxes
  - zone 13 total
  - zone 14 signature
  - zone 15 form code
  - plus `boxes` (`{zone: [[x0, y0, x1, y1], …]}`) and `scores`
- `test_parse_b2.py` is an assert-based self-test: it lives in `backend/devtools/`: run `uv run python devtools/test_parse_b2.py` from `backend/`. With a file argument, it pretty-prints that file's parse instead.
- **Importing it from `backend/`**: the parser is plain stdlib with no dependencies. it is a package inside `backend/`: `from deserialization.parse_b2 import parse_file`.

### `Facture2_06.txt` is malformed (detected by the parser)
From line 2 onwards, every line has **an extra space at position 12**, so every field is shifted one column to the right. This is probably a deliberately injected anomaly. **Do not fix the data, and do not auto-correct the shift**: the agent must see that the file is broken.
- `parse_file` checks the first data position of each record type: type 1 at pos 17, types 2–5 at pos 12, type 6 at pos 11. If that position is blank, it adds a `"column shift: …"` entry to `errors`. This flags all 44 lines of `Facture2_06` and nothing in the other 54 files.
- In `checks.py`: **C0 = KO** whenever `errors` is not empty (`"Fichier B2 mal formé (ligne N : décalage de colonnes)"`), and every other check becomes `A_VERIFIER`, because the parsed values are garbage.

## Scan zones to extract (diagram on page 1 of the rules PDF)
1. Cerfa number (top left, e.g. `12278*01`)
2. FINESS number of the establishment
3. N° LOT
4. N° FACTURE
5. Patient's n° d'immatriculation (first 13 characters only)
6. "Frais de structure et de soins": `prestation` + `n° GHS` + `montant facturé` for each row (tables (1) and (2))
7. "Produits LPP / médicaments": `prestation` + `n° GHS` for each row
8. Sous-total 1+2+3
9. Honoraires: `n° d'identification de l'exécutant` for each row
10. Honoraires: `code acte ou lettre-clé` for each row
11. Practitioner signature boxes 1–8: which boxes contain a signature
12. Sous-total 4
13. MONTANT TOTAL
14. Establishment director's signature: present or not
15. Form code bottom right (e.g. `S 3404`)

## Checks (each one returns `OK` / `KO` / `A_VERIFIER` plus the two values compared)
- **C0** The B2 file is structurally valid: `parse_file(...)["errors"]` is empty (see the `Facture2_06` section above). When C0 is KO, every other check is `A_VERIFIER`.
- **C1** Zone 1 matches `12278[*=]?0` (spaces ignored). The number is identical on every form and the OCR often drops the tiny `*` or reads it as `=` (RapidOCR does on every Facture1 scan), so a `*`, a `=`, a space or nothing is OK. KO only when the digits differ.
- **C2** Zone 2 = NumeroTiers. **C3** Zone 3 = NumeroLot. **C4** Zone 4 = NumeroFacture. **C5** Zone 5 (13 chars) = NumeroAssure.
- **C6** Zone 6 contains a `GHS` row with a GHS number, and that number = NumeroGH of the type-3 `GHS` act.
- **C7** Every zone 6 row that has a billed amount appears among the type-3 Actes.
- **C8** Every type-3 act **other than the GHS line** has NumeroGH = the GHS number from zone 6 (rule 3.3, "autres que GHS"); the GHS line itself is C6, so one wrong GHS number is not counted twice. Both sides use the same shape and list **only the prestations whose number is wrong** (`PH8 9606` vs `PH8 9616`, not the correct EMI next to it), so the card shows what is in error and the UI diff underlines the wrong digit; C12 does the same for the 4-S lines, labelled with the act as printed (`JCPD001 4158` vs `JCPD001 4159`); with no other prestation, C8 is OK ("aucune autre prestation"). This covers the duplicated first bullet of rules section 3.4.
- **Stats** (`stats.py`): an invoice whose C0 is KO is counted once, under C0. Its other checks are A_VERIFIER only because the B2 values are shifted (not evaluated), so they are left out of the per-check breakdown, the categories and the fraud score; the scan's printed total still counts towards the amount at risk.
- **Precise boxes**: a check can return `{"boxes": …}` as a 4th value; when it is KO they replace its zones' boxes. C6 points at the GHS row only, C8 / C12 at the GHS row plus the rows of the wrong prestations / acts (`item_boxes`, from the per-row `box` of zones 6, 7, 10), instead of whole columns.
- **Boxes**: each check gets the OCR boxes of its zones; zone 6 billed amounts are filed under `6m` and only C7 shows them (`EXTRA_BOXES` in checks.py).
- **C9** Every zone 7 row appears among the type-3 Actes.
- **C10** Zone 8 = TotalPrestations.
- **C10b** Every type-3 Acte appears in zone 6 or zone 7. (Split from C10 so the agent sees which of the two rules failed and each card compares one value; codes C11–C17 keep their numbers.)
- **C11** Zone 10 codes of ≤4 characters appear among the type-4 Actes, and codes of 7 characters appear among the 4-M CodeCCAM. Every type-4 act appears in zone 10 **either as its Acte code or as the CodeCCAM of its 4-M line**: a CCAM act's base line carries a grouping code (`ATM`, `ADA`, `ADC`…) that is not printed on the form.
- **C12** Every 4-S NumeroGH = the GHS number from zone 6.
- **C13** Zone 12 = TotalHonoraires.
- **C14** Each distinct zone 9 executor whose **3rd character ≠ `0`** (i.e. not an establishment) requires at least one signature in zone 11 (any of the 8 boxes).
- **C15** Zone 13 = zone 8 + zone 12 (in integer cents).
- **C16** Zone 14 has a signature.
- **C17** Zone 15 = `S3404` (ignore spaces).

## Implementation
- **`extract.py`** (batch, CLI): runs the OCR once per full page and caches the lines (text, box, score) in `backend/cache/<name>.json`, which is gitignored. The OCR is **RapidOCR running PP-OCRv6 medium (`lang_type="fr"`) on OpenVINO** (same model as PaddleOCR's default, checked at 165/165 on `devtools/eval.py`): about 20-30 s per page on CPU, so the full set takes about 20 min; it runs on the Intel iGPU when `intel-opencl-icd` is installed (`ocr_device()`, `MELEE_OCR_DEVICE=CPU|GPU` to force). **Never run OCR inside a request**. Skip images whose cache already exists. `main.py` starts this batch by itself in a separate process, at server startup and then from a watcher thread that checks every 15 s for scans missing from the cache (`ensure_ocr_batch()`, at most one launch per 60 s; finished batches are reaped so they never linger as zombies) (lock `cache/ocr.pid` so `--reload` never starts a second one, log `cache/ocr.log`, `MELEE_AUTO_OCR=0` to disable). Cache files are written atomically (tmp file + rename). `GET /api/health` reports `{status, ocr: {faits, total, en_cours}}`.
  - **Locate fields by anchors, not fixed pixels.** Find the printed labels (`N° LOT`, `N° FACTURE`, `sous-total 1+2+3`, `sous-total 4`, `MONTANT TOTAL`, `S 3404`, …) and read the box immediately to their right.
  - **Tables (zones 6, 7, 9, 10)**: find the column header boxes (`prestation`, `n° GHS`, `montant facturé`, `numéro d'identification de l'exécutant`, `code acte ou lettre-clé`). Assign boxes below each header by x-overlap, then group them into rows by y.
  - **Signatures (zones 11, 14)**: no OCR. Locate the region from anchors, mask the ruled lines, then measure dark-pixel density with OpenCV against a tunable threshold. For zone 14, look beyond the box, because Facture3's stamp overflows it.
  - Output is raw by design: never "correct" a value. A field below the confidence threshold is marked `illisible`, and its check becomes `A_VERIFIER`.
- **`checks.py`**: plain deterministic Python, no LLM. It implements C0–C17 on top of `backend/deserialization/parse_b2.parse_file`, and it compares the parsed B2 model against the OCR model, which has the same shape, field by field.
  - Include one assert-based self-test, run with `uv run python checks.py`:
    - `Facture1_01` parses to the values verified above.
    - `Facture2_06` yields C0 = KO.
  - **Normalise before comparing**:
    - Amounts: accept `,` or `.`, compare in cents.
    - Numbers: strip leading zeros (B2 `000491901` = form `491901`).
    - Codes: trim and uppercase.
  - **Merged OCR boxes**: the OCR sometimes glues a label to its value (`n° d'immatriculation et clé2520299007001 01`) or glues two columns together (`9606K` = GHS + code acte). Split them with regexes based on the expected formats.
- **`main.py`**: the API below. Read the cache and B2 files and compute the checks at startup or on demand (that part is cheap).
- **Treated invoices**: append the invoice id to `traitees.txt` (one per line, gitignored). Nothing else about the decision is stored.

## API contract (shared with the frontend — keep it identical)
All JSON. Field names are in French, to match the UI.

`GET /api/factures`: the queue, sorted with KO first, then `A_VERIFIER`, then the rest; undecided invoices before decided ones.
```json
[{ "id": "Facture1_01", "nb_ko": 0, "nb_a_verifier": 1, "ocr": true, "traitee": false, "difficulte": 4, "niveau": "Facile" }]
```
- `ocr` is `false` until `extract.py` has analysed the scan. Such an invoice has every scan check `A_VERIFIER` ("scan non traité (OCR)") and **is filtered out by the frontend**. Checks are cached per (invoice, OCR state), so an invoice is re-checked as soon as its OCR cache appears, without restarting uvicorn.
- `difficulte` (0–100) + `niveau` (`Facile`, `Modérée`, `Moyenne`, `Difficile`, `Très difficile`) estimate how hard the invoice is to review. Computed in `difficulte.py` from the check results and the scan: +8 per KO (cap 40), +4 per À-vérifier (cap 20), +20 when C0 is KO (malformed B2, fully manual review), +4 per unreadable anomaly zone (cap 12), per KO check `round((1 - confiance) * 10)` (cap 20) — a wrong line read with shaky OCR cannot be trusted, so the agent must verify from the pixels — and per KO check (C0 excluded) `max(len(attendu), len(lu)) // 15` (cap 10), since long mismatched values take longer to compare. `GET /api/factures/{id}` carries the same two fields.
- Each check also carries `confiance` (0–1, min OCR line score over its zones, `null` when unknown: no zones, unprocessed scan, or unscored zones like the ink-density signatures 11/14). The frontend shows it on the check card; `difficulte.py` uses the KO checks' values.

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
      "confiance": 1.0,
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
- `contexte`: boxes of the printed labels the values were found next to (e.g. "sous-total 4"), in image pixels. The UI puts them in the card crops so the agent sees which field a value is; they are never highlighted. Optional (absent from older caches).
- `statut` is `OK`, `KO` or `A_VERIFIER`.
- `attendu` is the value from the B2 file and `lu` is the value read on the scan. Both are display strings (for example `"28,80"`, `"GHS, PH8, EMI"`, `"signature absente"`).
- `boxes` are `[x0, y0, x1, y1]` in **original image pixels**. The frontend draws the crops and the zoom itself, so the backend does not generate crop images.
- `traitee` is `true` once the invoice has been validated or rejected (its id is in `backend/traitees.txt`).

`POST /api/factures/{id}/decision`: the body is `{ "statut": "valide" | "rejete", "commentaire": "…", "overrides": ["C1"] }`, and the response is `204`. Only the invoice id is recorded (in `backend/traitees.txt`); the body is not kept.

`GET /api/images/{name}.jpg`: the raw scan, served from `images/` at the repo root.

Return `404` for an unknown id. Validate `id` against the list of known basenames: **never build a file path from raw user input**.

## Evaluation
Hand-label about 10 invoices into `devtools/expected.json` (zone values as read by a human, at least 2 per Facture set). Write `devtools/eval.py` to report per-zone extraction accuracy, then tune the anchors and thresholds until those zones are 100% correct.

## OCR test results so far (Facture1_01, Facture2_01, Facture3_01)
- Read correctly:
  - FINESS, lot, invoice and insured numbers
  - all prestation codes, GHS numbers, CCAM codes and amounts
  - the anchors `sous-total 1+2+3` and `S 3404`
- `12278*01` loses its `*` on Facture1_01, even when the crop is upscaled 2× or 3× (C1 already allows for this).
- Amounts sometimes come back as `818.97` for a printed `818,97`.

## Open points
- The parser's data model allows several lots and invoices per file, but all 55 files have exactly one invoice (`Facture2_06` shows two only because of its column shift). The app assumes one invoice per file.
- 19 of the 55 files have a `2-S` complement line. The parser records it, but no check uses it.
- Zone 11 has 8 boxes, and one signature in any of them is enough.
- Invoices span a single page (`Page 1/1`). Multi-page forms are out of scope until one appears.
