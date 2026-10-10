"""Logique métier de l'API (lecture seule).

Chaque fonction publique correspond à une route de openapi.proposed.yaml et renvoie un
dictionnaire aux noms de champs EXACTS du contrat (camelCase). main.py le valide avec les
modèles Pydantic générés (models.py).

Idée centrale : chaque source charge ses propres lignes `products` (un produit par homologation
en France). Retrouver "un produit" dans tous les pays se fait donc par NOMS et ALIAS, et par
SUBSTANCE ACTIVE (espèce + souche). `matchedVia` dit toujours par quel chemin on l'a trouvé.
"""
import calendar
import csv
import io
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# normalize.py vit dans backend/etl (mêmes synonymes que l'ETL)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl"))
import normalize as nz  # noqa: E402

from . import models as m  # noqa: E402
from .db import query, query_many  # noqa: E402

DISCLAIMER = "Pas une source réglementaire officielle. Validation Regulatory Affairs requise."
NO_MATCH = "No match. This is not proof of no registration."

# Marchés cibles affichés dans `coverage` (liste de docs/openapi-changes.md), modifiable ici
TARGET_MARKETS = ["CA", "US", "MX", "BR", "UY", "FR", "DE", "BE", "ES", "IT"]

# Langue de la source selon le pays (Evidence.languageOriginal)
LANGUAGE = {"FR": "fr", "DE": "de", "CA": "en", "US": "en", "BE": "fr", "BR": "pt",
            "MX": "es", "UY": "es", "ES": "es", "IT": "it"}

# Relations de nom retenues pour retrouver les homologations d'un produit.
# Les produits SOEURS (hypothèses) n'en font pas partie : ils ont leur route /sisters.
NAME_RELATIONS = {"canonical_name", "historical_or_market_name", "related_formulation"}
ALIAS_RELATIONS = {"alternate_name", "historical_name", "confirmed_sister_product"}
SISTER_RELATIONS_ALIAS = ("sister_product_candidate", "confirmed_sister_product")
SISTER_RELATIONS_MAPPING = ("sister_product_candidate", "related_formulation", "historical_or_market_name")
CURRENT_NAME_RELATIONS = {"current_label_name", "current_eu_label_name"}


class NotFound(Exception):
    """Produit inconnu de notre catalogue (ce n'est PAS une preuve d'absence d'homologation)."""


# ---------------------------------------------------------------------------
# Petits outils
# ---------------------------------------------------------------------------
REFRESH_MAX_AGE = None   # mis à 60 (s) par warmup.py pendant un rafraîchissement : les valeurs plus vieilles sont recalculées


def cached(seconds):
    """Garde le résultat d'une fonction quelques secondes (petites tables de référence)."""
    def decorator(fn):
        store = {}

        def wrapper(*args):
            hit = store.get(args)
            max_age = seconds if REFRESH_MAX_AGE is None else min(seconds, REFRESH_MAX_AGE)
            if hit and time.time() - hit[0] < max_age:
                return hit[1]
            value = fn(*args)
            store[args] = (time.time(), value)
            return value
        wrapper.clear = store.clear
        return wrapper
    return decorator


def as_enum(value, enum_class):
    """Valeur de la base -> valeur d'enum du contrat, ou None si inconnue (jamais d'erreur)."""
    try:
        return enum_class(value).value
    except ValueError:
        return None


def lower_list(values):
    return sorted({v.strip().lower() for v in values if v and v.strip()})


def unique(values, cap=25):
    """Dédoublonne (sans tenir compte de la casse) en gardant l'ordre."""
    seen, out = set(), []
    for v in values:
        key = (v or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(v.strip())
    return out[:cap]


# ---------------------------------------------------------------------------
# Sources, fraîcheur et couverture par pays
# ---------------------------------------------------------------------------
@cached(30)
def sources_snapshot():
    """{source_id: infos} calculé depuis source_registry + collection_runs (rafraîchi toutes les 30 s)."""
    sources, runs, count_rows = query_many([
        ("""SELECT source_id, official_name, country_or_region, base_url, access_method,
                   data_format, license_name, manual_validation_required
            FROM source_registry ORDER BY source_id""", None),
        # Les lignes "normalize-db" sont des normalisations, pas des collectes : on les ignore
        ("""SELECT source_id, status, started_at, finished_at, input_file FROM collection_runs
            WHERE COALESCE(notes, '') <> 'normalize-db' ORDER BY started_at""", None),
        ("SELECT source_id, count(*) AS n FROM registrations GROUP BY source_id", None)])
    counts = {r["source_id"]: r["n"] for r in count_rows}
    snapshot = {}
    for s in sources:
        sid = s["source_id"]
        mine = [r for r in runs if r["source_id"] == sid]
        finished = [r for r in mine if r["status"] != "running"]   # une collecte en cours ne compte pas
        ok = [r for r in finished if r["status"] == "success"]
        country = s["country_or_region"] if s["country_or_region"] and re.fullmatch(r"[A-Z]{2}", s["country_or_region"]) else None
        snapshot[sid] = {
            "row": s, "country": country, "records": counts.get(sid, 0),
            "has_success": bool(ok),
            "last_status": finished[-1]["status"] if finished else None,
            "last_success": max((r["finished_at"] or r["started_at"] for r in ok), default=None),
            "frozen": any(r["input_file"] for r in ok),
        }
    return snapshot


def build_evidence(evidence_id, reg, validation_status=None, confidence=None):
    """Evidence du contrat à partir d'une ligne de registrations (jointe à son produit)."""
    src = sources_snapshot().get(reg["source_id"])
    row = src["row"] if src else {}
    ev = {
        "evidenceId": evidence_id,
        "sourceId": reg["source_id"],
        "sourceUrl": row.get("base_url") or reg["source_record_url"],
        "sourceRecordUrl": reg["source_record_url"],
        "collectedAt": reg["collected_at"],
        "validationStatus": as_enum(validation_status or reg["validation_status"], m.ValidationStatus) or "to_verify",
        "confidence": confidence,
        "isFrozenExtract": bool(src and src["frozen"]),
        "isSynthetic": bool(reg["is_synthetic"]),
        "languageOriginal": LANGUAGE.get(reg["country_code"]),
    }
    if row.get("official_name"):
        ev["sourceName"] = row["official_name"]
    return ev


def coverage_for(countries, found_by_country, terms):
    """Une entrée CountryCoverage par pays (règles de docs/openapi-changes.md).

    found            : au moins une homologation trouvée.
    not_found        : une source du pays a une collecte réussie mais rien n'a été trouvé
                       (PAS une preuve d'absence d'homologation).
    source_unavailable : la dernière collecte de toutes les sources du pays a échoué.
    not_covered      : aucune source du pays n'a de collecte réussie.
    """
    snapshot = sources_snapshot()
    result = []
    for cc in countries:
        sources = [s for s in snapshot.values() if s["country"] == cc]
        ok = [s for s in sources if s["has_success"]]
        last = max((s["last_success"] for s in ok), default=None)
        regs = found_by_country.get(cc, [])
        entry = {"countryCode": cc, "searchedTerms": terms}
        if regs:
            entry.update(outcome="found", sourceIds=sorted({r["source_id"] for r in regs}),
                         registrationIds=[r["registration_id"] for r in regs],
                         lastCollectedAt=last or max(r["collected_at"] for r in regs), note=None)
        elif ok:
            entry.update(outcome="not_found", sourceIds=sorted(s["row"]["source_id"] for s in ok),
                         lastCollectedAt=last, registrationIds=[],
                         note="Searched without result. Not proof of no registration.")
        elif sources and all(s["last_status"] in ("failed", "source_unavailable") for s in sources):
            entry.update(outcome="source_unavailable", sourceIds=sorted(s["row"]["source_id"] for s in sources),
                         lastCollectedAt=None, registrationIds=[],
                         note="The last collection of the source failed. Not proof of no registration.")
        else:
            entry.update(outcome="not_covered", sourceIds=[], lastCollectedAt=None, registrationIds=[],
                         note="No integrated source for this country yet. Not proof of no registration.")
            entry["searchedTerms"] = []
        result.append(entry)
    return result


def coverage_warnings(coverage):
    """Phrases prudentes pour chaque pays sans résultat."""
    texts = {
        "not_found": "{cc} : aucun résultat dans la source collectée. Cela ne prouve pas l'absence d'homologation.",
        "source_unavailable": "{cc} : source indisponible lors de la dernière collecte. Aucune conclusion possible.",
        "not_covered": "{cc} : pays pas encore couvert par une source intégrée. Aucune conclusion possible.",
    }
    return [texts[c["outcome"]].format(cc=c["countryCode"]) for c in coverage if c["outcome"] in texts]


# ---------------------------------------------------------------------------
# Catalogue produits
# ---------------------------------------------------------------------------
def get_product(product_id):
    rows = query("""SELECT product_id, commercial_name, active_entity_original, active_entity_normalized,
                           formulation_code, is_synthetic, validation_status
                    FROM products WHERE product_id = :p""", {"p": product_id})
    if not rows:
        raise NotFound(product_id)
    return rows[0]


@cached(60)
def lpc_names():
    """(ids, noms en minuscules) des produits LPC = ceux du fichier product_name_mapping (hors soeurs)."""
    rows = query("""SELECT product_id, name_variant FROM product_name_mapping
                    WHERE relationship_type <> 'sister_product_candidate'""")
    return sorted({r["product_id"] for r in rows}), sorted({r["name_variant"].lower() for r in rows})


def entity_patterns(terms):
    """Motifs LIKE pour chercher une substance active (termes trop courts ignorés : trop de bruit)."""
    patterns = {f"%{t.strip().lower()}%" for t in terms if t and (len(t.strip()) >= 8 or " " in t.strip())}
    return sorted(patterns)[:40]


def product_aliases_of(product_ids, include_synthetic):
    """Alias de plusieurs produits d'un coup (3 requêtes en tout) -> {product_id: [ProductAlias]}."""
    if not product_ids:
        return {}
    out = {pid: [] for pid in product_ids}
    syn = "" if include_synthetic else "AND NOT is_synthetic"

    def add(pid, name, kind, rel, strain=None, market=None, score=None, cstatus=None, review=None, summary=None):
        rel = as_enum(rel, m.AliasRelationshipType)
        if rel is None or not name:
            return
        alias = {"name": name, "kind": kind, "relationshipType": rel, "strain": strain, "marketOrCountry": market,
                 "confidenceScore": score, "evidenceSummary": summary}
        if as_enum(cstatus, m.ConfidenceStatus):
            alias["confidenceStatus"] = cstatus
        if as_enum(review, m.ReviewStatus):
            alias["reviewStatus"] = review
        out[pid].append(alias)

    ids = {"ids": list(product_ids)}
    alias_rows, mapping_rows, entity_rows = query_many([
        (f"""SELECT product_id, alias_name, country_code, relationship_type, confidence, evidence, review_status
             FROM product_aliases WHERE product_id = ANY(CAST(:ids AS text[])) {syn}""", ids),
        ("""SELECT product_id, name_variant, relationship_type, market_or_country, confidence_score,
                   confidence_status, evidence_summary, review_status
            FROM product_name_mapping WHERE product_id = ANY(CAST(:ids AS text[]))""", ids),
        ("""SELECT product_id, name_variant, strain, relationship_type, confidence_score,
                   confidence_status, evidence_summary, review_status
            FROM active_entity_mapping WHERE product_id = ANY(CAST(:ids AS text[]))""", ids)])
    for r in alias_rows:
        add(r["product_id"], r["alias_name"], "product_name", r["relationship_type"], market=r["country_code"],
            score=r["confidence"], review=r["review_status"], summary=r["evidence"])
    for r in mapping_rows:
        add(r["product_id"], r["name_variant"], "product_name", r["relationship_type"], market=r["market_or_country"],
            score=r["confidence_score"], cstatus=r["confidence_status"], review=r["review_status"],
            summary=r["evidence_summary"])
    for r in entity_rows:
        add(r["product_id"], r["name_variant"], "active_entity", r["relationship_type"], strain=r["strain"],
            score=r["confidence_score"], cstatus=r["confidence_status"], review=r["review_status"],
            summary=r["evidence_summary"])
    return out


def entity_via(original, normalized, fallback_name):
    """matchedVia d'un produit trouvé par sa substance active (via le mapping LPC si possible)."""
    for text in (original, normalized):
        res = nz.normalize_active_entity(text)
        if res:
            on = "active_entity" if res["relationship_type"] in CURRENT_NAME_RELATIONS else "active_entity_alias"
            via = {"matchedName": res["matched_variant"], "matchedOn": on, "aliasConfidenceScore": res["confidence"]}
            if as_enum(res["relationship_type"], m.AliasRelationshipType):
                via["aliasRelationshipType"] = res["relationship_type"]
            if as_enum(res["review_status"], m.ReviewStatus):
                via["aliasReviewStatus"] = res["review_status"]
            return via
    return {"matchedName": fallback_name, "matchedOn": "active_entity"}


def search_products(q, active_entity, crop, target, country, include_competitors, include_synthetic, limit, offset):
    """GET /products : nom, alias et synonymes (search_terms_for) + filtres. Triés par pertinence."""
    syn_prod = "" if include_synthetic else "AND NOT p.is_synthetic"
    hits = None   # {product_id: (rang, matchedVia)} ; None = pas de recherche texte

    def entity_request(terms):
        """Requête (ou None) cherchant les produits dont la substance active contient un des termes."""
        patterns = entity_patterns(terms)
        if not patterns:
            return None
        return (f"""SELECT p.product_id, p.active_entity_original, p.active_entity_normalized FROM products p
                    WHERE (lower(p.active_entity_normalized) LIKE ANY(CAST(:p AS text[]))
                           OR lower(p.active_entity_original) LIKE ANY(CAST(:p AS text[]))) {syn_prod}
                    LIMIT 3000""", {"p": patterns})

    def entity_found(rows, text):
        return {r["product_id"]: entity_via(r["active_entity_original"], r["active_entity_normalized"], text.strip())
                for r in rows}

    # Toutes les requêtes de recherche sont indépendantes : on les lance ensemble (en parallèle)
    text_q = q.strip() if q and q.strip() else None
    text_e = active_entity.strip() if active_entity and active_entity.strip() else None
    requests, kinds = [], []
    if text_q:
        terms_q = unique(nz.search_terms_for(text_q), cap=60)
        lowers = lower_list(terms_q)
        like = f"%{text_q.lower()}%"
        syn_alias = "" if include_synthetic else "AND NOT a.is_synthetic"
        requests += [
            (f"""SELECT p.product_id, p.commercial_name FROM products p
                 WHERE (lower(p.commercial_name) = ANY(CAST(:t AS text[])) OR lower(p.commercial_name) LIKE :like)
                 {syn_prod} LIMIT 3000""", {"t": lowers, "like": like}),
            (f"""SELECT a.product_id, a.alias_name, a.relationship_type, a.review_status, a.confidence
                 FROM product_aliases a
                 WHERE (lower(a.alias_name) = ANY(CAST(:t AS text[])) OR lower(a.alias_name) LIKE :like)
                 {syn_alias} LIMIT 3000""", {"t": lowers, "like": like})]
        kinds += ["name", "alias"]
        req = entity_request(terms_q)
        if req:
            requests.append(req)
            kinds.append("entity_q")
    if text_e:
        terms_e = unique(nz.search_terms_for(text_e), cap=60)
        req = entity_request(terms_e)
        if req:
            requests.append(req)
            kinds.append("entity_e")
    results = dict(zip(kinds, query_many(requests))) if requests else {}

    if text_q:
        hits = {}
        # rang 1 : nom exact (ou synonyme exact) ; rang 2 : nom qui contient le texte
        for r in results.get("name", []):
            rank = 1 if r["commercial_name"].lower() in lowers else 2
            hits[r["product_id"]] = (rank, {"matchedName": r["commercial_name"], "matchedOn": "commercial_name"})
        # rang 3 : alias
        for r in results.get("alias", []):
            if r["product_id"] in hits:
                continue
            via = {"matchedName": r["alias_name"], "matchedOn": "product_alias", "aliasConfidenceScore": r["confidence"]}
            if as_enum(r["relationship_type"], m.AliasRelationshipType):
                via["aliasRelationshipType"] = r["relationship_type"]
            if as_enum(r["review_status"], m.ReviewStatus):
                via["aliasReviewStatus"] = r["review_status"]
            hits[r["product_id"]] = (3, via)
        # rang 4 : substance active (texte d'origine ou normalisé)
        for pid, via in entity_found(results.get("entity_q", []), text_q).items():
            hits.setdefault(pid, (4, via))
    if text_e:
        ent = {pid: (4, via) for pid, via in entity_found(results.get("entity_e", []), text_e).items()}
        hits = ent if hits is None else {k: v for k, v in hits.items() if k in ent}

    conds, params = [], {"limit": limit, "offset": offset}
    if not include_synthetic:
        conds.append("NOT p.is_synthetic")
    join, order = "", "p.commercial_name, p.product_id"
    if hits is not None:
        ordered = sorted(hits, key=lambda pid: (hits[pid][0], pid))
        join = "JOIN unnest(CAST(:ids AS text[])) WITH ORDINALITY AS h(pid, ord) ON h.pid = p.product_id"
        order = "h.ord"
        params["ids"] = ordered
    if country:
        conds.append("EXISTS (SELECT 1 FROM registrations r WHERE r.product_id = p.product_id AND r.country_code = :country)")
        params["country"] = country.upper()
    for kind, value, resolver, code_col, name_col, orig_col in (
            ("crop", crop, nz.normalize_crop, "eppo_crop_code", "crop_name_normalized", "crop_name_original"),
            ("target", target, nz.normalize_target, "eppo_target_code", "target_name_normalized", "target_name_original")):
        if value and value.strip():
            code, like = resolve_eppo(value, resolver)
            if code:
                cond, params[f"{kind}_code"] = f"u.{code_col} = :{kind}_code", code
            else:
                cond, params[f"{kind}_like"] = f"(u.{orig_col} ILIKE :{kind}_like OR u.{name_col} ILIKE :{kind}_like)", like
            conds.append(f"""EXISTS (SELECT 1 FROM registrations r JOIN uses u ON u.registration_id = r.registration_id
                                     WHERE r.product_id = p.product_id AND {cond})""")
    if not include_competitors:
        lpc_ids, lpc_low = lpc_names()
        conds.append("(p.product_id = ANY(CAST(:lpc_ids AS text[])) OR lower(p.commercial_name) = ANY(CAST(:lpc_names AS text[])))")
        params["lpc_ids"], params["lpc_names"] = lpc_ids, lpc_low

    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    rows = query(f"""SELECT p.product_id, p.commercial_name, p.active_entity_original, p.active_entity_normalized,
                            p.formulation_code, p.is_synthetic, p.validation_status
                     FROM products p {join} {where} ORDER BY {order} LIMIT :limit OFFSET :offset""", params)

    aliases = product_aliases_of([r["product_id"] for r in rows], include_synthetic)
    lpc_ids, lpc_low = lpc_names()
    items = []
    for r in rows:
        item = {
            "productId": r["product_id"], "commercialName": r["commercial_name"],
            "activeEntityOriginal": r["active_entity_original"], "activeEntityNormalized": r["active_entity_normalized"],
            "formulationCode": r["formulation_code"], "isSynthetic": bool(r["is_synthetic"]),
            "isLpcProduct": r["product_id"] in lpc_ids or r["commercial_name"].lower() in lpc_low,
            "aliases": aliases.get(r["product_id"], []),
        }
        if as_enum(r["validation_status"], m.ValidationStatus):
            item["validationStatus"] = r["validation_status"]
        if hits is not None and r["product_id"] in hits:
            item["matchedVia"] = hits[r["product_id"]][1]
        items.append(item)
    return {"items": items}


def resolve_eppo(value, resolver):
    """Culture/cible (code EPPO ou nom, toute langue) -> (code EPPO ou None, motif LIKE de secours)."""
    value = value.strip()
    if re.fullmatch(r"[A-Z0-9]{5,6}", value):
        return value, None
    found = resolver(value)
    if found and found["eppo_code"]:
        return found["eppo_code"], None
    return None, f"%{value}%"


# ---------------------------------------------------------------------------
# Homologations d'un produit (cœur de l'API)
# ---------------------------------------------------------------------------
def load_reference(product_id):
    """Produit + lignes de mapping utiles à son profil, en UNE étape (4 requêtes en parallèle)."""
    p = {"p": product_id}
    product, name_rows, alias_rows, entity_rows = query_many([
        ("""SELECT product_id, commercial_name, active_entity_original, active_entity_normalized,
                   formulation_code, is_synthetic, validation_status FROM products WHERE product_id = :p""", p),
        ("""SELECT name_variant, relationship_type, review_status, confidence_score
            FROM product_name_mapping WHERE product_id = :p""", p),
        ("""SELECT alias_name, relationship_type, review_status, confidence
            FROM product_aliases WHERE product_id = :p AND NOT is_synthetic""", p),
        ("""SELECT name_variant, canonical_species, strain FROM active_entity_mapping WHERE product_id = :p""", p)])
    if not product:
        raise NotFound(product_id)
    return product[0], (name_rows, alias_rows, entity_rows)


def build_profile(ref, rows):
    """Noms, substances et souches à chercher pour retrouver les homologations du produit `ref`."""
    name_rows, alias_rows, ents = rows
    names = {}   # nom en minuscules -> infos sur le lien avec le produit

    def add(name, kind, rel=None, review=None, conf=None):
        key = (name or "").strip().lower()
        if key and key not in names:
            names[key] = {"name": name.strip(), "kind": kind, "rel": rel, "review": review, "conf": conf}

    add(ref["commercial_name"], "commercial_name")
    for r in name_rows:
        if r["relationship_type"] in NAME_RELATIONS:
            kind = "commercial_name" if r["relationship_type"] == "canonical_name" else "product_alias"
            add(r["name_variant"], kind, r["relationship_type"], r["review_status"], r["confidence_score"])
    for r in alias_rows:
        if r["relationship_type"] in ALIAS_RELATIONS:
            add(r["alias_name"], "product_alias", r["relationship_type"], r["review_status"], r["confidence"])

    species, strains, patterns, variants = set(), set(), set(), []
    for e in ents:
        species.add(e["canonical_species"])
        if e["strain"]:
            strains.add(nz.clean(e["strain"]))
        patterns.add(f"%{' '.join(e['name_variant'].lower().split()[:2])}%")   # ex. %metarhizium anisopliae%
        patterns.add(f"%{e['canonical_species'].lower()}%")
        variants.append(e["name_variant"])
    if not ents:   # produit hors mapping LPC : on lit sa propre substance active
        res = nz.normalize_active_entity(ref["active_entity_original"]) or nz.normalize_active_entity(ref["active_entity_normalized"])
        if res:
            species.add(res["species"])
            patterns.add(f"%{res['species'].lower()}%")
            if res["strain"]:
                strains.add(nz.clean(res["strain"]))
            variants.append(f"{res['species']} {res['strain']}" if res["strain"] else res["species"])
    return {"names": names, "species": species, "strains": strains, "patterns": sorted(patterns),
            "terms": unique([n["name"] for n in names.values()] + variants)}


def classify(row, ref, profile):
    """Dit si une homologation correspond au produit, et comment : (matchedVia, avertissement) ou None."""
    if row["product_id"] == ref["product_id"]:
        return {"matchedName": row["commercial_name"], "matchedOn": "commercial_name"}, None

    hit = profile["names"].get((row["commercial_name"] or "").strip().lower())
    if hit:
        via = {"matchedName": row["commercial_name"], "matchedOn": hit["kind"]}
        warning = None
        if hit["kind"] == "product_alias":
            if as_enum(hit["rel"], m.AliasRelationshipType):
                via["aliasRelationshipType"] = hit["rel"]
            if as_enum(hit["review"], m.ReviewStatus):
                via["aliasReviewStatus"] = hit["review"]
            via["aliasConfidenceScore"] = hit["conf"]
            if hit["review"] != "validated":
                warning = f"Correspondance par le nom « {hit['name']} », encore à vérifier."
        return via, warning

    if profile["species"]:
        res = nz.normalize_active_entity(row["active_entity_original"]) or nz.normalize_active_entity(row["active_entity_normalized"])
        if res and res["species"] in profile["species"]:
            strain = nz.clean(res["strain"]) if res["strain"] else None
            if profile["strains"] and strain and strain not in profile["strains"]:
                return None   # autre souche = autre identité : on ne rapproche pas
            weak = bool(profile["strains"]) and strain is None   # souche non écrite dans la source
            on = "active_entity" if res["relationship_type"] in CURRENT_NAME_RELATIONS else "active_entity_alias"
            review = "validated" if (res["review_status"] == "validated" and not weak) else "to_verify"
            via = {"matchedName": res["matched_variant"], "matchedOn": on, "aliasReviewStatus": review,
                   "aliasConfidenceScore": res["confidence"]}
            if as_enum(res["relationship_type"], m.AliasRelationshipType):
                via["aliasRelationshipType"] = res["relationship_type"]
            warning = None
            if weak:
                warning = "Souche non précisée dans la source : rapprochement au niveau de l'espèce, à vérifier."
            elif review != "validated":
                warning = f"Correspondance par la substance active « {res['matched_variant']} », encore à vérifier."
            return via, warning
    return None


MATCH_ORDER = {"commercial_name": 0, "product_alias": 1, "active_entity": 2, "active_entity_alias": 3}


def match_registrations(ref, profile, countries, include_synthetic, cap=1000):
    """Homologations liées au produit (noms, alias, substance active). Renvoie (liste, tronquée?)."""
    params = {"pid": ref["product_id"], "names": list(profile["names"])}
    cond = "r.product_id = :pid OR lower(p.commercial_name) = ANY(CAST(:names AS text[]))"
    if profile["patterns"]:
        cond += (" OR lower(p.active_entity_normalized) LIKE ANY(CAST(:pats AS text[]))"
                 " OR lower(p.active_entity_original) LIKE ANY(CAST(:pats AS text[]))")
        params["pats"] = profile["patterns"]
    extra = ""
    if countries:
        extra += " AND r.country_code = ANY(CAST(:ccs AS text[]))"
        params["ccs"] = list(countries)
    if not include_synthetic:
        extra += " AND NOT r.is_synthetic AND NOT p.is_synthetic"
    rows = query(f"""SELECT r.registration_id, r.product_id, r.country_code, r.authority_name, r.registration_number,
                            r.status_original, r.status_normalized, r.approval_date, r.expiration_date, r.source_id,
                            r.source_record_url, r.collected_at, r.validation_status, r.is_synthetic,
                            p.commercial_name, p.active_entity_original, p.active_entity_normalized
                     FROM registrations r JOIN products p ON p.product_id = r.product_id
                     WHERE ({cond}) {extra}
                     ORDER BY r.country_code, p.commercial_name, r.registration_id LIMIT :cap""",
                 dict(params, cap=cap + 1))
    truncated = len(rows) > cap
    matched = []
    for row in rows[:cap]:
        result = classify(row, ref, profile)
        if result:
            row["matched_via"], row["match_warning"] = result
            matched.append(row)
    matched.sort(key=lambda r: (r["country_code"], MATCH_ORDER[r["matched_via"]["matchedOn"]], r["commercial_name"], r["registration_id"]))
    return matched, truncated


def mapping_status(original, code, status, normalized=None):
    """cropMappingStatus / targetMappingStatus : validated, to_verify ou unmapped (None si rien à dire).

    Un nom normalisé sans code EPPO vient du dictionnaire IA (hypothèse à vérifier) : to_verify, pas unmapped.
    """
    if code:
        return as_enum(status, m.MappingStatus) or "to_verify"
    if normalized:
        return "to_verify"
    return "unmapped" if original else None


def fetch_uses(regs_by_id, include_synthetic, crop=None, target=None, cap=5000, per_registration=None):
    """Usages des homologations données -> ({registration_id: [AuthorizedUse]}, avertissements).

    per_registration : nombre maximum d'usages renvoyés par homologation (None = tous, dans la limite de `cap`).
    """
    if not regs_by_id:
        return {}, []
    where, params = "", {"rids": list(regs_by_id), "cap": cap + 1}
    if not include_synthetic:
        where += " AND NOT u.is_synthetic"
    for kind, value, resolver, code_col, name_col, orig_col in (
            ("crop", crop, nz.normalize_crop, "eppo_crop_code", "crop_name_normalized", "crop_name_original"),
            ("target", target, nz.normalize_target, "eppo_target_code", "target_name_normalized", "target_name_original")):
        if value and value.strip():
            code, like = resolve_eppo(value, resolver)
            if code:
                where += f" AND u.{code_col} = :{kind}_code"
                params[f"{kind}_code"] = code
            else:
                where += f" AND (u.{orig_col} ILIKE :{kind}_like OR u.{name_col} ILIKE :{kind}_like)"
                params[f"{kind}_like"] = like
    per = "" if per_registration is None else "WHERE rn <= :per"
    if per_registration is not None:
        params["per"] = per_registration
    rows = query(f"""SELECT * FROM (SELECT u.use_id, u.registration_id, u.crop_name_original, u.crop_name_normalized, u.eppo_crop_code,
                            u.target_name_original, u.target_name_normalized, u.eppo_target_code, u.application_method,
                            u.dose_value, u.dose_unit_original, u.dose_unit_normalized, u.max_applications,
                            u.application_interval_days, u.phi_days, u.rei_hours, u.restrictions_original,
                            u.validation_status, u.is_synthetic,
                            cm.mapping_status AS crop_ms, pm.mapping_status AS target_ms,
                            row_number() OVER (PARTITION BY u.registration_id ORDER BY u.use_id) AS rn,
                            count(*) OVER (PARTITION BY u.registration_id) AS total
                     FROM uses u
                     LEFT JOIN eppo_crop_mapping cm ON cm.eppo_code = u.eppo_crop_code
                     LEFT JOIN eppo_pest_mapping pm ON pm.eppo_code = u.eppo_target_code
                     WHERE u.registration_id = ANY(CAST(:rids AS text[])) {where}
                     ) t {per} ORDER BY registration_id, use_id LIMIT :cap""", params)
    warnings = []
    if len(rows) > cap:
        warnings.append(f"Liste d'usages tronquée ({cap} usages maximum par réponse) : ajoutez un filtre crop/target.")
    cut = {u["registration_id"]: u["total"] for u in rows if per_registration is not None and u["total"] > per_registration}
    if cut:
        warnings.append(f"{len(cut)} homologation(s) ont plus de {per_registration} usages : seuls les {per_registration} premiers "
                        f"sont renvoyés (paramètre usesLimit), ex. {next(iter(cut))} : {next(iter(cut.values()))} usages.")
    out = {}
    for u in rows[:cap]:
        reg = regs_by_id[u["registration_id"]]
        use = {
            "useId": u["use_id"],
            "cropOriginal": u["crop_name_original"], "cropNormalized": u["crop_name_normalized"],
            "eppoCropCode": u["eppo_crop_code"],
            "targetOriginal": u["target_name_original"], "targetNormalized": u["target_name_normalized"],
            "eppoTargetCode": u["eppo_target_code"],
            "doseValue": u["dose_value"], "doseUnitOriginal": u["dose_unit_original"],
            "doseUnitNormalized": u["dose_unit_normalized"], "applicationMethod": u["application_method"],
            "maxApplications": u["max_applications"], "applicationIntervalDays": u["application_interval_days"],
            "phiDays": u["phi_days"], "reiHours": u["rei_hours"], "restrictionsOriginal": u["restrictions_original"],
            "isSynthetic": bool(u["is_synthetic"] or reg["is_synthetic"]),
            "evidence": build_evidence(f"use:{u['use_id']}", reg, validation_status=u["validation_status"]),
        }
        for key, original, code, status, normalized in (
                ("cropMappingStatus", u["crop_name_original"], u["eppo_crop_code"], u["crop_ms"], u["crop_name_normalized"]),
                ("targetMappingStatus", u["target_name_original"], u["eppo_target_code"], u["target_ms"], u["target_name_normalized"])):
            value = mapping_status(original, code, status, normalized)
            if value:
                use[key] = value
        out.setdefault(u["registration_id"], []).append(use)
    return out, warnings


def registration_dict(row, uses):
    """Une ligne `registrations` (+ produit) -> Registration du contrat."""
    missing = [name for name, value in (("registrationNumber", row["registration_number"]),
                                        ("statusOriginal", row["status_original"]),
                                        ("approvalDate", row["approval_date"]),
                                        ("expirationDate", row["expiration_date"])) if value is None]
    if not uses:
        missing.append("uses")
    return {
        "registrationId": row["registration_id"], "productId": row["product_id"], "countryCode": row["country_code"],
        "authorityName": row["authority_name"], "registrationNumber": row["registration_number"],
        "statusOriginal": row["status_original"],
        "statusNormalized": as_enum(row["status_normalized"], m.RegistrationStatus) or "unknown",
        "approvalDate": row["approval_date"], "expirationDate": row["expiration_date"],
        "productNameOriginal": row["commercial_name"], "activeEntityOriginal": row["active_entity_original"],
        "matchedVia": row["matched_via"], "missingFields": missing,
        "warnings": [row["match_warning"]] if row.get("match_warning") else [],
        "isSynthetic": bool(row["is_synthetic"]),
        "uses": uses,
        "evidence": build_evidence(f"registration:{row['registration_id']}", row),
    }


def registrations_of_products(product_ids, countries, crop, target, include_synthetic, limit=200):
    """Homologations de produits PRÉCIS (sans élargir par alias ni substance), usages filtrés par crop/target.

    Sert à /ask (recherche par substance) : GET /products renvoie les produits, ceci renvoie leurs homologations.
    Avec un filtre crop/target, seules les homologations qui ont un usage correspondant sont gardées.
    Renvoie (liste de Registration, avertissements).
    """
    if not product_ids:
        return [], []
    params = {"ids": list(product_ids), "cap": limit}
    extra = ""
    if countries:
        extra += " AND r.country_code = ANY(CAST(:ccs AS text[]))"
        params["ccs"] = list(countries)
    if not include_synthetic:
        extra += " AND NOT r.is_synthetic AND NOT p.is_synthetic"
    rows = query(f"""SELECT r.registration_id, r.product_id, r.country_code, r.authority_name, r.registration_number,
                            r.status_original, r.status_normalized, r.approval_date, r.expiration_date, r.source_id,
                            r.source_record_url, r.collected_at, r.validation_status, r.is_synthetic,
                            p.commercial_name, p.active_entity_original, p.active_entity_normalized
                     FROM registrations r JOIN products p ON p.product_id = r.product_id
                     WHERE r.product_id = ANY(CAST(:ids AS text[])) {extra}
                     ORDER BY r.country_code, p.commercial_name, r.registration_id LIMIT :cap""", params)
    for row in rows:   # trouvées par leur propre produit : pas d'hypothèse de rapprochement
        row["matched_via"], row["match_warning"] = {"matchedName": row["commercial_name"], "matchedOn": "commercial_name"}, None
    uses, warnings = fetch_uses({r["registration_id"]: r for r in rows}, include_synthetic, crop, target, per_registration=5)
    if (crop and crop.strip()) or (target and target.strip()):
        rows = [r for r in rows if uses.get(r["registration_id"])]
    return [registration_dict(r, uses.get(r["registration_id"], [])) for r in rows], warnings


def search_terms_of(profile):
    return profile["terms"]


def product_registrations(product_id, country, include_synthetic, limit, offset, uses_limit):
    """GET /products/{id}/registrations."""
    ref, rows = load_reference(product_id)
    profile = build_profile(ref, rows)
    countries = [country.upper()] if country else None
    matched, truncated = match_registrations(ref, profile, countries, include_synthetic)

    found = {}
    for r in matched:
        found.setdefault(r["country_code"], []).append(r)
    shown = list(TARGET_MARKETS)
    shown += sorted(cc for cc in found if cc not in shown)
    if country:
        shown = [country.upper()]
    coverage = coverage_for(shown, found, search_terms_of(profile))

    page = matched[offset:offset + limit]
    uses, uses_warnings = fetch_uses({r["registration_id"]: r for r in page}, include_synthetic, per_registration=uses_limit)
    items = [registration_dict(r, uses.get(r["registration_id"], [])) for r in page]

    warnings = coverage_warnings(coverage)
    warnings += [w for w in unique([r["match_warning"] for r in matched if r.get("match_warning")], cap=10)]
    if truncated:
        warnings.append("Résultat limité aux 1000 premières lignes candidates.")
    warnings += uses_warnings
    if len(matched) > offset + limit:
        warnings.append(f"{len(matched)} homologations trouvées : utilisez limit/offset pour paginer.")
    return {"items": items, "coverage": coverage, "warnings": warnings, "disclaimer": DISCLAIMER}


# ---------------------------------------------------------------------------
# Comparaison entre pays
# ---------------------------------------------------------------------------
def eppo_lookup(uses):
    """{("crop"|"target", nom normalisé en minuscules): code EPPO} pour les noms qui ont UN SEUL code dans ces usages.

    Sert à rapprocher « Tomato » (sans code, FR ou CA) de « Tomato » (code LYPES, autre pays).
    """
    seen = {}
    for use in uses:
        for kind, code, name in (("crop", use["eppoCropCode"], use["cropNormalized"]),
                                 ("target", use["eppoTargetCode"], use["targetNormalized"])):
            if code and name:
                seen.setdefault((kind, name.strip().lower()), set()).add(code)
    return {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}


def row_key(use, lookup=None):
    """(clé d'alignement, alignedBy). Par partie (culture, cible) : code EPPO si connu, SINON nom normalisé
    (insensible à la casse), SINON valeur originale. alignedBy = la méthode la plus faible des deux parties
    (eppo > normalized_name > original)."""
    lookup = lookup or {}
    c, ck = key_part("crop", use["eppoCropCode"], use["cropNormalized"], use["cropOriginal"], lookup)
    t, tk = key_part("target", use["eppoTargetCode"], use["targetNormalized"], use["targetOriginal"], lookup)
    order = ["eppo", "normalized_name", "original"]
    weakest = max((k for k in (ck, tk) if k), key=order.index, default="original")
    return f"{ck}:{c}|{tk}:{t}", weakest


def key_part(kind, code, normalized, original, lookup):
    """(valeur, méthode) d'une partie (culture ou cible) : code EPPO, sinon nom normalisé, sinon valeur originale."""
    if code:
        return code, "eppo"
    if normalized:
        name = normalized.strip().lower()
        return (lookup[(kind, name)], "eppo") if (kind, name) in lookup else (name, "normalized_name")
    if original:
        return original.strip().lower(), "original"
    return "", None   # partie absente : ne compte pas dans alignedBy


def crop_key(use, lookup=None):
    """(clé, alignedBy) au niveau culture seulement : la cible est ignorée, deux cultures différentes ne sont jamais fusionnées."""
    c, ck = key_part("crop", use["eppoCropCode"], use["cropNormalized"], use["cropOriginal"], lookup or {})
    return f"{ck}:{c}", ck or "original"


def crop_cell_summary(uses):
    """Résumé d'une cellule (pays × culture) : nombre d'usages, cibles ORIGINALES, doses min-max PAR unité originale.
    Les unités ne sont jamais converties : une unité = une ligne de dose."""
    targets = sorted({u["targetOriginal"] for u in uses if u["targetOriginal"]})
    by_unit = {}
    for u in uses:
        if u["doseValue"] is not None:
            by_unit.setdefault(u["doseUnitOriginal"], []).append(float(u["doseValue"]))
    doses = [{"unitOriginal": unit, "min": min(vals), "max": max(vals)}
             for unit, vals in sorted(by_unit.items(), key=lambda kv: kv[0] or "")]
    return {"useCount": len(uses), "targetsOriginal": targets, "doses": doses}


def term_groups(use_ids):
    """{(use_id, "crop_group" | "target_group"): groupe} lu dans field_evidence (regroupement suggéré par l'IA).

    Le groupe (ex. "Powdery mildews") n'a pas de colonne dédiée : il est dans excerpt, sous la forme "group_en=...".
    """
    if not use_ids:
        return {}
    rows = query("""SELECT entity_id, field_name, excerpt FROM field_evidence
                    WHERE entity_type = 'use' AND field_name IN ('crop_group', 'target_group')
                      AND entity_id = ANY(CAST(:ids AS text[]))""", {"ids": list(use_ids)})
    return {(r["entity_id"], r["field_name"]): r["excerpt"].removeprefix("group_en=")
            for r in rows if r["excerpt"] and r["excerpt"].startswith("group_en=")}


def compare_uses(product_id, countries, crop, target, include_synthetic, limit, offset, granularity="use"):
    """GET /compare : lignes alignées par EPPO, une cellule par pays, jamais de mélange entre pays.

    granularity="use" : une ligne par culture × cible. "crop" : une ligne par culture (la cible est ignorée pour
    l'alignement mais reste visible dans summary.targetsOriginal) ; utile quand un pays ne précise pas la cible."""
    by_crop = granularity == "crop"
    ref, rows = load_reference(product_id)
    profile = build_profile(ref, rows)
    matched, truncated = match_registrations(ref, profile, countries, include_synthetic)
    regs_by_id = {r["registration_id"]: r for r in matched}
    uses, uses_warnings = fetch_uses(regs_by_id, include_synthetic, crop, target)

    found = {}
    for r in matched:
        found.setdefault(r["country_code"], []).append(r)
    coverage = coverage_for(countries, found, search_terms_of(profile))
    outcome = {c["countryCode"]: c["outcome"] for c in coverage}

    # Lignes : clé -> {libellés, cellules par pays}
    groups = term_groups([use["useId"] for use_list in uses.values() for use in use_list])
    lookup = eppo_lookup([use for use_list in uses.values() for use in use_list])
    rows = {}
    for rid, use_list in uses.items():
        cc = regs_by_id[rid]["country_code"]
        for use in use_list:
            key, aligned_by = (crop_key if by_crop else row_key)(use, lookup)
            row = rows.setdefault(key, {
                "alignedBy": aligned_by,
                "cropNormalized": use["cropNormalized"], "eppoCropCode": use["eppoCropCode"],
                "targetNormalized": None if by_crop else use["targetNormalized"],
                "eppoTargetCode": None if by_crop else use["eppoTargetCode"],
                "cropGroup": None, "targetGroup": None, "by_country": {}})
            for key, field in (("cropGroup", "crop_group"), ("targetGroup", "target_group")):
                if by_crop and field == "target_group":
                    continue   # plusieurs cibles par ligne : un groupe de cibles n'aurait pas de sens
                row[key] = row[key] or groups.get((use["useId"], field))
            row["by_country"].setdefault(cc, {"registrationId": rid, "uses": []})["uses"].append(use)

    out_rows = []
    for key, row in sorted(rows.items(), key=lambda kv: kv[0]):
        cells, doses = [], {}
        for cc in countries:
            if cc in row["by_country"]:
                cell = {"countryCode": cc, "state": "present", **row["by_country"][cc]}
                if by_crop:
                    cell["summary"] = crop_cell_summary(cell["uses"])
                doses[cc] = sorted({(u["doseValue"], u["doseUnitNormalized"]) for u in cell["uses"]},
                                   key=lambda d: (d[0] is None, d[0] or 0, d[1] or ""))
            elif cc in found:
                cell = {"countryCode": cc, "state": "absent_in_extracted_uses", "registrationId": found[cc][0]["registration_id"], "uses": []}
            else:
                state = {"not_found": "registration_not_found", "source_unavailable": "source_unavailable",
                         "not_covered": "not_covered"}.get(outcome.get(cc), "registration_not_found")
                cell = {"countryCode": cc, "state": state, "registrationId": None, "uses": []}
            cells.append(cell)
        # « Différent » = comparaison des seuls pays qui ont une valeur : un pays sans usage extrait n'est pas une différence
        doses_differ = len({tuple(v) for v in doses.values()}) > 1
        out_rows.append({
            "rowId": key, "cropNormalized": row["cropNormalized"], "eppoCropCode": row["eppoCropCode"],
            "targetNormalized": row["targetNormalized"], "eppoTargetCode": row["eppoTargetCode"],
            "cropGroup": row["cropGroup"], "targetGroup": row["targetGroup"],
            "alignedBy": row["alignedBy"], "differsAcrossCountries": doses_differ, "cells": cells})

    if not by_crop and len(countries) >= 2 and not any(sum(c["state"] == "present" for c in r["cells"]) >= 2 for r in out_rows):
        # Aucune ligne culture × cible commune : si une même culture existe dans 2 pays, proposer le niveau culture
        crops_by_country = {}
        for rid, use_list in uses.items():
            for use in use_list:
                crops_by_country.setdefault(regs_by_id[rid]["country_code"], set()).add(crop_key(use, lookup)[0])
        sets = list(crops_by_country.values())
        if any(a & b for i, a in enumerate(sets) for b in sets[i + 1:]):
            uses_warnings.append("Aucune ligne culture × cible n'est comparable entre ces pays : essayez granularity=crop "
                                 "(comparaison au niveau de la culture).")

    # registrations[] : 50 usages au plus par homologation (le détail complet est dans rows[].cells[].uses)
    registrations = [registration_dict(r, uses.get(r["registration_id"], [])[:50]) for r in matched[:300]]
    warnings = coverage_warnings(coverage)
    warnings += unique([r["match_warning"] for r in matched if r.get("match_warning")], cap=10)
    if len(out_rows) > offset + limit:
        warnings.append(f"{len(out_rows)} lignes de comparaison : seules {limit} sont renvoyées (limit/offset).")
    warnings += uses_warnings
    if truncated or len(matched) > 300:
        warnings.append("Résultat tronqué (trop d'homologations) : ajoutez un filtre crop/target.")
    return {"productId": product_id, "countries": countries, "registrations": registrations,
            "rows": out_rows[offset:offset + limit], "coverage": coverage, "warnings": warnings,
            "granularity": granularity, "disclaimer": DISCLAIMER}


CSV_COLUMNS = ["productId", "countryCode", "coverageOutcome", "registrationId", "registrationNumber",
               "statusOriginal", "statusNormalized", "matchedName", "matchedOn", "useId", "cropOriginal",
               "cropNormalized", "eppoCropCode", "targetOriginal", "targetNormalized", "eppoTargetCode",
               "doseValue", "doseUnitOriginal", "doseUnitNormalized", "maxApplications", "applicationIntervalDays",
               "phiDays", "reiHours", "sourceId", "sourceRecordUrl", "collectedAt", "validationStatus", "isSynthetic"]


def comparison_csv(data):
    """Une ligne par pays x usage, avec les colonnes de preuve (pays sans résultat = une ligne vide + son état)."""
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    outcomes = {c["countryCode"]: c["outcome"] for c in data["coverage"]}
    with_regs = set()
    for reg in data["registrations"]:
        with_regs.add(reg["countryCode"])
        base = {"productId": data["productId"], "countryCode": reg["countryCode"], "coverageOutcome": "found",
                "registrationId": reg["registrationId"], "registrationNumber": reg["registrationNumber"],
                "statusOriginal": reg["statusOriginal"], "statusNormalized": reg["statusNormalized"],
                "matchedName": reg["matchedVia"]["matchedName"], "matchedOn": reg["matchedVia"]["matchedOn"],
                "sourceId": reg["evidence"]["sourceId"], "sourceRecordUrl": reg["evidence"]["sourceRecordUrl"],
                "collectedAt": reg["evidence"]["collectedAt"], "validationStatus": reg["evidence"]["validationStatus"],
                "isSynthetic": reg["isSynthetic"]}
        for use in reg["uses"] or [{}]:
            writer.writerow({**base, **use, "validationStatus": use.get("evidence", {}).get("validationStatus", base["validationStatus"])})
    for cc in data["countries"]:
        if cc not in with_regs:
            writer.writerow({"productId": data["productId"], "countryCode": cc, "coverageOutcome": outcomes.get(cc)})
    return out.getvalue()


# ---------------------------------------------------------------------------
# Produits soeurs (hypothèses)
# ---------------------------------------------------------------------------
def sister_candidates(product_id, include_synthetic):
    """GET /products/{id}/sisters : product_aliases + product_name_mapping, dédoublonné par nom."""
    syn = "" if include_synthetic else "AND NOT is_synthetic"
    # Produit, alias soeurs et noms du mapping : 3 requêtes indépendantes, lancées ensemble
    products, alias_rows, mapping_rows = query_many([
        ("SELECT product_id, commercial_name FROM products WHERE product_id = :p", {"p": product_id}),
        (f"""SELECT alias_id, alias_name, country_code, relationship_type, confidence, evidence, review_status
             FROM product_aliases WHERE product_id = :p
             AND relationship_type IN ('sister_product_candidate', 'confirmed_sister_product') {syn}""", {"p": product_id}),
        ("""SELECT mapping_id, name_variant, relationship_type, market_or_country, confidence_score,
                   confidence_status, evidence_summary, evidence_type, review_status
            FROM product_name_mapping
            WHERE product_id = :p AND relationship_type = ANY(CAST(:rels AS text[]))""",
         {"p": product_id, "rels": list(SISTER_RELATIONS_MAPPING)})])
    if not products:
        raise NotFound(product_id)
    own = products[0]["commercial_name"].strip().lower()
    pool = []   # candidats bruts, un par ligne de base

    for a in alias_rows:
        reason = re.match(r"^\[([a-z_]+)\]\s*(.*)$", a["evidence"] or "")   # "[same_active_entity] same species ...; computed from ..."
        pool.append({"id": a["alias_id"], "name": a["alias_name"], "market": a["country_code"],
                     "rel": a["relationship_type"], "score": a["confidence"], "cstatus": None,
                     "summary": a["evidence"], "etype": None, "review": a["review_status"],
                     "trait": reason.group(2).split(";")[0] if reason else None})
    for r in mapping_rows:
        pool.append({"id": r["mapping_id"], "name": r["name_variant"], "market": r["market_or_country"],
                     "rel": r["relationship_type"], "score": r["confidence_score"], "cstatus": r["confidence_status"],
                     "summary": r["evidence_summary"], "etype": r["evidence_type"], "review": r["review_status"], "trait": None})

    # Dédoublonnage par nom : on garde le candidat le plus fiable, on complète avec les autres
    rank_review = {"validated": 0, "confirmed": 0, "to_verify": 1, "rejected": 2}
    by_name = {}
    for c in pool:
        key = c["name"].strip().lower()
        if key == own:
            continue
        by_name.setdefault(key, []).append(c)
    chosen = []
    for group in by_name.values():
        group.sort(key=lambda c: (rank_review.get(c["review"], 1), -(c["score"] or 0)))
        best = dict(group[0])
        for other in group[1:]:
            for field in ("cstatus", "etype", "summary", "market"):
                best[field] = best[field] or other[field]
        best["traits"] = unique([c["trait"] for c in group if c["trait"]])
        chosen.append(best)
    chosen.sort(key=lambda c: (-(c["score"] or 0), c["name"]))

    # Fiches officielles qui portent ces noms (preuves à l'appui de l'hypothèse), 3 au plus par nom
    evidence_by_name, product_by_name = {}, {}
    if chosen:
        rows = query(f"""SELECT lower(p.commercial_name) AS name_key, p.product_id, r.registration_id, r.country_code,
                                r.source_id, r.source_record_url, r.collected_at, r.validation_status, r.is_synthetic
                         FROM registrations r JOIN products p ON p.product_id = r.product_id
                         WHERE lower(p.commercial_name) = ANY(CAST(:n AS text[])) {"" if include_synthetic else "AND NOT r.is_synthetic AND NOT p.is_synthetic"}
                         ORDER BY r.country_code, r.registration_id LIMIT 600""", {"n": list(by_name)})
        for r in rows:
            product_by_name.setdefault(r["name_key"], set()).add(r["product_id"])
            bucket = evidence_by_name.setdefault(r["name_key"], [])
            if len(bucket) < 3:
                bucket.append(build_evidence(f"registration:{r['registration_id']}", r))

    candidates = []
    for c in chosen:
        key = c["name"].strip().lower()
        owners = product_by_name.get(key, set())
        item = {
            "candidateId": c["id"], "productId": product_id, "candidateName": c["name"],
            "candidateProductId": next(iter(owners)) if len(owners) == 1 else None,
            "marketOrCountry": c["market"],
            "relationshipType": as_enum(c["rel"], m.AliasRelationshipType) or "sister_product_candidate",
            "sharedTraits": c["traits"], "confidenceScore": c["score"],
            "reviewStatus": as_enum(c["review"], m.ReviewStatus) or "to_verify",
            "evidenceSummary": c["summary"], "evidenceType": c["etype"],
            "evidence": evidence_by_name.get(key, []),
        }
        if as_enum(c["cstatus"], m.ConfidenceStatus):
            item["confidenceStatus"] = c["cstatus"]
        candidates.append(item)

    warnings = ["Hypothèses à confirmer : un produit sœur n'est jamais confirmé tant que reviewStatus n'est pas « validated »."]
    if not candidates:
        warnings.append("Aucun candidat connu. Cela ne prouve pas l'absence de produits sœurs.")
    return {"productId": product_id, "candidates": candidates, "warnings": warnings, "disclaimer": DISCLAIMER}


# ---------------------------------------------------------------------------
# Qualité des données (/issues)
# ---------------------------------------------------------------------------
ALL_ISSUE_TYPES = ["source_unavailable", "not_validated", "unmapped", "uncertain", "missing", "conflicting"]
NOT_VALIDATED = "('automatically_extracted', 'to_verify')"
# Colonnes communes à toutes les branches du UNION (même ordre partout)
ISSUE_COLS = ("issue_type, priority, entity_type, entity_id, field, detail, confidence, validation_status, "
              "source_id, source_record_url, collected_at, is_synthetic, country_code, product_id")


def issue_branches(wanted, scope):
    """Construit les SELECT du UNION ALL, un par règle de docs/openapi-changes.md."""
    reg_where = []
    if scope["rids"] is not None:
        reg_where.append("r.registration_id = ANY(CAST(:rids AS text[]))")
    if scope["cc"]:
        reg_where.append("r.country_code = :cc")
    if not scope["inc"]:
        reg_where.append("NOT r.is_synthetic")
    rw = "".join(f" AND {c}" for c in reg_where)
    uw = rw + ("" if scope["inc"] else " AND NOT u.is_synthetic")
    reg_cols = "r.source_id, r.source_record_url, r.collected_at, r.is_synthetic, r.country_code, r.product_id"
    nulls = "NULL::text, NULL::text, NULL::timestamptz, NULL::boolean"
    branches = []

    def reg_issue(kind, prio, field, detail, cond):
        branches.append(f"""SELECT '{kind}', '{prio}', 'registration', r.registration_id, '{field}', {detail}, NULL::numeric,
                                   r.validation_status, {reg_cols} FROM registrations r WHERE {cond}{rw}""")

    def use_issue(kind, prio, field, detail, cond):
        branches.append(f"""SELECT '{kind}', '{prio}', 'use', u.use_id, '{field}', {detail}, NULL::numeric,
                                   u.validation_status, {reg_cols}
                            FROM uses u JOIN registrations r ON r.registration_id = u.registration_id WHERE {cond}{uw}""")

    if "not_validated" in wanted:
        reg_issue("not_validated", "high", "validationStatus", "'validationStatus = ' || r.validation_status",
                  f"r.validation_status IN {NOT_VALIDATED}")
        use_issue("not_validated", "high", "validationStatus", "'validationStatus = ' || u.validation_status",
                  f"u.validation_status IN {NOT_VALIDATED}")
    if "unmapped" in wanted:
        use_issue("unmapped", "medium", "eppoCropCode", "'Culture « ' || u.crop_name_original || ' » sans code EPPO'",
                  "u.crop_name_original IS NOT NULL AND u.eppo_crop_code IS NULL")
        use_issue("unmapped", "medium", "eppoTargetCode", "'Cible « ' || u.target_name_original || ' » sans code EPPO'",
                  "u.target_name_original IS NOT NULL AND u.eppo_target_code IS NULL")
    if "missing" in wanted:
        for field, column in (("registrationNumber", "registration_number"), ("statusOriginal", "status_original"),
                              ("approvalDate", "approval_date"), ("expirationDate", "expiration_date")):
            reg_issue("missing", "low", field, "NULL::text", f"r.{column} IS NULL")
        use_issue("missing", "medium", "doseValue", "NULL::text", "u.dose_value IS NULL")
        use_issue("missing", "low", "cropOriginal", "NULL::text", "u.crop_name_original IS NULL")
        use_issue("missing", "low", "targetOriginal", "NULL::text", "u.target_name_original IS NULL")
    if "uncertain" in wanted:
        fe_where = "fe.confidence < 0.7"
        if scope["rids"] is not None:
            fe_where += " AND fe.entity_type = 'registration' AND fe.entity_id = ANY(CAST(:rids AS text[]))"
        if scope["cc"]:
            fe_where += (" AND fe.entity_type = 'registration' AND fe.entity_id IN "
                         "(SELECT registration_id FROM registrations WHERE country_code = :cc)")
        branches.append(f"""SELECT 'uncertain', 'low', fe.entity_type, fe.entity_id, fe.field_name,
                                   'AI confidence ' || fe.confidence, fe.confidence, fe.validation_status,
                                   {nulls}, NULL::text, NULL::text FROM field_evidence fe WHERE {fe_where}""")
        al_where = "a.confidence < 0.7" + ("" if scope["inc"] else " AND NOT a.is_synthetic")
        if scope["pid"]:
            al_where += " AND a.product_id = :pid"
        if scope["cc"]:
            al_where += " AND a.country_code = :cc"
        branches.append(f"""SELECT 'uncertain', 'medium', 'mapping', a.alias_id, 'confidence',
                                   a.alias_name || ' (' || a.relationship_type || ')', a.confidence, a.review_status,
                                   {nulls}, a.country_code, a.product_id FROM product_aliases a WHERE {al_where}""")
    if "conflicting" in wanted:
        # Même pays + même numéro, deux sources, deux statuts différents
        branches.append(f"""SELECT 'conflicting', 'high', 'registration', r.registration_id, 'statusNormalized',
                                   'Statut ' || r.status_normalized || ' (' || r.source_id || ') contredit par ' || o.source_id,
                                   NULL::numeric, r.validation_status, {reg_cols}
                            FROM registrations r JOIN registrations o ON o.country_code = r.country_code
                              AND o.registration_number = r.registration_number AND o.source_id <> r.source_id
                              AND o.status_normalized <> r.status_normalized
                            WHERE r.registration_number IS NOT NULL{rw}""")
    if "source_unavailable" in wanted and scope["bad_sources"]:
        branches.append(f"""SELECT 'source_unavailable', 'high', 'source', s.sid, 'collection',
                                   'La dernière collecte de ' || s.sid || ' a échoué', NULL::numeric, 'source_unavailable',
                                   {nulls}, NULL::text, NULL::text FROM unnest(CAST(:bad AS text[])) AS s(sid)""")
    return branches


def data_issues(product_id, country, issue_type, include_synthetic, limit, offset):
    """GET /issues : file de travail Regulatory Affairs."""
    scope = {"rids": None, "pid": product_id, "cc": country.upper() if country else None, "inc": include_synthetic}
    params = {}
    if product_id:
        ref, rows = load_reference(product_id)
        matched, _ = match_registrations(ref, build_profile(ref, rows), [scope["cc"]] if scope["cc"] else None, include_synthetic)
        scope["rids"] = [r["registration_id"] for r in matched] or ["-"]   # liste vide = aucun résultat
        params["rids"], params["pid"] = scope["rids"], product_id
    if scope["cc"]:
        params["cc"] = scope["cc"]
    bad = [sid for sid, s in sources_snapshot().items() if s["last_status"] in ("failed", "source_unavailable")]
    scope["bad_sources"] = bad
    params["bad"] = bad

    wanted = [issue_type] if issue_type else ALL_ISSUE_TYPES
    branches = issue_branches(wanted, scope)
    if not branches:
        return {"items": [], "countsByType": {}, "disclaimer": DISCLAIMER}
    union = "\nUNION ALL\n".join(f"({b})" for b in branches)
    # Les branches n'ont pas d'alias de colonnes : on les nomme ici
    named = f"SELECT * FROM ({union}) AS t({ISSUE_COLS})"
    counts, rows = query_many([
        (f"SELECT issue_type, count(*) AS n FROM ({union}) AS t({ISSUE_COLS}) GROUP BY issue_type", params),
        (f"""{named} ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
             issue_type, entity_id, field LIMIT :limit OFFSET :offset""", dict(params, limit=limit, offset=offset))])

    items = []
    for r in rows:
        item = {"issueId": f"{r['issue_type']}:{r['entity_type']}:{r['entity_id']}:{r['field']}",
                "issueType": r["issue_type"], "priority": r["priority"], "productId": r["product_id"],
                "countryCode": r["country_code"], "entityType": r["entity_type"], "entityId": r["entity_id"],
                "field": r["field"], "detail": r["detail"], "confidence": r["confidence"], "evidence": []}
        if as_enum(r["validation_status"], m.ValidationStatus):
            item["validationStatus"] = r["validation_status"]
        if r["source_id"] and r["entity_type"] in ("registration", "use"):
            item["evidence"] = [build_evidence(f"{r['entity_type']}:{r['entity_id']}", r, validation_status=r["validation_status"])]
        items.append(item)
    return {"items": items, "countsByType": {c["issue_type"]: c["n"] for c in counts}, "disclaimer": DISCLAIMER}


# ---------------------------------------------------------------------------
# Expirations et sources
# ---------------------------------------------------------------------------
def add_months(d, months):
    """Date + n mois (le jour est ramené à la fin du mois si besoin : 31 janv. + 1 mois = 28/29 févr.)."""
    year, month = divmod(d.month - 1 + months, 12)
    year, month = d.year + year, month + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def expirations(within_months, reference_date, country, crop, include_synthetic, limit, offset):
    """GET /expirations : homologations expirées, retirées ou qui expirent dans la fenêtre."""
    ref_date = reference_date or datetime.now(timezone.utc).date()
    limit_date = add_months(ref_date, within_months)
    conds = ["r.expiration_date IS NOT NULL",
             "(r.expiration_date <= :limit_date OR r.status_normalized IN ('expired', 'withdrawn'))"]
    params = {"limit_date": limit_date, "ref": ref_date, "limit": limit, "offset": offset}
    if country:
        conds.append("r.country_code = :cc")
        params["cc"] = country.upper()
    if not include_synthetic:
        conds.append("NOT r.is_synthetic AND NOT p.is_synthetic")
    if crop and crop.strip():
        code, like = resolve_eppo(crop, nz.normalize_crop)
        cond = "u.eppo_crop_code = :crop_code" if code else "(u.crop_name_original ILIKE :crop_like OR u.crop_name_normalized ILIKE :crop_like)"
        params["crop_code" if code else "crop_like"] = code or like
        conds.append(f"EXISTS (SELECT 1 FROM uses u WHERE u.registration_id = r.registration_id AND {cond})")
    rows = query(f"""SELECT r.registration_id, r.product_id, r.country_code, r.registration_number, r.status_normalized,
                            r.expiration_date, r.source_id, r.source_record_url, r.collected_at, r.validation_status,
                            r.is_synthetic, p.commercial_name
                     FROM registrations r JOIN products p ON p.product_id = r.product_id
                     WHERE {' AND '.join(conds)}
                     ORDER BY CASE WHEN r.expiration_date >= :ref THEN 0 ELSE 1 END,
                              CASE WHEN r.expiration_date >= :ref THEN r.expiration_date END ASC,
                              r.expiration_date DESC, r.registration_id
                     LIMIT :limit OFFSET :offset""", params)
    items = [{
        "registrationId": r["registration_id"], "productId": r["product_id"], "commercialName": r["commercial_name"],
        "countryCode": r["country_code"], "registrationNumber": r["registration_number"],
        "statusNormalized": as_enum(r["status_normalized"], m.RegistrationStatus) or "unknown",
        "expirationDate": r["expiration_date"], "daysUntilExpiration": (r["expiration_date"] - ref_date).days,
        "evidence": build_evidence(f"registration:{r['registration_id']}", r)} for r in rows]
    warnings = ["Seules les homologations dont la date d'expiration est renseignée sont listées : "
                "une date absente ne signifie pas qu'il n'y a pas d'échéance.",
                "Les dates négatives (daysUntilExpiration) sont des échéances déjà dépassées."]
    return {"referenceDate": ref_date, "withinMonths": within_months, "items": items,
            "warnings": warnings, "disclaimer": DISCLAIMER}


def list_sources():
    """GET /sources : sources officielles et fraîcheur (source_registry + collection_runs)."""
    items = []
    for sid, s in sources_snapshot().items():
        row = s["row"]
        availability = ("available" if s["last_status"] == "success" else
                        "unavailable" if s["last_status"] in ("failed", "source_unavailable") else "unknown")
        items.append({
            "sourceId": sid, "officialName": row["official_name"], "countryOrRegion": row["country_or_region"],
            "countryCodes": [s["country"]] if s["country"] else [], "baseUrl": row["base_url"],
            "accessMethod": row["access_method"], "dataFormat": row["data_format"], "licenseName": row["license_name"],
            "lastCollectedAt": s["last_success"], "isFrozenExtract": s["frozen"], "availability": availability,
            "recordCount": s["records"], "manualValidationRequired": row["manual_validation_required"]})
    return {"items": items}
