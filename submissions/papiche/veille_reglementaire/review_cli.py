# SPDX-License-Identifier: AGPL-3.0-or-later
"""Commandes de relecture : ./veille review | confirm | correct | dismiss"""
from __future__ import annotations

import json

from . import review


def resolve(target: str, queue: list[dict]) -> str:
    """« 3 » = troisième ligne de `./veille review` ; sinon l'identifiant complet du passage."""
    if target.isdigit():
        index = int(target) - 1
        if not 0 <= index < len(queue):
            raise SystemExit(f"Numéro hors liste (1 à {len(queue)}). Lancer `./veille review`.")
        return queue[index]["passage_id"]
    return target


def print_queue(queue: list[dict]) -> None:
    if not queue:
        print("Rien à relire.")
        return
    print(f"{len(queue)} source(s) à relire :\n")
    for number, item in enumerate(queue, 1):
        label = "à corriger" if item["kind"] == "a_corriger" else "à confirmer"
        print(f"{number:>3}  {label:11} {item['country']}  {item['product'][:26]:26} {item['reason'][:70]}")
    print("\nVoir le détail : ./veille review --show N   ·   écran de relecture : ./veille serve puis http://localhost:8088/review")


def print_detail(item: dict) -> None:
    print(f"{item['product']} ({item['country']}, {item['source_id']}) — {item['kind']}")
    print(f"Source officielle : {item['source_url']}  (collectée le {item['collected_at']})")
    print(f"\nPourquoi : {item['reason']}")
    print(f"\n--- texte source ---\n{item['text']}\n")
    print("--- dernière proposition de l'IA ---\n" + json.dumps(item["proposal"], ensure_ascii=False, indent=1))


def run(args) -> None:
    if args.cmd == "review":
        queue = review.review_queue(include_decided=args.all)
        if args.show:
            print_detail(next(i for i in queue if i["passage_id"] == resolve(args.show, queue)))
        else:
            print_queue(queue)
        return
    queue = review.review_queue()
    passage_id = resolve(args.target, queue)
    try:
        if args.cmd == "confirm":
            review.decide(passage_id, "confirmed", args.author)
        elif args.cmd == "dismiss":
            review.decide(passage_id, "dismissed", args.author, reason=args.reason)
        else:
            item = next(i for i in review.review_queue(include_decided=True) if i["passage_id"] == passage_id)
            fields = dict(item["proposal"])                     # on repart de la proposition de l'IA…
            for name in review.EXTRACTION_FIELDS:               # …et les options de l'expert la remplacent
                value = getattr(args, name, None)
                if value is not None:
                    fields[name] = value
            review.decide(passage_id, "corrected", args.author, fields=fields)
    except ValueError as error:
        raise SystemExit(f"Refusé : {error}")
    print("Décision enregistrée.")
