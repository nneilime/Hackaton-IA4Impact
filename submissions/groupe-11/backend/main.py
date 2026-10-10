import os
import subprocess
import sys
import threading
import time
from functools import lru_cache
from pathlib import Path

import cv2
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse

from checks import RECEIPTS, run_checks
from difficulte import evaluer
from extract import CACHE, IMAGES, LOCK, batch_running, extract
from stats import compute_stats

app = FastAPI(title="Melee")

TREATED = Path(__file__).resolve().parent / "traitees.txt"  # one invoice id per line, appended on decision
# The only ids we ever build a path from: basenames present in both images/ and receipts/
NAMES = sorted({p.stem for p in IMAGES.glob("*.jpg")} & {p.stem for p in RECEIPTS.glob("*.txt")})


def known(id_):
    if id_ not in NAMES:
        raise HTTPException(404, "facture inconnue")
    return id_


def ocr_done(id_):
    """True once extract.py has OCR'd this scan (its cache file exists)."""
    return (CACHE / f"{id_}.json").exists()


def checks_for(id_):
    # Keyed on the OCR state too, so an invoice is re-checked as soon as extract.py caches its scan
    return _checks(id_, ocr_done(id_))


@lru_cache(maxsize=None)
def _checks(id_, ocr):
    return run_checks(id_)


OCR_CHECK_EVERY = 15    # seconds between two checks for scans missing from the cache
OCR_MIN_RESTART = 60    # seconds between two launches, so a crashing batch is not respawned in a loop
_ocr = {"proc": None, "last_start": 0.0}
_stop_watch = threading.Event()


def ensure_ocr_batch():
    """Start the OCR batch if some scans are not cached and no batch is running.

    Runs in a separate process so the API stays responsive; invoices reach the agent's queue one by
    one, as soon as their scan is cached. The batch survives `--reload` restarts, and the lock in
    extract.py prevents a second one. Set MELEE_AUTO_OCR=0 to disable.
    """
    proc = _ocr["proc"]
    if proc is not None and proc.poll() is not None:  # reap the finished batch, or it stays a zombie
        _ocr["proc"] = None                           # that batch_running() would see as alive
    if (os.environ.get("MELEE_AUTO_OCR", "1") == "0" or all(ocr_done(n) for n in NAMES)
            or batch_running() or time.monotonic() - _ocr["last_start"] < OCR_MIN_RESTART):
        return
    CACHE.mkdir(exist_ok=True)
    with (CACHE / "ocr.log").open("a") as log:
        _ocr["proc"] = subprocess.Popen([sys.executable, str(Path(__file__).with_name("extract.py"))],
                                        cwd=Path(__file__).parent, stdout=log, stderr=subprocess.STDOUT)
    _ocr["last_start"] = time.monotonic()
    LOCK.write_text(str(_ocr["proc"].pid))  # immediately, so a quick reload does not start a second batch


def _watch_ocr():
    """Keep checking, e.g. after the cache was deleted while the server was running."""
    while not _stop_watch.wait(OCR_CHECK_EVERY):
        try:
            ensure_ocr_batch()
        except Exception as e:  # never let the watcher die
            print(f"OCR watcher: {e!r}", file=sys.stderr, flush=True)


@app.on_event("startup")
def _start_ocr_batch():
    _ocr["last_start"] = 0.0
    ensure_ocr_batch()
    _stop_watch.clear()
    threading.Thread(target=_watch_ocr, name="ocr-watcher", daemon=True).start()


@app.on_event("shutdown")
def _stop_ocr_watch():
    _stop_watch.set()


@app.on_event("startup")
def _warm_cache():
    """Pre-compute all check results once at startup so every route is instant."""
    for n in NAMES:
        checks_for(n)


def treated():
    """Ids of the invoices the agent has already validated or rejected."""
    return set(TREATED.read_text(encoding="utf-8").split()) if TREATED.exists() else set()


@app.get("/api/health")
def health():
    return {"status": "ok",
            "ocr": {"faits": sum(ocr_done(n) for n in NAMES), "total": len(NAMES), "en_cours": batch_running()}}


def difficulte_for(id_, checks):
    """0-100 review difficulty (see difficulte.py), from cached checks + OCR scores."""
    ocr = extract(id_) if ocr_done(id_) else None
    return evaluer(checks, ocr["scan"] if ocr else None)


@app.get("/api/factures")
def list_factures():
    done = treated()
    out = []
    for n in NAMES:
        checks = checks_for(n)
        st = [c["statut"] for c in checks]
        diff = difficulte_for(n, checks)
        out.append({"id": n, "nb_ko": st.count("KO"), "nb_a_verifier": st.count("A_VERIFIER"),
                    "ocr": ocr_done(n), "traitee": n in done,
                    "difficulte": diff["score"], "niveau": diff["niveau"]})
    rank = lambda f: (f["traitee"], 0 if f["nb_ko"] else 1 if f["nb_a_verifier"] else 2, f["id"])  # noqa: E731
    return sorted(out, key=rank)


@app.get("/api/factures/{id_}")
def get_facture(id_: str):
    known(id_)
    ocr = extract(id_)
    if ocr:
        size = ocr["scan"]["image"]
    else:
        h, w = cv2.imread(str(IMAGES / f"{id_}.jpg"), cv2.IMREAD_GRAYSCALE).shape
        size = {"largeur": w, "hauteur": h}
    checks = checks_for(id_)
    diff = difficulte_for(id_, checks)
    return {"id": id_, "image": {"url": f"/api/images/{id_}.jpg", **size},
            "checks": checks, "traitee": id_ in treated(),
            "difficulte": diff["score"], "niveau": diff["niveau"]}


@app.post("/api/factures/{id_}/decision", status_code=204)
def post_decision(id_: str):
    """Marks the invoice as treated; the body (statut, commentaire, overrides) is not kept."""
    known(id_)
    with TREATED.open("a", encoding="utf-8") as fh:
        fh.write(id_ + "\n")
    return Response(status_code=204)


@app.get("/api/stats")
def get_stats():
    return compute_stats(NAMES, checks_for, ocr_done, difficulte_for)


@app.get("/api/ocr-status")
def ocr_status():
    """Per-invoice OCR processing status and per-zone confidence scores."""
    rows = []
    for name in NAMES:
        cache_file = CACHE / f"{name}.json"
        processed = cache_file.exists()
        zone_scores: dict | None = None
        unreadable: list[int] = []
        if processed:
            ocr = extract(name)
            if ocr:
                zone_scores = {k: round(v, 3) for k, v in ocr["scan"].get("scores", {}).items()}
                unreadable = ocr["scan"].get("illisible", [])
        rows.append({
            "id": name,
            "traite": processed,
            "zone_scores": zone_scores,
            "zones_illisibles": unreadable,
        })
    nb_traites = sum(1 for r in rows if r["traite"])
    return {
        "nb_total": len(NAMES),
        "nb_traites": nb_traites,
        "factures": rows,
    }


@app.get("/api/images/{filename}")
def image(filename: str):
    if not filename.endswith(".jpg"):
        raise HTTPException(404)
    return FileResponse(IMAGES / f"{known(filename[:-4])}.jpg", media_type="image/jpeg")
