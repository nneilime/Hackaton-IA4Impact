"""Opt-in integration test in a disposable PostgreSQL container; no app DB access.

python3 tests/db_smoke.py --schema /path/to/schema/postgresql.sql --export /path/to/export
Requires a locally available postgres:17 Docker image.
"""
import argparse
import csv
import subprocess
import time
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema',type=Path,required=True)
    parser.add_argument('--export',type=Path,required=True)
    args=parser.parse_args()
    exported=args.export.resolve()
    with (exported/'de_uses.csv').open() as f:
        use_count=sum(1 for _ in csv.DictReader(f))
    cid=subprocess.check_output(['docker','run','--rm','--detach','--network','none',
        '--env','POSTGRES_HOST_AUTH_METHOD=trust','--mount',f'type=bind,source={exported},target=/export,readonly',
        'postgres:17'],text=True).strip()
    def psql(sql,success=True):
        result=subprocess.run(['docker','exec','-i','--workdir','/export',cid,'psql','-X','-q','-U','postgres','-v','ON_ERROR_STOP=1','-v','actor_subject=test:germany-import'],
            input=sql,text=True,capture_output=True)
        if (result.returncode==0)!=success:
            raise AssertionError(result.stderr[-4000:])
        return result.stdout
    try:
        for _ in range(30):
            ready=subprocess.run(['docker','exec',cid,'pg_isready','-U','postgres'],capture_output=True)
            if ready.returncode==0:break
            time.sleep(1)
        else:raise RuntimeError('Temporary PostgreSQL did not become ready')
        psql(args.schema.read_text())
        loader=(exported/'load-regulatory.sql').read_text()
        psql(loader)
        checks=f"""
DO $$ BEGIN
 IF (SELECT count(*) FROM regulatory.authorized_use) <> {use_count} THEN RAISE EXCEPTION 'Use count mismatch'; END IF;
 IF EXISTS (SELECT 1 FROM regulatory.registration_version WHERE review_status <> 'to_verify' OR published_at IS NOT NULL) THEN RAISE EXCEPTION 'Unexpected publication'; END IF;
 IF EXISTS (SELECT 1 FROM regulatory.authorized_use u WHERE NOT EXISTS (SELECT 1 FROM regulatory.use_evidence e WHERE e.use_id=u.id)) THEN RAISE EXCEPTION 'Missing use evidence'; END IF;
 IF EXISTS (SELECT 1 FROM regulatory.registration_version v WHERE NOT EXISTS (SELECT 1 FROM regulatory.registration_evidence e WHERE e.registration_version_id=v.id)) THEN RAISE EXCEPTION 'Missing registration evidence'; END IF;
 IF EXISTS (SELECT 1 FROM regulatory.current_regulatory_uses) THEN RAISE EXCEPTION 'Unreviewed data is visible'; END IF;
 IF EXISTS (SELECT 1 FROM regulatory.application_rule WHERE dose_min IS NOT NULL AND dose_unit_code IS NULL) THEN RAISE EXCEPTION 'Missing unit'; END IF;
END $$;
"""
        psql(checks)
        psql(loader,success=False)
        psql(checks)
        psql("UPDATE regulatory.source_snapshot SET sha256=repeat('a',64);",success=False)
        print(f'PASS: PostgreSQL 17 schema, {use_count} uses, evidence links, unpublished records, immutable snapshots and duplicate-import rollback')
    finally:
        subprocess.run(['docker','stop','--time','1',cid],check=True,capture_output=True)


if __name__=='__main__':main()
