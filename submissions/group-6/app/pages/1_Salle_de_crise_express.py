"""Salle de crise — version EXPRESS (écrite par P1 pour sécuriser la démo ; P4 garde la page principale).

Lancement : streamlit run app/Accueil.py   puis menu de gauche « Salle de crise express »
Montre : KPI référence vs stratégie, courbe des clients coupés, saturation, Gantt des équipes,
décisions, et les résultats du banc d'essai s'ils existent (outputs/benchmark_kpi.csv).
"""
from __future__ import annotations

import json
import logging
import time

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st
from streamlit_folium import st_folium

from crise.benchmark import resoudre_strategie, resumer
from crise.carte import creer_carte_folium
from crise.config import charger_config, chemin_projet
from crise.copilote.templates import fiche_arbitrage, point_situation
from crise.instant import equipes_a, incidents_a, ligne_serie
from crise.kpi import calculer_kpi
from crise.models import lister_crises
from crise.simulateur import parametres_simulation, simuler_crise
from crise.trajet import ZONE_MONTAGNE, faire_trajet_min

logging.getLogger("crise.simulateur").setLevel(logging.ERROR)
st.set_page_config(page_title="Salle de crise express", layout="wide")
st.title("Salle de crise — copilote Enedis (express)")
st.caption("L'outil recommande, le responsable décide. Données synthétiques Enedis — hackathon IA for Impact 2026.")

# --------------------------------------------------------------------------- panneau latéral
NOMS = {"R1": "R1 · premier arrivé + plus proche", "R2": "R2 · plus de clients d'abord",
        "WSPT": "WSPT + hongrois (P2)", "WSPTX": "WSPT express (secours)"}
disponibles = []
for code in ("R1", "R2", "WSPT", "WSPTX"):
    try:
        resoudre_strategie(code)
        disponibles.append(code)
    except Exception:                                      # noqa: BLE001
        pass

with st.sidebar:
    try:
        crises_reelles = lister_crises()
    except Exception:
        crises_reelles = []
    crises = ["CRISE_FACTICE (T4.1)"] + crises_reelles
    idx_defaut = (
        crises.index("CRISE_024")
        if "CRISE_024" in crises
        else (crises.index("CRISE_027") if "CRISE_027" in crises else 0)
    )
    crise = st.selectbox("Crise", crises, index=idx_defaut)
    choix = st.multiselect("Stratégies à comparer", disponibles,
                           default=[c for c in disponibles if c != "WSPTX"] or disponibles,
                           format_func=lambda c: NOMS.get(c, c))
    st.subheader("Paramètres")
    alpha = st.slider("Poids client sensible α", 0.0, 20.0, 5.0, 0.5)
    beta = st.slider("Poids de l'attente β (par heure)", 0.0, 0.5, 0.1, 0.05)
    roulement = st.checkbox(
        "Roulement des équipes 75% / 25% (H7)",
        value=True,
        help="Hypothèse H7 : 75% des équipes débutent à t=0, repos de 11h après 12h ; 25% prennent le relais à t=12h.",
    )
    st.subheader("Stress tests")
    routes_coupees = st.checkbox("Routes coupées en montagne (vitesse ÷ 3)")
    peu_equipes = st.slider("Nombre d'équipes", 6 if "FACTICE" in crise else 10, 63, 6 if "FACTICE" in crise else 63)
    hs = st.slider("% d'équipes hors service à H+3", 0, 50, 0, 10)


@st.cache_data(show_spinner=False)
def simuler(crise: str, code: str, alpha: float, beta: float, routes: bool, nb_eq: int, hs_pct: int,
            roulement: bool = True, interdites: tuple = (), forcees: tuple = ()):
    from crise.simulateur import Indisponibilite

    cfg = charger_config()
    p = parametres_simulation(cfg, alpha_sensible=alpha, beta_attente_par_h=beta, roulement_actif=roulement)
    trajet = faire_trajet_min(cfg, zones=[ZONE_MONTAGNE] if routes else ())

    if "FACTICE" in crise:
        from crise.factice import generer_sim_result_factice

        res = generer_sim_result_factice(
            n_incidents=30,
            n_equipes=min(nb_eq, 6),
            seed=42,
            policy=resoudre_strategie(code)(),
            params=p,
        )
        return res, calculer_kpi(res)

    scenario = {"nb_equipes_max": nb_eq} if nb_eq < 63 else None
    options = {"interdites": set(interdites), "forcees": dict(forcees)}
    if hs_pct:
        from crise.models import charger_scenario

        _, eqs, _ = charger_scenario(crise, scenario)
        n = round(len(eqs) * hs_pct / 100)
        options["indisponibilites"] = [Indisponibilite(e.id_equipe, 180) for e in eqs[::max(1, len(eqs) // n)][:n]]
    res = simuler_crise(crise, resoudre_strategie(code)(), p, scenario=scenario, trajet_min=trajet, **options)
    return res, calculer_kpi(res)



if not choix:
    st.info("Choisir au moins une stratégie.")
    st.stop()

resultats = {}
with st.spinner("Simulation…"):
    for c in choix:
        try:
            resultats[c] = simuler(crise, c, alpha, beta, routes_coupees, peu_equipes, hs, roulement=roulement)
        except Exception as e:                             # noqa: BLE001 — la démo ne doit jamais planter
            st.warning(f"{NOMS.get(c, c)} : erreur, stratégie ignorée ({e!r})")
choix = [c for c in choix if c in resultats]
if not choix:
    st.stop()

# --------------------------------------------------------------------------- KPI
ref = "R2" if "R2" in resultats else choix[0]
st.subheader("Indicateurs")
cols = st.columns(len(choix))
for col, c in zip(cols, choix, strict=True):
    _, k = resultats[c]
    k_ref = resultats[ref][1]
    with col:
        st.markdown(f"**{NOMS.get(c, c)}**")
        delta = None if c == ref else f"{100 * (k['clients_heures'] / k_ref['clients_heures'] - 1):+.1f} % vs {ref}"
        st.metric("Clients·heures de coupure", f"{k['clients_heures']:,.0f}".replace(",", " "), delta,
                  delta_color="inverse")
        st.metric("Attente max d'un poste sensible", f"{k['attente_max_sensible_h']:.1f} h")
        st.metric("Clients rétablis en moins de 4h", f"{k['pct_clients_retablis_4h']:.0f} %")
        st.metric("Fin de crise", f"{k['fin_crise_h']:.0f} h")
        st.caption(f"Saturation {k['saturation_pct']:.0f} % du temps · Gini {k['gini_communes']:.2f} · "
                   f"dépassements d'amplitude : {k['depassements_amplitude']}")

# --------------------------------------------------------------------------- courbe phare
st.subheader("Clients coupés au fil de la crise")
fig = go.Figure()
for c in choix:
    s = resultats[c][0].serie
    fig.add_trace(go.Scatter(x=s["t"] / 60, y=s["clients_coupes"], mode="lines", name=NOMS.get(c, c)))
fig.update_layout(xaxis_title="Heures depuis le début de la crise", yaxis_title="Clients coupés",
                  height=380, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h"))
st.plotly_chart(fig, use_container_width=True)
st.caption("L'aire sous chaque courbe = clients·heures de coupure. "
           "L'écart entre deux courbes = foyers rallumés plus tôt.")

# --------------------------------------------------------------------------- détail d'une stratégie
detail = st.selectbox("Détail de la stratégie", choix, index=len(choix) - 1, format_func=lambda c: NOMS.get(c, c))
res, _ = resultats[detail]
st.markdown("**Équipes dans le temps**")
s = res.serie
fig2 = go.Figure()
for col_, nom in [("equipes_occupees", "en intervention"), ("equipes_repos", "retour / repos"),
                  ("equipes_disponibles", "disponibles"), ("equipes_hs", "hors service")]:
    fig2.add_trace(go.Scatter(x=s["t"] / 60, y=s[col_], stackgroup="a", name=nom, mode="none"))
fig2.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="Heures",
                   legend=dict(orientation="h"))
st.plotly_chart(fig2, use_container_width=True)

# --------------------------------------------------------------------------- carte animée (T4.2)
st.subheader("Carte de la crise à l'instant t")
fin_h = float(res.serie["t"].max() / 60)

# Contrôles temporels et animation (T4.2 : curseur pas 30 min + bouton lecture)
if "anim_t_h" not in st.session_state:
    st.session_state.anim_t_h = min(6.0, fin_h)
if "is_playing" not in st.session_state:
    st.session_state.is_playing = False

col_slide, col_btn_play, col_btn_reset = st.columns([6, 1.2, 1.2])

with col_btn_play:
    if st.button("⏸ Pause" if st.session_state.is_playing else "▶ Lecture", use_container_width=True):
        st.session_state.is_playing = not st.session_state.is_playing
        st.rerun()

with col_btn_reset:
    if st.button("⏮ Début", use_container_width=True):
        st.session_state.anim_t_h = 0.0
        st.session_state.is_playing = False
        st.rerun()

if st.session_state.is_playing:
    if round(st.session_state.anim_t_h + 0.5, 1) <= fin_h:
        st.session_state.anim_t_h = round(st.session_state.anim_t_h + 0.5, 1)
        time.sleep(0.3)
        st.rerun()
    else:
        st.session_state.is_playing = False

with col_slide:
    t_h = st.slider(
        "Heure depuis le début de la crise",
        0.0,
        fin_h,
        float(st.session_state.anim_t_h),
        0.5,
        key="slider_t_h",
    )
    st.session_state.anim_t_h = t_h

t_min = t_h * 60
inc_t = incidents_a(res, t_min)
eq_t = equipes_a(res, t_min)

# Indicateurs instantanés à l'instant t (T4.3)
c1, c2, c3, c4 = st.columns(4)
for col_, etat in zip((c1, c2, c3, c4), ("en attente", "en intervention", "rétabli", "à venir"), strict=True):
    n = inc_t["etat"].eq(etat)
    col_.metric(etat.capitalize(), f"{int(n.sum())} incidents", f"{int(inc_t.loc[n, 'nb_clients'].sum())} clients",
                delta_color="off")

mode_carte = st.radio(
    "Mode d'affichage cartographique :",
    ["🗺️ Carte interactive Folium (Leaflet)", "🌐 Vue 3D Pydeck", "📊 Vue Plotly (sans fond)"],
    index=0,
    horizontal=True,
)

# Récupération des sites de référence
sites_refs = None
if "FACTICE" in crise:
    from crise.factice import creer_sites_factices
    sites_refs = creer_sites_factices()
else:
    try:
        from crise.models import charger_scenario
        sites_refs, _, _ = charger_scenario(crise)
    except Exception:
        pass

if mode_carte == "🗺️ Carte interactive Folium (Leaflet)":
    carte_folium = creer_carte_folium(inc_t, eq_t, sites=sites_refs)
    st_folium(carte_folium, width=None, height=520, returned_objects=[])
elif mode_carte == "📊 Vue Plotly (sans fond)":
    fig3 = px.scatter(inc_t[inc_t["etat"] != "à venir"], x="lon", y="lat", color="etat", size="nb_clients",
                      size_max=14, hover_name="commune", height=520,
                      color_discrete_map={"en attente": "#d62828", "en intervention": "#f2a541", "rétabli": "#2a9d8f"})
    fig3.add_scatter(x=eq_t["lon"], y=eq_t["lat"], mode="markers", name="équipes",
                     marker=dict(symbol="triangle-up", size=9, color="#1e5ac8"), text=eq_t["id_equipe"])
    fig3.update_yaxes(scaleanchor="x", scaleratio=1.37)
    fig3.update_layout(margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig3, use_container_width=True)
else:
    COUL = {"à venir": [180, 180, 180, 60], "en attente": [214, 40, 40, 220],
            "en intervention": [242, 165, 65, 230], "rétabli": [42, 157, 143, 140]}
    inc_t["couleur"] = inc_t["etat"].map(COUL)
    inc_t["rayon"] = 400 + 25 * inc_t["nb_clients"]
    inc_t["contour"] = inc_t["sensible"].map(lambda v: [128, 0, 200, 255] if v else [0, 0, 0, 0])
    eq_t["couleur"] = eq_t["activite"].map({"trajet": [30, 90, 200, 255], "chantier": [30, 90, 200, 255],
                                            "retour": [120, 140, 160, 255], "repos": [90, 90, 90, 255],
                                            "hors_service": [0, 0, 0, 255]}).apply(
        lambda c: c if isinstance(c, list) else [30, 160, 255, 255])
    trajets = eq_t[eq_t["activite"] == "trajet"]
    couches = [
        pdk.Layer("ScatterplotLayer", inc_t, get_position="[lon, lat]", get_fill_color="couleur",
                  get_line_color="contour", line_width_min_pixels=2, stroked=True, get_radius="rayon",
                  pickable=True),
        pdk.Layer("LineLayer", trajets, get_source_position="[lon, lat]",
                  get_target_position="[lon_cible, lat_cible]", get_color=[30, 90, 200, 160], get_width=2),
        pdk.Layer("ScatterplotLayer", eq_t, get_position="[lon, lat]", get_fill_color="couleur",
                  get_radius=1200, radius_min_pixels=4, pickable=True),
    ]
    st.pydeck_chart(pdk.Deck(
        layers=couches, initial_view_state=pdk.ViewState(latitude=43.3, longitude=1.1, zoom=7.2),
        tooltip={"text": "{commune}{id_equipe}\n{etat}{activite}\n{nb_clients} clients"}, height=520))

st.caption("Rouge = en attente · orange = en intervention · vert = rétabli · contour violet = client sensible · "
           "bleu = équipes (traits = trajets en cours). Taille = nombre de clients.")
st.info(point_situation(int(t_min), ligne_serie(res, t_min),
                        sensibles_attente=int((inc_t["etat"].eq("en attente") & inc_t["sensible"]).sum()),
                        tension=inc_t[inc_t["etat"] == "en attente"]["departement"].value_counts()
                        .head(2).index.tolist()))

st.markdown("**Gantt des équipes**")
act = res.activites.copy()
act["debut"] = pd.Timestamp("2026-01-01") + pd.to_timedelta(act["t_debut"], unit="m")
act["fin"] = pd.Timestamp("2026-01-01") + pd.to_timedelta(act["t_fin"], unit="m")
act = act[act["t_fin"] > act["t_debut"]]
fig4 = px.timeline(act, x_start="debut", x_end="fin", y="id_equipe", color="type", height=900,
                   color_discrete_map={"trajet": "#f2a541", "chantier": "#d1495b", "retour": "#9db4c0",
                                       "repos": "#5c6b73", "hors_service": "#222222"})
fig4.update_yaxes(autorange="reversed", title=None)
fig4.update_layout(margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h"))
st.plotly_chart(fig4, use_container_width=True)

# --------------------------------------------------------------------------- décisions et arbitrage humain
st.subheader("Décisions expliquées — l'outil recommande, le responsable décide")
cle = f"{crise}|{detail}|{alpha}|{beta}|{routes_coupees}|{peu_equipes}|{hs}"
humain = st.session_state.setdefault("humain", {}).setdefault(cle, {"interdites": [], "forcees": []})

dec = res.decisions.copy()
dec["e"] = dec["explication"].map(json.loads)
dec["heure"] = (dec["t"] / 60).round(1)
dec["confiance"] = dec["e"].map(lambda e: e.get("confiance"))
dec["delta"] = dec["e"].map(lambda e: (e.get("alternative") or {}).get("delta_clients_heures"))
dec["a_discuter"] = dec["delta"].fillna(0) < 0
filtre = st.radio("Afficher", ["toutes les décisions", "seulement les décisions à discuter"], horizontal=True)
vue = dec[dec["a_discuter"]] if filtre.startswith("seulement") else dec
if vue.empty:
    st.info("Aucune décision à discuter pour ces paramètres.")
else:
    idx = st.selectbox(
        "Décision", vue.index,
        format_func=lambda k: (f"H+{dec.at[k, 'heure']} · {dec.at[k, 'id_equipe']} → {dec.at[k, 'id_incident']}"
                               f" · confiance {dec.at[k, 'confiance'] or 0:.0%}"
                               + (" · ⚠️ à discuter" if dec.at[k, 'a_discuter'] else "")))
    e = dec.at[idx, "e"]
    eq_sel, inc_sel = dec.at[idx, "id_equipe"], dec.at[idx, "id_incident"]
    a1, a2 = st.columns([3, 2])
    with a1:
        st.info(fiche_arbitrage(eq_sel, inc_sel, e))
        for lim in e.get("limites", []):
            st.caption(f"Limite : {lim}")
    with a2:
        contrib = e.get("contributions_pct") or {}
        if contrib:
            fig5 = px.bar(x=list(contrib.values()), y=list(contrib.keys()), orientation="h", height=220,
                          labels={"x": "contribution au score (%)", "y": ""},
                          color=[v > 0 for v in contrib.values()],
                          color_discrete_map={True: "#2a9d8f", False: "#e76f51"})
            fig5.update_layout(showlegend=False, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig5, use_container_width=True)
    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("❌ Refuser cette affectation"):
            humain["interdites"].append((eq_sel, inc_sel))
            st.rerun()
    with b2:
        autre = st.selectbox("Équipe à envoyer à la place", sorted(set(res.activites["id_equipe"]) - {eq_sel}))
        if st.button("✋ Forcer cette équipe"):
            humain["forcees"] = [(q, i) for q, i in humain["forcees"] if q != autre] + [(autre, inc_sel)]
            st.rerun()
    with b3:
        if st.button("↺ Annuler mes décisions"):
            humain["interdites"], humain["forcees"] = [], []
            st.rerun()

if humain["interdites"] or humain["forcees"]:
    res_h, k_h = simuler(crise, detail, alpha, beta, routes_coupees, peu_equipes, hs,
                         tuple(humain["interdites"]), tuple(humain["forcees"]))
    k0 = resultats[detail][1]
    ecart = k_h["clients_heures"] - k0["clients_heures"]
    st.markdown("**Impact de vos décisions** "
                f"({len(humain['interdites'])} refus, {len(humain['forcees'])} affectation(s) forcée(s))")
    m1, m2, m3 = st.columns(3)
    m1.metric("Clients·heures (recommandation)", f"{k0['clients_heures']:,.0f}".replace(",", " "))
    m2.metric("Clients·heures (avec vos décisions)", f"{k_h['clients_heures']:,.0f}".replace(",", " "),
              f"{ecart:+,.0f}".replace(",", " "), delta_color="inverse")
    m3.metric("Attente max sensible", f"{k_h['attente_max_sensible_h']:.1f} h",
              f"{k_h['attente_max_sensible_h'] - k0['attente_max_sensible_h']:+.1f} h", delta_color="inverse")
    st.caption("Vos décisions sont appliquées au rejeu ; le reste de la crise est recalculé par la stratégie.")

# --------------------------------------------------------------------------- banc d'essai
fichier = chemin_projet(charger_config()["chemins"]["outputs"]) / "benchmark_kpi.csv"
st.subheader("Banc d'essai sur toutes les crises")
if fichier.exists():
    kpi = pd.read_csv(fichier)
    st.dataframe(resumer(kpi).T, use_container_width=True)
    st.plotly_chart(px.box(kpi, x="strategie", y="clients_heures", points="all", height=380,
                           labels={"clients_heures": "Clients·heures par crise", "strategie": ""}),
                    use_container_width=True)
else:
    st.info("Lancer `python -m crise.benchmark` pour comparer les stratégies sur les 100 crises.")
