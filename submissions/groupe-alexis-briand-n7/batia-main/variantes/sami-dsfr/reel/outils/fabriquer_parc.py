#!/usr/bin/env python3
"""Fabrique reel/donnees/parc-reel.json : un enregistrement par groupe de bâtiments
BDNB d'In'li Sud-Ouest (SIREN 304234636), enrichi par les sources publiques.

À lancer UNE FOIS, avec Internet (les réponses brutes sont gardées dans reel/cache/,
une relance ne réinterroge pas les services) :

    python3 -I reel/outils/fabriquer_parc.py                       # 31, 33, 34, 40, 64
    python3 -I reel/outils/fabriquer_parc.py --departements 31,33  # fusionne dans le JSON existant

Python 3 standard uniquement (urllib, sans pyproj ni shapely).
Vie privée : rien à l'échelle du logement (aucun complément d'adresse, étage, porte,
numéro de DPE en clair ; pour les maisons, seulement des comptes agrégés).
"""
import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import math
import os
import re
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRUT = os.path.join(RACINE, "reel-brut")
CACHE = os.path.join(RACINE, "reel", "cache")
SORTIE = os.path.join(RACINE, "reel", "donnees", "parc-reel.json")
SIREN = "304234636"
AUJOURDHUI = dt.date.today()
DATE_LECTURE = AUJOURDHUI.isoformat()
NOMS_DEP = {"31": "Haute-Garonne", "33": "Gironde", "34": "Hérault", "40": "Landes",
            "64": "Pyrénées-Atlantiques"}
UA = "BâtIA-prototype-non-officiel/1.0 (hackathon ; lecture ponctuelle mise en cache)"

URL_BDNB = "https://api.bdnb.io/v1/bdnb/donnees/batiment_groupe_complet"
URL_DPE = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant/lines"
URL_GEORISQUES = "https://georisques.gouv.fr/api/v1/gaspar/catnat"
URL_GPU = "https://apicarto.ign.fr/api/gpu/assiette-sup-s"
URL_HUBEAU = "https://hubeau.eaufrance.fr/api/v1/qualite_eau_potable/resultats_dis"

CHAMPS_BDNB = [
    "batiment_groupe_id", "libelle_adr_principale_ban", "cle_interop_adr_principale_ban",
    "l_cle_interop_adr", "l_parcelle_id", "code_commune_insee", "libelle_commune_insee",
    "code_iris", "annee_construction", "nb_log", "nb_niveau", "hauteur_mean",
    "usage_niveau_1_txt", "mat_mur_txt", "classe_bilan_dpe", "conso_5_usages_ep_m2",
    "type_energie_chauffage", "type_installation_chauffage", "type_generateur_chauffage",
    "type_generateur_chauffage_anciennete", "type_installation_ecs", "type_generateur_ecs",
    "type_generateur_ecs_anciennete", "type_ventilation", "alea_argile",
    "nb_classe_bilan_dpe_a", "nb_classe_bilan_dpe_b", "nb_classe_bilan_dpe_c",
    "nb_classe_bilan_dpe_d", "nb_classe_bilan_dpe_e", "nb_classe_bilan_dpe_f",
    "nb_classe_bilan_dpe_g", "date_reception_dpe", "quartier_prioritaire", "geom_groupe",
    "surface_emprise_sol",
]
# Champs DPE demandés : aucun ne désigne un logement (pas de complément d'adresse,
# d'étage, de porte ni de nom). Le numéro de DPE ne sert qu'à dédoublonner : il est
# remplacé par une empreinte dès la mise en cache et n'est jamais écrit dans la sortie.
CHAMPS_DPE = [
    "numero_dpe", "date_etablissement_dpe", "etiquette_dpe", "conso_5_usages_par_m2_ep",
    "type_generateur_chauffage_principal", "type_generateur_n1_installation_n1",
    "type_generateur_n1_ecs_n1", "type_installation_chauffage", "type_energie_principale_chauffage", "type_ventilation",
    "id_rnb", "type_batiment",
]
CALENDRIER_2G = {
    "source": "ARCEP, fiche pratique « Extinction des réseaux mobiles 2G et 3G » (mise à jour du "
              "10/09/2026) et calendrier Orange d'extinction de la 2G par département (PDF ARCEP)",
    "url": "https://www.arcep.fr/mes-demarches-et-services/consommateurs/fiches-pratiques/"
           "extinction-reseaux-mobiles-2g-3g.html",
    "date_lecture": "2026-10-10",
    "operateurs": {
        "Orange": {"31": "2026-06-09", "33": "2026-10-20", "34": "2026-10-06",
                   "40": "2026-05-12", "64": "2026-05-12"},
        "SFR": {"tous": "2026-11-15"},
        "Bouygues Telecom": {"tous": "2026-12-01 au 2026-12-15"},
        "Free Mobile": {"tous": "pas de 2G en propre (itinérance sur Orange)"},
    },
    "derniere_extinction_par_departement": {d: "2026-12-15" for d in NOMS_DEP},
}

OCTETS = [0]
ECHECS = Counter()
VERROU_OCTETS = threading.Lock()


class Limiteur:
    """Espace les appels vers un service (débit maximal partagé entre fils)."""

    def __init__(self, intervalle):
        self.intervalle = intervalle
        self.verrou = threading.Lock()
        self.prochain = 0.0

    def attendre(self):
        with self.verrou:
            maintenant = time.monotonic()
            t = max(maintenant, self.prochain)
            self.prochain = t + self.intervalle
        if t > time.monotonic():
            time.sleep(t - time.monotonic())


LIM_BDNB = Limiteur(0.6)      # 120 appels/min
LIM_DPE = Limiteur(0.15)      # 600 requêtes/min
LIM_GPU = Limiteur(0.2)       # 5 req/s
LIM_HUBEAU = Limiteur(0.2)    # 5 req/s
LIM_GEORISQUES = Limiteur(0.1)


def obtenir(url, limiteur, delai=45, essais=3):
    """GET JSON ; None en cas d'échec (rien n'est mis en cache dans ce cas)."""
    for essai in range(essais):
        limiteur.attendre()
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept": "application/json", "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=delai) as r:
                brut = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    with VERROU_OCTETS:
                        OCTETS[0] += len(brut)
                    brut = gzip.decompress(brut)
                else:
                    with VERROU_OCTETS:
                        OCTETS[0] += len(brut)
            return json.loads(brut)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(2.0 * (essai + 1))
                continue
            return None
        except Exception:
            time.sleep(1.0 + essai)
    return None


def en_cache(cle, fabriquer):
    """Relit reel/cache/<cle> ou appelle fabriquer() et garde le résultat (s'il n'est pas None)."""
    chemin = os.path.join(CACHE, cle)
    if os.path.exists(chemin):
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    valeur = fabriquer()
    if valeur is None:
        return None
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    tmp = chemin + ".tmp%d" % threading.get_ident()
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(valeur, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, chemin)
    return valeur


# ---------------------------------------------------------------- Lambert-93 -> WGS84
A_GRS80 = 6378137.0
E_GRS80 = 0.0818191910428158


def _m(phi):
    return math.cos(phi) / math.sqrt(1 - (E_GRS80 * math.sin(phi)) ** 2)


def _t(phi):
    es = E_GRS80 * math.sin(phi)
    return math.tan(math.pi / 4 - phi / 2) / ((1 - es) / (1 + es)) ** (E_GRS80 / 2)


_PHI1, _PHI2, _PHI0 = math.radians(44), math.radians(49), math.radians(46.5)
_LAMBDA0 = math.radians(3)
_N = (math.log(_m(_PHI1)) - math.log(_m(_PHI2))) / (math.log(_t(_PHI1)) - math.log(_t(_PHI2)))
_F = _m(_PHI1) / (_N * _t(_PHI1) ** _N)
_RHO0 = A_GRS80 * _F * _t(_PHI0) ** _N


def lambert93_vers_wgs84(x, y):
    """Projection conique conforme de Lambert (EPSG:2154, RGF93 ~ WGS84) -> (lon, lat)."""
    dx = x - 700000.0
    dy = _RHO0 - (y - 6600000.0)
    rho = math.copysign(math.hypot(dx, dy), _N)
    t = (rho / (A_GRS80 * _F)) ** (1 / _N)
    theta = math.atan2(dx, dy)
    lon = theta / _N + _LAMBDA0
    phi = math.pi / 2 - 2 * math.atan(t)
    for _ in range(15):
        es = E_GRS80 * math.sin(phi)
        nouveau = math.pi / 2 - 2 * math.atan(t * ((1 - es) / (1 + es)) ** (E_GRS80 / 2))
        if abs(nouveau - phi) < 1e-12:
            phi = nouveau
            break
        phi = nouveau
    return math.degrees(lon), math.degrees(phi)


def _aire_centre(anneau):
    a = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(anneau, anneau[1:] + anneau[:1]):
        k = x1 * y2 - x2 * y1
        a += k
        cx += (x1 + x2) * k
        cy += (y1 + y2) * k
    a /= 2
    if abs(a) < 1e-9:
        n = len(anneau)
        return 0.0, sum(p[0] for p in anneau) / n, sum(p[1] for p in anneau) / n
    return abs(a), cx / (6 * a), cy / (6 * a)


def _douglas_peucker(points, tol):
    if len(points) < 3:
        return points
    (x1, y1), (x2, y2) = points[0], points[-1]
    dmax, imax = -1.0, 0
    lg = math.hypot(x2 - x1, y2 - y1)
    for i in range(1, len(points) - 1):
        x0, y0 = points[i]
        d = (abs((y2 - y1) * x0 - (x2 - x1) * y0 + x2 * y1 - y2 * x1) / lg) if lg else math.hypot(x0 - x1, y0 - y1)
        if d > dmax:
            dmax, imax = d, i
    if dmax <= tol:
        return [points[0], points[-1]]
    return _douglas_peucker(points[:imax + 1], tol)[:-1] + _douglas_peucker(points[imax:], tol)


def simplifier(anneau, maxi=40):
    pts = [tuple(p[:2]) for p in anneau]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) + 1 <= maxi:
        return pts + [pts[0]]
    tol = 0.2
    while True:
        # coupe l'anneau en deux pour que Douglas-Peucker garde sa forme
        moitie = len(pts) // 2
        a = _douglas_peucker(pts[:moitie + 1], tol)
        b = _douglas_peucker(pts[moitie:] + [pts[0]], tol)
        res = a[:-1] + b[:-1]
        if len(res) + 1 <= maxi:
            return res + [res[0]]
        tol *= 1.5


def geometrie(geom):
    """Centroïde [lon, lat] et emprise simplifiée (anneau extérieur du plus grand polygone)."""
    if not geom or not geom.get("coordinates"):
        return None, None
    polys = geom["coordinates"] if geom.get("type") == "MultiPolygon" else [geom["coordinates"]]
    total = sx = sy = 0.0
    plus_grand, aire_max = None, -1.0
    for poly in polys:
        if not poly:
            continue
        aire, cx, cy = _aire_centre([tuple(p[:2]) for p in poly[0]])
        poids = aire if aire > 0 else 1e-6
        total += poids
        sx += cx * poids
        sy += cy * poids
        if aire > aire_max:
            aire_max, plus_grand = aire, poly[0]
    if not total:
        return None, None
    lon, lat = lambert93_vers_wgs84(sx / total, sy / total)
    emprise = [[round(v, 6) for v in lambert93_vers_wgs84(x, y)] for x, y in simplifier(plus_grand)]
    return [round(lon, 6), round(lat, 6)], emprise


# ---------------------------------------------------------------- période des générateurs
def periode(libelle):
    """Période d'installation lue dans un libellé de générateur -> [début, fin] (None = borne ouverte)."""
    if not libelle:
        return None
    s = libelle.lower().replace(" ", " ")
    m = re.search(r"entre\s+(\d{4})\s+et\s+(\d{4})", s)
    if m:
        return [int(m.group(1)), int(m.group(2))]
    m = re.search(r"(?<!\d)(\d{4})\s*[-–]\s*(\d{4})(?!\d)", s)
    if m:
        return [int(m.group(1)), int(m.group(2))]
    m = re.search(r"(?:après|apres)\s+(\d{4})", s)
    if m:
        return [int(m.group(1)) + 1, None]
    m = re.search(r"(?:à partir de|a partir de|depuis)\s+(\d{4})", s)
    if m:
        return [int(m.group(1)), None]
    m = re.search(r"avant\s+(\d{4})", s)
    if m:
        return [None, int(m.group(1)) - 1]
    m = re.search(r"(?:en|de)\s+(\d{4})(?!\d)", s)
    if m:
        return [int(m.group(1)), int(m.group(1))]
    return None


def _tests_periode():
    assert periode("Chaudière gaz standard 2001-2015") == [2001, 2015]
    assert periode("Chaudière gaz à condensation après 2015") == [2016, None]
    assert periode("Chaudière fioul standard avant 1991") == [None, 1990]
    assert periode("PAC air/eau installée entre 2008 et 2014") == [2008, 2014]
    assert periode("Radiateur électrique NFC, NF** et NF***") is None
    assert periode(None) is None


# ---------------------------------------------------------------- kit et DGFiP
def lire_kit(dep):
    with open(os.path.join(BRUT, "bdnb_%s.json" % dep), encoding="utf-8") as f:
        return json.load(f)


def parcelle14(dep, commune, prefixe, section, plan):
    prefixe = (prefixe or "").strip()
    prefixe = prefixe.zfill(3) if prefixe else "000"
    section = (section or "").strip()
    section = section.rjust(2, "0")
    return "%s%s%s%s%s" % (dep, (commune or "").strip().zfill(3), prefixe, section, (plan or "").strip().zfill(4))


def locaux_dgfip(dep):
    """{parcelle14: nombre de locaux uniques en propriété} pour le SIREN d'In'li Sud-Ouest."""
    def fabriquer():
        chemin = os.path.join(BRUT, "pm_%s.csv" % dep)
        if not os.path.exists(chemin):
            return None
        uniques = set()
        with open(chemin, encoding="utf-8", errors="replace", newline="") as f:
            entete = next(csv.reader([f.readline()], delimiter=";"))
            i = {nom: k for k, nom in enumerate(entete)}
            for ligne in f:
                if SIREN not in ligne:
                    continue
                c = next(csv.reader([ligne], delimiter=";"))
                if len(c) < len(entete) or c[i["N° SIREN"]].strip() != SIREN:
                    continue
                if not c[i["Code droit"]].strip().startswith("P"):
                    continue
                p = parcelle14(dep, c[i["Code Commune"]], c[i["Préfixe"]], c[i["Section"]], c[i["N° plan"]])
                uniques.add((p, c[i["Bâtiment"]], c[i["Entrée"]], c[i["Niveau"]], c[i["Porte"]], c[i["N° Majic"]]))
        compte = Counter(u[0] for u in uniques)
        return dict(sorted(compte.items()))
    return en_cache("dgfip/locaux_%s.json" % dep, fabriquer) or {}


# ---------------------------------------------------------------- BDNB
def bdnb_paquet(ids):
    cle = "bdnb/%s.json" % hashlib.sha1(",".join(sorted(ids)).encode()).hexdigest()[:16]

    def fabriquer():
        q = urllib.parse.urlencode({
            "batiment_groupe_id": "in.(%s)" % ",".join(ids),
            "select": ",".join(CHAMPS_BDNB), "limit": "10"})
        return obtenir(URL_BDNB + "?" + q, LIM_BDNB)
    return en_cache(cle, fabriquer)


# ---------------------------------------------------------------- DPE ADEME
def _nettoyer_dpe(lignes):
    propres = []
    for l in lignes:
        d = {k: l.get(k) for k in CHAMPS_DPE if k != "numero_dpe"}
        num = l.get("numero_dpe")
        d["empreinte"] = hashlib.sha1(num.encode()).hexdigest()[:12] if num else None
        propres.append(d)
    return propres


def dpe_groupe(gid, cles):
    if not cles:
        return []

    def fabriquer():
        tout = []
        for k in range(0, len(cles), 25):
            morceau = cles[k:k + 25]
            qs = "identifiant_ban:(%s)" % " OR ".join('"%s"' % c for c in morceau)
            url = URL_DPE + "?" + urllib.parse.urlencode(
                {"qs": qs, "size": "1000", "select": ",".join(CHAMPS_DPE)})
            pages = 0
            while url and pages < 5:
                rep = obtenir(url, LIM_DPE)
                if rep is None:
                    return None
                tout.extend(_nettoyer_dpe(rep.get("results", [])))
                url = rep.get("next") if len(rep.get("results", [])) >= 1000 else None
                pages += 1
        return tout
    return en_cache("dpe2/%s.json" % gid, fabriquer)


# ---------------------------------------------------------------- risques, eau
GEORISQUES_OK = [None]


def georisques_commune(code):
    if GEORISQUES_OK[0] is False:
        return None

    def fabriquer():
        arretes, url, pages = [], URL_GEORISQUES + "?" + urllib.parse.urlencode(
            {"code_insee": code, "page_size": "100"}), 0
        while url and pages < 10:
            rep = obtenir(url, LIM_GEORISQUES, delai=10, essais=1)
            if rep is None:
                return None
            for a in rep.get("data", []):
                arretes.append({"libelle": a.get("libelle_risque_jo"), "debut": a.get("date_debut_evt"),
                                "arrete": a.get("date_publication_arrete") or a.get("date_publication_jo")})
            url = rep.get("next")
            pages += 1
        return arretes
    return en_cache("georisques/%s.json" % code, fabriquer)


def gpu_pm1(gid, position):
    if not position:
        return None

    def fabriquer():
        geom = json.dumps({"type": "Point", "coordinates": position}, separators=(",", ":"))
        rep = obtenir(URL_GPU + "?" + urllib.parse.urlencode({"geom": geom, "categorie": "PM1"}), LIM_GPU, delai=60)
        if rep is None:
            return None
        return [{k: (f.get("properties") or {}).get(k) for k in ("suptype", "nomsuplitt", "nomass", "idgen", "typeass")}
                for f in rep.get("features", [])]
    return en_cache("gpu/%s.json" % gid, fabriquer)


def durete_commune(code):
    def fabriquer():
        mesures = []
        for param in ("7972", "1345"):
            url = URL_HUBEAU + "?" + urllib.parse.urlencode({
                "code_commune": code, "code_parametre": param, "size": "20", "sort": "desc",
                "fields": "date_prelevement,resultat_numerique,libelle_unite,code_parametre"})
            rep = obtenir(url, LIM_HUBEAU)
            if rep is None:
                return None
            for m in rep.get("data", []):
                if m.get("resultat_numerique") is not None and (m.get("libelle_unite") or "").strip() in ("°f", "°F"):
                    mesures.append([m.get("date_prelevement"), m.get("resultat_numerique"), param])
        return mesures
    mesures = en_cache("hubeau/%s.json" % code, fabriquer)
    if not mesures:
        return None, None
    mesures.sort(key=lambda m: m[0] or "", reverse=True)
    recentes = mesures[:10]
    return round(statistics.median(m[1] for m in recentes), 1), (recentes[0][0] or "")[:10]


# ---------------------------------------------------------------- 2G (ANFR)
def extraire_anfr_2g(OUT):
    """Stations 2G (GSM 900/1800, hors GSM-R) des 31, 33, 34, 40, 64 tirées de l'export ANFR
    (data.gouv.fr) : lecture du répertoire du zip par requêtes Range, puis des seuls membres utiles
    (SUP_EMETTEUR, SUP_STATION, SUP_SUPPORT), décompressés en flux. Écrit OUT (JSON)."""
    import struct, zlib, io, zipfile, collections

    T0 = time.time()
    UA = {'User-Agent': 'f-reel-prototype/1.0 (lecture ponctuelle de donnees ouvertes)'}
    NB = [0]
    DEPTS = {'31', '33', '34', '40', '64'}
    AUJ = DATE_LECTURE
    API = 'https://www.data.gouv.fr/api/1/datasets/donnees-sur-les-installations-radioelectriques-de-plus-de-5-watts-1/'

    def ouvrir(url, rng=None):
        h = dict(UA)
        if rng: h['Range'] = 'bytes=%d-%d' % rng
        return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=90)

    def lire(url, rng=None):
        r = ouvrir(url, rng); d = r.read(); NB[0] += len(d)
        return r.status, r.headers, d

    def repertoire(url):
        st, hd, _ = lire(url, (0, 0))
        if st != 206: raise SystemExit('Range refusé (statut %s)' % st)
        total = int(hd['Content-Range'].split('/')[1])
        tl = min(total, 65536 + 22)
        _, _, tail = lire(url, (total - tl, total - 1))
        i = tail.rfind(b'PK\x05\x06')
        _, _, _, _, n, cds, cdo, _ = struct.unpack('<IHHHHIIH', tail[i:i+22])
        if cdo == 0xFFFFFFFF or n == 0xFFFF or cds == 0xFFFFFFFF:
            j = tail.rfind(b'PK\x06\x07')
            _, _, z64o, _ = struct.unpack('<IIQI', tail[j:j+20])
            _, _, z = lire(url, (z64o, z64o + 55))
            _, _, _, _, _, _, _, n, cds, cdo = struct.unpack('<IQHHIIQQQQ', z[:56])
        s = cdo - (total - tl)
        cd = tail[s:s+cds] if s >= 0 else lire(url, (cdo, cdo + cds - 1))[2]
        ents, p = [], 0
        for _ in range(n):
            f = struct.unpack('<IHHHHHHIIIHHHHHII', cd[p:p+46])
            meth, cs, us, fnl, exl, cml, lo = f[4], f[8], f[9], f[10], f[11], f[12], f[16]
            name = cd[p+46:p+46+fnl].decode('utf-8', 'replace')
            ex = cd[p+46+fnl:p+46+fnl+exl]; q = 0
            while q + 4 <= len(ex):
                hid, hl = struct.unpack('<HH', ex[q:q+4])
                if hid == 1:
                    v, k = ex[q+4:q+4+hl], 0
                    if us == 0xFFFFFFFF: us = struct.unpack('<Q', v[k:k+8])[0]; k += 8
                    if cs == 0xFFFFFFFF: cs = struct.unpack('<Q', v[k:k+8])[0]; k += 8
                    if lo == 0xFFFFFFFF: lo = struct.unpack('<Q', v[k:k+8])[0]; k += 8
                q += 4 + hl
            ents.append(dict(name=name, method=meth, csize=cs, usize=us, loff=lo))
            p += 46 + fnl + exl + cml
        return total, ents

    def lignes(url, e):
        _, _, lh = lire(url, (e['loff'], e['loff'] + 29))
        assert lh[:4] == b'PK\x03\x04'
        fnl, exl = struct.unpack('<HH', lh[26:30])
        deb = e['loff'] + 30 + fnl + exl
        r = ouvrir(url, (deb, deb + e['csize'] - 1)); assert r.status == 206
        if e['method'] not in (0, 8): raise SystemExit('méthode %d' % e['method'])
        d = zlib.decompressobj(-15) if e['method'] == 8 else None
        buf = b''; premier = True
        while True:
            c = r.read(1 << 20)
            if not c: break
            NB[0] += len(c)
            buf += d.decompress(c) if d else c
            ls = buf.split(b'\n'); buf = ls.pop()
            for l in ls:
                if premier: l = l.lstrip(b'\xef\xbb\xbf'); premier = False
                yield l.rstrip(b'\r')
        if d: buf += d.flush()
        for l in buf.split(b'\n'):
            if l.strip(): yield l.rstrip(b'\r')

    def champs(l): return [x.strip().strip('"') for x in l.decode('latin-1').split(';')]

    def iso(s):
        s = s.strip()
        if not s: return ''
        if '/' in s:
            p = s.split()[0].split('/')
            return '%s-%s-%s' % (p[2], p[1].zfill(2), p[0].zfill(2)) if len(p) == 3 else ''
        return s[:10]

    def dec(dg, mn, sc, h):
        v = float(dg.replace(',', '.') or 0) + float(mn.replace(',', '.') or 0) / 60 + float(sc.replace(',', '.') or 0) / 3600
        return -v if h.upper() in ('W', 'O', 'S') else v

    # Métadonnées data.gouv
    _, _, raw = lire(API); meta = json.loads(raw)
    lic = meta.get('license'); res = meta.get('resources', [])
    zips = [r for r in res if (r.get('url') or '').lower().endswith('.zip')]
    princ = sorted([r for r in zips if 'export-etalab-data' in r['url']], key=lambda r: r.get('last_modified') or '')[-1]
    autres = [r for r in zips if 'export-etalab-data' not in r['url']]
    print('principale :', princ['url'], princ.get('last_modified'), princ.get('filesize'), file=sys.stderr)
    for r in autres[:6]: print('  autre :', r.get('title'), r['url'], r.get('last_modified'), r.get('filesize'), file=sys.stderr)
    URL = princ['url']
    total, ents = repertoire(URL)
    for e in ents: print('  membre', e['name'], e['method'], e['csize'], e['usize'], file=sys.stderr)
    def membre(cle):
        c = [e for e in ents if cle in e['name'].upper()]
        return c[0] if c else None
    em, sta, sup, exp = membre('EMETTEUR'), membre('SUP_STATION') or membre('STATION'), membre('SUP_SUPPORT'), membre('EXPLOITANT')

    # Exploitants : archive de référence (petite) si absents de l'archive principale
    expl = {}
    def lit_expl(octets_lignes):
        hdr = None
        for l in octets_lignes:
            try: t = l.decode('utf-8')
            except UnicodeDecodeError: t = l.decode('cp1252')
            f = [x.strip().strip('"') for x in t.split(';')]
            if hdr is None: hdr = [h.upper() for h in f]; continue
            if len(f) >= 2: expl[f[hdr.index('ADM_ID')]] = f[hdr.index('ADM_LB_NOM')]
    if exp:
        lit_expl(lignes(URL, exp))
    else:
        refs = sorted([r for r in autres if (r.get('filesize') or 0) < 200000 and r.get('filesize')], key=lambda r: r.get('last_modified') or '')
        ref = refs[-1]; print('référence :', ref['url'], file=sys.stderr)
        _, _, z = lire(ref['url'])
        with zipfile.ZipFile(io.BytesIO(z)) as zf:
            nm = [n for n in zf.namelist() if 'EXPLOITANT' in n.upper()][0]
            lit_expl(zf.read(nm).lstrip(b'\xef\xbb\xbf').splitlines())
    print('exploitants :', len(expl), file=sys.stderr)

    # 1) émetteurs GSM en service
    gsm = set(); systemes = collections.Counter(); sans_date = futur = 0; hdr = None
    for l in lignes(URL, em):
        f = champs(l)
        if hdr is None: hdr = [h.upper() for h in f]; print('EMETTEUR', hdr, file=sys.stderr); iS, iN, iD = hdr.index('EMR_LB_SYSTEME'), hdr.index('STA_NM_ANFR'), (hdr.index('EMR_DT_SERVICE') if 'EMR_DT_SERVICE' in hdr else None); continue
        s = f[iS].upper()
        if not s.startswith('GSM'): continue
        systemes[s] += 1
        if s.replace(' ', '').replace('-', '') .startswith('GSMR'): continue
        if iD is not None:
            d = iso(f[iD])
            if not d: sans_date += 1; continue
            if d > AUJ: futur += 1; continue
        gsm.add(f[iN])
    print('systèmes GSM*', dict(systemes), 'sans date', sans_date, 'futur', futur, 'stations', len(gsm), file=sys.stderr)

    # 2) stations -> exploitant
    adm = {}; hdr = None
    for l in lignes(URL, sta):
        f = champs(l)
        if hdr is None: hdr = [h.upper() for h in f]; print('STATION', hdr, file=sys.stderr); iN, iA = hdr.index('STA_NM_ANFR'), hdr.index('ADM_ID'); continue
        if f[iN] in gsm: adm[f[iN]] = f[iA]

    # 3) supports -> coordonnées et commune
    pos = {}; hdr = None; ecarts = 0
    for l in lignes(URL, sup):
        f = champs(l)
        if hdr is None:
            hdr = [h.upper() for h in f]; print('SUPPORT', hdr, file=sys.stderr)
            ix = {k: hdr.index(k) for k in ['STA_NM_ANFR', 'COM_CD_INSEE', 'COR_NB_DG_LAT', 'COR_NB_MN_LAT', 'COR_NB_SC_LAT', 'COR_CD_NS_LAT', 'COR_NB_DG_LON', 'COR_NB_MN_LON', 'COR_NB_SC_LON', 'COR_CD_EW_LON']}
            nh = len(hdr); continue
        if len(f) != nh: ecarts += 1; continue
        n = f[ix['STA_NM_ANFR']]
        if n not in gsm or n in pos: continue
        insee = f[ix['COM_CD_INSEE']]
        if insee.isdigit() and len(insee) == 4: insee = '0' + insee
        dep = insee[:2]
        if dep not in DEPTS: continue
        try:
            lat = dec(f[ix['COR_NB_DG_LAT']], f[ix['COR_NB_MN_LAT']], f[ix['COR_NB_SC_LAT']], f[ix['COR_CD_NS_LAT']])
            lon = dec(f[ix['COR_NB_DG_LON']], f[ix['COR_NB_MN_LON']], f[ix['COR_NB_SC_LON']], f[ix['COR_CD_EW_LON']])
        except ValueError: continue
        pos[n] = (round(lon, 6), round(lat, 6), dep)
    print('lignes support mal formées', ecarts, file=sys.stderr)

    stations = sorted([[p[0], p[1], p[2], expl.get(adm.get(n, ''), 'INCONNU')] for n, p in pos.items()], key=lambda s: (s[2], s[3], s[0], s[1]))
    nomf = URL.rsplit('/', 1)[-1]
    sortie = {"source": "ANFR, installations radioélectriques de plus de 5 W (data.gouv.fr)", "url": URL,
              "date_export": "%s (fichier %s, données au %s)" % ((princ.get('last_modified') or '')[:10], nomf, nomf[:4] + '-' + nomf[4:6] + '-' + nomf[6:8]),
              "date_lecture": AUJ, "licence": {'lov2': 'Licence Ouverte v2.0 (Etalab)'}.get(lic, lic), "stations": stations}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as fo: json.dump(sortie, fo, ensure_ascii=False, separators=(',', ':'))
    c = collections.Counter((s[2], s[3]) for s in stations)
    for k in sorted(c): print(k[0], k[1], c[k])
    print('par département', dict(sorted(collections.Counter(s[2] for s in stations).items())))
    print('total', len(stations), 'octets téléchargés', NB[0], 'durée %.1f s' % (time.time() - T0))


def stations_2g():
    chemin = os.path.join(CACHE, "anfr_2g_stations.json")
    if not os.path.exists(chemin):
        try:
            extraire_anfr_2g(chemin)
        except (Exception, SystemExit) as e:
            print("ANFR : extraction impossible (%s) ; antenne_2g vaudra null" % e, file=sys.stderr)
            return None
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def distance_m(lon1, lat1, lon2, lat2):
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def plus_proche(position, stations):
    if not position or not stations:
        return None
    lon, lat = position
    meilleur = None
    for s in stations:
        if abs(s[1] - lat) > 0.3 or abs(s[0] - lon) > 0.4:
            continue
        d = distance_m(lon, lat, s[0], s[1])
        if meilleur is None or d < meilleur[0]:
            meilleur = (d, s[3])
    if meilleur is None:
        for s in stations:
            d = distance_m(lon, lat, s[0], s[1])
            if meilleur is None or d < meilleur[0]:
                meilleur = (d, s[3])
    return meilleur


# ---------------------------------------------------------------- synthèse par immeuble
def mode(valeurs):
    c = Counter(v for v in valeurs if v)
    return c.most_common(1)[0][0] if c else None


def r1(v):
    return None if v is None else round(float(v), 1)


def gen_chauffage(d):
    """Générateur de chauffage d'un DPE : le principal, sinon le n°1 de l'installation n°1."""
    return d.get("type_generateur_chauffage_principal") or d.get("type_generateur_n1_installation_n1")


def resume_dpe(dpe):
    """Synthèse à l'échelle de l'immeuble des DPE (déjà dédoublonnés)."""
    for d in dpe:
        d["_gen_ch"] = gen_chauffage(d)
    dpe = sorted((d for d in dpe if d.get("date_etablissement_dpe")), key=lambda d: d["date_etablissement_dpe"])
    limite = (AUJOURDHUI - dt.timedelta(days=5 * 365 + 1)).isoformat()
    recents = [d for d in dpe if d["date_etablissement_dpe"] >= limite] or dpe
    gen_ch = mode(d.get("_gen_ch") for d in recents)
    gen_ecs = mode(d.get("type_generateur_n1_ecs_n1") for d in recents)
    installs = [d.get("type_installation_chauffage") for d in dpe if d.get("type_installation_chauffage")]
    part_coll = (sum(1 for v in installs if v.strip().lower().startswith("collectif")) / len(installs)) if installs else None
    # Remplacement daté : entre deux DPE successifs, la période du générateur passe à une période
    # strictement plus récente, et aucun DPE ultérieur ne revient à une période plus ancienne
    # (sinon ce sont deux logements équipés différemment, pas un remplacement).
    remplacements = []

    def fin(p):
        return p[1] if p[1] is not None else p[0]

    def debut(p):
        return p[0] if p[0] is not None else p[1]
    for usage, champ in (("chauffage", "_gen_ch"), ("eau chaude", "type_generateur_n1_ecs_n1")):
        seq = [(d, periode(d.get(champ))) for d in dpe]
        seq = [(d, p) for d, p in seq if p]
        for j in range(1, len(seq)):
            (dp, pp), (dc, pc) = seq[j - 1], seq[j]
            if fin(pp) is None or debut(pc) is None or debut(pc) <= fin(pp):
                continue
            if any(fin(p) is not None and fin(p) < debut(pc) for _, p in seq[j + 1:]):
                continue
            remplacements.append({"usage": usage, "entre": [dp["date_etablissement_dpe"][:10], dc["date_etablissement_dpe"][:10]],
                                  "avant": dp[champ], "apres": dc[champ]})
    return {
        "nb": len(dpe),
        "gen_ch": gen_ch, "gen_ecs": gen_ecs, "part_coll": part_coll,
        "energie": mode(d.get("type_energie_principale_chauffage") for d in recents),
        "ventilation": mode(d.get("type_ventilation") for d in recents),
        "id_rnb": mode(d.get("id_rnb") for d in dpe),
        "etiquette": mode(d.get("etiquette_dpe") for d in recents),
        "conso": statistics.median([d["conso_5_usages_par_m2_ep"] for d in recents if d.get("conso_5_usages_par_m2_ep") is not None] or [None]) if any(d.get("conso_5_usages_par_m2_ep") is not None for d in recents) else None,
        "repartition": {k: sum(1 for d in dpe if d.get("etiquette_dpe") == k) for k in "ABCDEFG"},
        "liste": [{"date": d["date_etablissement_dpe"][:10], "etiquette": d.get("etiquette_dpe"),
                   "generateur_chauffage": d.get("_gen_ch"),
                   "generateur_ecs": d.get("type_generateur_n1_ecs_n1")} for d in dpe][-30:],
        "remplacements": remplacements,
    }


def construire(dep, kit, bdnb, dpe_par_groupe, pm1, eau, georisques, anfr, locaux):
    ffo = kit.get("ffo") or {}
    b = bdnb or {}
    gid = kit["batiment_groupe_id"]
    src = defaultdict(list)

    def prendre(cle_api, cle_ffo, champ_sortie):
        if b.get(cle_api) is not None:
            src["BDNB"].append(champ_sortie)
            return b[cle_api]
        if cle_ffo and ffo.get(cle_ffo) is not None:
            src["BDNB (export du kit, fichiers fonciers)"].append(champ_sortie)
            return ffo[cle_ffo]
        return None

    position, emprise = geometrie(b.get("geom_groupe")) if b else (None, None)
    if position:
        src["BDNB"] += ["position", "emprise"]
    usage = prendre("usage_niveau_1_txt", "usage_niveau_1_txt", "usage")
    nb_log = prendre("nb_log", "nb_log", "nb_logements")
    individuel = (usage == "Résidentiel individuel") or (nb_log is not None and nb_log <= 1)
    adresse = prendre("libelle_adr_principale_ban", None, "adresse")
    commune = prendre("libelle_commune_insee", None, "commune")
    code_commune = prendre("code_commune_insee", None, "code_commune")
    code_iris = prendre("code_iris", None, "code_iris")
    annee = prendre("annee_construction", "annee_construction", "annee_construction")
    niveaux = prendre("nb_niveau", "nb_niveau", "nb_niveaux")
    hauteur = prendre("hauteur_mean", None, "hauteur_m")
    mur = prendre("mat_mur_txt", "mat_mur_txt", "mur")
    etiquette = prendre("classe_bilan_dpe", None, "etiquette_dpe")
    conso = prendre("conso_5_usages_ep_m2", None, "conso_kwhep_m2_an")

    r = resume_dpe(dpe_par_groupe) if dpe_par_groupe else None
    if r and etiquette is None and r["etiquette"]:
        etiquette = r["etiquette"]
        src["DPE ADEME"].append("etiquette_dpe")
    if r and conso is None and r["conso"] is not None:
        conso = r["conso"]
        src["DPE ADEME"].append("conso_kwhep_m2_an")

    # Chauffage et eau chaude : générateur et période des DPE (plus précis), sinon BDNB.
    install_bdnb = b.get("type_installation_chauffage")
    if r and r["part_coll"] is not None:
        collectif = r["part_coll"] >= 0.5
        src["DPE ADEME"].append("chauffage.collectif")
    elif install_bdnb:
        collectif = install_bdnb.lower().startswith("collectif")
        src["BDNB"].append("chauffage.collectif")
    else:
        collectif = None
    energie = b.get("type_energie_chauffage")
    if energie:
        src["BDNB"].append("chauffage.energie")
    elif r and r["energie"]:
        energie = r["energie"]
        src["DPE ADEME"].append("chauffage.energie")
    if r and r["gen_ch"] and not individuel:
        gen_ch, per_ch = r["gen_ch"], periode(r["gen_ch"])
        src["DPE ADEME"] += ["chauffage.generateur", "chauffage.periode_generateur"]
    else:
        gen_ch, per_ch = b.get("type_generateur_chauffage"), None
        if gen_ch:
            src["BDNB"].append("chauffage.generateur")
    if r and r["gen_ecs"] and not individuel:
        gen_ecs, per_ecs = r["gen_ecs"], periode(r["gen_ecs"])
        src["DPE ADEME"] += ["eau_chaude.generateur", "eau_chaude.periode_generateur"]
    else:
        gen_ecs, per_ecs = b.get("type_generateur_ecs"), None
        if gen_ecs:
            src["BDNB"].append("eau_chaude.generateur")
    chauffage = {"collectif": collectif,
                 "part_dpe_collectif": None if not r or r["part_coll"] is None else round(r["part_coll"], 2),
                 "energie": energie, "generateur": gen_ch, "periode_generateur": per_ch,
                 "anciennete_bdnb": b.get("type_generateur_chauffage_anciennete")}
    eau_chaude = {"generateur": gen_ecs, "periode_generateur": per_ecs,
                  "anciennete_bdnb": b.get("type_generateur_ecs_anciennete")}
    if r and r["ventilation"] and not individuel:
        ventilation = r["ventilation"]
        src["DPE ADEME"].append("ventilation")
    else:
        ventilation = b.get("type_ventilation")
        if ventilation:
            src["BDNB"].append("ventilation")

    repartition = None
    if b and any(b.get("nb_classe_bilan_dpe_" + k) is not None for k in "abcdefg"):
        src["BDNB"].append("repartition_dpe_bdnb")
    if r and r["nb"]:
        repartition = r["repartition"]
        src["DPE ADEME"] += ["nb_dpe", "repartition_dpe"]
    elif b and any(b.get("nb_classe_bilan_dpe_" + k) for k in "abcdefg"):
        repartition = {k.upper(): int(b.get("nb_classe_bilan_dpe_" + k) or 0) for k in "abcdefg"}
        src["BDNB"].append("repartition_dpe")
    id_rnb = r["id_rnb"] if r else None
    if id_rnb:
        src["DPE ADEME"].append("id_rnb")
    if r and not individuel:
        src["DPE ADEME"] += ["dpe", "remplacements"]

    argile = b.get("alea_argile")
    if argile:
        src["BDNB"].append("risques.argile")
    inondation = None
    if georisques is not None or pm1 is not None:
        inondation = {"arretes": None, "dernier": None, "ppr": None}
        if georisques is not None:
            inond = [a for a in georisques if "inondation" in (a.get("libelle") or "").lower()
                     and (a.get("debut") or "0000") >= "1982"]
            inondation["arretes"] = len(inond)
            dates = sorted((a.get("arrete") or a.get("debut") or "")[:10] for a in inond)
            inondation["dernier"] = dates[-1] if dates else None
            src["Géorisques (GASPAR)"] += ["risques.inondation.arretes", "risques.inondation.dernier"]
        if pm1 is not None:
            # PM1 = plans de prévention des risques. On écarte la sécheresse (argile) et les feux de forêt
            # (PPRIF) ; « PPRI », « inondation », « crue » ou « submersion » marquent un plan inondation ;
            # un PPRN générique (multirisque) laisse la réponse inconnue (null) avec son nom.
            noms, flood, generique = [], False, False
            for s in pm1:
                texte = " ".join(str(s.get(k) or "") for k in ("nomsuplitt", "nomass", "idgen")).lower()
                if "secheresse" in texte or "sécheresse" in texte or re.search(r"pprif|incendie|feux? de for", texte):
                    continue
                noms.append(s.get("nomsuplitt") or s.get("nomass"))
                if re.search(r"inond|ppri(?!f)|crue|submersion|lez_mosson|mosson|coulazou|bassin de risque", texte):
                    flood = True
                else:
                    generique = True
            inondation["ppr"] = True if flood else (None if generique else False)
            inondation["ppr_noms"] = sorted({n for n in noms if n})[:5]
            src["Géoportail de l'urbanisme (servitudes PM1)"] += ["risques.inondation.ppr", "risques.ppr_secheresse"]

    antenne = None
    if anfr is not None and position:
        p = plus_proche(position, anfr)
        if p:
            antenne = {"distance_m": int(round(p[0], -1)), "operateur": p[1],
                       "extinction_prevue": CALENDRIER_2G["derniere_extinction_par_departement"].get(dep)}
            src["ANFR"].append("antenne_2g.distance_m")
            src["Calendrier 2G (ARCEP, Orange)"].append("antenne_2g.extinction_prevue")
    durete, date_eau = eau if eau else (None, None)
    if durete is not None:
        src["Hub'Eau (qualité de l'eau potable)"].append("durete_eau_f")
    parcelles = b.get("l_parcelle_id") or []
    locaux_inli = sum(locaux.get(p, 0) for p in parcelles) if parcelles else None
    if parcelles:
        src["DGFiP (locaux des personnes morales)"].append("locaux_inli")
    qpv = b.get("quartier_prioritaire")
    if qpv is not None:
        src["BDNB"].append("qpv")

    noms_dates = {"BDNB": DATE_LECTURE, "BDNB (export du kit, fichiers fonciers)": None}
    return {
        "id_bdnb": gid, "id_rnb": id_rnb, "adresse": adresse, "commune": commune,
        "code_commune": code_commune, "departement": dep, "code_iris": code_iris,
        "position": position, "emprise": emprise,
        "usage": usage, "individuel": individuel,
        "annee_construction": annee, "nb_logements": nb_log, "nb_niveaux": niveaux,
        "hauteur_m": r1(hauteur), "mur": mur,
        "etiquette_dpe": etiquette, "conso_kwhep_m2_an": r1(conso),
        "chauffage": chauffage, "eau_chaude": eau_chaude, "ventilation": ventilation,
        "dpe": (r["liste"] if r and not individuel else None),
        "nb_dpe": r["nb"] if r else (0 if dpe_par_groupe is not None else None),
        "remplacements": (r["remplacements"][-10:] if r and not individuel else None),
        "repartition_dpe": repartition,
        "repartition_dpe_bdnb": ({k.upper(): int(b.get("nb_classe_bilan_dpe_" + k) or 0) for k in "abcdefg"}
                                 if b and any(b.get("nb_classe_bilan_dpe_" + k) is not None for k in "abcdefg") else None),
        "risques": {"argile": argile, "inondation": inondation,
                    "ppr_secheresse": (None if pm1 is None else any(
                        "secheresse" in " ".join(str(s.get(k) or "") for k in ("nomsuplitt", "nomass")).lower()
                        for s in pm1))},
        "antenne_2g": antenne,
        "durete_eau_f": durete, "durete_eau_date": date_eau,
        "locaux_inli": locaux_inli, "parcelles": parcelles or None, "qpv": qpv,
        "sources": [{"nom": nom, "date_lecture": noms_dates.get(nom, DATE_LECTURE),
                     "champs": sorted(set(champs))} for nom, champs in src.items()],
    }


# ---------------------------------------------------------------- programme
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--departements", default="31,33,34,40,64")
    ap.add_argument("--sans-gpu", action="store_true", help="ne pas interroger le Géoportail de l'urbanisme")
    args = ap.parse_args()
    deps = [d.strip() for d in args.departements.split(",") if d.strip()]
    _tests_periode()
    debut = time.time()
    os.makedirs(CACHE, exist_ok=True)

    kits = {d: lire_kit(d) for d in deps}
    print("Groupes du kit :", {d: len(k) for d, k in kits.items()}, flush=True)

    # 1. BDNB
    bdnb = {}
    for d in deps:
        ids = [k["batiment_groupe_id"] for k in kits[d]]
        paquets = [ids[i:i + 10] for i in range(0, len(ids), 10)]
        with ThreadPoolExecutor(2) as ex:
            for rep in ex.map(bdnb_paquet, paquets):
                for ligne in rep or []:
                    bdnb[ligne["batiment_groupe_id"]] = ligne
        print("BDNB %s : %d/%d groupes lus (%.0f s)" % (d, sum(1 for i in ids if i in bdnb), len(ids), time.time() - debut), flush=True)

    # 2. DGFiP
    locaux = {d: locaux_dgfip(d) for d in deps}
    print("DGFiP :", {d: sum(v.values()) for d, v in locaux.items()}, flush=True)

    # 3. DPE, servitudes PM1, Hub'Eau, Géorisques (en parallèle, chaque service à son débit)
    tous = [(d, k["batiment_groupe_id"]) for d in deps for k in kits[d]]
    communes = sorted({bdnb[g]["code_commune_insee"] for _, g in tous if g in bdnb and bdnb[g].get("code_commune_insee")})
    test = obtenir(URL_GEORISQUES + "?code_insee=31555&page_size=1", LIM_GEORISQUES, delai=8, essais=1)
    GEORISQUES_OK[0] = test is not None
    print("Géorisques joignable :", GEORISQUES_OK[0], flush=True)

    def tache_dpe(g):
        b = bdnb.get(g)
        cles = (b or {}).get("l_cle_interop_adr") or ([b["cle_interop_adr_principale_ban"]] if b and b.get("cle_interop_adr_principale_ban") else [])
        return g, dpe_groupe(g, cles)

    def tache_gpu(g):
        b = bdnb.get(g)
        pos = geometrie(b.get("geom_groupe"))[0] if b else None
        return g, gpu_pm1(g, pos)

    dpe, pm1, eau, geo = {}, {}, {}, {}
    # un groupe de fils par service : les quatre services avancent en même temps
    with ThreadPoolExecutor(4) as ex, ThreadPoolExecutor(3) as ex_gpu, ThreadPoolExecutor(2) as ex_eau, \
            ThreadPoolExecutor(2) as ex_geo:
        f_dpe = [ex.submit(tache_dpe, g) for _, g in tous]
        f_gpu = [] if args.sans_gpu else [ex_gpu.submit(tache_gpu, g) for _, g in tous]
        f_eau = {c: ex_eau.submit(durete_commune, c) for c in communes}
        f_geo = {c: ex_geo.submit(georisques_commune, c) for c in communes} if GEORISQUES_OK[0] else {}
        for n, f in enumerate(f_dpe, 1):
            g, v = f.result()
            dpe[g] = v
            if n % 100 == 0:
                print("  DPE %d/%d (%.0f s)" % (n, len(f_dpe), time.time() - debut), flush=True)
        for f in f_gpu:
            g, v = f.result()
            pm1[g] = v
        for c, f in f_eau.items():
            eau[c] = f.result()
        for c, f in f_geo.items():
            geo[c] = f.result()
    print("DPE, PM1, eau : %.0f s" % (time.time() - debut), flush=True)

    anfr = stations_2g()
    stations = anfr["stations"] if anfr else None

    # 4. Assemblage
    immeubles, departements = [], {}
    for d in deps:
        parcelles_bdnb = set()
        for k in kits[d]:
            g = k["batiment_groupe_id"]
            b = bdnb.get(g)
            c = (b or {}).get("code_commune_insee")
            dpe_g = dpe.get(g)
            if dpe_g:
                vus, uniques = set(), []
                for x in dpe_g:
                    cle = x.get("empreinte") or json.dumps(x, sort_keys=True)
                    if cle not in vus:
                        vus.add(cle)
                        uniques.append(x)
                dpe_g = uniques
            imm = construire(d, k, b, dpe_g, pm1.get(g), eau.get(c), geo.get(c), stations, locaux[d])
            immeubles.append(imm)
            parcelles_bdnb.update((b or {}).get("l_parcelle_id") or [])
        imm_d = [i for i in immeubles if i["departement"] == d]
        coll10 = [i for i in imm_d if not i["individuel"] and (i["nb_logements"] or 0) >= 10]
        departements[d] = {
            "nom": NOMS_DEP.get(d), "groupes": len(imm_d),
            "groupes_lus_api_bdnb": sum(1 for k in kits[d] if k["batiment_groupe_id"] in bdnb),
            "logements_bdnb": sum(i["nb_logements"] or 0 for i in imm_d),
            "collectifs_10_et_plus": len(coll10),
            "logements_collectifs_10_et_plus": sum(i["nb_logements"] or 0 for i in coll10),
            "locaux_dgfip": sum(locaux[d].values()), "parcelles_dgfip": len(locaux[d]),
            "parcelles_sans_groupe_bdnb": sum(1 for p in locaux[d] if p not in parcelles_bdnb),
            "extinction_2g_prevue": CALENDRIER_2G["derniere_extinction_par_departement"].get(d),
        }

    # Fusion avec un fichier existant (relance sur une partie des départements)
    # (seulement si le fichier existant a bien été écrit par ce script : clé "genere_le")
    if os.path.exists(SORTIE):
        try:
            with open(SORTIE, encoding="utf-8") as f:
                ancien = json.load(f)
            if ancien.get("genere_le") and ancien.get("sources", {}).get("calendrier_2g"):
                garder = {d for d in NOMS_DEP if d not in deps}
                immeubles = [i for i in ancien.get("immeubles", []) if i.get("departement") in garder] + immeubles
                for d, v in ancien.get("departements", {}).items():
                    if d in garder:
                        departements.setdefault(d, v)
        except Exception:
            pass
    immeubles.sort(key=lambda i: (i["departement"], i["code_commune"] or "", i["adresse"] or "", i["id_bdnb"]))

    ademe_meta = en_cache("dpe/_meta.json", lambda: obtenir(
        "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant", LIM_DPE)) or {}
    sortie = {
        "genere_le": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "avertissement": "Prototype non officiel. Données publiques à l'échelle de l'immeuble ; aucune donnée de logement.",
        "sources": {
            "bdnb": {"nom": "Base de données nationale des bâtiments (CSTB), API ouverte", "millesime": "2026-02",
                     "date_lecture": DATE_LECTURE, "licence": "Licence Ouverte 2.0", "url": URL_BDNB},
            "dpe": {"nom": "DPE des logements existants depuis juillet 2021 (ADEME, jeu dpe03existant)",
                    "millesime": (ademe_meta.get("dataUpdatedAt") or "")[:10] or None,
                    "date_lecture": DATE_LECTURE, "licence": "Licence Ouverte 2.0", "url": URL_DPE,
                    "note": "Recherche par clés d'adresse BAN du groupe (identifiant_ban). Aucun champ désignant un logement n'est lu ni gardé."},
            "dgfip": {"nom": "Fichier des locaux des personnes morales (DGFiP), situation 2025", "millesime": "2025",
                      "date_lecture": DATE_LECTURE, "licence": "Licence Ouverte 2.0",
                      "note": "SIREN 304234636, code droit P ; seul le nombre de locaux par parcelle est gardé."},
            "georisques": {"nom": "Géorisques, arrêtés de catastrophe naturelle (GASPAR)",
                           "date_lecture": DATE_LECTURE, "licence": "Licence Ouverte 2.0",
                           "statut": "lu" if GEORISQUES_OK[0] else "injoignable depuis cette machine le %s : arretes et dernier valent null" % DATE_LECTURE,
                           "remplacement": None if args.sans_gpu else {
                               "nom": "Géoportail de l'urbanisme, servitudes PM1 (plans de prévention des risques) au point du bâtiment, via API Carto (IGN)",
                               "url": URL_GPU, "date_lecture": DATE_LECTURE, "licence": "Licence Ouverte 2.0"}},
            "hubeau": {"nom": "Hub'Eau, qualité de l'eau potable (titre hydrotimétrique, codes 7972 et 1345)",
                       "date_lecture": DATE_LECTURE, "licence": "Licence Ouverte 2.0", "url": URL_HUBEAU,
                       "note": "Médiane des 10 derniers résultats de la commune, en °f ; date du plus récent dans durete_eau_date."},
            "anfr": ({"nom": anfr.get("source"), "url": anfr.get("url"), "millesime": anfr.get("date_export"),
                      "date_lecture": anfr.get("date_lecture"), "licence": anfr.get("licence"),
                      "note": "Stations avec au moins un émetteur GSM 900 ou GSM 1800 daté (hors GSM-R), tous opérateurs."}
                     if anfr else None),
            "calendrier_2g": CALENDRIER_2G,
        },
        "departements": dict(sorted(departements.items())),
        "immeubles": immeubles,
    }
    os.makedirs(os.path.dirname(SORTIE), exist_ok=True)
    tmp = SORTIE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, SORTIE)
    print("Écrit %s : %d immeubles, %.2f Mo, %.1f Mo téléchargés, %.0f s" % (
        SORTIE, len(immeubles), os.path.getsize(SORTIE) / 1e6, OCTETS[0] / 1e6, time.time() - debut), flush=True)


if __name__ == "__main__":
    main()
