"""Test d'interface du parcours simple (version 3.0) — navigateur réel, application lancée.

    python scripts/e2e_parcours_simple.py --user agent1 --password ******** [--url http://127.0.0.1:8000]

1. Sur les 55 dossiers du corpus, en mode simple :
   - le résultat global annoncé correspond au nombre d'écarts et de points à vérifier calculés par le serveur ;
   - la liste des écarts contient exactement ces contrôles, avec un libellé métier (jamais un code seul) ;
   - chaque écart s'ouvre, affiche les deux valeurs et l'agrandissement du bordereau (image réellement chargée) ;
   - les zones conformes sont discrètes (sans badge) et les zones en écart sont encadrées en rouge.
2. Parcours chronométré des cinq tâches essentielles (ouvrir un dossier, trouver l'écart, comparer les valeurs,
   décider, retrouver le dossier traité), avec le nombre de clics. La décision de test est annulée ensuite.

Ce test automatique vérifie que le parcours est réalisable et mesure son coût minimal ; il ne remplace PAS un
test avec de vrais utilisateurs (protocole dans docs/PROTOCOLE_MESURES.md).
Résultat : data/e2e_parcours_simple.json.
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


async def main(a):
    from playwright.async_api import async_playwright
    out = {"dossiers": [], "erreurs": [], "parcours": {}}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1440, "height": 860})
        pg = await ctx.new_page()
        await pg.goto(a.url)
        await pg.evaluate("localStorage.removeItem('sentinel.mode')")
        await pg.fill("input[autocomplete=username]", a.user)
        await pg.fill("input[type=password]", a.password)
        await pg.click("button.primary")
        await pg.wait_for_timeout(1200)
        api = lambda path: pg.evaluate(f"fetch('{path}', {{credentials: 'same-origin'}}).then(r => r.json())")
        cases = [c["id"] for c in await api("/api/cases") if (c.get("source") or "corpus") == "corpus"][: a.cases]
        t0 = time.time()
        for cid in cases:
            d = await api(f"/api/cases/{cid}")
            res = d["analysis"]["results"]
            exp = sorted(r["rule_id"] for r in res if r["status"] in ("ANOMALIE", "NON_VERIFIABLE", "ERREUR_TECHNIQUE"))
            await pg.goto(f"{a.url}/#/controle/{cid}")
            await pg.wait_for_selector(".simple .s-result")
            await pg.wait_for_timeout(250)
            head = await pg.inner_text(".s-result")
            n_ano = sum(1 for r in res if r["status"] == "ANOMALIE")
            if (n_ano == 0 and "écart" in head and "Aucun" not in head) or (n_ano and str(n_ano) not in head):
                out["erreurs"].append(f"{cid} : résultat annoncé « {head} » incohérent ({n_ano} écart(s))")
            items = await pg.locator(".s-item").count()
            if items != len(exp):
                out["erreurs"].append(f"{cid} : {items} élément(s) listé(s) au lieu de {len(exp)}")
            titles = await pg.locator(".s-item-t").all_inner_texts()
            if any(t.strip().startswith("R") and t.strip()[1:3].isdigit() for t in titles):
                out["erreurs"].append(f"{cid} : libellé technique affiché à la place d'un libellé métier")
            # zones : conformes discrètes, écarts encadrés en rouge avec badge
            zst = {z["zone_id"]: z["status"] for z in d["analysis"]["zones"]}
            quiet_badges = await pg.locator(".zbox.quiet .zbadge").count()
            if quiet_badges:
                out["erreurs"].append(f"{cid} : badge affiché sur une zone conforme discrète")
            for zid, st in zst.items():
                if st == "ANOMALIE":
                    cls = await pg.get_attribute(f".zbox[data-zone={zid}]", "class")
                    if "quiet" in (cls or "") or "ANOMALIE" not in (cls or ""):
                        out["erreurs"].append(f"{cid} {zid} : zone en écart non mise en avant")
            # chaque écart : deux valeurs et agrandissement chargé
            for i in range(items):
                await pg.locator(".s-item").nth(i).click()
                await pg.wait_for_selector("[data-testid=issue-card]")
                await pg.wait_for_function("() => { const i = document.querySelector('.s-crop'); return i && i.complete; }", timeout=8000)
                ok_img = await pg.evaluate("document.querySelector('.s-crop').naturalWidth > 0")
                vals = await pg.locator(".s-side .v").count()
                if not ok_img:
                    out["erreurs"].append(f"{cid} : agrandissement du bordereau non chargé (écart {i + 1})")
                if vals != 2:
                    out["erreurs"].append(f"{cid} : les deux valeurs ne sont pas affichées (écart {i + 1})")
                await pg.click("text=← Liste")
            out["dossiers"].append({"dossier": cid, "ecarts": len(exp)})
            print(f"{cid} : {len(exp)} écart(s)/point(s) vérifié(s)", flush=True)
        out["duree_s"] = round(time.time() - t0, 1)

        # ---------------- parcours chronométré (5 tâches)
        clicks = 0
        times = {}
        await pg.goto(f"{a.url}/#/"); await pg.wait_for_selector("text=Contrôler le dossier suivant")
        t = time.time()
        await pg.click("text=Contrôler le dossier suivant"); clicks += 1
        await pg.wait_for_selector(".simple .s-result")
        times["1_ouvrir_un_dossier_s"] = round(time.time() - t, 2); c1 = clicks
        cid = pg.url.split("/controle/")[1].split("?")[0]
        t = time.time()
        if await pg.locator("text=Examiner les écarts").count():
            await pg.click("text=Examiner les écarts"); clicks += 1
        await pg.wait_for_selector("[data-testid=issue-card]")
        times["2_trouver_l_ecart_s"] = round(time.time() - t, 2); c2 = clicks
        t = time.time()
        vals = await pg.locator(".s-side .v").all_inner_texts()
        times["3_comparer_les_valeurs_s"] = round(time.time() - t, 2)
        t = time.time()
        btn = pg.locator("text=Confirmer l'écart")
        if await btn.count():
            await btn.click(); clicks += 1
        else:
            await pg.click("text=À revoir"); clicks += 1
        await pg.wait_for_timeout(800)
        times["4_decider_s"] = round(time.time() - t, 2); c4 = clicks
        t = time.time()
        await pg.goto(f"{a.url}/#/"); clicks += 1
        await pg.click("text=Retrouver un dossier traité"); clicks += 1
        await pg.fill("input[placeholder^='Filtrer']", cid); clicks += 1
        await pg.wait_for_timeout(300)
        found = await pg.locator(f"td.mono:text-is('{cid}')").count()
        if not found:   # une décision ne change pas le statut : recherche sur tous les dossiers
            await pg.select_option("select[aria-label=Statut]", ""); clicks += 1
            await pg.wait_for_timeout(300)
            found = await pg.locator(f"td.mono:text-is('{cid}')").count()
        times["5_retrouver_le_dossier_s"] = round(time.time() - t, 2)
        out["parcours"] = {"dossier": cid, "valeurs_comparees": vals, "temps": times,
                           "clics": {"ouvrir": c1, "trouver_ecart": c2 - c1, "decider": c4 - c2, "retrouver": clicks - c4,
                                     "total": clicks}, "dossier_retrouve": bool(found)}
        # annulation de la décision de test (traçée, motif obligatoire)
        d = await api(f"/api/cases/{cid}")
        last = next((x for x in d["decisions"] if x["kind"] in ("confirmation", "revue_complementaire")), None)
        if last:
            await pg.evaluate(f"""fetch('/api/cases/{cid}/decisions', {{method: 'POST', credentials: 'same-origin',
                headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{kind: 'annulation', rule_id: '{last['rule_id']}',
                value: '{last['id']}', comment: 'décision de test (e2e)'}})}})""")
        await b.close()
    out["resume"] = {"dossiers": len(out["dossiers"]), "ecarts_ouverts": sum(x["ecarts"] for x in out["dossiers"]),
                     "erreurs": len(out["erreurs"]), "parcours": out["parcours"]}
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "e2e_parcours_simple.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out["resume"], ensure_ascii=False))
    for e in out["erreurs"][:30]:
        print("  ÉCART :", e)
    return 0 if not out["erreurs"] else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--cases", type=int, default=55)
    sys.exit(asyncio.run(main(ap.parse_args())))
