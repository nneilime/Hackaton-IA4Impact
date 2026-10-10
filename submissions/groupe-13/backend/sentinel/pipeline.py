"""Orchestration : corpus → extraction (cache) → parsing → corrections humaines → règles → stockage."""
from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Optional

from . import ENGINE_VERSION, RULESET_VERSION
from .b2parser import parse_b2
from .config import CORPUS_DIR, DATA_DIR, OCR_CACHE_DIR, PRIORITY_WEIGHTS
from .corpus import build_manifest, pair_documents, safe_extract, corpus_root
from .db import DB, now
from .imports import import_pairs
from .jobs import case_lock
from .rules import (ANOMALIE, NON_VERIFIABLE, complementary_observations, pairing_check, run_rules,
                    summarize)

log = logging.getLogger("sentinel")

ID_RULES = {"R02", "R03", "R04", "R05"}
ACT_RULES = {"R08", "R11", "R13", "R14", "R15", "R19"}
AMOUNT_RULES = {"R12", "R17", "R20"}
GH_RULES = {"R06", "R07", "R09", "R10", "R16"}
SIG_RULES = {"R18", "R21"}
DOC_RULES = {"R01", "R22"}


# ---------------------------------------------------------------- extraction (avec cache)
def load_extraction(jpg: Path, sha: str, allow_compute: bool = True, force: bool = False) -> Optional[dict]:
    """Extraction d'un bordereau via le cache versionné (voir ocrcache.py)."""
    from .ocrcache import load_or_compute
    return load_or_compute(jpg, sha, allow_compute, force)


# ---------------------------------------------------------------- corrections humaines
def apply_corrections(ext: dict, corrections: list) -> dict:
    """Applique les corrections (et validations) de lecture enregistrées par les agents. L'extraction d'origine
    reste en cache ; chaque valeur corrigée garde la lecture d'origine dans « original ». Les corrections sont
    validées avant enregistrement (corrections.py) ; une correction devenue inapplicable (extraction recalculée
    différente) est signalée dans `corrections_inapplicables`, jamais ignorée silencieusement."""
    from .corrections import CorrectionError, parse_target, resolve, validate_value
    ext = copy.deepcopy(ext)
    rejected = []
    for c in corrections:
        try:
            t = parse_target(c["target"])
            item = resolve(ext, t)
            val = validate_value(t, c["corrected"])
            if t["type"] == "signature":
                item.setdefault("original_status", item.get("status"))
                item["status"] = val
                item["corrected_by"] = c.get("username")
                item["correction_kind"] = c.get("kind") or "correction"
                continue
            item["original"] = item.get("original") or {k: item.get(k) for k in ("value", "agreement", "candidates", "raw")}
            item["value"] = val
            item["raw"] = str(c["corrected"])
            item["agreement"] = "corrigé"
            item["votes"] = 99
            item["candidates"] = [{"value": val, "votes": 99, "engines": ["correction humaine"]}]
            item["corrected_by"] = c.get("username")
            item["corrected_at"] = c.get("created_at")
            item["correction_kind"] = c.get("kind") or "correction"
        except (CorrectionError, KeyError, IndexError, ValueError, TypeError) as e:
            log.warning("Correction inapplicable (%s) : %s", c.get("target"), e)
            rejected.append({"id": c.get("id"), "target": c.get("target"), "raison": str(e)})
    ext["corrections_inapplicables"] = rejected
    # recalcul des lignes / exécutants après correction
    from .ocr.extract import _classify_row
    for z in ("Z6", "Z7", "Z10"):
        for r in ext.get("tables", {}).get(z, []):
            _classify_row(r)
    from .ocr.extract import collect_executants
    ext["executants"] = collect_executants(ext.get("tables", {}).get("Z10", []))
    return ext


# ---------------------------------------------------------------- priorisation (paramètre proposé)
def priority(results: list, pairing: dict, summary: dict) -> tuple[float, list]:
    W = PRIORITY_WEIGHTS
    an = {r["rule_id"] for r in results if r["status"] == ANOMALIE}
    nv = [r["rule_id"] for r in results if r["status"] == NON_VERIFIABLE]
    score, reasons = 0.0, []
    if an & ID_RULES or pairing.get("status") != "confirmé":
        score += W["identification_anomaly"]; reasons.append("identification / rapprochement en écart")
    if an & ACT_RULES:
        score += W["act_anomaly"]; reasons.append("prestation ou acte présent d'un seul côté")
    if an & AMOUNT_RULES:
        score += W["amount_anomaly"]; reasons.append("écart de montant")
    if an & GH_RULES:
        score += 15; reasons.append("incohérence de n° GHS")
    if an & DOC_RULES:
        score += 10; reasons.append("identifiant ou code de formulaire en écart")
    if an & SIG_RULES or set(nv) & SIG_RULES:
        score += W["signature_issue"]; reasons.append("signature absente ou non vérifiable")
    if nv:
        score += W["per_unverifiable"] * len(nv); reasons.append(f"{len(nv)} contrôle(s) non vérifiable(s)")
    gap = summary.get("net_total_gap_cents") or 0
    if gap:
        g = min(W["euro_gap_cap"], W["per_euro_gap"] * gap / 100)
        score += g; reasons.append(f"écart monétaire mesuré de {gap/100:.2f} €")
    return round(score, 1), reasons


# ---------------------------------------------------------------- analyse d'un dossier
_ANALYSIS_CODE = None


def analysis_code_hash() -> str:
    """Empreinte du code d'analyse (parseur, règles, zones, normalisations, orchestration) : une évolution du
    code invalide les analyses enregistrées, même sans changement de numéro de version."""
    global _ANALYSIS_CODE
    if _ANALYSIS_CODE is None:
        import hashlib
        h = hashlib.sha256()
        for name in ("b2parser.py", "rules.py", "zones.py", "normalize.py", "pipeline.py"):
            h.update((Path(__file__).parent / name).read_bytes().replace(b"\r\n", b"\n"))
        _ANALYSIS_CODE = h.hexdigest()[:16]
    return _ANALYSIS_CODE


def convention_decisions(db) -> dict:
    """Décisions métier enregistrées sur les ambiguïtés du cahier des charges (AMB-xx → validée | rejetée)."""
    import json
    try:
        row = db.one("SELECT value FROM meta WHERE key='convention_decisions'")
        return {k: v["decision"] for k, v in json.loads(row["value"]).items()} if row else {}
    except Exception:  # noqa
        return {}


def analysis_key(jsha: Optional[str], tsha: Optional[str], conventions: Optional[dict] = None) -> str:
    """Empreinte de tout ce qui détermine le résultat d'une analyse : images et fichiers sources, version du
    moteur, version des règles, code d'analyse et code d'extraction. Une différence déclenche une réanalyse."""
    import hashlib
    from .ocrcache import code_hash
    conv = ",".join(f"{k}={v}" for k, v in sorted((conventions or {}).items()))
    return hashlib.sha256(f"{jsha}|{tsha}|{ENGINE_VERSION}|{RULESET_VERSION}|{code_hash()}|{analysis_code_hash()}|{conv}"
                          .encode()).hexdigest()[:24]


def analyze_case(db: DB, pair: dict, run_id: Optional[int] = None, allow_compute: bool = True) -> dict:
    """Analyse d'un dossier, sérialisée par un verrou propre au dossier (voir jobs.py)."""
    with case_lock(pair["id"]):
        return _analyze_case(db, pair, run_id, allow_compute)


def _analyze_case(db: DB, pair: dict, run_id: Optional[int] = None, allow_compute: bool = True) -> dict:
    import time
    from .corpus import sha256_file
    t0 = time.time()
    cid = pair["id"]
    txt_dir = "Import" if pair.get("source") == "import" else "Factures txt"
    txt = parse_b2(pair["txt"], display_path=f"{txt_dir}/{pair['txt'].name}") if pair.get("txt") else None
    jsha = sha256_file(pair["jpg"]) if pair.get("jpg") else None
    ext_orig = load_extraction(pair["jpg"], jsha, allow_compute) if pair.get("jpg") else None
    if txt is None or ext_orig is None:
        payload = {"id": cid, "error": "Paire incomplète ou extraction indisponible", "txt": txt.to_dict() if txt else None}
        _store(db, cid, pair, payload, None, txt, run_id)
        return payload
    corr = db.q("SELECT c.*, u.username FROM corrections c LEFT JOIN users u ON u.id=c.user_id "
                "WHERE c.case_id=? AND c.active=1 ORDER BY c.id", (cid,))
    ext = apply_corrections(ext_orig, corr) if corr else copy.deepcopy(ext_orig)
    from .ocr.extract import collect_executants
    ext["executants"] = collect_executants(ext.get("tables", {}).get("Z10", []))
    results = run_rules(txt, ext, convention_decisions(db))
    obs = complementary_observations(txt, ext)
    pairing = pairing_check(txt, ext)
    summary = summarize(results, txt, ext)
    score, reasons = priority(results, pairing, summary)
    if txt.realignment:
        _mark_realigned(results, txt)
        score = round(score + 15, 1)
        reasons = reasons + [f"fichier B2 mal formé (caractère inséré en position {txt.realignment['position']}, "
                             f"lecture réalignée à confirmer)"]
    from .zones import build_zones
    zones = build_zones(ext, txt, results)
    txt_view = txt.to_dict()
    if txt.realignment:
        _map_positions([results, zones, txt_view], txt)
    payload = {
        "id": cid, "family": pair["family"], "source": pair.get("source", "corpus"), "label": pair.get("label"),
        "jpg": f"{'Import' if pair.get('source') == 'import' else 'Bordereaux jpg'}/{pair['jpg'].name}",
        "txt_file": f"{txt_dir}/{pair['txt'].name}", "txt": txt_view, "extraction": ext,
        "results": results, "observations": obs, "pairing": pairing, "summary": summary,
        "priority": {"score": score, "reasons": reasons,
                     "note": "Score opérationnel proposé par l'équipe (paramétrable), pas une norme MSA."},
        "zones": zones,
        "corrections": corr, "engine_version": ENGINE_VERSION, "ruleset_version": RULESET_VERSION,
        "analyzed_at": now(), "analysis_key": analysis_key(jsha, txt.sha256, convention_decisions(db)),
        "timings": {"analyse_s": None, "ocr_s": ext_orig.get("duration_s")},
    }
    payload["timings"]["analyse_s"] = round(time.time() - t0, 3)
    _store(db, cid, pair, payload, summary, txt, run_id, jsha, score, reasons, len(obs), pairing)
    return payload


def _mark_realigned(results: list, txt) -> None:
    """Signale les contrôles qui reposent sur un champ situé après le caractère inséré : leur valeur provient de
    la lecture réalignée (interprétation démontrée mais à confirmer), jamais du fichier tel quel."""
    idx = txt.realignment["index"]
    for r in results:
        refs = [x for x in r.get("txt_refs") or [] if isinstance(x.get("start"), int)]
        if any(x["start"] > idx for x in refs):
            r.setdefault("details", {})["lecture_realignee"] = True
            r["realignment_note"] = (f"Valeur lue après réalignement du fichier (caractère blanc inséré en position "
                                     f"{txt.realignment['position']}) : interprétation à confirmer.")


def _map_positions(objs: list, txt) -> None:
    """Convertit les positions de la lecture réalignée en positions de la ligne d'origine (surlignage du TXT)."""
    from .b2parser import original_position
    seen = set()

    def walk(o):
        if id(o) in seen:
            return
        seen.add(id(o))
        if isinstance(o, dict):
            if isinstance(o.get("start"), int) and isinstance(o.get("end"), int) and "line_no" in o:
                o["start"], o["end"] = original_position(txt, o["start"]), original_position(txt, o["end"])
            for v in o.values():
                if isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                if isinstance(v, (dict, list)):
                    walk(v)
    for o in objs:
        walk(o)


def _establishment(txt) -> str:
    for r in txt.records:
        if r.rtype == "1" and len(r.raw) > 70:
            # libellé de l'établissement présent dans l'enregistrement de lot (zone libre, non contrôlée)
            name = r.raw[29 + (txt.alignment_shift or 0):69 + (txt.alignment_shift or 0)].strip()
            return name or "—"
    return "—"


def _rel(p):
    """Chemin relatif au dossier data/ (corpus ou imports), stocké en base."""
    if not p:
        return None
    try:
        return Path(p).resolve().relative_to(DATA_DIR.resolve()).as_posix()
    except ValueError:
        return Path(p).name


def all_pairs() -> list:
    try:
        corpus = [dict(p, source="corpus") for p in pair_documents()]
    except FileNotFoundError:
        corpus = []                     # archive non déposée : seuls les dossiers importés sont analysés
    return corpus + import_pairs()


def _uploader_id(db, pair):
    """Un dossier importé est affecté à l'agent qui l'a déposé : les autres agents ne le voient pas
    (l'affectation initiale ne s'applique qu'à la création du dossier)."""
    by = (pair.get("meta") or {}).get("by")
    if pair.get("source") != "import" or not by:
        return None
    u = db.one("SELECT id, role FROM users WHERE username=?", (by,))
    return u["id"] if u and u["role"] == "agent" else None


def _store(db, cid, pair, payload, summary, txt, run_id, jsha=None, score=None, reasons=None, n_obs=0, pairing=None):
    with db.tx() as c:
        c.execute("""INSERT INTO cases (id, family, jpg_path, txt_path, jpg_sha256, txt_sha256, pairing_status,
                     finess, establishment, invoice_no, billed_cents, n_anomalies, n_nv, n_errors, n_observations,
                     state, net_gap_cents, act_gap_cents, priority_score, priority_reasons, analyzed_at, run_id,
                     analysis_key, source, source_status, label, analysis_s, assigned_to, created_by)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'ok',?,?,?,?)
                     ON CONFLICT(id) DO UPDATE SET family=excluded.family, jpg_path=excluded.jpg_path,
                     txt_path=excluded.txt_path, jpg_sha256=excluded.jpg_sha256, txt_sha256=excluded.txt_sha256,
                     pairing_status=excluded.pairing_status, finess=excluded.finess,
                     establishment=excluded.establishment, invoice_no=excluded.invoice_no,
                     billed_cents=excluded.billed_cents, n_anomalies=excluded.n_anomalies, n_nv=excluded.n_nv,
                     n_errors=excluded.n_errors, n_observations=excluded.n_observations, state=excluded.state,
                     net_gap_cents=excluded.net_gap_cents, act_gap_cents=excluded.act_gap_cents,
                     priority_score=excluded.priority_score, priority_reasons=excluded.priority_reasons,
                     analyzed_at=excluded.analyzed_at, run_id=excluded.run_id, analysis_key=excluded.analysis_key,
                     source=excluded.source, source_status='ok', label=excluded.label, analysis_s=excluded.analysis_s,
                     created_by=COALESCE(cases.created_by, excluded.created_by)""",
                  (cid, pair["family"], _rel(pair.get("jpg")), _rel(pair.get("txt")), jsha, txt.sha256 if txt else None,
                   pairing["status"] if pairing else "non vérifiable",
                   txt.numero_tiers.value if txt and txt.numero_tiers else None,
                   _establishment(txt) if txt else None,
                   txt.numero_facture.value if txt and txt.numero_facture else None,
                   summary["billed_cents"] if summary else None,
                   summary["n_anomalies"] if summary else None, summary["n_non_verifiable"] if summary else None,
                   summary["n_errors"] if summary else None, n_obs, summary["state"] if summary else "erreur",
                   summary["net_total_gap_cents"] if summary else None, summary["act_level_gap_cents"] if summary else None,
                   score, json.dumps(reasons or [], ensure_ascii=False), now(), run_id,
                   payload.get("analysis_key"), pair.get("source", "corpus"), pair.get("label"),
                   (payload.get("timings") or {}).get("analyse_s"), _uploader_id(db, pair),
                   (pair.get("meta") or {}).get("by")))
        c.execute("INSERT INTO analyses (case_id, payload, analyzed_at) VALUES (?,?,?) ON CONFLICT(case_id) "
                  "DO UPDATE SET payload=excluded.payload, analyzed_at=excluded.analyzed_at",
                  (cid, json.dumps(payload, ensure_ascii=False), now()))
        c.execute("DELETE FROM check_results WHERE case_id=?", (cid,))
        for r in payload.get("results", []):
            gap = (r.get("gap") or {}).get("amount_cents")
            c.execute("INSERT INTO check_results VALUES (?,?,?,?,?,?)",
                      (cid, r["rule_id"], r["status"], gap, json.dumps(r.get("uncertainty"), ensure_ascii=False), run_id))


# ---------------------------------------------------------------- initialisation complète
def init_corpus(db: DB, force_extract: bool = False) -> dict:
    report = {}
    try:
        corpus_root(CORPUS_DIR)
        exists = True
    except FileNotFoundError:
        exists = False
    if force_extract or not exists:
        report["extraction"] = safe_extract()
    manifest = build_manifest()
    with db.tx() as c:
        for f in manifest["files"]:
            c.execute("INSERT INTO source_files VALUES (?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET "
                      "sha256=excluded.sha256, size=excluded.size, kind=excluded.kind, read_only=excluded.read_only",
                      (f["path"], f["kind"], f["size"], f["sha256"], int(f["read_only"]), now()))
    db.meta_set("manifest", manifest)
    report["manifest"] = manifest["counts"]
    return report


def analyze_all(db: DB, triggered_by: str = "système", allow_compute: bool = True, progress=None) -> dict:
    pairs = all_pairs()
    with db.tx() as c:
        cur = c.execute("INSERT INTO runs (started_at, engine_version, ruleset_version, n_cases, triggered_by) "
                        "VALUES (?,?,?,?,?)", (now(), ENGINE_VERSION, RULESET_VERSION, len(pairs), triggered_by))
        run_id = cur.lastrowid
    db.meta_set("pairs", [{"id": p["id"], "family": p["family"], "status": p["status"],
                           "jpg": p["jpg"].name if p["jpg"] else None, "txt": p["txt"].name if p["txt"] else None}
                          for p in pairs])
    done = 0
    for p in pairs:
        analyze_case(db, p, run_id, allow_compute)
        done += 1
        if progress:
            progress(done, len(pairs), p["id"])
    with db.tx() as c:
        c.execute("UPDATE runs SET finished_at=? WHERE id=?", (now(), run_id))
    return {"run_id": run_id, "n_cases": len(pairs)}


def sync_cases(db: DB, triggered_by: str = "démarrage", allow_compute: bool = True, progress=None) -> dict:
    """Synchronisation incrémentale : analyse les dossiers nouveaux ou dont une source (JPG, TXT), la version
    des règles, du moteur ou du code d'extraction a changé ; marque « source absente » les dossiers dont les
    fichiers ont disparu (leurs décisions sont conservées)."""
    from .corpus import sha256_file
    pairs = all_pairs()
    known = {c["id"]: c for c in db.q("SELECT id, analysis_key, source_status FROM cases")}
    todo, unchanged = [], 0
    for p in pairs:
        jsha = sha256_file(p["jpg"]) if p.get("jpg") else None
        tsha = sha256_file(p["txt"]) if p.get("txt") else None
        k = known.get(p["id"])
        if k and k["analysis_key"] == analysis_key(jsha, tsha, convention_decisions(db)) and k["source_status"] == "ok":
            unchanged += 1
        else:
            todo.append((p, "nouveau" if not k else "modifié"))
    gone = [cid for cid in known if cid not in {p["id"] for p in pairs} and known[cid]["source_status"] != "absente"]
    with db.tx() as c:
        for cid in gone:
            c.execute("UPDATE cases SET source_status='absente' WHERE id=?", (cid,))
    run_id = None
    if todo:
        with db.tx() as c:
            run_id = c.execute("INSERT INTO runs (started_at, engine_version, ruleset_version, n_cases, triggered_by) "
                               "VALUES (?,?,?,?,?)", (now(), ENGINE_VERSION, RULESET_VERSION, len(todo), triggered_by)).lastrowid
    db.meta_set("pairs", [{"id": p["id"], "family": p["family"], "status": p["status"],
                           "jpg": p["jpg"].name if p["jpg"] else None, "txt": p["txt"].name if p["txt"] else None}
                          for p in pairs])
    for i, (p, why) in enumerate(todo, 1):
        analyze_case(db, p, run_id, allow_compute)
        if progress:
            progress(i, len(todo), p["id"])
    if run_id:
        with db.tx() as c:
            c.execute("UPDATE runs SET finished_at=? WHERE id=?", (now(), run_id))
    return {"analyses": len(todo), "nouveaux": sum(1 for _, w in todo if w == "nouveau"),
            "modifies": sum(1 for _, w in todo if w == "modifié"), "inchanges": unchanged, "sources_absentes": len(gone),
            "run_id": run_id}


def reanalyze_case(db: DB, cid: str) -> dict:
    pair = next((p for p in all_pairs() if p["id"] == cid), None)
    if not pair:
        raise KeyError(cid)
    run = db.one("SELECT MAX(id) AS id FROM runs")
    return analyze_case(db, pair, run["id"] if run else None)
