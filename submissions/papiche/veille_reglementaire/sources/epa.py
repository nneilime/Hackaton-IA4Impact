# SPDX-License-Identifier: AGPL-3.0-or-later
"""Source 3 — US EPA : registre APPRIL (dump public xlsx, sans clé) + étiquettes PDF officielles (PPLS).

C'est la source la plus hétérogène : l'étiquette est un PDF dont l'IA doit extraire doses et cultures
(unités américaines : fl oz/acre, lb/acre...). Les PDF ne sont pas redistribués : le script les retélécharge.
Dépendance système : `pdftotext` (poppler-utils).
"""
from __future__ import annotations
import hashlib, json, re, subprocess, zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from .. import config, polite_http
from . import Passage

XLSX = "https://www3.epa.gov/pesticides/appril/apprildatadump_public.xlsx"
PPLS = "https://www3.epa.gov/pesticides/chem_search/ppls/"
APPRIL_PAGE = "https://ordspub.epa.gov/ords/pesticides/f?p=APPRIL_PUBLIC:2::::::"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
SHEET = "ACTIVE_REGISTRATIONS5_PUBLIC_V"
COMPANY_NUM = "64137"        # Danstar Ferment AG / Lallemand Plant Care
MAX_PER_LABEL = 10           # passages de dose retenus par étiquette (échantillon reproductible)


def _fold(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _sheet_rows(path):
    """Lecture en flux de la feuille APPRIL (stdlib seule). Produit des dict colonne -> valeur."""
    z = zipfile.ZipFile(path)
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rid = next(s.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
               for s in wb.iter(NS + "sheet") if s.attrib["name"] == SHEET)
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = next(r.attrib["Target"] for r in rels if r.attrib["Id"] == rid)
    target = target.lstrip("/")
    target = target if target.startswith("xl/") else "xl/" + target
    strings = []
    if "xl/sharedStrings.xml" in z.namelist():
        with z.open("xl/sharedStrings.xml") as f:
            for _, el in ET.iterparse(f):
                if el.tag == NS + "si":
                    strings.append("".join(t.text or "" for t in el.iter(NS + "t")))
                    el.clear()
    header = None
    with z.open(target) as f:
        for _, el in ET.iterparse(f):
            if el.tag != NS + "row":
                continue
            vals = {}
            for c in el.findall(NS + "c"):
                col = re.match(r"[A-Z]+", c.attrib["r"]).group()
                t = c.attrib.get("t")
                if t == "inlineStr":                       # le dump EPA écrit ses textes en ligne
                    vals[col] = "".join(x.text or "" for x in c.iter(NS + "t"))
                    continue
                v = c.find(NS + "v")
                if v is None:
                    continue
                vals[col] = strings[int(v.text)] if t == "s" else v.text
            el.clear()
            if header is None:
                header = vals
                continue
            yield {header[k]: v for k, v in vals.items() if k in header}


def _xl_date(v):
    try:
        return (datetime(1899, 12, 30) + timedelta(days=float(v))).date().isoformat()
    except (TypeError, ValueError):
        return None


INFO = {"id": "epa", "name": "EPA (APPRIL + étiquettes)", "country_code": "US", "country": "États-Unis",
        "region": "Amérique du Nord", "format": "XLSX + PDF", "lang": "EN"}


def has_current_label(product: dict) -> bool:
    """Seuls les produits enregistrés ont une étiquette utile (les produits annulés sont ignorés)."""
    return bool(product["label_pdf"]) and "registered" in (product["status"] or "").lower()


def collect(scope: dict | None = None) -> dict:
    out = config.RAW / "epa"
    (out / "labels").mkdir(parents=True, exist_ok=True)
    xlsx = out / "appril.xlsx"
    polite_http.download(XLSX, xlsx)          # 94 Mo une seule fois ; 304 (0 octet) si inchangé
    scope = scope or json.loads((config.CONFIG / "scope.json").read_text())
    wanted = [_fold(n) for p in scope["products"] for n in p.get("epa", [])]
    rows = []
    for r in _sheet_rows(xlsx):
        name = _fold(r.get("PRODUCT_NAME", ""))
        if any(w and w in name for w in wanted):
            rows.append(r)
    products = []
    for r in rows:
        labels = [x.strip() for x in (r.get("LABEL_NAMES") or "").split(",") if x.strip()]
        products.append({"reg_no": r["REG_NUM"], "product": r["PRODUCT_NAME"], "company": r.get("COMPANY_NAME"),
                         "company_no": r.get("COMPANY_NUM"), "status": r.get("STATUS_DESC") or r.get("STATUS"),
                         "ais": r.get("AIS"), "label_pdf": labels[0] if labels else None})
    for product in products:
        if not has_current_label(product):
            continue                                   # pas de requête inutile pour un produit annulé
        pdf = out / "labels" / product["label_pdf"]
        if polite_http.download(PPLS + product["label_pdf"], pdf)["changed"] or not pdf.with_suffix(".txt").exists():
            subprocess.run(["pdftotext", "-layout", str(pdf), str(pdf.with_suffix(".txt"))], check=True)
    (out / "products.json").write_text(json.dumps({"collected_at": date.today().isoformat(), "products": products},
                                                  ensure_ascii=False, indent=1))
    (out / "_meta.json").write_text(json.dumps({"collected_at": date.today().isoformat()}))
    return {"source": "epa", "products": [(p["reg_no"], p["product"]) for p in products]}


RATE = re.compile(r"\b(fl\.?\s?oz|oz\.?|lbs?\.?|pints?|pt\.?|quarts?|qt\.?|gal(?:lons?)?)\b[^.\n]{0,40}\b(acre|A|1,?000 sq)", re.I)


def passages(scope: dict) -> list[Passage]:
    meta = json.loads((config.RAW / "epa" / "products.json").read_text())
    out: list[Passage] = []
    for p in meta["products"]:
        if not has_current_label(p):
            continue                                  # étiquettes de produits annulés : hors périmètre
        txt = (config.RAW / "epa" / "labels" / p["label_pdf"]).with_suffix(".txt")
        if not txt.exists():
            continue
        lines = [re.sub(r"\s{2,}", "  ", l).strip() for l in txt.read_text(errors="replace").splitlines()]
        lines = [l for l in lines if l]
        seen, n_kept = set(), 0
        for i, l in enumerate(lines):
            if not RATE.search(l) or l in seen or n_kept >= MAX_PER_LABEL:
                continue
            ctx = " ".join(lines[max(0, i - 2): i + 2])[:700]       # la ligne + son contexte immédiat
            if not re.search(r"\bacre\b|1,?000 sq", ctx, re.I):     # on ne garde que les taux d'application
                continue
            seen.add(l)
            n_kept += 1
            status = (p["status"] or "").lower()
            out.append(Passage(
                passage_id=f"epa:{p['reg_no']}:{hashlib.sha1(ctx.encode()).hexdigest()[:10]}",
                source_id="epa", country="US", region="Amérique du Nord", product=re.sub(r"[®™]", "", p["product"]).strip().upper(),
                reg_number=p["reg_no"], holder=p["company"] or "", status_original=p["status"] or "",
                status="autorise" if "registered" in status else "autre",
                ai=p.get("ais") or "", text=f"EPA Reg. No. {p['reg_no']} | Product: {p['product']} | Label text: {ctx}",
                source_url=PPLS + p["label_pdf"], dataset_url=XLSX, collected_at=meta["collected_at"], kind="label"))
    return out
