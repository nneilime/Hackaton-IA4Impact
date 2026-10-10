"""Test d'interface (navigateur réel) du cockpit des 15 zones — 55 dossiers × 15 zones = 825 entrées.

Prérequis : application lancée (python -m sentinel.cli serve), un compte agent existant, Playwright installé
(pip install playwright && python -m playwright install chromium).

    python scripts/e2e_zones.py --user agent1 --password ******** [--url http://127.0.0.1:8000] [--cases 55]

Vérifie pour chaque dossier :
  A. présence : 15 zones encadrées sur le bordereau, y compris vides, illisibles ou non applicables ;
  B. navigation : un clic sur chaque zone Z1…Z15 la sélectionne, l'affiche dans la fiche et la cadre à l'écran
     (cadre visible, non masqué par les panneaux) ;
  C. synchronisation : couleur de l'encadrement = statut calculé par le serveur = pastille de la grille ;
  D. aucune zone verte si l'un de ses contrôles est non vérifiable ;
puis, sur un dossier par famille : alignement des encadrements après zoom, navigation au clavier,
et mise à jour des couleurs après une correction (annulée ensuite).
Résultat : data/e2e_zones.json + résumé à l'écran ; code de sortie ≠ 0 en cas d'écart.
"""
import argparse
import asyncio
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLORS = {"CONFORME": "rgb(22, 163, 74)", "ANOMALIE": "rgb(220, 38, 38)", "NON_VERIFIABLE": "rgb(107, 114, 128)",
          "ERREUR_TECHNIQUE": "rgb(245, 158, 11)"}


async def main(a):
    from playwright.async_api import async_playwright
    out = {"dossiers": [], "erreurs": [], "controles_specifiques": {}}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1440, "height": 860})
        pg = await ctx.new_page()
        await pg.goto(a.url)
        await pg.fill("input[autocomplete=username]", a.user)
        await pg.fill("input[type=password]", a.password)
        await pg.click("button.primary")
        await pg.wait_for_timeout(1200)
        api = lambda path: pg.evaluate(f"fetch('{path}', {{credentials: 'same-origin'}}).then(r => r.json())")
        cases = [c["id"] for c in await api("/api/cases") if (c.get("source") or "corpus") == "corpus"][: a.cases]
        t0 = time.time()
        for cid in cases:
            d = await api(f"/api/cases/{cid}")
            zones = {z["zone_id"]: z for z in d["analysis"]["zones"]}
            await pg.goto(f"{a.url}/#/controle/{cid}?mode=expert")
            await pg.wait_for_selector("[data-testid=zone-inspector]")
            await pg.wait_for_timeout(400)
            rec = {"dossier": cid, "famille": d["analysis"]["extraction"]["layout"]["family"], "zones": {}}
            drawn = await pg.eval_on_selector_all(".zbox[data-zone]", "els => els.map(e => [e.dataset.zone, e.dataset.status, getComputedStyle(e).borderTopColor, getComputedStyle(e).borderTopStyle])")
            seen = {}
            for zid, st, col, style in drawn:
                seen.setdefault(zid, set()).add((st, col, style))
            if len(seen) != 15:
                out["erreurs"].append(f"{cid} : {len(seen)} zones encadrées au lieu de 15")
            for zid, z in zones.items():
                ent = {"statut": z["status"], "regles": [r["rule_id"] for r in z["related_rules"]], "regions": len(z["regions"])}
                st_set = seen.get(zid, set())
                if not st_set:
                    out["erreurs"].append(f"{cid} {zid} : zone non affichée")
                for st, col, style in st_set:
                    if st != z["status"]:
                        out["erreurs"].append(f"{cid} {zid} : statut affiché {st} ≠ serveur {z['status']}")
                    if z["status"] in COLORS and col != COLORS[z["status"]]:
                        out["erreurs"].append(f"{cid} {zid} : couleur {col} ≠ {COLORS[z['status']]}")
                    if z["status"] == "NON_APPLICABLE" and style != "dashed":
                        out["erreurs"].append(f"{cid} {zid} : non applicable sans pointillés")
                if z["status"] == "CONFORME" and any(r["status"] == "NON_VERIFIABLE" or (r["status"] == "CONFORME" and r.get("uncertainty"))
                                                     for r in z["rule_results"]):
                    out["erreurs"].append(f"{cid} {zid} : zone verte malgré un contrôle incertain")
                chip_cls = await pg.get_attribute(f"[data-chip={zid}]", "class")
                if z["status"] not in (chip_cls or ""):
                    out["erreurs"].append(f"{cid} {zid} : pastille de grille incohérente ({chip_cls})")
                # B. navigation : vue d'ensemble (« Ajuster »), puis clic sur la zone du bordereau (première région)
                await pg.click(".viewer-tools >> text=Ajuster")
                await pg.wait_for_timeout(60)
                await pg.click(f".zbox[data-zone={zid}][tabindex=\"0\"]")
                await pg.wait_for_timeout(120)
                sheet = await pg.get_attribute("[data-testid=zone-sheet]", "data-zone")
                ok_sel = sheet == zid
                vb = await pg.eval_on_selector("[data-testid=viewer]", "e => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }")
                fb = await pg.eval_on_selector(".zfocus", "e => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }")
                cx, cy = (fb[0] + fb[2]) / 2, (fb[1] + fb[3]) / 2
                ok_frame = vb[0] <= cx <= vb[2] and vb[1] <= cy <= vb[3]
                ent.update(selection=ok_sel, cadrage=ok_frame)
                if not ok_sel:
                    out["erreurs"].append(f"{cid} {zid} : la fiche affiche {sheet}")
                if not ok_frame:
                    out["erreurs"].append(f"{cid} {zid} : zone hors de la visionneuse après cadrage")
                rec["zones"][zid] = ent
            out["dossiers"].append(rec)
            print(f"{cid} ({rec['famille']}) : 15 zones vérifiées", flush=True)
        # ---------------- contrôles spécifiques sur un dossier par famille
        fams = {}
        for r in out["dossiers"]:
            fams.setdefault(r["famille"], r["dossier"])
        for fam, cid in sorted(fams.items()):
            await pg.goto(f"{a.url}/#/controle/{cid}?mode=expert")
            await pg.wait_for_selector("[data-testid=zone-inspector]")
            await pg.wait_for_timeout(500)
            # alignement après zoom : la région affichée suit l'image (rapport des positions constant)
            zz = await api(f"/api/cases/{cid}")
            reg = next(z for z in zz["analysis"]["zones"] if z["zone_id"] == "Z8")["regions"][0]["box"]
            def pos():
                return pg.evaluate("""() => { const img = document.querySelector('.viewer img').getBoundingClientRect();
                    const z = document.querySelector('.zbox[data-zone=Z8]').getBoundingClientRect();
                    return [img.left, img.top, img.width, z.left, z.top]; }""")
            size = zz["analysis"]["extraction"]["size"]
            errs = []
            for wheel in (0, -400, 300):
                if wheel:
                    await pg.mouse.move(300, 450); await pg.mouse.wheel(0, wheel); await pg.wait_for_timeout(250)
                il, it, iw, zl, ztop = await pos()
                k = iw / size[0]
                if abs((zl - il) - reg[0] * k) > 2.5 or abs((ztop - it) - reg[1] * k) > 2.5:
                    errs.append(f"décalage après zoom {wheel}")
            # clavier : ] passe à la zone suivante
            await pg.click("[data-chip=Z3]"); await pg.wait_for_timeout(150)
            await pg.keyboard.press("]"); await pg.wait_for_timeout(150)
            if await pg.get_attribute("[data-testid=zone-sheet]", "data-zone") != "Z4":
                errs.append("raccourci ] inopérant")
            out["controles_specifiques"][fam] = {"dossier": cid, "erreurs": errs}
            out["erreurs"] += [f"{cid} : {e}" for e in errs]
        # mise à jour des couleurs après correction (Facture1_04 : Z8 818,97 → correction 818,98)
        cid = "Facture1_04"
        if cid in cases:
            res = await pg.evaluate("""async () => { const r = await fetch('/api/cases/Facture1_04/corrections', {method: 'POST', credentials: 'same-origin',
                headers: {'Content-Type': 'application/json'}, body: JSON.stringify({target: 'fields.Z8', corrected: '818,98', comment: 'test e2e'})}); return r.json(); }""")
            await pg.goto(f"{a.url}/#/controle/{cid}?mode=expert"); await pg.reload(); await pg.wait_for_selector(".zbox[data-zone=Z13]"); await pg.wait_for_timeout(400)
            z13 = await pg.get_attribute(".zbox[data-zone=Z13]", "data-status")
            d = await api(f"/api/cases/{cid}")
            corr = d["analysis"]["corrections"][-1]["id"]
            await pg.evaluate(f"fetch('/api/cases/{cid}/corrections/{corr}', {{method: 'DELETE', credentials: 'same-origin'}})")
            await pg.wait_for_timeout(500)
            await pg.reload(); await pg.wait_for_selector(".zbox[data-zone=Z13]"); await pg.wait_for_timeout(400)
            z13b = await pg.get_attribute(".zbox[data-zone=Z13]", "data-status")
            ok = z13 == "ANOMALIE" and z13b == "CONFORME" and res.get("effect", {}).get("zones", {}).get("Z13") == ["CONFORME", "ANOMALIE"]
            out["controles_specifiques"]["correction"] = {"Z13_apres_correction": z13, "Z13_apres_annulation": z13b, "ok": ok}
            if not ok:
                out["erreurs"].append("couleurs non mises à jour après correction")
        await b.close()
    n = sum(len(r["zones"]) for r in out["dossiers"])
    out["resume"] = {"entrees": n, "dossiers": len(out["dossiers"]), "erreurs": len(out["erreurs"]),
                     "familles": sorted({r["famille"] for r in out["dossiers"]}), "duree_s": round(time.time() - t0, 1)}
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "e2e_zones.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
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
