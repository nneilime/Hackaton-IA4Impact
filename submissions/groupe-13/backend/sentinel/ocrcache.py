"""Cache des extractions OCR, versionné et vérifié (version 2.0).

Clé d'une extraction : empreinte SHA-256 de l'image + empreinte du CODE d'extraction (sources du paquet
`ocr/`, normalisations, gabarits F1/F2/F3 et cartes de référence des mises en page, paramètres de
prétraitement compris). Toute évolution de l'extracteur invalide donc automatiquement les extractions
concernées : elles sont recalculées, jamais réutilisées silencieusement.

La configuration des moteurs OCR (RapidOCR, version de Tesseract ou absence de Tesseract) est enregistrée
avec chaque extraction. Si elle diffère de celle de la machine, l'extraction reste utilisable (elle a été
produite par le même code sur la même image) mais elle est SIGNALÉE dans le dossier, et
`python -m sentinel.cli extract --force` la recalcule avec les moteurs locaux.

Format du fichier data/cache/ocr/<sha256>.json :
    {"cache_meta": {format, image_sha256, code_hash, code_profile, engine_profile, content_sha256, created_at},
     "extraction": {...}}
Écriture atomique (fichier temporaire puis remplacement), contrôle d'intégrité à la lecture (empreinte du
contenu), mise à l'écart et recalcul d'un fichier corrompu.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Optional

from .config import OCR_CACHE_DIR

log = logging.getLogger("sentinel")
FORMAT = 2
PKG = Path(__file__).resolve().parent


def _norm_bytes(p: Path) -> bytes:
    b = p.read_bytes()
    return b.replace(b"\r\n", b"\n") if p.suffix == ".py" else b   # indépendant des fins de ligne (Windows/Git)


@lru_cache(maxsize=1)
def code_profile() -> dict:
    """Empreintes des éléments de code qui déterminent le résultat d'une extraction."""
    files = sorted((PKG / "ocr").glob("*.py")) + [PKG / "normalize.py"] + sorted((PKG / "ocr" / "refs").glob("*.png"))
    parts = {f.relative_to(PKG).as_posix(): hashlib.sha256(_norm_bytes(f)).hexdigest()[:16] for f in files if f.exists()}
    from .ocr.extract import EXTRACTOR_VERSION
    return {"extractor_version": EXTRACTOR_VERSION, "files": parts}


@lru_cache(maxsize=1)
def code_hash() -> str:
    return hashlib.sha256(json.dumps(code_profile(), sort_keys=True).encode()).hexdigest()[:20]


_ENGINE_PROFILE: Optional[dict] = None


def engine_profile() -> dict:
    """Configuration des moteurs OCR de la machine (versions des paquets / du binaire Tesseract)."""
    global _ENGINE_PROFILE
    if _ENGINE_PROFILE is None:
        prof = {"rapidocr": None, "tesseract": None}
        try:
            from importlib.metadata import version
            prof["rapidocr"] = version("rapidocr_onnxruntime")
        except Exception:  # noqa
            pass
        try:
            from .ocr.reader import _optional_tesseract
            t = _optional_tesseract()
            prof["tesseract"] = ".".join(str(getattr(t, "version", "")).split(".")[:2]) if t else None
        except Exception:  # noqa
            pass
        _ENGINE_PROFILE = prof
    return _ENGINE_PROFILE


def _content_hash(ext: dict) -> str:
    return hashlib.sha256(json.dumps(ext, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def path_for(sha: str) -> Path:
    return OCR_CACHE_DIR / f"{sha}.json"


def write(sha: str, ext: dict, engines: Optional[dict] = None) -> dict:
    """Écriture atomique d'une extraction avec ses métadonnées de version."""
    OCR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    meta = {"format": FORMAT, "image_sha256": sha, "code_hash": code_hash(), "code_profile": code_profile(),
            "engine_profile": engines or engine_profile(), "content_sha256": _content_hash(ext),
            "created_at": dt.datetime.now().isoformat(timespec="seconds")}
    fd, tmp = tempfile.mkstemp(dir=OCR_CACHE_DIR, prefix=f".{sha[:12]}-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"cache_meta": meta, "extraction": ext}, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path_for(sha))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return meta


def read(sha: str) -> tuple[Optional[dict], str, dict]:
    """Lit une extraction. Retourne (extraction | None, statut, informations).

    Statuts : « valide », « autre_configuration_ocr » (utilisable, signalée), « absente »,
    « obsolete » (code d'extraction différent ou ancien format), « corrompue »."""
    p = path_for(sha)
    if not p.exists():
        return None, "absente", {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, "corrompue", {"erreur": f"{type(e).__name__}: {e}"}
    meta = data.get("cache_meta") if isinstance(data, dict) else None
    if not meta or meta.get("format") != FORMAT or "extraction" not in data:
        return None, "obsolete", {"raison": "ancien format de cache (sans version d'extraction)"}
    ext = data["extraction"]
    if meta.get("image_sha256") != sha or meta.get("content_sha256") != _content_hash(ext):
        return None, "corrompue", {"raison": "empreinte du contenu ou de l'image incohérente"}
    if meta.get("code_hash") != code_hash():
        return None, "obsolete", {"raison": "code d'extraction modifié depuis le calcul",
                                  "ancien": meta.get("code_hash"), "actuel": code_hash()}
    info = {"code_hash": meta["code_hash"], "engine_profile": meta.get("engine_profile"), "created_at": meta.get("created_at")}
    local = engine_profile()
    if meta.get("engine_profile") != local:
        info["engine_profile_local"] = local
        return ext, "autre_configuration_ocr", info
    return ext, "valide", info


def quarantine(sha: str):
    p = path_for(sha)
    if p.exists():
        dest = p.with_suffix(f".corrompu-{dt.datetime.now():%Y%m%d%H%M%S}")
        os.replace(p, dest)
        log.warning("Cache OCR corrompu mis à l'écart : %s", dest.name)


def load_or_compute(jpg: Path, sha: str, allow_compute: bool = True, force: bool = False) -> Optional[dict]:
    """Extraction d'un bordereau : cache valide, sinon recalcul (si autorisé). Le statut du cache est
    ajouté à l'extraction (`ext["cache"]`) pour être affiché dans le dossier."""
    status, info = "recalcul_force", {}
    if not force:
        ext, status, info = read(sha)
        if status == "corrompue":
            quarantine(sha)
        if ext is not None:
            ext = dict(ext)
            ext["cache"] = {"statut": status, **info}
            if status == "autre_configuration_ocr":
                ext["cache"]["message"] = (
                    "Extraction produite par le même code d'extraction mais avec une autre configuration OCR "
                    f"({_fmt(info.get('engine_profile'))}) que celle de ce poste ({_fmt(info.get('engine_profile_local'))}). "
                    "Commande pour la recalculer : python -m sentinel.cli extract --force")
            return ext
    if not allow_compute:
        return None
    from .ocr.extract import extract_bordereau   # import tardif : moteurs OCR facultatifs
    import time
    t0 = time.time()
    ext = extract_bordereau(jpg)
    ext["duration_s"] = round(time.time() - t0, 1)
    meta = write(sha, ext)
    out = dict(ext)
    out["cache"] = {"statut": "calcule", "raison_recalcul": status, "previous": info, "code_hash": meta["code_hash"],
                    "engine_profile": meta["engine_profile"], "created_at": meta["created_at"]}
    return out


def _fmt(p: Optional[dict]) -> str:
    if not p:
        return "inconnue"
    return "RapidOCR " + str(p.get("rapidocr") or "absent") + (f" + Tesseract {p['tesseract']}" if p.get("tesseract") else ", sans Tesseract")


def status_report() -> dict:
    """État du cache pour l'administration : nombre d'extractions valides, obsolètes, corrompues."""
    from collections import Counter
    c = Counter()
    for p in OCR_CACHE_DIR.glob("*.json"):
        c[read(p.stem)[1]] += 1
    return {"code_hash": code_hash(), "engine_profile": engine_profile(), "fichiers": dict(c)}
