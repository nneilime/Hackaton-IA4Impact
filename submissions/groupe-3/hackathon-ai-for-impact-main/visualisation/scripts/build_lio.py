"""Construit carte/lio.js à partir du GTFS liO (data/lio/) : tracés des lignes et arrêts desservis."""
import csv, json, math, os
from collections import defaultdict
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = lambda f: open(os.path.join(ROOT, 'data', 'lio', f), encoding='utf-8-sig')

routes = {r['route_id']: r for r in csv.DictReader(G('routes.txt'))}
agencies = {a['agency_id']: a['agency_name'] for a in csv.DictReader(G('agency.txt'))}

shape_route, trip_route = {}, {}
for t in csv.DictReader(G('trips.txt')):
    trip_route[t['trip_id']] = t['route_id']
    if t['shape_id']: shape_route[t['shape_id']] = t['route_id']

def km(a, b):
    return math.hypot((a[1] - b[1]) * math.cos(math.radians(a[0])), a[0] - b[0]) * 111.2

pts = defaultdict(list)
for r in csv.DictReader(G('shapes.txt')):
    if r['shape_id'] in shape_route:
        pts[r['shape_id']].append((int(r['shape_pt_sequence']), float(r['shape_pt_lat']), float(r['shape_pt_lon'])))
lines = defaultdict(list)  # route -> liste de tracés simplifiés (1 point / ~300 m)
for sid, p in pts.items():
    p.sort(); p = [(a, o) for _, a, o in p]
    out = [p[0]]
    for q in p[1:-1]:
        if km(out[-1], q) > 0.3: out.append(q)
    out.append(p[-1])
    out = [[round(a, 5), round(o, 5)] for a, o in out]
    if out not in lines[shape_route[sid]]: lines[shape_route[sid]].append(out)

stop_routes = defaultdict(set)
for r in csv.DictReader(G('stop_times.txt')):
    if r['trip_id'] in trip_route: stop_routes[r['stop_id']].add(trip_route[r['trip_id']])
stops = []
for s in csv.DictReader(G('stops.txt')):
    if s['stop_id'] in stop_routes:
        stops.append([s['stop_name'], round(float(s['stop_lat']), 5), round(float(s['stop_lon']), 5),
                      sorted(stop_routes[s['stop_id']])])

out = {
    'routes': {rid: [r['route_short_name'], r['route_long_name'], '#' + (r['route_color'] or '7a7a7a'),
                     agencies.get(r['agency_id'], '')] for rid, r in routes.items() if rid in lines},
    'lines': lines, 'stops': stops,
}
with open(os.path.join(ROOT, 'carte', 'lio.js'), 'w', encoding='utf-8') as f:
    f.write('window.LIO=' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';')
print(len(out['routes']), 'lignes,', sum(map(len, lines.values())), 'tracés,', len(stops), 'arrêts')
