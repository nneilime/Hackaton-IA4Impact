# France scheduled ingestion service

For setup, Docker startup, local Python, CSV export and troubleshooting,
see the [shared run guide](../README.md).

`main.py` runs continuously. With no prior successful run it imports immediately,
then refreshes every seven days (604800 seconds). E-Phy exports, raw snapshots,
CSV evidence and validation reports are retained in a persistent Docker volume.
The last successful `collection_runs` row determines the next due time across
restarts. A changed interval takes effect after restarting the service.

## One-time deployment

Run the commands below from `backend/etl/adapters/france/` (relative to the repository root).

Create `.env` from `.env.example`, set `DATABASE_URL`, then:

```sh
docker compose up -d --build
```

No manual weekly command is needed. Docker restarts the process on failure or
when Docker restarts. On a laptop it runs only while the machine is awake and
Docker is running; deploy the same directory to an always-on Docker host for
uninterrupted operation. Missed refreshes run when the service returns.

```sh
docker compose logs -f --tail=50
docker compose ps
docker compose stop
```

`REFRESH_INTERVAL_SECONDS` defaults to 604800; `RETRY_INTERVAL_SECONDS` defaults
to 300, backing off up to one hour after failures. Refresh runs are serialized
with a PostgreSQL advisory lock, including across multiple instances. Connections
have bounded connection, lock and statement timeouts. SIGTERM lets the active
transaction complete; forced termination rolls it back. No credentials are logged
or built into the Docker image; `.env` is excluded from Git and the build context.
Use a URL with the server's required TLS parameters when TLS is configured.

## Database behavior

This uses the existing public flat schema; no application tables are created or
migrated. Every refresh has a `collection_runs` record. The five requested CSV
rules are checked before the database transaction. The source SHA-256 is compared
to the last successful run; unchanged archives produce a successful no-change run.

On changed snapshots the service stages CSVs, upserts source-scoped products,
registrations and aliases, replaces adapter-owned authorized uses/evidence, and
commits everything with the success record. Obsolete uses are removed because
the target schema has no use-status column. Missing registrations are retained
with status `unknown`, never inferred to be withdrawn. Other countries and
other ID namespaces are untouched. Source review decisions in this adapter's
namespace stop the refresh for reconciliation rather than being overwritten.
Empty snapshots or a product-count drop exceeding 20% also stop the import.
Failures preserve the previous committed snapshot and are retried.

The adapter uses `P-FR-EPHY-*`, `R-FR-EPHY-*`, `U-FR-EPHY-*`, and `A-FR-EPHY-*` IDs.
It does not merge these into LPC global identities. Only fully authorized uses
of authorized PPP products are imported; excluded uses remain in the snapshot.
`validation_status` is `automatically_extracted` in products, registrations and
uses. `authority_name` is ANSES, status values follow the allowed enum, URLs are
HTTPS and country is FR. Original download timestamps are preserved.

## Operations

`docker compose run --rm france python main.py --check-db` performs a read-only
connection/schema check. `--once` runs a refresh if due and exits; `--once --force`
forces reprocessing. These are diagnostic options, not the normal scheduled mode.
Legacy CSV export is available through `python exporter.py --output NEW_DIRECTORY`.

Container health measures process liveness; refresh failures are recorded in
`collection_runs` and logs and do not falsely report a completed import. Snapshot
retention is unbounded; monitor the persistent volume's disk usage.
