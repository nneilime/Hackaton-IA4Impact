"""Instantané des résultats des 22 règles sur les 55 dossiers du corpus (extractions en cache, sans OCR).

    python scripts/snapshot_corpus.py sortie.json            # écrit l'instantané
    python scripts/snapshot_corpus.py nouveau.json ancien.json   # écrit puis compare à un instantané précédent

Sert de test de non-régression : toute différence de statut entre deux versions est listée et doit être
expliquée (changement de politique documenté) ou corrigée.
"""
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
_tmp = tempfile.mkdtemp(prefix="snap-")
os.environ["SENTINEL_DB"] = str(Path(_tmp) / "snap.db")
os.environ.setdefault("SENTINEL_IMPORTS", str(Path(_tmp) / "imports"))

from sentinel.b2parser import parse_b2  # noqa: E402
from sentinel.corpus import pair_documents, sha256_file  # noqa: E402
from sentinel.pipeline import load_extraction  # noqa: E402
from sentinel.ocr.extract import collect_executants  # noqa: E402
from sentinel.rules import run_rules, summarize  # noqa: E402


def snapshot():
    out = {}
    for p in pair_documents():
        txt = parse_b2(p["txt"])
        ext = load_extraction(p["jpg"], sha256_file(p["jpg"]), allow_compute=False)
        if ext is None:
            out[p["id"]] = {"erreur": "extraction absente du cache"}
            continue
        ext["executants"] = collect_executants(ext.get("tables", {}).get("Z10", []))
        res = run_rules(txt, ext)
        out[p["id"]] = {r["rule_id"]: r["status"] for r in res}
    return out


def stats(snap):
    c = Counter(s for v in snap.values() for s in v.values())
    cases_ano = sum(1 for v in snap.values() if "ANOMALIE" in v.values())
    cases_nv = sum(1 for v in snap.values() if "NON_VERIFIABLE" in v.values())
    clean = sum(1 for v in snap.values() if not ({"ANOMALIE", "NON_VERIFIABLE", "ERREUR_TECHNIQUE"} & set(v.values())))
    return {"controles": dict(c), "dossiers": len(snap), "avec_anomalie": cases_ano, "avec_nv": cases_nv, "sans_ecart": clean}


if __name__ == "__main__":
    snap = snapshot()
    Path(sys.argv[1]).write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Nouveau :", stats(snap))
    if len(sys.argv) > 2:
        old = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        print("Ancien  :", stats(old))
        diffs = [(cid, rid, old.get(cid, {}).get(rid), st) for cid, v in snap.items() for rid, st in v.items()
                 if old.get(cid, {}).get(rid) != st]
        print(f"{len(diffs)} différence(s) de statut")
        for d in diffs:
            print("  {} {} : {} → {}".format(*d))
