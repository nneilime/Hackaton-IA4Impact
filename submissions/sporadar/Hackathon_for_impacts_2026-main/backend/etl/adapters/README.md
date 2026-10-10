# Run the France and Germany adapters

These are independent scheduled ingestion services. France downloads ANSES E-Phy
exports; Germany collects the BVL API. Both write to the existing flat PostgreSQL
schema and retain source snapshots and evidence. CSV-only export is also available.

## Prerequisites

- Docker with the Compose plugin, running locally or on an always-on host.
- A reachable PostgreSQL database with the application's flat schema already
  installed. The adapters do not create or migrate application tables. The
  separate `regulatory` schema is not the scheduled services' target.
- Database credentials with permission to import data, and internet access to
  the official source for live collection. No AI API key is required.
- For local Python commands instead of Docker: Python 3.12 is recommended,
  matching the Docker images.

## Start France with Docker

From the repository root:

```sh
cd backend/etl/adapters/france
cp .env.example .env
```

Only copy the example for a new installation; preserve an existing `.env`.
On Windows PowerShell, use `Copy-Item .env.example .env` instead of `cp`.
Edit the country directory's `.env` with your database connection:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
REFRESH_INTERVAL_SECONDS=604800
RETRY_INTERVAL_SECONDS=300
```

Replace the placeholders and retain any server-required TLS parameters. Inside
Docker, `localhost` means the adapter container. For PostgreSQL on the Docker
Desktop host, use `host.docker.internal`; for a team server, use its reachable
hostname. Each adapter reads its own `.env`, not the repository root's file.

Then, from the same country directory:

```sh
docker compose build
docker compose run --rm france python main.py --check-db
docker compose up -d
docker compose logs -f --tail=50 france
```

`--check-db` is a read-only connection/schema check. `up -d` starts the scheduled
service, which imports immediately if it has no previous successful run.
Press Ctrl+C to leave the log viewer; the detached service continues running.

## Start Germany with Docker

In a new terminal, from the repository root:

```sh
cd backend/etl/adapters/germany
cp .env.example .env
```

Set `DATABASE_URL` to the same flat database used by France. Germany supports an
optional registration scope in its `.env`:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
REFRESH_INTERVAL_SECONDS=604800
RETRY_INTERVAL_SECONDS=300
BVL_REGISTRATIONS=034346-00
```

`034346-00` selects the CONTANS pilot. Use comma-separated registration numbers
for multiple products, or leave `BVL_REGISTRATIONS=` empty to collect all
registrations. Full collection can take substantially longer.

```sh
docker compose build
docker compose run --rm germany python main.py --check-db
docker compose up -d
docker compose logs -f --tail=50 germany
```

The two Compose projects can run together. They have independent schedules,
advisory locks, and persistent volumes. The repository's root Compose command
does not start these adapters; use their country directories.

## Scheduling, status and stopping

The default refresh interval is seven days. The last successful `collection_runs`
record determines when another run is due across restarts. Failed runs retry with
backoff, starting at 300 seconds and capped at one hour. Missed refreshes run when
the service returns. Continuous operation requires Docker and the host to remain
running and awake.

Run these commands from the relevant country directory:

```sh
docker compose ps
docker compose logs --tail=100
docker compose stop
# Start again, or apply changed .env values / source code:
docker compose up -d --build
```

A healthy container indicates process liveness. Check logs and `collection_runs`
for actual refresh success. Snapshots persist in the `france_state` or
`germany_state` volume in that country's Compose project. Retention is unbounded;
monitor disk space. `docker compose down` retains named volumes; adding `-v`
deletes those snapshots.

## Run a single database refresh

From `backend/etl/adapters/france/`:

```sh
docker compose run --rm france python main.py --once
# Force processing even if the next scheduled run is not due:
docker compose run --rm france python main.py --once --force
```

From `backend/etl/adapters/germany/`:

```sh
docker compose run --rm germany python main.py --once
docker compose run --rm germany python main.py --once --force
```

These commands write to the configured database. `--once` can exit without an
import if it is not due. If a scheduled instance is already collecting, the
advisory lock prevents an overlapping import. For Germany recovery from an
existing complete snapshot, see the [Germany guide](germany/README.md).

## Local Python setup

From either country directory, create a fresh virtual environment. Recreate it
when moving the checkout because virtual environments contain absolute paths.

macOS / Linux:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Direct Python execution does **not** load `.env`. Set environment variables in
your shell before running the service:

```sh
export DATABASE_URL='postgresql://USER:PASSWORD@HOST:5432/DATABASE'
# Germany only; omit for all registrations:
export BVL_REGISTRATIONS='034346-00'
python main.py --check-db
python main.py --once
# Continuous foreground service; Ctrl+C requests shutdown:
python main.py
```

In PowerShell, set variables using `$env:DATABASE_URL = 'postgresql://USER:PASSWORD@HOST:5432/DATABASE'`
and, for Germany, `$env:BVL_REGISTRATIONS = '034346-00'`.
`REFRESH_INTERVAL_SECONDS` and `RETRY_INTERVAL_SECONDS` can also be set in the
shell. Local snapshots default to `state/` beside `main.py`; set `DATA_DIR` to
choose another directory. Local Python does not provide Docker's automatic restart.

## Export CSV files without importing into the database

Use the activated local Python environment above. These export commands need no
database connection. Each output directory must be new; choose another name on
subsequent runs.

France, from `backend/etl/adapters/france/`:

```sh
python exporter.py --output out/france-export
python validate.py out/france-export --report out/france-export/manual-validation.json
```

Germany, from `backend/etl/adapters/germany/`:

```sh
# Live pilot; omit --registration for all registrations.
python exporter.py --registration 034346-00 --out out/contans
# Offline demonstration; the bundled data is explicitly synthetic.
python exporter.py --offline fixtures/de --out out/demo
# Replay a saved export without downloading again.
python exporter.py --offline out/contans --out out/contans-replay
```

Preserve the complete export bundle, including raw data, manifest, evidence and
validation reports. See the country guides for source semantics and SQL loaders.

## Tests

From each country directory with its environment activated:

```sh
python -m unittest discover -s tests -v
```

Run the suites separately because they use local module names. Database tests
are skipped unless `TEST_DATABASE_URL` points to a disposable test database.
Germany also provides `python tests/service_smoke.py`, which builds its image and
uses an isolated PostgreSQL 17 container; see its README for prerequisites.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Compose says `DATABASE_URL` is missing | Create/edit `.env` in the country directory and run Compose there. |
| Python says `DATABASE_URL is required` | Set the shell variable; direct Python does not read `.env`. |
| Connection refused or timed out | Check the database hostname, port, network access and TLS settings; container `localhost` is not the host machine. |
| Schema check fails | Confirm the database has the application's flat schema; these services do not install it. |
| No refresh after startup | Check the persisted schedule and logs; use `--once --force` for an intentional immediate refresh. |
| Import rejected or retrying | Read logs for empty/incomplete snapshots, large count drops or reviewed-data protection; resolve the reported condition before retrying. |
| Export directory already exists | Choose a new output path to retain previous evidence. |
| Python import fails after moving files | Recreate `.venv`, install requirements, and run from the correct country directory. |

## Layout and further details

Both `france/` and `germany/` contain `main.py`, `exporter.py`, `tests/`,
`requirements.txt`, `Dockerfile`, `compose.yaml`, and `.env.example`.
France adds `validate.py`; Germany adds `verify.py`, the `bvl/` package, and
synthetic `fixtures/de/` data. Local `.env`, `.venv/`, `state/`, and `out/` are
ignored by Git. Historical copied backups were preserved in ignored `_archive/`.

- [France: source behavior and operational details](france/README.md)
- [Germany: source behavior, replay and integration tests](germany/README.md)

The former top-level `adapters/France/` and `adapters/Germany/` paths are now
`backend/etl/adapters/france/` and `backend/etl/adapters/germany/`. Germany's
`run_de.py` became `exporter.py`, `verify_de.py` became `verify.py`, and its nested
`adapters/` package became `bvl/`. France's `validate_france_csv.py` became
`validate.py`. Update external scripts using the old paths.
