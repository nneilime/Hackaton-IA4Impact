#!/usr/bin/env bash
# Reset the review workflow to a clean start: every ticket unassigned and untreated.
#
#   ./reset.sh            asks for confirmation, then:
#                           - tickets: open, no assignee, no decision, no manager request (escalation) pending
#                           - deleted: decisions, check reviews, fraud reports ("Signaler"), ticket history
#                             (each ticket gets a fresh "created" event)
#   ./reset.sh --sessions also signs everyone out of the web app
#   ./reset.sh --full     deletes the database and rebuilds it from the documents (demo accounts included,
#                         clinic corrections lost); same data folders as dev.sh
#   -y                    no confirmation
#
# Kept by default: the documents, extraction, checks and algorithmic verdicts, the clinics (and their manual
# corrections), the user accounts and their sessions. Works on $INVOICES_DB (default invoices.db).
set -euo pipefail
cd "$(dirname "$0")"

DB="${INVOICES_DB:-invoices.db}"
YES=0 FULL=0 SESSIONS=0
for arg in "$@"; do
  case "$arg" in
    -y|--yes) YES=1 ;;
    --full) FULL=1 ;;
    --sessions) SESSIONS=1 ;;
    -h|--help) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg (see ./reset.sh --help)" >&2; exit 1 ;;
  esac
done

if [ ! -f "$DB" ]; then
  echo "$DB does not exist: run ./dev.sh to create it" >&2
  exit 1
fi

if [ "$YES" -eq 0 ]; then
  if [ "$FULL" -eq 1 ]; then what="DELETE $DB and rebuild it from the documents"; else what="reset every ticket of $DB"; fi
  read -r -p "This will $what. Continue? [y/N] " answer
  case "$answer" in y|Y|yes|oui) ;; *) echo "Cancelled."; exit 0 ;; esac
fi

cp "$DB" "$DB.bak"  # one level of undo: mv invoices.db.bak invoices.db

if [ "$FULL" -eq 1 ]; then
  FACTURES_DIR="${FACTURES_DIR:-$HOME/Downloads/General-main/Factures txt}"
  BORDEREAUX_DIR="${BORDEREAUX_DIR:-factures}"
  IMAGES_DIR="${IMAGES_DIR:-$HOME/Downloads/General-main/Bordereaux jpg}"
  .venv/bin/python create_db.py --db "$DB" --force --demo
  .venv/bin/python ingest.py "$FACTURES_DIR" "$BORDEREAUX_DIR" --images "$IMAGES_DIR" --db "$DB" | tail -2
  echo "Rebuilt $DB (backup of the previous one: $DB.bak)."
  exit 0
fi

INVOICES_DB="$DB" RESET_SESSIONS="$SESSIONS" .venv/bin/python - <<'EOF'
import os
from pipeline import store

conn = store.connect(os.environ["INVOICES_DB"])
store.create_schema(conn)  # an older database gets the current tables first
with conn:
    before = dict(conn.execute(
        "SELECT SUM(status = 'assigned') AS assigned, SUM(status = 'resolved') AS resolved, "
        "SUM(escalated = 1) AS escalated FROM tickets").fetchone())
    reviews = conn.execute("DELETE FROM check_reviews").rowcount
    reports = conn.execute("DELETE FROM clinic_reports").rowcount
    conn.execute("DELETE FROM ticket_events")
    conn.execute(
        "UPDATE tickets SET status = 'open', assignee_id = NULL, final_verdict = NULL, final_category = NULL, "
        "final_comment = NULL, resolved_by = NULL, resolved_at = NULL, escalated = 0, escalation_comment = NULL, "
        "updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')")
    conn.execute(
        "INSERT INTO ticket_events (ticket_id, user_id, action, detail) "
        "SELECT t.id, NULL, 'created', 'algorithmic verdict ' || COALESCE(p.algo_verdict, '?') "
        "FROM tickets t JOIN pairs p ON p.id = t.pair_id")
    sessions = conn.execute("DELETE FROM sessions").rowcount if os.environ["RESET_SESSIONS"] == "1" else None
    tickets = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]

print(f"{tickets} tickets reset to open: {before['assigned'] or 0} were assigned, {before['resolved'] or 0} resolved, "
      f"{before['escalated'] or 0} waiting for a manager.")
print(f"Deleted {reviews} check reviews and {reports} fraud reports; ticket history restarted.")
if sessions is not None:
    print(f"Signed out {sessions} web sessions.")
EOF
echo "Backup of the previous state: $DB.bak (restore with: mv $DB.bak $DB)."
