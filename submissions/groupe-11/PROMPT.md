# Project brief — Bordereau vs. invoice-file checker (hackathon POC)

> Per-team briefs, with the shared API contract: [PROMPT_BACKEND.md](PROMPT_BACKEND.md) · [PROMPT_FRONTEND.md](PROMPT_FRONTEND.md)

## Goal
Billing agents currently compare, by hand and invoice by invoice, a **scanned billing form** (cerfa n° 12278*01 "bordereau de facturation", form S 3404) against the **structured text invoice file** (B2 format) for the same invoice. Build a local web app that pre-computes every check and lets an agent confirm or reject each invoice **using only the keyboard**, in a few seconds per invoice. Users are non-technical, so the UI is in **French**.

Constraints: hackathon (≤48h), runs locally (no deployment), working demo over production polish.

## Inputs (already in the repo)
- `receipts/FactureX_NN.txt`: one invoice per file, fixed-width B2 records.
- `images/FactureX_NN.jpg`: the matching scanned form. Files are paired by basename. 55 pairs: Facture1 ×20, Facture2 ×20, Facture3 ×15.
  - **The layout is not pixel-identical across sets.** Facture1 and Facture2 scans are about 1190×1684 px, Facture3 scans are 1684×2382 px with a slightly different rendering.
  - Amounts appear with `,` or `.` and sometimes without trailing zeros (`398,3`, `448.78`).
  - Facture3's establishment signature is a digital stamp ("Signé numériquement par…") that sits partly outside the box.
- There is no ground truth. The test set probably contains injected discrepancies.

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

### Parser already implemented — `backend/deserialization/parse_b2.py` (RaphxelS)
- `parse_file(path)` returns the nested model described in `b2.schema.json`:
  - lots → factures → `prestations_hospitalieres` / `actes`, with sub-lines nested in `details`
  - amounts as float euros, which must be converted to cents before comparing
- The schema is the **shared model**: the OCR fills the same fields from the scan, and the scan-only fields go in an extra `scan` object.
- Reuse the parser. Details are in [PROMPT_BACKEND.md](PROMPT_BACKEND.md).
- ⚠️ **`Facture2_06.txt` is malformed.** It has an extra space at position 12, so every field is shifted one column. The parser now reports a `column shift` error for it, and the new check **C0** turns that into KO.

## Scan zones to extract (see the diagram on page 1 of the rules PDF)
1. Cerfa number (top left, e.g. `12278*01`)
2. FINESS number of the establishment
3. N° LOT
4. N° FACTURE
5. Patient's n° d'immatriculation (first 13 characters only)
6. "Frais de structure et de soins": `prestation` code + `n° GHS` + `montant facturé` for each row (both tables (1) and (2))
7. "Produits LPP / médicaments": `prestation` code + `n° GHS` for each row
8. Sous-total 1+2+3
9. Honoraires: `n° d'identification de l'exécutant` for each row
10. Honoraires: `code acte ou lettre-clé` for each row
11. Practitioner signature boxes 1–8: which boxes contain a signature
12. Sous-total 4
13. MONTANT TOTAL
14. Establishment director's signature: present or not
15. Form code bottom right (e.g. `S 3404`)

## Checks (each one returns OK / KO plus the two values compared)
- **C0** The B2 file is well formed: no parser errors and no column shift. When C0 is KO, every other check is "À vérifier".
- **C1** Zone 1 starts with `12278*0`. The OCR sometimes drops the tiny `*` (it read `1227801` on Facture1_01), so match `12278[*=]?0` (the OCR also reads it as `=`). The number is identical on every form, so a `*`, a space or nothing between `12278` and `0` is **OK**, and it is KO only when the digits differ.
- **C2** Zone 2 = NumeroTiers. **C3** Zone 3 = NumeroLot. **C4** Zone 4 = NumeroFacture. **C5** Zone 5 (13 chars) = NumeroAssure.
- **C6** Zone 6 contains a `GHS` row with a GHS number, and that number = NumeroGH of the type-3 `GHS` act.
- **C7** Every zone 6 row that has a billed amount appears among the type-3 Actes.
- **C8** Every type-3 act other than the GHS line has NumeroGH = the GHS number from zone 6 (the GHS line itself is C6).
- **C9** Every zone 7 row appears among the type-3 Actes.
- **C10** Zone 8 = TotalPrestations.
- **C10b** Every type-3 Acte appears in zone 6 or zone 7. (Split from C10 so the agent sees which of the two rules failed and each card compares one value; codes C11–C17 keep their numbers.)
- **C11** Zone 10 codes of ≤4 characters appear among the type-4 Actes, codes of 7 characters appear among the 4-M CodeCCAM, and every type-4 act appears in zone 10 **either as its Acte code or as the CodeCCAM of its 4-M line**. A CCAM act's base line carries a grouping code (`ATM`, `ADA`, `ADC`…) that is not printed on the form; only its CCAM code is.
- **C12** Every 4-S NumeroGH = the GHS number from zone 6.
- **C13** Zone 12 = TotalHonoraires.
- **C14** Each distinct zone 9 executor whose **3rd character ≠ `0`** (i.e. not an establishment) requires at least one signature in zone 11.
- **C15** Zone 13 = zone 8 + zone 12 (compute in integer cents).
- **C16** Zone 14 has a signature.
- **C17** Zone 15 = `S3404` (ignore spaces).

## Architecture
- **Backend**: Python + FastAPI. **Everything runs locally and no data leaves the machine** (health data).
- **Extraction**: a batch script `extract.py` runs **RapidOCR + OpenVINO (PP-OCRv6 medium, French; CPU, or the Intel iGPU when its driver is installed)** once on the full page. That takes about 20-30 s per page on CPU, so the 55 test pages take about 20 min: run it once as a batch, never at review time. It returns every text line with its bounding box and confidence, and the result is cached in `cache/<name>.json`.
  - **Locate fields by anchors, not fixed pixels.** Find the printed labels (`N° LOT`, `N° FACTURE`, `sous-total 1+2+3`, `sous-total 4`, `MONTANT TOTAL`, `S 3404`, …) and read the box immediately to their right.
  - **Tables (zones 6, 7, 9, 10)**: find the column header boxes (`prestation`, `n° GHS`, `montant facturé`, `numéro d'identification de l'exécutant`, `code acte ou lettre-clé`). Assign every box under a header to that column by x-overlap, and group boxes into rows by y.
  - **Signatures (zones 11, 14)**: no OCR. Locate the region from anchors (practitioner boxes 1–8; the area right of `MONTANT TOTAL`), mask the ruled lines, then measure dark-pixel density with OpenCV against a threshold you can tune.
  - OCR output is raw by design: nothing gets "corrected". Any field whose confidence is below a threshold is marked `illisible`, and the related check becomes **"À vérifier"** instead of OK/KO.
- **Checks**: plain deterministic Python in `checks.py` (B2 parser + C1–C17). No LLM. Compare amounts in cents and codes after trimming and uppercasing. Add one assert-based self-test that uses `Facture1_01`.
- **Zone crops**: each check is shown next to the crop of its zone, taken from the anchor and OCR boxes. The agent then checks the pixels, not the OCR.
- **Frontend**: an Angular project in `angular/` at the repo root (latest Angular CLI, standalone components, signals, no NgModules). The FastAPI backend in `backend/` only serves a JSON API plus the images and crops (`GET /api/factures`, `GET /api/factures/{id}`, `POST /api/factures/{id}/decision`). `proxy.conf.json` forwards `/api` to FastAPI during `ng serve`.
  - Keyboard shortcuts are handled by one `@HostListener('document:keydown')` in a shortcuts service.
  - Add Angular CDK only when it's needed (for example `cdk/a11y` focus management, or overlays for the zoom). No UI kit up front.
- **Results**: the id of each validated or rejected invoice is appended to `traitees.txt`.

## UX — keyboard-first review (UI in French)
- A queue of invoices, with anomalies sorted first. The layout is a split view: the scan (zoomable) on the left, the list of checks on the right. Each check shows its OK/KO status, the two values compared and the zone crop.
- Shortcuts are always shown in a footer:
  - `Entrée` = validate the invoice
  - `R` = reject (opens a comment field, `Entrée` saves it)
  - `J`/`K` or `↓`/`↑` = next/previous check
  - `N`/`P` = next/previous invoice
  - `Z` = zoom the scan onto the selected check's zone
  - `Espace` = override the selected check
  - `?` = help
- Large type, high-contrast KO in red and OK in green, no mouse required, and the next invoice preloads instantly.

## Evaluation
No ground truth exists. Hand-label about 10 invoices into `expected.json` (the zone values as read by a human), then write `eval.py` to report per-zone extraction accuracy. Tune the anchors and thresholds until those zones are 100% correct. Include at least 2 invoices from each Facture set.

## OCR test results (Facture1_01, Facture2_01, Facture3_01)
- Read correctly: FINESS, lot, invoice and insured numbers; all prestation codes; GHS numbers; CCAM codes; amounts; anchors (`sous-total 1+2+3`, `S 3404`, `12278*01`).
- **Normalise before comparing**:
  - Amounts: the OCR returns `818.97` for a printed `818,97`, so accept `,` or `.` and compare in cents.
  - Numbers: strip leading zeros (B2 has `000491901`, the form shows `491901`).
- **OCR boxes merge neighbouring cells**: a label with its value (`n° d'immatriculation et clé2520299007001 01`), or two table columns (`9606K` = GHS + code acte). Split them with regexes on the expected formats.
- Upscaling the crop did **not** recover the missing `*` in Facture1_01 (see C1).

## Open points / ambiguities to keep in mind
- C1: the rule says `12278*0` while the scan shows `12278*01`, so the check is "starts with".
- The first bullet of rules section 3.4 repeats a rule from section 3.3. It is implemented once, as C8.
- Zone 11 has 8 boxes, and one signature in any box is enough.
- Invoices span a single page (`Page 1/1`). Multi-page forms are out of scope until one appears.
