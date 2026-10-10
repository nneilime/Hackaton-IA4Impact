"""Import manuel de nouveaux dossiers (un bordereau image + un fichier de facturation TXT).

Les dossiers importés sont stockés à part (data/imports/<id>/), en lecture seule, et marqués
« Import » partout dans l'application : ils ne sont jamais mélangés aux statistiques du corpus
officiel sans être identifiés comme tels.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import secrets
import shutil
from pathlib import Path

from .config import DATA_DIR

IMPORTS_DIR = Path(os.environ.get("SENTINEL_IMPORTS", DATA_DIR / "imports"))
MAX_IMG = 25 * 1024 * 1024
MAX_TXT = 2 * 1024 * 1024
IMG_MAGIC = {b"\xff\xd8\xff": ".jpg", b"\x89PNG\r\n\x1a\n": ".png"}


class ImportError_(ValueError):
    pass


def _safe_name(name: str, default: str) -> str:
    base = Path(name or default).name
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", base).strip(" .") or default
    return base[:80]


def validate(img: bytes, txt: bytes):
    if not img or len(img) > MAX_IMG:
        raise ImportError_("Bordereau absent ou trop volumineux (25 Mo maximum).")
    ext = next((e for m, e in IMG_MAGIC.items() if img.startswith(m)), None)
    if not ext:
        raise ImportError_("Le bordereau doit être une image JPG ou PNG.")
    if not txt or len(txt) > MAX_TXT:
        raise ImportError_("Fichier de facturation absent ou trop volumineux (2 Mo maximum).")
    try:
        text = txt.decode("latin-1")
    except Exception:
        raise ImportError_("Fichier de facturation illisible.")
    lines = [l for l in re.split(r"\r?\n", text) if l]
    if not lines or not all(l[0] in "0123456789" for l in lines):
        raise ImportError_("Le fichier TXT ne ressemble pas à une facture B2 : chaque ligne doit commencer "
                           "par un type d'enregistrement (0 à 6).")
    if not any(l[0] == "2" for l in lines):
        raise ImportError_("Le fichier TXT ne contient aucun enregistrement de début de facture (type 2).")
    return ext


def create_import(img: bytes, img_name: str, txt: bytes, txt_name: str, label: str | None, username: str,
                  origin: str | None = None, edits: list | None = None) -> dict:
    ext = validate(img, txt)
    iid = "Import_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + secrets.token_hex(2)
    d = IMPORTS_DIR / iid
    d.mkdir(parents=True, exist_ok=False)
    jn = Path(_safe_name(img_name, "bordereau")).stem + ext
    tn = Path(_safe_name(txt_name, "facture")).stem + ".txt"
    (d / jn).write_bytes(img)
    (d / tn).write_bytes(txt)
    meta = {"id": iid, "label": (label or "").strip()[:120], "jpg": jn, "txt": tn, "by": username,
            "created_at": dt.datetime.now().isoformat(timespec="seconds"),
            # « simulation » : copie d'un dossier autorisé dont le TXT a été modifié dans l'application
            "kind": "simulation" if origin else "import", "origin": origin, "edits": edits or []}
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    for p in (d / jn, d / tn):
        os.chmod(p, 0o444)               # originaux en lecture seule
    return meta


def import_pairs() -> list:
    out = []
    if not IMPORTS_DIR.exists():
        return out
    for d in sorted(IMPORTS_DIR.iterdir()):
        mf = d / "meta.json"
        if not d.is_dir() or not mf.exists():
            continue
        m = json.loads(mf.read_text(encoding="utf-8"))
        jpg, txt = d / m["jpg"], d / m["txt"]
        if jpg.exists() and txt.exists():
            out.append({"id": d.name, "family": "Import", "jpg": jpg, "txt": txt, "status": "paire",
                        "source": "import", "label": m.get("label"), "meta": m})
    return out


def delete_import(iid: str):
    if not re.fullmatch(r"Import_[0-9_a-f]+", iid):
        raise ImportError_("Identifiant d'import invalide.")
    d = IMPORTS_DIR / iid
    if d.exists():
        for p in d.iterdir():
            os.chmod(p, 0o644)
        shutil.rmtree(d)
