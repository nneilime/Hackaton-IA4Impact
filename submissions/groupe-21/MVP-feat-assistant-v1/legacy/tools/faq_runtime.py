#!/usr/bin/env python3
"""Bank-filtered FAQ search and on-demand official HTML context. Stdlib only."""
import argparse
from collections import Counter
import datetime as dt
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import unicodedata
import urllib.parse
import urllib.request

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'sources'))
from collecter import Tree, Node

HOSTS = {'CE': 'www.caisse-epargne.fr', 'BP': 'www.banquepopulaire.fr'}
STOP = set('comment que quoi quel quelle quels quelles qui je tu il elle on nous vous mon ma mes le la les un une des de du en et ou au aux pour par sur dans est sont ce cette ces puis peux faire'.split())


def tokens(text):
    text = unicodedata.normalize('NFKD', text.casefold())
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return [t for t in re.findall(r'[a-z0-9]+', text) if t not in STOP and len(t) > 1]


@lru_cache(maxsize=1)
def records():
    return {r['source_id']: r for line in (BASE / 'corpus.jsonl').read_text().splitlines() if line.strip() for r in [json.loads(line)]}


def search_faq(query, bank_code, limit=5):
    if bank_code not in {'CE', 'BP', 'BOTH'}:
        raise ValueError('bank_code doit être CE, BP ou BOTH pour une comparaison explicite.')
    limit = max(1, min(int(limit), 15))
    query_tokens = tokens(query)
    if not query_tokens:
        return []
    output = []
    for bank in (['CE', 'BP'] if bank_code == 'BOTH' else [bank_code]):
        docs = [r for r in records().values() if r['bank_code'] == bank]
        counters = [Counter(tokens(r['retrieval_text'])) for r in docs]
        df = Counter(t for counter in counters for t in counter)
        avg = sum(sum(c.values()) for c in counters) / len(counters)
        ranked = []
        for record, counter in zip(docs, counters):
            length, score = sum(counter.values()), 0.0
            for term in set(query_tokens):
                frequency = counter[term]
                if frequency:
                    idf = math.log(1 + (len(docs) - df[term] + .5) / (df[term] + .5))
                    score += idf * frequency * 2.2 / (frequency + 1.2 * (.25 + .75 * length / avg))
            # Exact own-question and variant terms keep browser-specific pages distinct.
            own = set(tokens(record['question'] + ' ' + record['variant']))
            score += 1.5 * len(own.intersection(query_tokens))
            if score > 0:
                ranked.append((score, record))
        for score, record in sorted(ranked, key=lambda x: (-x[0], x[1]['source_id']))[:limit]:
            output.append({key: record[key] for key in ['source_id', 'group_id', 'bank_code', 'question', 'variant', 'source_url', 'answerability']} | {'score': round(score, 4), 'is_answer': False})
    return output


def in_scope(url, bank):
    u = urllib.parse.urlsplit(url)
    return u.scheme == 'https' and u.netloc == HOSTS[bank] and u.path.startswith('/faq-particuliers/') and not u.query


class ScopedRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, bank):
        self.bank = bank

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not in_scope(newurl, self.bank):
            raise ValueError('Redirection hors de la FAQ autorisée.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def classes(node):
    return set(node.attrs.get('class', '').split())


def ancestors(node):
    node = node.parent
    while node:
        yield node
        node = node.parent


def without_lists(node):
    return re.sub(r'\s+', ' ', ' '.join(c.text() if isinstance(c, Node) else c for c in node.children if not isinstance(c, Node) or c.tag not in {'ul', 'ol'})).strip()


def list_items(node):
    result = []
    for item in node.children:
        if not isinstance(item, Node) or item.tag != 'li':
            continue
        nested = [{'ordered': c.tag == 'ol', 'items': list_items(c)} for c in item.children if isinstance(c, Node) and c.tag in {'ul', 'ol'}]
        result.append({'text': without_lists(item), 'nested_lists': nested})
    return result


def text_blocks(node):
    for c in node.children:
        if not isinstance(c, Node):
            continue
        if c.tag in {'script', 'style', 'svg', 'noscript'}:
            continue
        if c.tag in {'p', 'h2', 'h3', 'h4'}:
            if c.text():
                yield {'type': 'paragraph' if c.tag == 'p' else 'heading', 'text': c.text()}
        elif c.tag in {'ul', 'ol'}:
            yield {'type': 'list', 'ordered': c.tag == 'ol', 'start': c.attrs.get('start', '1'), 'items': list_items(c)}
        elif c.tag == 'table':
            rows = []
            for tr in c.all('tr'):
                cells = [{'is_header': cell.tag == 'th', 'text': cell.text(), 'colspan': cell.attrs.get('colspan', '1'), 'rowspan': cell.attrs.get('rowspan', '1')} for cell in tr.children if isinstance(cell, Node) and cell.tag in {'th', 'td'}]
                if cells:
                    rows.append(cells)
            yield {'type': 'table', 'rows': rows}
        else:
            yield from text_blocks(c)


def flatten(blocks):
    lines = []
    def items(rows, depth=0):
        for item in rows:
            lines.append('  ' * depth + '- ' + item['text'])
            for nested in item['nested_lists']:
                items(nested['items'], depth + 1)
    for block in blocks:
        if block['type'] in {'paragraph', 'heading', 'video_description'}:
            lines.append(block['text'])
        elif block['type'] == 'list':
            items(block['items'])
        elif block['type'] == 'table':
            lines.extend(' | '.join(cell['text'] for cell in row) for row in block['rows'])
    return '\n\n'.join(lines)


def extract(html, url):
    tree = Tree(html).root
    main = next(tree.all('main'), None)
    if main is None:
        raise ValueError('Structure inattendue : contenu principal absent.')
    h1 = next(main.all('h1'), None)
    if h1 is None:
        raise ValueError('Structure inattendue : titre absent.')
    blocks, links, media, containers = [], [], [], []
    for node in main.all():
        if 'wysiwyg' in classes(node) and any('wp-block-bpce-block-rte' in classes(a) for a in ancestors(node)):
            if any('wysiwyg' in classes(a) for a in ancestors(node)):
                continue
            containers.append(node)
            blocks.extend(text_blocks(node))
        elif 'video-description' in classes(node) and not any('video-description' in classes(a) for a in ancestors(node)):
            containers.append(node)
            seen = set()
            for p in node.all('p'):
                if 'video-mask-info' not in classes(p) and p.text() and p.text() not in seen:
                    seen.add(p.text())
                    blocks.append({'type': 'video_description', 'text': p.text()})
    if not blocks:
        raise ValueError('Aucun bloc de réponse reconnu ; ne pas répondre depuis les extraits.')
    for node in containers:
        for picture in node.all('img'):
            src = picture.attrs.get('data-src') or picture.attrs.get('src', '')
            if src and not src.startswith('data:'):
                value = urllib.parse.urljoin(url, src)
                if value not in media:
                    media.append(value)
        for anchor in node.all('a'):
            href = anchor.attrs.get('href', '')
            if href and href != '#':
                value = urllib.parse.urljoin(url, href)
                if value not in links:
                    links.append(value)
                if urllib.parse.urlsplit(value).netloc in {'www.youtube.com', 'youtu.be', 'player.vimeo.com'} and value not in media:
                    media.append(value)
    # Detect new unrecognized editorial blocks instead of silently losing conditions.
    known = set(containers)
    unparsed = []
    excluded = {'modal', 'hero-banner', 'breadcrumb', 'publish-modification-date-section', 'links-listing-block'}
    for n in main.all():
        if n.tag not in {'p', 'li', 'h2', 'h3', 'td', 'th'} or not n.text():
            continue
        chain = [n, *ancestors(n)]
        if any(a in known for a in chain) or any(classes(a).intersection(excluded) for a in chain):
            continue
        unparsed.append(n.tag)
    canonical = next((n.attrs.get('href') for n in tree.all('link') if n.attrs.get('rel') == 'canonical'), url)
    time_node = next(main.all('time'), None)
    reference = flatten(blocks)
    return {'question': h1.text(), 'canonical_url': canonical, 'source_dates_display': time_node.text() if time_node else None, 'answer_blocks': blocks, 'reference_text': reference, 'structured_answer_sha256': hashlib.sha256(json.dumps(blocks, ensure_ascii=False, sort_keys=True).encode()).hexdigest(), 'related_links': links, 'media_links': media, 'media_transcribed': False, 'content_limitations': ['illustrations et vidéos non transcrites', 'documents liés non lus'], 'unparsed_editorial_tags': unparsed, 'extraction_complete_for_recognized_html': not unparsed}


def read_source(source_id, bank_code, cache_dir=None):
    record = records().get(source_id)
    if record is None:
        return {'status': 'error', 'error': 'source_id inconnu.', 'factual_answer_allowed': False}
    if bank_code not in HOSTS or record['bank_code'] != bank_code:
        return {'status': 'error', 'error': 'La source ne correspond pas à la banque choisie.', 'factual_answer_allowed': False}
    url = record['source_url']
    if not in_scope(url, bank_code):
        return {'status': 'error', 'error': 'URL hors périmètre.', 'factual_answer_allowed': False}
    try:
        if cache_dir:
            key = hashlib.sha256(url.encode()).hexdigest()
            directory = Path(cache_dir)
            body = (directory / (key + '.html')).read_bytes()
            meta = json.loads((directory / (key + '.json')).read_text())
            read_at, mode = meta['collected_at'], 'historical_cache'
            final_url = meta['final_url']
        else:
            opener = urllib.request.build_opener(ScopedRedirect(bank_code))
            request = urllib.request.Request(url, headers={'User-Agent': 'FAQSourceReader/1.0 (single public help page)', 'Accept': 'text/html'})
            with opener.open(request, timeout=25) as response:
                if response.status != 200 or 'text/html' not in response.headers.get('Content-Type', ''):
                    raise ValueError('Réponse HTTP non HTML ou statut inattendu.')
                body, final_url = response.read(4_000_001), response.url
            if len(body) > 4_000_000:
                raise ValueError('Page trop volumineuse pour ce lecteur.')
            read_at, mode = dt.datetime.now(dt.timezone.utc).isoformat(), 'live_http'
        if not in_scope(final_url, bank_code):
            raise ValueError('URL finale hors périmètre.')
        result = extract(body.decode('utf-8', errors='strict'), final_url)
        if not in_scope(result['canonical_url'], bank_code):
            raise ValueError('URL canonique hors périmètre.')
        actual_hash = hashlib.sha256(body).hexdigest()
        return {'status': 'ok', 'source_id': source_id, 'bank_code': bank_code, 'source_url': url, 'final_url': final_url, 'read_at': read_at, 'read_mode': mode, 'html_sha256': actual_hash, 'snapshot_collected_at': record['snapshot_collected_at'], 'html_changed_since_snapshot': actual_hash != record['snapshot_html_sha256'], 'structured_answer_hash_basis': 'ordered_blocks_v1; distinct from the original snapshot answer hash', 'factual_answer_allowed': result['extraction_complete_for_recognized_html'] and mode == 'live_http', 'historical_evidence_only': mode != 'live_http', **result}
    except Exception as exc:
        return {'status': 'error', 'source_id': source_id, 'bank_code': bank_code, 'source_url': url, 'error': str(exc), 'factual_answer_allowed': False}


def main():
    parser = argparse.ArgumentParser(description='Recherche FAQ et preuve HTML officielle, sans réponse générée.')
    sub = parser.add_subparsers(dest='command', required=True)
    search = sub.add_parser('search')
    search.add_argument('query')
    search.add_argument('--bank', required=True, choices=['CE', 'BP', 'BOTH'])
    search.add_argument('--limit', type=int, default=5)
    read = sub.add_parser('read')
    read.add_argument('source_id')
    read.add_argument('--bank', required=True, choices=['CE', 'BP'])
    read.add_argument('--cache-dir', type=Path)
    args = parser.parse_args()
    result = search_faq(args.query, args.bank, args.limit) if args.command == 'search' else read_source(args.source_id, args.bank, args.cache_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
