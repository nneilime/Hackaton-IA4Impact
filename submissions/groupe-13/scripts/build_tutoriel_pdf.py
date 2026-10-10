"""Génère docs/TUTORIEL_iMSA_Sentinel.pdf (tutoriel illustré).

Usage (depuis la racine du projet) : python scripts/build_tutoriel_pdf.py
Dépendances : reportlab, Pillow, fontTools (pour convertir la police IBM Plex de l'interface ;
à défaut, DejaVu Sans est utilisée).
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

from PIL import Image as PILImage, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
                                Image, PageBreak, KeepTogether, Flowable, CondPageBreak, NextPageTemplate)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "images"
OUT = ROOT / "docs" / "TUTORIEL_iMSA_Sentinel.pdf"
WORK = Path(tempfile.mkdtemp(prefix="tuto_"))

# ------------------------------------------------------------------ couleurs (celles de l'interface)
INDIGO = colors.HexColor("#232c73")
INDIGO_2 = colors.HexColor("#2f3a8f")
INDIGO_SOFT = colors.HexColor("#e8eaf6")
OCHRE = colors.HexColor("#e3a62b")
OCHRE_SOFT = colors.HexColor("#fbf0d9")
INK = colors.HexColor("#1d2a33")
INK2 = colors.HexColor("#4a5864")
INK3 = colors.HexColor("#6f7c87")
LINE = colors.HexColor("#d6dce1")
LINE2 = colors.HexColor("#e7ebee")
PANEL2 = colors.HexColor("#f7f9f8")
OK = colors.HexColor("#0b7a3b"); OK_SOFT = colors.HexColor("#e3f3e8")
ANO = colors.HexColor("#b42f2f"); ANO_SOFT = colors.HexColor("#fbe4e2")
NV = colors.HexColor("#8a5a00"); NV_SOFT = colors.HexColor("#fff1d2")
NA = colors.HexColor("#6b7680"); NA_SOFT = colors.HexColor("#eef1f3")
ERR = colors.HexColor("#6a3fb5"); ERR_SOFT = colors.HexColor("#efe7fb")


# ------------------------------------------------------------------ polices
def setup_fonts():
    dv = "/usr/share/fonts/truetype/dejavu/"
    fb = {"r": "DejaVuSans.ttf", "b": "DejaVuSans-Bold.ttf", "i": "DejaVuSans-Oblique.ttf", "m": "DejaVuSansMono.ttf"}
    fallback_dir = None
    for d in (dv, "C:/Windows/Fonts/"):
        if os.path.exists(d + fb["r"]):
            fallback_dir = d
    if fallback_dir:
        pdfmetrics.registerFont(TTFont("Sym", fallback_dir + fb["r"]))
    plex = ROOT / "frontend" / "node_modules" / "@fontsource"
    ok = False
    try:
        from fontTools.ttLib import TTFont as FT
        spec = {"Plex": "ibm-plex-sans/files/ibm-plex-sans-latin-400-normal.woff",
                "Plex-It": "ibm-plex-sans/files/ibm-plex-sans-latin-400-italic.woff",
                "Plex-Md": "ibm-plex-sans/files/ibm-plex-sans-latin-500-normal.woff",
                "Plex-SB": "ibm-plex-sans/files/ibm-plex-sans-latin-600-normal.woff",
                "Plex-SBIt": "ibm-plex-sans/files/ibm-plex-sans-latin-600-italic.woff",
                "Plex-Bd": "ibm-plex-sans/files/ibm-plex-sans-latin-700-normal.woff",
                "Mono": "ibm-plex-mono/files/ibm-plex-mono-latin-400-normal.woff",
                "Mono-Md": "ibm-plex-mono/files/ibm-plex-mono-latin-500-normal.woff"}
        for name, rel in spec.items():
            t = FT(str(plex / rel)); t.flavor = None
            p = WORK / (name + ".ttf"); t.save(str(p))
            pdfmetrics.registerFont(TTFont(name, str(p)))
        ok = True
    except Exception as e:  # noqa
        print("IBM Plex indisponible, DejaVu utilisée :", e)
    if not ok:
        for name, f in (("Plex", "r"), ("Plex-It", "i"), ("Plex-Md", "b"), ("Plex-SB", "b"), ("Plex-SBIt", "b"),
                        ("Plex-Bd", "b"), ("Mono", "m"), ("Mono-Md", "m")):
            pdfmetrics.registerFont(TTFont(name, fallback_dir + fb[f]))
    pdfmetrics.registerFontFamily("Plex", normal="Plex", bold="Plex-SB", italic="Plex-It", boldItalic="Plex-SBIt")
    pdfmetrics.registerFontFamily("Mono", normal="Mono", bold="Mono-Md", italic="Mono", boldItalic="Mono-Md")
    return ok


PLEX_OK = setup_fonts()
_PLEX_CMAP = None
if PLEX_OK:
    from fontTools.ttLib import TTFont as _FT
    _PLEX_CMAP = set(_FT(str(WORK / "Plex.ttf")).getBestCmap().keys())


def fx(t: str) -> str:
    """Caractères absents du sous-ensemble latin d'IBM Plex (flèches, ≤, ≠…) → police de secours."""
    if not _PLEX_CMAP:
        return t
    out = []
    for ch in t:
        if ord(ch) > 127 and ord(ch) not in _PLEX_CMAP:
            out.append(f'<font name="Sym">{ch}</font>')
        else:
            out.append(ch)
    return "".join(out)


# ------------------------------------------------------------------ styles
S = {}
S["body"] = ParagraphStyle("body", fontName="Plex", fontSize=9.6, leading=14.2, textColor=INK, spaceAfter=6)
S["lead"] = ParagraphStyle("lead", parent=S["body"], fontSize=11.2, leading=16.5, textColor=INK2, spaceAfter=10)
S["small"] = ParagraphStyle("small", parent=S["body"], fontSize=8.4, leading=11.6, textColor=INK2, spaceAfter=3)
S["cap"] = ParagraphStyle("cap", parent=S["body"], fontSize=8.2, leading=11, textColor=INK3, spaceBefore=4,
                          spaceAfter=0)
S["h1"] = ParagraphStyle("h1", fontName="Plex-Bd", fontSize=23, leading=28, textColor=INDIGO, spaceAfter=4)
S["h2"] = ParagraphStyle("h2", fontName="Plex-SB", fontSize=13.2, leading=17, textColor=INDIGO, spaceBefore=12,
                         spaceAfter=6)
S["h3"] = ParagraphStyle("h3", fontName="Plex-SB", fontSize=10.4, leading=14, textColor=INK, spaceBefore=8,
                         spaceAfter=3)
S["cell"] = ParagraphStyle("cell", fontName="Plex", fontSize=8.5, leading=11.6, textColor=INK)
S["cellb"] = ParagraphStyle("cellb", parent=S["cell"], fontName="Plex-SB")
S["cellh"] = ParagraphStyle("cellh", parent=S["cell"], fontName="Plex-SB", textColor=colors.white)
S["code"] = ParagraphStyle("code", fontName="Mono", fontSize=8.2, leading=11.6, textColor=INK)
S["bul"] = ParagraphStyle("bul", parent=S["body"], leftIndent=12, bulletIndent=2, spaceAfter=3)
S["step"] = ParagraphStyle("step", parent=S["body"], spaceAfter=0)
S["callt"] = ParagraphStyle("callt", parent=S["body"], fontName="Plex-SB", fontSize=9.2, spaceAfter=2)
S["call"] = ParagraphStyle("call", parent=S["body"], fontSize=9.1, leading=13.2, spaceAfter=0)
S["toc0"] = ParagraphStyle("toc0", fontName="Plex-SB", fontSize=10.5, leading=15, textColor=INDIGO, spaceBefore=5)
S["toc1"] = ParagraphStyle("toc1", fontName="Plex", fontSize=8.8, leading=12.2, textColor=INK2, leftIndent=18)

W = A4[0] - 40 * mm  # largeur utile
CW = [W]            # largeur courante (réduite dans une mise en page texte + capture)


def P(t, st="body"):
    return Paragraph(fx(t), S[st] if isinstance(st, str) else st)


def ui(t):
    """Libellé d'un élément de l'interface."""
    return f'<font name="Plex-SB" color="#2f3a8f">{t}</font>'


def code(t):
    return f'<font name="Mono" size="8.6" color="#232c73" backColor="#eef0f7">\u00a0{t}\u00a0</font>'


# ------------------------------------------------------------------ titres + sommaire
class Heading(Paragraph):
    def __init__(self, text, style, level, toc_text, key):
        super().__init__(fx(text), S[style])
        self.toc_level, self.toc_text, self.key = level, toc_text, key


_hn = [0]


def H1(num, title, lead=None):
    _hn[0] += 1
    label = f"{num:02d}" if isinstance(num, int) else num
    toc = f"{num}. {title}" if isinstance(num, int) else f"{title}"
    out = [PageBreak(),
           Paragraph(f'<font name="Plex-Bd" color="#e3a62b" size="34">{label}</font>', ParagraphStyle(
               "num", fontName="Plex-Bd", fontSize=34, leading=36, spaceAfter=6)),
           Heading(title, "h1", 0, toc, f"h{_hn[0]}"),
           Rule(W, 2.2, OCHRE, 34 * mm, after=10)]
    if lead:
        out.append(P(lead, "lead"))
    return out


def H2(title, need=55):
    _hn[0] += 1
    return [CondPageBreak(need * mm), Heading(title, "h2", 1, title, f"h{_hn[0]}")]


def H3(title):
    return P(title, "h3")


class Rule(Flowable):
    def __init__(self, width, thick=0.6, color=LINE, length=None, after=6):
        super().__init__()
        self.width, self.thick, self.color, self.length, self.after = width, thick, color, length, after

    def wrap(self, aw, ah):
        return self.width, self.thick + self.after

    def draw(self):
        c = self.canv
        c.setStrokeColor(self.color); c.setLineWidth(self.thick)
        c.line(0, self.after, self.length or self.width, self.after)


class Badge(Flowable):
    def __init__(self, n, size=6.4 * mm, fill=INDIGO, text=colors.white):
        super().__init__()
        self.n, self.size, self.fill, self.text = n, size, fill, text

    def wrap(self, aw, ah):
        return self.size, self.size

    def draw(self):
        c = self.canv
        r = self.size / 2
        c.setFillColor(self.fill); c.circle(r, r, r, stroke=0, fill=1)
        c.setFillColor(self.text); c.setFont("Plex-Bd", 9.5)
        c.drawCentredString(r, r - 3.3, str(self.n))


def bullets(items, st="bul"):
    return [Paragraph(fx(i), S[st], bulletText="•") for i in items]


def steps(items, start=1):
    rows = []
    for i, it in enumerate(items):
        title, body = it if isinstance(it, tuple) else (None, it)
        cell = []
        if title:
            cell.append(P(f'<font name="Plex-SB">{title}</font>', "step"))
        if body:
            cell.append(P(body, "step"))
        rows.append([Badge(start + i), cell])
    t = Table(rows, colWidths=[10 * mm, CW[0] - 10 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 3),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (1, 0), (1, -1), 4)]))
    return [t, Spacer(1, 4)]


CALLOUTS = {
    "retenir": ("À retenir", INDIGO_2, INDIGO_SOFT),
    "astuce": ("Astuce", OK, OK_SOFT),
    "attention": ("Attention", NV, NV_SOFT),
    "important": ("Important", ANO, ANO_SOFT),
}


def callout(kind, text, title=None):
    t0, bar, bg = CALLOUTS[kind]
    cell = [P(f'<font color="{bar.hexval().replace("0x", "#")}">{title or t0}</font>', "callt")]
    for para in text if isinstance(text, list) else [text]:
        cell.append(P(para, "call"))
    t = Table([["", cell]], colWidths=[1.6 * mm, CW[0] - 1.6 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), bar), ("BACKGROUND", (1, 0), (1, 0), bg),
                           ("LEFTPADDING", (1, 0), (1, 0), 10), ("RIGHTPADDING", (1, 0), (1, 0), 10),
                           ("TOPPADDING", (1, 0), (1, 0), 7), ("BOTTOMPADDING", (1, 0), (1, 0), 8),
                           ("LEFTPADDING", (0, 0), (0, 0), 0), ("RIGHTPADDING", (0, 0), (0, 0), 0)]))
    if CW[0] != W:
        return [Spacer(1, 4), t]
    return [Spacer(1, 4), KeepTogether(t), Spacer(1, 8)]


def table(header, rows, widths, first_bold=False, mono_first=False, zebra=True, head_bg=INDIGO):
    data = [[P(h, "cellh") for h in header]]
    for r in rows:
        line = []
        for j, c in enumerate(r):
            if isinstance(c, Flowable) or isinstance(c, list):
                line.append(c)
            elif j == 0 and mono_first:
                line.append(P(f'<font name="Mono-Md" size="8.2">{c}</font>', "cell"))
            else:
                line.append(P(c, "cellb" if (j == 0 and first_bold) else "cell"))
        data.append(line)
    tw = [w * CW[0] for w in widths]
    t = Table(data, colWidths=tw, repeatRows=1)
    st = [("BACKGROUND", (0, 0), (-1, 0), head_bg), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE2), ("TOPPADDING", (0, 0), (-1, -1), 4.5),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5), ("LEFTPADDING", (0, 0), (-1, -1), 6),
          ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("BOX", (0, 0), (-1, -1), 0.5, LINE)]
    if zebra:
        for i in range(2, len(data), 2):
            st.append(("BACKGROUND", (0, i), (-1, i), PANEL2))
    t.setStyle(TableStyle(st))
    return [Spacer(1, 2), t, Spacer(1, 8)]


def codeblock(lines):
    cell = [Paragraph(fx(l.replace(" ", "\u00a0")) or "\u00a0", S["code"]) for l in lines]
    t = Table([[cell]], colWidths=[W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f4f8")),
                           ("BOX", (0, 0), (-1, -1), 0.5, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 9),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    return [Spacer(1, 2), t, Spacer(1, 8)]


# ------------------------------------------------------------------ images
def _font(sz):
    for f in (WORK / "Plex-Bd.ttf", Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")):
        if f.exists():
            return ImageFont.truetype(str(f), sz)
    return ImageFont.load_default()


def prep(name, crop=None, marks=None, maxw=1800):
    """Recadre / annote / compresse une capture. marks : [(n, x, y)] en pixels de la capture."""
    im = PILImage.open(IMG / name).convert("RGB")
    if marks:
        d = ImageDraw.Draw(im)
        f = _font(27)
        for n, x, y in marks:
            r = 22
            d.ellipse((x - r - 5, y - r - 5, x + r + 5, y + r + 5), fill=(255, 255, 255))
            d.ellipse((x - r, y - r, x + r, y + r), fill=(227, 166, 43))
            d.text((x, y + 1), str(n), font=f, fill=(29, 42, 51), anchor="mm")
    if crop:
        im = im.crop(crop)
    if im.width > maxw:
        im = im.resize((maxw, round(im.height * maxw / im.width)), PILImage.LANCZOS)
    key = name.replace(".png", "") + ("_c%d_%d" % crop[:2] if crop else "") + ("_m" if marks else "")
    out = WORK / (key + ".jpg")
    im.save(out, quality=86, optimize=True)
    return out, im.size


_fig = [0]


def framed(path, size, width):
    h = width * size[1] / size[0]
    img = Image(str(path), width=width, height=h)
    t = Table([[img]], colWidths=[width])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return t


def fig(name, caption, width=None, crop=None, marks=None):
    _fig[0] += 1
    width = width or W
    path, size = prep(name, crop, marks)
    cap = P(f'<font name="Plex-SB" color="#4a5864">Figure {_fig[0]}</font> · {caption}', "cap")
    return [Spacer(1, 4), KeepTogether([framed(path, size, width), cap]), Spacer(1, 10)]


def side(name, crop, caption, content, img_w=78 * mm):
    """Capture recadrée à droite, texte à gauche."""
    _fig[0] += 1
    path, size = prep(name, crop)
    if callable(content):
        CW[0] = W - img_w - 7 * mm
        try:
            content = content()
        finally:
            CW[0] = W
    right = [framed(path, size, img_w), P(f'<font name="Plex-SB" color="#4a5864">Figure {_fig[0]}</font> · {caption}', "cap")]
    t = Table([[content, right]], colWidths=[W - img_w - 7 * mm, img_w + 7 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (0, 0), 7 * mm), ("RIGHTPADDING", (1, 0), (1, 0), 0)]))
    return [Spacer(1, 4), t, Spacer(1, 8)]


def legend(items):
    rows = [[Badge(n, 5.4 * mm, OCHRE, INK), P(t, "cell")] for n, t in items]
    t = Table(rows, colWidths=[8 * mm, W - 8 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                           ("TOPPADDING", (1, 0), (1, -1), 3)]))
    return [t, Spacer(1, 8)]


def status_chip(label, fg, bg):
    t = Table([[P(f'<font name="Plex-SB" color="{fg}">{label}</font>', "cell")]])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("LEFTPADDING", (0, 0), (-1, -1), 5),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
    return t


def hexc(c):
    return "#" + c.hexval()[2:]


# Les captures font 2160 × 1290 px (fenêtre 1440 × 860 à l'échelle 1,5).
def q(x, y):
    """Coordonnées relevées sur une vignette 1000 px de large → pixels de la capture."""
    return round(x * 2.16), round(y * 2.16)


# ------------------------------------------------------------------ gabarits de page
class Doc(BaseDocTemplate):
    def __init__(self, fn):
        super().__init__(fn, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=22 * mm,
                         bottomMargin=20 * mm, title="iMSA Sentinel — Tutoriel d'utilisation",
                         author="Équipe iMSA Sentinel", subject="Contrôle automatisé des justificatifs de santé")
        fr = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f", leftPadding=0,
                   rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate("cover", [fr], onPage=draw_cover),
                               PageTemplate("normal", [fr], onPageEnd=draw_page)])
        self.chapter = ""

    def afterFlowable(self, f):
        if isinstance(f, Heading):
            if f.toc_level == 0:
                self.chapter = f.toc_text
            self.canv.bookmarkPage(f.key)
            self.canv.addOutlineEntry(f.toc_text, f.key, level=f.toc_level, closed=f.toc_level == 0)
            self.notify("TOCEntry", (f.toc_level, f.toc_text, self.page, f.key))

    def handle_documentBegin(self):
        self.chapter = ""
        super().handle_documentBegin()


def draw_page(c, doc):
    c.saveState()
    pw, ph = A4
    c.setFillColor(INDIGO); c.rect(0, ph - 9 * mm, pw, 9 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white); c.setFont("Plex-SB", 8)
    c.drawString(20 * mm, ph - 5.8 * mm, "iMSA Sentinel")
    c.setFont("Plex", 8); c.setFillColor(colors.HexColor("#c9cdea"))
    c.drawString(20 * mm + c.stringWidth("iMSA Sentinel", "Plex-SB", 8) + 6, ph - 5.8 * mm, "Tutoriel d'utilisation")
    chap = getattr(doc, "chapter", "")
    if chap:
        c.drawRightString(pw - 20 * mm, ph - 5.8 * mm, chap)
    c.setStrokeColor(LINE); c.setLineWidth(0.5); c.line(20 * mm, 13 * mm, pw - 20 * mm, 13 * mm)
    c.setFont("Plex", 7.6); c.setFillColor(INK3)
    c.drawString(20 * mm, 9 * mm, "Une anomalie est un écart documentaire constaté, pas une fraude démontrée.")
    c.setFont("Plex-SB", 8.5); c.setFillColor(INDIGO)
    c.drawRightString(pw - 20 * mm, 9 * mm, str(doc.page))
    c.restoreState()


COVER_SHOT = None


def draw_cover(c, doc):
    pw, ph = A4
    c.saveState()
    c.setFillColor(INDIGO); c.rect(0, 0, pw, ph, stroke=0, fill=1)
    # trame discrète rappelant les zones d'un formulaire
    c.setStrokeColor(colors.HexColor("#2c3681")); c.setLineWidth(0.5)
    for i in range(0, int(pw), 18):
        c.line(i, 0, i, ph)
    for j in range(0, int(ph), 18):
        c.line(0, j, pw, j)
    # logo (case cochée, comme dans l'application)
    x0, y0 = 22 * mm, ph - 40 * mm
    c.setFillColor(colors.HexColor("#3a46a8")); c.roundRect(x0, y0, 14 * mm, 14 * mm, 3 * mm, stroke=0, fill=1)
    c.setStrokeColor(OCHRE); c.setLineWidth(2.6); c.setLineCap(1); c.setLineJoin(1)
    p = c.beginPath(); p.moveTo(x0 + 4 * mm, y0 + 7.2 * mm); p.lineTo(x0 + 6.4 * mm, y0 + 4.8 * mm)
    p.lineTo(x0 + 10.4 * mm, y0 + 9.6 * mm); c.drawPath(p, stroke=1, fill=0)
    c.setFillColor(colors.white); c.setFont("Plex-SB", 11)
    c.drawString(x0 + 18 * mm, y0 + 8 * mm, "iMSA Sentinel")
    c.setFillColor(colors.HexColor("#b9bfe6")); c.setFont("Plex", 8.5)
    c.drawString(x0 + 18 * mm, y0 + 3.4 * mm, "Contrôle des justificatifs de dépenses de santé")
    # titre
    c.setFillColor(OCHRE); c.setFont("Plex-SB", 11)
    c.drawString(22 * mm, ph - 70 * mm, "TUTORIEL D'UTILISATION")
    c.setFillColor(colors.white); c.setFont("Plex-Bd", 40)
    c.drawString(22 * mm, ph - 88 * mm, "Contrôler un dossier")
    c.drawString(22 * mm, ph - 103 * mm, "pas à pas")
    c.setFont("Plex", 12.5); c.setFillColor(colors.HexColor("#d5d9f2"))
    lines = ["Voir les 15 zones du bordereau CERFA 12278 encadrées,",
             "comprendre les 22 contrôles face à la facture B2,",
             "décider preuves à l'appui, piloter l'activité de la caisse."]
    for k, l in enumerate(lines):
        c.drawString(22 * mm, ph - (118 + 7 * k) * mm, l)
    # capture
    if COVER_SHOT:
        path, size = COVER_SHOT
        w = pw - 44 * mm + 14 * mm
        h = w * size[1] / size[0]
        x, y = 22 * mm, 30 * mm
        c.setFillColor(colors.HexColor("#141a4d")); c.rect(x + 3, y - 3, w, h, stroke=0, fill=1)
        c.drawImage(str(path), x, y, w, h)
        c.setStrokeColor(colors.HexColor("#4a55b5")); c.setLineWidth(0.8); c.rect(x, y, w, h, stroke=1, fill=0)
        # version 3.0 : ce tutoriel décrit le mode expert (bandeau entre le sous-titre et la capture)
        by = y + h + 3 * mm
        c.setFillColor(OCHRE); c.roundRect(22 * mm, by, pw - 44 * mm, 12 * mm, 2 * mm, stroke=0, fill=1)
        c.setFillColor(INDIGO); c.setFont("Plex-SB", 10)
        c.drawString(26 * mm, by + 7 * mm, "Version 3.0 : ce tutoriel décrit le MODE EXPERT (Autres actions, puis Mode expert).")
        c.setFont("Plex", 8.6)
        c.drawString(26 * mm, by + 2.6 * mm, "Pour le parcours essentiel, affiché par défaut, lisez d'abord le guide d'une page (docs/GUIDE_1_PAGE.pdf).")
    c.setFillColor(INDIGO); c.rect(0, 0, pw, 26 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white); c.setFont("Plex-SB", 9)
    c.drawString(22 * mm, 15 * mm, "Mode expert de la version 3.0  ·  contenu et captures de la version 2.0, toujours valables en mode expert")
    c.setFont("Plex", 8.5); c.setFillColor(colors.HexColor("#b9bfe6"))
    c.drawString(22 * mm, 10 * mm, "Défi iMSA · Hackathon IA for Impact · octobre 2026 · traitement 100 % local")
    c.restoreState()


# ================================================================== CONTENU
def content():
    s = []
    # ---------------------------------------------------------------- page 2 : sommaire
    s.append(NextPageTemplate("normal"))
    s.append(PageBreak())
    s.append(P("Sommaire", "h1"))
    s.append(Rule(W, 2.2, OCHRE, 34 * mm, after=12))
    toc = TableOfContents(levelStyles=[S["toc0"], S["toc1"]], dotsMinLevel=0)
    toc.dotsMinLevel = 0
    s.append(toc)

    # ---------------------------------------------------------------- 1
    s += H1(1, "Avant de commencer",
            "iMSA Sentinel fait à la place de l'agent la comparaison ligne à ligne entre ce que la clinique a "
            "signé et ce qu'elle facture. L'agent ne regarde plus que les écarts, avec la preuve sous les yeux.")
    s += H2("Les deux documents d'un dossier")
    s += table(["", "Bordereau de facturation", "Facture structurée"], [
        ["Format", "image JPG ou PNG (CERFA 12278 / S 3404)", "fichier TXT « B2 » à positions fixes"],
        ["Contenu", "15 zones : identifiants, prestations, honoraires, sous-totaux, signatures, code CERFA",
         "enregistrements numérotés (types 1 à 6) : en-têtes, actes, codes CCAM, totaux"],
        ["Lecture", "OCR local : deux moteurs, plusieurs lectures par champ, vote",
         "lecture exacte aux positions du cahier des charges"],
    ], [0.16, 0.42, 0.42], first_bold=True)
    s.append(P("Un <b>dossier</b> est une paire bordereau + facture. Le corpus fourni en contient 55, issus de trois "
               "établissements, chacun avec sa propre mise en page de bordereau."))
    s += H2("Le principe fondamental")
    s += callout("important", [
        "<b>Une anomalie est un écart documentaire constaté, pas une fraude démontrée</b>, ni la preuve qu'un soin a "
        "ou n'a pas été réalisé. L'application ne calcule aucune « probabilité de fraude » et n'extrapole aucune "
        "économie.",
        "C'est toujours l'agent qui conclut. Chaque décision est horodatée, signée et conservée."],
        "Une règle d'or")
    s += H2("Les cinq statuts d'un contrôle")
    s.append(P("Chacun des 22 contrôles reçoit, pour chaque dossier, exactement un statut :"))
    s += table(["Statut", "Signification", "Ce que vous faites"], [
        [status_chip("Conforme", hexc(OK), OK_SOFT), "Les deux documents concordent.", "Rien."],
        [status_chip("Anomalie", hexc(ANO), ANO_SOFT), "Écart constaté avec une lecture fiable.",
         "Vérifier visuellement, puis confirmer l'écart ou le déclarer faux positif."],
        [status_chip("Non vérifiable", hexc(NV), NV_SOFT),
         "La lecture du bordereau est douteuse (moteurs en désaccord, zone illisible).",
         "Lire vous-même la zone ; corriger la lecture si besoin. Jamais compté comme conforme."],
        [status_chip("Non applicable", hexc(NA), NA_SOFT),
         "La règle ne concerne pas ce dossier (ex. pas de zone 7).", "Rien."],
        [status_chip("Erreur technique", hexc(ERR), ERR_SOFT),
         "Le contrôle n'a pas pu s'exécuter. Les autres contrôles ne sont pas affectés.",
         "Signaler à l'administrateur."],
    ], [0.22, 0.42, 0.36])

    # ---------------------------------------------------------------- 2
    s += H1(2, "Installer et lancer",
            "L'installation se fait une seule fois. Ensuite, l'application démarre en un double-clic et "
            "fonctionne sans Internet.")
    s += H2("Prérequis")
    s += bullets([
        "<b>Python 3.10 à 3.13</b> (3.12 recommandé), à télécharger sur python.org. Sous Windows, cochez "
        f"{ui('Add python.exe to PATH')} pendant l'installation.",
        "Une connexion Internet <b>pendant l'installation uniquement</b>, pour télécharger les bibliothèques.",
        "<b>Tesseract OCR</b>, le second moteur de lecture. Il est recommandé et installé automatiquement sous "
        "Windows."])
    s += H2("Windows")
    s += steps([
        ("Récupérer le projet", f"Sur GitHub, {ui('Code')} → {ui('Download ZIP')}, puis décompressez l'archive. "
                                f"Vous pouvez aussi utiliser {code('git clone')}."),
        ("Installer (une seule fois)", f"Double-cliquez sur {code('INSTALLER.bat')}. Le script crée un "
                                       "environnement isolé, installe les bibliothèques et Tesseract (via winget). "
                                       "Comptez quelques minutes."),
        ("Lancer", f"Double-cliquez sur {code('LANCER.bat')}. Le navigateur s'ouvre sur "
                   f"{code('http://127.0.0.1:8000')}. Laissez la fenêtre noire ouverte : la fermer arrête "
                   "l'application."),
    ])
    s += H2("macOS et Linux")
    s += codeblock(["# second moteur OCR (facultatif)",
                    "brew install tesseract            # macOS",
                    "sudo apt install tesseract-ocr    # Debian / Ubuntu",
                    "",
                    "./lancer.sh                       # installe au premier lancement, puis démarre"])
    s += callout("astuce", "Si le port 8000 est déjà utilisé, l'application prend automatiquement le port libre "
                           "suivant et l'affiche dans la console (par exemple http://127.0.0.1:8001).")
    s += H2("Première mise en service")
    s.append(P("Au tout premier lancement, l'application extrait le corpus de façon sécurisée (originaux en lecture "
               "seule, empreintes SHA-256) et applique les 22 contrôles aux 55 dossiers. Cela prend quelques "
               "secondes, car les lectures OCR du corpus sont fournies en cache. Elle vous demande ensuite de créer "
               "le compte administrateur."))
    s += side("00-mise-en-service.png", (*q(340, 98), *q(658, 498)), "Écran de première mise en service.", lambda: [
        *steps([("Identifiant et nom", "Par exemple « admin » et « Administrateur »."),
                ("Mot de passe", "8 caractères minimum. Vous le choisissez : aucun mot de passe n'est fourni par "
                                 "défaut ni codé en dur."),
                ("Mode démonstration", "Facultatif : cochez la case pour créer aussi agent1, agent2, superviseur et "
                                       "auditeur, avec le même mot de passe. À ne pas utiliser en production."),
                ("Valider", f"{ui('Créer le compte et entrer')}.")]),
    ], img_w=70 * mm)
    s += H2("Les comptes et leurs droits")
    s += table(["Compte", "Rôle", "Peut…"], [
        ["agent1, agent2", "Agent de contrôle", "Ouvrir les dossiers non affectés et les siens, décider, corriger "
                                                "une lecture, importer, simuler, transmettre."],
        ["superviseur", "Gestionnaire de caisse", "Tout ce que fait l'agent, plus affecter, prioriser, "
                                                  "enregistrer une décision motivée, clôturer, voir la supervision "
                                                  "et le journal d'audit."],
        ["auditeur", "Auditeur", "Tout consulter, sans rien modifier."],
        ["(votre compte)", "Administrateur technique", "Synchronisation, recalcul forcé, sauvegardes, purge des "
                                                    "métadonnées."],
    ], [0.2, 0.24, 0.56], mono_first=True)

    # ---------------------------------------------------------------- 3
    s += H1(3, "Se repérer et trouver un dossier",
            "Connectez-vous avec agent1. Vous arrivez sur la vue d'ensemble, votre point de départ.")
    marks = [(1, *q(75, 200)), (2, *q(330, 19)), (3, *q(560, 150)), (4, *q(300, 217)), (5, *q(780, 217)),
             (6, *q(915, 92)), (7, *q(75, 562))]
    s += fig("02-vue-ensemble.png", "La vue d'ensemble d'un agent.", marks=marks)
    s += legend([
        (1, f"<b>Menu</b> : toutes les fonctions. Le groupe {ui('Pilotage')} n'apparaît que pour le gestionnaire, "
            "l'administrateur et l'auditeur."),
        (2, "<b>Recherche</b> : un n° de dossier, de facture ou un établissement."),
        (3, "<b>Compteurs</b> : dossiers accessibles, à contrôler, en cours, avec anomalie, lecture humaine requise, "
            "déjà vérifiés. Chaque compteur indique son dénominateur."),
        (4, "<b>Ordre de traitement proposé</b> : les dossiers sont triés par un score paramétrable (écarts "
            "d'identification, actes présents d'un seul côté, montants, signatures). Ce n'est pas une norme MSA."),
        (5, "<b>Historique des décisions</b> et raccourcis vers <b>Mes dossiers</b>."),
        (6, f"{ui('Démarrer la revue rapide')} : les anomalies une par une (chapitre 7)."),
        (7, "<b>Version et moteurs OCR actifs</b>. Un avertissement apparaît ici si Tesseract est absent."),
    ])
    s += H2("La liste des dossiers")
    s += fig("03-dossiers.png", "Menu Dossiers : tous les dossiers accessibles, avec la bande des 15 zones.")
    s += bullets([
        "<b>Filtres</b> : texte libre, statut d'instruction, résultat, règle, famille de mise en page, et "
        "<b>zone</b> (par exemple : les dossiers dont la zone 10 est en anomalie).",
        "<b>Bande des 15 zones</b> : 15 petits carrés colorés résument chaque dossier d'un coup d'œil, avec les "
        "mêmes couleurs que sur le bordereau.",
        "Un agent voit les dossiers <b>non affectés</b> et <b>les siens</b>. Le bouton "
        f"{ui('Prendre le dossier')} vous l'affecte.",
    ])

    # ---------------------------------------------------------------- 4 : LES 15 ZONES
    s += H1(4, "Contrôler les 15 zones du bordereau, pas à pas",
            "C'est le cœur de l'application. En ouvrant un dossier, vous voyez immédiatement les 15 zones du "
            "bordereau encadrées selon leur résultat : ce qui est conforme, ce qui est en anomalie, ce qui est "
            "douteux. Un clic sur une zone montre la preuve.")
    s += H2("Étape 1 — Ouvrir le dossier : la vue globale")
    s.append(P(f"Ouvrez {code('Facture1_04')} depuis la vue d'ensemble ou le menu {ui('Dossiers')}. L'onglet "
               f"{ui('15 zones')} s'affiche par défaut."))
    marks = [(1, *q(200, 85)), (2, *q(178, 138)), (3, *q(445, 300)), (4, *q(415, 375)), (5, *q(585, 160)),
             (6, *q(600, 340)), (7, *q(870, 300)), (8, *q(260, 584))]
    s += fig("10-zones-vue-globale.png", "Facture1_04 : les 15 zones encadrées. Z8 est rouge, les autres vertes.",
             marks=marks, width=0.9 * W)
    s += legend([
        (1, f"<b>En-tête du dossier</b> : établissement, FINESS, n° de facture, montant, résultat. Dessous : le statut "
            f"et les boutons {ui('Prendre le dossier')}, {ui('Transmettre')}, {ui('Simuler une modification')}, "
            f"{ui('Réanalyser')}, {ui('Rapport PDF')}, {ui('JSON')}."),
        (2, f"Case {ui('15 zones')} : affiche ou masque les encadrements (bouton équivalent sous l'image)."),
        (3, "<b>Le bordereau</b> : chaque zone porte un cadre de couleur et un badge (Z1 à Z15) avec une icône. "
            "L'intérieur du cadre reste transparent : le document n'est jamais masqué."),
        (4, "<b>Z8 en rouge</b> : le seul écart de ce dossier."),
        (5, "<b>Pastilles Z1 à Z15</b>, de la même couleur que les cadres."),
        (6, "<b>Cartes de synthèse</b> : statut de chaque zone et nombre de règles concernées."),
        (7, "<b>Facture structurée</b> (TXT), avec la règle des positions."),
        (8, "<b>Légende permanente</b> des couleurs et bouton " + ui("Masquer les encadrements") + "."),
    ])
    s += H2("Étape 2 — Lire les couleurs")
    s += table(["Cadre", "Statut", "Ce que cela veut dire", "Ce que vous faites"], [
        [status_chip("vert", "#16A34A", colors.HexColor("#e7f6ec")), "Conforme",
         "Tous les contrôles applicables de la zone concordent, avec des lectures fiables.", "Rien."],
        [status_chip("rouge", "#DC2626", colors.HexColor("#fde8e8")), "Anomalie",
         "Au moins un contrôle de la zone constate un écart.", "Ouvrir la zone, comparer, décider."],
        [status_chip("gris", "#4B5563", colors.HexColor("#eceef1")), "Non vérifiable",
         "La lecture est douteuse (moteurs en désaccord, zone illisible), ou la conformité ne repose que sur une "
         "lecture isolée.", "Lire vous-même la zone ; corriger ou valider la lecture."],
        [status_chip("pointillés", "#9CA3AF", colors.HexColor("#f6f7f8")), "Non applicable",
         "Aucun contrôle ne s'applique (par exemple, pas d'actes exécutés : zones 9 et 11).", "Rien."],
        [status_chip("orange", "#B45309", colors.HexColor("#fef3c7")), "Erreur technique",
         "Un contrôle n'a pas pu s'exécuter.", "Signaler à l'administrateur."],
    ], [0.15, 0.17, 0.4, 0.28])
    s += bullets([
        "<b>« Contrôles également incertains »</b> : la zone est rouge, mais l'un de ses autres contrôles est "
        "douteux. Le rouge l'emporte, et l'incertitude reste signalée.",
        "<b>« Résultats mixtes »</b> : les contrôles d'une même zone n'ont pas tous le même résultat ; la fiche les "
        "détaille un par un.",
        "La couleur n'est jamais seule : chaque zone a aussi une icône, un libellé, une infobulle au survol et peut "
        "être atteinte au clavier.",
    ])
    s += callout("retenir", "Une zone n'est <b>jamais verte par défaut</b>. Si l'application n'est pas sûre de sa "
                            "lecture, la zone est grise et vous demande de regarder.")
    s += H2("Étape 3 — Cliquer sur une zone conforme", need=150)
    s += fig("11-zone-conforme.png", "Clic sur Z2 : la zone est cadrée sur le bordereau, la fiche s'ouvre et la "
                                     "position du FINESS est surlignée dans le fichier (ligne 1, positions 2 à 10).")
    s.append(P("La sélection ajoute un <b>halo bleu</b> autour de la zone ; la couleur de conformité reste visible à "
               "l'intérieur. La fiche indique pourquoi la zone est verte et quelles données ont été comparées : "
               "200200145 sur le bordereau et 200200145 dans le fichier."))
    s += H2("Étape 4 — Examiner une zone en anomalie", need=120)
    s += fig("12-zone-anomalie.png", "Clic sur Z8 : 818,97 € sur le bordereau, 818,98 € dans TotalPrestations "
                                     "(ligne 12 surlignée). Contrôle R12 en anomalie.")
    s += side("13-zone-anomalie-detail.png", (q(470, 0)[0], q(0, 140)[1], q(733, 0)[0], q(0, 560)[1]),
              "Suite de la fiche de Z8.", lambda: [
        P("En faisant défiler la fiche, vous trouvez :"),
        *table(["Rubrique", "Contenu"], [
            ["Contrôles associés", "chaque règle de la zone, avec son résultat et ses boutons de décision "
                                   "(ici R12, puis R20 qui relie les zones 8, 12 et 13)"],
            ["Extraction du bordereau", "valeur brute et normalisée, accord des moteurs, lectures individuelles, "
                                        f"bouton {ui('Corriger / valider')}"],
            ["Facture TXT", "la donnée du fichier, sa ligne et ses positions"],
            ["Assistance", "ce qui a été comparé, ce qui n'a pas pu l'être, l'action recommandée"],
            ["Traçabilité", "gabarit, recalage, versions, historique de la zone"],
        ], [0.36, 0.64], first_bold=True)], img_w=62 * mm)
    s += steps([
        ("Comparer de vos yeux", "Regardez la zone sur l'image et la valeur surlignée dans le fichier. "
                                 "L'application montre ; c'est vous qui jugez."),
        ("Décider", f"Sous le contrôle : {ui('Confirmer l’écart')}, {ui('Faux positif')} (motif obligatoire), "
                    f"{ui('Revue complémentaire')} ou {ui('Commenter')} (chapitre 6)."),
        ("Passer à la suite", f"{ui('Suivante')} ou la touche {code(']')} ouvre la zone suivante ; "
                              f"{code('[')} revient en arrière ; {code('Échap')} revient à la vue globale."),
    ])
    s += H2("Étape 5 — Comprendre une zone non vérifiable", need=110)
    s += fig("14-zone-non-verifiable.png", "Bordereau importé dont le montant total a été effacé : Z13 est grise, "
                                           "R20 est non vérifiable.")
    s.append(P("Ce dossier est un <b>test</b> : le bordereau Facture1_02 a été déposé après effacement du montant "
               "de la zone 13. L'application ne devine pas : elle déclare le contrôle R20 <b>non vérifiable</b> "
               "(« montant de la zone 13 illisible ») et la zone passe au gris. Sur le corpus réel, aucune zone "
               "n'est grise : les lectures y sont fiables."))
    s += callout("attention", "Deux lectures OCR qui se contredisent à égalité donnent toujours « non vérifiable », "
                              "même si l'une d'elles correspond au fichier. L'application ne choisit jamais la "
                              "lecture qui « arrange ».")
    s += H2("Étape 6 — Les tableaux, ligne par ligne (zones 6, 7 et 10)", need=110)
    s += fig("15-zone-tableau.png", "Facture1_09, Z6 : chaque prestation du bordereau est rapprochée de sa ligne "
                                    "du fichier ; PH7, présente dans le fichier (ligne 8), est absente du bordereau.")
    s += bullets([
        "Pour chaque ligne : code, n° GHS, montant, ligne du TXT et résultat du rapprochement.",
        "Une ligne du fichier absente du bordereau est listée à part, avec la zone où elle aurait dû figurer. "
        "Aucune position n'est inventée sur l'image.",
        "Cliquer sur une ligne du TXT dans la fiche la surligne dans le fichier.",
    ])
    s += H2("Étape 7 — Les signatures (zones 11 et 14)", need=110)
    s += fig("16-zone-signatures.png", "Facture1_01, Z11 : les huit cases de signature, chacune avec sa présence "
                                       "détectée. L'exécutant 201400330 n'a aucune signature (R18).")
    s.append(P(f"Chaque case indique « présent » ou « vide », l'encre mesurée et l'incertitude. Le bouton "
               f"{code('✎')} permet de confirmer à l'écran qu'une case est présente ou vide : c'est une correction "
               "tracée, comme pour une valeur. La zone 9 liste les exécutants lus dans le tableau des actes."))
    s += callout("retenir", "Seule la <b>présence</b> d'un tracé, d'un cachet ou d'une mention est détectée. "
                            "L'authenticité d'une signature n'est jamais jugée.")
    s += H2("Étape 8 — Corriger ou valider une lecture", need=120)
    s += side("17-correction-modal.png", (q(318, 0)[0], q(0, 168)[1], q(682, 0)[0], q(0, 428)[1]),
              "Fenêtre de correction de la zone 8.", lambda: [
        *steps([("Ouvrir", f"{ui('Corriger / valider')} dans la fiche de la zone."),
                ("Saisir", "la valeur telle qu'imprimée. Saisir la même valeur que la lecture la <b>valide</b> et "
                           "lève l'incertitude."),
                ("Enregistrer", "Le serveur vérifie le format. Les 22 contrôles et les 15 zones sont recalculés.")])],
        img_w=74 * mm)
    s += fig("18-correction-effet.png", "Après correction de Z8 à 818,98 € : R12 devient conforme, mais R20 passe "
                                        "en anomalie (818,98 + 28,80 ≠ 847,77). Le message annonce « Z12 Conforme → "
                                        "Anomalie, Z13 Conforme → Anomalie ».")
    s.append(P("La lecture d'origine est conservée, la correction vous est attribuée et elle peut être annulée : "
               "les couleurs reviennent alors à leur état initial. Ici, la correction a été annulée après la capture."))
    s += H2("Étape 9 — Le rapport")
    s += fig("58-rapport-zones.png", "Rapport PDF de Facture1_04 : section « Les 15 zones du bordereau » "
                                     "(tableau des statuts) et bordereau encadré avec les mêmes couleurs.")
    s += H2("Raccourcis du cockpit")
    s += table(["Touche", "Action"], [
        ["]", "zone suivante"], ["[", "zone précédente"], ["Échap", "revenir à la vue globale"],
        ["molette", "zoomer ; les cadres suivent l'image"], ["glisser", "se déplacer dans l'image"],
        ["Tab puis Entrée", "atteindre et ouvrir une zone au clavier"],
    ], [0.3, 0.7], mono_first=True)

    # ---------------------------------------------------------------- 5 : 22 contrôles
    s += H1(5, "La vue des 22 contrôles",
            "Les 15 zones résument ; les 22 contrôles détaillent. L'onglet Contrôles présente chaque règle du "
            "cahier des charges, groupée de A à F.")
    s += fig("20-controles-22.png", "Onglet Contrôles de Facture1_04, contrôle R12 sélectionné : la zone 8 est "
                                    "cadrée sur l'image et la ligne 12 surlignée aux positions 42 à 49.")
    s += side("20-controles-22.png", (q(465, 0)[0], q(0, 145)[1], q(733, 0)[0], q(0, 600)[1] - 6),
              "Détail du contrôle R12.", lambda: [
        P("Ce que contient le panneau de détail :"),
        *table(["Rubrique", "Contenu"], [
            ["Bordereau / Fichier", "les deux valeurs confrontées"],
            ["Écart mesuré", "la différence (ici 0,01 €)"],
            ["Incertitude", "la fiabilité de la lecture"],
            ["Cahier des charges", "la phrase d'origine"],
            ["Convention retenue", "l'interprétation appliquée"],
            ["Prochaine étape", "ce qu'il reste à faire"],
            ["Lectures OCR", "chaque lecture : moteur, prétraitement, texte, confiance"],
        ], [0.42, 0.58], first_bold=True)], img_w=62 * mm)
    s += H2("Exemple : une signature manquante")
    s += fig("22-controle-signature.png", "Facture2_05, R21 : la zone 14 (signature du directeur) est vide.",
             width=0.88 * W)
    s += H2("L'onglet « Lectures OCR »")
    s.append(P("Chaque champ du bordereau est lu plusieurs fois : quatre lectures RapidOCR et deux lectures "
               "Tesseract, sur l'image brute, sur l'image sans les traits du formulaire et sur une version étirée. "
               "Chaque lecture est validée par le format attendu (FINESS à 9 chiffres, montant, code CCAM…), puis "
               "les lectures votent ; l'accord de deux moteurs différents prime."))
    s += table(["Accord", "Signification", "Effet sur le contrôle"], [
        ["concordant", "toutes les lectures valides donnent la même valeur", "fiable"],
        ["majoritaire", "une valeur est soutenue par plus de moteurs différents", "fiable"],
        ["lecture unique", "une seule lecture valide", "zone grise si c'est la seule preuve d'une conformité"],
        ["égalité", "deux valeurs différentes avec autant de soutiens", "non vérifiable"],
        ["divergent", "deux moteurs soutiennent des valeurs différentes", "non vérifiable"],
        ["illisible", "aucune lecture ne respecte le format", "non vérifiable"],
        ["vide", "la zone ne contient pas d'encre", "selon la règle"],
    ], [0.2, 0.46, 0.34], mono_first=True)
    s += fig("23-lectures-ocr.png", "Onglet Lectures OCR : toutes les valeurs extraites, avec leur niveau d'accord "
                                    "et un bouton de correction.")
    s += H2("L'onglet « Observations »")
    s += fig("24-observations.png", "Facture2_06 : fichier décalé d'un caractère, signalé dans les Observations.",
             width=0.8 * W)
    s.append(P("Certaines particularités ne relèvent d'aucune des 22 règles mais méritent d'être signalées : en-tête "
               "de type 0 absent, ligne trop courte, lignes identiques, positions décalées, incohérence interne au "
               "bordereau, image de mauvaise qualité. Elles ne sont jamais comptées comme des anomalies."))
    s += callout("attention", [
        "<b>Facture2_06</b> : le fichier est décalé d'un caractère à partir de la position 11. Les règles "
        "s'appliquent aux positions officielles ; la lecture décalée est montrée comme une simple hypothèse et "
        "aucun écart monétaire non fiable n'est chiffré.",
        "<b>Facture2_04</b> : le bordereau porte le n° de facture et le n° d'assuré d'un autre dossier. Le "
        "rapprochement est signalé <b>ambigu</b> au lieu d'être supposé correct."])

    # ---------------------------------------------------------------- 6 : décider
    s += H1(6, "Décider et conclure",
            "Chaque contrôle peut recevoir une décision, et chaque dossier un statut. Tout est horodaté, signé "
            "et visible dans l'historique.")
    s += H2("Les actions sur un contrôle")
    s += side("25-decision.png", (q(466, 0)[0], q(0, 240)[1], q(733, 0)[0], q(0, 548)[1]),
              "Contrôle R03 de Facture1_07, avec ses boutons de décision.", lambda: [
        *table(["Bouton", "Effet"], [
            [ui("Marquer examiné"), "vous avez regardé ce contrôle"],
            [ui("Confirmer l'écart"), "l'écart est réel ; commentaire facultatif"],
            [ui("Faux positif"), "l'écart n'en est pas un ; <b>motif obligatoire</b>"],
            [ui("Revue complémentaire"), "un autre avis est nécessaire"],
            [ui("Commenter"), "ajouter une note"],
            [ui("Corriger la lecture"), "l'OCR s'est trompé (chapitre 4, étape 8)"],
        ], [0.45, 0.55])], img_w=66 * mm)
    s += bullets([
        "Les décisions sont prises <b>règle par règle</b> : confirmer R12 ne confirme pas R20.",
        "Une décision peut être <b>annulée</b>, avec un motif ; l'annulation est tracée.",
        "Une décision ne change jamais le statut calculé d'une règle ou d'une zone. Seule une correction de lecture, "
        "qui modifie les données d'entrée, entraîne un recalcul.",
    ])
    s += H2("Le statut du dossier")
    s.append(P("La liste déroulante en haut à gauche de l'écran change le statut. Les huit statuts suivent "
               "l'instruction :"))
    s += table(["Statut", "Quand l'utiliser"], [
        ["À contrôler", "état initial"],
        ["En analyse", "vous êtes en train d'examiner le dossier"],
        ["Anomalie à vérifier", "un écart attend une vérification"],
        ["Revue complémentaire nécessaire", "un second avis est demandé"],
        ["Écart confirmé", "au moins un écart est confirmé après vérification"],
        ["Faux positif reconnu", "les écarts signalés n'en sont pas"],
        ["Contrôle terminé", "l'examen est fini"],
        ["Clôturé", "décision finale, <b>réservée au gestionnaire de caisse</b>"],
    ], [0.38, 0.62], first_bold=True)
    s += H2("Tracer et rendre compte")
    s += side("26-historique.png", (q(466, 0)[0], q(0, 150)[1], q(733, 0)[0], q(0, 250)[1]),
              "Onglet Historique de Facture1_07.", lambda: [
        P("Sur <b>Facture1_07</b>, le contrôle R03 signale le lot 574 sur le bordereau et 575 dans le fichier. "
          "L'agent a vérifié l'image, confirmé l'écart avec un commentaire, puis passé le dossier en « Écart "
          "confirmé ». Les deux actions apparaissent dans l'historique et dans le journal d'audit."),
        P(f"{ui('Transmettre')} envoie le dossier au superviseur avec un motif obligatoire.")], img_w=74 * mm)
    s += H2("L'assistant de contrôle")
    s += side("27-assistant.png", (q(466, 0)[0], q(0, 318)[1], q(733, 0)[0], q(0, 590)[1]),
              "L'assistant explique le contrôle R03.", lambda: [
        P(f"{ui("Ouvrir l'assistant de contrôle")} (bas du panneau central) propose : résumé du dossier, « Que "
          "dois-je faire ? », écarts de montant, éléments à vérifier. Vous pouvez aussi poser une question, par "
          "exemple « pourquoi R03 ? »."),
        *callout("retenir", "L'assistant est <b>déterministe</b> : il ne répond qu'à partir du dossier et du "
                            "cahier des charges, sans service externe, et ne conclut jamais à une fraude.")],
        img_w=66 * mm)

    # ---------------------------------------------------------------- 7 : revue rapide
    s += H1(7, "La revue rapide",
            "Pour traiter une série d'écarts sans changer d'écran : les anomalies défilent une par une, par "
            "priorité, avec la zone annoncée et des raccourcis clavier.")
    s += fig("30-revue-rapide.png", "Revue rapide : « Vous vérifiez la zone Z2 — N° FINESS de l'établissement ». "
                                    "La zone est cadrée et la position du fichier surlignée.")
    s += table(["Touche", "Action"], [
        ["C", "confirmer l'écart"], ["F", "faux positif (motif demandé)"], ["R", "revue complémentaire"],
        ["L", "corriger la lecture"], ["M", "commenter"], ["N ou →", "élément suivant"],
        ["P ou ←", "élément précédent"],
    ], [0.3, 0.7], mono_first=True)
    s += bullets([
        f"{ui('Raccourcis')} permet de changer chaque touche ; le choix est mémorisé dans votre navigateur.",
        "Les touches sont ignorées pendant une saisie.",
        f"La case {ui('Inclure les non vérifiables')} ajoute les contrôles douteux à la file.",
        "Une décision n'est affichée comme enregistrée qu'après confirmation par le serveur.",
    ])

    # ---------------------------------------------------------------- 8 : simulation + import
    s += H1(8, "Tester l'application : simulation et import",
            "Deux façons de vérifier que l'application lit vraiment chaque document : modifier une copie d'un "
            "dossier existant, ou déposer vos propres fichiers.")
    s += H2("Simuler une modification (sans fichier)")
    s += side("31-simulation-modal.png", (q(318, 0)[0], q(0, 176)[1], q(682, 0)[0], q(0, 420)[1]),
              "Simulation sur Facture3_13 : NumeroLot 925 → 999.", lambda: [
        *steps([("Ouvrir un dossier", f"Par exemple {code('Facture3_13')}, qui n'a aucun écart."),
                ("Simuler", f"{ui('Simuler une modification')}, choisir la donnée du fichier (ici NumeroLot, "
                            "3 caractères) et saisir la nouvelle valeur."),
                ("Créer", f"{ui('Créer la simulation')}. La copie est analysée par le moteur réel.")])],
        img_w=72 * mm)
    s += fig("33-simulation-dossier.png", "La copie simulée : R03 et Z3 en anomalie (925 sur le bordereau, 999 "
                                          "dans le fichier modifié).")
    s += callout("retenir", "Le dossier d'origine n'est jamais modifié. La copie est <b>privée</b> (seul son auteur "
                            "la voit, sauf affectation), marquée « Simulation » et <b>exclue des statistiques</b>.")
    s += H2("Importer un nouveau dossier", need=100)
    s += steps([
        ("Ouvrir l'import", f"Menu {ui('Import · simulation')}."),
        ("Choisir les fichiers", "Un bordereau (JPG ou PNG) et sa facture structurée (TXT au format B2)."),
        ("Donner un libellé", "Facultatif, par exemple « Test : montant modifié »."),
        ("Lancer l'analyse", f"{ui('Déposer et analyser')}. Le traitement se fait en arrière-plan : comptez 15 à 40 "
                             "secondes pour une image nouvelle, quelques secondes si elle est déjà connue."),
    ])
    s += fig("34-import.png", "L'écran d'import : dépôt, libellé, puis suivi des traitements.")
    s += H2("Exercice : provoquer un écart de montant")
    s.append(P("Prenez une paire du corpus, modifiez le fichier TXT avec le Bloc-notes et vérifiez que "
               "l'application détecte la modification. Les fichiers sont dans "
               f"{code('data/corpus/General-main/')} (créé au premier lancement)."))
    s += steps([
        ("Copier le fichier", f"Copiez {code('Factures txt/Facture1_02.txt')} sous un autre nom, par exemple "
                              f"{code('Facture1_02_modifiee.txt')}."),
        ("Modifier le total", "Sur la ligne qui commence par 5, les positions 42 à 49 portent TotalPrestations : "
                              f"{code('00081897')} (818,97 €). Remplacez-le par {code('00082897')} (828,97 €)."),
        ("Déposer", f"Importez {code('Bordereaux jpg/Facture1_02.jpg')} avec votre TXT modifié : Z8 et R12 passent "
                    "en rouge."),
    ])
    s += codeblock(["position        1        10        20        30        40  42    49",
                    "                |        |         |         |         |   |      |",
                    "avant  5200200145 2xxxxxxxxxx020700026080000200900081897000818970...",
                    "après  5200200145 2xxxxxxxxxx020700026080000200900082897000818970...",
                    "(n° d'assuré masqué dans ce tutoriel : x)"])
    s += callout("attention", [
        "Gardez la longueur des lignes : remplacez un caractère par un autre, sans en ajouter ni en supprimer. "
        "Sinon les positions sont décalées, ce que l'application signale aussi.",
        "Le bordereau doit suivre l'une des trois mises en page du corpus. Sinon il est signalé « mise en page non "
        "reconnue » et les contrôles qui dépendent de l'image passent en non vérifiable."])

    # ---------------------------------------------------------------- 9 : comparaison
    s += H1(9, "Comparer deux bordereaux",
            "Le module de comparaison aligne deux images pour repérer ce qui a changé, zone par zone : une valeur "
            "réécrite, une signature effacée, un document réutilisé.")
    s += fig("40-comparaison.png", "Comparaison de Facture2_01 et Facture2_05 : documents non homologues ; Z4, Z5 "
                                   "et Z14 diffèrent, les 12 autres zones sont identiques.")
    s += bullets([
        f"Choisissez les dossiers <b>A</b> et <b>B</b>, puis {ui('Comparer')}. Trois modes : "
        f"{ui('Côte à côte')} (zoom synchronisé), {ui('Superposition')}, {ui('Carte des différences')}.",
        "<b>Vérification d'homologie</b> : si les identifiants diffèrent, les documents ne concernent pas le même "
        "dossier ; la comparaison est alors « exploratoire ».",
        "<b>Comparaison par zone (Z1 à Z15)</b> : pour chaque zone, « identique », « différence purement "
        "graphique » ou « différence documentaire », avec les valeurs lues dans A et dans B. Un clic cadre la zone "
        "sur les deux images.",
        "Une différence entre deux patients n'est pas une anomalie de facturation : la conformité JPG ↔ TXT se "
        "vérifie dans l'écran de contrôle de chaque dossier.",
    ])

    # ---------------------------------------------------------------- 10 : anomalies
    s += H1(10, "Anomalies et investigations",
            "Deux vues transversales pour travailler par type d'écart ou par piste de vérification.")
    s += fig("41-anomalies.png", "Menu Anomalies : tous les écarts du corpus, filtrables par règle, zone et "
                                 "établissement.")
    s.append(P("Chaque ligne donne le dossier, la règle, la zone, la valeur du bordereau, celle du fichier, l'écart, "
               "l'explication et la dernière décision. Un clic ouvre le dossier sur le contrôle concerné."))
    s += fig("42-investigations-regroupements.png", "Investigations : les regroupements d'alertes, des pistes "
                                                    "formulées au conditionnel.")
    s += bullets([
        "<b>Regroupements</b> : plusieurs alertes qui pourraient avoir une même origine (même n° GHS, identifiants du "
        "dossier, code différent entre les deux documents, écart de total expliqué par une ligne, lectures "
        "incertaines, fichier décalé).",
        "Ce sont des <b>hypothèses</b> à vérifier, jamais des conclusions.",
    ])

    # ---------------------------------------------------------------- 11 : gestionnaire
    s += H1(11, "Espace gestionnaire de caisse",
            "Connectez-vous avec le compte superviseur. Le groupe Pilotage apparaît dans le menu.")
    s += fig("50-supervision.png", "Supervision de caisse : indicateurs avec leurs dénominateurs.")
    s += H2("La matrice des 15 zones", need=120)
    s += fig("51-supervision-matrice.png", "Pour chaque zone, le nombre de dossiers par statut (55 dossiers, 825 "
                                           "zones évaluées). Un clic sur une cellule ouvre la liste filtrée.")
    s.append(P("Lecture du corpus : Z10 (actes médicaux) est la zone la plus souvent en anomalie (11 dossiers), "
               "suivie de Z6 (10) et de Z8 et Z12 (7 chacune). Z9 et Z11 sont non applicables pour 15 dossiers sans "
               "actes exécutés. Aucune zone n'est non vérifiable."))
    s += H2("Le volet financier", need=120)
    s += fig("52-supervision-finances.png", "Volet financier et répartition par établissement.")
    s += table(["Niveau", "Corpus", "Ce qu'il mesure"], [
        ["Montant total facturé", "60 735,32 €", "TotalPrestations + TotalHonoraires des 55 fichiers"],
        ["Montant en anomalie (dédoublonné)", "3 784,70 €", "écarts constatés, sans compter deux fois le total et "
                                                            "ses lignes"],
        ["Montant facturé des dossiers en alerte", "56 192,32 €", "contexte : la facture entière des dossiers avec "
                                                                  "au moins un écart"],
        ["Écarts confirmés par un agent", "selon les décisions", "règle par règle, d'après la dernière décision non "
                                                                 "annulée"],
        ["Indu établi, montants récupérés", "non calculable", "aucune donnée de recouvrement dans le corpus"],
    ], [0.34, 0.2, 0.46], first_bold=True)
    s += callout("important", "Aucune extrapolation d'économies : un écart documentaire n'est ni un indu établi, "
                              "ni une économie réalisée.")
    s += H2("Activité et productivité")
    s.append(P("Le panneau « Activité et productivité mesurées » affiche des temps <b>mesurés</b> : lecture OCR d'un "
               "bordereau, analyse, temps de revue <b>actif</b> (une pause n'est pas comptée), délais jusqu'à la "
               "première décision et jusqu'à la clôture. Sans mesure, la valeur est « indisponible ». Aucun gain "
               "n'est annoncé."))
    s += H2("La qualité mesurée", need=150)
    s += fig("53-qualite.png", "Qualité mesurée : chaque taux affiche son effectif ; un faible effectif est signalé.")
    s += bullets([
        "Exactitude de l'OCR d'après les lectures validées ou corrigées par les agents.",
        "Désaccords entre moteurs par zone, et lectures illisibles.",
        "Précision et rappel des alertes, calculés uniquement sur les dossiers annotés.",
        "Une mesure impossible est affichée « indisponible », jamais 100 %.",
    ])
    s += H2("Instruire un dossier")
    s.append(P("Depuis l'écran de contrôle, le gestionnaire peut en plus affecter le dossier à un agent, passer sa "
               "priorité en haute, enregistrer une <b>décision motivée</b> et <b>clôturer</b> le dossier."))

    # ---------------------------------------------------------------- 12 : rapports
    s += H1(12, "Rapports, exports et administration")
    s += fig("54-rapports.png", "Menu Rapports : rapports par dossier, exports, et, pour l'administrateur, "
                                "synchronisation, recalcul, sauvegardes et traitements.")
    s += table(["Export", "Contenu", "Usage"], [
        ["Rapport PDF", "références et empreintes, synthèse, <b>15 zones</b> (tableau et bordereau encadré), 22 "
                        "résultats, preuves, observations, corrections, décisions", "revue, archivage"],
        ["Rapport JSON", "le même contenu, zones comprises, sous forme structurée", "intégration à un autre système"],
        ["CSV", "une ligne par dossier et par règle ; séparateur « ; », UTF-8 compatible Excel", "analyse, tableur"],
        ["Manifeste", "chaque fichier du corpus : type, taille, SHA-256, lecture seule", "intégrité"],
    ], [0.18, 0.56, 0.26], first_bold=True)
    s += H2("Administration (rôle administrateur)")
    s += bullets([
        f"{ui('Synchroniser le corpus')} : prend en compte les sources nouvelles, modifiées ou disparues.",
        f"{ui('Recalcul forcé de tous les dossiers')} : relit l'OCR et réapplique les règles, en arrière-plan.",
        f"{ui('Créer une sauvegarde')} : copie vérifiée de la base (empreinte et intégrité). La liste des sauvegardes est "
        "affichée ; la restauration se fait en ligne de commande, après une sauvegarde de sécurité automatique.",
        f"{ui('Effacer les métadonnées de session')} : efface les métadonnées de session (décisions, corrections, journal), toujours après une "
        "sauvegarde automatique.",
        "Le tableau <b>Traitements</b> suit les tâches en cours ou terminées ; deux traitements identiques ne sont "
        "jamais lancés en même temps.",
    ])
    s += fig("57-audit.png", "Journal d'audit (gestionnaire, administrateur, auditeur).", crop=(340, 0, 2160, 1290))
    s.append(P("Le journal trace les connexions, les consultations de dossiers, les décisions, les corrections, les "
               "imports, les simulations et les exports. Les données personnelles et les mots de passe n'y sont "
               "jamais recopiés."))

    # ---------------------------------------------------------------- 13 : fiabilité
    s += H1(13, "Fiabilité : règles, conventions et test à l'aveugle")
    s += fig("55-regles-zones.png", "Menu Règles et conventions : la table zone ↔ règles, puis chaque règle avec sa "
                                    "formulation d'origine et ses résultats sur le corpus.")
    s += H2("Le centre des conventions", need=120)
    s += fig("56-conventions.png", "Centre de validation des conventions : pour chaque ambiguïté, la convention "
                                   "appliquée et l'effet calculé d'une autre interprétation.")
    s += table(["Réf.", "Sujet", "Convention retenue", "Effet d'un changement"], [
        ["AMB-01", "Identifiant du formulaire (R01) : 12278*0 ou 12278*01", "préfixe exigé, version acceptée",
         "52 résultats changeraient"],
        ["AMB-02", "Zéros de cadrage des n° (R03, R04)", "comparaison numérique", "14 résultats"],
        ["AMB-03", "Actes imprimés sous leur code CCAM (R19)", "code CCAM, sinon code acte", "28 résultats"],
        ["AMB-04", "Lignes de détail de biologie (R14)", "détail de l'acte B", "non simulable"],
        ["AMB-05", "« Par mandat » ou cachet en zone 11 (R18)", "présence = signature présente", "non simulable"],
        ["AMB-06", "Formulations proches de R09 et R10", "R10 : LPP vs GHS lu en zone 6", "22 résultats"],
        ["AMB-07", "Un même code présent plusieurs fois", "occurrence par occurrence", "3 résultats"],
        ["AMB-08", "Aucun enregistrement de type 0", "pas une erreur", "55 résultats"],
    ], [0.11, 0.39, 0.28, 0.22], mono_first=True)
    s.append(P("Ces conventions sont des propositions de l'équipe, à valider par la MSA. Les effets sont calculés en "
               "rejouant la règle sur le corpus ; les résultats officiels ne sont pas modifiés.", "small"))
    s += H2("L'application n'a pas appris les réponses")
    s.append(P("Rien n'est entraîné sur le corpus et aucun résultat n'est mémorisé par dossier. Le cache OCR n'est "
               "utilisé que si l'image est identique octet pour octet (SHA-256) et que le code de lecture n'a pas "
               "changé. Ce qui vient du corpus, c'est la connaissance du <b>formulaire</b> : l'emplacement des 15 "
               "zones, comme un agent qui sait où regarder."))
    s.append(P(f"Le script {code('scripts/test_aveugle.py')} fabrique 17 dossiers qui n'existent pas dans le "
               "corpus et les analyse sans cache :"))
    s += table(["Famille", "Exemples", "Attendu"], [
        ["Documents authentiques transformés", "agrandis, recompressés, décalés, retournés à 180°, floutés",
         "aucune alerte"],
        ["Bordereaux falsifiés", "montant, lot ou n° de facture réécrits ; signature ou cachets effacés ; acte "
                                 "réécrit", "la règle concernée"],
        ["Factures TXT modifiées", "code CCAM, n° d'assuré, prestation supprimée, total, code inventé, n° GHS",
         "la règle concernée"],
    ], [0.3, 0.48, 0.22], first_bold=True)
    s += callout("retenir", "Version 2.0, deux moteurs OCR : <b>17 cas sur 17 exacts</b>, toutes les falsifications "
                            "détectées, aucune fausse alerte. Avec RapidOCR seul : aucune fausse alerte, aucune "
                            "falsification manquée, mais 6 cas demandent une vérification humaine supplémentaire.")
    s += codeblock(["python scripts/test_aveugle.py      # depuis la racine, environnement activé",
                    "set NO_TESS=1                      # (Windows) pour tester avec RapidOCR seul"])
    s += H2("Limites connues")
    s += bullets([
        "Seules les trois mises en page de bordereau du corpus sont reconnues ; il n'y a pas d'éditeur de gabarits.",
        "Une inclinaison de quelques degrés n'est pas corrigée (le retournement à 180° l'est).",
        "Aucun taux global de précision OCR n'est affirmé : il est mesuré sur les lectures validées par les agents.",
        "Les signatures sont détectées en présence, jamais en authenticité.",
        "Le score de priorité est un paramétrage proposé, pas une norme MSA.",
    ])

    # ---------------------------------------------------------------- 14 : démo
    s += H1(14, "Démonstration jury en 10 minutes",
            "Un parcours fondé sur des dossiers réels du corpus ; seule l'étape 9 crée une simulation, en direct.")
    s += table(["", "Durée", "Où", "Ce qu'il faut montrer"], [
        ["1", "30 s", "Vue d'ensemble", "55 dossiers, 50 avec au moins un écart, 1 non vérifiable. Un écart n'est "
                                        "pas une fraude."],
        ["2", "1 min 30", "Facture1_04 · 15 zones", "Les 15 cadres, Z8 rouge ; clic sur Z2 (conforme), puis Z8 : "
                                                    "818,97 € contre 818,98 €, ligne 12, positions 42-49."],
        ["3", "45 s", "Facture1_04 · Z8", "Revue complémentaire ou confirmer l'écart ; montrer l'historique."],
        ["4", "1 min", "Facture1_04 · correction", "Corriger Z8 à 818,98 : R12 conforme, mais Z12 et Z13 passent "
                                                   "au rouge (R20). Annuler."],
        ["5", "45 s", "Facture1_09 · Z6", "PH7 facturé mais absent du bordereau (R13), ligne 8 surlignée."],
        ["6", "45 s", "Facture1_01 · Z11, Facture2_05 · Z14", "Case de signature vide ; directeur absent. "
                                                              "Présence, jamais authenticité."],
        ["7", "45 s", "Revue rapide", "Les anomalies une à une, zone annoncée, raccourcis."],
        ["8", "45 s", "Facture2_06", "Fichier décalé signalé sans écart inventé ; regroupement d'alertes."],
        ["9", "1 min", "Facture3_13 · simulation", "NumeroLot 925 → 999 : R03 et Z3 en rouge ; original intact, "
                                                   "exclu des statistiques."],
        ["10", "1 min", "Compte superviseur", "Matrice des 15 zones, montants confirmés, temps actif, qualité "
                                              "mesurée, conventions (AMB-01 : 52), journal d'audit."],
    ], [0.05, 0.1, 0.27, 0.58])
    s += callout("astuce", "Pour la question « l'application connaît-elle les réponses ? », faites l'étape 9 avec "
                           "une valeur proposée par le jury.")

    # ---------------------------------------------------------------- 15
    s += H1(15, "Problèmes fréquents")
    s += table(["Symptôme", "Solution"], [
        ["« Python est introuvable »", "Installez Python 3.12 depuis python.org en cochant « Add python.exe to "
                                       "PATH », puis relancez INSTALLER.bat."],
        ["« error while attempting to bind on address … 8000 »", "Une autre application utilise le port 8000. "
                                                                 "L'application prend automatiquement le port suivant ; "
                                                                 "regardez l'adresse affichée dans la console."],
        ["Le navigateur ne s'ouvre pas", "Ouvrez vous-même http://127.0.0.1:8000 (ou le port affiché)."],
        ["Avertissement « Tesseract absent » en bas du menu", "L'application fonctionne avec RapidOCR seul, avec "
                                                              "davantage de zones grises. Installez Tesseract "
                                                              "(winget install UB-Mannheim.TesseractOCR), puis relancez."],
        ["Les cadres ne tombent pas sur les zones", "Le bordereau est peut-être incliné, ou d'une autre mise en page. "
                                                    "Masquez les encadrements et vérifiez à l'œil ; signalez le cas."],
        ["Un import ou une simulation reste « en analyse »", "La lecture OCR d'une image nouvelle prend 15 à 40 "
                                                            "secondes, davantage sur un PC lent. Actualisez la page."],
        ["« Mise en page non reconnue »", "Le bordereau ne suit aucune des trois mises en page du corpus. Les "
                                          "contrôles liés à l'image passent en non vérifiable."],
        ["Pas de comptes agent1, superviseur…", "Ils ne sont créés que si la case « Mode démonstration » a été "
                                                "cochée à la mise en service. Pour une démonstration, fermez "
                                                "l'application, supprimez data/sentinel.db et relancez : l'écran de "
                                                "mise en service réapparaît (les décisions sont perdues, les "
                                                "documents ne sont pas touchés)."],
        ["Mot de passe oublié", "Fermez l'application, puis dans backend : python -m sentinel.cli reset-password "
                                "admin (saisie masquée). Inutile de supprimer la base : les décisions sont conservées."],
        ["Page blanche après une mise à jour", "Rechargez sans cache : Ctrl + F5."],
        ["Les tests échouent", "Lancez TESTS.bat (ou python -m pytest -q tests dans backend) après au moins un "
                               "lancement de l'application."],
    ], [0.36, 0.64], first_bold=True)

    # ---------------------------------------------------------------- annexe
    s += H1("A", "Annexe : glossaire et commandes")
    s += H2("Glossaire")
    s += table(["Terme", "Définition"], [
        ["B2", "format d'échange de facturation : fichier texte à enregistrements de longueur et de positions fixes"],
        ["CCAM", "Classification commune des actes médicaux ; code de 7 caractères (4 lettres, 3 chiffres)"],
        ["CERFA 12278 / S 3404", "le modèle de bordereau de facturation des établissements de santé privés"],
        ["FINESS", "n° d'identification de l'établissement, sur 9 chiffres"],
        ["GHS", "groupe homogène de séjour : le forfait d'hospitalisation, avec son numéro"],
        ["LPP", "liste des produits et prestations (dispositifs médicaux), zone 7 du bordereau"],
        ["OCR", "reconnaissance optique de caractères : lecture du texte d'une image"],
        ["SHA-256", "empreinte d'un fichier ; la moindre modification la change entièrement"],
        ["Homologue", "se dit de deux documents qui concernent le même dossier (mêmes identifiants)"],
    ], [0.25, 0.75], first_bold=True)
    s += H2("Commandes utiles")
    s.append(P(f"Dans le dossier {code('backend')}, environnement activé "
               f"({code('.venv\\Scripts\\activate')} sous Windows, {code('source .venv/bin/activate')} ailleurs) :"))
    s += table(["Commande", "Effet"], [
        ["python -m sentinel.cli serve", "lance l'application (options --host, --port)"],
        ["python -m sentinel.cli extract --force", "relit par OCR les 55 bordereaux (15 à 30 s par image)"],
        ["python -m sentinel.cli analyze", "ré-applique les 22 règles à tous les dossiers"],
        ["python -m sentinel.cli stats", "affiche les résultats par règle"],
        ["python -m sentinel.cli sync", "synchronise le corpus (sources nouvelles, modifiées, disparues)"],
        ["python -m sentinel.cli cache", "état du cache OCR (valide, obsolète, corrompu)"],
        ["python -m sentinel.cli backup", "sauvegarde vérifiée de la base"],
        ["python -m sentinel.cli restore &lt;fichier&gt;", "restaure une sauvegarde (sauvegarde de sécurité préalable)"],
        ["python -m sentinel.cli reset-password &lt;compte&gt;", "nouveau mot de passe, saisie masquée"],
        ["python -m sentinel.cli create-admin", "crée un administrateur, saisie masquée"],
        ["python -m pytest -q tests", "lance les 109 tests automatisés"],
    ], [0.48, 0.52], mono_first=True)
    s.append(Spacer(1, 10))
    s.append(P("Documentation complémentaire dans le dépôt : README.md, docs/ARCHITECTURE.md, docs/GUIDES.md, "
               "docs/RESULTATS.md, docs/TEST_AVEUGLE.md, docs/ZONES.md, docs/RAPPORT_TECHNIQUE_V2.md.", "small"))
    return s


def main():
    global COVER_SHOT
    COVER_SHOT = prep("10-zones-vue-globale.png", maxw=1600)
    doc = Doc(str(OUT))
    story = [Spacer(1, 1)] + content()
    doc.multiBuild(story)
    print("PDF :", OUT, f"{OUT.stat().st_size / 1e6:.1f} Mo")


if __name__ == "__main__":
    main()
