#!/usr/bin/env python3
"""Verify actual BVL joins and preserve a complete replayable verification export.

A successful extraction is not legal, licensing or human regulatory validation.
"""
import argparse
import json
from pathlib import Path
from bvl import GermanyBVLAdapter
from exporter import export


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registration',action='append',help='Repeatable; defaults to CONTANS 034346-00')
    parser.add_argument('--offline',type=Path,help='Replay a saved manifest instead of accessing the API')
    parser.add_argument('--out',type=Path,default=Path('out/de-verification'),help='New directory, must not exist')
    args=parser.parse_args()
    adapter=GermanyBVLAdapter(offline_dir=args.offline,
        registrations=args.registration or ([] if args.offline else ['034346-00']))
    report=export(adapter,args.out)
    report.update(scope='Technical extraction/export checks only; not regulatory approval or licence verification',
        snapshots=len(adapter.pages), warnings=adapter.warnings,
        licence_status='manual_review_required', db_status='Not loaded by this command')
    (args.out/'verification_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
