import streamlit as st
from batia.services import data as D
from batia.ui import charts as G
from batia.ui.theme import header, pill, demo_note

header(
    "Carte du patrimoine",
    "France → métropole toulousaine → bâtiment · signal rouge / orange / vert selon la nature des équipements",
)
bat, lg, a = D.batiments(), D.logements(), D.equipements()

VUES = {
    "France": ({"lat": 46.6, "lon": 2.4}, 4.6),
    "Toulouse (métropole)": ({"lat": 43.59, "lon": 1.43}, 10.4),
}
if "vue" not in st.session_state:
    st.session_state.vue = "France"

b1, b2, b3, b4 = st.columns([1, 1.3, 1.4, 2])
if b1.button("🇫🇷 France", width="stretch"):
    st.session_state.vue = "France"
if b2.button("📍 Toulouse", width="stretch"):
    st.session_state.vue = "Toulouse (métropole)"
couche = b3.radio("Couche", ["Bâtiments", "Logements"], horizontal=True)
res_ids = ["(toutes)"] + sorted(bat.residence_id.unique())
res_sel = b4.selectbox(
    "Zoom sur une résidence",
    res_ids,
    format_func=lambda x: x.replace("RES-", "Résidence "),
)
statuts = st.multiselect(
    "Statuts affichés",
    ["rouge", "orange", "vert", "non suivi"],
    default=["rouge", "orange", "vert"],
)

centre, zoom = VUES[st.session_state.vue]
if res_sel != "(toutes)":
    g = bat[bat.residence_id == res_sel]
    centre, zoom = {"lat": g.lat.mean(), "lon": g.lon.mean()}, 15.2

if couche == "Bâtiments":
    df = bat[bat.statut.isin(statuts)]
    if res_sel != "(toutes)":
        df = df[df.residence_id == res_sel]
    df = df.assign(
        info=df.batiment_id + " (" + df.residence_id.str.replace("RES-", "Rés. ") + ")"
    )
    fig = G.carte(
        df.reset_index(drop=True),
        centre,
        zoom,
        taille=18,
        hover=["info", "motif", "equip_critique", "nb_logements"],
    )
else:
    df = lg[lg.statut.isin(statuts)]
    if res_sel != "(toutes)":
        df = df[df.residence_id == res_sel]
    df = df.assign(info=df.logement_id)
    fig = G.carte(
        df.reset_index(drop=True),
        centre,
        zoom,
        taille=7,
        hover=["info", "batiment_id", "equip_critique", "typologie"],
    )

try:
    ev = st.plotly_chart(fig, key="carte", on_select="rerun", selection_mode="points")
    pts = ev.selection.point_indices if ev and ev.selection else []
except TypeError:
    st.plotly_chart(fig, key="carte")
    pts = []
clic = None
if pts and couche == "Bâtiments":
    clic = df.reset_index(drop=True).iloc[pts[0]].batiment_id

st.subheader("Détail d'un bâtiment")
liste = sorted(bat.batiment_id)
top_id = bat.sort_values("risque_max", ascending=False).iloc[0].batiment_id
bid = st.selectbox(
    "Bâtiment (ou cliquez sur la carte)",
    liste,
    index=liste.index(clic if clic in liste else top_id),
)
row = bat[bat.batiment_id == bid].iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.markdown(f"**Signal** {pill(row.statut)}", unsafe_allow_html=True)
c2.metric("Équipements à risque élevé", int(row.n_rouge))
c3.metric("Équipements à surveiller", int(row.n_orange))
c4.metric("Coût exposé", f"{row.cout_expose:,.0f} €".replace(",", " "))
st.caption(f"Motif : {row.motif} · équipement le plus sensible : {row.equip_critique}")
e = a[a.batiment_id == bid].sort_values("risque_pondere", ascending=False).head(12)
e = e.assign(
    risque_pct=e.proba * 100,
    signal=e.statut_equip.map({"rouge": "🔴", "orange": "🟠", "vert": "🟢"}),
    logement=e.logement_id.fillna("Parties communes"),
)
st.dataframe(
    e[
        [
            "signal",
            "logement",
            "libelle_famille",
            "risque_pct",
            "raisons",
            "cout_remplacement",
        ]
    ],
    hide_index=True,
    width="stretch",
    column_config={
        "risque_pct": st.column_config.ProgressColumn(
            "Risque", min_value=0, max_value=100, format="%.0f %%"
        ),
        "libelle_famille": "Équipement",
        "raisons": "Pourquoi",
        "cout_remplacement": st.column_config.NumberColumn(
            "Remplacement (€)", format="%d"
        ),
    },
)
demo_note(
    "Positions fictives : le jeu de données ne contient pas de coordonnées (« métropole toulousaine »). À remplacer par les vraies adresses géocodées."
)
