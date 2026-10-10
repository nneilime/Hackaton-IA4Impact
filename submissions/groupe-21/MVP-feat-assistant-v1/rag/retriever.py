"""Recherche lexicale BM25 (fragments et intitulés), fusion RRF. Aucun modèle local : la compréhension
de la question (reformulation, choix de la fiche) est faite par le modèle de langage appelé par API.

    from rag.retriever import Retriever
    r = Retriever()
    r.search("j'ai perdu ma carte", bank="CE")      # -> fiches classées
    r.get("CE-1a2b3c4d5e6f")                        # -> fiche complète
"""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path

from rag.text import tokens, fold

INDEX = Path(__file__).resolve().parent / "index"


class BM25:
    def __init__(self, texts, k1=1.4, b=0.7):
        self.k1, self.b = k1, b
        self.tf = [Counter(tokens(t)) for t in texts]
        self.len = [sum(c.values()) for c in self.tf]
        self.avg = sum(self.len) / max(1, len(self.len))
        df = Counter(t for c in self.tf for t in c)
        n = len(texts)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query, allowed=None):
        q = set(tokens(query))
        out = {}
        for i, tf in enumerate(self.tf):
            if allowed is not None and i not in allowed:
                continue
            s = 0.0
            for t in q:
                f = tf.get(t)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
            if s > 0:
                out[i] = s
        return out


class Retriever:
    def __init__(self, index_dir=INDEX):
        index_dir = Path(index_dir)
        self.meta = json.loads((index_dir / "meta.json").read_text())
        self.docs = {d["id"]: d for d in map(json.loads, (index_dir / "docs.jsonl").read_text().splitlines())}
        self.chunks = [json.loads(l) for l in (index_dir / "chunks.jsonl").read_text().splitlines()]
        self.doc_ids = list(self.docs)
        self.bm25_chunks = BM25([c["text"] for c in self.chunks])
        # Index des intitulés seuls : très discriminant pour une FAQ.
        self.bm25_titles = BM25([f"{d['question']} {d['subcategory']}" for d in self.docs.values()])

    # ------------------------------------------------------------------ catalogue
    def categories(self, bank=None):
        tree = defaultdict(lambda: defaultdict(int))
        for d in self.docs.values():
            if bank in (None, d["bank_code"]):
                tree[d["category"]][d["subcategory"]] += 1
        return {c: dict(s) for c, s in sorted(tree.items())}

    def get(self, doc_id):
        return self.docs.get(doc_id)

    def list_questions(self, bank, category=None, subcategory=None):
        return [{"id": d["id"], "question": d["question"], "category": d["category"], "subcategory": d["subcategory"]}
                for d in self.docs.values()
                if d["bank_code"] == bank and (not category or fold(category) in fold(d["category"]))
                and (not subcategory or fold(subcategory) in fold(d["subcategory"]))]

    # ------------------------------------------------------------------ recherche
    def search(self, query, bank=None, k=6, category=None):
        """Renvoie les k meilleures fiches (dédoublonnées), meilleur fragment en extrait."""
        banks = {"CE", "BP"} if bank in (None, "BOTH", "LES_DEUX") else {bank}
        okc = {i for i, c in enumerate(self.chunks) if c["bank_code"] in banks and (not category or fold(category) in fold(c["category"]))}
        okd = {i for i, d in enumerate(self.doc_ids)
               if self.docs[d]["bank_code"] in banks and (not category or fold(category) in fold(self.docs[d]["category"]))}
        rankings = []  # listes de (doc_id, chunk_idx|None) classées

        def by_chunk(scores):
            best = {}
            for i, s in sorted(scores.items(), key=lambda x: -x[1]):
                best.setdefault(self.chunks[i]["doc_id"], i)
            return list(best.items())

        rankings.append(by_chunk(self.bm25_chunks.scores(query, okc)))
        t = self.bm25_titles.scores(query, okd)
        rankings.append([(self.doc_ids[i], None) for i, _ in sorted(t.items(), key=lambda x: -x[1])])

        fused, best_chunk = defaultdict(float), {}
        for ranking in rankings:
            for rank, (doc_id, ci) in enumerate(ranking[:60]):
                fused[doc_id] += 1.0 / (60 + rank)
                if ci is not None:
                    best_chunk.setdefault(doc_id, ci)
        results = []
        for doc_id, score in sorted(fused.items(), key=lambda x: -x[1])[:k]:
            d = self.docs[doc_id]
            ci = best_chunk.get(doc_id)
            text = self.chunks[ci]["text"].split("\n\n", 1)[-1] if ci is not None else d["answer_markdown"]
            words = text.replace("*", "").split()
            results.append({"id": doc_id, "bank_code": d["bank_code"], "question": d["question"],
                            "category": d["category"], "subcategory": d["subcategory"], "url": d["url"],
                            "score": round(score * 1000, 2),
                            "extrait": " ".join(words[:60]) + (" …" if len(words) > 60 else "")})
        return results

    def context(self, query, bank=None, k=3):
        """Contexte prêt à injecter dans le prompt d'une IA : fiches complètes + sources."""
        hits = self.search(query, bank=bank, k=k)
        blocks = []
        for i, h in enumerate(hits, 1):
            d = self.docs[h["id"]]
            blocks.append(
                f'<source id="{i}" fiche="{d["id"]}" banque="{d["bank"]}" rubrique="{d["category"]} > {d["subcategory"]}" '
                f'url="{d["url"]}" mise_a_jour="{(d.get("date_modified") or "")[:10]}">\n'
                f"Question : {d['question']}\n"
                + (f"Public visé : {d['audience']}\n" if d.get("audience") else "")
                + f"Réponse officielle :\n{d['answer_markdown']}\n</source>")
        return {"query": query, "bank": bank, "hits": hits, "context": "\n\n".join(blocks)}
