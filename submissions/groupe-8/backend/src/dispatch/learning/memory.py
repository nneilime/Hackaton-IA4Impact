"""Knowledge base of decisions (SQLite): every recommendation the manager accepted, modified or rejected,
with reason, rules applied and their cost. Feeds (1) past-refusal hints during a crisis and (2) the periodic
expert review (learning/review.py). Stores roles and sites, never people's names (no personal data)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA = """CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, logged_at TEXT, crisis TEXT, sim_time_h REAL,
    team TEXT, site TEXT, incident TEXT, commune TEXT, departement TEXT, customers INTEGER, sensitive INTEGER,
    decision TEXT, reason_code TEXT, reason_text TEXT, modifiers TEXT, cost_delta REAL,
    registry_version INTEGER, facts TEXT, simulated INTEGER DEFAULT 0)"""
COLS = ["crisis", "sim_time_h", "team", "site", "incident", "commune", "departement", "customers", "sensitive",
        "decision", "reason_code", "reason_text", "modifiers", "cost_delta", "registry_version", "facts", "simulated"]


class DecisionLog:
    def __init__(self, path: str | Path = ":memory:"):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute(SCHEMA)
        self.db.commit()

    def append(self, entry: dict, simulated: bool = False) -> int:
        row = dict(entry, simulated=int(simulated), sensitive=int(bool(entry.get("sensitive"))),
                   modifiers=json.dumps(entry.get("modifiers") or [], ensure_ascii=False),
                   facts=json.dumps(entry.get("facts"), ensure_ascii=False))
        cur = self.db.execute(f"INSERT INTO decisions (logged_at, {', '.join(COLS)}) VALUES (?{', ?' * len(COLS)})",
                              [datetime.now().isoformat(timespec="seconds")] + [row.get(c) for c in COLS])
        self.db.commit()
        return cur.lastrowid

    def _rows(self, sql: str, args=()) -> list[dict]:
        out = []
        for r in self.db.execute(sql, args).fetchall():
            d = dict(r)
            d["modifiers"] = json.loads(d["modifiers"] or "[]")
            d["facts"] = json.loads(d["facts"]) if d["facts"] else None
            out.append(d)
        return out

    def rejections(self) -> list[dict]:
        return self._rows("SELECT * FROM decisions WHERE decision='rejected' ORDER BY id DESC")

    def similar(self, site: str, commune: str, departement: str | None = None, limit: int = 20) -> list[dict]:
        """Past refusals for the same site sending to the same commune (most recent first)."""
        return self._rows("SELECT * FROM decisions WHERE decision='rejected' AND site=? AND commune=? "
                          "ORDER BY id DESC LIMIT ?", (site, commune, limit))

    def stats(self) -> dict:
        rows = self.db.execute("SELECT decision, COUNT(*) n FROM decisions GROUP BY decision").fetchall()
        by = {r["decision"]: r["n"] for r in rows}
        total = sum(by.values())
        return {"total": total, **by, "refusal_rate": by.get("rejected", 0) / total if total else 0.0}
