"""The recap PDF the customer downloads at the end of a loan simulation or a complaint.

Tagged PDF (PDF/UA-1): a screen reader reads it in order, with its title, heading and
table, in French. Large print and high contrast for low vision. Made with WeasyPrint,
which needs Pango (there on most Linux desktops; see the Dockerfile for the server).
"""

from datetime import date
from html import escape

from weasyprint import HTML

MONTHS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)

CSS = """
@page { size: A4; margin: 2cm; }
body { font-family: "DejaVu Sans", "Liberation Sans", sans-serif; font-size: 14pt;
       line-height: 1.5; color: #000; }
h1 { font-size: 22pt; line-height: 1.2; margin: 0 0 6pt; }
table { width: 100%; border-collapse: collapse; margin: 18pt 0; }
th, td { text-align: left; padding: 7pt 8pt; border-bottom: 1pt solid #555; }
th { font-weight: normal; width: 55%; }
td { font-weight: bold; }
"""


def write_recap_pdf(path, title, kind, reference, rows, notes):
    """kind: "simulation", "réclamation"...; rows: (label, value) pairs, shown as a
    table; notes: paragraphs below it."""
    today = date.today()
    table = "\n".join(
        f'<tr><th scope="row">{escape(label)}</th><td>{escape(value)}</td></tr>'
        for label, value in rows
    )
    paragraphs = "\n".join(f"<p>{escape(note)}</p>" for note in notes)
    html = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{escape(title)}</title>
<meta name="author" content="Assistant bancaire vocal">
<style>{CSS}</style>
</head>
<body>
<h1>{escape(title)}</h1>
<p>Référence {escape(reference)}, {escape(kind)} du {today.day} {MONTHS[today.month - 1]}
{today.year}.</p>
<table>
{table}
</table>
{paragraphs}
</body>
</html>"""
    HTML(string=html).write_pdf(path, pdf_variant="pdf/ua-1")
