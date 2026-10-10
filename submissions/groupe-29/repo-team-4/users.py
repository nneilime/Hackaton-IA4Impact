"""Manage the reviewer / admin accounts of the review API.

Usage:
    python users.py add <username> [--name "Display Name"] [--admin] [--password PW]   prints the API token (once)
    python users.py password <username> <password>                     sets the web login password
    python users.py demo                                               creates / resets agent/agent and admin/admin
    python users.py token <username>                                   issues a new token, the old one stops working
    python users.py list
    python users.py deactivate <username>                              their assigned tickets go back to the queue
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline import review, store


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=store.DEFAULT_DB, help="database file (default: %(default)s)")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    add.add_argument("username")
    add.add_argument("--name", help="display name")
    add.add_argument("--admin", action="store_true")
    add.add_argument("--password", help="web login password")
    pw = sub.add_parser("password")
    pw.add_argument("username")
    pw.add_argument("password")
    sub.add_parser("demo")
    sub.add_parser("token").add_argument("username")
    sub.add_parser("list")
    sub.add_parser("deactivate").add_argument("username")
    args = parser.parse_args()

    if not args.db.exists():
        parser.error(f"{args.db} does not exist, run create_db.py first")
    with store.connect(args.db) as conn:
        store.create_schema(conn)  # older databases get the newer tables / columns
        try:
            if args.command == "add":
                user, token = review.create_user(conn, args.username, args.name, "admin" if args.admin else "reviewer",
                                                 args.password)
                print(f"created {user['role']} {user['username']} (id {user['id']})\ntoken: {token}")
            elif args.command == "password":
                review.set_password(conn, args.username, args.password)
                print(f"password set for {args.username}")
            elif args.command == "demo":
                for username, password, role in review.ensure_demo_accounts(conn):
                    print(f"{role}: {username} / {password}")
            elif args.command == "token":
                print(f"token: {review.rotate_token(conn, args.username)}")
            elif args.command == "list":
                for u in review.list_users(conn):
                    state = "" if u["active"] else "  (deactivated)"
                    print(f"{u['id']:>3}  {u['username']:<16} {u['role']:<9} {u['active_tickets']} assigned{state}")
            elif args.command == "deactivate":
                user = next((u for u in review.list_users(conn) if u["username"] == args.username), None)
                if user is None:
                    raise review.NotFound(f"no user {args.username!r}")
                review.update_user(conn, user["id"], active=False)
                print(f"deactivated {args.username}")
        except review.ReviewError as e:
            print(e, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
