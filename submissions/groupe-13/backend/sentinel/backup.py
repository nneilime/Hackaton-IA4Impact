"""Sauvegarde et restauration des métadonnées SQLite (version 2.0).

- Sauvegarde transactionnelle via l'API de sauvegarde de SQLite (cohérente même application en marche).
- Contrôle d'intégrité (PRAGMA integrity_check) et empreinte SHA-256 de chaque sauvegarde.
- Restauration contrôlée : vérification d'intégrité et du schéma AVANT remplacement, sauvegarde automatique
  de la base courante (aucun écrasement sans copie), remplacement atomique.

Les documents originaux (corpus, imports) ne sont jamais concernés : seules les métadonnées (comptes,
décisions, corrections, journal, résultats) le sont.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import sqlite3
from pathlib import Path

from .config import DATA_DIR, DB_PATH

BACKUP_DIR = Path(os.environ.get("SENTINEL_BACKUPS", DATA_DIR / "backups"))
REQUIRED_TABLES = {"users", "cases", "decisions", "corrections", "audit", "analyses"}


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(path: Path) -> dict:
    """Intégrité SQLite + présence des tables attendues."""
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        ok = con.execute("PRAGMA integrity_check").fetchone()[0]
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        n_users = con.execute("SELECT COUNT(*) FROM users").fetchone()[0] if "users" in tables else 0
        n_dec = con.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] if "decisions" in tables else 0
        con.close()
    except sqlite3.Error as e:
        return {"ok": False, "erreur": str(e)}
    missing = REQUIRED_TABLES - tables
    return {"ok": ok == "ok" and not missing, "integrity": ok, "tables_manquantes": sorted(missing),
            "utilisateurs": n_users, "decisions": n_dec}


def create_backup(db=None, reason: str = "manuelle", source: Path = DB_PATH) -> dict:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    name = f"sentinel-{dt.datetime.now():%Y%m%d-%H%M%S}-{reason}.db"
    dest = BACKUP_DIR / name
    src = db.conn if db is not None else sqlite3.connect(str(source))
    out = sqlite3.connect(str(dest))
    try:
        if db is not None:
            from .db import _lock
            with _lock:
                src.backup(out)
        else:
            src.backup(out)
    finally:
        out.close()
        if db is None:
            src.close()
    chk = verify(dest)
    meta = {"file": name, "path": str(dest), "sha256": _sha(dest), "size": dest.stat().st_size,
            "created_at": dt.datetime.now().isoformat(timespec="seconds"), "reason": reason, "verification": chk}
    dest.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    if not chk["ok"]:
        raise RuntimeError(f"Sauvegarde créée mais invalide : {chk}")
    return meta


def list_backups() -> list:
    out = []
    for m in sorted(BACKUP_DIR.glob("*.json"), reverse=True):
        try:
            out.append(json.loads(m.read_text(encoding="utf-8")))
        except ValueError:
            continue
    return out


def restore(backup: Path, target: Path = DB_PATH) -> dict:
    """Restaure une sauvegarde après vérification ; la base courante est d'abord sauvegardée.
    À exécuter application ARRÊTÉE (commande `python -m sentinel.cli restore`)."""
    backup = Path(backup)
    if not backup.exists():
        raise FileNotFoundError(backup)
    meta_f = backup.with_suffix(".json")
    if meta_f.exists():
        meta = json.loads(meta_f.read_text(encoding="utf-8"))
        if meta.get("sha256") and meta["sha256"] != _sha(backup):
            raise RuntimeError("L'empreinte SHA-256 de la sauvegarde ne correspond pas : fichier altéré, restauration refusée.")
    chk = verify(backup)
    if not chk["ok"]:
        raise RuntimeError(f"Sauvegarde invalide, restauration refusée : {chk}")
    safety = None
    if Path(target).exists():
        safety = create_backup(None, "avant-restauration", source=Path(target))
    tmp = Path(target).with_suffix(".restore-tmp")
    shutil.copy2(backup, tmp)
    for ext in ("-wal", "-shm"):
        p = Path(str(target) + ext)
        if p.exists():
            p.unlink()
    os.replace(tmp, target)
    return {"restaure": str(backup), "verification": chk, "sauvegarde_de_securite": safety["file"] if safety else None}
