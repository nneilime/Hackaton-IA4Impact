# SPDX-License-Identifier: AGPL-3.0-or-later
"""Interface en ligne de commande : python -m veille_reglementaire <commande>"""
from __future__ import annotations
import argparse, json, sys
from . import comparison_table, config, llm, pipeline, qdrant_store


def main(argv=None):
    ap = argparse.ArgumentParser(prog="veille_reglementaire", description="Agent IA maison de veille réglementaire LPC")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="modèle, backend, Qdrant, volumes")
    c = sub.add_parser("collect", help="télécharge les sources officielles"); c.add_argument("--only", nargs="*")
    i = sub.add_parser("index", help="découpe en passages et indexe dans Qdrant"); i.add_argument("--only", nargs="*")
    e = sub.add_parser("extract", help="boucle IA : extraire, valider, auditer")
    e.add_argument("--limit", type=int); e.add_argument("--product"); e.add_argument("--source")
    e.add_argument("--per-product", type=int, help="échantillon : N passages max par produit et pays")
    sub.add_parser("eval", help="évalue contre la vérité structurée")
    t = sub.add_parser("compare", help="tableau produit x pays x usage"); t.add_argument("--product"); t.add_argument("--csv")
    sub.add_parser("sisters", help="hypothèses de produits sœurs")
    a = sub.add_parser("ask", help="question en langage naturel"); a.add_argument("question")
    s = sub.add_parser("serve", help="API REST + interface d'administration (FastAPI)"); s.add_argument("--port", type=int, default=8088)
    s.add_argument("--host", default="127.0.0.1", help="127.0.0.1 par défaut (local seulement) ; 0.0.0.0 pour ouvrir au réseau")
    sub.add_parser("web", help="génère web/data.js pour la page didactique")
    b = sub.add_parser("bench", help="comparatif de modèles LLM + dimensionnement GPU / stockage")
    b.add_argument("--models", nargs="*"); b.add_argument("--small", action="store_true", help="échantillon réduit (12 passages)")
    sub.add_parser("cost", help="coût : service local vs API au token vs forfaits (après `bench`)")
    sub.add_parser("network", help="requêtes sortantes vers les sources (preuve de sobriété)")
    v = sub.add_parser("voice", help="génère les fichiers audio de la présentation (web/audio/)")
    v.add_argument("--engine", default="orpheus", choices=["orpheus", "espeak"]); v.add_argument("--voice", default="amelie")
    v.add_argument("--slides", type=int, nargs="*", help="refaire seulement ces diapositives (ex. --slides 13)")
    h = sub.add_parser("holdout", help="test hors échantillon : produits e-Phy jamais utilisés pour régler le prompt")
    h.add_argument("--products", type=int, default=40); h.add_argument("--per-product", type=int, default=4); h.add_argument("--seed", type=int, default=1)
    n = sub.add_parser("new-source", help="crée le squelette d'une nouvelle source officielle")
    n.add_argument("source_id"); n.add_argument("--name", required=True); n.add_argument("--country-code", required=True)
    n.add_argument("--country", required=True); n.add_argument("--region", required=True)
    n.add_argument("--format", default="CSV"); n.add_argument("--lang", default="EN")
    r = sub.add_parser("review", help="sources à faire relire par un humain (trois échecs, ou « à confirmer »)")
    r.add_argument("--all", action="store_true", help="inclure les sources déjà décidées"); r.add_argument("--show", metavar="N_OU_ID")
    for name, text in (("confirm", "confirmer la proposition de l'IA"), ("correct", "corriger avec de nouvelles valeurs"), ("dismiss", "écarter la source")):
        d = sub.add_parser(name, help=text); d.add_argument("target", metavar="N_OU_ID"); d.add_argument("--author", required=True)
        if name == "dismiss":
            d.add_argument("--reason", required=True)
        if name == "correct":
            for flag in ("crop-original", "target-original", "dose-original", "dose-unit", "quote"):
                d.add_argument(f"--{flag}")
            for flag in ("dose-value",):
                d.add_argument(f"--{flag}", type=float)
            for flag in ("max-applications", "min-interval-days", "pre-harvest-interval-days"):
                d.add_argument(f"--{flag}", type=int)
    sub.add_parser("storyboard", help="écrit video/storyboard.json (format generate_scene.sh) et les sous-titres")
    sub.add_parser("export", help="CSV comparatif + contrat OpenAPI + schéma Dataverse (dossier m365/)")
    args = ap.parse_args(argv)

    if args.cmd == "status":
        print(json.dumps({"modele": config.MODEL, "embed": config.EMBED_MODEL, "backend_llm": llm.backend(),
                          "qdrant": qdrant_store.mode(), "records": len(pipeline.load("records.jsonl")),
                          "hitl": len(pipeline.load("hitl.jsonl"))}, ensure_ascii=False, indent=1))
    elif args.cmd == "collect":
        print(json.dumps(pipeline.collect(args.only), ensure_ascii=False, indent=1))
    elif args.cmd == "index":
        pipeline.index(args.only)
    elif args.cmd == "extract":
        print(json.dumps(pipeline.extract(args.limit, args.product, args.source, args.per_product)))
    elif args.cmd == "eval":
        from . import evaluation
        r = evaluation.run(pipeline.load("traces.jsonl"))
        (config.PROCESSED / "eval.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
        print(json.dumps(r, ensure_ascii=False, indent=1))
    elif args.cmd == "compare":
        rows = comparison_table.table(pipeline.load("records.jsonl"), args.product)
        if args.csv:
            open(args.csv, "w", encoding="utf-8").write(comparison_table.to_csv(rows))
        for r in rows[:40]:
            print(f"{r['product'][:20]:20} {r['country']} {str(r['crop_original'])[:22]:22} {str(r['target_original'])[:24]:24} "
                  f"{str(r['dose_original'])[:22]:22} {r['validation_status']}")
        print(f"{len(rows)} lignes")
    elif args.cmd == "sisters":
        from . import sister_products
        meta = [{"product": p.product, "country": p.country, "ai": p.ai, "holder": p.holder} for p in qdrant_store.all_passages()]
        found = sister_products.detect(meta)
        pipeline._dump("sisters.jsonl", found)
        for s_ in found:
            print(f"{s_['confidence']:.2f}  {s_['product_a']} ({s_['country_a']}) ~ {s_['product_b']} ({s_['country_b']})")
    elif args.cmd == "ask":
        from . import question_answering
        r = question_answering.ask(args.question)
        print(r["answer"]); [print(f"  [{c['n']}] {c['source_url']} ({c['collected_at']})") for c in r["citations"][:6]]
    elif args.cmd == "serve":
        import uvicorn
        uvicorn.run("veille_reglementaire.api:app", host=args.host, port=args.port)
    elif args.cmd == "bench":
        from . import model_benchmark
        r = model_benchmark.run(args.models, {"ephy": 6, "pmra": 3, "epa": 3} if args.small else None)
        print(json.dumps({m: {k: v for k, v in x.items() if k in ("s_per_passage_mean", "decode_tok_s", "accepted", "hitl", "accuracy_vs_structured")}
                          for m, x in r["results"].items()}, ensure_ascii=False, indent=1))
    elif args.cmd == "cost":
        from . import cost_estimate
        report = cost_estimate.run()
        print(f"docs/COUT.md écrit ({len(report['options'])} options, {len(report['scenarios'])} scénarios)")
    elif args.cmd == "network":
        from . import polite_http
        summary = polite_http.summarize_requests(polite_http.read_request_log())
        print(json.dumps(summary, ensure_ascii=False, indent=1))
    elif args.cmd == "voice":
        from . import narration
        report = narration.render_audio(args.engine, args.voice, args.slides)
        too_long = [r["slide"] for r in report if not r["fits_20s"]]
        print("Toutes les diapositives tiennent en 20 s." if not too_long else f"Trop longues (>20 s) : {too_long}")
    elif args.cmd == "holdout":
        from . import holdout_test
        print(json.dumps(holdout_test.run(args.products, args.per_product, args.seed), ensure_ascii=False, indent=1))
    elif args.cmd == "new-source":
        from . import source_scaffold
        path = source_scaffold.create_source(args.source_id, args.name, args.country_code, args.country, args.region, args.format, args.lang)
        print(f"Créé : {path}\n" + source_scaffold.NEXT_STEPS.format(path=path, source_id=args.source_id))
    elif args.cmd in ("review", "confirm", "correct", "dismiss"):
        from . import review_cli
        review_cli.run(args)
    elif args.cmd == "storyboard":
        from . import storyboard
        print(json.dumps(storyboard.write(), ensure_ascii=False))
    elif args.cmd == "export":
        from . import microsoft365_export
        microsoft365_export.export()
    elif args.cmd == "web":
        from . import web_data
        web_data.build()


if __name__ == "__main__":
    main()
