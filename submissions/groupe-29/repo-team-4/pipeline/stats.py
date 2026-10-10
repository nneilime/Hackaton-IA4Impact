"""Figures for the manager screens (dashboard, clinics, map, regional funds).

A pair's verdict is the reviewer's final word once its ticket is resolved, the algorithm's guess until then.
Amounts are in cents:
  amount        what the B2 file bills (prestations + honoraires); the form's total when the file's layout is broken
                (check X1), since its amounts are then sliced from the wrong positions
  discrepancy   |file prestations - form sous-total 1+2+3| + |file honoraires - form sous-total 4| (0 when the
                file's layout is broken, for the same reason)
  at risk       the billed amount of the pairs whose verdict is ISSUES
"""

from __future__ import annotations

import sqlite3
from typing import Any

FLAG_THRESHOLD = 15.0  # % of ISSUES above which a clinic is flagged (web/src/lib/risk.ts uses the same)

PAIR_FIGURES = """
    SELECT p.id AS pair_id, p.name, p.clinic_id, p.algo_verdict, p.risk_score, p.image_path IS NOT NULL AS has_image,
           t.id AS ticket_id, t.status AS ticket_status, t.final_verdict, t.final_category, t.escalated,
           COALESCE(t.final_verdict, p.algo_verdict) AS verdict,
           f.numero_facture, f.date_fichier,
           CASE WHEN x1.status = 'FAIL' THEN COALESCE(b.montant_total, 0)
                ELSE COALESCE(f.total_prestations, 0) + COALESCE(f.total_honoraires, 0) END AS amount,
           CASE WHEN x1.status = 'FAIL' THEN 0
                ELSE COALESCE(ABS(f.total_prestations - b.sous_total_123), 0)
                     + COALESCE(ABS(f.total_honoraires - b.sous_total_4), 0) END AS discrepancy,
           (SELECT COUNT(*) FROM checks k WHERE k.pair_id = p.id AND k.status = 'FAIL') AS failed_checks,
           (SELECT COUNT(*) FROM checks k WHERE k.pair_id = p.id AND k.status = 'FAIL' AND k.risk = 'fraud'
              AND k.ocr_suspect = 0) AS fraud_signals
    FROM pairs p
    LEFT JOIN tickets t ON t.pair_id = p.id
    LEFT JOIN factures f ON f.pair_id = p.id
    LEFT JOIN bordereaux b ON b.pair_id = p.id
    LEFT JOIN checks x1 ON x1.pair_id = p.id AND x1.code = 'X1'
"""


def _clinic_rows(conn: sqlite3.Connection, where: str = "", params: tuple = ()) -> list[dict[str, Any]]:
    sql = f"""
        WITH figures AS ({PAIR_FIGURES})
        SELECT c.*,
               COUNT(x.pair_id) AS invoices,
               COALESCE(SUM(x.verdict = 'ISSUES'), 0) AS issues,
               COALESCE(SUM(CASE WHEN x.verdict = 'ISSUES' THEN x.amount END), 0) AS at_risk,
               COALESCE(SUM(x.amount), 0) AS billed,
               COALESCE(SUM(x.discrepancy), 0) AS discrepancy,
               COALESCE(SUM(x.ticket_status != 'resolved'), 0) AS pending,
               COALESCE(SUM(x.final_category = 'suspected_fraud'), 0) AS confirmed_fraud,
               (SELECT COUNT(*) FROM clinic_reports r WHERE r.clinic_id = c.id) AS reports
        FROM clinics c LEFT JOIN figures x ON x.clinic_id = c.id
        {where}
        GROUP BY c.id ORDER BY c.name
    """
    out = []
    for r in conn.execute(sql, params):
        row = dict(r)
        row["error_rate"] = round(100 * row["issues"] / row["invoices"], 1) if row["invoices"] else 0.0
        row["flagged"] = row["error_rate"] > FLAG_THRESHOLD
        out.append(row)
    return out


def clinics(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return _clinic_rows(conn)


def clinic(conn: sqlite3.Connection, clinic_id: int) -> dict[str, Any] | None:
    rows = _clinic_rows(conn, "WHERE c.id = ?", (clinic_id,))
    return rows[0] if rows else None


def clinic_invoices(conn: sqlite3.Connection, clinic_id: int) -> list[dict[str, Any]]:
    """One row per pair of the clinic, most recent file first."""
    return [dict(r) for r in conn.execute(
        f"SELECT * FROM ({PAIR_FIGURES}) WHERE clinic_id = ? ORDER BY date_fichier DESC, numero_facture DESC",
        (clinic_id,))]


def overview(conn: sqlite3.Connection) -> dict[str, Any]:
    row = dict(conn.execute(f"""
        WITH figures AS ({PAIR_FIGURES})
        SELECT COUNT(*) AS invoices,
               COALESCE(SUM(verdict = 'ISSUES'), 0) AS issues,
               COALESCE(SUM(algo_verdict = 'ISSUES'), 0) AS algo_issues,
               COALESCE(SUM(ticket_status = 'resolved'), 0) AS resolved,
               COALESCE(SUM(ticket_status != 'resolved'), 0) AS pending,
               COALESCE(SUM(ticket_status = 'open' AND escalated = 1), 0) AS escalated,
               COALESCE(SUM(final_category = 'suspected_fraud'), 0) AS confirmed_fraud,
               COALESCE(SUM(CASE WHEN final_category = 'suspected_fraud' THEN amount END), 0) AS confirmed_fraud_amount,
               COALESCE(SUM(CASE WHEN verdict = 'ISSUES' THEN amount END), 0) AS at_risk,
               COALESCE(SUM(amount), 0) AS billed,
               COALESCE(SUM(discrepancy), 0) AS discrepancy,
               COALESCE(SUM(ticket_status = 'resolved' AND final_verdict = algo_verdict), 0) AS agreed
        FROM figures""").fetchone())
    clinic_rows = clinics(conn)
    row["clinics"] = len(clinic_rows)
    row["flagged_clinics"] = sum(c["flagged"] for c in clinic_rows)
    row["error_rate"] = round(100 * row["issues"] / row["invoices"], 1) if row["invoices"] else 0.0
    row["agreement_rate"] = round(100 * row["agreed"] / row["resolved"], 1) if row["resolved"] else None
    row["reports"] = conn.execute("SELECT COUNT(*) FROM clinic_reports").fetchone()[0]
    row["top_failed_checks"] = [dict(r) for r in conn.execute(
        "SELECT code, label, COUNT(*) AS count FROM checks WHERE status = 'FAIL' GROUP BY code, label "
        "ORDER BY count DESC, code LIMIT 6")]
    return row
