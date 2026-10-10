"""Test de robustesse de la lecture des bordereaux (version 3.0).

Fabrique des COPIES transformées de bordereaux du corpus (jamais modifiés), dans data/test_robustesse/ :
rotations de -5° à +5°, luminosité, compression, redimensionnement, marges ajoutées, léger décalage.
Chaque copie est lue sans cache, puis comparée à la lecture de l'original :
  - champs simples (Z1 à Z15, sous-totaux) : même valeur retenue ?
  - tableaux : mêmes codes lus ?
  - contrôles R01 à R22 avec le TXT d'origine : même statut ?
Un champ qui change de valeur est une erreur ; un champ qui devient « à vérifier » (non vérifiable) est
une dégradation acceptable (l'outil reconnaît son doute) ; aucun contrôle ne doit passer d'un statut
conforme à « anomalie » à cause de la transformation.

Usage (racine du projet) : python scripts/test_robustesse.py [--dossiers Facture1_04,Facture2_01,Facture3_01]
Résultat : data/test_robustesse/resultats.json et résumé à l'écran.
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from sentinel.b2parser import parse_b2  # noqa: E402
from sentinel.corpus import corpus_root  # noqa: E402
from sentinel.ocr.extract import collect_executants, extract_bordereau  # noqa: E402
from sentinel.rules import run_rules  # noqa: E402

OUT = ROOT / "data" / "test_robustesse"


def rotate(img, a):
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), a, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255))


TRANSFORMS = {
    "rotation -5°": lambda im: rotate(im, -5), "rotation -3°": lambda im: rotate(im, -3),
    "rotation -1°": lambda im: rotate(im, -1), "rotation +1°": lambda im: rotate(im, 1),
    "rotation +3°": lambda im: rotate(im, 3), "rotation +5°": lambda im: rotate(im, 5),
    "plus sombre (-40)": lambda im: np.clip(im.astype(int) - 40, 0, 255).astype(np.uint8),
    "plus clair (+30)": lambda im: np.clip(im.astype(int) + 30, 0, 255).astype(np.uint8),
    "JPEG qualité 40": None,             # appliqué à l'enregistrement
    "réduit à 85 %": lambda im: cv2.resize(im, None, fx=0.85, fy=0.85, interpolation=cv2.INTER_AREA),
    "marges blanches ajoutées": lambda im: cv2.copyMakeBorder(im, 40, 40, 30, 30, cv2.BORDER_CONSTANT,
                                                              value=(255, 255, 255)),
    "décalé de 12 px / 9 px": lambda im: cv2.warpAffine(im, np.float32([[1, 0, 12], [0, 1, 9]]),
                                                        (im.shape[1], im.shape[0]), borderValue=(255, 255, 255)),
}


def summary(ext, txt):
    ext["executants"] = collect_executants(ext.get("tables", {}).get("Z10", []))
    fields = {k: (v.get("value"), v.get("agreement")) for k, v in ext.get("fields", {}).items()}
    tables = {z: [r["cells"].get("prestation", r["cells"].get("code", {})).get("value") for r in rows]
              for z, rows in ext.get("tables", {}).items()}
    rules = {r["rule_id"]: r["status"] for r in run_rules(txt, ext)}
    return fields, tables, rules


def main(cases):
    OUT.mkdir(parents=True, exist_ok=True)
    root = corpus_root()
    report = {"dossiers": {}, "resume": {}}
    n = {"copies": 0, "champs_identiques": 0, "champs_a_verifier": 0, "champs_faux": 0, "controles_identiques": 0,
         "controles_a_verifier": 0, "fausses_anomalies": 0, "controles_total": 0, "champs_total": 0}
    t0 = time.time()
    for cid in cases:
        jpg = root / "Bordereaux jpg" / f"{cid}.jpg"
        txt = parse_b2(root / "Factures txt" / f"{cid}.txt")
        ref_f, ref_t, ref_r = summary(extract_bordereau(jpg), txt)
        img = cv2.imdecode(np.fromfile(str(jpg), np.uint8), cv2.IMREAD_COLOR)
        rec = {}
        for name, fn in TRANSFORMS.items():
            out = OUT / f"{cid}_{name.replace(' ', '_').replace('°', 'deg').replace('/', '-').replace('%', 'pc')}.jpg"
            im = img if fn is None else fn(img)
            q = 40 if fn is None else 92
            cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, q])[1].tofile(str(out))
            ext = extract_bordereau(out)
            f, tb, r = summary(ext, txt)
            changed = {k: [ref_f[k][0], f[k][0]] for k in ref_f if f.get(k, (None,))[0] != ref_f[k][0]
                       and f.get(k, (None, ""))[1] not in ("divergent", "illisible", "vide") and ref_f[k][0] is not None}
            doubt = [k for k in ref_f if f.get(k, (None,))[0] != ref_f[k][0] and k not in changed]
            rdiff = {k: [ref_r[k], r[k]] for k in ref_r if r.get(k) != ref_r[k]}
            false_ano = [k for k, (a, b) in rdiff.items() if b == "ANOMALIE"]
            rec[name] = {"deskew_deg": ext["layout"].get("deskew_deg"), "famille": ext["layout"].get("family"),
                         "champs_faux": changed, "champs_a_verifier": doubt, "tableaux_modifies":
                         {z: [ref_t[z], tb.get(z)] for z in ref_t if tb.get(z) != ref_t[z]},
                         "controles_modifies": rdiff, "fausses_anomalies": false_ano}
            n["copies"] += 1
            n["champs_total"] += len(ref_f)
            n["champs_faux"] += len(changed)
            n["champs_a_verifier"] += len(doubt)
            n["champs_identiques"] += len(ref_f) - len(changed) - len(doubt)
            n["controles_total"] += len(ref_r)
            n["fausses_anomalies"] += len(false_ano)
            n["controles_a_verifier"] += sum(1 for a, b in rdiff.values() if b == "NON_VERIFIABLE")
            n["controles_identiques"] += len(ref_r) - len(rdiff)
            print(f"{cid} · {name:26s} redressement {ext['layout'].get('deskew_deg')}° · champs faux "
                  f"{len(changed)} · à vérifier {len(doubt)} · contrôles modifiés {len(rdiff)} · fausses anomalies "
                  f"{false_ano}", flush=True)
        report["dossiers"][cid] = rec
    report["resume"] = dict(n, duree_s=round(time.time() - t0, 1))
    (OUT / "resultats.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report["resume"], ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dossiers", default="Facture1_04,Facture2_01,Facture3_01")
    main(ap.parse_args().dossiers.split(","))
