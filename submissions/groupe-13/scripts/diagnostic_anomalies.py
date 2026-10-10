"""Diagnostic des anomalies : remonter de chaque résultat « ANOMALIE » à ses éléments de preuve.

Pour chaque anomalie du corpus (base locale, analyses en cours) :
  dossier, règle, zone(s), valeur retenue sur le bordereau, lectures par moteur (RapidOCR / Tesseract),
  valeur du TXT avec ligne et positions, appariements (règles de présence), convention appliquée,
  géométrie (boîtes, recalage), recadrage agrandi de la région, et la revue humaine si elle existe.

Sorties (dossier data/diagnostic/, local, non versionné car il contient des extraits de documents de santé) :
  diagnostic.json   — une entrée par anomalie
  crops/<dossier>_<règle>.png — recadrage de la région du bordereau

Usage (depuis la racine du projet) : python scripts/diagnostic_anomalies.py [--statuts ANOMALIE,NON_VERIFIABLE]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from PIL import Image, ImageDraw  # noqa: E402

from sentinel.corpus import corpus_root  # noqa: E402
from sentinel.db import DB  # noqa: E402

OUT = ROOT / "data" / "diagnostic"


def _image(payload):
    rel = payload.get("jpg")
    if not rel:
        return None
    for base in (corpus_root(), ROOT / "data" / "imports"):
        p = base / rel
        if p.exists():
            im = Image.open(p).convert("RGB")
            if (payload["extraction"].get("layout") or {}).get("rotation") == 180:
                im = im.rotate(180)
            return im
    return None


def _boxes(payload, res):
    boxes = [(r["box"], r.get("label", "")) for r in res.get("img_refs") or [] if r.get("box")]
    if not boxes:  # règles de présence : toute la zone
        zmap = {z["zone_id"]: z for z in payload.get("zones") or []}
        for zid in res.get("zones") or []:
            for reg in (zmap.get(zid) or {}).get("regions", []):
                boxes.append((reg["box"], f"{zid} — {reg.get('label', '')}"))
    return boxes


def _crop(im, boxes, path):
    if not boxes or im is None:
        return None
    x0 = max(0, min(b[0][0] for b in boxes) - 25)
    y0 = max(0, min(b[0][1] for b in boxes) - 25)
    x1 = min(im.width, max(b[0][2] for b in boxes) + 25)
    y1 = min(im.height, max(b[0][3] for b in boxes) + 25)
    c = im.crop((x0, y0, x1, y1)).copy()
    d = ImageDraw.Draw(c)
    for (bx, _lab) in boxes:
        d.rectangle((bx[0] - x0, bx[1] - y0, bx[2] - x0, bx[3] - y0), outline=(220, 38, 38), width=2)
    k = max(1, round(900 / max(1, c.width)))
    if k > 1:
        c = c.resize((c.width * k, c.height * k), Image.LANCZOS)
    c.save(path)
    return str(path.relative_to(ROOT))


def _readings(res):
    out = {"rapidocr": [], "tesseract": []}
    for lec in (res.get("details") or {}).get("lectures") or []:
        out.setdefault(lec.get("moteur", "?"), []).append(lec.get("texte"))
    return out


def main(statuts):
    db = DB()
    (OUT / "crops").mkdir(parents=True, exist_ok=True)
    reviews = {}
    try:
        for r in db.q("SELECT * FROM validations"):
            reviews.setdefault((r["case_id"], r["rule_id"]), []).append(r)
    except Exception:  # noqa — table absente (version antérieure)
        pass
    cases = [c["id"] for c in db.q("SELECT id FROM cases WHERE COALESCE(source,'corpus')='corpus' ORDER BY id")]
    out = []
    for cid in cases:
        row = db.one("SELECT payload FROM analyses WHERE case_id=?", (cid,))
        if not row:
            continue
        p = json.loads(row["payload"])
        im = _image(p)
        for res in p["results"]:
            if res["status"] not in statuts:
                continue
            crop = _crop(im, _boxes(p, res), OUT / "crops" / f"{cid}_{res['rule_id']}.png")
            out.append({
                "dossier": cid, "regle": res["rule_id"], "statut": res["status"], "zones": res.get("zones"),
                "bordereau": res.get("jpg_value"), "fichier": res.get("txt_value"),
                "lectures": _readings(res),
                "positions_txt": res.get("txt_refs"), "champs_txt": res.get("txt_fields"),
                "appariements": (res.get("details") or {}).get("appariements"),
                "convention": res.get("convention"), "explication": res.get("explanation"),
                "incertitude": res.get("uncertainty"),
                "geometrie": {"boites": res.get("img_refs"), "recalage": p["extraction"].get("layout")},
                "rapprochement_dossier": (p.get("pairing") or {}).get("status"),
                "observations": [o.get("code") for o in p.get("observations") or []],
                "recadrage": crop,
                "revue_humaine": reviews.get((cid, res["rule_id"]), []),
            })
    (OUT / "diagnostic.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(out)} résultat(s) → {OUT / 'diagnostic.json'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--statuts", default="ANOMALIE,NON_VERIFIABLE")
    main(set(ap.parse_args().statuts.split(",")))
