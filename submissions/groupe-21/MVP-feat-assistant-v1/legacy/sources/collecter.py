#!/usr/bin/env python3
"""Inventaire reproductible des deux FAQ publiques, via leurs réponses HTML.

Bibliothèque standard uniquement. Deux collectes parallèles, au plus deux
requêtes simultanées par domaine et deux départs par seconde par domaine.
Les réponses brutes restent dans un cache temporaire local.
Le livrable contient des extraits bornés, des repères factuels et des sources.
"""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque

ROOTS = {
    "Caisse d’Épargne": "https://www.caisse-epargne.fr/faq-particuliers/",
    "Banque Populaire": "https://www.banquepopulaire.fr/faq-particuliers/",
}
VOID = set("area base br col embed hr img input link meta param source track wbr".split())
AGENT = "PublicHelpInventory/1.0 (public FAQ; max 2 requests/second/host)"
HOST_LOCKS = {urllib.parse.urlsplit(root).netloc: threading.Lock() for root in ROOTS.values()}
HOST_NEXT = {host: 0.0 for host in HOST_LOCKS}


class Node:
    def __init__(self, tag="root", attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []

    def all(self, tag=None, cls=None):
        for c in self.children:
            if isinstance(c, Node):
                if (tag is None or c.tag == tag) and (cls is None or cls in c.attrs.get("class", "").split()):
                    yield c
                yield from c.all(tag, cls)

    def text(self):
        if self.tag in {"script", "style", "svg", "noscript"}:
            return ""
        return re.sub(r"\s+", " ", " ".join(c.text() if isinstance(c, Node) else c for c in self.children)).strip()


class Tree(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.current = self.root
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.current)
        self.current.children.append(n)
        if tag not in VOID:
            self.current = n

    def handle_startendtag(self, tag, attrs):
        self.current.children.append(Node(tag, attrs, self.current))

    def handle_endtag(self, tag):
        n = self.current
        while n.parent is not None:
            if n.tag == tag:
                self.current = n.parent
                return
            n = n.parent

    def handle_data(self, data):
        self.current.children.append(data)


def normalized(url, base):
    u = urllib.parse.urlsplit(urllib.parse.urljoin(base, url))
    return urllib.parse.urlunsplit((u.scheme, u.netloc.lower(), u.path, u.query, ""))


def scoped(url, root):
    u, r = urllib.parse.urlsplit(url), urllib.parse.urlsplit(root)
    return u.scheme in {"http", "https"} and u.netloc == r.netloc and u.path.startswith(r.path) and not u.query


def unique(values):
    return list(dict.fromkeys(v for v in values if v))


def factual_markers(text):
    patterns = {
        "montants": r"\b\d[\d .]*(?:,\d+)?\s*(?:€|euros?)\b|\b\d[\d .]*(?:,\d+)?\s*€",
        "pourcentages": r"\b\d+(?:[.,]\d+)?\s*%",
        "durées": r"\b\d+\s*(?:secondes?|minutes?|heures?|jours?(?:\s+ouvr[ée]s?)?|semaines?|mois|ans?|années?)\b",
        "téléphones": r"(?<!\d)(?:\+33|0033|0)[ .-]?[1-9](?:[ .-]?\d{2}){4}(?!\d)",
        "courriels": r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
    }
    return {k: unique(re.findall(pattern, text, flags=re.I)) for k, pattern in patterns.items() if re.search(pattern, text, flags=re.I)}


def parse_page(html, url, root):
    tree = Tree(html).root
    main = next(tree.all("main"), None)
    if main is None:
        raise ValueError("Balise main absente")
    h1 = next(main.all("h1"), None)
    title = h1.text() if h1 else ""
    canonical = next((n.attrs.get("href") for n in tree.all("link") if n.attrs.get("rel") == "canonical"), url)
    listing = list(main.all(cls="links-listing-block"))
    sections = list(main.all(cls="wp-block-bpce-block-rte"))
    answers = [n for section in sections for n in section.all(cls="wysiwyg")]
    text = "\n\n".join(n.text() for n in answers)
    media_sections = list(main.all(cls="video-description"))
    media_text = unique(p.text() for section in media_sections for p in section.all("p") if "video-mask-info" not in p.attrs.get("class", "").split())
    if media_text:
        text += "\n\n" + "\n\n".join(media_text)
    links = []
    for n in listing:
        for a in n.all("a"):
            href = normalized(a.attrs.get("href", ""), url)
            if scoped(href, root):
                links.append({"url": href, "title": a.text()})
    # All internal FAQ links in main are tracked, including breadcrumbs and related links.
    internal = unique(normalized(a.attrs.get("href", ""), url) for a in main.all("a") if a.attrs.get("href") and scoped(normalized(a.attrs["href"], url), root))
    external = unique(normalized(a.attrs["href"], url) for n in answers for a in n.all("a") if a.attrs.get("href") and not scoped(normalized(a.attrs["href"], url), root))
    resources = []
    for n in answers:
        for image in n.all("img"):
            src = image.attrs.get("data-src") or image.attrs.get("src", "")
            if src and not src.startswith("data:"):
                resources.append(normalized(src, url))
    for n in main.all("iframe"):
        src = n.attrs.get("data-src") or n.attrs.get("src", "")
        if src:
            resources.append(normalized(src, url))
    for section in media_sections:
        for a in section.all("a"):
            href = a.attrs.get("href", "")
            if href and urllib.parse.urlsplit(href).netloc in {"www.youtube.com", "youtube.com", "youtu.be", "player.vimeo.com", "www.dailymotion.com"}:
                resources.append(normalized(href, url))
    date = next(main.all("time"), None)
    paragraphs = [p.text() for n in answers for p in n.all() if p.tag in {"p", "li"}]
    content = [p for p in paragraphs if p and not p.lower().startswith(("ce contenu s’adresse", "ce contenu s'adresse", "cette réponse s’adresse", "cette réponse s'adresse"))]
    source = content[0] if content else text
    ui_paths = []
    for container in answers:
        for block in container.all():
            if block.tag not in {"p", "li"} or not re.search(r"cliqu|appuy|sélectionn|touchez|choisiss", block.text(), re.I):
                continue
            labels = []
            for strong in block.all("strong"):
                label = strong.text().strip(" ():.\u00a0")
                if label and len(label.split()) <= 6 and not label.lower().startswith(("depuis votre", "bon à savoir", "le bon réflexe")):
                    labels.append(label)
            if labels:
                ui_paths.append(" → ".join(unique(labels)))
    # Bound title, interface labels and excerpt together to 25 source words.
    title_words = title.split()
    budget = max(0, 25 - len(title_words))
    bounded_paths = []
    for path in unique(ui_paths):
        count = len(path.replace("→", " ").split())
        if count <= budget:
            bounded_paths.append(path)
            budget -= count
    excerpt = " ".join(source.split()[:budget])
    if excerpt and len(source.split()) > budget:
        excerpt += " […]"
    return {
        "title": title, "canonical": canonical, "kind": "question" if text else "rubrique",
        "date_source": date.text() if date else "",
        "listed_links": list({x["url"]: x for x in links}.values()),
        "internal_links": internal, "related_links": external,
        "resources": unique(resources), "excerpt": excerpt,
        "excerpt_words": len(excerpt.replace(" […]", "").split()),
        "answer_words": len(text.split()), "answer_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "facts": factual_markers(text),
        "ui_paths": bounded_paths,
        "quoted_words": len(title_words) + len(excerpt.replace(" […]", "").split()) + sum(len(p.replace("→", " ").split()) for p in bounded_paths),
        "supports": [label for needle, label in [("application", "Application mobile"), ("espace client web", "Espace client web"), ("ordinateur", "Ordinateur"), ("conseiller", "Conseiller bancaire")] if needle in text.lower()],
    }


def get(url, cache):
    key = hashlib.sha256(url.encode()).hexdigest()
    meta_path, html_path = cache / (key + ".json"), cache / (key + ".html")
    if meta_path.exists() and html_path.exists():
        return json.loads(meta_path.read_text()), html_path.read_text()
    for attempt in range(3):
        try:
            host = urllib.parse.urlsplit(url).netloc
            with HOST_LOCKS[host]:
                wait = HOST_NEXT[host] - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                HOST_NEXT[host] = time.monotonic() + 0.5
            req = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "text/html"})
            with urllib.request.urlopen(req, timeout=35) as r:
                body = r.read()
                data = {
                    "url": url, "final_url": r.url, "status": r.status,
                    "content_type": r.headers.get("Content-Type", ""),
                    "collected_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "html_sha256": hashlib.sha256(body).hexdigest(),
                }
                html = body.decode(r.headers.get_content_charset() or "utf-8", errors="replace")
                html_path.write_text(html)
                meta_path.write_text(json.dumps(data, ensure_ascii=False))
                return data, html
        except urllib.error.HTTPError as e:
            if e.code not in {429, 500, 502, 503, 504}:
                raise
            retry_after = e.headers.get("Retry-After", "")
            time.sleep(min(30, int(retry_after)) if retry_after.isdigit() else (attempt + 1) * 2)
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep((attempt + 1) * 2)
    raise RuntimeError("Échec HTTP après trois tentatives")


def crawl(bank, root, cache, output):
    todo, seen, records = deque([root]), set(), {}
    # The robots endpoint is recorded for traceability, without following non-FAQ links.
    origin = urllib.parse.urlsplit(root)
    robots_url = urllib.parse.urlunsplit((origin.scheme, origin.netloc, "/robots.txt", "", ""))
    try:
        rm, robots = get(robots_url, cache)
        (output / (origin.netloc + "-robots.txt")).write_text(robots)
    except Exception as e:
        print(f"{bank}: robots indisponible: {e}", flush=True)
    def fetch_page(url):
        try:
            meta, html = get(url, cache)
            if not scoped(meta["final_url"], root):
                raise ValueError("Redirection hors de l'arbre FAQ demandé")
            if "text/html" not in meta["content_type"]:
                raise ValueError("Réponse non HTML")
            data = parse_page(html, meta["final_url"], root)
            data.update(meta)
            if not data["title"]:
                raise ValueError("Titre h1 absent")
            return data
        except Exception as e:
            print(f"ERREUR {url}: {e}", flush=True)
            return {"url": url, "kind": "erreur", "error": str(e), "status": getattr(e, "code", None)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        pending = {}
        while todo or pending:
            while todo and len(pending) < 2:
                url = todo.popleft()
                if url in seen:
                    continue
                seen.add(url)
                pending[pool.submit(fetch_page, url)] = url
            if not pending:
                continue
            completed, _ = concurrent.futures.wait(pending, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in completed:
                url = pending.pop(future)
                data = future.result()
                records[url] = data
                for href in data.get("internal_links", []):
                    if href not in seen:
                        todo.append(href)
                if len(records) % 25 == 0:
                    print(f"{bank}: {len(records)} pages, {len(set(todo) - seen) + len(pending)} à visiter", flush=True)
                    (output / (origin.netloc + "-progression.json")).write_text(json.dumps(records, ensure_ascii=False, indent=2))
    return bank, {"root": root, "pages": records}


def md_escape(s):
    return re.sub(r"([\\`*_{}\[\]<>|])", r"\\\1", s).replace("\n", " ")


def render(result, output):
    # Also normalize older checkpoint records when resuming/rendering only.
    for data in result.values():
        for p in data["pages"].values():
            if p["kind"] == "erreur":
                continue
            if len(p["title"].split()) > 25:
                p["title"] = " ".join(p["title"].split()[:24]) + " […]"
                p["title_abridged"] = True
            remaining = max(0, 25 - len(p["title"].split()))
            paths = []
            for path in p.get("ui_paths", []):
                count = len(path.replace("→", " ").split())
                if count <= remaining:
                    paths.append(path)
                    remaining -= count
            original = p.get("excerpt", "").replace(" […]", "")
            words = original.split()
            excerpt = " ".join(words[:remaining])
            if excerpt and (len(words) > remaining or p.get("excerpt", "").endswith(" […]")):
                excerpt += " […]"
            p["ui_paths"] = paths
            p["excerpt"] = excerpt
            p["excerpt_words"] = min(len(words), remaining)
            p["quoted_words"] = len(p["title"].split()) + p["excerpt_words"] + sum(len(path.replace("→", " ").split()) for path in paths)
            p["listed_links"] = [{"url": link["url"]} for link in p.get("listed_links", [])]
    lines = ["# Inventaire des aides publiques — Caisse d’Épargne et Banque Populaire", "",
             f"Généré le {dt.datetime.now(dt.timezone.utc).isoformat()} (UTC).", "",
             "## Périmètre et lecture", "",
             "Les deux FAQ nationales **particuliers** indiquées par l’utilisateur sont parcourues par requêtes GET HTML publiques. Chaque lien interne de leur contenu principal est suivi récursivement. Aucun espace authentifié ni variante régionale n’est consulté.", "",
             "Ce document est un inventaire documenté avec de courts extraits et des repères factuels détectés automatiquement. Il **ne contient pas les réponses intégrales ni une synthèse exhaustive de leurs conditions**. La longueur cumulée du titre, des libellés d’interface et de l’extrait est limitée à 25 mots par page ; les rares titres plus longs sont abrégés et marqués […]. Les montants, durées et coordonnées sont des repères isolés : consulter la source pour leurs conditions et leur contexte. Les supports indiquent des mots présents dans la réponse, sans garantie de disponibilité de chaque fonction.", "",
             "Les rubriques et questions sont classées selon les liens de navigation HTML. Les descriptions HTML des vidéos sont incluses dans les repères factuels et la taille de réponse ; les vidéos restent des liens, sans transcription audiovisuelle. Les liens complémentaires hors FAQ sont référencés mais ne sont pas parcourus.", "",
             "## Couverture", "", "| Banque | Catégories | Sous-catégories | Questions | Autres rubriques | Erreurs | Liens internes non visités |", "|---|---:|---:|---:|---:|---:|---:|"]
    report = {}
    for bank, data in result.items():
        pages, root = data["pages"], data["root"]
        good = [p for p in pages.values() if p.get("status") == 200]
        listed = {link["url"] for p in good for link in p.get("listed_links", [])}
        discovered = {u for p in good for u in p.get("internal_links", [])}
        root_parts = len(urllib.parse.urlsplit(root).path.strip("/").split("/"))
        depth = lambda p: len(urllib.parse.urlsplit(p["url"]).path.strip("/").split("/")) - root_parts
        stats = {
            "pages": len(pages), "categories": sum(depth(p) == 1 and p["kind"] == "rubrique" for p in good),
            "subcategories": sum(depth(p) == 2 and p["kind"] == "rubrique" for p in good),
            "questions": sum(p["kind"] == "question" for p in good),
            "other_sections": sum(p["kind"] == "rubrique" and depth(p) not in {1, 2} for p in good),
            "errors": [p for p in pages.values() if p["kind"] == "erreur"],
            "unvisited_internal_links": sorted(discovered - set(pages)),
            "listed_question_urls": len({u for u in listed if pages.get(u, {}).get("kind") == "question"}),
            "empty_answer_questions": [p["url"] for p in good if depth(p) >= 3 and p["kind"] != "question"],
            "overlong_quotes": [p["url"] for p in good if p.get("quoted_words", len(p["title"].split()) + p["excerpt_words"]) > 25],
            "canonical_aliases": {p["url"]: p["canonical"] for p in good if p["url"] != p["canonical"]},
        }
        report[bank] = stats
        lines.append(f"| {bank} | {stats['categories']} | {stats['subcategories']} | {stats['questions']} | {stats['other_sections']} | {len(stats['errors'])} | {len(stats['unvisited_internal_links'])} |")
    for bank, data in result.items():
        lines.extend(["", f"## {bank}", "", f"Point d’entrée : [FAQ particuliers]({data['root']})", ""])
        pages = data["pages"]
        visited = set()
        def emit(url, level=0):
            if url in visited:
                return
            visited.add(url)
            p = pages[url]
            if p["kind"] == "erreur":
                lines.extend([f"- Lecture impossible : [{url}]({url}) — {md_escape(p['error'])}", ""])
                return
            if level == 0:
                for link in p["listed_links"]:
                    if link["url"] in pages:
                        emit(link["url"], 1)
                return
            lines.extend(["#" * min(6, level + 2) + " " + md_escape(p["title"]), "", f"Source : [Consulter la page]({url})", ""])
            if p.get("date_source"):
                lines.extend([md_escape(p["date_source"]), ""])
            if p["kind"] == "question":
                if p["excerpt"]:
                    lines.extend(["> " + md_escape(p["excerpt"]), ""])
                for field, values in p["facts"].items():
                    lines.append(f"- {field.capitalize()} détectés : {md_escape('; '.join(values))}.")
                if p["supports"]:
                    lines.append("- Supports/interlocuteurs mentionnés : " + "; ".join(p["supports"]) + ".")
                if p.get("ui_paths"):
                    lines.append("- Libellés d’interface, dans l’ordre de chaque passage source : " + md_escape(" ; ".join(p["ui_paths"])) + ".")
                for i, href in enumerate(p["related_links"], 1):
                    lines.append(f"- [Lien complémentaire {i}]({href})")
                for i, href in enumerate(p["resources"], 1):
                    lines.append(f"- [Illustration ou vidéo {i}]({href})")
                lines.extend([f"- Taille de la réponse source : {p['answer_words']} mots ; récupération HTML : HTTP {p['status']}.", ""])
            for link in p["listed_links"]:
                if link["url"] in pages:
                    emit(link["url"], level + 1)
        emit(data["root"])
        remaining = sorted(set(pages) - visited)
        if remaining:
            lines.extend(["### Autres pages découvertes par des liens internes", ""])
            for u in remaining:
                emit(u, 2)
    lines.extend(["## Méthode et contrôle", "",
                  "Le manifeste JSON contient, pour chaque endpoint, son statut HTTP, son URL finale et canonique, l’horodatage de collecte, les empreintes SHA-256 du HTML et de la réponse, les liens découverts et les extraits autorisés. Le rapport JSON signale les erreurs, les liens internes non visités, les réponses vides et les alias canoniques.", "",
                  "Une visite exhaustive s’entend ici comme la fermeture du graphe des liens internes de ces deux arbres HTML au moment de la collecte. Des contenus non liés, ajoutés ultérieurement ou réservés à une région ne sont pas inclus. Les réponses sources peuvent évoluer.", ""])
    (output / "aides-banques.md").write_text("\n".join(lines))
    (output / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    (output / "rapport-controle.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--cache", type=Path, default=Path(tempfile.gettempdir()) / "collecte-aides-banques-cache")
    parser.add_argument("--render-only", action="store_true")
    parser.add_argument("--reparse-cache", action="store_true", help="Recalculer les fiches depuis les HTML locaux, sans requête réseau")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    args.cache.mkdir(parents=True, exist_ok=True)
    if args.render_only or args.reparse_cache:
        result = json.loads((args.output / "manifest.json").read_text())
        if args.reparse_cache:
            for data in result.values():
                for url, record in data["pages"].items():
                    if record["kind"] == "erreur":
                        continue
                    html_path = args.cache / (hashlib.sha256(url.encode()).hexdigest() + ".html")
                    record.update(parse_page(html_path.read_text(), record["final_url"], data["root"]))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(crawl, bank, root, args.cache, args.output) for bank, root in ROOTS.items()]
            result = dict(f.result() for f in futures)
    report = render(result, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
