# SPDX-License-Identifier: AGPL-3.0-or-later
"""Rend le code concret : extraits exacts (fichier, fonction, lignes) pour la page, et pages de source navigables.

La page ne contient jamais de code recopié à la main : chaque extrait est relu dans le dépôt à chaque `./veille web`,
avec ses vrais numéros de ligne et un lien direct vers ces lignes (web/source/<fichier>.html#L53-L83).
"""
from __future__ import annotations

import ast
import html

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_for_filename

from . import config

SOURCE_FOLDER = config.WEB / "source"
FORMATTER = HtmlFormatter(nowrap=True, style="monokai")

# clé -> (fichier, symbole ou None pour tout le fichier, titre affiché)
REFERENCES = {
    "proof_check": ("veille_reglementaire/extraction_loop.py", "check_proof", "Le contrôle de preuve"),
    "normalize_text": ("veille_reglementaire/extraction_loop.py", "normalize_text", "Comparer sans tenir compte des espaces ni de la casse"),
    "contract": ("veille_reglementaire/models.py", "Extraction", "Le contrat de données (Pydantic)"),
    "numbers_in": ("veille_reglementaire/models.py", "numbers_in", "Lire les nombres d'un texte"),
    "attempt": ("veille_reglementaire/extraction_loop.py", "run_one_attempt", "Une tentative : appeler, valider, vérifier"),
    "retry_prompt": ("veille_reglementaire/extraction_loop.py", "build_retry_prompt", "Le retour d'erreur envoyé au modèle"),
    "loop": ("veille_reglementaire/extraction_loop.py", "extract_passage", "La boucle complète (3 essais, puis un expert)"),
    "critic": ("veille_reglementaire/extraction_loop.py", "ask_critic", "Le second avis, indicatif"),
    "eppo": ("veille_reglementaire/eppo_codes.py", "normalize", "Codes EPPO : le modèle choisit, la table confirme"),
    "dose_norm": ("veille_reglementaire/models.py", "normalize_dose", "Conversion des unités par calcul"),
    "passage": ("veille_reglementaire/sources/__init__.py", "Passage", "Un passage : l'unité de preuve"),
    "epa_passages": ("veille_reglementaire/sources/epa.py", "passages", "Passages EPA : seulement les taux d'application"),
    "ephy_collect": ("veille_reglementaire/sources/ephy.py", "collect", "Collecte e-Phy en bloc"),
    "polite": ("veille_reglementaire/polite_http.py", "download", "Télécharger seulement ce qui a changé"),
    "send_request": ("veille_reglementaire/polite_http.py", "send_request", "Pause, attente et journal de chaque requête"),
    "evaluation": ("veille_reglementaire/evaluation.py", "score_against_source", "Comparer l'IA à la source structurée"),
    "holdout": ("veille_reglementaire/holdout_test.py", "run", "Test hors échantillon"),
    "llm_call": ("veille_reglementaire/llm.py", "chat_json", "Appel à l'IA : température 0, JSON forcé, cache"),
    "vram": ("veille_reglementaire/model_benchmark.py", "estimate_vram", "VRAM = poids + cache + marge"),
    "calibrate": ("veille_reglementaire/model_benchmark.py", "calibrate_efficiency", "Efficacité mesurée sur la carte"),
    "recommend": ("veille_reglementaire/model_benchmark.py", "recommend", "Choisir le plus petit modèle suffisant"),
    "cost_local": ("veille_reglementaire/cost_estimate.py", "local_cost_per_passage", "Coût local d'un passage"),
    "sisters": ("veille_reglementaire/sister_products.py", "detect", "Produits sœurs : score lisible"),
    "qdrant_search": ("veille_reglementaire/qdrant_store.py", "search_passages", "Recherche sémantique dans Qdrant"),
    "review_decide": ("veille_reglementaire/review.py", "decide", "Enregistrer une décision de l'expert"),
    "review_build": ("veille_reglementaire/review.py", "build_human_record", "Les valeurs de l'expert : mêmes contrôles que l'IA"),
    "scaffold": ("veille_reglementaire/source_scaffold.py", "create_source", "Créer le squelette d'une nouvelle source"),
    "test_proof": ("tests/test_loop.py", "Loop.test_citation_inventee_est_rejetee", "Test : une citation inventée est rejetée"),
    "test_pydantic": ("tests/test_loop.py", "Loop.test_pydantic_rejette_puis_corrige", "Test : Pydantic refuse, le modèle corrige"),
    "test_expert": ("tests/test_loop.py", "Loop.test_trois_echecs_arbitrage_humain", "Test : trois échecs, rien n'est publié"),
    "prompt_extractor": ("prompts/extractor.system.md", None, "Le prompt d'extraction"),
    "prompt_critic": ("prompts/critic.system.md", None, "Le prompt du critique"),
    "prompt_retry": ("prompts/retry.user.md", None, "Le message de correction"),
    "prompt_eppo": ("prompts/eppo.system.md", None, "Le prompt EPPO (choix fermé)"),
}

PUBLISHED_FOLDERS = ("veille_reglementaire", "tests", "prompts")
PUBLISHED_FILES = ("config/scope.json", "config/pricing.json", "config/narration_fr.json", "web/pechakucha.js")


# ── Lire un symbole dans un fichier Python ───────────────────────────────────

def find_symbol_lines(source: str, symbol: str) -> tuple[int, int]:
    """Lignes (début, fin) d'une fonction, d'une classe ou d'une méthode « Classe.methode »."""
    tree = ast.parse(source)
    scope = tree.body
    node = None
    for name in symbol.split("."):
        node = next(n for n in scope if getattr(n, "name", None) == name)
        scope = getattr(node, "body", [])
    start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    return start, node.end_lineno


def highlighted_lines(source: str, file_name: str) -> list[str]:
    try:
        lexer = get_lexer_for_filename(file_name)
    except Exception:
        lexer = TextLexer()
    return highlight(source, lexer, FORMATTER).rstrip("\n").split("\n")


# ── Extraits pour la page ────────────────────────────────────────────────────

def source_url(path: str, start: int | None = None, end: int | None = None) -> str:
    anchor = f"#L{start}-L{end}" if start else ""
    return f"web/source/{path}.html{anchor}"


def build_references() -> dict:
    references = {}
    for key, (path, symbol, title) in REFERENCES.items():
        source = (config.ROOT / path).read_text(encoding="utf-8")
        total_lines = len(source.splitlines())
        start, end = find_symbol_lines(source, symbol) if symbol else (1, total_lines)
        lines = highlighted_lines(source, path)
        numbered = "\n".join(f'<span class="cl"><i>{n}</i>{lines[n - 1]}</span>' for n in range(start, end + 1))
        references[key] = {"title": title, "path": path, "symbol": symbol, "start": start, "end": end,
                           "url": source_url(path, start, end), "html": numbered}
    return references


# ── Pages de source navigables ───────────────────────────────────────────────

PAGE_STYLE = """
:root{color-scheme:dark} body{background:#0b1117;color:#e8ecf2;font:14px/1.55 ui-monospace,'JetBrains Mono',monospace;margin:0}
header{position:sticky;top:0;background:rgba(11,17,23,.95);border-bottom:1px solid #27323f;padding:10px 20px;font:600 14px system-ui,sans-serif;display:flex;gap:14px;flex-wrap:wrap;align-items:center}
header a{color:#4aa3ff} header .path{color:#2ed573;font-family:ui-monospace,monospace} header .licence{color:#8c98a8;margin-left:auto;font-weight:400}
table{border-collapse:collapse;width:100%} td{padding:0 12px;vertical-align:top;white-space:pre-wrap;word-break:break-word}
td.ln{width:1%;white-space:nowrap;min-width:3.2em;text-align:right;color:#6b7888;user-select:none;position:sticky;left:0;background:#0b1117} td.ln a{color:inherit;text-decoration:none}
tr.on td{background:rgba(46,213,115,.12)} tr.on td.ln{background:#12301f;color:#2ed573}
.index li{margin:6px 0;font-family:system-ui,sans-serif} .index span{color:#8c98a8}
"""
HIGHLIGHT_SCRIPT = """
const m = location.hash.match(/^#L(\\d+)(?:-L(\\d+))?$/);
if (m) { const a = +m[1], b = +(m[2] || m[1]); for (let i = a; i <= b; i++) { const row = document.getElementById('L' + i); if (row) row.classList.add('on'); }
  const first = document.getElementById('L' + a); if (first) first.scrollIntoView({block: 'start'}); window.scrollBy(0, -70); }
"""


def write_source_page(path: str) -> str:
    source = (config.ROOT / path).read_text(encoding="utf-8")
    lines = highlighted_lines(source, path)
    depth = path.count("/") + 2                       # web/source/<chemin>.html -> racine du dépôt
    back = "../" * depth + "index.html"
    rows = "\n".join(f'<tr id="L{n}"><td class="ln"><a href="#L{n}">{n}</a></td><td class="hl">{line}</td></tr>'
                     for n, line in enumerate(lines, 1))
    page = (f'<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(path)}</title><link rel="stylesheet" href="{"../" * path.count("/")}pygments.css"><style>{PAGE_STYLE}</style>'
            f'<header><a href="{back}">← retour à la présentation</a><span class="path">{html.escape(path)}</span>'
            f'<a href="{"../" * path.count("/")}index.html">tout le code</a><span class="licence">AGPL-3.0-or-later</span></header>'
            f'<table>{rows}</table><script>{HIGHLIGHT_SCRIPT}</script></html>')
    target = SOURCE_FOLDER / f"{path}.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding="utf-8")
    return path


def published_paths() -> list[str]:
    paths = []
    for folder in PUBLISHED_FOLDERS:
        paths += sorted(str(p.relative_to(config.ROOT)) for p in (config.ROOT / folder).rglob("*")
                        if p.is_file() and p.suffix in (".py", ".md") and "__pycache__" not in p.parts)
    return paths + [p for p in PUBLISHED_FILES if (config.ROOT / p).exists()]


def first_docstring_line(path: str) -> str:
    if not path.endswith(".py"):
        return ""
    docstring = ast.get_docstring(ast.parse((config.ROOT / path).read_text(encoding="utf-8"))) or ""
    return docstring.splitlines()[0] if docstring else ""


def write_index_page(paths: list[str]) -> None:
    items = "\n".join(f'<li><a href="{p}.html">{html.escape(p)}</a> <span>{html.escape(first_docstring_line(p))}</span></li>' for p in paths)
    page = (f'<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Tout le code</title><style>{PAGE_STYLE}</style><header><a href="../../index.html">← retour à la présentation</a>'
            f'<span class="path">tout le code · {len(paths)} fichiers</span><span class="licence">AGPL-3.0-or-later</span></header>'
            f'<ul class="index" style="padding:14px 34px">{items}</ul></html>')
    (SOURCE_FOLDER / "index.html").write_text(page, encoding="utf-8")


def build() -> dict:
    """Écrit les pages de source et retourne les extraits pour la page d'accueil."""
    SOURCE_FOLDER.mkdir(parents=True, exist_ok=True)
    (SOURCE_FOLDER / "pygments.css").write_text(HtmlFormatter(style="monokai").get_style_defs(".hl"), encoding="utf-8")
    paths = published_paths()
    for path in paths:
        write_source_page(path)
    write_index_page(paths)
    return build_references()
