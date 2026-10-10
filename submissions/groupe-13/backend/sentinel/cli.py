"""Ligne de commande iMSA Sentinel.

    python -m sentinel.cli init        # extrait l'archive (sécurisé) et construit le manifeste
    python -m sentinel.cli extract     # (ré)extrait les 55 bordereaux par OCR local -> data/cache/ocr
    python -m sentinel.cli analyze     # applique les 22 règles à tous les dossiers -> data/sentinel.db
    python -m sentinel.cli stats       # affiche les résultats réels par règle et par dossier
    python -m sentinel.cli serve       # lance l'application (http://127.0.0.1:8000)
    python -m sentinel.cli sync        # analyse les dossiers nouveaux ou modifiés (TXT, image, versions)
    python -m sentinel.cli cache       # état du cache OCR (valide, obsolète, corrompu)
    python -m sentinel.cli backup      # sauvegarde vérifiée des métadonnées (data/backups)
    python -m sentinel.cli restore F   # restaure une sauvegarde (application arrêtée ; copie de sécurité préalable)
    python -m sentinel.cli reset-password NOM   # récupération locale d'un compte (mot de passe saisi, jamais affiché)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict


def _extract_one(args):
    jpg, sha, force = args
    from .ocrcache import load_or_compute
    t = time.time()
    ext = load_or_compute(jpg, sha, allow_compute=True, force=force)
    st = (ext.get("cache") or {}).get("statut")
    return jpg.name, ("cache valide" if st == "valide" else f"{st} ({round(time.time() - t, 1)} s)")


def cmd_extract(force: bool, workers: int):
    from multiprocessing import Pool
    from .config import OCR_CACHE_DIR
    from .corpus import pair_documents, sha256_file
    OCR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    jobs = [(p["jpg"], sha256_file(p["jpg"]), force) for p in pair_documents() if p.get("jpg")]
    print(f"{len(jobs)} bordereaux à traiter ({workers} processus)")
    with Pool(workers) as pool:
        for name, info in pool.imap_unordered(_extract_one, jobs):
            print(f"  {name}: {info}", flush=True)


def cmd_stats():
    from .db import DB
    db = DB()
    rows = db.q("SELECT case_id, rule_id, status FROM check_results ORDER BY rule_id, case_id")
    by = defaultdict(Counter)
    an = defaultdict(list)
    for r in rows:
        by[r["rule_id"]][r["status"]] += 1
        if r["status"] in ("ANOMALIE", "NON_VERIFIABLE"):
            an[r["rule_id"]].append(f"{r['case_id']}{'' if r['status'] == 'ANOMALIE' else ' (n.v.)'}")
    print(f"{'Règle':6} {'évaluables':>10} {'conformes':>9} {'anomalies':>9} {'non vérif.':>10} {'n/a':>4} {'erreurs':>7}")
    for rid in sorted(by):
        c = by[rid]
        ev = sum(v for k, v in c.items() if k != "NON_APPLICABLE")
        print(f"{rid:6} {ev:>10} {c['CONFORME']:>9} {c['ANOMALIE']:>9} {c['NON_VERIFIABLE']:>10} {c['NON_APPLICABLE']:>4} {c['ERREUR_TECHNIQUE']:>7}"
              f"   {', '.join(an[rid])}")
    cases = db.q("SELECT id, n_anomalies, n_nv, pairing_status FROM cases ORDER BY id")
    print(f"\n{len(cases)} dossiers — {sum(1 for c in cases if c['n_anomalies'])} avec anomalie — "
          f"{sum(1 for c in cases if c['n_nv'])} avec contrôle non vérifiable — "
          f"{sum(1 for c in cases if not c['n_anomalies'] and not c['n_nv'])} sans écart")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sentinel")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    e = sub.add_parser("extract"); e.add_argument("--force", action="store_true"); e.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    sub.add_parser("analyze")
    sub.add_parser("stats")
    sub.add_parser("sync")
    sub.add_parser("cache")
    sub.add_parser("backup")
    r = sub.add_parser("restore"); r.add_argument("fichier"); r.add_argument("--oui", action="store_true", help="ne pas demander de confirmation")
    rp = sub.add_parser("reset-password"); rp.add_argument("username")
    ca = sub.add_parser("create-admin"); ca.add_argument("username"); ca.add_argument("--nom", default="Administrateur")
    s = sub.add_parser("serve"); s.add_argument("--host", default="127.0.0.1"); s.add_argument("--port", type=int, default=8000)
    s.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "init":
        from .db import DB
        from .pipeline import init_corpus
        print(json.dumps(init_corpus(DB(), force_extract=True), ensure_ascii=False, indent=1))
    elif a.cmd == "extract":
        cmd_extract(a.force, a.workers)
    elif a.cmd == "analyze":
        from . import ENGINE_VERSION, RULESET_VERSION
        from .db import DB
        from .pipeline import analyze_all, init_corpus
        db = DB()
        init_corpus(db)
        r = analyze_all(db, "cli", progress=lambda d, t, c: print(f"  {d}/{t} {c}", flush=True))
        db.meta_set("last_versions", [ENGINE_VERSION, RULESET_VERSION])
        print(r)
    elif a.cmd == "stats":
        cmd_stats()
    elif a.cmd == "sync":
        from .db import DB
        from .pipeline import init_corpus, sync_cases
        db = DB(); init_corpus(db)
        print(sync_cases(db, "cli", progress=lambda d, t, c: print(f"  {d}/{t} {c}", flush=True)))
    elif a.cmd == "cache":
        from .ocrcache import status_report
        print(json.dumps(status_report(), ensure_ascii=False, indent=1))
    elif a.cmd == "backup":
        from .backup import create_backup
        from .db import DB
        b = create_backup(DB(), "cli")
        print(f"Sauvegarde vérifiée : {b['path']}\nSHA-256 : {b['sha256']}")
    elif a.cmd == "restore":
        from pathlib import Path
        from .backup import restore, verify
        f = Path(a.fichier)
        print(f"Vérification : {verify(f)}")
        if not a.oui and input("Arrêtez l'application avant de continuer. Restaurer cette sauvegarde ? (oui/non) ").strip().lower() != "oui":
            print("Restauration annulée."); return
        print(json.dumps(restore(f), ensure_ascii=False, indent=1))
    elif a.cmd in ("reset-password", "create-admin"):
        import getpass
        from .db import DB
        db = DB()
        pw = getpass.getpass("Nouveau mot de passe (8 caractères minimum, non affiché) : ")
        if pw != getpass.getpass("Confirmer : "):
            print("Les mots de passe ne correspondent pas."); sys.exit(1)
        try:
            if a.cmd == "create-admin":
                db.create_user(a.username, a.nom, "admin", pw)
                print(f"Compte administrateur « {a.username} » créé.")
            elif db.set_password(a.username, pw):
                print(f"Mot de passe de « {a.username} » réinitialisé ; ses sessions ouvertes sont fermées.")
            else:
                print(f"Compte « {a.username} » introuvable."); sys.exit(1)
        except Exception as e:
            print(f"Échec : {e}"); sys.exit(1)
        db.audit(None, "compte.recuperation_locale", a.username, {"commande": a.cmd})
    elif a.cmd == "serve":
        import socket
        import threading
        import webbrowser
        import uvicorn
        # port déjà occupé (autre fenêtre ouverte, autre logiciel) : on prend le suivant libre
        port = a.port
        for cand in range(a.port, a.port + 30):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind((a.host, cand))
                    port = cand
                    break
                except OSError:
                    continue
        if port != a.port:
            print(f"Le port {a.port} est déjà utilisé : utilisation du port {port}.")
        a.port = port
        url = f"http://{a.host}:{a.port}"
        if not a.no_browser:
            threading.Timer(2.0, lambda: webbrowser.open(url)).start()
        print(f"iMSA Sentinel : {url}  (Ctrl+C pour arrêter)")
        uvicorn.run("sentinel.api:app", host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
