"""Construit carte/data.js à partir des fichiers bruts de data/.

- data/desserte.csv        (export de « Détail desserte (1).xlsx » via xlsx_to_csv.py)
- data/Data_Hackathon.csv  (axes, O/D et indicateurs mensuels par train)
- data/gares.json          (gares SNCF : code UIC -> coordonnées)
- data/rfn.geojson         (tracé du réseau ferré national, pour suivre les voies)
"""
import csv, json, math, os, re, sys
from collections import defaultdict
import networkx as nx
from scipy.spatial import cKDTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(ROOT, 'data', *p)
BBOX = (-1.2, 41.9, 5.6, 46.6)  # lon_min, lat_min, lon_max, lat_max (Occitanie élargie)

def tomin(t):
    if not t: return None
    h, m, *_ = t.split(':')
    return int(h) * 60 + int(m)

# --- gares -------------------------------------------------------------------
gares = {}
for g in json.load(open(D('gares.json'), encoding='utf-8')):
    p = g.get('position_geographique')
    if p and g.get('codes_uic'):
        for c in str(g['codes_uic']).split(';'):
            gares[c.strip()[:8]] = (p['lat'], p['lon'], g['nom'])

# --- dessertes -----------------------------------------------------------------
circ = defaultdict(list)  # (date, train) -> [(ordre, code, name, arr, dep)]
with open(D('desserte.csv'), encoding='utf-8') as f:
    for r in csv.DictReader(f):
        circ[(r['date'], r['train'])].append((int(r['ordre'] or 0), r['code'], r['stop'], r['arr'], r['dep']))

# Arrêts absents du référentiel SNCF (haltes du Train Jaune, arrêts de car) :
# coordonnées relevées manuellement / via le géocodeur IGN (scripts/geocode_missing.py).
MANUEL = {
    'Serdinya': (42.5665, 2.3186), 'Nyer': (42.5410, 2.2630), 'Thuès les Bains': (42.5285, 2.2490),
    'Sauto': (42.5110, 2.1570), 'Planès': (42.4930, 2.1370), 'Bolquère - Eyne': (42.4970, 2.0870),
    'Estavar': (42.4680, 2.0000), 'Err': (42.4440, 2.0310), 'Sainte-Léocadie': (42.4410, 1.9980),
    'Osséja': (42.4150, 1.9770), 'Ur les Escaldes': (42.4590, 1.9280), 'Bena Fanes': (42.4550, 1.9150),
    'Portbou': (42.4265, 3.1590), 'Luchon': (42.7936, 0.5945), 'Marignac - Saint-Béat': (42.9170, 0.6640),
    'Saléchan - Siradan': (42.9600, 0.6400), 'Loures - Barbazan': (43.0300, 0.6160),
    'Saint-Césaire V3': (43.8180, 4.3300), 'Aguessac Avenue de Causses': (44.1555, 3.0979),
    'Aguessac Bellevue': (44.1560, 3.0912), "Severac d'Aveyron Lapanouse": (44.3442, 3.0346),
    'Severac-D-Aveyron Recoules': (44.3446, 2.9794), "Gaillac-d'Aveyron Bourg": (44.3565, 2.9064),
    'Gaillac-D-Aveyron Lugans': (44.3600, 2.8950), "Grèzes Séverac-l'Eglise": (44.3656, 2.8521),
    'Laissac Place du Foiral': (44.3822, 2.8217), 'Bertholène Centre': (44.3950, 2.7840),
    'Montrozier Gages Pont': (44.3920, 2.6779), 'Onet-le-Château la Roquette': (44.3692, 2.6285),
    'Onet-le-Château Route de Sévérac': (44.3624, 2.5999), 'Loubiere Canabols': (44.3750, 2.6600),
    'Verrieres Engayresque': (44.2110, 3.0350), "Séverac d'Aveyron Embrachement le Massegros": (44.3000, 3.1100),
}

stops, stop_idx, missing = [], {}, set()
def sidx(code, name):
    if code in stop_idx: return stop_idx[code]
    m = re.search(r'(\d{7,8})$', code)
    uic = m.group(1)[:7] if m else None
    hit = next((v for k, v in gares.items() if uic and k.startswith(uic)), None)
    if not hit and name in MANUEL: hit = MANUEL[name]
    if not hit:
        missing.add(name); return None
    stop_idx[code] = len(stops)
    stops.append([name, round(hit[0], 5), round(hit[1], 5)])
    return stop_idx[code]

patterns, pat_idx = [], {}
services = defaultdict(list)  # (train, pattern) -> dates
dates = sorted({d for d, _ in circ})
for (date, train), rows in circ.items():
    rows.sort()
    seq, prev = [], -1
    for _, code, name, arr, dep in rows:
        i = sidx(code, name)
        if i is None: continue
        a, d = tomin(arr), tomin(dep)
        a = a if a is not None else d
        d = d if d is not None else a
        while a < prev: a += 1440
        while d < a: d += 1440
        prev = d
        seq.append((i, a, d))
    if len(seq) < 2: continue
    key = tuple(seq)
    if key not in pat_idx:
        pat_idx[key] = len(patterns)
        patterns.append([x for s in seq for x in s])
    services[(int(train), pat_idx[key])].append(dates.index(date))

# --- tracés sur voies ----------------------------------------------------------
G = nx.Graph()
def nk(c): return (round(c[0], 5), round(c[1], 5))
def dist(a, b):
    dx = (a[0] - b[0]) * math.cos(math.radians(a[1])); dy = a[1] - b[1]
    return math.hypot(dx, dy) * 111.2
def inb(c): return BBOX[0] <= c[0] <= BBOX[2] and BBOX[1] <= c[1] <= BBOX[3]
for ft in json.load(open(D('rfn.geojson'), encoding='utf-8'))['features']:
    geom = ft.get('geometry') or {}
    lines = geom.get('coordinates', [])
    if geom.get('type') == 'LineString': lines = [lines]
    for ln in lines:
        for a, b in zip(ln, ln[1:]):
            if inb(a) or inb(b):
                a, b = nk(a), nk(b)
                if a != b: G.add_edge(a, b, w=dist(a, b))
# relie les extrémités de tronçons très proches (jonctions imparfaites)
nodes = list(G.nodes)
tree = cKDTree(nodes)
for i, j in tree.query_pairs(0.0015):
    if not G.has_edge(nodes[i], nodes[j]):
        G.add_edge(nodes[i], nodes[j], w=dist(nodes[i], nodes[j]))
snap = [nodes[tree.query((s[2], s[1]))[1]] for s in stops]

paths = {}
for p in patterns:
    for k in range(0, len(p) - 3, 3):
        a, b = p[k], p[k + 3]
        if (a, b) in paths or (b, a) in paths: continue
        straight = dist((stops[a][2], stops[a][1]), (stops[b][2], stops[b][1]))
        try:
            nodes_path = nx.astar_path(G, snap[a], snap[b], heuristic=dist, weight='w')
            length = sum(dist(u, v) for u, v in zip(nodes_path, nodes_path[1:]))
            pts = nodes_path if length < straight * 2.5 + 3 else None
        except nx.NetworkXNoPath:
            pts = None
        if pts is None:
            pts = [(stops[a][2], stops[a][1]), (stops[b][2], stops[b][1])]
        # simplification légère : 1 point tous les ~300 m
        out, last = [pts[0]], pts[0]
        for q in pts[1:-1]:
            if dist(last, q) > 0.3: out.append(q); last = q
        out.append(pts[-1])
        paths[f'{a}-{b}'] = [[round(q[1], 5), round(q[0], 5)] for q in out]

# --- infos mensuelles (Data_Hackathon.csv) ---------------------------------------
MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
        'septembre', 'octobre', 'novembre', 'décembre']
info = defaultdict(dict)
with open(D('Data_Hackathon.csv'), encoding='utf-8-sig') as f:
    for r in csv.DictReader(f, delimiter=';'):
        m = MOIS.index(r['Mois'].strip().lower()) + 1
        info[r['N° Train'].strip()][f"{r['Année']}-{m:02d}"] = [
            r['Axe'], r['Origine / Destination'], r['Frequentation'],
            r['Taux régularité du train'], r['Nombre de suppressions'], r['Minutes perdues']]

out = {
    'dates': dates, 'stops': stops, 'patterns': patterns, 'paths': paths,
    'services': [[t, p, ds] for (t, p), ds in services.items()],
    'info': info,
}
os.makedirs(os.path.join(ROOT, 'carte'), exist_ok=True)
with open(os.path.join(ROOT, 'carte', 'data.js'), 'w', encoding='utf-8') as f:
    f.write('window.DATA=' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';')
print(f'{len(circ)} circulations, {len(stops)} arrêts, {len(patterns)} horaires types, '
      f'{len(services)} services, {len(paths)} tronçons', file=sys.stderr)
if missing: print('Arrêts sans coordonnées :', sorted(missing), file=sys.stderr)
