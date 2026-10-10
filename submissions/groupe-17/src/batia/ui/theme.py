"""Identité visuelle. Le logo officiel n'est PAS fourni : déposez-le dans assets/logo_action_logement.png."""

import base64
import streamlit as st
from batia import config as C

BLEU = "#0B3C7D"
BLEU_CLAIR = "#2E6FC4"
ACCENT = "#FF7A1A"
FOND = "#F3F6FB"
LOGO = C.ASSETS / "logo_action_logement.png"

CSS = f"""
<style>
.stApp {{ background: {FOND}; }}
.block-container {{ padding-top: 1.2rem; max-width: 1500px; }}
[data-testid="stSidebar"] {{ background: #FFFFFF; border-right: 4px solid {ACCENT}; }}
h1, h2, h3 {{ color: {BLEU}; letter-spacing: -0.3px; }}
.bt-header {{ background: linear-gradient(110deg, {BLEU} 0%, {BLEU_CLAIR} 70%, #5A9BE6 100%);
  border-radius: 18px; padding: 22px 28px; color: #fff; display:flex; align-items:center; gap:22px;
  box-shadow: 0 8px 24px rgba(11,60,125,.22); margin-bottom: 18px; }}
.bt-header h1 {{ color:#fff; margin:0; font-size: 1.9rem; }}
.bt-header p {{ margin:2px 0 0 0; opacity:.9; font-size:.98rem; }}
.bt-logo {{ background:#fff; border-radius:12px; padding:8px 14px; display:flex; align-items:center; min-height:54px; }}
.bt-logo img {{ height:42px; }}
.bt-wordmark {{ color:{BLEU}; font-weight:800; letter-spacing:1.2px; font-size:1.05rem; line-height:1.05; }}
.bt-wordmark span {{ color:{ACCENT}; }}
.bt-card {{ background:#fff; border-radius:16px; padding:16px 18px; box-shadow:0 2px 10px rgba(16,24,40,.07);
  border-left:6px solid {BLEU}; height:100%; }}
.bt-card .l {{ color:#667085; font-size:.82rem; text-transform:uppercase; letter-spacing:.6px; }}
.bt-card .v {{ color:#101828; font-size:2rem; font-weight:800; line-height:1.15; }}
.bt-card .s {{ color:#667085; font-size:.82rem; }}
.bt-pill {{ display:inline-block; padding:3px 12px; border-radius:999px; font-weight:700; font-size:.8rem; color:#fff; }}
.bt-rouge {{ background:{C.COULEURS["rouge"]}; }}
.bt-orange {{ background:{C.COULEURS["orange"]}; }}
.bt-vert {{ background:{C.COULEURS["vert"]}; }}
.bt-note {{ background:#FFF4E5; border-left:5px solid {ACCENT}; border-radius:10px; padding:10px 14px; color:#7A4300; font-size:.9rem; }}
div[data-testid="stMetric"] {{ background:#fff; border-radius:14px; padding:10px 14px; box-shadow:0 2px 8px rgba(16,24,40,.06); }}
.stButton > button[kind="primary"] {{ background:{ACCENT}; border:0; color:#fff; font-weight:700; border-radius:12px; padding:.6rem 1.2rem; }}
.stButton > button[kind="primary"]:hover {{ background:#E5650B; }}
</style>
"""


def _logo_b64():
    return base64.b64encode(LOGO.read_bytes()).decode() if LOGO.exists() else None


def apply_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    if LOGO.exists():
        try:
            st.logo(str(LOGO))
        except Exception:
            pass


def header(titre: str, sous_titre: str = "") -> None:
    b64 = _logo_b64()
    logo = (
        f'<div class="bt-logo"><img src="data:image/png;base64,{b64}"/></div>'
        if b64
        else '<div class="bt-logo"><div class="bt-wordmark">ACTION<br><span>LOGEMENT</span></div></div>'
    )
    st.markdown(
        f'<div class="bt-header">{logo}<div><h1>{titre}</h1><p>{sous_titre}</p></div></div>',
        unsafe_allow_html=True,
    )


def kpi(label: str, valeur: str, sous: str = "", couleur: str = BLEU) -> str:
    return (
        f'<div class="bt-card" style="border-left-color:{couleur}"><div class="l">{label}</div>'
        f'<div class="v">{valeur}</div><div class="s">{sous}</div></div>'
    )


def pill(statut: str) -> str:
    lab = {"rouge": "DANGER", "orange": "RISQUE", "vert": "SAFE"}.get(statut, statut)
    return f'<span class="bt-pill bt-{statut}">{lab}</span>'


def demo_note(texte: str) -> None:
    st.markdown(f'<div class="bt-note">{texte}</div>', unsafe_allow_html=True)
