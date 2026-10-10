"""Initialiser ou relancer un classement partagé depuis le poste serveur."""

import argparse
from datetime import date
from scripts.database import connection, safe
from scripts.scoring import schedule, run_job


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--as-of-date", type=date.fromisoformat, default=date(2026, 1, 1)
    )
    args = parser.parse_args()
    run_id, created = schedule(None, args.as_of_date)
    if created:
        run_job(run_id, None)
    with connection() as conn:
        print(
            safe(
                conn.execute(
                    "select id,statut,revision,progression,nb_equipements,erreur from public.calculs where id=%s",
                    [run_id],
                ).fetchone()
            )
        )


if __name__ == "__main__":
    main()
