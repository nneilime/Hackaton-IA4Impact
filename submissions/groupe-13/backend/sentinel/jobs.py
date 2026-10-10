"""Gestion simple et fiable des traitements (version 2.0).

- Chaque traitement (analyse d'un import, réanalyse d'un dossier, réanalyse complète, synchronisation du
  corpus) est enregistré dans la table `jobs` : identifiant, statut, dates, progression, résultat ou erreur.
- Idempotence : soumettre un traitement identique (même type, même cible) déjà en attente ou en cours
  renvoie le traitement existant (un double-clic ne crée pas deux analyses).
- Verrou par dossier : deux analyses d'un même dossier ne s'exécutent jamais simultanément ; une correction
  humaine attend la fin de l'analyse en cours avant de recalculer ; une analyse terminée ne peut donc pas
  être écrasée par une analyse plus ancienne.
- Maintenance exclusive (purge des métadonnées) : elle attend la fin des opérations en cours et les
  opérations demandées pendant la maintenance sont refusées proprement.
- Reprise : au démarrage, un traitement resté « en cours » (arrêt de l'application) est marqué
  « interrompu » ; la synchronisation du corpus recalcule ensuite ce qui doit l'être.

Aucune infrastructure externe (file distribuée, Redis…) : threads + SQLite, suffisants pour un poste local.
"""
from __future__ import annotations

import logging
import threading
import time
import traceback
from collections import defaultdict
from contextlib import contextmanager
from typing import Callable, Optional

from .db import DB, now

log = logging.getLogger("sentinel")

_case_locks: dict = defaultdict(threading.Lock)
_registry_lock = threading.Lock()
_ops = threading.Condition()
_state = {"active": 0, "maintenance": False}


class Busy(RuntimeError):
    """Opération refusée : traitement concurrent ou maintenance en cours."""


@contextmanager
def operation():
    """Enregistre une opération métier ; refusée pendant une maintenance exclusive."""
    with _ops:
        if _state["maintenance"]:
            raise Busy("Maintenance en cours (purge des métadonnées) : réessayez dans quelques secondes.")
        _state["active"] += 1
    try:
        yield
    finally:
        with _ops:
            _state["active"] -= 1
            _ops.notify_all()


@contextmanager
def exclusive(timeout: float = 120):
    """Maintenance : attend la fin des opérations en cours, puis bloque les nouvelles."""
    with _ops:
        if _state["maintenance"]:
            raise Busy("Une maintenance est déjà en cours.")
        _state["maintenance"] = True
        end = time.time() + timeout
        while _state["active"] > 0:
            left = end - time.time()
            if left <= 0:
                _state["maintenance"] = False
                raise Busy("Des traitements sont en cours : maintenance reportée.")
            _ops.wait(left)
    try:
        yield
    finally:
        with _ops:
            _state["maintenance"] = False
            _ops.notify_all()


@contextmanager
def case_lock(cid: str, timeout: float = 600):
    """Verrou d'un dossier : sérialise analyses, réanalyses et corrections du même dossier."""
    with _registry_lock:
        lk = _case_locks[cid]
    if not lk.acquire(timeout=timeout):
        raise Busy(f"Le dossier {cid} est en cours de traitement.")
    try:
        yield
    finally:
        lk.release()


def is_locked(cid: str) -> bool:
    with _registry_lock:
        lk = _case_locks.get(cid)
    return bool(lk and lk.locked())


def active_job(db: DB, kind: Optional[str] = None, target: Optional[str] = None) -> Optional[dict]:
    sql = "SELECT * FROM jobs WHERE status IN ('en_attente','en_cours')"
    args: list = []
    if kind:
        sql += " AND kind=?"; args.append(kind)
    if target:
        sql += " AND target=?"; args.append(target)
    return db.one(sql + " ORDER BY id DESC", tuple(args))


def get(db: DB, job_id: int) -> Optional[dict]:
    return db.one("SELECT * FROM jobs WHERE id=?", (job_id,))


def recent(db: DB, limit: int = 30) -> list:
    return db.q("SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,))


_submit_lock = threading.Lock()


def submit(db: DB, kind: str, target: Optional[str], fn: Callable, created_by: str = "système",
           background: bool = True) -> dict:
    """Crée (ou renvoie) un traitement. `fn(progress)` reçoit une fonction progress(done, total, message)."""
    with _submit_lock:
        existing = active_job(db, kind, target)
        if existing:
            return dict(existing, deja_en_cours=True)
        with db.tx() as c:
            cur = c.execute("INSERT INTO jobs (kind, target, status, created_by, created_at) VALUES (?,?,?,?,?)",
                            (kind, target, "en_attente", created_by, now()))
            jid = cur.lastrowid

    def progress(done, total, message=None):
        with db.tx() as c:
            c.execute("UPDATE jobs SET progress=?, total=?, message=? WHERE id=?", (done, total, message, jid))

    def run():
        t0 = time.time()
        with db.tx() as c:
            c.execute("UPDATE jobs SET status='en_cours', started_at=? WHERE id=?", (now(), jid))
        try:
            with operation():
                res = fn(progress)
            with db.tx() as c:
                c.execute("UPDATE jobs SET status='termine', finished_at=?, duration_s=?, message=COALESCE(?, message) "
                          "WHERE id=?", (now(), round(time.time() - t0, 2), _summary(res), jid))
        except Exception as e:  # noqa
            log.exception("traitement %s", kind)
            with db.tx() as c:
                c.execute("UPDATE jobs SET status='erreur', finished_at=?, duration_s=?, error=? WHERE id=?",
                          (now(), round(time.time() - t0, 2), f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=2)}"[:2000], jid))

    if background:
        threading.Thread(target=run, daemon=True, name=f"job-{jid}").start()
    else:
        run()
    return get(db, jid)


def _summary(res) -> Optional[str]:
    if res is None:
        return None
    if isinstance(res, dict):
        return ", ".join(f"{k}: {v}" for k, v in res.items() if not isinstance(v, (dict, list)))[:500]
    return str(res)[:500]
