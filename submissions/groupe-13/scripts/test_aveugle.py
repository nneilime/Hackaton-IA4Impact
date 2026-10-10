"""Test à l'aveugle : fabrique 17 dossiers absents du corpus (images transformées ou falsifiées, factures TXT
modifiées autrement que dans les données fournies), les analyse SANS cache OCR et compare au résultat attendu.

    python scripts/test_aveugle.py            # deux moteurs OCR
    set NO_TESS=1 && python scripts/test_aveugle.py   # RapidOCR seul (Windows sans Tesseract)
    set REUSE=1 && python scripts/test_aveugle.py     # réutilise les extractions déjà calculées (règles seules)
"""
import sys, json, warnings, time, hashlib
warnings.filterwarnings("ignore")
ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from pathlib import Path
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont
from sentinel.ocr.extract import extract_bordereau
from sentinel.b2parser import parse_b2
from sentinel.rules import run_rules
import os, sentinel.ocr.reader as RD
if os.environ.get("NO_TESS"): RD._TES = None
C = ROOT / 'data' / 'corpus' / 'General-main'
J, T = C/'Bordereaux jpg', C/'Factures txt'
OUT = ROOT / 'data' / 'test_aveugle'; OUT.mkdir(parents=True, exist_ok=True); CACHE = ROOT / 'data' / 'cache' / 'ocr'
FONT = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf', '/Library/Fonts/Arial.ttf') if Path(f).exists()), None)

def cached(name):
    from sentinel import ocrcache
    ext, status, _ = ocrcache.read(hashlib.sha256((J/name).read_bytes()).hexdigest())
    if ext is None:
        raise SystemExit(f"Extraction de {name} absente ou obsolète ({status}) : lancer d'abord « python -m sentinel.cli extract »")
    return ext

def overwrite(name, field, new_text, out):
    ext = cached(name); x0,y0,x1,y1 = ext['fields'][field]['text_box']
    im = Image.open(J/name).convert('RGB'); d = ImageDraw.Draw(im)
    d.rectangle([x0-1,y0-1,x1+1,y1+1], fill='white')
    f = ImageFont.truetype(FONT, int((y1-y0)*0.95)) if FONT else ImageFont.load_default()
    d.text((x0, y0-1), new_text, fill='black', font=f)
    im.save(out, quality=92); return out

def txt_edit(name, fn, out):
    lines = (T/name).read_bytes().decode('latin-1').split('\r\n')
    lines = fn(lines); Path(out).write_bytes('\r\n'.join(lines).encode('latin-1')); return out

def sub(line, start, end, val):   # positions 1-based inclusives, longueur conservée
    assert len(val) == end-start+1
    return line[:start-1] + val + line[end:]

cases = []
# ---- contrôles négatifs : documents authentiques transformés (aucun écart attendu)
g = cv2.imread(str(J/'Facture2_01.jpg'))
g2 = cv2.resize(g, None, fx=1.12, fy=1.12, interpolation=cv2.INTER_AREA)
cv2.imwrite(str(OUT/'n1.jpg'), g2, [cv2.IMWRITE_JPEG_QUALITY, 70])
cases.append(('N1', 'Facture2_01 agrandie de 12 % et recompressée (JPEG 70)', OUT/'n1.jpg', T/'Facture2_01.txt', []))
g = cv2.imread(str(J/'Facture1_02.jpg')); M = np.float32([[1,0,14],[0,1,11]])
cv2.imwrite(str(OUT/'n2.jpg'), cv2.warpAffine(g, M, (g.shape[1], g.shape[0]), borderValue=(255,255,255)))
cases.append(('N2', 'Facture1_02 décalée de 14 px / 11 px', OUT/'n2.jpg', T/'Facture1_02.txt', []))
cv2.imwrite(str(OUT/'n3.jpg'), cv2.rotate(cv2.imread(str(J/'Facture3_13.jpg')), cv2.ROTATE_180))
cases.append(('N3', 'Facture3_13 scannée à l\'envers (180°)', OUT/'n3.jpg', T/'Facture3_13.txt', []))
# ---- bordereaux falsifiés (nouvelle police, valeurs jamais vues)
cases.append(('I1', 'Facture1_02 : zone 8 réécrite 818,97 → 828,97', overwrite('Facture1_02.jpg','Z8','828,97',OUT/'i1.jpg'), T/'Facture1_02.txt', ['R12','R20']))
cases.append(('I2', 'Facture2_01 : lot réécrit 351 → 357', overwrite('Facture2_01.jpg','Z3','357',OUT/'i2.jpg'), T/'Facture2_01.txt', ['R03']))
cases.append(('I3', 'Facture1_02 : n° facture réécrit 260800002 → 260800092', overwrite('Facture1_02.jpg','Z4','260800092',OUT/'i3.jpg'), T/'Facture1_02.txt', ['R04']))
cases.append(('I4', 'Facture3_01 : montant total réécrit 448.78 → 498.78', overwrite('Facture3_01.jpg','Z13','498.78',OUT/'i4.jpg'), T/'Facture3_01.txt', ['R20']))
im = cv2.imread(str(J/'Facture3_01.jpg')); im[2110:2255, 1385:1684] = 255; cv2.imwrite(str(OUT/'i5.jpg'), im)
cases.append(('I5', 'Facture3_01 : signature numérique du directeur effacée', OUT/'i5.jpg', T/'Facture3_01.txt', ['R21']))
im = cv2.imread(str(J/'Facture2_01.jpg')); im[935:1055, 970:1145] = 255; cv2.imwrite(str(OUT/'i6.jpg'), im)
cases.append(('I6', 'Facture2_01 : cachets des cases 1 et 2 (zone 11) effacés', OUT/'i6.jpg', T/'Facture2_01.txt', ['R18']))
# ---- factures TXT modifiées autrement que dans le corpus
def t1(L):
    i = next(i for i,l in enumerate(L) if l[35:36]=='M' and 'YYYY405' in l); L[i] = L[i].replace('YYYY405','YYYY406',1); return L
cases.append(('T1', 'Facture2_01.txt : un code CCAM YYYY405 → YYYY406', J/'Facture2_01.jpg', txt_edit('Facture2_01.txt', t1, OUT/'t1.txt'), ['R15','R19']))
def t2(L):
    i = next(i for i,l in enumerate(L) if l.startswith('2')); L[i] = sub(L[i], 12, 24, L[i][11:22] + '99'); return L
cases.append(('T2', 'Facture3_01.txt : n° d\'assuré modifié (2 derniers chiffres)', J/'Facture3_01.jpg', txt_edit('Facture3_01.txt', t2, OUT/'t2.txt'), ['R05']))
def t3(L):
    i = next(i for i,l in enumerate(L) if l.startswith('3') and l[55:58]=='EMI'); del L[i:i+2]; return L
cases.append(('T3', 'Facture1_02.txt : prestation EMI supprimée du fichier', J/'Facture1_02.jpg', txt_edit('Facture1_02.txt', t3, OUT/'t3.txt'), ['R11']))
def t4(L):
    i = next(i for i,l in enumerate(L) if l.startswith('5')); L[i] = sub(L[i], 58, 65, '00095000'); return L
cases.append(('T4', 'Facture2_01.txt : TotalHonoraires 936,68 → 950,00', J/'Facture2_01.jpg', txt_edit('Facture2_01.txt', t4, OUT/'t4.txt'), ['R17']))
def t5(L):
    i = next(i for i,l in enumerate(L) if l.startswith('3') and l[55:58]=='FJA'); L[i] = sub(L[i], 56, 60, 'DIA  '); return L
cases.append(('T5', 'Facture2_01.txt : FJA remplacé par « DIA » (acte jamais vu)', J/'Facture2_01.jpg', txt_edit('Facture2_01.txt', t5, OUT/'t5.txt'), ['R08','R13']))
def t6(L):
    i = next(i for i,l in enumerate(L) if l[35:36]=='S' and l.startswith('4')); L[i] = sub(L[i], 120, 123, '4199'); return L
cases.append(('T6', 'Facture2_01.txt : NumeroGH d\'un 4-S → 4199', J/'Facture2_01.jpg', txt_edit('Facture2_01.txt', t6, OUT/'t6.txt'), ['R16']))

# ---- cas supplémentaires
im = cv2.imread(str(J/'Facture3_13.jpg')); im = cv2.GaussianBlur(im, (3,3), 0)
cv2.imwrite(str(OUT/'n4.jpg'), im, [cv2.IMWRITE_JPEG_QUALITY, 60])
cases.append(('N4', 'Facture3_13 légèrement floue + JPEG qualité 60', OUT/'n4.jpg', T/'Facture3_13.txt', []))
ext = cached('Facture2_01.jpg')
row = next(r for r in ext['tables']['Z10'] if r['cells']['code']['value'] == 'APC')
x0,y0,x1,y1 = row['cells']['code']['text_box']
im = Image.open(J/'Facture2_01.jpg').convert('RGB'); d = ImageDraw.Draw(im)
d.rectangle([x0-1,y0-1,x1+1,y1+1], fill='white'); d.text((x0, y0-1), 'ACO', fill='black', font=ImageFont.truetype(FONT, int((y1-y0)*0.95)) if FONT else ImageFont.load_default())
im.save(OUT/'i7.jpg', quality=92)
cases.append(('I7', 'Facture2_01 : acte APC réécrit « ACO » en zone 10', OUT/'i7.jpg', T/'Facture2_01.txt', ['R14','R19']))

rows = []
for cid, desc, jpg, txt, expected in cases:
    t = time.time()
    saved = OUT / f'{cid}_extraction{"_notess" if os.environ.get("NO_TESS") else ""}.json'
    if os.environ.get('REUSE') and saved.exists():
        ext = json.loads(saved.read_text(encoding='utf-8'))   # extraction déjà calculée (règles seules)
    else:
        ext = extract_bordereau(jpg)      # lecture OCR complète, sans cache
        saved.write_text(json.dumps(ext, ensure_ascii=False), encoding='utf-8')
    res = run_rules(parse_b2(txt), ext)
    got = sorted(r['rule_id'] for r in res if r['status']=='ANOMALIE')
    nv = sorted(r['rule_id'] for r in res if r['status']=='NON_VERIFIABLE')
    ok = got == sorted(expected) and not nv
    rows.append((cid, desc, expected, got, nv, ok, round(time.time()-t,1), ext['layout'].get('family'), ext['layout'].get('rotation')))
    print(cid, 'OK ' if ok else 'ÉCART', desc, '| attendu', expected, 'obtenu', got, 'non vérifiable', nv, flush=True)
json.dump(rows, open(OUT/('results_notess.json' if os.environ.get('NO_TESS') else 'results.json'),'w'), ensure_ascii=False)
