"""Calculs sur la base FICTIVE data/finance.db : simulations de crédit, prévisions de taux, projections d'épargne.

Chaque fonction renvoie un dict sérialisable en JSON. `to_text(result)` le met en forme pour le modèle de langage :
tous les chiffres que l'assistant peut citer y figurent déjà calculés (le modèle ne calcule rien lui-même).
"""
from __future__ import annotations

import math
import sqlite3
import threading
import unicodedata
from functools import lru_cache
from pathlib import Path

from .build_db import DB_PATH, build

DISCLAIMER = "Données fictives du prototype : estimation indicative, ce n'est pas une offre de prêt."
LEGAL_CREDIT = "Un crédit vous engage et doit être remboursé. Vérifiez vos capacités de remboursement avant de vous engager."
MAX_DEBT_RATIO = 35.0
DEFAULT_AGE = 35

_local = threading.local()


class FinanceError(ValueError):
    """Paramètre invalide : le message est présentable à l'utilisateur et au modèle."""


def _db(path: Path = DB_PATH) -> sqlite3.Connection:
    con = getattr(_local, "con", None)
    if con is None:
        if not path.exists():
            build(path)
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        con.row_factory = sqlite3.Row
        _local.con = con
    return con


def _q(sql: str, *args) -> list[sqlite3.Row]:
    return _db().execute(sql, args).fetchall()


@lru_cache(maxsize=1)
def meta() -> dict:
    return {r["cle"]: r["valeur"] for r in _q("SELECT cle, valeur FROM meta")}


def ref_month() -> str:
    return meta()["mois_reference"]


# --------------------------------------------------------------------------- formats français

def eur(x: float, dec: int = 0) -> str:
    s = f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")
    return f"{s} €"


def pct(x: float, dec: int = 2) -> str:
    return f"{x:.{dec}f}".replace(".", ",") + " %"


def years_label(years: float) -> str:
    y = round(years, 1)
    text = str(y).replace(".", ",").removesuffix(",0")
    return f"{text} an" if y < 2 else f"{text} ans"


def month_label(m: str) -> str:
    names = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
             "novembre", "décembre"]
    y, mo = m.split("-")
    return f"{names[int(mo) - 1]} {y}"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s).lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("'", " ").replace("’", " ").strip()


def _month_index(m: str) -> int:
    y, mo = m.split("-")
    return int(y) * 12 + int(mo) - 1


def _month_str(i: int) -> str:
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def _parse_month(value: str | None) -> str | None:
    """Accepte « 2027-03 », « 03/2027 », « 2027 » (janvier) ; None si vide."""
    if not value:
        return None
    v = str(value).strip()
    try:
        if len(v) == 4 and v.isdigit():
            return f"{v}-01"
        if "/" in v:
            mo, y = v.split("/")[-2:]
            return f"{int(y):04d}-{int(mo):02d}"
        y, mo = v.split("-")[:2]
        return f"{int(y):04d}-{int(mo):02d}"
    except ValueError:
        raise FinanceError(f"Date de début illisible : « {value} ». Format attendu : AAAA-MM.") from None


# --------------------------------------------------------------------------- séries et prévisions

SERIES_ALIASES = {
    "immo": "immo_20", "immobilier": "immo_20", "credit immobilier": "immo_20", "pret immobilier": "immo_20",
    "immo 15": "immo_15", "immo 20": "immo_20", "immo 25": "immo_25",
    "conso": "conso", "consommation": "conso", "pret personnel": "conso", "auto": "conso", "travaux": "conso",
    "livret a": "livret_a", "ldds": "livret_a", "lep": "lep", "pel": "pel", "cel": "cel",
    "livret jeune": "livret_jeune", "livret b": "livret_b", "compte a terme": "cat_12m", "cat": "cat_12m",
    "fonds euros": "fonds_euros", "assurance vie": "fonds_euros", "bce": "bce_depot", "taux directeur": "bce_depot",
    "euribor": "euribor_3m", "oat": "oat_10", "inflation": "inflation",
}


def _serie_code(name: str) -> str:
    codes = {r["code"] for r in _q("SELECT code FROM series")}
    if name in codes:
        return name
    n = _norm(name).replace("_", " ").replace("-", " ")
    if n in SERIES_ALIASES:
        return SERIES_ALIASES[n]
    for alias, code in sorted(SERIES_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in n:
            return code
    raise FinanceError(f"Série inconnue « {name} ». Séries disponibles : {', '.join(sorted(codes))}.")


def value_at(serie: str, month: str, scenario: str = "central") -> float:
    """Valeur d'une série à un mois donné : historique si passé, prévision du scénario sinon (bornée à la fin)."""
    ref = ref_month()
    if month <= ref:
        row = _q("SELECT valeur FROM observations WHERE serie=? AND scenario='reel' AND mois<=? ORDER BY mois DESC LIMIT 1",
                 serie, month)
        if not row:
            row = _q("SELECT valeur FROM observations WHERE serie=? AND scenario='reel' ORDER BY mois LIMIT 1", serie)
        return row[0]["valeur"]
    row = _q("SELECT valeur FROM observations WHERE serie=? AND scenario=? AND mois<=? ORDER BY mois DESC LIMIT 1",
             serie, scenario, month)
    return row[0]["valeur"]


def forecast(serie: str, horizon_mois: int = 24) -> dict:
    """Historique résumé (fin d'année, 5 dernières années) et prévisions par trimestre selon 3 scénarios."""
    code = _serie_code(serie)
    info = _q("SELECT * FROM series WHERE code=?", code)[0]
    ref = ref_month()
    last_year = int(ref[:4])
    history = [{"mois": f"{y}-12", "valeur": value_at(code, f"{y}-12")} for y in range(last_year - 5, last_year)]
    history.append({"mois": ref, "valeur": value_at(code, ref)})
    end = _q("SELECT MAX(mois) m FROM observations WHERE serie=? AND type='prevision'", code)[0]["m"]
    horizon = max(3, min(int(horizon_mois or 24), _month_index(end) - _month_index(ref)))
    points = []
    for k in range(3, horizon + 1, 3):
        m = _month_str(_month_index(ref) + k)
        points.append({"mois": m, **{sc: value_at(code, m, sc) for sc in ("bas", "central", "haut")}})
    if points[-1]["mois"] != _month_str(_month_index(ref) + horizon):
        m = _month_str(_month_index(ref) + horizon)
        points.append({"mois": m, **{sc: value_at(code, m, sc) for sc in ("bas", "central", "haut")}})
    return {"type": "prevision_taux", "serie": code, "libelle": info["libelle"], "description": info["description"],
            "unite": info["unite"], "mois_reference": ref, "valeur_actuelle": value_at(code, ref),
            "historique": history, "previsions": points, "methode": meta()["methode_previsions"]}


# --------------------------------------------------------------------------- crédit

PRODUCT_ALIASES = {
    "immo": "IMMO_FIXE", "immobilier": "IMMO_FIXE", "maison": "IMMO_FIXE", "appartement": "IMMO_FIXE",
    "logement": "IMMO_FIXE", "modulable": "IMMO_MODULABLE", "ptz": "PTZ", "taux zero": "PTZ",
    "pas": "PAS", "accession sociale": "PAS", "relais": "RELAIS", "eco ptz": "ECO_PTZ", "eco-ptz": "ECO_PTZ",
    "renovation energetique": "ECO_PTZ", "travaux": "TRAVAUX", "perso": "PERSO", "personnel": "PERSO",
    "consommation": "PERSO", "conso": "PERSO", "auto": "AUTO_NEUF", "voiture": "AUTO_NEUF", "vehicule": "AUTO_NEUF",
    "moto": "AUTO_NEUF", "occasion": "AUTO_OCCASION", "electrique": "AUTO_ELEC", "hybride": "AUTO_ELEC",
    "etudiant": "ETUDIANT", "etudes": "ETUDIANT", "renouvelable": "RENOUVELABLE", "revolving": "RENOUVELABLE",
}


def _product(code: str) -> sqlite3.Row:
    c = str(code or "").strip().upper().replace("-", "_").replace(" ", "_")
    rows = _q("SELECT * FROM produits_credit WHERE code=?", c)
    if not rows:
        n = _norm(code)
        for alias, target in sorted(PRODUCT_ALIASES.items(), key=lambda x: -len(x[0])):
            if alias in n:
                rows = _q("SELECT * FROM produits_credit WHERE code=?", target)
                break
    if not rows:
        codes = ", ".join(r["code"] for r in _q("SELECT code FROM produits_credit"))
        raise FinanceError(f"Produit de crédit inconnu « {code} ». Produits : {codes}.")
    return rows[0]


def _annuity(capital: float, annual_rate_pct: float, n: int) -> float:
    i = annual_rate_pct / 100 / 12
    return capital / n if i == 0 else capital * i / (1 - (1 + i) ** -n)


def _taeg(net_received: float, payment: float, n: int) -> float:
    """Taux annuel effectif global (méthode actuarielle) : taux mensuel r tel que la valeur actuelle des
    échéances égale la somme réellement reçue ; TAEG = (1 + r)^12 - 1."""
    if payment * n <= net_received:
        return 0.0
    lo, hi = 0.0, 0.05
    for _ in range(200):
        mid = (lo + hi) / 2
        pv = payment * (1 - (1 + mid) ** -n) / mid if mid else payment * n
        lo, hi = (mid, hi) if pv > net_received else (lo, mid)
    return ((1 + lo) ** 12 - 1) * 100


def _insurance_rate(age: int, smoker: bool) -> float:
    rows = _q("SELECT taux_annuel_pct FROM assurance_emprunteur WHERE ?>=age_min AND ?<=age_max AND fumeur=?",
              age, age, 1 if smoker else 0)
    if not rows:
        raise FinanceError("Âge hors des barèmes d'assurance (18 à 75 ans).")
    return rows[0]["taux_annuel_pct"]


def _profile(apport: float, montant: float, revenus: float | None, charges: float, payment: float) -> tuple[str, str]:
    if not revenus:
        return "standard", "profil standard (revenus non précisés)"
    ratio = (payment + charges) / revenus * 100
    if ratio > MAX_DEBT_RATIO:
        return "fragile", "profil fragile (endettement au-dessus de 35 %)"
    if ratio <= 30 and apport >= 0.10 * (montant + apport):
        return "excellent", "profil favorable (endettement sous 30 % et apport d'au moins 10 %)"
    return "standard", "profil standard"


def _grid_rate(product: str, n: int, profil: str) -> float:
    rows = _q("SELECT profil, taux_nominal FROM grille_taux_credit WHERE produit=? AND ?>=duree_min_mois AND ?<=duree_max_mois",
              product, n, n)
    rates = {r["profil"]: r["taux_nominal"] for r in rows}
    if not rates:
        raise FinanceError("Aucun taux pour cette durée.")
    return rates.get(profil, rates.get("standard"))


def simulate_loan(produit: str, montant: float, duree_mois: int, age: int | None = None, fumeur: bool = False,
                  apport: float = 0, revenus_mensuels: float | None = None, charges_mensuelles: float = 0,
                  debut: str | None = None) -> dict:
    p = _product(produit)
    try:
        montant, n = float(montant), int(round(float(duree_mois)))
        apport, charges = float(apport or 0), float(charges_mensuelles or 0)
        revenus = float(revenus_mensuels) if revenus_mensuels else None
    except (TypeError, ValueError):
        raise FinanceError("Montant, durée, apport, revenus et charges doivent être des nombres.") from None
    if not p["montant_min"] <= montant <= p["montant_max"]:
        raise FinanceError(f"{p['nom']} : montant entre {eur(p['montant_min'])} et {eur(p['montant_max'])}.")
    if not p["duree_min_mois"] <= n <= p["duree_max_mois"]:
        raise FinanceError(f"{p['nom']} : durée entre {p['duree_min_mois']} et {p['duree_max_mois']} mois.")
    hypotheses = []
    if age is None:
        age = DEFAULT_AGE
        hypotheses.append(f"emprunteur de {DEFAULT_AGE} ans non-fumeur (âge non précisé)")
    age = int(age)

    # Profil : d'abord estimé avec le taux standard, puis taux de la grille correspondante.
    base_std = _grid_rate(p["code"], n, "standard")
    profil, profil_txt = _profile(apport, montant, revenus, charges, _annuity(montant, base_std, n))
    base_rate = _grid_rate(p["code"], n, profil)

    ref = ref_month()
    start = _parse_month(debut) or _month_str(_month_index(ref) + 1)
    future = start > _month_str(_month_index(ref) + 1)
    serie = p["serie_reference"]

    ins_rate = _insurance_rate(age, bool(fumeur)) if p["assurance"] != "aucune" else 0.0
    ins_monthly = montant * ins_rate / 100 / 12
    ins_in_taeg = p["assurance"] == "obligatoire"
    fees = 0.0 if p["frais_dossier_pct"] == 0 else min(max(montant * p["frais_dossier_pct"] / 100, p["frais_dossier_min"]),
                                                         p["frais_dossier_max"])
    guarantee = montant * p["garantie_pct"] / 100
    usure = _q("SELECT * FROM taux_usure WHERE categorie=?", p["usure"])[0]

    def compute(rate: float) -> dict:
        rate = max(0.0, round(rate, 2))
        pay = _annuity(montant, rate, n)
        if p["code"] == "RELAIS":  # intérêts seuls, capital remboursé à la vente
            pay = montant * rate / 100 / 12
            interest = pay * n
        else:
            interest = pay * n - montant
        total_pay = pay + (ins_monthly if ins_in_taeg else 0)
        cash = montant - fees - guarantee
        if p["code"] == "RELAIS":
            taeg = rate + (fees + guarantee) / montant * 100 * 12 / n + (ins_rate if ins_in_taeg else 0)
        else:
            taeg = _taeg(cash, total_pay, n)
        return {"taux_nominal": rate, "mensualite": pay, "mensualite_avec_assurance": pay + ins_monthly,
                "taeg": taeg, "cout_interets": interest, "cout_assurance": ins_monthly * n,
                "cout_total": interest + (ins_monthly * n if ins_in_taeg else 0) + fees + guarantee}

    scenarios = {}
    if future and serie:
        now = value_at(serie, ref)
        for sc in ("bas", "central", "haut"):
            scenarios[sc] = compute(base_rate + value_at(serie, start, sc) - now)
    else:
        scenarios["central"] = compute(base_rate)
    main = scenarios["central"]
    result = {
        "type": "simulation_credit", "produit": p["code"], "produit_nom": p["nom"], "montant": montant,
        "duree_mois": n, "duree_annees": n / 12, "debut": start, "debut_futur": future, "profil": profil,
        "profil_detail": profil_txt, "apport": apport, "age": age, "fumeur": bool(fumeur),
        "frais_dossier": fees, "garantie": guarantee, "assurance": p["assurance"], "assurance_taux_annuel": ins_rate,
        "assurance_mensuelle": ins_monthly, "scenarios": scenarios, **main,
        "taux_usure": usure["taux_max_pct"], "au_dessus_usure": main["taeg"] > usure["taux_max_pct"],
        "conditions": p["conditions"], "hypotheses": hypotheses, "avertissement": DISCLAIMER,
        "mention_legale": LEGAL_CREDIT if p["categorie"] != "immobilier" else None,
    }
    if revenus:
        ratio = (main["mensualite_avec_assurance"] + charges) / revenus * 100
        result.update(revenus_mensuels=revenus, charges_mensuelles=charges, taux_endettement=ratio,
                      endettement_ok=ratio <= MAX_DEBT_RATIO)
    return result


def borrowing_capacity(revenus_mensuels: float, charges_mensuelles: float = 0, duree_mois: int = 300,
                       produit: str = "IMMO_FIXE", apport: float = 0, age: int | None = None) -> dict:
    p = _product(produit)
    try:
        revenus, charges = float(revenus_mensuels), float(charges_mensuelles or 0)
        n, apport = int(round(float(duree_mois))), float(apport or 0)
    except (TypeError, ValueError):
        raise FinanceError("Revenus, charges, durée et apport doivent être des nombres.") from None
    if revenus <= 0:
        raise FinanceError("Les revenus mensuels doivent être positifs.")
    n = min(max(n, p["duree_min_mois"]), p["duree_max_mois"])
    hypotheses = []
    if age is None:
        age = DEFAULT_AGE
        hypotheses.append(f"emprunteur de {DEFAULT_AGE} ans non-fumeur (âge non précisé)")
    budget = revenus * MAX_DEBT_RATIO / 100 - charges
    if budget <= 0:
        return {"type": "capacite_emprunt", "produit": p["code"], "produit_nom": p["nom"], "revenus_mensuels": revenus,
                "charges_mensuelles": charges, "mensualite_max": 0.0, "capital_max": 0.0, "duree_mois": n,
                "hypotheses": hypotheses, "avertissement": DISCLAIMER,
                "message": "Les charges actuelles dépassent déjà 35 % des revenus : pas de capacité d'emprunt supplémentaire."}
    profil = "excellent" if charges / revenus <= 0.05 and apport > 0 else "standard"
    rate = _grid_rate(p["code"], n, profil)
    ins = _insurance_rate(int(age), False) if p["assurance"] == "obligatoire" else 0.0
    factor = _annuity(1.0, rate, n) + ins / 100 / 12
    capital = min(budget / factor, p["montant_max"])
    capital = math.floor(capital / 100) * 100
    out = {"type": "capacite_emprunt", "produit": p["code"], "produit_nom": p["nom"], "revenus_mensuels": revenus,
           "charges_mensuelles": charges, "mensualite_max": budget, "duree_mois": n, "taux_nominal": rate,
           "assurance_taux_annuel": ins, "capital_max": capital, "apport": apport, "hypotheses": hypotheses,
           "avertissement": DISCLAIMER}
    if p["categorie"] == "immobilier":
        out["budget_achat_ancien"] = math.floor((capital + apport) / 1.08 / 100) * 100   # frais de notaire ≈ 8 %
        out["budget_achat_neuf"] = math.floor((capital + apport) / 1.025 / 100) * 100    # ≈ 2,5 % dans le neuf
    return out


# --------------------------------------------------------------------------- épargne

# Ordre de priorité : le plus précis d'abord (« assurance vie dynamique » avant « assurance vie »).
SAVINGS_ALIASES = [
    ("livret jeune", "LIVRET_JEUNE"), ("livret a", "LIVRET_A"), ("ldds", "LDDS"), ("lep", "LEP"),
    ("livret b", "LIVRET_B"), ("compte a terme", "CAT_12"), ("fonds euro", "AV_EUROS"), ("prudent", "AV_PRUDENT"),
    ("equilibre", "AV_EQUILIBRE"), ("dynamique", "AV_DYNAMIQUE"), ("assurance vie", "AV_EQUILIBRE"),
    ("retraite", "PER"), ("per", "PER"), ("pea", "PEA"), ("actions", "PEA"), ("bourse", "PEA"), ("cel", "CEL"),
    ("pel", "PEL"), ("cat", "CAT_12"),
]


def _saving(code: str) -> sqlite3.Row:
    c = str(code or "").strip().upper().replace("-", "_").replace(" ", "_")
    rows = _q("SELECT * FROM produits_epargne WHERE code=?", c)
    if not rows:
        n = _norm(code)
        words = f" {n} "
        for alias, target in SAVINGS_ALIASES:
            if f" {alias}" in words:
                rows = _q("SELECT * FROM produits_epargne WHERE code=?", target)
                break
    if not rows:
        codes = ", ".join(r["code"] for r in _q("SELECT code FROM produits_epargne"))
        raise FinanceError(f"Produit d'épargne inconnu « {code} ». Produits : {codes}.")
    return rows[0]


def current_rate(saving: sqlite3.Row) -> float | None:
    if saving["serie_taux"]:
        return value_at(saving["serie_taux"], ref_month())
    return saving["taux_fixe"]


def project_savings(produit: str, versement_initial: float = 0, versement_mensuel: float = 0,
                    duree_annees: float = 5) -> dict:
    s = _saving(produit)
    try:
        initial, monthly = float(versement_initial or 0), float(versement_mensuel or 0)
        years = float(duree_annees)
    except (TypeError, ValueError):
        raise FinanceError("Versements et durée doivent être des nombres.") from None
    if not 0 < years <= 40:
        raise FinanceError("Durée de projection entre 1 et 40 ans.")
    if initial < 0 or monthly < 0 or initial + monthly <= 0:
        raise FinanceError("Indiquez un versement initial ou mensuel positif.")
    n = int(round(years * 12))
    ref_i = _month_index(ref_month())
    plafond = s["plafond"]
    notes = []
    hyp = _q("SELECT * FROM hypotheses_rendement WHERE produit=?", s["code"])
    garanti = bool(s["garanti"])
    fixed_rate = s["code"] in ("PEL", "CAT_12")  # taux bloqué à l'ouverture

    scenarios = {}
    for sc in ("bas", "central", "haut"):
        balance, paid, gains, year_interest = 0.0, 0.0, 0.0, 0.0
        capped = False
        for k in range(n):
            deposit = (initial if k == 0 else 0) + monthly
            if plafond is not None and balance + deposit > plafond:
                deposit = max(0.0, plafond - balance)
                capped = True
            deposit_net = deposit * (1 - s["frais_entree_pct"] / 100)
            balance += deposit_net
            paid += deposit
            month = _month_str(ref_i + 1 + k)
            if garanti and s["serie_taux"]:
                rate = current_rate(s) if fixed_rate else value_at(s["serie_taux"], month, sc)
                rate -= s["frais_gestion_pct"] if s["famille"] == "assurance_vie" else 0
            elif garanti:
                rate = s["taux_fixe"] or 0.0
            else:
                h = hyp[0]
                rate = h["rendement_attendu_pct"] + {"bas": -0.5, "central": 0.0, "haut": 0.5}[sc] * h["volatilite_pct"]
                rate -= s["frais_gestion_pct"]
            interest = balance * rate / 100 / 12
            if garanti:
                year_interest += interest
                if (k + 1) % 12 == 0 or k == n - 1:   # intérêts versés une fois par an
                    balance += year_interest
                    gains += year_interest
                    year_interest = 0.0
            else:
                balance += interest
                gains += interest
        scenarios[sc] = {"capital_final": balance, "total_verse": paid, "gains": balance - paid,
                         "gains_nets_estimes": (balance - paid) * (1 - s["imposition_pct"] / 100) if balance > paid else balance - paid}
        if capped:
            notes.append(f"Plafond de {eur(plafond)} atteint : les versements au-delà ne sont pas possibles.")
    if not garanti:
        notes.append("Capital non garanti : la valeur peut baisser. Scénarios = rendement attendu plus ou moins la moitié de la volatilité.")
    elif s["serie_taux"] and not fixed_rate:
        notes.append("Le taux évolue selon les prévisions de la base (révisions en février et en août pour les livrets réglementés).")
    rendements = [dict(r) for r in _q("SELECT annee, rendement_pct FROM rendements_annuels WHERE produit=? ORDER BY annee",
                                      s["code"])]
    return {"type": "projection_epargne", "produit": s["code"], "produit_nom": s["nom"], "taux_actuel": current_rate(s),
            "versement_initial": initial, "versement_mensuel": monthly, "duree_annees": years, "plafond": plafond,
            "fiscalite": s["fiscalite"], "disponibilite": s["disponibilite"], "risque": s["risque"],
            "frais_entree_pct": s["frais_entree_pct"], "frais_gestion_pct": s["frais_gestion_pct"],
            "scenarios": {k: {kk: round(vv, 2) for kk, vv in v.items()} for k, v in scenarios.items()},
            "rendements_passes": rendements[-5:], "notes": list(dict.fromkeys(notes)), "avertissement": DISCLAIMER}


# --------------------------------------------------------------------------- catalogue

CATALOGUE_TOPICS = ("credits", "taux_credit", "epargne", "tarifs", "cartes", "offres", "delais", "usure", "assurance")


def catalogue(sujet: str, filtre: str | None = None) -> dict:
    t = _norm(sujet).replace(" ", "_")
    topic = next((x for x in CATALOGUE_TOPICS if x in t or t in x), None)
    if topic is None:
        raise FinanceError(f"Sujet inconnu « {sujet} ». Sujets : {', '.join(CATALOGUE_TOPICS)}.")
    f = _norm(filtre) if filtre else None

    def keep(*fields) -> bool:
        return not f or any(f in _norm(x or "") for x in fields)

    items: list[dict] = []
    if topic == "credits":
        for r in _q("SELECT * FROM produits_credit"):
            if keep(r["code"], r["nom"], r["categorie"], r["objet"]):
                rates = _q("SELECT MIN(taux_nominal) lo, MAX(taux_nominal) hi FROM grille_taux_credit WHERE produit=? AND profil!='fragile'",
                           r["code"])[0]
                items.append({"code": r["code"], "nom": r["nom"], "objet": r["objet"],
                              "montant": f"{eur(r['montant_min'])} à {eur(r['montant_max'])}",
                              "duree": f"{r['duree_min_mois']} à {r['duree_max_mois']} mois",
                              "taux_nominal": f"{pct(rates['lo'])} à {pct(rates['hi'])}", "assurance": r["assurance"],
                              "conditions": r["conditions"], "description": r["description"]})
    elif topic == "taux_credit":
        for r in _q("SELECT g.*, p.nom FROM grille_taux_credit g JOIN produits_credit p ON p.code=g.produit ORDER BY g.produit, g.duree_min_mois"):
            if keep(r["produit"], r["nom"]):
                items.append({"produit": r["nom"], "duree": f"{r['duree_min_mois']} à {r['duree_max_mois']} mois",
                              "profil": r["profil"], "taux_nominal": pct(r["taux_nominal"])})
    elif topic == "epargne":
        for r in _q("SELECT * FROM produits_epargne"):
            if keep(r["code"], r["nom"], r["famille"]):
                rate = current_rate(r)
                items.append({"code": r["code"], "nom": r["nom"],
                              "taux_actuel": pct(rate) if rate is not None else "variable (non garanti)",
                              "plafond": eur(r["plafond"]) if r["plafond"] else "aucun", "risque_sur_7": r["risque"],
                              "fiscalite": r["fiscalite"], "disponibilite": r["disponibilite"], "public": r["public"],
                              "description": r["description"]})
    elif topic == "tarifs":
        for r in _q("SELECT * FROM tarifs"):
            if keep(r["categorie"], r["service"]):
                prix = "gratuit" if r["prix"] == 0 else f"{str(r['prix']).replace('.', ',')} {r['unite']}"
                items.append({"categorie": r["categorie"], "service": r["service"], "prix": prix, "remarque": r["remarque"]})
    elif topic == "cartes":
        for r in _q("SELECT * FROM cartes"):
            if keep(r["code"], r["nom"]):
                items.append({"nom": r["nom"], "cotisation_annuelle": eur(r["cotisation_annuelle"]),
                              "plafond_paiement_30_jours": eur(r["plafond_paiement_30j"]),
                              "plafond_retrait_7_jours": eur(r["plafond_retrait_7j"]),
                              "retraits_gratuits_autres_banques_par_mois": r["retraits_gratuits_autres_banques_mois"],
                              "debit": r["debit"], "assurances": r["assurances"], "pour": r["revenus_conseilles"]})
    elif topic == "offres":
        for r in _q("SELECT o.*, c.nom carte FROM offres_compte o JOIN cartes c ON c.code=o.carte_incluse"):
            if keep(r["code"], r["nom"]):
                items.append({"nom": r["nom"], "cotisation_mensuelle": eur(r["cotisation_mensuelle"], 2),
                              "carte": r["carte"], "decouvert": r["decouvert_autorise"], "services": r["services"],
                              "pour": r["public"]})
    elif topic == "delais":
        for r in _q("SELECT * FROM delais"):
            if keep(r["sujet"], r["demarche"]):
                items.append({"sujet": r["sujet"], "demarche": r["demarche"], "delai": r["delai"], "remarque": r["remarque"]})
    elif topic == "usure":
        items = [{"categorie": r["libelle"], "taux_maximum": pct(r["taux_max_pct"]), "trimestre": r["trimestre"]}
                 for r in _q("SELECT * FROM taux_usure")]
    elif topic == "assurance":
        items = [{"age": f"{r['age_min']} à {r['age_max']} ans", "fumeur": "oui" if r["fumeur"] else "non",
                  "taux_annuel": pct(r["taux_annuel_pct"]) + " du capital emprunté"}
                 for r in _q("SELECT * FROM assurance_emprunteur ORDER BY age_min, fumeur")]
    return {"type": "catalogue", "sujet": topic, "filtre": filtre, "elements": items[:40],
            "avertissement": DISCLAIMER}


# --------------------------------------------------------------------------- mise en forme pour le modèle

def _scenario_lines(sc: dict, key: str, fmt) -> str:
    return " ; ".join(f"{name} {fmt(v[key])}" for name, v in sc.items())


def to_text(r: dict) -> str:
    """Texte compact transmis au modèle : chiffres déjà calculés et arrondis comme ils doivent être affichés."""
    kind = r.get("type")
    lines = []
    if kind == "simulation_credit":
        lines.append(f"Simulation {r['produit_nom']} : {eur(r['montant'])} sur {r['duree_mois']} mois "
                     f"({years_label(r['duree_annees'])}), début {month_label(r['debut'])}, {r['profil_detail']}.")
        lines.append(f"Taux nominal {pct(r['taux_nominal'])} ; mensualité hors assurance {eur(r['mensualite'], 2)} "
                     f"(environ {eur(r['mensualite'])}) ; avec assurance {eur(r['mensualite_avec_assurance'], 2)} "
                     f"(environ {eur(r['mensualite_avec_assurance'])}).")
        lines.append(f"TAEG {pct(r['taeg'])} ; coût des intérêts {eur(r['cout_interets'])} ; coût de l'assurance "
                     f"{eur(r['cout_assurance'])} ({r['assurance']}, {pct(r['assurance_taux_annuel'])} par an du capital) ; "
                     f"frais de dossier {eur(r['frais_dossier'])} ; garantie {eur(r['garantie'])} ; coût total du crédit {eur(r['cout_total'])}.")
        if r["debut_futur"]:
            sc = r["scenarios"]
            lines.append("Taux prévu au démarrage selon les scénarios : " + _scenario_lines(sc, "taux_nominal", pct) + ".")
            lines.append("Mensualité hors assurance selon les scénarios : " + _scenario_lines(sc, "mensualite", eur) + ".")
        if "taux_endettement" in r:
            lines.append(f"Taux d'endettement avec ce prêt : {pct(r['taux_endettement'], 1)} "
                         f"({'acceptable' if r['endettement_ok'] else 'au-dessus de la limite de 35 %'}).")
        if r["au_dessus_usure"]:
            lines.append(f"ATTENTION : TAEG au-dessus du taux d'usure ({pct(r['taux_usure'])}) : prêt impossible en l'état.")
        lines.append(f"Conditions : {r['conditions']}")
        if r["hypotheses"]:
            lines.append("Hypothèses : " + " ; ".join(r["hypotheses"]) + ".")
        if r["mention_legale"]:
            lines.append(f"Mention légale obligatoire, à reprendre mot pour mot : « {r['mention_legale']} »")
    elif kind == "capacite_emprunt":
        if r.get("message"):
            lines.append(r["message"])
        else:
            lines.append(f"Capacité d'emprunt ({r['produit_nom']}, {r['duree_mois']} mois, taux {pct(r['taux_nominal'])}, "
                         f"assurance {pct(r['assurance_taux_annuel'])}) : environ {eur(r['capital_max'])}.")
            lines.append(f"Mensualité maximale (35 % des revenus de {eur(r['revenus_mensuels'])} moins {eur(r['charges_mensuelles'])} "
                         f"de charges) : {eur(r['mensualite_max'])}.")
            if "budget_achat_ancien" in r:
                lines.append(f"Avec l'apport de {eur(r['apport'])} : budget d'achat d'environ {eur(r['budget_achat_ancien'])} "
                             f"dans l'ancien (frais de notaire d'environ 8 %) ou {eur(r['budget_achat_neuf'])} dans le neuf.")
        if r["hypotheses"]:
            lines.append("Hypothèses : " + " ; ".join(r["hypotheses"]) + ".")
    elif kind == "prevision_taux":
        u = r["unite"]
        f = (lambda v: pct(v)) if u == "%" else (lambda v: str(v))
        lines.append(f"{r['libelle']} : {f(r['valeur_actuelle'])} en {month_label(r['mois_reference'])}. {r['description']}")
        lines.append("Historique (fin d'année) : " + " ; ".join(f"{h['mois'][:4]} {f(h['valeur'])}" for h in r["historique"][:-1]) + ".")
        lines.append("Prévisions (bas / central / haut) : " + " ; ".join(
            f"{month_label(p['mois'])} {f(p['bas'])} / {f(p['central'])} / {f(p['haut'])}" for p in r["previsions"]) + ".")
        lines.append(f"Méthode : {r['methode']}")
    elif kind == "projection_epargne":
        rate = r["taux_actuel"]
        lines.append(f"Projection {r['produit_nom']} : versement initial {eur(r['versement_initial'])}, "
                     f"{eur(r['versement_mensuel'])} par mois pendant {years_label(r['duree_annees'])}"
                     + (f", taux actuel {pct(rate)}" if rate is not None else ", rendement non garanti") + ".")
        for name, v in r["scenarios"].items():
            lines.append(f"Scénario {name} : capital final {eur(v['capital_final'])}, total versé {eur(v['total_verse'])}, "
                         f"gains {eur(v['gains'])}, gains nets estimés {eur(v['gains_nets_estimes'])}.")
        lines.append(f"Fiscalité : {r['fiscalite']} Disponibilité : {r['disponibilite']} Risque {r['risque']} sur 7.")
        if r["frais_entree_pct"] or r["frais_gestion_pct"]:
            lines.append(f"Frais : {pct(r['frais_entree_pct'])} sur versements, {pct(r['frais_gestion_pct'])} par an de gestion.")
        if r["rendements_passes"]:
            lines.append("Rendements passés : " + " ; ".join(f"{x['annee']} {pct(x['rendement_pct'])}" for x in r["rendements_passes"]) + ".")
        lines.extend(r["notes"])
    elif kind == "catalogue":
        lines.append(f"Catalogue « {r['sujet']} »" + (f" filtré sur « {r['filtre']} »" if r["filtre"] else "") +
                     f" : {len(r['elements'])} élément(s).")
        for it in r["elements"]:
            lines.append("- " + " | ".join(f"{k} : {v}" for k, v in it.items()))
    lines.append(r.get("avertissement", DISCLAIMER))
    return "\n".join(lines)
