# SPDX-License-Identifier: AGPL-3.0-or-later
"""Mémoire vectorielle Qdrant (mode embarqué par défaut : aucun serveur, aucune clé).

Deux collections :
  veille_passages : textes sources verbatim (unité de preuve) + métadonnées filtrables (pays, produit, source)
  veille_records  : enregistrements canoniques validés (Pydantic), interrogeables par similarité + filtres
"""
from __future__ import annotations
import hashlib, json, sys, uuid, warnings
warnings.filterwarnings("ignore", message="Api key is used with an insecure connection")
from dataclasses import asdict
from qdrant_client import QdrantClient, models as qm
from . import config, llm
from .sources import Passage

PASSAGES, RECORDS = "veille_passages", "veille_records"
_client = None


def client() -> QdrantClient:
    global _client
    if _client is None:
        if not config.QDRANT_FORCE_EMBEDDED:
            try:
                c = QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY, check_compatibility=False, timeout=10)
                c.get_collections()          # sonde : serveur joignable et clé acceptée ?
                _client = c
            except Exception as e:
                print(f"[store] Qdrant serveur indisponible ({type(e).__name__}) -> mode embarqué", file=sys.stderr)
        if _client is None:
            config.QDRANT_PATH.mkdir(parents=True, exist_ok=True)
            _client = QdrantClient(path=str(config.QDRANT_PATH))
    return _client


def pid(key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def cached_embed(text: str) -> list[float]:
    p = config.CACHE / f"emb_{hashlib.sha256((config.EMBED_MODEL + text).encode()).hexdigest()}.json"
    if p.is_file():
        return json.loads(p.read_text())
    v = llm.embed(text)
    p.write_text(json.dumps(v))
    return v


def _ensure(name: str, size: int):
    c = client()
    if not c.collection_exists(name):
        c.create_collection(name, vectors_config=qm.VectorParams(size=size, distance=qm.Distance.COSINE))


def _flt(**kw):
    must = [qm.FieldCondition(key=k, match=qm.MatchValue(value=v)) for k, v in kw.items() if v]
    return qm.Filter(must=must) if must else None


def reset():
    """Repart d'un index propre (collections lpc_* uniquement ; les autres collections ne sont jamais touchées)."""
    for name in (PASSAGES, RECORDS):
        if client().collection_exists(name):
            client().delete_collection(name)


def index_passages(passages: list[Passage]) -> int:
    pts = []
    for p in passages:
        v = cached_embed(p.text)
        _ensure(PASSAGES, len(v))
        payload = asdict(p)
        pts.append(qm.PointStruct(id=pid(p.passage_id), vector=v, payload=payload))
    if pts:
        client().upsert(PASSAGES, pts)
    return len(pts)


def get_passage(passage_id: str) -> Passage | None:
    """Retrouve un passage par son identifiant (relecture humaine : on repart du texte source d'origine)."""
    if not client().collection_exists(PASSAGES):
        return None
    points, _ = client().scroll(PASSAGES, scroll_filter=_flt(passage_id=passage_id), limit=1, with_payload=True)
    return Passage(**points[0].payload) if points else None


def search_passages(query: str, k: int = 5, **filters) -> list[dict]:
    v = cached_embed(query)
    if not client().collection_exists(PASSAGES):
        return []
    hits = client().query_points(PASSAGES, query=v, limit=k, query_filter=_flt(**filters), with_payload=True).points
    return [{"score": round(h.score, 4), **h.payload} for h in hits]


def all_passages(**filters) -> list[Passage]:
    if not client().collection_exists(PASSAGES):
        return []
    out, off = [], None
    while True:
        pts, off = client().scroll(PASSAGES, scroll_filter=_flt(**filters), limit=256, offset=off, with_payload=True)
        out += [Passage(**p.payload) for p in pts]
        if off is None:
            break
    return sorted(out, key=lambda p: p.passage_id)


def record_text(r: dict) -> str:
    return (f"{r['product']} {r['country']} culture {r.get('crop_original') or ''} cible {r.get('target_original') or ''} "
            f"dose {r.get('dose_original') or 'non indiquée'} statut {r.get('authorization_status') or ''}")


def upsert_records(records: list[dict]) -> int:
    pts = []
    for r in records:
        v = cached_embed(record_text(r))
        _ensure(RECORDS, len(v))
        pts.append(qm.PointStruct(id=pid(r["record_id"]), vector=v, payload=r))
    if pts:
        client().upsert(RECORDS, pts)
    return len(pts)


def search_records(query: str, k: int = 8, **filters) -> list[dict]:
    if not client().collection_exists(RECORDS):
        return []
    hits = client().query_points(RECORDS, query=cached_embed(query), limit=k, query_filter=_flt(**filters),
                                 with_payload=True).points
    return [{"score": round(h.score, 4), **h.payload} for h in hits]


def all_records(**filters) -> list[dict]:
    if not client().collection_exists(RECORDS):
        return []
    out, off = [], None
    while True:
        pts, off = client().scroll(RECORDS, scroll_filter=_flt(**filters), limit=256, offset=off, with_payload=True)
        out += [p.payload for p in pts]
        if off is None:
            break
    return out


def mode() -> str:
    return "serveur " + config.QDRANT_URL if getattr(client(), "_client", None).__class__.__name__ != "QdrantLocal" else "embarqué"
