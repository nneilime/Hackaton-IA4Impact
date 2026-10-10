#!/usr/bin/env python3
"""Centres officiels des communes des cinq départements (API Découpage administratif, geo.api.gouv.fr).

Sert à poser, au centre de leur commune, les groupes de petits immeubles et de maisons :
un immeuble de moins de 10 logements, ou une maison, ne s'affiche jamais seul à sa place.
Lancement : python3 -I reel/outils/communes.py   →   reel/donnees/communes.json
"""
import json, sys, time, urllib.request
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SORTIE = RACINE / 'reel' / 'donnees' / 'communes.json'
DEPARTEMENTS = ['31', '33', '34', '40', '64']

def lire(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'foraine-prototype-hackathon/1.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

communes = {}
for d in DEPARTEMENTS:
    liste = lire(f'https://geo.api.gouv.fr/departements/{d}/communes?fields=nom,code,centre,population&format=json')
    for c in liste:
        lon, lat = c['centre']['coordinates']
        communes[c['code']] = {'nom': c['nom'], 'centre': [round(lon, 5), round(lat, 5)]}
    print(d, len(liste), 'communes', file=sys.stderr)
    time.sleep(0.3)

SORTIE.write_text(json.dumps({
    'source': {'nom': 'API Découpage administratif (geo.api.gouv.fr), centre des communes', 'date_lecture': date.today().isoformat(), 'licence': 'Licence Ouverte 2.0'},
    'communes': communes,
}, ensure_ascii=False, separators=(',', ':')))
print(SORTIE, len(communes), file=sys.stderr)
