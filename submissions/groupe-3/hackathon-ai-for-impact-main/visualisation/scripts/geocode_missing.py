"""Géocode (IGN Géoplateforme) les arrêts absents du référentiel des gares SNCF."""
import csv, json, os, urllib.request, urllib.parse, re
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pref={str(x['codes_uic'])[:7] for x in json.load(open(os.path.join(ROOT,'data','gares.json'),encoding='utf-8'))}
names={}
for r in csv.DictReader(open(os.path.join(ROOT,'data','desserte.csv'),encoding='utf-8')):
    m=re.search(r'(\d{7,8})$',r['code'])
    if not m or m.group(1)[:7] not in pref: names[r['code']]=r['stop']
out={}
for code,n in names.items():
    q=re.sub(r'\bV3\b','',n).replace(' - ',' ')
    for typ in ('', 'municipality'):
        url='https://data.geopf.fr/geocodage/search?'+urllib.parse.urlencode({'q':q,'limit':1,'lat':43.6,'lon':2.5,**({'type':typ} if typ else {})})
        try: f=json.load(urllib.request.urlopen(url,timeout=15))['features']
        except Exception: f=[]
        if f and f[0]['properties'].get('score',0)>0.4:
            lon,lat=f[0]['geometry']['coordinates']; out[code]=[n,lat,lon,f[0]['properties']['label']]; break
for v in out.values(): print(v)
print('NON TROUVÉS:', set(names.values())-{v[0] for v in out.values()})
json.dump(out,open(os.path.join(ROOT,'data','arrets_geocodes.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=1)
