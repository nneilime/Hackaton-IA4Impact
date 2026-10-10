#!/usr/bin/env python3
"""Scraping complet des FAQ particuliers Caisse d'Épargne et Banque Populaire.

- Découverte : union du crawl récursif (liens internes de /faq-particuliers/)
  et des URLs des sitemaps officiels.
- Extraction : texte intégral de chaque réponse, converti en Markdown
  (paragraphes, listes imbriquées, tableaux, encadrés vidéo, liens).
- Politesse : robots.txt respecté (la FAQ est autorisée), 2 requêtes/s max par
  domaine, cache HTML local pour relancer sans re-télécharger.

Bibliothèque standard uniquement (Python 3.9+).

    python3 scraper/scrape_faq.py                 # collecte complète
    python3 scraper/scrape_faq.py --refresh       # ignore le cache HTML
    python3 scraper/scrape_faq.py --sections faq-particuliers faq-independants
"""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections import deque

ROOT_DIR = Path(__file__).resolve().parents[1]
BANKS = {
    "CE": {"name": "Caisse d'Épargne", "host": "www.caisse-epargne.fr"},
    "BP": {"name": "Banque Populaire", "host": "www.banquepopulaire.fr"},
}
AGENT = "FAQ-RAG-Collector/2.0 (public FAQ indexing; max 2 req/s/host)"
VOID = set("area base br col embed hr img input link meta param source track wbr".split())
SKIP = {"script", "style", "svg", "noscript", "button", "picture"}
AUDIENCE_PREFIXES = ("ce contenu s’adresse", "ce contenu s'adresse", "cette réponse s’adresse", "cette réponse s'adresse")

_locks, _next = {}, {}


# --------------------------------------------------------------------------- HTML tree
class Node:
    def __init__(self, tag="root", attrs=(), parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs), parent, []

    @property
    def classes(self):
        return (self.attrs.get("class") or "").split()

    def all(self, tag=None, cls=None):
        for c in self.children:
            if isinstance(c, Node):
                if (tag is None or c.tag == tag) and (cls is None or cls in c.classes):
                    yield c
                yield from c.all(tag, cls)

    def first(self, tag=None, cls=None):
        return next(self.all(tag, cls), None)

    def text(self):
        if self.tag in SKIP:
            return ""
        return re.sub(r"\s+", " ", " ".join(c.text() if isinstance(c, Node) else c for c in self.children)).strip()


class Tree(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = self.current = Node()
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


# --------------------------------------------------------------------------- HTML -> Markdown
def clean(s):
    return re.sub(r"[ \t\u00a0]+", " ", s).strip()


def inline(node, base):
    """Inline Markdown (gras, italique, liens) d'un nœud."""
    out = []
    for c in node.children:
        if isinstance(c, str):
            out.append(re.sub(r"\s+", " ", c))
            continue
        if c.tag in SKIP or c.tag in {"ul", "ol", "table"}:
            continue
        if c.tag == "br":
            out.append("  \n")
            continue
        inner = inline(c, base)
        if not inner.strip():
            out.append(inner)
            continue
        if c.tag in {"strong", "b"}:
            lead, core, trail = re.match(r"^(\s*)(.*?)(\s*)$", inner, re.S).groups()
            out.append(f"{lead}**{core}**{trail}")
        elif c.tag == "a" and c.attrs.get("href") and not c.attrs["href"].startswith(("#", "javascript")):
            out.append(f"[{inner.strip()}]({urllib.parse.urljoin(base, c.attrs['href'])})")
        else:
            out.append(inner)
    s = "".join(out)
    s = re.sub(r"\*\*\s*\*\*", "", s)
    return re.sub(r"[ \t\u00a0]+", " ", s)


def list_md(node, base, depth=0):
    lines, i = [], int(node.attrs.get("start", 1) or 1)
    for li in node.children:
        if not isinstance(li, Node) or li.tag != "li":
            continue
        bullet = f"{i}." if node.tag == "ol" else "-"
        i += 1
        lines.append("   " * depth + f"{bullet} {clean(inline(li, base))}")
        for sub in li.children:
            if isinstance(sub, Node) and sub.tag in {"ul", "ol"}:
                lines.extend(list_md(sub, base, depth + 1))
    return lines


def table_md(node, base):
    rows = [[clean(inline(td, base)).replace("|", "\\|").replace("\n", " ") for td in tr.children if isinstance(td, Node) and td.tag in {"td", "th"}]
            for tr in node.all("tr")]
    rows = [r for r in rows if r]
    if not rows:
        return []
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
    out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return out


def blocks_md(container, base):
    """Convertit un conteneur wysiwyg en blocs Markdown, dans l'ordre."""
    blocks = []
    for c in container.children:
        if isinstance(c, str):
            if c.strip():
                blocks.append(clean(c))
            continue
        if c.tag in SKIP:
            continue
        if c.tag in {"ul", "ol"}:
            blocks.append("\n".join(list_md(c, base)))
        elif c.tag == "table":
            blocks.append("\n".join(table_md(c, base)))
        elif re.fullmatch(r"h[1-6]", c.tag):
            blocks.append("### " + clean(inline(c, base)))
        elif c.tag in {"div", "section", "figure"}:
            if c.first("table"):
                blocks.append("\n".join(table_md(c.first("table"), base)))
            else:
                blocks.extend(blocks_md(c, base))
        else:
            t = clean(inline(c, base))
            if t:
                blocks.append(t)
    return [b for b in blocks if b.strip()]


# --------------------------------------------------------------------------- HTTP
def fetch(url, cache, refresh=False):
    key = hashlib.sha256(url.encode()).hexdigest()
    meta_p, html_p = cache / f"{key}.json", cache / f"{key}.html"
    if not refresh and meta_p.exists() and html_p.exists():
        return json.loads(meta_p.read_text()), html_p.read_text()
    host = urllib.parse.urlsplit(url).netloc
    lock = _locks.setdefault(host, threading.Lock())
    for attempt in range(4):
        with lock:
            wait = _next.get(host, 0) - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            _next[host] = time.monotonic() + 0.5
        try:
            req = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "text/html,application/xml", "Accept-Language": "fr-FR"})
            with urllib.request.urlopen(req, timeout=40) as r:
                body = r.read()
                meta = {"url": url, "final_url": r.url, "status": r.status,
                        "content_type": r.headers.get("Content-Type", ""),
                        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
                html = body.decode(r.headers.get_content_charset() or "utf-8", errors="replace")
            html_p.write_text(html)
            meta_p.write_text(json.dumps(meta, ensure_ascii=False))
            return meta, html
        except urllib.error.HTTPError as e:
            if e.code not in {429, 500, 502, 503, 504}:
                raise
            ra = e.headers.get("Retry-After", "")
            time.sleep(min(60, int(ra)) if ra.isdigit() else 2 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Échec HTTP : {url}")


def norm(href, base):
    u = urllib.parse.urlsplit(urllib.parse.urljoin(base, href))
    path = u.path if u.path.endswith("/") or "." in u.path.rsplit("/", 1)[-1] else u.path + "/"
    return urllib.parse.urlunsplit(("https", u.netloc.lower(), path, "", ""))


def in_scope(url, host, sections):
    u = urllib.parse.urlsplit(url)
    return u.netloc == host and any(u.path.startswith(f"/{s}/") for s in sections)


def sitemap_urls(host, cache, sections):
    urls = []
    try:
        _, idx = fetch(f"https://{host}/sitemap_index.xml", cache, refresh=True)
        for sm in re.findall(r"<loc>([^<]+)</loc>", idx):
            _, xml = fetch(sm.strip(), cache, refresh=True)
            urls += [norm(u.strip(), sm) for u in re.findall(r"<loc>([^<]+)</loc>", xml)]
    except Exception as e:  # le crawl reste la source principale
        print(f"[{host}] sitemap indisponible : {e}", flush=True)
    return {u for u in urls if in_scope(u, host, sections)}


# --------------------------------------------------------------------------- Page parsing
def parse(html, url, host, sections):
    tree = Tree(html).root
    main = tree.first("main")
    if main is None:
        raise ValueError("balise <main> absente")
    h1 = main.first("h1")
    title = h1.text() if h1 else ""
    crumbs = []
    bc = main.first("section", "breadcrumb") or tree.first(cls="breadcrumb")
    if bc:
        for a in bc.all("a"):
            t, href = a.text(), a.attrs.get("href", "")
            if t and "faq" in href:
                crumbs.append({"title": t, "url": norm(href, url)})
    crumbs = [c for c in crumbs if urllib.parse.urlsplit(c["url"]).path.strip("/").count("/") >= 1]  # retire "FAQ particuliers"

    modified = published = ""
    m = re.search(r'"dateModified":"([^"]+)"', html)
    if m:
        modified = m.group(1)
    m = re.search(r'"datePublished":"([^"]+)"', html)
    if m:
        published = m.group(1)

    body, audience, videos, links = [], [], [], []
    for sec in main.children:
        if not isinstance(sec, Node):
            continue
        for node in [sec] + list(sec.all("section")):
            cls = node.classes
            if "wp-block-bpce-block-rte" in cls:
                for w in node.all(cls="wysiwyg"):
                    for b in blocks_md(w, url):
                        plain = re.sub(r"[*_]", "", b).strip().lower()
                        (audience if plain.startswith(AUDIENCE_PREFIXES) else body).append(b)
                    for a in w.all("a"):
                        href = a.attrs.get("href", "")
                        if href and not href.startswith(("#", "javascript")):
                            links.append({"text": a.text(), "url": urllib.parse.urljoin(url, href)})
            elif "video-description" in cls and node.tag == "section":
                desc = node.first(cls="block-video-right")
                vtitle = vdesc = ""
                if desc:
                    ps = [p.text() for p in desc.all("p") if p.text()]
                    vtitle, vdesc = (ps[0] if ps else ""), " ".join(ps[1:])
                yt = next((b.attrs["data-video"] for b in node.all("button") if b.attrs.get("data-video")), "")
                videos.append({"title": vtitle, "description": vdesc, "url": f"https://www.youtube.com/watch?v={yt}" if yt else ""})
                body.append(f"> 🎬 Vidéo : **{vtitle}**" + (f" — {vdesc}" if vdesc else "") + (f" ({videos[-1]['url']})" if yt else ""))

    # Sous-pages listées (rubriques)
    children = []
    for blk in main.all(cls="links-listing-block"):
        for a in blk.all("a"):
            h = norm(a.attrs.get("href", ""), url)
            if in_scope(h, host, sections):
                children.append({"title": a.text(), "url": h})
    internal = {norm(a.attrs["href"], url) for a in main.all("a") if a.attrs.get("href")}
    internal = sorted(u for u in internal if in_scope(u, host, sections))

    answer_md = "\n\n".join(body).strip()
    return {
        "title": title, "breadcrumb": crumbs, "audience": " ".join(re.sub(r"[*]", "", a) for a in audience).strip(),
        "answer_markdown": answer_md, "videos": videos,
        "links": list({l["url"]: l for l in links}.values()),
        "children": list({c["url"]: c for c in children}.values()),
        "internal_links": internal, "date_modified": modified, "date_published": published,
        "kind": "question" if answer_md else "rubrique",
    }


# --------------------------------------------------------------------------- Crawl
def crawl(code, cache, sections, refresh):
    host = BANKS[code]["host"]
    rp = urllib.robotparser.RobotFileParser(f"https://{host}/robots.txt")
    try:
        rp.read()
    except Exception:
        rp = None
    roots = [f"https://{host}/{s}/" for s in sections]
    from_sitemap = sitemap_urls(host, cache, sections)
    todo, seen, pages, errors = deque(roots + sorted(from_sitemap)), set(), {}, []

    def work(u):
        if rp and not rp.can_fetch(AGENT, u):
            return u, None, "interdit par robots.txt"
        try:
            meta, html = fetch(u, cache, refresh)
            final = norm(meta["final_url"], u)
            if not in_scope(final, host, sections):
                return u, None, f"redirection hors périmètre : {final}"
            p = parse(html, final, host, sections)
            p.update(url=final, status=meta["status"], fetched_at=meta["fetched_at"])
            return u, p, None
        except Exception as e:
            return u, None, str(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        pending = {}
        while todo or pending:
            while todo and len(pending) < 4:
                u = todo.popleft()
                if u not in seen:
                    seen.add(u)
                    pending[pool.submit(work, u)] = u
            if not pending:
                continue
            done, _ = concurrent.futures.wait(pending, return_when=concurrent.futures.FIRST_COMPLETED)
            for f in done:
                pending.pop(f)
                u, p, err = f.result()
                if err:
                    errors.append({"url": u, "error": err})
                    print(f"[{code}] ERREUR {u} : {err}", flush=True)
                    continue
                pages.setdefault(p["url"], p)
                for link in p["internal_links"]:
                    if link not in seen:
                        todo.append(link)
                if len(pages) % 50 == 0:
                    print(f"[{code}] {len(pages)} pages, {len(todo)} en file", flush=True)
    return pages, errors, from_sitemap


def to_records(code, pages, sections):
    bank = BANKS[code]
    records = []
    for url, p in sorted(pages.items()):
        if p["kind"] != "question":
            continue
        parts = urllib.parse.urlsplit(url).path.strip("/").split("/")
        crumbs = p["breadcrumb"]
        category = crumbs[0]["title"] if len(crumbs) > 0 else parts[1] if len(parts) > 1 else ""
        subcategory = crumbs[1]["title"] if len(crumbs) > 1 else parts[2] if len(parts) > 3 else ""
        text = p["answer_markdown"]
        records.append({
            "id": f"{code}-{hashlib.sha1(url.encode()).hexdigest()[:12]}",
            "bank_code": code, "bank": bank["name"], "section": parts[0],
            "category": category, "subcategory": subcategory,
            "question": p["title"], "audience": p["audience"],
            "answer_markdown": text,
            "answer_text": re.sub(r"\*\*|\*|^#+ |^> ", "", text, flags=re.M),
            "videos": p["videos"], "links": p["links"],
            "url": url, "date_published": p["date_published"], "date_modified": p["date_modified"],
            "fetched_at": p["fetched_at"], "words": len(text.split()),
            "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
        })
    return records


def write_markdown(records, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    by_bank = {}
    for r in records:
        by_bank.setdefault(r["bank_code"], []).append(r)
    for code, recs in by_bank.items():
        lines = [f"# FAQ particuliers — {BANKS[code]['name']}", "",
                 f"{len(recs)} questions, collectées le {dt.date.today().isoformat()}.", ""]
        cat = sub = None
        for r in sorted(recs, key=lambda r: (r["category"], r["subcategory"], r["question"])):
            if r["category"] != cat:
                cat, sub = r["category"], None
                lines += [f"## {cat}", ""]
            if r["subcategory"] != sub:
                sub = r["subcategory"]
                lines += [f"### {sub}", ""]
            lines += [f"#### {r['question']}", "", f"Source : {r['url']}  ", f"Mis à jour : {r['date_modified'][:10]}", ""]
            if r["audience"]:
                lines += [f"*{r['audience']}*", ""]
            lines += [r["answer_markdown"], ""]
        (out_dir / f"faq_{code.lower()}.md").write_text("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--banks", nargs="+", default=list(BANKS), choices=list(BANKS))
    ap.add_argument("--sections", nargs="+", default=["faq-particuliers"])
    ap.add_argument("--cache", type=Path, default=ROOT_DIR / ".cache" / "html")
    ap.add_argument("--out", type=Path, default=ROOT_DIR / "data")
    ap.add_argument("--refresh", action="store_true", help="re-télécharger toutes les pages")
    args = ap.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=True)

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(args.banks)) as pool:
        futs = {pool.submit(crawl, c, args.cache, args.sections, args.refresh): c for c in args.banks}
        for f in concurrent.futures.as_completed(futs):
            results[futs[f]] = f.result()

    all_records, report = [], {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "sections": args.sections, "banks": {}}
    for code in args.banks:
        pages, errors, sm = results[code]
        recs = to_records(code, pages, args.sections)
        all_records += recs
        crawled = set(pages)
        report["banks"][code] = {
            "pages_visitees": len(pages), "questions": len(recs),
            "rubriques": sum(p["kind"] == "rubrique" for p in pages.values()),
            "urls_sitemap": len(sm), "urls_sitemap_non_collectees": sorted(sm - crawled),
            "questions_vides": [p["url"] for p in pages.values() if p["kind"] == "rubrique" and urllib.parse.urlsplit(p["url"]).path.strip("/").count("/") >= 3],
            "mots_total": sum(r["words"] for r in recs), "erreurs": errors,
        }
    with open(args.out / "faq_corpus.jsonl", "w") as f:
        for r in all_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    write_markdown(all_records, args.out / "markdown")
    (args.out / "scrape_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    for code, s in report["banks"].items():
        print(f"{code}: {s['questions']} questions / {s['pages_visitees']} pages, {s['mots_total']} mots, "
              f"{len(s['erreurs'])} erreurs, {len(s['urls_sitemap_non_collectees'])} URLs sitemap manquantes")


if __name__ == "__main__":
    main()
