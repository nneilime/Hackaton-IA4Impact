"""CLI : recherche ou contexte prêt pour une IA.

    .venv/bin/python -m rag "j'ai perdu ma carte" --bank CE
    .venv/bin/python -m rag "j'ai perdu ma carte" --bank CE --context
"""
import argparse
import json

from rag.retriever import Retriever

ap = argparse.ArgumentParser()
ap.add_argument("query")
ap.add_argument("--bank", choices=["CE", "BP", "BOTH"], default=None)
ap.add_argument("-k", type=int, default=5)
ap.add_argument("--context", action="store_true", help="affiche le contexte complet à injecter dans le prompt")
a = ap.parse_args()
r = Retriever()
if a.context:
    print(r.context(a.query, bank=a.bank, k=a.k)["context"])
else:
    for h in r.search(a.query, bank=a.bank, k=a.k):
        print(json.dumps(h, ensure_ascii=False))
