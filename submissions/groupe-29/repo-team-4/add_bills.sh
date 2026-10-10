#!/usr/bin/env bash
# Run the whole pipeline on the bills that are not in the database yet.
#
# A new bill is a B2 file <name>.txt in FACTURES_DIR with its scan <name>.jpg in IMAGES_DIR (same name), whose pair is
# not in the database. For those only:
#   1. OCR of the scan                    (ocr.py: factures/<name>/result.json, HF Space)
#   2. OCR of the signed signature boxes  (check_signatures.py --ocr: factures/<name>/signature_boxes.json)
#   3. ingestion                          (ingest.py: extraction, controls, verdict, clinic, open ticket)
# Steps 1-2 skip what is already done, so the script can be run again after a failure.
#
#   ./add_bills.sh            process the new bills
#   ./add_bills.sh -n         only list them
#   ./add_bills.sh NAME ...   process these bills (new or not; existing pairs are refreshed, their tickets kept)
#
# Same data folders as dev.sh: FACTURES_DIR, IMAGES_DIR, BORDEREAUX_DIR (OCR outputs), INVOICES_DB.
set -euo pipefail
cd "$(dirname "$0")"

FACTURES_DIR="${FACTURES_DIR:-$HOME/Downloads/General-main/Factures txt}"
IMAGES_DIR="${IMAGES_DIR:-$HOME/Downloads/General-main/Bordereaux jpg}"
BORDEREAUX_DIR="${BORDEREAUX_DIR:-factures}"
DB="${INVOICES_DB:-invoices.db}"
PY=.venv/bin/python

DRY_RUN=0
NAMES=()
for arg in "$@"; do
  case "$arg" in
    -n|--dry-run) DRY_RUN=1 ;;
    -h|--help) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "unknown option: $arg (see ./add_bills.sh --help)" >&2; exit 1 ;;
    *) NAMES+=("$arg") ;;
  esac
done

if [ ! -f "$DB" ]; then
  echo "$DB does not exist: run ./dev.sh first" >&2
  exit 1
fi

# the bills to process: given on the command line, else the B2 files whose pair is not in the database
if [ ${#NAMES[@]} -eq 0 ]; then
  while IFS= read -r name; do NAMES+=("$name"); done < <(
    FACTURES_DIR="$FACTURES_DIR" DB="$DB" "$PY" - <<'EOF'
import os, sqlite3
from pathlib import Path
known = {r[0] for r in sqlite3.connect(os.environ["DB"]).execute("SELECT name FROM pairs")}
for f in sorted(Path(os.environ["FACTURES_DIR"]).iterdir()):
    if f.suffix.lower() in (".txt", ".json") and f.stem not in known:
        print(f.stem)
EOF
  )
fi

if [ ${#NAMES[@]} -eq 0 ]; then
  echo "No new bill: every B2 file in $FACTURES_DIR is already in $DB."
  exit 0
fi

# a bill needs its scan; report the ones that do not have one
READY=()
for name in "${NAMES[@]}"; do
  if [ -f "$IMAGES_DIR/$name.jpg" ] || [ -f "$IMAGES_DIR/$name.jpeg" ]; then
    READY+=("$name")
  else
    echo "  $name: no scan $IMAGES_DIR/$name.jpg, skipped" >&2
  fi
done
if [ ${#READY[@]} -eq 0 ]; then
  echo "None of the ${#NAMES[@]} bill(s) has its scan: nothing to do." >&2
  exit 1
fi

echo "${#READY[@]} bill(s) to process: ${READY[*]}"
[ "$DRY_RUN" -eq 1 ] && exit 0

echo
echo "== 1/3 OCR of the scans"
if ! "$PY" ocr.py "$IMAGES_DIR" --out "$BORDEREAUX_DIR" --only "${READY[@]}"; then
  echo "Some scans failed or were cut off (see above): they are ingested if a result exists;" \
       "rerun this script, or ocr.py --redo-truncated --only NAME, to retry." >&2
fi

echo
echo "== 2/3 Signature boxes"
"$PY" check_signatures.py "$IMAGES_DIR" "$BORDEREAUX_DIR" --ocr --only "${READY[@]}" \
  || echo "Signature boxes could not all be read: C18 / X3 stay to be checked on the scan." >&2

echo
echo "== 3/3 Ingestion"
"$PY" ingest.py "$FACTURES_DIR" "$BORDEREAUX_DIR" --images "$IMAGES_DIR" --db "$DB" --only "${READY[@]}"

echo
echo "Done: the new tickets are in the agents' queue (refresh the web app)."
