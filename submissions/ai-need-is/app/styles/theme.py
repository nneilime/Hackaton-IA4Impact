"""
app/styles/theme.py — Design System IA_NEED_IS

Palette Enedis étendue, CSS global WCAG-AA, helpers de rendu.
Importer inject_css() une seule fois au démarrage de app/main.py.
"""

from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Palette de couleurs (tokens)
# ---------------------------------------------------------------------------
ENEDIS_BLEU = "#005EB8"
ENEDIS_VERT = "#93C90E"

# Fond & surfaces
COLOR_BG        = "#F0F2F6"   # fond global (légèrement plus chaud que le défaut Streamlit)
COLOR_SURFACE   = "#FFFFFF"   # cards, expanders
COLOR_BORDER    = "#E2E8F0"   # séparateurs, bordures légères

# Texte
COLOR_TEXT      = "#1A202C"   # corps principal — ratio > 7:1 sur blanc
COLOR_TEXT_MUTED = "#64748B"  # captions, labels secondaires

# Fonctionnel
COLOR_SUCCESS   = "#16A34A"   # pannes résolues, objectifs atteints
COLOR_WARNING   = "#D97706"   # en cours, fatigue ≥ 75 %
COLOR_DANGER    = "#DC2626"   # en attente, dépassement critique
COLOR_INFO      = "#0369A1"   # équipes libres, info neutre

# Stratégies — couleurs distinctes pour les graphes
COULEURS_STRATEGIES = {
    "Distance minimale":         "#005EB8",
    "Premier arrivé":            "#D97706",
    "Score pondéré":             "#16A34A",
    "🤖 IA Optimale (ML + Hongrois)": "#7C3AED",
}

# ---------------------------------------------------------------------------
# CSS global injecté une fois
# ---------------------------------------------------------------------------
_CSS = f"""
<style>
/* ── Imports Google Fonts ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* ── Sélection de texte : contraste stable sur tous les composants ── */
.stApp *::selection {{
    background: #004A92 !important;
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}}

.stApp *::-moz-selection {{
    background: #004A92 !important;
    color: #FFFFFF !important;
}}

/* ── Reset & base ── */
html, body, [class*="css"], .stApp {{
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    color: {COLOR_TEXT} !important;
    color-scheme: light !important;
}}

/* ── Fond global ── */
.stApp {{
    background-color: {COLOR_BG};
}}

/* ── Header Streamlit ── */
[data-testid="stHeader"] {{
    background-color: #FFFFFF !important;
    border-bottom: 3px solid {ENEDIS_BLEU};
}}

/* ── Sidebar ── */
[data-testid="stSidebar"] {{
    background-color: {COLOR_SURFACE} !important;
    border-right: 1px solid {COLOR_BORDER};
}}
/* Texte générique noir */
[data-testid="stSidebar"],
[data-testid="stSidebar"] * {{
    color: #000000 !important;
}}
/* Labels des widgets (p, span, div) dans la sidebar */
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"],
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stSlider label,
[data-testid="stSidebar"] .stNumberInput label,
[data-testid="stSidebar"] p {{
    color: #000000 !important;
}}
/* Fond des inputs (selectbox, number_input) dans sidebar */
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] input {{
    background-color: rgba(255,255,255,0.7) !important;
    color: #000000 !important;
    border-color: rgba(0,0,0,0.3) !important;
}}
/* Texte dans la liste déroulante ouverte (reste sur fond blanc) */
[data-baseweb="popover"] * {{
    color: {COLOR_TEXT} !important;
}}
[data-testid="stSidebar"] .stSlider > div > div > div {{
    background-color: {ENEDIS_VERT} !important;
}}
/* Valeur affichée du slider */
[data-testid="stSidebar"] [data-testid="stThumbValue"],
[data-testid="stSidebar"] [data-testid="stTickBarMin"],
[data-testid="stSidebar"] [data-testid="stTickBarMax"] {{
    color: #000000 !important;
}}
[data-testid="stSidebar"] hr {{
    border-color: rgba(0,0,0,0.25) !important;
}}

/* ── Contrastes explicites des champs et menus ── */
[data-baseweb="select"] > div,
[data-baseweb="input"] > div,
[data-baseweb="base-input"],
[data-baseweb="textarea"],
.stTextInput input,
.stNumberInput input,
.stTextArea textarea,
.stDateInput input,
.stTimeInput input {{
    background-color: #FFFFFF !important;
    color: #172033 !important;
    -webkit-text-fill-color: #172033 !important;
    border-color: #94A3B8 !important;
}}
[data-baseweb="select"] input,
[data-baseweb="select"] span,
[data-baseweb="select"] svg,
[data-baseweb="input"] input,
[data-baseweb="textarea"] textarea {{
    color: #172033 !important;
    fill: #172033 !important;
    -webkit-text-fill-color: #172033 !important;
}}
[data-baseweb="popover"],
[data-baseweb="popover"] > div,
[role="listbox"],
[data-baseweb="menu"] {{
    background-color: #FFFFFF !important;
    color: #172033 !important;
}}
[role="option"] {{
    background-color: #FFFFFF !important;
    color: #172033 !important;
    -webkit-text-fill-color: #172033 !important;
}}
[role="option"]:hover,
[role="option"][aria-selected="true"] {{
    background-color: #DBEAFE !important;
    color: #0F3D70 !important;
    -webkit-text-fill-color: #0F3D70 !important;
}}
[data-baseweb="tag"] {{
    background-color: #DBEAFE !important;
    color: #0F3D70 !important;
}}
[data-baseweb="tag"] span,
[data-baseweb="tag"] svg {{
    color: #0F3D70 !important;
    fill: #0F3D70 !important;
}}
input::placeholder,
textarea::placeholder {{
    color: #64748B !important;
    opacity: 1 !important;
    -webkit-text-fill-color: #64748B !important;
}}
input:disabled,
textarea:disabled,
[aria-disabled="true"] {{
    color: #475569 !important;
    -webkit-text-fill-color: #475569 !important;
    opacity: 1 !important;
}}

/* Labels et contrôles de choix : lisibles quel que soit le thème système. */
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p,
.stRadio label,
.stCheckbox label,
.stSelectbox label,
.stMultiSelect label,
.stTextInput label,
.stTextArea label,
.stNumberInput label {{
    color: #172033 !important;
}}
.stRadio label span,
.stCheckbox label span {{
    color: #172033 !important;
}}

/* Formulaires et conteneurs restent sur une surface claire. */
[data-testid="stForm"],
[data-testid="stVerticalBlockBorderWrapper"] > div {{
    background-color: #FFFFFF !important;
    color: #172033 !important;
    border-color: {COLOR_BORDER} !important;
}}

/* ── Typographie : titres ── */
h1 {{
    font-family: 'Inter', sans-serif;
    font-size: 1.75rem !important;
    font-weight: 700 !important;
    color: {ENEDIS_BLEU} !important;
    letter-spacing: -0.02em;
}}
h2, h3 {{
    font-family: 'Inter', sans-serif;
    font-weight: 600 !important;
    color: {ENEDIS_BLEU} !important;
}}

/* ── Métriques ── */
[data-testid="stMetricValue"] {{
    font-family: 'Inter', sans-serif;
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    color: {ENEDIS_BLEU} !important;
}}
[data-testid="stMetricLabel"] {{
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    color: {COLOR_TEXT_MUTED} !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}
[data-testid="stMetricDelta"] {{
    font-size: 0.85rem !important;
    font-weight: 600 !important;
}}

/* ── Bouton primaire (CTA) — WCAG AA : fond vert assombri, texte blanc ── */
div.stButton > button[kind="primary"] {{
    background-color: #5A8A08 !important;   /* assombri pour ratio 4.5:1 avec #fff */
    color: #FFFFFF !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 0.55rem 1.2rem !important;
    letter-spacing: 0.01em;
    transition: background-color 0.2s ease, transform 0.1s ease;
}}
div.stButton > button[kind="primary"]:hover {{
    background-color: #496E06 !important;
    transform: translateY(-1px);
}}
div.stButton > button[kind="primary"]:active {{
    transform: translateY(0);
}}
div.stButton > button[kind="primary"]:disabled {{
    background-color: #E2E8F0 !important;
    color: #475569 !important;
    cursor: not-allowed !important;
}}

/* ── Bouton secondaire ── */
div.stButton > button[kind="secondary"] {{
    background-color: transparent !important;
    border: 1.5px solid {ENEDIS_BLEU} !important;
    color: {ENEDIS_BLEU} !important;
    font-weight: 600 !important;
    border-radius: 6px !important;
    transition: background-color 0.2s ease;
}}
div.stButton > button[kind="secondary"]:hover {{
    background-color: rgba(0,94,184,0.07) !important;
}}

/* ── Bouton danger (Streamlit ne supporte pas nativement, classe CSS manuelle) ── */
div.stButton.btn-danger > button {{
    background-color: {COLOR_DANGER} !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 700 !important;
}}

/* ── Focus visible (WCAG 2.1 — 2.4.7) ── */
button:focus-visible,
[data-baseweb="select"]:focus-visible,
input:focus-visible,
textarea:focus-visible {{
    outline: 2.5px solid {ENEDIS_VERT} !important;
    outline-offset: 2px !important;
}}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {{
    gap: 0.25rem;
    border-bottom: 2px solid {COLOR_BORDER};
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 4px 4px 0 0 !important;
    padding: 0.5rem 1.1rem !important;
    font-weight: 500;
    font-size: 0.92rem;
    color: {COLOR_TEXT_MUTED};
    transition: color 0.15s;
}}
.stTabs [aria-selected="true"] {{
    background-color: {COLOR_SURFACE} !important;
    color: {ENEDIS_BLEU} !important;
    font-weight: 700 !important;
    border-bottom: 3px solid {ENEDIS_BLEU} !important;
}}

/* ── Cards (conteneurs) ── */
.card {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    padding: 1.1rem 1.25rem;
    margin-bottom: 0.75rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}}
.card-success {{ border-left: 4px solid {COLOR_SUCCESS}; }}
.card-warning {{ border-left: 4px solid {COLOR_WARNING}; }}
.card-danger  {{ border-left: 4px solid {COLOR_DANGER};  }}
.card-info    {{ border-left: 4px solid {COLOR_INFO};    }}
.card-neutral {{ border-left: 4px solid {COLOR_BORDER};  }}

/* Nouvelle coque : navigation par mode et décision humaine */
.app-hero {{ display:flex; align-items:center; gap:0.8rem; padding:0.35rem 0 0.9rem; }}
.app-logo {{ font-size:2rem; }}
.app-title {{ color:{ENEDIS_BLEU}; font-size:1.45rem; font-weight:800; line-height:1.1; }}
.app-subtitle {{ color:{COLOR_TEXT_MUTED}; font-size:0.82rem; margin-top:0.15rem; }}
.human-chip {{ margin-left:auto; color:#166534; background:#DCFCE7; border:1px solid #86EFAC; padding:0.35rem 0.8rem; border-radius:999px; font-size:0.78rem; font-weight:700; }}
.human-banner {{ background:#EFF6FF; border:1px solid #BFDBFE; border-left:5px solid {ENEDIS_BLEU}; border-radius:10px; padding:0.85rem 1rem; margin:0.2rem 0 1rem; display:flex; flex-direction:column; gap:0.2rem; }}
.human-banner strong {{ color:#1E3A8A; }}
.human-banner span {{ color:#475569; font-size:0.86rem; }}
.decision-card {{ background:#FFFFFF; border:1px solid #CBD5E1; border-top:5px solid {ENEDIS_BLEU}; border-radius:12px; padding:1rem 1.1rem; box-shadow:0 4px 14px rgba(15,23,42,0.08); }}
.decision-eyebrow {{ color:#B45309; font-size:0.7rem; font-weight:800; letter-spacing:0.06em; }}
.decision-card h3 {{ margin:0.35rem 0 !important; font-size:1.2rem !important; }}
.decision-team {{ padding:0.5rem 0 0.8rem; color:#334155; }}
.decision-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:0.55rem; }}
.decision-grid span {{ background:#F8FAFC; border-radius:8px; padding:0.55rem 0.65rem; }}
.decision-grid small {{ display:block; color:#64748B; font-size:0.68rem; text-transform:uppercase; }}
.decision-grid strong {{ display:block; color:#0F172A; margin-top:0.12rem; }}

/* ── Badges de statut ── */
.badge {{
    display: inline-block;
    padding: 0.18rem 0.65rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
    line-height: 1.4;
}}
.badge-success {{ background: #DCFCE7; color: #15803D; }}
.badge-warning {{ background: #FEF3C7; color: #B45309; }}
.badge-danger  {{ background: #FEE2E2; color: #B91C1C; }}
.badge-info    {{ background: #E0F2FE; color: #0369A1; }}
.badge-neutral {{ background: #F1F5F9; color: #475569; }}

/* ── Expanders : surface et texte toujours contrastés ── */
.streamlit-expanderHeader,
[data-testid="stExpander"] summary,
[data-testid="stExpander"] > div:first-child {{
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    color: {COLOR_TEXT} !important;
    background-color: {COLOR_SURFACE} !important;
}}
/* Contenu de l'expander (journal, listes) — forcé sur fond blanc avec texte foncé */
[data-testid="stExpander"] > div[data-testid="stExpanderDetails"],
[data-testid="stExpander"] .stMarkdown,
[data-testid="stExpander"] .stMarkdown p,
[data-testid="stExpander"] .stMarkdown li,
[data-testid="stExpander"] .stMarkdown ul {{
    background-color: {COLOR_SURFACE} !important;
    color: {COLOR_TEXT} !important;
}}

/* ── Tableaux ── */
[data-testid="stDataFrame"] {{
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid {COLOR_BORDER};
}}

/* ── Progress bar (st.progress) ── */
[data-testid="stProgressBar"] > div > div {{
    background: linear-gradient(90deg, {ENEDIS_BLEU}, {ENEDIS_VERT}) !important;
}}

/* ── Captions ── */
.stCaption, small {{
    color: {COLOR_TEXT_MUTED} !important;
    font-size: 0.78rem !important;
}}

/* ── Barre de statut persistante ── */
.status-bar {{
    position: sticky;
    top: 0;
    z-index: 100;
    background: {COLOR_SURFACE};
    border-bottom: 2px solid {COLOR_BORDER};
    padding: 0.5rem 1rem;
    display: flex;
    align-items: center;
    gap: 1.5rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    border-radius: 0 0 8px 8px;
    margin-bottom: 1rem;
}}
.status-pill {{
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.22rem 0.75rem;
    border-radius: 999px;
    font-weight: 600;
    font-size: 0.82rem;
}}
.status-pill.en-attente {{ background:#FEE2E2; color:#B91C1C; }}
.status-pill.en-cours   {{ background:#FEF3C7; color:#B45309; }}
.status-pill.resolue    {{ background:#DCFCE7; color:#15803D; }}
.status-pill.equipes    {{ background:#E0F2FE; color:#0369A1; }}

/* ── Scrollbar discrète ── */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {COLOR_BG}; }}
::-webkit-scrollbar-thumb {{ background: #CBD5E1; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: #94A3B8; }}
</style>
"""


def inject_css() -> None:
    """Injecte le CSS global du Design System. À appeler une seule fois."""
    st.markdown(_CSS, unsafe_allow_html=True)


def card(contenu_html: str, variante: str = "neutral") -> None:
    """
    Affiche un bloc HTML dans une card stylée.

    variante : "success" | "warning" | "danger" | "info" | "neutral"
    """
    st.markdown(
        f'<div class="card card-{variante}">{contenu_html}</div>',
        unsafe_allow_html=True,
    )


def badge(texte: str, variante: str = "neutral") -> str:
    """Retourne le HTML d'un badge de statut inline."""
    return f'<span class="badge badge-{variante}">{texte}</span>'


def statut_etat(etat: str) -> str:
    """Convertit un état d'équipe en badge HTML coloré."""
    mapping = {
        "libre":       ("En attente", "info"),
        "en_mission":  ("En mission", "warning"),
        "au_repos":    ("Au repos",   "neutral"),
    }
    texte, variante = mapping.get(etat, (etat, "neutral"))
    return badge(texte, variante)
