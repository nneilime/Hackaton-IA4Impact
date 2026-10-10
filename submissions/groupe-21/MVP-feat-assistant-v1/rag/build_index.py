#!/usr/bin/env python3
"""Construit l'index RAG à partir de data/faq_corpus.jsonl.

Sorties (rag/index/) :
- chunks.jsonl          fragments indexés (en-tête contextuel + texte), métadonnées
- docs.jsonl            fiches complètes (réponse intégrale), servies au chatbot
- meta.json             dates, volumes

Index lexical uniquement : aucun modèle n'est téléchargé ni exécuté localement.

    .venv/bin/python rag/build_index.py
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MAX_WORDS = 220  # au-delà, la réponse est découpée en plusieurs fragments


def header(d):
    path = " > ".join(x for x in [d["category"], d["subcategory"]] if x)
    return f"{d['bank']} — {path}\nQuestion : {d['question']}"


def split_answer(text, max_words=MAX_WORDS):
    """Découpe aux frontières de blocs (paragraphes, listes), avec 1 bloc de recouvrement."""
    blocks = [b for b in re.split(r"\n\s*\n", text) if b.strip()]
    chunks, cur, n = [], [], 0
    for b in blocks:
        w = len(b.split())
        if cur and n + w > max_words:
            chunks.append(cur)
            cur, n = cur[-1:], len(cur[-1].split())  # recouvrement
        cur.append(b)
        n += w
    if cur:
        chunks.append(cur)
    return ["\n\n".join(c) for c in chunks]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=ROOT / "data" / "faq_corpus.jsonl")
    ap.add_argument("--out", type=Path, default=ROOT / "rag" / "index")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    docs = [json.loads(l) for l in args.corpus.read_text().splitlines() if l.strip()]
    chunks = []
    for d in docs:
        parts = split_answer(d["answer_text"])
        for i, part in enumerate(parts):
            chunks.append({
                "chunk_id": f"{d['id']}#{i}", "doc_id": d["id"], "bank_code": d["bank_code"],
                "category": d["category"], "subcategory": d["subcategory"], "question": d["question"],
                "position": i, "of": len(parts),
                "text": header(d) + "\n\n" + part,
            })

    with open(args.out / "docs.jsonl", "w") as f:
        for d in docs:
            f.write(json.dumps({k: d[k] for k in ["id", "bank_code", "bank", "category", "subcategory", "question", "audience",
                                                  "answer_markdown", "videos", "links", "url", "date_modified", "words"]}, ensure_ascii=False) + "\n")
    with open(args.out / "chunks.jsonl", "w") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    meta = {"built_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "docs": len(docs),
            "chunks": len(chunks),
            "banks": {b: sum(d["bank_code"] == b for d in docs) for b in sorted({d["bank_code"] for d in docs})}}

    (args.out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
