# Melee — Contrôle des bordereaux de facturation

Compares a scanned billing form (`images/`) against its B2 text invoice (`receipts/`). See [PROMPT.md](PROMPT.md) for the full brief and the list of checks.

## Prerequisites
- [uv](https://docs.astral.sh/uv/) (`brew install uv`). It installs the right Python version (3.13) by itself.
- Node.js ≥ 22.22.3 or ≥ 24.15 with npm (required by the Angular CLI; `nvm install 24` works)

## Backend (FastAPI + RapidOCR/OpenVINO) — `backend/`
```bash
cd backend && uv sync
```
```bash
cd backend && uv run uvicorn main:app --reload
```
The API runs on http://localhost:8000, and http://localhost:8000/docs lists the endpoints.

The API starts the OCR batch by itself, in a separate process, for every scan not cached yet: at startup, then whenever a check every 15 s finds scans missing from the cache (e.g. after `backend/cache/` was deleted, or the batch crashed; at most one launch per minute) (progress in `backend/cache/ocr.log` and in `GET /api/health`). The OCR is RapidOCR running PP-OCRv6 medium on OpenVINO: about 20-30 s per scan on CPU. It uses the Intel iGPU instead when its compute driver is installed (`sudo apt install intel-opencl-icd`); `MELEE_OCR_DEVICE=CPU|GPU` forces a device. Results are cached in `backend/cache/`, and already-cached scans are skipped. A lock (`backend/cache/ocr.pid`) prevents two batches at once, including across `--reload` restarts. An invoice is shown to the agent only once its scan is in the cache; until then the review screen leaves it out (and says "Aucune facture disponible" while nothing is ready). Newly analysed invoices are added to the end of the agent's queue every 15 s, without reloading the page or restarting the API.

Set `MELEE_AUTO_OCR=0` to disable the automatic batch, and run it by hand instead with:
```bash
cd backend && uv run python extract.py
```
Self-test for the checks (C0–C17):
```bash
cd backend && uv run python checks.py
```
Per-zone extraction accuracy against the hand-labelled `backend/devtools/expected.json`:
```bash
cd backend && uv run python devtools/eval.py
```
Each invoice the agent validates or rejects is appended (its id, one per line) to `backend/traitees.txt`; delete the file to put every invoice back in the queue.

## Frontend (Angular) — `angular/`
```bash
cd angular && npm install
```
```bash
cd angular && npm start
```
The app runs on http://localhost:4200. During development, `/api` calls are forwarded to the backend through `proxy.conf.json`, so **start the backend first**. Without it, the review screen shows "Impossible de charger les factures".

- http://localhost:4200: the agent's review screen. It queues the undecided invoices that have at least one KO or À vérifier check, shows those checks next to the scan with their zones highlighted, and `V` / `R` validate or reject (the invoice is recorded in `backend/traitees.txt`). Treated invoices no longer appear on the next load.
- http://localhost:4200/dashboard: the supervisor dashboard (`GET /api/stats`).

Tests (Vitest; HTTP is mocked, no backend needed):
```bash
cd angular && npm test
```

## Layout
```
images/     scanned forms (JPG)
receipts/   B2 invoice files (TXT), paired with images/ by filename
backend/    FastAPI + OCR + checks (Python)
angular/    review UI (Angular)
```
