"""Cherche dans la vraie base (LECTURE SEULE) les meilleures comparaisons pour la démo et écrit docs/demo_cases.md.

Usage (racine du dépôt, venv activé, DATABASE_URL dans .env) :
    python scripts/find_demo_cases.py

Trois recherches :
  a) produits pilotes LPC + produits sœurs : lignes comparables par paire de pays, niveau use et niveau crop ;
  b) top 10 des couples (culture normalisée, cible normalisée) présents en FR ET DE, avec le plus de produits ;
  c) top 10 des cultures avec des produits retirés/expirés dans au moins un pays ;
  d) « Opportunité marché » : les 5 meilleurs couples culture × cible (usages chimiques actifs, peu ou pas de biologiques) par pays.
Aucun INSERT/UPDATE/DELETE : seulement des SELECT (via backend.app.db.query, connexion en lecture seule).
"""
import itertools
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")   # Windows : évite le plantage d'affichage
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from backend.app import opportunities, services  # noqa: E402
from backend.app.db import query  # noqa: E402

PILOTS = ["P-LPC-G46", "P-LPC-CONTANS", "P-LPC-M52"]
COUNTRIES = ["FR", "CA", "DE"]
MAX_SISTERS = 12   # on garde les sœurs/produits les plus proches : le but est de trouver des cas de démo, pas tout comparer


def comparable(rows):
    """Nombre de lignes avec une valeur dans au moins 2 pays."""
    return sum(1 for r in rows if sum(c["state"] == "present" for c in r["cells"]) >= 2)


def candidate_products():
    """Produits pilotes + produits sœurs (lien exact related_product_id, jamais par le nom) + produits PRESTOP."""
    sisters = query("""SELECT DISTINCT a.related_product_id AS pid, p.commercial_name
                       FROM product_aliases a JOIN products p ON p.product_id = a.related_product_id
                       WHERE a.related_product_id IS NOT NULL AND a.product_id = ANY(CAST(:p AS text[]))
                         AND NOT p.is_synthetic AND a.related_product_id <> ALL(CAST(:p AS text[]))""", {"p": PILOTS})
    prestop = query("""SELECT product_id AS pid, commercial_name FROM products
                       WHERE commercial_name ILIKE 'prestop%' AND NOT is_synthetic""")
    names = {r["product_id"]: r["commercial_name"] for r in query(
        "SELECT product_id, commercial_name FROM products WHERE product_id = ANY(CAST(:p AS text[]))", {"p": PILOTS})}
    found = {pid: (names.get(pid, pid), "pilote") for pid in PILOTS}
    for r in sisters:
        found.setdefault(r["pid"], (r["commercial_name"], "sœur (hypothèse)"))
    for r in prestop:
        found.setdefault(r["pid"], (r["commercial_name"], "PRESTOP"))
    return found


def part_a():
    results = []
    for pid, (name, kind) in list(candidate_products().items())[:MAX_SISTERS + len(PILOTS)]:
        for a, b in itertools.combinations(COUNTRIES, 2):
            try:
                n = {}
                for g in ("use", "crop"):
                    data = services.compare_uses(pid, [a, b], None, None, False, 1000, 0, g)
                    n[g] = comparable(data["rows"] or [])
            except Exception as exc:   # un produit sans homologation ne doit pas arrêter la recherche
                print(f"  ignoré {pid} {a},{b}: {exc}")
                continue
            results.append({"pid": pid, "name": name, "kind": kind, "pair": f"{a},{b}", "use": n["use"], "crop": n["crop"]})
    return sorted(results, key=lambda r: (-r["crop"], -r["use"]))


def part_b():
    return query("""
        WITH x AS (
          SELECT r.country_code, p.product_id, u.crop_name_normalized AS crop, u.target_name_normalized AS target
          FROM uses u JOIN registrations r ON r.registration_id = u.registration_id
                      JOIN products p ON p.product_id = r.product_id
          WHERE r.country_code IN ('FR','DE') AND NOT u.is_synthetic AND NOT r.is_synthetic
            AND u.crop_name_normalized IS NOT NULL AND u.target_name_normalized IS NOT NULL)
        SELECT crop, target,
               count(DISTINCT product_id) FILTER (WHERE country_code = 'FR') AS fr_products,
               count(DISTINCT product_id) FILTER (WHERE country_code = 'DE') AS de_products
        FROM x GROUP BY crop, target
        HAVING count(DISTINCT product_id) FILTER (WHERE country_code = 'FR') > 0
           AND count(DISTINCT product_id) FILTER (WHERE country_code = 'DE') > 0
        ORDER BY least(count(DISTINCT product_id) FILTER (WHERE country_code = 'FR'),
                       count(DISTINCT product_id) FILTER (WHERE country_code = 'DE')) DESC,
                 count(DISTINCT product_id) DESC
        LIMIT 10""")


def part_c():
    return query("""
        WITH x AS (
          SELECT DISTINCT u.crop_name_normalized AS crop, r.country_code, p.product_id, r.status_normalized AS st
          FROM uses u JOIN registrations r ON r.registration_id = u.registration_id
                      JOIN products p ON p.product_id = r.product_id
          WHERE NOT u.is_synthetic AND NOT r.is_synthetic AND u.crop_name_normalized IS NOT NULL),
        gone AS (SELECT crop FROM x WHERE st IN ('withdrawn','expired') GROUP BY crop
                 ORDER BY count(DISTINCT product_id) DESC LIMIT 10)
        SELECT x.crop, x.country_code,
               count(DISTINCT product_id) FILTER (WHERE st = 'active') AS active,
               count(DISTINCT product_id) FILTER (WHERE st IN ('withdrawn','expired')) AS gone
        FROM x JOIN gone USING (crop) GROUP BY x.crop, x.country_code ORDER BY x.crop, x.country_code""")


def part_d():
    """Les 5 meilleurs couples par pays (FR, DE) + un exemple avec un produit LPC. Même fonction que GET /opportunities."""
    out = []
    for query_text, kwargs in (("country=FR&limit=5", {"country": "FR"}), ("country=DE&limit=5", {"country": "DE"}),
                               ("country=FR&lpcOnly=true&limit=5", {"country": "FR", "lpc_only": True}),
                               ("productId=P-LPC-M52&limit=5", {"product_id": "P-LPC-M52"})):
        data = opportunities.opportunities(kwargs.get("country"), None, None, 5, kwargs.get("product_id"), 5, kwargs.get("lpc_only", False))
        out.append((query_text, data["items"]))
    return out


def md_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def main():
    print("a) produits pilotes et sœurs…")
    a = part_a()
    print("b) culture × cible FR et DE…")
    b = part_b()
    print("c) cultures avec produits retirés…")
    c = part_c()
    print("d) opportunités biocontrôle…")
    d = part_d()

    out = ["# Cas de démo (comparaisons réelles)", "",
           f"Généré par `scripts/find_demo_cases.py` le {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC, lecture seule sur la base partagée. "
           "Les chiffres sont des comptes de lignes extraites : une absence ne prouve jamais une absence d'homologation. "
           "Les sœurs sont des hypothèses (`to_verify`). Les doses gardent leur unité originale (jamais converties).", "",
           "Base URL des requêtes : `http://localhost:3000/api` (lancer `uvicorn backend.app.main:app --port 3000`).", "",
           "## a) Produits pilotes et sœurs : lignes comparables par paire de pays", "",
           "`use` = culture × cible, `crop` = culture seule (granularity=crop). Trié par `crop` puis `use`.", ""]
    top = [r for r in a if r["crop"] or r["use"]][:12]
    # La paire FR,CA est la comparaison attendue par LPC : toujours montrée si elle a des lignes
    top += [r for r in a if r["pair"] == "FR,CA" and (r["crop"] or r["use"]) and r not in top][:6]
    out.append(md_table(["Produit", "ID", "Type", "Paire", "Lignes use", "Lignes crop"],
                        [(r["name"], r["pid"], r["kind"], r["pair"], r["use"], r["crop"]) for r in top]) if top
               else "Aucune ligne comparable trouvée.")
    out += ["", "Requêtes à utiliser en démo :", ""]
    for r in top[:5] + [r for r in top[5:] if r["pair"] == "FR,CA"][:3]:
        g = "crop" if r["crop"] > r["use"] else "use"
        out.append(f"- {r['name']} ({r['pair']}, {r[g]} lignes {g}) : `GET /compare?productId={r['pid']}&countries={r['pair']}&granularity={g}`")
    if not any(r["use"] for r in a):
        out += ["", "Aucune paire n'a de ligne comparable au niveau culture × cible pour ces produits : le niveau `crop` est le "
                    "seul qui donne un résultat (les usages canadiens n'ont presque jamais de cible)."]

    out += ["", "## b) Top 10 des couples culture × cible présents en FR et en DE", "",
            "Nombre de produits (non synthétiques) ayant un usage sur ce couple, par pays. Trié par le plus petit des deux comptes.", ""]
    out.append(md_table(["Culture", "Cible", "Produits FR", "Produits DE"],
                        [(r["crop"], r["target"], r["fr_products"], r["de_products"]) for r in b]) if b else "Aucun couple commun trouvé.")
    out += ["", "Requêtes :", ""]
    for r in b[:5]:
        out.append(f"- {r['crop']} × {r['target']} : `GET /products?crop={r['crop']}&target={r['target']}` "
                   f"puis `GET /compare?productId=<id>&countries=FR,DE&crop={r['crop']}&target={r['target']}`")

    out += ["", "## c) Top 10 des cultures avec des produits retirés ou expirés", "",
            "Produits distincts par culture et par pays (statut normalisé `withdrawn` ou `expired` vs `active`). "
            "Un produit peut compter dans les deux colonnes s'il a plusieurs homologations.", ""]
    if c:
        out.append(md_table(["Culture", "Pays", "Actifs", "Retirés/expirés"],
                            [(r["crop"], r["country_code"], r["active"], r["gone"]) for r in c]))
    else:
        s = query("""SELECT r.country_code, r.status_normalized, count(DISTINCT r.registration_id) AS regs, count(u.use_id) AS uses
                     FROM registrations r LEFT JOIN uses u ON u.registration_id = r.registration_id
                     WHERE NOT r.is_synthetic GROUP BY 1, 2 ORDER BY 1, 2""")
        out += ["**Aucune culture n'a de produit retiré/expiré avec des usages.** Dans les données actuelles, les homologations "
                "retirées (FR : `RETIRE`) n'ont aucun usage extrait, donc aucun lien avec une culture ; DE n'a pas de statut "
                "(`unknown`). Ce n'est pas une preuve d'absence de retraits par culture.", "",
                md_table(["Pays", "Statut normalisé", "Homologations", "Usages"],
                         [(r["country_code"], r["status_normalized"], r["regs"], r["uses"]) for r in s]), "",
                "Cas de démo possible : lister les retraits sans culture avec `GET /expirations?country=FR`."]
    out += ["", "Requêtes :", ""]
    for crop in dict.fromkeys(r["crop"] for r in c):
        out.append(f"- {crop} : `GET /expirations?crop={crop}&withinMonths=12`")
    if not c:
        out.append("- (voir ci-dessus : `GET /expirations?country=FR`)")

    out += ["", "## d) Opportunité marché : espaces libres pour le biocontrôle", "",
            "**Aide à l'analyse, pas une décision réglementaire ; classification biologique/chimique par règle, à vérifier.** "
            "Par couple culture × cible normalisés : usages ACTIFS de produits chimiques vs biologiques (catégorie déduite du nom de la "
            "substance active, hypothèse). Score = usages chimiques / (1 + usages biologiques). Aucun usage retiré n'existe dans les "
            "sources : le classement montre l'état actuel, pas un recul. « Retirés, même substance » = produits retirés du même pays "
            "contenant une substance de ces chimiques, SANS lien culture × cible (ce ne sont pas des usages retirés). "
            "Un 0 biologique ne prouve pas l'absence de produit biologique homologué.", ""]
    for query_text, items in d:
        out += [f"Requête exacte : `GET /opportunities?{query_text}`", ""]
        if not items:
            out += ["Aucun couple trouvé.", ""]
            continue
        rows = []
        for it in items:
            wd = it["withdrawnSameSubstance"]
            lpc = ", ".join(f"{p['commercialName']} ({p['relation']})" for p in it["lpcProducts"][:3]) or "aucun"
            rows.append((f"{it['cropNormalized']} × {it['targetNormalized']}", it["countryCode"], it["chemicalUses"],
                         it["biologicalUses"], it["biocontrolSpaceScore"], lpc, wd["withdrawnProducts"] if wd else "n/a"))
        out += [md_table(["Culture × cible", "Pays", "Usages chimiques", "Usages biologiques", "Score", "Produits LPC / sœurs autorisés",
                          "Retirés, même substance"], rows), ""]
    out += ["Avec `lpcOnly=true`, seuls les couples où un produit LPC, un candidat sœur ou un produit de même substance est déjà autorisé "
            "sont gardés (potentiel d'extension d'un produit déjà présent). Avec `productId`, la liste montre les couples où la substance du produit est autorisée dans au moins un pays mais pas dans "
            "le pays indiqué. Les produits sœurs et de même substance sont des hypothèses (`to_verify`). Question `/ask` associée : "
            "« Où les usages chimiques reculent-ils sur la vigne ? » ou « Quelles opportunités pour LALGUARD M52 ? »."]

    path = ROOT / "docs" / "demo_cases.md"
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("écrit", path)


if __name__ == "__main__":
    main()
