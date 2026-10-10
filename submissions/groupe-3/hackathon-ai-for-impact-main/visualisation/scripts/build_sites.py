"""Construit carte/sites.js à partir de data/top-des-sites-touristiques-2021-enrichi.json."""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = os.path.join(ROOT, 'data', 'top-des-sites-touristiques-2021-enrichi.json')
sites = [s for s in json.load(open(src, encoding='utf-8')) if s.get('latitude') and s.get('longitude')]
with open(os.path.join(ROOT, 'carte', 'sites.js'), 'w', encoding='utf-8') as f:
    f.write('window.SITES=' + json.dumps(sites, ensure_ascii=False, separators=(',', ':')) + ';')
print(len(sites), 'sites')
