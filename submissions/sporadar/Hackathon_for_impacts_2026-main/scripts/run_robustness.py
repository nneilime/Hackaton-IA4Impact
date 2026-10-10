"""Banc de robustesse de POST /ask : pose les ~50 questions de evaluation/robustness_questions.csv,
vérifie chaque réponse et indique À QUELLE ÉTAPE elle échoue (compréhension, résolution EPPO, filtrage...).

But : savoir quelles corrections apportent le plus pour le moins d'effort (voir le rapport Markdown).

Usage (depuis la racine du dépôt, venv activé, DATABASE_URL dans .env) :
    python scripts/run_robustness.py                         # API en mémoire (le code local)
    python scripts/run_robustness.py --url http://64.176.83.254:3000/api --sleep 2   # serveur de prod
    python scripts/run_robustness.py --no-llm                # en mémoire, sans IA (mode mots-clés)
    python scripts/run_robustness.py --only culture_cible    # une catégorie (ou un qid : --only C01)
    python scripts/run_robustness.py --probes-only           # vérifie seulement la vérité terrain du corpus

Sorties (dossier evaluation/robustness/) :
    results_<horodatage>_<mode>.jsonl : une ligne par question (réponse complète + diagnostic)
    report_<horodatage>_<mode>.md      : synthèse (score, étapes fautives triées, détail par question)

Colonnes du corpus : « | » = plusieurs valeurs acceptées (une suffit) ; « ; » dans expected_countries = tous requis.
La « sonde » (probe) est une route REST qui prouve que la donnée existe, indépendamment de l'agent.
"""
import argparse
import csv
import json
import os
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")   # Windows : évite le plantage sur les caractères accentués
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CORPUS_FILE = ROOT / "evaluation" / "robustness_questions.csv"
OUTPUT_DIR = ROOT / "evaluation" / "robustness"
EPPO_CODE = re.compile(r"^[A-Z0-9]{5,6}$")

# Étapes fautives, dans l'ordre du pipeline : la première rencontrée est « la » cause retenue
STAGES = {
    "technical": "Erreur technique (HTTP ≠ 200, timeout, exception)",
    "understanding_intent": "Compréhension : mauvaise intention",
    "understanding_params": "Compréhension : produit / substance / culture / cible / pays non extrait",
    "resolution_eppo": "Résolution : culture ou cible non traduite en code EPPO (texte brut resté)",
    "data_absent": "Données : la sonde REST ne trouve rien non plus (source, pas agent)",
    "filtering": "Filtrage : la donnée existe (sonde > 0) mais /ask ne la renvoie pas",
    "status_mismatch": "Statut de réponse inattendu (clarification inutile, hors périmètre à tort...)",
    "answer_text": "Texte de la réponse : formulation attendue absente",
    "guardrail": "Réponse « trouvée » sans fait ni preuve",
    "ok": "OK",
}
VALID_INTENTS = {"registration_lookup", "use_comparison", "ingredient_search", "expiry_watch", "data_quality",
                 "sister_product", "source_lookup", "other", "market_opportunity"}
VALID_STATUSES = {"answered", "partial", "no_data", "out_of_scope", "needs_clarification"}


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------
def alternatives(value):
    """« a|b » -> ['a', 'b'] ; vide -> []."""
    return [v.strip() for v in (value or "").split("|") if v.strip()]


def load_corpus(path=CORPUS_FILE):
    """Lit le corpus et vérifie les valeurs attendues (intention, statut) : une faute de frappe fausserait le score."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    errors = []
    for row in rows:
        for intent in alternatives(row["expected_intent"]):
            if intent not in VALID_INTENTS:
                errors.append(f"{row['qid']} : intention inconnue « {intent} »")
        for status in alternatives(row["expected_status"]):
            if status not in VALID_STATUSES:
                errors.append(f"{row['qid']} : statut inconnu « {status} »")
        if row["context_json"]:
            json.loads(row["context_json"])   # lève une erreur claire si le JSON est invalide
    if len({r["qid"] for r in rows}) != len(rows):
        errors.append("qid en double")
    if errors:
        sys.exit("Corpus invalide :\n  " + "\n  ".join(errors))
    return rows


# ---------------------------------------------------------------------------
# Diagnostic (fonction pure : testée par tests/test_robustness.py)
# ---------------------------------------------------------------------------
def contains_any(text, expected):
    """True si le texte contient une des valeurs attendues (casse ignorée)."""
    text = (text or "").lower()
    return any(e.lower() in text for e in expected)


def probe_count_of(data):
    """Nombre d'éléments d'une réponse REST (items, candidates ou rows selon la route)."""
    for key in ("items", "candidates", "rows"):
        if isinstance(data.get(key), list):
            return len(data[key])
    return 0


def diagnose(row, http_code, response, probe_count):
    """Renvoie (étape retenue, liste de tous les écarts constatés).

    row : ligne du corpus ; response : JSON de /ask (ou None) ; probe_count : None si pas de sonde.
    """
    if http_code != 200 or not isinstance(response, dict):
        return "technical", [f"HTTP {http_code}"]

    issues = []   # (étape, message)
    minor = []    # écarts jamais retenus comme cause principale (listés quand même)
    params = response.get("parameters") or {}
    status = response.get("answerStatus")
    expected_status = alternatives(row["expected_status"])
    status_ok = status in expected_status

    intents = alternatives(row["expected_intent"])
    if intents and response.get("intent") not in intents:
        issues.append(("understanding_intent", f"intention {response.get('intent')} au lieu de {'|'.join(intents)}"))

    products = alternatives(row["expected_product_id"])
    if products and not set(products) & set(params.get("productIds") or []):
        issues.append(("understanding_params", f"produit {params.get('productIds')} au lieu de {'|'.join(products)}"))

    entities = alternatives(row["expected_entity"])
    if entities and not contains_any(params.get("activeEntity"), entities):
        issues.append(("understanding_params", f"substance {params.get('activeEntity')!r} au lieu de {'|'.join(entities)}"))

    countries = [c.strip() for c in row["expected_countries"].split(";") if c.strip()]
    missing = [c for c in countries if c not in (params.get("countries") or [])]
    if missing:
        issues.append(("understanding_params", f"pays manquants {missing} (obtenus : {params.get('countries')})"))

    for field in ("crop", "target"):
        expected = alternatives(row[f"expected_{field}"])
        if not expected:
            continue
        got = params.get(field)
        codes = [e for e in expected if EPPO_CODE.match(e)]
        if not got:
            issues.append(("understanding_params", f"{field} non extrait (attendu {'|'.join(expected)})"))
        elif EPPO_CODE.match(got):
            if got not in codes and not contains_any(got, expected):
                issues.append(("resolution_eppo", f"{field} = {got}, code EPPO inattendu (attendu {'|'.join(expected)})"))
        elif codes:   # texte brut resté alors qu'un code EPPO existe
            message = f"{field} = {got!r} non traduit en code EPPO {'|'.join(codes)}"
            words = [e for e in expected if e not in codes]
            if contains_any(got, words):   # le filtre texte (LIKE) peut suffire : écart secondaire seulement
                minor.append(("resolution_eppo", message + " (texte exploitable par le filtre LIKE)"))
            else:
                issues.append(("resolution_eppo", message))
        elif not contains_any(got, expected):
            issues.append(("understanding_params", f"{field} = {got!r} au lieu de {'|'.join(expected)}"))

    if not status_ok:
        wants_answer = bool({"answered", "partial"} & set(expected_status))
        if wants_answer and probe_count == 0:
            issues.append(("data_absent", f"statut {status} ; la sonde REST ne trouve rien non plus"))
        elif wants_answer and status == "no_data" and probe_count:
            issues.append(("filtering", f"statut no_data alors que la sonde trouve {probe_count} élément(s)"))
        else:
            issues.append(("status_mismatch", f"statut {status} au lieu de {'|'.join(expected_status)}"))

    regex = alternatives(row["expected_answer_regex"])
    if regex and not any(re.search(r, response.get("answer") or "", re.IGNORECASE) for r in regex):
        issues.append(("answer_text", f"réponse sans « {'|'.join(regex)} »"))

    if status == "answered" and not response.get("evidence"):
        issues.append(("guardrail", "answered sans aucune preuve (evidence)"))

    # Une résolution EPPO ratée n'est « la » cause que si le résultat est faux ; sinon elle reste un écart secondaire
    blocking = [i for i in issues if i[0] != "resolution_eppo" or not status_ok]
    order = list(STAGES)
    stage = min(blocking, key=lambda i: order.index(i[0]))[0] if blocking else "ok"
    return stage, [f"[{s}] {m}" for s, m in issues + minor]


# ---------------------------------------------------------------------------
# Appels (en mémoire ou HTTP)
# ---------------------------------------------------------------------------
def make_clients(url):
    """Renvoie (ask(body), get(path)) -> (code HTTP, JSON). url = base de l'API (…/api) ou None (en mémoire)."""
    key = os.environ.get("API_KEY", "").strip()
    headers = {"X-API-Key": key} if key else {}
    if url:
        import requests
        base = url.rstrip("/").removesuffix("/ask")

        def ask(body):
            r = requests.post(f"{base}/ask", json=body, headers=headers, timeout=180)
            return r.status_code, r.json()

        def get(path):
            r = requests.get(f"{base}{path}", headers=headers, timeout=180)
            return r.status_code, r.json()
        return ask, get

    from fastapi.testclient import TestClient

    from backend.app.main import app
    client = TestClient(app, raise_server_exceptions=False)

    def ask(body):
        r = client.post("/api/ask", json=body, headers=headers)
        return r.status_code, r.json()

    def get(path):
        r = client.get(f"/api{path}", headers=headers)
        return r.status_code, r.json()
    return ask, get


def safe_call(fn, arg):
    """(code, json, secondes) ; une exception (timeout, JSON invalide...) devient code 0."""
    start = time.perf_counter()
    try:
        code, data = fn(arg)
    except Exception as e:   # noqa: BLE001 - on veut tout capturer pour le diagnostic
        code, data = 0, {"exception": f"{type(e).__name__}: {e}"}
    return code, data, round(time.perf_counter() - start, 2)


def run_question(row, ask, get):
    body = {"question": row["question"], "language": "fr", **json.loads(row["context_json"] or "{}")}
    code, data, seconds = safe_call(ask, body)
    probe_count = None
    if row["probe"]:
        p_code, p_data, _ = safe_call(get, row["probe"])
        probe_count = probe_count_of(p_data) if p_code == 200 else None
    stage, issues = diagnose(row, code, data, probe_count)
    ok = code == 200 and isinstance(data, dict)
    return {
        "qid": row["qid"], "category": row["category"], "variant": row["variant"], "question": row["question"],
        "stage": stage, "issues": issues, "http": code, "seconds": seconds, "probe": row["probe"],
        "probeCount": probe_count, "notes": row["notes"],
        "expected": {k.removeprefix("expected_"): v for k, v in row.items() if k.startswith("expected_") and v},
        "intent": data.get("intent") if ok else None, "answerStatus": data.get("answerStatus") if ok else None,
        "parameters": data.get("parameters") if ok else None,
        "mode": (data.get("generator") or {}).get("mode") if ok else None,
        "answer": data.get("answer") if ok else None,
        "facts": len(data.get("facts") or []) if ok else 0, "evidence": len(data.get("evidence") or []) if ok else 0,
        "warnings": data.get("warnings") if ok else None,
        "error": None if ok else data,
    }


# ---------------------------------------------------------------------------
# Rapport Markdown
# ---------------------------------------------------------------------------
def pct(n, total):
    return f"{100 * n / total:.0f} %" if total else "-"


def score_table(results, key, title):
    groups = defaultdict(list)
    for r in results:
        groups[r[key]].append(r)
    lines = [f"| {title} | OK | Total | % |", "|---|---|---|---|"]
    for name, items in sorted(groups.items(), key=lambda kv: sum(i["stage"] == "ok" for i in kv[1]) / len(kv[1])):
        ok = sum(i["stage"] == "ok" for i in items)
        lines.append(f"| {name} | {ok} | {len(items)} | {pct(ok, len(items))} |")
    return lines


def build_report(results, meta):
    total = len(results)
    ok = sum(r["stage"] == "ok" for r in results)
    stages = Counter(r["stage"] for r in results if r["stage"] != "ok")
    secondary = Counter(i.split("]")[0].strip("[") for r in results for i in r["issues"])
    secs = [r["seconds"] for r in results]
    modes = Counter(r["mode"] for r in results if r["mode"])

    out = [f"# Banc de robustesse /ask — {meta['startedAt']}", "",
           f"- Cible : `{meta['target']}` ; mode(s) du générateur : {dict(modes)}",
           f"- Corpus : `{CORPUS_FILE.relative_to(ROOT).as_posix()}` ({total} questions)",
           f"- **Score : {ok}/{total} ({pct(ok, total)})**",
           f"- Latence : médiane {statistics.median(secs):.1f} s, max {max(secs):.1f} s" if secs else "",
           "", "## Étapes fautives (cause principale, triées) — liste de priorités", "",
           "| Étape | Questions | Écarts au total (y c. secondaires) | Signification |", "|---|---|---|---|"]
    for stage, n in stages.most_common():
        out.append(f"| `{stage}` | {n} | {secondary.get(stage, 0)} | {STAGES[stage]} |")
    for stage in secondary:   # écarts qui ne sont jamais la cause principale
        if stage not in stages:
            out.append(f"| `{stage}` | 0 | {secondary[stage]} | {STAGES[stage]} (secondaire uniquement) |")
    out += ["", "## Score par catégorie", "", *score_table(results, "category", "Catégorie"),
            "", "## Score par variante de syntaxe", "", *score_table(results, "variant", "Variante")]

    out += ["", "## Détail des échecs, par étape", ""]
    by_stage = defaultdict(list)
    for r in results:
        if r["stage"] != "ok":
            by_stage[r["stage"]].append(r)
    for stage, _ in stages.most_common():
        out += [f"### `{stage}` — {STAGES[stage]}", ""]
        for r in by_stage[stage]:
            p = r["parameters"] or {}
            got = (f"intent={r['intent']}, statut={r['answerStatus']}, produits={p.get('productIds')}, "
                   f"substance={p.get('activeEntity')}, culture={p.get('crop')}, cible={p.get('target')}, "
                   f"pays={p.get('countries')}")
            out += [f"- **{r['qid']}** ({r['category']} / {r['variant']}) : « {r['question']} »",
                    f"  - obtenu : {got} ; sonde {r['probe'] or '-'} → {r['probeCount']}",
                    *[f"  - {i}" for i in r["issues"]],
                    f"  - réponse : {(r['answer'] or json.dumps(r['error'], ensure_ascii=False))[:300]}"]
        out.append("")
    out += ["## Toutes les questions", "", "| qid | Étape | Statut | Intention | Durée (s) |", "|---|---|---|---|---|"]
    out += [f"| {r['qid']} | `{r['stage']}` | {r['answerStatus']} | {r['intent']} | {r['seconds']} |" for r in results]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", help="Base de l'API d'un serveur lancé, ex. http://64.176.83.254:3000/api (sinon : en mémoire)")
    parser.add_argument("--only", help="Ne lancer qu'une catégorie ou qu'un qid (plusieurs : séparés par des virgules)")
    parser.add_argument("--sleep", type=float, default=0, help="Pause entre deux questions, en secondes (quota du fournisseur IA)")
    parser.add_argument("--no-llm", action="store_true", help="En mémoire uniquement : désactive l'IA (mode mots-clés)")
    parser.add_argument("--probes-only", action="store_true", help="Vérifie seulement que chaque sonde du corpus trouve des données")
    args = parser.parse_args()

    if args.no_llm:
        if args.url:
            sys.exit("--no-llm ne s'applique qu'à l'API en mémoire (le serveur garde sa propre configuration).")
        os.environ["AI_API_KEY"] = ""   # avant l'import du backend : load_dotenv n'écrase pas une variable déjà définie

    rows = load_corpus()
    if args.only:
        wanted = {w.strip() for w in args.only.split(",")}
        rows = [r for r in rows if r["qid"] in wanted or r["category"] in wanted]
    ask, get = make_clients(args.url)

    if args.probes_only:
        empty = 0
        for row in rows:
            if not row["probe"]:
                continue
            code, data, _ = safe_call(get, row["probe"])
            n = probe_count_of(data) if code == 200 else None
            wants_answer = bool({"answered", "partial"} & set(alternatives(row["expected_status"])))
            flag = "  <-- attendu answered mais sonde vide" if wants_answer and not n else ""
            empty += bool(flag)
            print(f"{row['qid']:5} HTTP {code} → {n}  {row['probe']}{flag}")
        sys.exit(1 if empty else 0)

    started = datetime.now(timezone.utc)
    stamp = started.strftime("%Y%m%d-%H%M%S")
    mode = "prod" if args.url else ("local-nollm" if args.no_llm else "local")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    jsonl = OUTPUT_DIR / f"results_{stamp}_{mode}.jsonl"

    results = []
    with open(jsonl, "w", encoding="utf-8") as f:
        for i, row in enumerate(rows):
            if i and args.sleep:
                time.sleep(args.sleep)
            result = run_question(row, ask, get)
            results.append(result)
            f.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")
            f.flush()   # résultats conservés même si le run est interrompu
            print(f"{result['qid']:5} {result['stage']:22} {str(result['answerStatus']):20} {result['seconds']:6.1f}s  "
                  f"{result['question'][:70]}")

    meta = {"startedAt": started.strftime("%Y-%m-%d %H:%M UTC"), "target": args.url or f"en mémoire ({mode})"}
    report = OUTPUT_DIR / f"report_{stamp}_{mode}.md"
    report.write_text(build_report(results, meta), encoding="utf-8")
    ok = sum(r["stage"] == "ok" for r in results)
    print(f"\nScore {ok}/{len(results)} — détail : {report.relative_to(ROOT)} ; brut : {jsonl.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
