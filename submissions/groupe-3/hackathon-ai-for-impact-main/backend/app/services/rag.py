"""RAG hors ligne : recherche de lieux pour une sortie scolaire (BM25 maison, filtres durs).

Corpus (chargé une fois) : top 58 des sites 2021 (mots-clés enrichis), POI Datatourisme visitables
d'Occitanie, catalogue fait main (prioritaire à pertinence égale). Fichier absent -> corpus vide.
`reformuler_requete` transforme la demande en requête (1 appel LLM au plus, repli par thésaurus local).
Rien n'est inventé : chaque Document vient du corpus et cite un passage.
"""
from __future__ import annotations

import csv
import json
import logging
import math
import re
from collections import Counter, defaultdict
from functools import lru_cache
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .. import config, llm, prompts_rag
from .texte import normaliser

log = logging.getLogger("lio.rag")

csv.field_size_limit(10_000_000)

# --- Schémas --------------------------------------------------------------------------------------


class CentreGeo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: Optional[float] = None
    lon: Optional[float] = None
    rayon_km: Optional[float] = None


class FiltresRAG(BaseModel):
    model_config = ConfigDict(extra="forbid")
    communes: list[str] = Field(default_factory=list)
    centre_geo: CentreGeo = Field(default_factory=CentreGeo)
    interieur_uniquement: Optional[bool] = None
    frequentation_min: Optional[int] = None


class SortieReformulation(BaseModel):
    """Schéma strict attendu du LLM."""
    model_config = ConfigDict(extra="forbid")
    intention: str = ""
    requete_semantique: str = ""
    mots_cles_cibles: list[str] = Field(default_factory=list)
    termes_expansion: list[str] = Field(default_factory=list)
    mots_cles_exclus: list[str] = Field(default_factory=list)
    filtres: FiltresRAG = Field(default_factory=FiltresRAG)
    question_clarification: Optional[str] = None


class RequeteRAG(SortieReformulation):
    origine: Literal["llm", "regles"] = "regles"


class Document(BaseModel):
    id: str
    nom: str
    commune: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    source: Literal["top58", "datatourisme", "catalogue"]
    score: float = 0.0
    mots_cles: list[str] = Field(default_factory=list)
    passage: str = ""
    total_visites: Optional[int] = None
    gare_proche: Optional[str] = None
    distance_gare_km: Optional[float] = None
    marche_min: Optional[int] = None


# --- Texte ----------------------------------------------------------------------------------------

STOP = set("""le la les l un une des du de d et ou a au aux en dans pour par sur avec sans que qui quoi
ce cet cette ces se sa son ses leur leurs nous vous je tu il elle on ils elles mon ma mes notre votre
est sont etre avoir ai as avons avez ont y ne pas plus moins tres trop aussi mais donc car si
classe classes eleves eleve prof professeur professeurs ecole college lycee sortie sortie visite visiter
voir veux voudrais souhaite cherche chercher trouver idee idees lieu lieux site sites depart partir
autour pres proche environ km de la ce programme theme niveau cm1 cm2 ce1 ce2 cp 6e 5e 4e 3e 2de 1re tle
6eme 5eme 4eme 3eme sixieme cinquieme quatrieme troisieme seconde premiere terminale
tes ton ta mes tout toute tous""".split())
# Mots d'une tentative d'injection ou d'une demande de réservation : écartés de la requête libre seulement.
INJECTION = {"ignore", "ignorer", "ignores", "instruction", "reserve", "reserver", "reservez", "place", "oublie",
             "oublier", "systeme", "prompt", "regle", "obeis", "desormais"}
GENERIQUES = {"famille", "patrimonial", "culturel", "plein", "air", "decouverte", "monument",
              "historique", "touristique", "loisir", "attraction"}
PRIX_GENERIQUE = 0.2

_RE_MAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_RE_TEL = re.compile(r"(?:\+?\d[\d .\-]{7,}\d)")
_RE_NOM = re.compile(r"\b(?:M\.|Mme|Mlle|Mr|Monsieur|Madame|Mademoiselle|Prof(?:esseur)?\.?)\s+"
                     r"[A-ZÉÈÀ][\w'’-]+(?:\s+[A-ZÉÈÀ][\w'’-]+)?")
_RE_SE_PRESENTE = re.compile(r"(?i)\b(je m['’]appelle|je suis|moi c['’]est|mon nom est)\s+"
                             r"[A-ZÉÈÀ][\w'’-]+(?:\s+[A-ZÉÈÀ][\w'’-]+)?")


def anonymiser(texte: str) -> str:
    """Retire e-mails, téléphones et noms de personnes avant tout envoi à un LLM."""
    t = _RE_MAIL.sub(" ", texte or "")
    t = _RE_TEL.sub(" ", t)
    t = _RE_NOM.sub(" ", t)
    t = _RE_SE_PRESENTE.sub(" ", t)
    t = t.replace("<", " ").replace(">", " ")
    return " ".join(t.split())[:500]


def _racine(m: str) -> str:
    if len(m) > 4 and m.endswith("e"):
        m = m[:-1]
    if len(m) > 3 and m[-1] in "sx":
        m = m[:-1]
    return m


def jetons(texte: str) -> list[str]:
    return [_racine(m) for m in normaliser(texte).split() if m not in STOP and len(m) > 1 and not m.isdigit()]


_INJECTION_R = {_racine(m) for m in INJECTION} | INJECTION


def jetons_libres(texte: str) -> list[str]:
    """Jetons d'un texte saisi par l'utilisateur : sans mots d'injection ni de réservation."""
    return [t for t in jetons(texte) if t not in _INJECTION_R]


# --- Corpus ---------------------------------------------------------------------------------------

POIDS_CHAMP = {"mots_cles": 3.0, "nom": 2.5, "categories": 1.5, "description": 1.0}
PRIOR = {"catalogue": 1.15, "top58": 1.1, "datatourisme": 1.0}

_CAT_EXCLUES = ("hebergement", "restauration", "restaurant", "commerce", "fete et manifestation",
                "evenement", "hotel", "camping", "location", "vente", "services pratiques",
                "service pratique", "gite", "chambre d hotes", "degustation", "office de tourisme",
                "point d information", "marche", "artisan", "prestataire")
_CAT_RETENUES = ("site culturel", "patrimoine", "musee", "chateau", "edifice religieux", "biodiversite",
                 "geologie", "botanique", "jardin", "architecture", "visite guidee", "atelier pedagogique",
                 "archeolog", "grotte", "abbaye", "eglise", "cathedrale", "parc", "reserve", "histoire",
                 "science", "centre d interpretation", "exposition")
_PLEIN_AIR = {"plein air", "randonnée", "sentier", "balade", "plage", "lac", "extérieur", "jardin",
              "jardins", "promenade", "vélo", "pêche", "pique-nique"}


class _Entree(BaseModel):
    doc: Document
    tf: dict[str, float]
    longueur: float
    categories: str = ""
    exterieur: bool = False


class Corpus:
    def __init__(self, entrees: list[_Entree]):
        self.entrees = entrees
        self.postings: dict[str, list[tuple[int, float]]] = defaultdict(list)
        for i, e in enumerate(entrees):
            for t, w in e.tf.items():
                self.postings[t].append((i, w))
        n = max(len(entrees), 1)
        self.longueur_moy = sum(e.longueur for e in entrees) / n
        self.idf = {t: math.log(1 + (n - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self.postings.items()}
        # commune normalisée -> centroïde, pour la géolocalisation d'une demande
        somme: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
        noms: dict[str, str] = {}
        for e in entrees:
            d = e.doc
            if d.lat is None or d.lon is None or not d.commune:
                continue
            k = normaliser(d.commune)
            s = somme[k]
            s[0] += d.lat; s[1] += d.lon; s[2] += 1
            noms.setdefault(k, d.commune)
        self.communes: dict[str, tuple[float, float, int]] = {
            k: (s[0] / s[2], s[1] / s[2], int(s[2])) for k, s in somme.items()}
        self.noms_communes = noms


def _tf(champs: dict[str, str], generiques_bas: bool = True) -> tuple[dict[str, float], float]:
    tf: dict[str, float] = defaultdict(float)
    for champ, texte in champs.items():
        poids = POIDS_CHAMP[champ]
        for t in jetons(texte):
            w = poids * (0.3 if (champ == "mots_cles" and t in GENERIQUES) else 1.0)
            tf[t] += w
    return dict(tf), sum(tf.values())


def _tronquer(texte: str, n: int = 300) -> str:
    texte = " ".join((texte or "").split())
    if len(texte) <= n:
        return texte
    coupe = texte[:n - 1]
    fin = max(coupe.rfind(". "), coupe.rfind("; "))
    return (coupe[:fin + 1] if fin > n // 2 else coupe.rsplit(" ", 1)[0]) + ("" if fin > n // 2 else "…")


def _slug(s: str) -> str:
    return normaliser(s).replace(" ", "-")[:60]


def _metriques() -> dict[str, dict]:
    try:
        d = json.loads(config.RAG_TOP58_METRIQUES.read_text(encoding="utf-8"))
        return {m["site"]: m for m in d.get("sites", [])}
    except (OSError, ValueError, KeyError):
        return {}


def _charger_top58() -> list[_Entree]:
    try:
        sites = json.loads(config.RAG_TOP58_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    metr = _metriques()
    out = []
    for s in sites:
        mc = [m for m in s.get("mots_cles", []) if m]
        m = metr.get(s["site"], {})
        passage = _tronquer(f"{s['site']} ({str(s.get('commune', '')).title()}) : " + ", ".join(mc)
                            + (f". {s['adresse']}" if s.get("adresse") else ""))
        doc = Document(id=f"top58:{_slug(s['site'])}", nom=s["site"], commune=str(s.get("commune", "")).title(),
                       lat=s.get("latitude"), lon=s.get("longitude"), source="top58", mots_cles=mc,
                       passage=passage, total_visites=s.get("total_visites"),
                       gare_proche=m.get("gare_proche"), distance_gare_km=m.get("distance_gare_km"),
                       marche_min=m.get("marche_min"))
        tf, ln = _tf({"mots_cles": " ".join(mc), "nom": s["site"]})
        out.append(_Entree(doc=doc, tf=tf, longueur=ln, exterieur=_exterieur(mc)))
    return out


def _exterieur(mots: list[str]) -> bool:
    bas = {m.lower() for m in mots}
    return bool(bas & _PLEIN_AIR) and "intérieur" not in bas


def _charger_catalogue() -> list[_Entree]:
    try:
        from etl import catalogue
    except Exception:  # pragma: no cover - dossier etl absent du PYTHONPATH
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("catalogue", config.BACKEND_DIR / "etl" / "catalogue.py")
            catalogue = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(catalogue)
        except Exception:
            return []
    out = []
    for s in catalogue.SITES:
        mc = list(s.get("themes", [])) + list(s.get("activites", []))[:0]
        passage = _tronquer(s.get("interet_pedagogique", ""))
        doc = Document(id=f"catalogue:{s['id']}", nom=s["nom"], commune=s.get("commune", ""),
                       lat=s.get("lat"), lon=s.get("lon"), source="catalogue", mots_cles=list(s.get("themes", [])),
                       passage=passage, marche_min=s.get("minutes_pied"),
                       gare_proche=(s.get("gares") or [None])[0])
        tf, ln = _tf({"mots_cles": " ".join(s.get("themes", [])), "nom": s["nom"],
                      "description": s.get("interet_pedagogique", "") + " " + " ".join(s.get("activites", []))})
        out.append(_Entree(doc=doc, tf=tf, longueur=ln, exterieur=_exterieur(mc)))
    return out


def _charger_datatourisme() -> list[_Entree]:
    out = []
    try:
        with open(config.RAG_DATATOURISME_CSV, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                cats = r.get("Categories_de_POI", "")
                ncat = normaliser(cats)
                if any(x in ncat for x in _CAT_EXCLUES) or not any(x in ncat for x in _CAT_RETENUES):
                    continue
                try:
                    lat, lon = float(r["Latitude"]), float(r["Longitude"])
                except (ValueError, KeyError):
                    continue
                nom = (r.get("Nom_du_POI") or "").strip()
                if not nom:
                    continue
                commune = (r.get("Code_postal_et_commune") or "").split("#")[-1].strip()
                mc = [m.strip() for m in (r.get("Mots_cles") or "").split(";") if m.strip()]
                cat_liste = [c.strip() for c in cats.split(";") if c.strip()]
                desc = r.get("Description") or ""
                doc = Document(id="datatourisme:" + (r.get("URI_ID_du_POI") or nom).rsplit("/", 1)[-1],
                               nom=nom, commune=commune, lat=lat, lon=lon, source="datatourisme",
                               mots_cles=mc or cat_liste, passage=_tronquer(desc or ", ".join(cat_liste)))
                tf, ln = _tf({"mots_cles": " ".join(mc), "nom": nom,
                              "categories": " ".join(cat_liste), "description": desc})
                out.append(_Entree(doc=doc, tf=tf, longueur=ln, categories=ncat,
                                   exterieur="plein air" in ncat or "randonnee" in ncat))
    except OSError:
        return []
    return out


@lru_cache(maxsize=1)
def corpus() -> Corpus:
    entrees = _charger_catalogue() + _charger_top58() + _charger_datatourisme()
    log.info("Corpus RAG : %d documents", len(entrees))
    return Corpus(entrees)


def vider_cache() -> None:
    corpus.cache_clear()
    vocabulaire.cache_clear()


@lru_cache(maxsize=1)
def vocabulaire() -> dict[str, int]:
    """Mots-clés du top 58, dédoublonnés (forme normalisée) et comptés ; forme affichée = la plus fréquente."""
    comptes: Counter = Counter()
    formes: dict[str, Counter] = defaultdict(Counter)
    for e in corpus().entrees:
        if e.doc.source != "top58":
            continue
        for m in e.doc.mots_cles:
            k = normaliser(m)
            comptes[k] += 1
            formes[k][m.lower()] += 1
    return {formes[k].most_common(1)[0][0]: n for k, n in comptes.most_common()}


@lru_cache(maxsize=1)
def _vocabulaire_normalise() -> frozenset[str]:
    """Tous les mots-clés réels du corpus (top 58, catalogue, Datatourisme), sous forme normalisée."""
    v = {normaliser(m) for e in corpus().entrees for m in e.doc.mots_cles}
    v |= {normaliser(m) for m in vocabulaire()}
    return frozenset(v)


# --- Géographie -----------------------------------------------------------------------------------

_NON_COMMUNES = {"mars", "avril", "juin", "mai", "foire", "pierre", "rouge", "bas", "haut", "vieux", "grand",
                 "petit", "eglise", "ville", "parc", "lac", "mer", "saint", "sainte"}


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def commune_dans(texte: str) -> tuple[str, float, float] | None:
    """Première commune connue du corpus citée dans le texte (mot entier) : (nom, lat, lon)."""
    c = corpus()
    t = " " + normaliser(texte) + " "
    meilleur = None
    for k, (lat, lon, n) in c.communes.items():
        if len(k) < 4 or k in _NON_COMMUNES or (n < 8 and k not in {normaliser(e.doc.commune) for e in c.entrees
                                                                       if e.doc.source != "datatourisme"}):
            continue
        i = t.find(f" {k} ")
        if i >= 0 and (meilleur is None or i < meilleur[0]):
            meilleur = (i, c.noms_communes[k], lat, lon)
    return meilleur[1:] if meilleur else None


# --- Thésaurus pédagogique (repli déterministe) --------------------------------------------------

THESAURUS: list[tuple[str, list[str]]] = [
    (r"moyen age|medieva|chevali|feodal|croisade|cathare|catharisme",
     ["moyen âge", "château", "cathédrale", "basilique", "cité médiévale", "remparts", "fortifications",
      "abbaye", "catharisme", "chevaliers", "roman", "gothique", "cloître", "couvent"]),
    (r"\brome\b|romain|antiqui|gaul|gallo|gladiat",
     ["romain", "antiquité", "civilisation romaine", "archéologie", "amphithéâtre", "aqueduc", "temple",
      "via domitia", "mosaïques", "gladiateurs"]),
    (r"prehistoire|paleolith|neolith|homme de cro|prehistori",
     ["préhistoire", "grotte", "archéologie", "paléontologie", "dinosaures", "souterrain"]),
    (r"\bsvt\b|sciences de la vie|vie et de la terre|ecolog|ecosyst|biodivers|environnement|vivant|faune|flore|zone humide",
     ["biodiversité", "écologie", "environnement", "zones humides", "sciences de la vie", "faune sauvage",
      "réserve naturelle", "espace naturel protégé", "nature", "éducation à l'environnement"]),
    (r"astronom|\bespace\b|spatial|fusee|planet|aeronaut|aviation|avion",
     ["espace", "astronomie", "conquête spatiale", "planétarium", "aéronautique", "aviation", "astronaute",
      "observatoire", "sciences"]),
    (r"sciences?\b|physique|chimie|technolog|innovation|ingenier",
     ["sciences", "technologie", "innovation", "ingénierie", "histoire des techniques"]),
    (r"geograph|montagne|pyrene|altitude|relief|paysage|massif",
     ["montagne", "pyrénées", "altitude", "panorama", "paysage", "géologie", "causses"]),
    (r"geolog|volcan|grotte|karst|speleo|roche|erosion",
     ["géologie", "grotte", "karst", "concrétions", "stalactites", "spéléologie", "sciences de la terre"]),
    (r"\bart\b|arts|peinture|musee|sculpt|plastique|picasso|lautrec|soulages",
     ["art", "musée", "peinture", "art moderne", "art contemporain", "beaux-arts", "sculpture", "arts plastiques"]),
    (r"industri|revolution industrielle|canal du midi|riquet|mine|minier|ferroviaire|locomotive|train",
     ["histoire industrielle", "patrimoine industriel", "patrimoine minier", "canal du midi", "patrimoine ferroviaire",
      "chemin de fer", "génie civil", "histoire des techniques"]),
    (r"religi|roman\b|art roman|pelerin|compostelle|cathedrale|abbaye",
     ["religieux", "pèlerinage", "chemins de compostelle", "roman", "cathédrale", "abbaye", "art sacré"]),
    (r"animaux|zoo|ferme|oiseau|marin|aquarium|ocean|mer\b",
     ["animaux", "zoo", "aquarium", "ferme pédagogique", "faune sauvage", "biodiversité marine", "ornithologie"]),
    (r"histoire|patrimoine",
     ["histoire", "historique", "monument historique", "patrimoine culturel"]),
]
_RE_INTERIEUR = re.compile(r"\b(pluie|intempérie|intemperie|à l'abri|a l'abri|en intérieur|interieur|intérieur)\b", re.I)


def _expansion_regles(demande: str) -> list[str]:
    t = normaliser(demande)
    out: list[str] = []
    svt = False
    for motif, mots in THESAURUS:
        if motif.startswith(r"sciences?") and svt:
            continue
        if re.search(motif, t):
            svt = svt or motif.startswith(r"\bsvt")
            out += mots
    return list(dict.fromkeys(out))


def _filtrer_vocab(mots: list[str]) -> list[str]:
    v = _vocabulaire_normalise()
    return list(dict.fromkeys(m.strip().lower() for m in mots if isinstance(m, str) and normaliser(m) in v))


def _geo_depuis_demande(demande: str, rayon_llm: float | None = None) -> tuple[list[str], CentreGeo]:
    c = commune_dans(demande)
    if not c:
        return [], CentreGeo()
    nom, lat, lon = c
    rayon = rayon_llm if rayon_llm and 5 <= rayon_llm <= 100 else 40.0
    return [nom], CentreGeo(lat=round(lat, 4), lon=round(lon, 4), rayon_km=rayon)


def _requete_regles(demande: str) -> RequeteRAG:
    exp = _expansion_regles(demande)
    cibles = _filtrer_vocab(exp)
    communes, geo = _geo_depuis_demande(demande)
    return RequeteRAG(
        intention=demande[:200], requete_semantique=demande, mots_cles_cibles=cibles,
        termes_expansion=[m for m in exp if m not in cibles],
        filtres=FiltresRAG(communes=[], centre_geo=geo,
                           interieur_uniquement=True if _RE_INTERIEUR.search(demande) else None),
        question_clarification=None if (cibles or len(jetons_libres(demande)) >= 2) else "Quel thème ou quelle matière souhaitez-vous aborder ?",
        origine="regles")


def _valider_llm(s: SortieReformulation, demande: str) -> RequeteRAG:
    """Garde-fous : mots-clés réels uniquement, géographie seulement via une commune connue de la demande."""
    cibles = _filtrer_vocab(s.mots_cles_cibles)
    expansion = list(dict.fromkeys(
        [m for m in s.termes_expansion if isinstance(m, str) and m.strip()][:15]
        + [m for m in s.mots_cles_cibles if m not in cibles]))
    exclus = _filtrer_vocab(s.mots_cles_exclus)
    rayon = s.filtres.centre_geo.rayon_km
    communes, geo = _geo_depuis_demande(demande, rayon)
    if not communes:  # la commune citée par le LLM compte seulement si le texte de la demande la contient
        communes, geo = [], CentreGeo()
    f = s.filtres
    freq = f.frequentation_min if isinstance(f.frequentation_min, int) and f.frequentation_min > 0 else None
    return RequeteRAG(intention=s.intention[:300], requete_semantique=s.requete_semantique[:400],
                      mots_cles_cibles=cibles, termes_expansion=expansion, mots_cles_exclus=exclus,
                      filtres=FiltresRAG(communes=communes, centre_geo=geo,
                                         interieur_uniquement=f.interieur_uniquement, frequentation_min=freq),
                      question_clarification=s.question_clarification, origine="llm")


def reformuler_requete(demande: str) -> RequeteRAG:
    """Demande du professeur -> requête structurée. 1 appel LLM au plus, repli déterministe sur tout échec."""
    demande = " ".join((demande or "").split())[:500]
    propre = anonymiser(demande)
    if llm.mode() == "llm" and propre:
        try:
            voc = ", ".join(f"{m} ({n})" for m, n in list(vocabulaire().items())[:260])
            sortie = llm.appel_json("rag", prompts_rag.systeme(voc), prompts_rag.utilisateur(propre),
                                    SortieReformulation, max_tokens=900)
            if sortie is not None:
                r = _valider_llm(sortie, demande)
                if r.mots_cles_cibles or r.termes_expansion or r.question_clarification:
                    return r
        except Exception as e:
            log.warning("Reformulation RAG : repli règles (%s)", type(e).__name__)
    return _requete_regles(demande)


# --- Recherche ------------------------------------------------------------------------------------

K1, B = 1.4, 0.6


def _poids_requete(req: RequeteRAG, demande: str) -> dict[str, float]:
    q: dict[str, float] = defaultdict(float)

    def ajouter(texte: str, poids: float, libre: bool = False) -> None:
        for t in set(jetons_libres(texte) if libre else jetons(texte)):
            q[t] += poids * (PRIX_GENERIQUE if t in GENERIQUES else 1.0)

    for m in req.mots_cles_cibles:
        ajouter(m, 1.0)
    for m in req.termes_expansion:
        ajouter(m, 0.4)
    ajouter(req.requete_semantique, 0.4, libre=True)
    ajouter(demande, 0.3, libre=True)
    return dict(q)


def _score(c: Corpus, q: dict[str, float], exclus: set[str]) -> dict[int, float]:
    scores: dict[int, float] = defaultdict(float)
    for t, wq in q.items():
        idf = c.idf.get(t)
        if idf is None:
            continue
        for i, w in c.postings[t]:
            ln = c.entrees[i].longueur
            scores[i] += wq * idf * w * (K1 + 1) / (w + K1 * (1 - B + B * ln / c.longueur_moy))
    for t in exclus:
        for i, _ in c.postings.get(t, []):
            if i in scores:
                scores[i] *= 0.3
    return scores


def _meme_lieu(a: Document, b: Document) -> bool:
    if None in (a.lat, a.lon, b.lat, b.lon) or haversine_km(a.lat, a.lon, b.lat, b.lon) > 0.3:
        return False
    return bool(set(jetons(a.nom)) & set(jetons(b.nom)))


def _chercher(req: RequeteRAG, demande: str, centre, rayon_km, k, communes, interieur, freq) -> list[Document]:
    c = corpus()
    if not c.entrees:
        return []
    q = _poids_requete(req, demande)
    if not q:
        return []
    scores = _score(c, q, {t for m in req.mots_cles_exclus for t in jetons(m)})
    communes_n = {normaliser(x) for x in (communes or [])}
    resultats: list[tuple[float, int]] = []
    for i, s in scores.items():
        e = c.entrees[i]
        d = e.doc
        if communes_n and normaliser(d.commune) not in communes_n:
            continue
        if centre and rayon_km:
            if d.lat is None or haversine_km(centre[0], centre[1], d.lat, d.lon) > rayon_km:
                continue
        if interieur and e.exterieur:
            continue
        if freq and (d.total_visites is None or d.total_visites < freq):
            continue
        prior = PRIOR[d.source]
        if d.source == "top58" and d.total_visites:
            prior *= 1 + 0.03 * math.log10(max(d.total_visites, 1))
        resultats.append((s * prior, i))
    resultats.sort(key=lambda x: (-x[0], c.entrees[x[1]].doc.id))
    sortie: list[Document] = []
    for s, i in resultats:
        d = c.entrees[i].doc.model_copy(update={"score": round(s, 3)})
        if any(_meme_lieu(d, x) for x in sortie):
            continue
        sortie.append(d)
        if len(sortie) >= k:
            break
    return sortie


def rechercher(demande: str, centre: tuple[float, float] | None = None, rayon_km: float | None = None,
               k: int = 8, *, communes: list[str] | None = None, interieur_uniquement: bool | None = None,
               frequentation_min: int | None = None) -> list[Document]:
    """Lieux les plus pertinents pour la demande (reformulée), triés par score décroissant.

    `centre`/`rayon_km` explicites l'emportent sur la géographie déduite de la demande ; si trop peu de
    résultats, le rayon est doublé une fois, puis levé. Hors ligne : la reformulation retombe sur les règles.
    """
    req = reformuler_requete(demande)
    f = req.filtres
    if centre is None and f.centre_geo.lat is not None and f.centre_geo.lon is not None:
        centre = (f.centre_geo.lat, f.centre_geo.lon)
        rayon_km = rayon_km or f.centre_geo.rayon_km
    if centre and not rayon_km:
        rayon_km = 40.0
    interieur = interieur_uniquement if interieur_uniquement is not None else f.interieur_uniquement
    freq = frequentation_min if frequentation_min is not None else f.frequentation_min
    docs: list[Document] = []
    for r in ([rayon_km, rayon_km * 2, None] if centre and rayon_km else [None]):
        docs = _chercher(req, demande, centre if r else None, r, k, communes, interieur, freq)
        if len(docs) >= min(k, 3):
            break
    return docs


def fiche(site_id: str, nom: str) -> Document | None:
    """Fiche du corpus qui décrit un site déjà évalué (sans appel LLM) : catalogue d'abord, puis même nom."""
    try:
        entrees = corpus().entrees
    except Exception:  # corpus absent ou illisible : pas de fiche, jamais d'erreur
        return None
    cible = f"catalogue:{site_id}"
    nom_n = normaliser(nom)
    par_nom = None
    for e in entrees:
        d = e.doc
        if d.id == cible and d.passage:
            return d
        if par_nom is None and d.passage and normaliser(d.nom) == nom_n:
            par_nom = d
    return par_nom
