"""Construit docs/GUIDE_1_PAGE.pdf : le parcours essentiel du mode simple, sur une seule page A4.

Usage (racine du projet) : python scripts/build_guide_1_page.py
Nécessite reportlab et une capture docs/images/v3/02-ecart.png (scripts : capture des écrans).
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "GUIDE_1_PAGE.pdf"
SHOT = ROOT / "docs" / "images" / "v3" / "02-ecart.png"

INDIGO = colors.HexColor("#1F2A6B")
RED = colors.HexColor("#DC2626")
GREY = colors.HexColor("#6B7280")
LIGHT = colors.HexColor("#EEF1F8")


def fonts():
    for d in ("/usr/share/fonts/truetype/dejavu/", "C:/Windows/Fonts/"):
        if Path(d + "DejaVuSans.ttf").exists():
            pdfmetrics.registerFont(TTFont("G", d + "DejaVuSans.ttf"))
            pdfmetrics.registerFont(TTFont("G-B", d + "DejaVuSans-Bold.ttf"))
            pdfmetrics.registerFontFamily("G", normal="G", bold="G-B", italic="G", boldItalic="G-B")
            return "G", "G-B"
    return "Helvetica", "Helvetica-Bold"


def main():
    reg, bold = fonts()
    st = {
        "title": ParagraphStyle("t", fontName=bold, fontSize=16, leading=19, textColor=INDIGO),
        "lead": ParagraphStyle("l", fontName=reg, fontSize=10, leading=13, textColor=GREY, spaceAfter=4),
        "h": ParagraphStyle("h", fontName=bold, fontSize=11.5, leading=14, textColor=INDIGO, spaceBefore=7),
        "b": ParagraphStyle("b", fontName=reg, fontSize=9.6, leading=12.6, alignment=TA_LEFT),
        "small": ParagraphStyle("s", fontName=reg, fontSize=7.6, leading=9.6, textColor=GREY),
        "note": ParagraphStyle("n", fontName=bold, fontSize=9, leading=11.5, textColor=INDIGO),
    }
    P = lambda t, s="b": Paragraph(t, st[s])  # noqa: E731
    story = [
        P("iMSA Sentinel : le parcours essentiel", "title"),
        P("Dossier → écart → preuve → décision. Rien d'autre n'est nécessaire pour contrôler une facture.", "lead"),
    ]
    left = [
        P("1. Choisir un dossier", "h"),
        P("À l'ouverture, <b>Mes dossiers</b> liste les dossiers à traiter, dans l'ordre proposé. "
          "Cliquez sur <b>Contrôler le dossier suivant</b>, ou sur une ligne du tableau."),
        P("2. Examiner les écarts", "h"),
        P("En haut, une phrase donne le résultat, par exemple « 1 écart à examiner ». Sur le bordereau, les zones "
          "en écart sont <font color='#DC2626'><b>encadrées en rouge</b></font>, les zones à vérifier "
          "<font color='#6B7280'><b>en gris</b></font> ; les zones conformes restent discrètes. Cliquez sur "
          "<b>Examiner les écarts</b>, sur un écart de la liste ou sur une zone de l'image."),
        P("3. Comparer les preuves", "h"),
        P("Deux encadrés côte à côte : <b>ce que dit le bordereau</b> (la valeur lue et l'agrandissement réel de "
          "la case) et <b>ce que dit le fichier de facturation</b> (la valeur, sa ligne, ses positions surlignées). "
          "<b>Différence</b> donne l'écart mesuré."),
        P("<b>« À vérifier manuellement »</b> : le logiciel n'a pas pu lire la case avec certitude. Il ne devine "
          "jamais. Regardez l'agrandissement, puis <b>Corriger la lecture</b> si besoin : le dossier est recalculé."),
        P("4. Enregistrer la décision", "h"),
    ]
    dec = Table([[P("<b>Confirmer l'écart</b>"), P("les deux documents diffèrent vraiment")],
                 [P("<b>Faux positif</b>"), P("les documents concordent (motif obligatoire)")],
                 [P("<b>À revoir</b>"), P("vous souhaitez un second avis")]],
                colWidths=[30 * mm, 58 * mm])
    dec.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD2E1")),
                             ("BACKGROUND", (0, 0), (0, -1), LIGHT), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
    left += [dec, Spacer(1, 3),
             P("Le logiciel passe ensuite tout seul à l'écart suivant. Quand tout est décidé : <b>Terminer le "
               "contrôle</b>, puis <b>Dossier suivant</b>.")]
    right = []
    if SHOT.exists():
        import tempfile
        from PIL import Image as PI
        im = PI.open(SHOT)
        W, H = im.size
        # panneau de droite de la capture (l'écart, ses deux preuves et les décisions)
        crop = im.crop((int(W * 0.632), int(H * 0.16), int(W * 0.993), int(H * 0.73)))
        tmp = Path(tempfile.mkdtemp()) / "ecart.png"
        crop.save(tmp)
        iw = 88 * mm
        right.append(Image(str(tmp), width=iw, height=iw * crop.size[1] / crop.size[0]))
        right.append(Spacer(1, 2))
        right.append(P("Un écart en mode simple (dossier Facture1_04) : la case du bordereau, la ligne du fichier, "
                       "la différence et les décisions.", "small"))
        right.append(Spacer(1, 6))
        iw2 = 88 * mm
        right.append(Image(str(SHOT), width=iw2, height=iw2 * H / W))
        right.append(P("L'écran complet : le bordereau à gauche, la zone en écart encadrée en rouge.", "small"))
    grid = Table([[left, right]], colWidths=[92 * mm, 92 * mm])
    grid.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (0, 0), 6 * mm)]))
    story += [grid, Spacer(1, 6)]
    box = Table([[P("Un écart est une différence entre deux documents. Ce n'est pas une fraude. C'est vous qui "
                    "décidez, et chaque décision est enregistrée à votre nom.", "note")]], colWidths=[184 * mm])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("BOX", (0, 0), (-1, -1), 0.6, INDIGO),
                             ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                             ("LEFTPADDING", (0, 0), (-1, -1), 7)]))
    story += [box, Spacer(1, 7), P("Ce que signifient les couleurs du bordereau", "h"), Spacer(1, 2)]
    sw = lambda c, dash=False: Table([[""]], colWidths=[9 * mm], rowHeights=[4 * mm], style=TableStyle(  # noqa: E731
        [("BOX", (0, 0), (-1, -1), 1.4, c)] + ([("LINEBELOW", (0, 0), (-1, -1), 0, colors.white)] if dash else [])))
    legend = Table([
        [sw(RED), P("<b>Écart</b> : les deux documents diffèrent. À examiner, puis décider."),
         sw(GREY), P("<b>À vérifier manuellement</b> : lecture incertaine. Le logiciel ne conclut pas : à vous de regarder.")],
        [sw(colors.HexColor("#16A34A")), P("<b>Conforme</b> : les deux documents concordent (affiché discrètement)."),
         sw(colors.HexColor("#C4C9D4")), P("<b>Sans objet</b> : le contrôle ne s'applique pas à ce dossier.")],
    ], colWidths=[12 * mm, 80 * mm, 12 * mm, 80 * mm])
    legend.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story += [legend, Spacer(1, 6),
              P("<b>Pour aller plus loin</b> : les 22 contrôles, les lectures OCR détaillées et le fichier complet "
                "sont dans <b>Autres actions → Mode expert</b> (tutoriel détaillé, docs/TUTORIEL_iMSA_Sentinel.pdf).",
                "small")]
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=13 * mm, rightMargin=13 * mm, topMargin=13 * mm,
                            bottomMargin=12 * mm, title="iMSA Sentinel — guide d'une page", author="iMSA Sentinel")
    doc.build(story)
    from pypdf import PdfReader
    n = len(PdfReader(str(OUT)).pages)
    print(f"{OUT} : {n} page(s)")
    if n != 1:
        raise SystemExit("Le guide doit tenir sur une page.")


if __name__ == "__main__":
    main()
