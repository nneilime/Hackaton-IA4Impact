"""Create the SQLite database that holds the processed (facture, bordereau) pairs.

Usage: python create_db.py [--db invoices.db] [--force] [--admin USERNAME] [--demo]

--demo creates the web app's placeholder accounts: agent / agent (reviewer) and admin / admin (manager).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline import review, store


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=store.DEFAULT_DB, help="database file (default: %(default)s)")
    parser.add_argument("--force", action="store_true", help="delete an existing database first")
    parser.add_argument("--admin", metavar="USERNAME", help="also create a first admin account and print its token")
    parser.add_argument("--demo", action="store_true", help="create the demo logins agent/agent and admin/admin")
    args = parser.parse_args()

    if args.db.exists():
        if not args.force:
            print(f"{args.db} already exists, use --force to recreate it", file=sys.stderr)
            return 1
        args.db.unlink()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    with store.connect(args.db) as conn:
        store.create_schema(conn)
        tables = [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
        print(f"Created {args.db} with tables: {', '.join(tables)}")
        if args.admin:
            user, token = review.create_user(conn, args.admin, role="admin")
            print(f"Admin {user['username']} token (shown once): {token}")
        if args.demo:
            for username, password, role in review.ensure_demo_accounts(conn):
                print(f"Demo login ({role}): {username} / {password}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
