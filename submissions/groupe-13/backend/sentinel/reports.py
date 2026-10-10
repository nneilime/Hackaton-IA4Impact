"""Rapports de contrôle : PDF (revue), JSON (intégration), CSV (analyses tabulaires)."""
from __future__ import annotations

import csv
import io
import json

from . import ENGINE_VERSION, RULESET_VERSION
from .db import now
from .normalize import amount_str

STATUS_FR = {"CONFORME": "Conforme", "ANOMALIE": "Anomalie", "NON_VERIFIABLE": "Non vérifiable",
             "NON_APPLICABLE": "Non applicable", "ERREUR_TECHNIQUE": "Erreur technique"}


def case_report_json(payload: dict, decisions: list) -> bytes:
    rep = {
        "rapport": "Rapport de contrôle documentaire — iMSA Sentinel",
        "genere_le": now(), "version_moteur": ENGINE_VERSION, "version_regles": RULESET_VERSION,
        "avertissement": "Une anomalie est un écart documentaire constaté ; elle ne constitue pas une preuve de fraude.",
        "dossier": payload["id"], "sources": {"bordereau": payload.get("jpg"), "facture": payload.get("txt_file"),
                                              "sha256_bordereau": payload.get("extraction", {}).get("sha256"),
                                              "sha256_facture": payload.get("txt", {}).get("sha256")},
        "rapprochement": payload.get("pairing"), "synthese": payload.get("summary"),
        "resultats": [{k: r.get(k) for k in ("rule_id", "title", "status", "jpg_value", "txt_value", "gap",
                                             "explanation", "uncertainty", "convention", "img_refs", "txt_refs")}
                      for r in payload.get("results", [])],
        "zones": [{k: z.get(k) for k in ("zone_id", "label", "status", "flags", "reason", "related_rules", "regions")}
                  for z in payload.get("zones", [])],
        "observations_complementaires": payload.get("observations"),
        "corrections_humaines": payload.get("corrections"),
        "decisions": decisions,
    }
    return json.dumps(rep, ensure_ascii=False, indent=2).encode("utf-8")


def results_csv(rows: list) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["dossier", "famille", "statut_dossier", "regle", "intitule", "statut", "valeur_bordereau",
                "valeur_fichier", "ecart_centimes", "incertitude", "explication"])
    for r in rows:
        w.writerow(r)
    return ("﻿" + buf.getvalue()).encode("utf-8")   # BOM : ouverture directe dans Excel


ZONE_RGB = {"CONFORME": (22, 163, 74), "ANOMALIE": (220, 38, 38), "NON_VERIFIABLE": (107, 114, 128),
            "NON_APPLICABLE": (184, 191, 199), "ERREUR_TECHNIQUE": (245, 158, 11)}


def zone_illustration(jpg_path, zones: list, rotation: int = 0, width: int = 900) -> bytes:
    """Bordereau réduit avec les encadrements colorés des 15 zones (même code couleur que l'application)."""
    from PIL import Image, ImageDraw, ImageFont
    im = Image.open(jpg_path).convert("RGB")
    if rotation == 180:
        im = im.rotate(180)
    W, H = im.size
    k = width / W
    im = im.resize((width, int(H * k)))
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    for z in zones:
        col = ZONE_RGB.get(z["status"], (107, 114, 128))
        for i, r in enumerate(z.get("regions") or []):
            x0, y0, x1, y1 = [v * k for v in r["box"]]
            if z["status"] == "NON_APPLICABLE":
                for xx in range(int(x0), int(x1), 8):
                    d.line([(xx, y0), (min(xx + 4, x1), y0)], fill=col, width=2); d.line([(xx, y1), (min(xx + 4, x1), y1)], fill=col, width=2)
                for yy in range(int(y0), int(y1), 8):
                    d.line([(x0, yy), (x0, min(yy + 4, y1))], fill=col, width=2); d.line([(x1, yy), (x1, min(yy + 4, y1))], fill=col, width=2)
            else:
                d.rectangle([x0, y0, x1, y1], outline=col, width=2)
            if i == 0:
                tw = d.textlength(z["zone_id"], font=font)
                d.rectangle([x0, y0 - 15, x0 + tw + 6, y0], fill=col)
                d.text((x0 + 3, y0 - 15), z["zone_id"], fill=(255, 255, 255), font=font)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def case_report_pdf(payload: dict, decisions: list, case_row: dict, jpg_path=None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm,
                            bottomMargin=14 * mm, title=f"Rapport de contrôle {payload['id']}")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=15, spaceAfter=4, textColor=colors.HexColor("#14365d"))
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=11.5, spaceBefore=8, spaceAfter=4,
                        textColor=colors.HexColor("#14365d"))
    p = ParagraphStyle("p", parent=ss["BodyText"], fontSize=8.6, leading=11)
    small = ParagraphStyle("s", parent=p, fontSize=7.4, leading=9.2, textColor=colors.HexColor("#444444"))
    S = []
    summ = payload.get("summary", {})
    S.append(Paragraph(f"Rapport de contrôle documentaire — dossier {payload['id']}", h1))
    S.append(Paragraph(f"iMSA Sentinel · moteur {ENGINE_VERSION} · règles {RULESET_VERSION} · généré le {now()}", small))
    S.append(Spacer(1, 4))
    S.append(Paragraph("<b>Avertissement.</b> Les anomalies signalées sont des écarts documentaires constatés entre le "
                       "bordereau et le fichier de facturation. Elles ne constituent ni une preuve de fraude ni la preuve "
                       "qu'un soin a ou n'a pas été réalisé ; leur interprétation appartient aux personnes habilitées.", p))
    S.append(Paragraph("1. Références et sources", h2))
    txt = payload.get("txt", {})
    ref = [["Dossier", payload["id"]], ["Établissement (fichier)", f"{case_row.get('establishment') or '—'} — FINESS {case_row.get('finess') or '—'}"],
           ["N° facture (fichier)", case_row.get("invoice_no") or "—"],
           ["Bordereau", f"{payload.get('jpg')}  (SHA-256 {payload.get('extraction', {}).get('sha256', '')[:16]}…)"],
           ["Fichier de facturation", f"{payload.get('txt_file')}  (SHA-256 {txt.get('sha256', '')[:16]}…)"],
           ["Rapprochement", f"{payload.get('pairing', {}).get('status')} — {payload.get('pairing', {}).get('methode', '')}"],
           ["Statut du dossier", case_row.get("status") or "—"]]
    t = Table([[Paragraph(a, p), Paragraph(str(b), p)] for a, b in ref], colWidths=[45 * mm, 133 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c9d3df")),
                           ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2f7")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    S.append(t)
    S.append(Paragraph("2. Synthèse", h2))
    c = summ.get("counts", {})
    S.append(Paragraph(
        f"Contrôles : {len(payload.get('results', []))} — conformes {c.get('CONFORME', 0)}, anomalies {c.get('ANOMALIE', 0)}, "
        f"non vérifiables {c.get('NON_VERIFIABLE', 0)}, non applicables {c.get('NON_APPLICABLE', 0)}, "
        f"erreurs techniques {c.get('ERREUR_TECHNIQUE', 0)}. Montant facturé (fichier : TotalPrestations + TotalHonoraires) : "
        f"{amount_str(summ.get('billed_cents'))}. Écart net mesuré sur les totaux : {amount_str(summ.get('net_total_gap_cents'))}.", p))
    zones = payload.get("zones") or []
    if zones:
        from reportlab.platypus import Image as RLImage
        S.append(Paragraph("3. Les 15 zones du bordereau", h2))
        S.append(Paragraph("Couleur de chaque zone : vert = conforme (données fiables), rouge = anomalie, gris = non vérifiable "
                           "(doute ou preuve insuffisante), gris clair en pointillés = non applicable, orange = erreur technique. "
                           "Le statut de zone ne remplace pas le détail des règles (section 4).", small))
        ztab = [[Paragraph("<b>Zone</b>", small), Paragraph("<b>Statut</b>", small), Paragraph("<b>Règles</b>", small),
                 Paragraph("<b>Motif</b>", small)]]
        zst = [("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c9d3df")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7"))]
        for i, z in enumerate(zones, start=1):
            ztab.append([Paragraph(f"<b>{z['zone_id']}</b> {_esc(z['label'])}", small), Paragraph(STATUS_FR[z["status"]], small),
                         Paragraph(", ".join(r["rule_id"] for r in z.get("related_rules", [])), small),
                         Paragraph(_esc(z.get("reason")) + (" (contrôles également incertains)" if "controles_egalement_incertains" in (z.get("flags") or []) else ""), small)])
            r, g, b = ZONE_RGB[z["status"]]
            zst.append(("BACKGROUND", (1, i), (1, i), colors.Color(r / 255, g / 255, b / 255, alpha=0.22)))
        tz = Table(ztab, colWidths=[46 * mm, 22 * mm, 30 * mm, 80 * mm], repeatRows=1)
        tz.setStyle(TableStyle(zst))
        S.append(tz)
        if jpg_path:
            try:
                png = zone_illustration(jpg_path, zones, (payload.get("extraction", {}).get("layout") or {}).get("rotation", 0))
                img = RLImage(io.BytesIO(png))
                ratio = img.imageHeight / img.imageWidth
                img.drawWidth, img.drawHeight = 120 * mm, 120 * mm * ratio
                S.append(Spacer(1, 4)); S.append(img)
                S.append(Paragraph("Illustration : bordereau avec les encadrements des 15 zones selon leur statut.", small))
            except Exception as e:  # noqa
                S.append(Paragraph(f"Illustration indisponible ({_esc(type(e).__name__)}).", small))
    S.append(Paragraph("4. Résultat de chaque contrôle", h2))
    rows = [[Paragraph("<b>Règle</b>", small), Paragraph("<b>Statut</b>", small), Paragraph("<b>Bordereau</b>", small),
             Paragraph("<b>Fichier</b>", small), Paragraph("<b>Explication</b>", small)]]
    style = [("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c9d3df")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7"))]
    colmap = {"ANOMALIE": "#fde3e1", "NON_VERIFIABLE": "#e5e7eb", "ERREUR_TECHNIQUE": "#fef3c7"}
    for i, r in enumerate(payload.get("results", []), start=1):
        rows.append([Paragraph(f"<b>{r['rule_id']}</b> {r['title']}", small), Paragraph(STATUS_FR[r["status"]], small),
                     Paragraph(_esc(r.get("jpg_value")), small), Paragraph(_esc(r.get("txt_value")), small),
                     Paragraph(_esc(r.get("explanation")), small)])
        if r["status"] in colmap:
            style.append(("BACKGROUND", (1, i), (1, i), colors.HexColor(colmap[r["status"]])))
    t = Table(rows, colWidths=[42 * mm, 18 * mm, 28 * mm, 28 * mm, 62 * mm], repeatRows=1)
    t.setStyle(TableStyle(style))
    S.append(t)
    an = [r for r in payload.get("results", []) if r["status"] == "ANOMALIE"]
    S.append(Paragraph("5. Anomalies et éléments de preuve", h2))
    if not an:
        S.append(Paragraph("Aucune anomalie détectée par le moteur de contrôle.", p))
    for r in an:
        loc = "; ".join(f"{x.get('label')} (zone {x.get('zone')}, boîte {x.get('box')})" for x in r.get("img_refs", []))
        tl = "; ".join(f"{x.get('label')} (ligne {x.get('line_no')}, pos. {x.get('start')}-{x.get('end')})" for x in r.get("txt_refs", []))
        gap = r.get("gap") or {}
        S.append(Paragraph(f"<b>{r['rule_id']} — {r['title']}</b><br/>{_esc(r['explanation'])}"
                           + (f"<br/>Écart : {amount_str(gap.get('amount_cents'))} ({gap.get('label', '')})" if gap.get("amount_cents") else "")
                           + (f"<br/>Bordereau : {_esc(loc)}" if loc else "") + (f"<br/>Fichier : {_esc(tl)}" if tl else ""), p))
        S.append(Spacer(1, 3))
    nv = [r for r in payload.get("results", []) if r["status"] == "NON_VERIFIABLE"]
    S.append(Paragraph("6. Contrôles non vérifiables", h2))
    S.append(Paragraph("Aucun." if not nv else "<br/>".join(f"<b>{r['rule_id']}</b> : {_esc(r['explanation'])}" for r in nv), p))
    S.append(Paragraph("7. Observations complémentaires (hors cahier des charges)", h2))
    obs = payload.get("observations", [])
    S.append(Paragraph("Aucune." if not obs else "<br/>".join(f"• [{o.get('source')}] {_esc(o.get('message'))}" for o in obs[:30]), p))
    S.append(Paragraph("8. Corrections humaines et décisions", h2))
    corr = payload.get("corrections") or []
    lines = [f"• Correction OCR {c['target']} : « {_esc(c.get('original'))} » → « {_esc(c['corrected'])} » par "
             f"{c.get('username')} le {c['created_at']}" + (f" — {_esc(c.get('comment'))}" if c.get("comment") else "") for c in corr]
    lines += [f"• {d['created_at']} — {d.get('display_name') or d.get('username') or '—'} : {d['kind']}"
              + (f" [{d['rule_id']}]" if d.get("rule_id") else "") + (f" → {_esc(d.get('value'))}" if d.get("value") else "")
              + (f" — {_esc(d.get('comment'))}" if d.get("comment") else "") for d in decisions]
    S.append(Paragraph("Aucune." if not lines else "<br/>".join(lines), p))
    S.append(Spacer(1, 6))
    S.append(Paragraph(f"Horodatage de l'analyse : {payload.get('analyzed_at')} · moteur {payload.get('engine_version')} · "
                       f"règles {payload.get('ruleset_version')}", small))
    doc.build(S)
    return buf.getvalue()


def _esc(v) -> str:
    if v is None:
        return "—"
    return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
