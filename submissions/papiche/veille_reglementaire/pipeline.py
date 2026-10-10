# SPDX-License-Identifier: AGPL-3.0-or-later
"""Chaîne complète : collecte -> passages -> Qdrant -> extraction (boucle de contrôle) -> enregistrements."""
from __future__ import annotations
import json, sys, time
from datetime import datetime, timezone
from . import config, extraction_loop, polite_http, qdrant_store, sister_products
from .sources import discover_sources

SOURCES = discover_sources()          # toute source déposée dans sources/ est prise en compte automatiquement


def scope() -> dict:
    return json.loads((config.CONFIG / "scope.json").read_text(encoding="utf-8"))


def collect(only: list[str] | None = None) -> dict:
    """Collecte les sources et garde la preuve de sobriété : combien de requêtes, vers quels serveurs."""
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    results = []
    for name, module in SOURCES.items():
        if only and name not in only:
            continue
        print(f"[collecte] {name} ...", flush=True)
        results.append(module.collect(scope()))
    network = polite_http.summarize_requests(polite_http.read_request_log(since=started_at))
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    with (config.PROCESSED / "collect_runs.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps({"at": started_at, "network": network}, ensure_ascii=False) + "\n")
    print(f"[collecte] {network['total_requests']} requêtes, {network['total_megabytes']} Mo reçus, "
          f"{network['not_modified']} réponse(s) « inchangé » (rien à retélécharger pour ces fichiers)", flush=True)
    return {"results": results, "network": network}


def index(only: list[str] | None = None) -> int:
    if not only:
        qdrant_store.reset()
    n = 0
    for name, mod in SOURCES.items():
        if only and name not in only:
            continue
        try:
            ps = mod.passages(scope())
        except FileNotFoundError:
            print(f"[index] {name}: données brutes absentes (lancer `collect`)", file=sys.stderr)
            continue
        k = qdrant_store.index_passages(ps)
        print(f"[index] {name}: {k} passages -> Qdrant", flush=True)
        n += k
    return n


def extract(limit: int | None = None, product: str | None = None, source: str | None = None,
            per_product: int | None = None) -> dict:
    passages = qdrant_store.all_passages(**({"source_id": source} if source else {}))
    if product:
        passages = [p for p in passages if product.casefold() in p.product.casefold()]
    if per_product:
        seen, keep = {}, []
        for p in passages:
            key = (p.product, p.country)
            if seen.get(key, 0) < per_product:
                seen[key] = seen.get(key, 0) + 1
                keep.append(p)
        passages = keep
    if limit:
        passages = passages[:limit]
    traces, records, hitl = [], [], []
    t0 = time.time()
    for i, p in enumerate(passages, 1):
        tr = extract_one(p)
        traces.append(tr)
        (records if tr["outcome"] == "accepted" else hitl).append(tr["record"] or {"passage_id": p.passage_id})
        print(f"[{i}/{len(passages)}] {p.country} {p.product[:22]:22} {tr['outcome']:8} essais={len(tr['attempts'])} "
              f"({time.time() - t0:.0f}s)", flush=True)
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    _dump("traces.jsonl", traces)
    _dump("records.jsonl", records)
    _dump("hitl.jsonl", hitl)
    qdrant_store.upsert_records(records)
    meta = [{"product": p.product, "country": p.country, "ai": p.ai, "holder": p.holder} for p in qdrant_store.all_passages()]
    _dump("sisters.jsonl", sister_products.detect(meta))
    from . import review                 # import tardif : review utilise pipeline
    review.apply_stored_corrections()
    return {"passages": len(passages), "records": len(records), "hitl": len(hitl)}


def extract_one(p) -> dict:
    return extraction_loop.extract_passage(p)


def _dump(name: str, rows: list[dict]):
    (config.PROCESSED / name).write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else ""),
                                         encoding="utf-8")


def load(name: str) -> list[dict]:
    p = config.PROCESSED / name
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []
