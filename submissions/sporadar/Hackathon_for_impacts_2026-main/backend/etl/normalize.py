"""Normalisation des cultures, cibles, substances actives et produits soeurs.

Ce module NE SE CONNECTE PAS à la base : il lit seulement les CSV de mapping du
dossier data/ (eppo_crop_mapping.csv, eppo_pest_mapping.csv,
active_entity_mapping.csv, product_name_mapping.csv, ai_term_mapping.csv).

Règles du projet :
- Jamais d'invention : pas de correspondance (ou correspondance ambiguë) -> None.
- Cultures/cibles : mapping LPC d'abord, puis data/ai_term_mapping.csv (traductions suggérées par l'IA, à vérifier).
- On ne modifie jamais les valeurs *_original : on renvoie seulement une valeur
  normalisée que l'appelant range dans les colonnes *_normalized.
- Les produits soeurs sont des HYPOTHESES ("to_verify") sauf validation explicite.
"""
import csv
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

# Dossier data/ du dépôt (ce fichier est dans backend/etl/)
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


# ---------------------------------------------------------------------------
# Outils de base
# ---------------------------------------------------------------------------
def clean(text):
    """Met un texte sous forme comparable : minuscules, sans accents, espaces simplifiés.

    "  Pourriture  GRISE " -> "pourriture grise" ; "Süßkirsche" -> "sussk..." (idem des deux côtés).
    """
    if text is None:
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))  # retire les accents
    text = text.casefold()
    text = re.sub(r"[-_]", " ", text)  # tirets et underscores = espaces
    return re.sub(r"\s+", " ", text).strip()


def _read_csv(name):
    with open(DATA_DIR / name, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _contains_words(haystack, needle):
    """True si `needle` apparaît dans `haystack` comme suite de mots entiers."""
    return bool(needle) and f" {needle} " in f" {haystack} "


def _single_forms(key):
    """Le texte lui-même, puis des formes au singulier probables ("Tomaten" -> "tomate").

    On essaie d'abord le texte exact ; ces variantes ne servent qu'en second choix.
    """
    forms = [key]
    if key.endswith(("s", "x", "n")):
        forms.append(key[:-1])
    if key.endswith(("en", "es")):
        forms.append(key[:-2])
    return forms


# ---------------------------------------------------------------------------
# Cultures et cibles (EPPO)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=None)
def _load_eppo_index(filename):
    """Construit un index {texte nettoyé: ligne du mapping} pour un fichier EPPO.

    Un texte qui pointe vers deux concepts différents est AMBIGU : on le retire
    de l'index (mieux vaut ne rien répondre que se tromper).
    """
    candidates = {}  # texte nettoyé -> {concept_id: ligne}
    for row in _read_csv(filename):
        names = [row["name_original"], row["name_normalized"], row["concept_id"], row["scientific_name"]]
        for alias in (row.get("multilingual_aliases") or "").split("|"):
            alias = re.sub(r"^[a-z]{2}:", "", alias.strip())  # retire le préfixe "fr:"
            names.append(alias)
        for name in names:
            key = clean(name)
            if key:
                candidates.setdefault(key, {})[row["concept_id"]] = row
    return {k: next(iter(v.values())) for k, v in candidates.items() if len(v) == 1}


def _eppo_lookup(texte, filename):
    key = clean(texte)
    if not key:
        return None
    index = _load_eppo_index(filename)
    for form in _single_forms(key):
        row = index.get(form)
        if row:
            return {
                "normalized": row["name_normalized"] or None,
                "eppo_code": row["eppo_code"] or None,
                "mapping_status": row["mapping_status"],
                "method": "lpc_mapping",
                "group": None, "confidence": None, "model_name": None, "review_status": None,
            }
    return None


# ---------------------------------------------------------------------------
# Dictionnaire de traduction suggéré par l'IA (data/ai_term_mapping.csv)
# Second recours, utilisé SEULEMENT si le mapping LPC ne reconnaît pas la valeur.
# ---------------------------------------------------------------------------
@lru_cache(maxsize=None)
def _load_ai_index():
    """{(kind, texte nettoyé): ligne} ; kind = "crop" ou "target". Fichier absent -> index vide."""
    path = DATA_DIR / "ai_term_mapping.csv"
    if not path.exists():
        return {}
    index = {}
    for row in _read_csv("ai_term_mapping.csv"):
        key = clean(row["value_original"])
        if key and row["normalized_en"]:
            index[(row["kind"], key)] = row
    return index


def _ai_lookup(texte, kind):
    """Valeur exacte (casse/accents ignorés) trouvée dans le dictionnaire IA, sinon None.

    Le code EPPO n'est repris que si `eppo_code_candidate` est rempli (jamais deviné).
    Une ligne que l'expert a passée à review_status = "validated" devient mapping_status "validated".
    """
    row = _load_ai_index().get((kind, clean(texte)))
    if not row:
        return None
    return {
        "normalized": row["normalized_en"],
        "eppo_code": row["eppo_code_candidate"] or None,
        "mapping_status": "validated" if row["review_status"] == "validated" else "ai_suggested",
        "method": row["method"] or "ai_suggested",
        "group": row["group_en"] or None,
        "confidence": float(row["confidence"]) if row["confidence"] else None,
        "model_name": row["model_name"] or None,
        "review_status": row["review_status"],
    }


def normalize_crop(texte):
    """Culture -> {normalized, eppo_code, mapping_status, method, group, ...} ou None.

    Ordre : mapping LPC (toujours prioritaire), puis dictionnaire IA.
    """
    return _eppo_lookup(texte, "eppo_crop_mapping.csv") or _ai_lookup(texte, "crop")


def normalize_target(texte):
    """Cible (ravageur / maladie / adventice) -> même forme que normalize_crop, ou None."""
    return _eppo_lookup(texte, "eppo_pest_mapping.csv") or _ai_lookup(texte, "target")


# ---------------------------------------------------------------------------
# Substances actives (espèce + souche)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=None)
def _entity_rows():
    rows = _read_csv("active_entity_mapping.csv")
    for r in rows:
        r["_variant"] = clean(r["name_variant"])
        r["_conf"] = float(r["confidence_score"]) if r["confidence_score"] else None
    return rows


def _species_level_rows():
    """{"metarhizium anisopliae": [lignes...], ...} : les deux premiers mots de chaque variante.

    Permet de reconnaître un ancien nom d'espèce écrit sans souche.
    """
    groups = {}
    for r in _entity_rows():
        key = " ".join(r["_variant"].split()[:2])
        groups.setdefault(key, []).append(r)
    return groups


def normalize_active_entity(texte):
    """Texte libre -> {species, strain, matched_variant, confidence, review_status} ou None.

    1) variante identique, 2) variante contenue dans le texte (la plus longue),
    3) nom d'espèce seul (confiance 0.6, to_verify).
    La souche n'est renvoyée que si elle est écrite dans le texte : on ne
    l'invente pas à partir du mapping (cf. AE-002 du mapping).
    """
    t = clean(texte)
    if not t:
        return None
    rows = _entity_rows()

    row = next((r for r in rows if r["_variant"] == t), None)
    if row is None:
        inside = [r for r in rows if _contains_words(t, r["_variant"])]
        row = max(inside, key=lambda r: len(r["_variant"]), default=None)
    species_only = False
    if row is None:
        for key, group in _species_level_rows().items():
            if _contains_words(t, key):
                # Si une souche connue est écrite dans le texte, on prend la variante de cette souche ;
                # sinon la variante la plus fiable de l'espèce.
                with_strain = [r for r in group if r["strain"] and clean(r["strain"]) in t]
                row = max(with_strain or group, key=lambda r: r["_conf"] or 0)
                species_only = not with_strain   # souche reconnue = correspondance précise, sinon niveau espèce
                break
    if row is None:
        return None

    strain = row["strain"] if row["strain"] and clean(row["strain"]) in t else None
    return {
        "species": row["canonical_species"],
        "strain": strain,
        "matched_variant": row["name_variant"],
        "relationship_type": row["relationship_type"],
        "confidence": 0.6 if species_only else row["_conf"],
        "review_status": "to_verify" if species_only else row["review_status"],
    }


# ---------------------------------------------------------------------------
# Synonymes pour la recherche
# ---------------------------------------------------------------------------
def search_terms_for(texte):
    """Tous les synonymes connus d'un terme ("Gliocladium" -> aussi "Clonostachys rosea").

    Le texte d'origine est toujours en premier. Les produits "soeurs" ne sont
    PAS des synonymes : ils ne sont jamais ajoutés ici.
    """
    t = clean(texte)
    terms = [str(texte).strip()] if texte and str(texte).strip() else []
    if not t:
        return terms

    # Cultures et cibles : tous les noms du même concept
    for filename in ("eppo_crop_mapping.csv", "eppo_pest_mapping.csv"):
        index = _load_eppo_index(filename)
        row = next((index[f] for f in _single_forms(t) if f in index), None)
        if row:
            terms += [row["name_original"], row["name_normalized"], row["scientific_name"]]
            for alias in (row.get("multilingual_aliases") or "").split("|"):
                terms.append(re.sub(r"^[a-z]{2}:", "", alias.strip()))

    # Substances actives : toutes les variantes de la même espèce
    species = {
        r["canonical_species"]
        for r in _entity_rows()
        if _contains_words(r["_variant"], t) or _contains_words(t, r["_variant"]) or clean(r["canonical_species"]) == t
    }
    for r in _entity_rows():
        if r["canonical_species"] in species:
            terms += [r["name_variant"], r["canonical_species"]]
            terms.append(" ".join(r["name_variant"].split()[:2]))  # ex. "Gliocladium catenulatum"

    # Produits : noms connus du même produit (hors produits soeurs) + sa substance active
    for r in _read_csv("product_name_mapping.csv"):
        if clean(r["name_variant"]) == t:
            product_id = r["product_id"]
            terms += [
                p["name_variant"]
                for p in _read_csv("product_name_mapping.csv")
                if p["product_id"] == product_id and p["relationship_type"] != "sister_product_candidate"
            ]
            terms += [e["name_variant"] for e in _entity_rows() if e["product_id"] == product_id]

    # Suppression des doublons (sans tenir compte de la casse/accents), ordre conservé
    seen, result = set(), []
    for term in terms:
        key = clean(term)
        if key and key not in seen:
            seen.add(key)
            result.append(term.strip())
    return result


# ---------------------------------------------------------------------------
# Produits soeurs (hypothèses à vérifier)
# ---------------------------------------------------------------------------
def entity_of_product(product):
    """Espèce + souche d'un produit, à partir de ses colonnes ou, à défaut, du mapping validé."""
    for field in ("active_entity_original", "active_entity_normalized"):
        found = normalize_active_entity(product.get(field))
        if found:
            return found
    # Colonnes vides : on regarde si LPC a déjà validé une substance pour cet identifiant
    for r in _entity_rows():
        if r["product_id"] == product.get("product_id") and r["review_status"] == "validated":
            return {"species": r["canonical_species"], "strain": r["strain"] or None}
    return None


def find_sister_candidates(produits):
    """Liste de produits (dicts avec product_id, commercial_name, active_entity_*) -> candidats soeurs.

    Chaque candidat : {product_a, product_b, reason, evidence, confidence, review_status}
    (+ product_a_id, product_b_id, country_code pour que l'appelant puisse les ranger).
    - même espèce + même souche : 0.9 ; même espèce, souche absente d'un côté : 0.6
      (souches différentes : pas de candidat, la souche est plus précise que l'espèce) ;
    - noms du fichier product_name_mapping.csv (type sister_product_candidate) :
      leur propre confiance et leur propre review_status.
    Statut "to_verify" partout, sauf "validated" écrit explicitement dans le mapping.
    """
    candidates = []
    entities = [(p, entity_of_product(p)) for p in produits]

    # 1) Même espèce (et éventuellement même souche) entre deux produits connus
    for i, (a, ea) in enumerate(entities):
        for b, eb in entities[i + 1:]:
            if not ea or not eb or ea["species"] != eb["species"]:
                continue
            sa, sb = ea.get("strain"), eb.get("strain")
            if sa and sb and clean(sa) == clean(sb):
                confidence, why = 0.9, f"same species ({ea['species']}) and same strain ({sa})"
            elif not sa or not sb:
                confidence, why = 0.6, f"same species ({ea['species']}); strain missing on at least one product"
            else:
                continue  # souches différentes -> identités différentes
            candidates.append({
                "product_a": a["commercial_name"], "product_b": b["commercial_name"],
                "product_a_id": a["product_id"], "product_b_id": b["product_id"],
                "country_code": None,
                "reason": "same_active_entity",
                "evidence": f"{why}; computed from active_entity of both products",
                "confidence": confidence, "review_status": "to_verify",
            })

    # 2) Noms soeurs listés dans product_name_mapping.csv
    by_id = {p["product_id"]: p for p in produits}
    for r in _read_csv("product_name_mapping.csv"):
        if r["relationship_type"] != "sister_product_candidate" or r["product_id"] not in by_id:
            continue
        country = r["market_or_country"] if re.fullmatch(r"[A-Z]{2}", r["market_or_country"] or "") else None
        status = "validated" if r["review_status"] == "validated" else "to_verify"
        candidates.append({
            "product_a": by_id[r["product_id"]]["commercial_name"], "product_b": r["name_variant"],
            "product_a_id": r["product_id"], "product_b_id": None,
            "country_code": country,
            "reason": "lpc_product_name_mapping",
            "evidence": r["evidence_summary"],
            "confidence": float(r["confidence_score"]) if r["confidence_score"] else None,
            "review_status": status,
        })
    return candidates
