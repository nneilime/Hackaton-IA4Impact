"""Construit data/finance.db : base FICTIVE des flux financiers utilisés par l'assistant (prototype de hackathon).

Toutes les valeurs sont inventées mais plausibles (ordres de grandeur du marché français 2016-2026) :
elles ne constituent ni une offre ni une information officielle de la Caisse d'Épargne ou de BPCE.

  python -m finance.build_db            # reconstruit data/finance.db (déterministe)

Contenu :
  meta                  date de référence, avertissement
  series / observations taux de marché et taux réglementés, mensuels : historique 2016-01 → 2026-09,
                        prévisions 2026-10 → 2028-12 en trois scénarios (bas, central, haut)
  produits_credit       catalogue des crédits (montants, durées, frais, assurance)
  grille_taux_credit    taux nominaux actuels par produit, tranche de durée et profil d'emprunteur
  assurance_emprunteur  taux annuels par âge et tabagisme (en % du capital emprunté)
  taux_usure            seuils légaux (fictifs) par catégorie de crédit
  produits_epargne      livrets, épargne logement, comptes à terme, assurance vie, retraite, bourse
  rendements_annuels    rendements passés (2016-2025) des supports non garantis et des fonds euros
  hypotheses_rendement  rendement attendu et volatilité, pour les projections
  cartes, offres_compte, tarifs, delais
"""
from __future__ import annotations

import random
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "finance.db"

REF_MONTH = "2026-09"          # dernier mois d'historique
FORECAST_END = "2028-12"
SCENARIOS = ("bas", "central", "haut")


# --------------------------------------------------------------------------- outils de dates

def month_index(m: str) -> int:
    y, mo = m.split("-")
    return int(y) * 12 + int(mo) - 1


def month_str(i: int) -> str:
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def months(start: str, end: str) -> list[str]:
    return [month_str(i) for i in range(month_index(start), month_index(end) + 1)]


HISTORY = months("2016-01", REF_MONTH)
FUTURE = months(month_str(month_index(REF_MONTH) + 1), FORECAST_END)


def interpolate(anchors: dict[str, float], span: list[str]) -> dict[str, float]:
    """Interpolation linéaire entre des points d'ancrage (mois -> valeur)."""
    pts = sorted((month_index(k), v) for k, v in anchors.items())
    out = {}
    for m in span:
        i = month_index(m)
        if i <= pts[0][0]:
            out[m] = pts[0][1]
            continue
        if i >= pts[-1][0]:
            out[m] = pts[-1][1]
            continue
        for (i0, v0), (i1, v1) in zip(pts, pts[1:]):
            if i0 <= i <= i1:
                out[m] = v0 + (v1 - v0) * (i - i0) / (i1 - i0)
                break
    return out


def steps(changes: dict[str, float], span: list[str]) -> dict[str, float]:
    """Série en escalier : chaque valeur s'applique à partir de son mois."""
    pts = sorted((month_index(k), v) for k, v in changes.items())
    out, current = {}, pts[0][1]
    for m in span:
        for i, v in pts:
            if i == month_index(m):
                current = v
        out[m] = current
    return out


def noisy(series: dict[str, float], rng: random.Random, amp: float) -> dict[str, float]:
    return {m: v + rng.uniform(-amp, amp) for m, v in series.items()}


def r2(x: float) -> float:
    return round(x + 0.0, 2)


def round_to(x: float, step: float) -> float:
    return round(round(x / step) * step, 2)


# --------------------------------------------------------------------------- séries de taux

SERIES = [
    # code, libellé, unité, catégorie, description
    ("bce_depot", "Taux de dépôt de la BCE", "%", "marche", "Taux directeur de la Banque centrale européenne."),
    ("euribor_3m", "Euribor 3 mois", "%", "marche", "Taux auquel les banques se prêtent entre elles à 3 mois ; sert de base aux crédits à taux variable."),
    ("oat_10", "OAT 10 ans", "%", "marche", "Taux d'emprunt de l'État français à 10 ans ; principal moteur des taux immobiliers."),
    ("inflation", "Inflation en France (sur un an)", "%", "marche", "Hausse des prix à la consommation sur douze mois."),
    ("immo_15", "Taux moyen du crédit immobilier sur 15 ans", "%", "credit", "Taux nominal moyen observé sur le marché, hors assurance."),
    ("immo_20", "Taux moyen du crédit immobilier sur 20 ans", "%", "credit", "Taux nominal moyen observé sur le marché, hors assurance."),
    ("immo_25", "Taux moyen du crédit immobilier sur 25 ans", "%", "credit", "Taux nominal moyen observé sur le marché, hors assurance."),
    ("conso", "Taux moyen du prêt personnel (3 à 5 ans)", "%", "credit", "Taux nominal moyen des prêts à la consommation amortissables."),
    ("livret_a", "Taux du Livret A et du LDDS", "%", "epargne", "Taux réglementé, révisé en février et en août."),
    ("lep", "Taux du Livret d'épargne populaire (LEP)", "%", "epargne", "Taux réglementé réservé aux revenus modestes."),
    ("cel", "Taux du Compte épargne logement (CEL)", "%", "epargne", "Environ deux tiers du taux du Livret A."),
    ("pel", "Taux des nouveaux Plans épargne logement (PEL)", "%", "epargne", "Taux fixé à l'ouverture pour toute la durée du plan."),
    ("livret_jeune", "Taux du Livret Jeune (Caisse d'Épargne, fictif)", "%", "epargne", "Livret des 12-25 ans ; taux au moins égal au Livret A."),
    ("livret_b", "Taux du Livret B (Caisse d'Épargne, fictif)", "%", "epargne", "Livret fiscalisé sans plafond légal."),
    ("cat_12m", "Taux du compte à terme 12 mois (fictif)", "%", "epargne", "Taux fixe garanti pour un placement bloqué un an."),
    ("fonds_euros", "Rendement moyen des fonds euros d'assurance vie", "%", "epargne", "Rendement annuel net de frais de gestion, avant prélèvements sociaux."),
]


def build_series(rng: random.Random) -> dict[str, dict[str, dict[str, float]]]:
    """Renvoie {serie: {'historique': {mois: v}, 'bas': {...}, 'central': {...}, 'haut': {...}}}."""
    H, F = HISTORY, FUTURE
    s: dict[str, dict[str, dict[str, float]]] = {}

    # --- BCE : escalier réaliste puis hypothèses de politique monétaire
    bce_h = steps({"2016-01": -0.30, "2016-03": -0.40, "2019-09": -0.50, "2022-07": 0.00, "2022-09": 0.75,
                   "2022-11": 1.50, "2022-12": 2.00, "2023-02": 2.50, "2023-03": 3.00, "2023-05": 3.25,
                   "2023-06": 3.50, "2023-08": 3.75, "2023-09": 4.00, "2024-06": 3.75, "2024-09": 3.50,
                   "2024-10": 3.25, "2024-12": 3.00, "2025-02": 2.75, "2025-03": 2.50, "2025-04": 2.25,
                   "2025-06": 2.00}, H)
    s["bce_depot"] = {"historique": bce_h,
                      "bas": steps({"2026-10": 2.00, "2026-12": 1.75, "2027-03": 1.50, "2027-09": 1.25}, F),
                      "central": steps({"2026-10": 2.00, "2027-06": 1.75}, F),
                      "haut": steps({"2026-10": 2.00, "2027-01": 2.25, "2027-09": 2.50}, F)}

    def euribor(bce: dict[str, float], amp: float) -> dict[str, float]:
        return {m: v + 0.08 + rng.uniform(-amp, amp) for m, v in bce.items()}
    s["euribor_3m"] = {"historique": euribor(bce_h, 0.06)}
    for sc in SCENARIOS:
        s["euribor_3m"][sc] = {m: v + 0.08 for m, v in s["bce_depot"][sc].items()}

    # --- OAT 10 ans
    oat_h = noisy(interpolate({"2016-01": 0.90, "2016-07": 0.20, "2017-01": 0.80, "2018-01": 0.80, "2019-01": 0.60,
                               "2019-08": -0.35, "2020-03": 0.00, "2020-12": -0.30, "2021-12": 0.20, "2022-06": 2.20,
                               "2022-12": 3.00, "2023-10": 3.50, "2023-12": 2.60, "2024-06": 3.20, "2024-12": 3.10,
                               "2025-06": 3.25, "2025-12": 3.45, "2026-09": 3.40}, H), rng, 0.07)
    oat_h[REF_MONTH] = 3.40
    s["oat_10"] = {"historique": oat_h,
                   "bas": interpolate({"2026-10": 3.35, "2027-12": 2.85, "2028-12": 2.60}, F),
                   "central": interpolate({"2026-10": 3.40, "2027-12": 3.30, "2028-12": 3.25}, F),
                   "haut": interpolate({"2026-10": 3.45, "2027-12": 3.90, "2028-12": 4.10}, F)}

    # --- Inflation
    infl_h = noisy(interpolate({"2016-01": 0.2, "2016-12": 0.6, "2017-06": 1.0, "2018-07": 2.3, "2018-12": 1.6,
                                "2019-12": 1.1, "2020-06": 0.2, "2020-12": 0.0, "2021-06": 1.5, "2021-12": 2.8,
                                "2022-06": 5.8, "2022-12": 5.9, "2023-02": 6.3, "2023-12": 3.7, "2024-06": 2.2,
                                "2024-12": 1.3, "2025-06": 0.9, "2025-12": 1.0, "2026-09": 1.3}, H), rng, 0.15)
    infl_h[REF_MONTH] = 1.3
    s["inflation"] = {"historique": infl_h,
                      "bas": interpolate({"2026-10": 1.2, "2027-12": 0.8, "2028-12": 1.0}, F),
                      "central": interpolate({"2026-10": 1.3, "2027-12": 1.6, "2028-12": 1.8}, F),
                      "haut": interpolate({"2026-10": 1.5, "2027-12": 2.6, "2028-12": 2.8}, F)}

    # --- Crédit immobilier : historique de marché, prévision déduite de l'OAT et de la BCE
    immo20_h = noisy(interpolate({"2016-01": 2.20, "2016-12": 1.45, "2017-12": 1.50, "2018-12": 1.45,
                                  "2019-12": 1.15, "2020-12": 1.15, "2021-12": 1.05, "2022-06": 1.60,
                                  "2022-12": 2.35, "2023-06": 3.60, "2023-12": 4.20, "2024-06": 3.70,
                                  "2024-12": 3.30, "2025-06": 3.10, "2025-12": 3.20, "2026-09": 3.25}, H), rng, 0.04)
    immo20_h[REF_MONTH] = 3.25
    immo20 = {"historique": immo20_h}
    for sc in SCENARIOS:
        immo20[sc] = {m: 3.25 + 0.8 * (s["oat_10"][sc][m] - 3.40) + 0.2 * (s["bce_depot"][sc][m] - 2.00) for m in F}
    s["immo_20"] = immo20
    s["immo_15"] = {k: {m: v - 0.15 for m, v in d.items()} for k, d in immo20.items()}
    s["immo_25"] = {k: {m: v + 0.15 for m, v in d.items()} for k, d in immo20.items()}

    conso_h = noisy(interpolate({"2016-01": 4.10, "2017-12": 3.70, "2019-12": 3.40, "2021-12": 3.20,
                                 "2022-12": 3.90, "2023-12": 6.00, "2024-12": 5.60, "2025-12": 5.40,
                                 "2026-09": 5.30}, H), rng, 0.06)
    conso_h[REF_MONTH] = 5.30
    s["conso"] = {"historique": conso_h}
    for sc in SCENARIOS:
        s["conso"][sc] = {m: 5.30 + 0.6 * (s["euribor_3m"][sc][m] - 2.08) for m in F}

    # --- Épargne réglementée : historique réel arrondi, prévisions par la formule de calcul du Livret A
    la_h = steps({"2016-01": 0.75, "2020-02": 0.50, "2022-02": 1.00, "2022-08": 2.00, "2023-02": 3.00,
                  "2025-02": 2.40, "2025-08": 1.70, "2026-02": 1.50}, H)
    lep_h = steps({"2016-01": 1.25, "2020-02": 1.00, "2022-02": 2.20, "2022-08": 4.60, "2023-02": 6.10,
                   "2023-08": 6.00, "2024-02": 5.00, "2024-08": 4.00, "2025-02": 3.50, "2025-08": 2.70,
                   "2026-02": 2.50}, H)
    pel_h = steps({"2016-01": 1.50, "2016-02": 1.00, "2023-01": 2.00, "2024-01": 2.25, "2025-01": 1.75,
                   "2026-01": 2.00}, H)
    s["livret_a"], s["lep"], s["pel"] = {"historique": la_h}, {"historique": lep_h}, {"historique": pel_h}
    for sc in SCENARIOS:
        la, lep, current_la, current_lep = {}, {}, 1.50, 2.50
        for m in F:
            if m.endswith("-02") or m.endswith("-08"):
                # Formule du Livret A : moyenne de l'inflation et du taux interbancaire, arrondie au dixième, 0,5 % minimum
                estr = s["bce_depot"][sc][m] - 0.10
                current_la = max(0.5, round_to((s["inflation"][sc][m] + estr) / 2, 0.1))
                current_lep = max(current_la + 0.5, round_to(s["inflation"][sc][m], 0.1))
            la[m], lep[m] = current_la, current_lep
        s["livret_a"][sc], s["lep"][sc] = la, lep
        s["pel"][sc] = steps({"2026-10": 2.00, "2027-01": {"bas": 1.75, "central": 2.00, "haut": 2.25}[sc],
                              "2028-01": {"bas": 1.50, "central": 2.00, "haut": 2.50}[sc]}, F)
    for key in ["historique", *SCENARIOS]:
        la = s["livret_a"][key]
        s["cel"] = s.get("cel", {})
        s["cel"][key] = {m: max(0.25, round_to(v * 2 / 3, 0.25)) for m, v in la.items()}
        s["livret_jeune"] = s.get("livret_jeune", {})
        s["livret_jeune"][key] = {m: round_to(v + 0.25, 0.05) for m, v in la.items()}
        s["livret_b"] = s.get("livret_b", {})
        s["livret_b"][key] = {m: max(0.25, round_to(v * 0.5, 0.05)) for m, v in la.items()}
    s["cat_12m"] = {"historique": {m: max(0.05, round_to(v - 0.05, 0.05)) for m, v in s["euribor_3m"]["historique"].items()}}
    for sc in SCENARIOS:
        s["cat_12m"][sc] = {m: max(0.05, round_to(v - 0.05, 0.05)) for m, v in s["euribor_3m"][sc].items()}

    # Fonds euros : valeur annuelle, appliquée à chaque mois de l'année (servie en janvier de l'année suivante)
    fe_years = {2016: 1.90, 2017: 1.80, 2018: 1.80, 2019: 1.40, 2020: 1.30, 2021: 1.30, 2022: 2.00, 2023: 2.60,
                2024: 2.60, 2025: 2.50, 2026: 2.45}
    fe_fut = {"bas": {2026: 2.30, 2027: 2.00, 2028: 1.80}, "central": {2026: 2.45, 2027: 2.40, 2028: 2.35},
              "haut": {2026: 2.60, 2027: 2.90, 2028: 3.00}}
    s["fonds_euros"] = {"historique": {m: fe_years[int(m[:4])] for m in H}}
    for sc in SCENARIOS:
        s["fonds_euros"][sc] = {m: fe_fut[sc][int(m[:4])] for m in F}
    return s


# --------------------------------------------------------------------------- schéma

SCHEMA = """
CREATE TABLE meta (cle TEXT PRIMARY KEY, valeur TEXT NOT NULL);
CREATE TABLE series (code TEXT PRIMARY KEY, libelle TEXT NOT NULL, unite TEXT NOT NULL, categorie TEXT NOT NULL,
                     description TEXT NOT NULL);
CREATE TABLE observations (serie TEXT NOT NULL REFERENCES series(code), mois TEXT NOT NULL,
                           type TEXT NOT NULL CHECK (type IN ('historique', 'prevision')),
                           scenario TEXT NOT NULL CHECK (scenario IN ('reel', 'bas', 'central', 'haut')),
                           valeur REAL NOT NULL, PRIMARY KEY (serie, mois, scenario));
CREATE TABLE produits_credit (code TEXT PRIMARY KEY, nom TEXT NOT NULL, categorie TEXT NOT NULL, objet TEXT NOT NULL,
                              montant_min REAL NOT NULL, montant_max REAL NOT NULL,
                              duree_min_mois INTEGER NOT NULL, duree_max_mois INTEGER NOT NULL,
                              frais_dossier_pct REAL NOT NULL, frais_dossier_min REAL NOT NULL, frais_dossier_max REAL NOT NULL,
                              garantie_pct REAL NOT NULL, assurance TEXT NOT NULL CHECK (assurance IN ('obligatoire', 'facultative', 'aucune')),
                              serie_reference TEXT REFERENCES series(code), usure TEXT NOT NULL,
                              conditions TEXT NOT NULL, description TEXT NOT NULL);
CREATE TABLE grille_taux_credit (produit TEXT NOT NULL REFERENCES produits_credit(code),
                                 duree_min_mois INTEGER NOT NULL, duree_max_mois INTEGER NOT NULL,
                                 profil TEXT NOT NULL CHECK (profil IN ('excellent', 'standard', 'fragile')),
                                 taux_nominal REAL NOT NULL, date_effet TEXT NOT NULL,
                                 PRIMARY KEY (produit, duree_min_mois, profil));
CREATE TABLE assurance_emprunteur (age_min INTEGER NOT NULL, age_max INTEGER NOT NULL, fumeur INTEGER NOT NULL,
                                   taux_annuel_pct REAL NOT NULL, PRIMARY KEY (age_min, fumeur));
CREATE TABLE taux_usure (categorie TEXT PRIMARY KEY, libelle TEXT NOT NULL, taux_max_pct REAL NOT NULL, trimestre TEXT NOT NULL);
CREATE TABLE produits_epargne (code TEXT PRIMARY KEY, nom TEXT NOT NULL, famille TEXT NOT NULL,
                               serie_taux TEXT REFERENCES series(code), taux_fixe REAL, plafond REAL,
                               versement_min REAL NOT NULL, garanti INTEGER NOT NULL, risque INTEGER NOT NULL,
                               fiscalite TEXT NOT NULL, imposition_pct REAL NOT NULL, disponibilite TEXT NOT NULL,
                               public TEXT NOT NULL, frais_entree_pct REAL NOT NULL, frais_gestion_pct REAL NOT NULL,
                               duree_conseillee TEXT NOT NULL, description TEXT NOT NULL);
CREATE TABLE rendements_annuels (produit TEXT NOT NULL REFERENCES produits_epargne(code), annee INTEGER NOT NULL,
                                 rendement_pct REAL NOT NULL, PRIMARY KEY (produit, annee));
CREATE TABLE hypotheses_rendement (produit TEXT PRIMARY KEY REFERENCES produits_epargne(code),
                                   rendement_attendu_pct REAL NOT NULL, volatilite_pct REAL NOT NULL);
CREATE TABLE cartes (code TEXT PRIMARY KEY, nom TEXT NOT NULL, reseau TEXT NOT NULL, debit TEXT NOT NULL,
                     cotisation_annuelle REAL NOT NULL, plafond_paiement_30j REAL NOT NULL, plafond_retrait_7j REAL NOT NULL,
                     retraits_gratuits_autres_banques_mois INTEGER NOT NULL, assurances TEXT NOT NULL,
                     revenus_conseilles TEXT NOT NULL);
CREATE TABLE offres_compte (code TEXT PRIMARY KEY, nom TEXT NOT NULL, cotisation_mensuelle REAL NOT NULL,
                            carte_incluse TEXT NOT NULL REFERENCES cartes(code), decouvert_autorise TEXT NOT NULL,
                            services TEXT NOT NULL, public TEXT NOT NULL);
CREATE TABLE tarifs (id INTEGER PRIMARY KEY, categorie TEXT NOT NULL, service TEXT NOT NULL, prix REAL,
                     unite TEXT NOT NULL, remarque TEXT NOT NULL);
CREATE TABLE delais (id INTEGER PRIMARY KEY, sujet TEXT NOT NULL, demarche TEXT NOT NULL, delai TEXT NOT NULL,
                     remarque TEXT NOT NULL);
CREATE INDEX obs_serie ON observations (serie, type, scenario, mois);
"""


# --------------------------------------------------------------------------- données de référence

CREDITS = [
    # code, nom, catégorie, objet, mt_min, mt_max, d_min, d_max, frais %, frais min, frais max, garantie %, assurance,
    # série de référence, catégorie d'usure, conditions, description
    ("IMMO_FIXE", "Prêt immobilier à taux fixe", "immobilier", "Achat de résidence principale, secondaire ou locative",
     50000, 1500000, 84, 300, 1.0, 500, 1500, 1.0, "obligatoire", "immo_20", "immo_20_plus",
     "Taux d'endettement de 35 % au plus, assurance comprise ; durée de 25 ans au plus (27 ans avec différé pour le neuf) ; apport conseillé de 10 % pour couvrir les frais.",
     "Mensualités identiques pendant toute la durée : le taux ne bouge pas."),
    ("IMMO_MODULABLE", "Prêt immobilier modulable", "immobilier", "Achat immobilier avec mensualités ajustables",
     50000, 1000000, 84, 300, 1.0, 500, 1500, 1.0, "obligatoire", "immo_20", "immo_20_plus",
     "Mêmes conditions que le taux fixe ; modulation des mensualités de plus ou moins 30 % une fois par an après 12 mois.",
     "Taux fixe avec la possibilité d'augmenter, de baisser ou de reporter des mensualités."),
    ("PTZ", "Prêt à taux zéro (PTZ)", "immobilier", "Primo-accession, neuf ou ancien avec travaux selon la zone",
     5000, 100000, 120, 300, 0.0, 0, 0, 0.0, "obligatoire", None, "immo_20_plus",
     "Réservé aux primo-accédants sous plafond de revenus ; finance au plus 50 % du projet ; toujours complété par un autre prêt.",
     "Prêt sans intérêts aidé par l'État ; remboursement parfois différé selon les revenus."),
    ("PAS", "Prêt d'accession sociale (PAS)", "immobilier", "Résidence principale sous plafond de revenus",
     30000, 400000, 84, 300, 0.5, 300, 500, 1.0, "obligatoire", "immo_20", "immo_20_plus",
     "Plafonds de revenus ; frais de dossier réduits ; ouvre droit à l'APL accession.",
     "Prêt immobilier conventionné à taux plafonné."),
    ("RELAIS", "Prêt relais", "immobilier", "Acheter avant d'avoir vendu son logement actuel",
     30000, 800000, 12, 24, 0.5, 300, 800, 0.0, "obligatoire", "immo_20", "immo_20_plus",
     "Finance jusqu'à 70 % de la valeur estimée du bien à vendre ; intérêts seuls chaque mois, capital remboursé à la vente.",
     "Avance sur le prix de vente du logement actuel."),
    ("ECO_PTZ", "Éco-prêt à taux zéro", "travaux", "Travaux de rénovation énergétique",
     7000, 50000, 36, 240, 0.0, 0, 0, 0.0, "facultative", None, "conso_plus_6000",
     "Logement achevé depuis plus de 2 ans, résidence principale ; travaux réalisés par un artisan RGE.",
     "Financement sans intérêts de l'isolation, du chauffage ou de la rénovation globale."),
    ("TRAVAUX", "Prêt travaux", "travaux", "Rénovation, aménagement, agrandissement",
     1500, 75000, 12, 120, 1.0, 0, 150, 0.0, "facultative", "conso", "conso_plus_6000",
     "Sans justificatif jusqu'à 21 500 € ; devis demandés au-delà.",
     "Prêt amortissable à mensualités fixes pour vos travaux."),
    ("PERSO", "Prêt personnel", "consommation", "Tout projet sans justificatif",
     1000, 75000, 12, 84, 1.0, 0, 150, 0.0, "facultative", "conso", "conso_plus_6000",
     "Sans justificatif d'utilisation ; délai de rétractation de 14 jours.",
     "Somme fixe remboursée par mensualités identiques."),
    ("AUTO_NEUF", "Prêt auto neuf", "consommation", "Voiture ou moto neuve",
     3000, 75000, 12, 84, 1.0, 0, 150, 0.0, "facultative", "conso", "conso_plus_6000",
     "Bon de commande demandé ; financement jusqu'à 100 % du prix.",
     "Prêt affecté : s'il n'y a pas de vente, le crédit est annulé."),
    ("AUTO_OCCASION", "Prêt auto d'occasion", "consommation", "Véhicule de moins de 8 ans",
     3000, 50000, 12, 72, 1.0, 0, 150, 0.0, "facultative", "conso", "conso_plus_6000",
     "Véhicule de moins de 8 ans ; facture ou certificat de cession demandé.",
     "Prêt affecté à l'achat d'un véhicule d'occasion."),
    ("AUTO_ELEC", "Prêt véhicule propre", "consommation", "Véhicule électrique ou hybride rechargeable",
     3000, 75000, 12, 84, 0.5, 0, 75, 0.0, "facultative", "conso", "conso_plus_6000",
     "Véhicule électrique ou hybride rechargeable, neuf ou d'occasion ; vélo électrique dès 1 000 €.",
     "Taux réduit pour encourager la mobilité moins polluante."),
    ("ETUDIANT", "Prêt étudiant", "consommation", "Études supérieures",
     1000, 75000, 12, 120, 0.0, 0, 0, 0.0, "facultative", None, "conso_plus_6000",
     "Étudiants de 18 à 28 ans ; différé total ou partiel possible pendant les études ; garant souvent demandé.",
     "Financer ses études et ne commencer à rembourser qu'à la fin."),
    ("RENOUVELABLE", "Crédit renouvelable", "consommation", "Réserve d'argent disponible",
     500, 6000, 12, 60, 0.0, 0, 0, 0.0, "facultative", None, "conso_moins_6000",
     "Réserve qui se reconstitue à mesure des remboursements ; coût élevé : à réserver aux petits besoins ponctuels.",
     "Réserve d'argent utilisable à tout moment, remboursée par petites mensualités."),
]

TAUX_USURE = [
    ("immo_moins_10", "Prêt immobilier de moins de 10 ans", 4.95, "2026-T4"),
    ("immo_10_20", "Prêt immobilier de 10 à 20 ans", 5.20, "2026-T4"),
    ("immo_20_plus", "Prêt immobilier de 20 ans et plus", 5.35, "2026-T4"),
    ("conso_moins_3000", "Crédit à la consommation jusqu'à 3 000 €", 22.00, "2026-T4"),
    ("conso_moins_6000", "Crédit à la consommation de 3 000 à 6 000 €", 15.40, "2026-T4"),
    ("conso_plus_6000", "Crédit à la consommation de plus de 6 000 €", 8.85, "2026-T4"),
]

ASSURANCE = [  # âge min, âge max, taux non-fumeur, taux fumeur (% annuel du capital emprunté)
    (18, 29, 0.10, 0.18), (30, 39, 0.15, 0.27), (40, 49, 0.25, 0.45), (50, 59, 0.40, 0.70), (60, 75, 0.65, 1.10),
]

PROFILS = {"excellent": -0.25, "standard": 0.0, "fragile": 0.40}


def credit_grid(series) -> list[tuple]:
    """Grille actuelle (date d'effet = mois suivant la référence) construite autour des taux de marché."""
    ref = REF_MONTH
    immo = {15: series["immo_15"]["historique"][ref], 20: series["immo_20"]["historique"][ref],
            25: series["immo_25"]["historique"][ref]}
    effet = month_str(month_index(REF_MONTH) + 1) + "-01"
    rows = []

    def add(produit, buckets, profils=PROFILS):
        for (dmin, dmax), base in buckets:
            for profil, delta in profils.items():
                rows.append((produit, dmin, dmax, profil, r2(max(0.0, base + delta)), effet))

    immo_buckets = [((84, 120), immo[15] - 0.20), ((121, 180), immo[15] - 0.05), ((181, 240), immo[20] - 0.05),
                    ((241, 300), immo[25] - 0.05)]
    add("IMMO_FIXE", immo_buckets)
    add("IMMO_MODULABLE", [(b, v + 0.10) for b, v in immo_buckets])
    add("PAS", [(b, v - 0.10) for b, v in immo_buckets])
    add("PTZ", [((120, 300), 0.0)], {"standard": 0.0})
    add("RELAIS", [((12, 24), immo[20] + 0.45)])
    add("ECO_PTZ", [((36, 240), 0.0)], {"standard": 0.0})
    conso = series["conso"]["historique"][ref]  # 5,30 %
    add("PERSO", [((12, 36), conso - 0.40), ((37, 60), conso + 0.10), ((61, 84), conso + 0.60)],
        {"excellent": -0.40, "standard": 0.0, "fragile": 1.20})
    add("TRAVAUX", [((12, 36), conso - 0.60), ((37, 60), conso - 0.20), ((61, 120), conso + 0.30)],
        {"excellent": -0.40, "standard": 0.0, "fragile": 1.20})
    add("AUTO_NEUF", [((12, 36), conso - 0.80), ((37, 60), conso - 0.40), ((61, 84), conso + 0.10)],
        {"excellent": -0.40, "standard": 0.0, "fragile": 1.20})
    add("AUTO_OCCASION", [((12, 36), conso - 0.40), ((37, 60), conso + 0.10), ((61, 72), conso + 0.60)],
        {"excellent": -0.40, "standard": 0.0, "fragile": 1.20})
    add("AUTO_ELEC", [((12, 36), conso - 1.40), ((37, 60), conso - 1.10), ((61, 84), conso - 0.70)],
        {"excellent": -0.30, "standard": 0.0, "fragile": 1.00})
    add("ETUDIANT", [((12, 60), 1.90), ((61, 120), 2.40)], {"excellent": -0.20, "standard": 0.0, "fragile": 0.50})
    add("RENOUVELABLE", [((12, 60), 14.90)], {"standard": 0.0})
    return rows


EPARGNE = [
    # code, nom, famille, série, taux fixe, plafond, versement min, garanti, risque (1-7), fiscalité, imposition %,
    # disponibilité, public, frais entrée %, frais gestion %, durée conseillée, description
    ("LIVRET_A", "Livret A", "livret_reglemente", "livret_a", None, 22950, 10, 1, 1,
     "Intérêts exonérés d'impôt et de prélèvements sociaux.", 0.0, "Argent disponible à tout moment.",
     "Tout le monde, un seul par personne.", 0, 0, "Épargne de précaution",
     "L'épargne de précaution de référence : sans risque, sans frais, disponible."),
    ("LDDS", "Livret de développement durable et solidaire (LDDS)", "livret_reglemente", "livret_a", None, 12000, 10, 1, 1,
     "Intérêts exonérés d'impôt et de prélèvements sociaux.", 0.0, "Argent disponible à tout moment.",
     "Majeurs domiciliés en France, un seul par personne.", 0, 0, "Épargne de précaution",
     "Même taux que le Livret A ; finance la transition énergétique et l'économie solidaire."),
    ("LEP", "Livret d'épargne populaire (LEP)", "livret_reglemente", "lep", None, 10000, 30, 1, 1,
     "Intérêts exonérés d'impôt et de prélèvements sociaux.", 0.0, "Argent disponible à tout moment.",
     "Revenu fiscal de référence sous un plafond (environ 22 800 € pour une personne seule).", 0, 0,
     "Épargne de précaution", "Le livret réglementé le mieux rémunéré, réservé aux revenus modestes."),
    ("LIVRET_JEUNE", "Livret Jeune", "livret_reglemente", "livret_jeune", None, 1600, 10, 1, 1,
     "Intérêts exonérés d'impôt et de prélèvements sociaux.", 0.0, "Argent disponible à tout moment.",
     "Jeunes de 12 à 25 ans.", 0, 0, "Premières économies", "Un livret pour apprendre à épargner, mieux rémunéré que le Livret A."),
    ("LIVRET_B", "Livret B", "livret_bancaire", "livret_b", None, None, 10, 1, 1,
     "Intérêts soumis au prélèvement forfaitaire unique de 30 %.", 30.0, "Argent disponible à tout moment.",
     "Tout le monde.", 0, 0, "Épargne de précaution au-delà des plafonds",
     "Livret sans plafond, utile quand le Livret A et le LDDS sont pleins."),
    ("CEL", "Compte épargne logement (CEL)", "epargne_logement", "cel", None, 15300, 300, 1, 1,
     "Intérêts soumis au prélèvement forfaitaire unique de 30 %.", 30.0, "Argent disponible ; retrait total = clôture.",
     "Tout le monde, un seul par personne.", 0, 0, "Projet immobilier à moyen terme",
     "Livret d'épargne qui ouvre droit à un prêt immobilier."),
    ("PEL", "Plan épargne logement (PEL)", "epargne_logement", "pel", None, 61200, 225, 1, 1,
     "Intérêts soumis au prélèvement forfaitaire unique de 30 % dès la première année.", 30.0,
     "Argent bloqué au moins 4 ans pour garder le taux ; retrait = clôture.",
     "Tout le monde ; versements de 540 € par an au moins.", 0, 0, "4 à 10 ans",
     "Taux garanti dès l'ouverture pour toute la durée du plan ; versements réguliers obligatoires."),
    ("CAT_12", "Compte à terme 12 mois", "compte_a_terme", "cat_12m", None, None, 1000, 1, 1,
     "Intérêts soumis au prélèvement forfaitaire unique de 30 %.", 30.0,
     "Argent bloqué 12 mois ; sortie anticipée possible avec un taux réduit.", "Tout le monde.", 0, 0, "1 an",
     "Placement à taux fixe garanti, connu à l'avance."),
    ("AV_EUROS", "Assurance vie, fonds euros", "assurance_vie", "fonds_euros", None, None, 50, 1, 1,
     "Prélèvements sociaux de 17,2 % chaque année ; impôt réduit sur les gains après 8 ans (abattement de 4 600 € pour une personne seule).",
     17.2, "Rachat possible à tout moment, en général sous un mois.", "Tout le monde.", 2.0, 0.75, "8 ans et plus",
     "Capital garanti ; rendement fixé chaque année par l'assureur."),
    ("AV_PRUDENT", "Assurance vie, gestion pilotée prudente", "assurance_vie", None, None, None, 50, 0, 3,
     "Gains imposés seulement au rachat ; fiscalité réduite après 8 ans.", 17.2, "Rachat possible, valeur variable.",
     "Tout le monde.", 2.0, 0.85, "5 ans et plus", "Environ 70 % de fonds euros et d'obligations, 30 % d'actions."),
    ("AV_EQUILIBRE", "Assurance vie, gestion pilotée équilibrée", "assurance_vie", None, None, None, 50, 0, 4,
     "Gains imposés seulement au rachat ; fiscalité réduite après 8 ans.", 17.2, "Rachat possible, valeur variable.",
     "Tout le monde.", 2.0, 0.95, "8 ans et plus", "Environ moitié actions, moitié supports plus sûrs."),
    ("AV_DYNAMIQUE", "Assurance vie, gestion pilotée dynamique", "assurance_vie", None, None, None, 50, 0, 5,
     "Gains imposés seulement au rachat ; fiscalité réduite après 8 ans.", 17.2, "Rachat possible, valeur variable.",
     "Tout le monde.", 2.0, 1.00, "10 ans et plus", "Majorité d'actions : plus de potentiel, plus de variations."),
    ("PER", "Plan d'épargne retraite (PER), gestion pilotée", "retraite", None, None, None, 50, 0, 4,
     "Versements déductibles du revenu imposable (dans une limite) ; argent imposé à la sortie.", 0.0,
     "Bloqué jusqu'à la retraite, sauf achat de la résidence principale et accidents de la vie.", "Tout le monde.",
     2.0, 0.90, "Jusqu'à la retraite", "Épargne retraite : moins d'impôt aujourd'hui, capital ou rente à la retraite."),
    ("PEA", "Plan d'épargne en actions (PEA)", "bourse", None, None, 150000, 10, 0, 6,
     "Gains exonérés d'impôt après 5 ans (prélèvements sociaux de 17,2 % dus).", 17.2,
     "Retrait avant 5 ans = clôture du plan.", "Majeurs domiciliés en France, un seul par personne.", 0, 0.50,
     "5 ans et plus", "Investir en actions européennes avec une fiscalité avantageuse."),
]

RENDEMENTS = {  # 2016 → 2025
    "AV_PRUDENT": [2.0, 2.5, -4.0, 7.0, 1.5, 4.0, -9.0, 6.5, 4.5, 3.5],
    "AV_EQUILIBRE": [3.5, 5.5, -7.5, 13.0, 2.5, 10.0, -11.0, 9.5, 7.5, 6.0],
    "AV_DYNAMIQUE": [5.0, 9.0, -11.0, 20.0, 4.0, 17.0, -14.0, 13.0, 11.0, 8.5],
    "PER": [3.0, 5.0, -7.0, 12.5, 2.5, 9.5, -10.5, 9.0, 7.0, 5.5],
    "PEA": [5.5, 10.5, -12.5, 24.0, -5.0, 23.0, -9.5, 15.0, 6.5, 9.0],
    "AV_EUROS": [1.90, 1.80, 1.80, 1.40, 1.30, 1.30, 2.00, 2.60, 2.60, 2.50],
}

HYPOTHESES = [("AV_EUROS", 2.40, 0.3), ("AV_PRUDENT", 3.00, 4.0), ("AV_EQUILIBRE", 4.50, 9.0),
              ("AV_DYNAMIQUE", 6.00, 14.0), ("PER", 4.50, 9.0), ("PEA", 6.50, 17.0)]

CARTES = [
    ("SECURITE", "Carte à autorisation systématique", "Visa", "immédiat", 18.0, 1000, 300, 0,
     "Assistance et assurance de base.", "Tous publics, y compris mineurs et budgets serrés"),
    ("VISA_CLASSIC", "Visa Classic", "Visa", "immédiat ou différé", 48.0, 2500, 600, 3,
     "Assurance et assistance voyage de base, garantie des achats en ligne.", "Dès 1 200 € de revenus par mois"),
    ("VISA_PREMIER", "Visa Premier", "Visa", "immédiat ou différé", 138.0, 8000, 1500, 10,
     "Assurance voyage étendue, location de voiture, garantie neige et montagne, conciergerie.",
     "Dès 1 900 € de revenus par mois"),
    ("VISA_INFINITE", "Visa Infinite", "Visa", "différé", 330.0, 15000, 3000, 30,
     "Assurances haut de gamme, accès aux salons d'aéroport, conciergerie 24 h sur 24.", "Dès 6 000 € de revenus par mois"),
]

OFFRES = [
    ("INITIAL", "Initial", 3.00, "SECURITE", "Non", "Compte, carte à autorisation systématique, banque à distance, alertes SMS.",
     "Ceux qui veulent l'essentiel, sans risque de découvert"),
    ("CONFORT_CLASSIC", "Confort Classic", 8.90, "VISA_CLASSIC", "Oui, sur demande",
     "Carte Visa Classic, banque à distance, assurance des moyens de paiement, 3 retraits gratuits par mois dans les autres banques.",
     "Usage courant du quotidien"),
    ("CONFORT_PREMIER", "Confort Premier", 16.90, "VISA_PREMIER", "Oui, sur demande",
     "Carte Visa Premier, plafonds élevés, assurances voyage étendues, retraits gratuits partout, accompagnement personnalisé.",
     "Voyageurs et revenus plus élevés"),
    ("JEUNES", "Offre 18-25 ans", 1.00, "VISA_CLASSIC", "Oui, petit montant",
     "Carte Visa Classic, banque à distance, retraits gratuits dans toute la zone euro.", "Jeunes de 18 à 25 ans"),
    ("OCF", "Offre clientèle fragile", 3.00, "SECURITE", "Non",
     "Carte à autorisation systématique, 4 virements et 2 chèques de banque par mois, frais d'incident plafonnés.",
     "Clients en difficulté financière (offre réglementée)"),
]

TARIFS = [  # catégorie, service, prix (None = gratuit / variable), unité, remarque
    ("Compte", "Ouverture de compte", 0.0, "€", "Gratuit."),
    ("Compte", "Tenue de compte (hors offre groupée)", 2.50, "€ par mois", "Incluse dans les offres Confort."),
    ("Compte", "Clôture de compte", 0.0, "€", "Gratuit."),
    ("Compte", "Relevé de compte mensuel en ligne", 0.0, "€", "Gratuit."),
    ("Compte", "Relevé de compte papier", 1.50, "€ par mois", "Gratuit en version électronique."),
    ("Banque à distance", "Accès à l'espace client et à l'appli Banxo", 0.0, "€", "Gratuit."),
    ("Banque à distance", "Alertes SMS sur le solde", 2.40, "€ par mois", "Incluses dans les offres Confort."),
    ("Virements", "Virement SEPA en ligne", 0.0, "€", "Gratuit, arrive en général le jour ouvré suivant."),
    ("Virements", "Virement instantané en ligne", 0.0, "€", "Gratuit, arrive en 10 secondes, 24 h sur 24."),
    ("Virements", "Virement en agence", 4.00, "€", "Par virement."),
    ("Virements", "Virement international hors zone SEPA", 18.00, "€", "Plus frais du correspondant éventuels."),
    ("Virements", "Paiement Wero entre particuliers", 0.0, "€", "Gratuit."),
    ("Prélèvements", "Mise en place d'un prélèvement", 0.0, "€", "Gratuit."),
    ("Prélèvements", "Opposition sur un prélèvement", 0.0, "€", "Gratuit."),
    ("Cartes", "Opposition sur carte (perte, vol, fraude)", 0.0, "€", "Gratuit, 24 h sur 24."),
    ("Cartes", "Réédition du code confidentiel par courrier", 9.00, "€", "Gratuit si consulté dans l'appli Banxo."),
    ("Cartes", "Refabrication de carte avant échéance", 15.00, "€", "Gratuit après une opposition pour fraude."),
    ("Cartes", "Retrait dans un distributeur d'une autre banque (zone euro)", 1.00, "€ par retrait",
     "Au-delà des retraits gratuits inclus dans la carte."),
    ("Cartes", "Paiement par carte hors zone euro", 2.70, "% du montant", "Plus 0,30 € par paiement."),
    ("Cartes", "Retrait hors zone euro", 3.00, "€ + 2,70 %", "Par retrait."),
    ("Cartes", "Modification temporaire des plafonds", 0.0, "€", "Gratuit dans l'appli Banxo."),
    ("Chèques", "Chéquier", 0.0, "€", "Gratuit, envoi à domicile possible."),
    ("Chèques", "Chèque de banque", 12.00, "€", "Par chèque."),
    ("Chèques", "Opposition sur chèque", 15.00, "€", "Par opposition."),
    ("Incidents", "Commission d'intervention", 8.00, "€ par opération", "Plafonnée à 80 € par mois (20 € pour l'offre clientèle fragile)."),
    ("Incidents", "Lettre d'information pour compte débiteur", 15.00, "€", "Par lettre."),
    ("Incidents", "Rejet de prélèvement", 20.00, "€", "Plafonné au montant du prélèvement."),
    ("Incidents", "Rejet de chèque de 50 € ou moins", 30.00, "€", "Frais légaux plafonnés."),
    ("Incidents", "Rejet de chèque de plus de 50 €", 50.00, "€", "Frais légaux plafonnés."),
    ("Découvert", "Taux du découvert autorisé", 16.50, "% par an", "Taux annuel effectif global, appliqué seulement aux jours à découvert."),
    ("Découvert", "Taux du découvert non autorisé", 18.50, "% par an", "Dans la limite du taux d'usure."),
    ("Épargne", "Ouverture d'un livret", 0.0, "€", "Gratuit."),
    ("Épargne", "Transfert d'un PEL ou d'un PEA vers une autre banque", 120.00, "€", "PEA : 150 € au plus par la loi."),
    ("Crédit", "Frais de dossier du prêt immobilier", 1.00, "% du montant", "500 € au moins, 1 500 € au plus."),
    ("Crédit", "Frais de dossier du prêt personnel", 1.00, "% du montant", "150 € au plus."),
    ("Crédit", "Remboursement anticipé du prêt immobilier", 3.00, "% du capital remboursé",
     "Plafonné à 6 mois d'intérêts ; gratuit en cas de vente pour mutation, licenciement ou décès."),
    ("Crédit", "Remboursement anticipé d'un crédit à la consommation", 1.00, "% du capital remboursé",
     "0,5 % s'il reste moins d'un an ; gratuit sous 10 000 € remboursés sur 12 mois."),
    ("Réclamations", "Traitement d'une réclamation", 0.0, "€", "Gratuit."),
    ("Succession", "Frais de dossier succession", 1.00, "% des avoirs", "150 € au moins, 800 € au plus ; gratuit sous 5 910 €."),
]

DELAIS = [
    ("Réclamation", "Accusé de réception d'une réclamation", "10 jours ouvrables au plus", "Réponse sous 2 mois au plus."),
    ("Réclamation", "Réponse à une réclamation", "2 mois au plus", "15 jours ouvrables pour un service de paiement (carte, virement)."),
    ("Réclamation", "Saisine du médiateur", "Après réponse insatisfaisante ou 2 mois sans réponse", "Gratuit pour le client."),
    ("Fraude", "Remboursement d'une opération non autorisée signalée", "Au plus tard le jour ouvré suivant le signalement",
     "Sauf soupçon de fraude du client ou négligence grave."),
    ("Fraude", "Délai pour contester une opération non autorisée", "13 mois après le débit", "70 jours hors Espace économique européen."),
    ("Carte", "Nouvelle carte après opposition", "7 à 10 jours ouvrés", "Livrée à domicile ou en agence."),
    ("Carte", "Code confidentiel par courrier", "5 à 8 jours ouvrés", "Immédiat dans l'appli Banxo (accès rapide « Code CB »)."),
    ("Carte", "Hausse temporaire des plafonds", "Immédiat dans l'appli", "Valable 30 jours au plus."),
    ("Virement", "Virement SEPA classique", "1 jour ouvré", "Ordonné avant l'heure limite du jour."),
    ("Virement", "Virement instantané", "10 secondes", "24 h sur 24, 7 jours sur 7."),
    ("Virement", "Activation d'un nouveau bénéficiaire", "Immédiat avec Sécur'Pass", "Jusqu'à 72 heures avec un code SMS."),
    ("Compte", "Ouverture de compte en ligne", "Moins de 10 minutes de saisie", "Validation sous quelques jours après réception des justificatifs."),
    ("Compte", "Changement de banque (mobilité bancaire)", "22 jours ouvrés", "La banque d'arrivée s'occupe de tout."),
    ("Crédit immobilier", "Réponse de principe", "48 heures", "Après réception du dossier complet."),
    ("Crédit immobilier", "Délai de réflexion après réception de l'offre", "10 jours", "Obligation légale : l'offre ne peut pas être acceptée avant."),
    ("Crédit immobilier", "Déblocage des fonds", "Environ 45 à 60 jours après la demande", "Selon la date de signature chez le notaire."),
    ("Crédit consommation", "Délai de rétractation", "14 jours", "Après la signature du contrat."),
    ("Crédit consommation", "Mise à disposition des fonds", "8 jours", "Plus tôt sur demande expresse (à partir du 4e jour)."),
    ("Épargne", "Rachat sur assurance vie", "Moins d'un mois", "Deux mois au plus selon la loi."),
    ("Conseiller", "Rendez-vous avec un conseiller", "Sous 48 heures en général", "Par téléphone, en agence ou en visio."),
]


def build(path: Path = DB_PATH) -> Path:
    rng = random.Random(2026)
    series = build_series(rng)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    try:
        con.executescript(SCHEMA)
        con.executemany("INSERT INTO meta VALUES (?, ?)", [
            ("mois_reference", REF_MONTH),
            ("fin_previsions", FORECAST_END),
            ("avertissement", "Données FICTIVES générées pour un prototype de hackathon : ni offre, ni information "
                              "officielle de la Caisse d'Épargne ou de BPCE."),
            ("methode_previsions", "Trois scénarios (bas, central, haut) de taux BCE, OAT 10 ans et inflation. Taux "
                                   "immobiliers = taux actuel + 0,8 × variation de l'OAT + 0,2 × variation de la BCE. "
                                   "Livret A = moyenne de l'inflation et du taux interbancaire, arrondie au dixième, "
                                   "0,5 % minimum, révisée en février et en août."),
            ("generateur", "python -m finance.build_db"),
        ])
        con.executemany("INSERT INTO series VALUES (?, ?, ?, ?, ?)", SERIES)
        rows = []
        for code, *_ in SERIES:
            for m, v in series[code]["historique"].items():
                rows.append((code, m, "historique", "reel", r2(v)))
            for sc in SCENARIOS:
                for m, v in series[code][sc].items():
                    rows.append((code, m, "prevision", sc, r2(v)))
        con.executemany("INSERT INTO observations VALUES (?, ?, ?, ?, ?)", rows)
        con.executemany("INSERT INTO produits_credit VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", CREDITS)
        con.executemany("INSERT INTO grille_taux_credit VALUES (?, ?, ?, ?, ?, ?)", credit_grid(series))
        con.executemany("INSERT INTO assurance_emprunteur VALUES (?, ?, ?, ?)",
                        [(a, b, f, t) for a, b, nf, fu in ASSURANCE for f, t in ((0, nf), (1, fu))])
        con.executemany("INSERT INTO taux_usure VALUES (?, ?, ?, ?)", TAUX_USURE)
        con.executemany("INSERT INTO produits_epargne VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", EPARGNE)
        con.executemany("INSERT INTO rendements_annuels VALUES (?, ?, ?)",
                        [(p, 2016 + i, v) for p, vals in RENDEMENTS.items() for i, v in enumerate(vals)])
        con.executemany("INSERT INTO hypotheses_rendement VALUES (?, ?, ?)", HYPOTHESES)
        con.executemany("INSERT INTO cartes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", CARTES)
        con.executemany("INSERT INTO offres_compte VALUES (?, ?, ?, ?, ?, ?, ?)", OFFRES)
        con.executemany("INSERT INTO tarifs (categorie, service, prix, unite, remarque) VALUES (?, ?, ?, ?, ?)", TARIFS)
        con.executemany("INSERT INTO delais (sujet, demarche, delai, remarque) VALUES (?, ?, ?, ?)", DELAIS)
        con.commit()
    finally:
        con.close()
    tmp.replace(path)
    return path


if __name__ == "__main__":
    out = build()
    con = sqlite3.connect(out)
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for (t,) in
              con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")}
    con.close()
    print(f"{out.relative_to(ROOT)} : " + ", ".join(f"{t} {n}" for t, n in counts.items()))
