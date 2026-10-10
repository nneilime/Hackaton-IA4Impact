import streamlit as st
from batia import config as C
from batia.services import data as D, decision as DEC, scoring as SC
from batia.ui import charts as G
from batia.ui.theme import header, kpi, demo_note

header(
    "Vue d'ensemble du patrimoine",
    f"Risque de panne bloquante · prévision {C.WINDOW_LABEL} · 8 résidences · 1 100 logements",
)
a, bat, iv = D.equipements(), D.batiments(), D.interventions()
st.caption(f"Source des scores : {a.source.iloc[0]}")
metr = D.metriques()

nr, no, nv = [(bat.statut == s).sum() for s in ("rouge", "orange", "vert")]
c = st.columns(5)
c[0].markdown(
    kpi("Bâtiments en danger", str(nr), "à traiter en priorité", C.COULEURS["rouge"]),
    unsafe_allow_html=True,
)
c[1].markdown(
    kpi("Bâtiments à risque", str(no), "à surveiller", C.COULEURS["orange"]),
    unsafe_allow_html=True,
)
c[2].markdown(
    kpi("Bâtiments safe", str(nv), "aucun signal marquant", C.COULEURS["vert"]),
    unsafe_allow_html=True,
)
c[3].markdown(
    kpi(
        "Équipements scorés",
        f"{len(a):,}".replace(",", " "),
        f"risque moyen {a.proba.mean() * 100:.1f} %",
    ),
    unsafe_allow_html=True,
)
c[4].markdown(
    kpi(
        "Coût exposé",
        DEC.fmt_eur(a[a.statut_equip != "vert"].cout_remplacement.sum()),
        "équipements orange / rouge",
        "#FF7A1A",
    ),
    unsafe_allow_html=True,
)

st.write("")
left, right = st.columns([1, 1.6])
with left:
    st.plotly_chart(G.donut_statuts(bat), key="donut")
with right:
    st.plotly_chart(G.heatmap(a), key="heat")

l2, r2 = st.columns([1.2, 1])
with l2:
    st.plotly_chart(G.top_risque(a), key="top")
with r2:
    st.plotly_chart(G.timeline(iv), key="time")

l3, r3 = st.columns(2)
with l3:
    st.plotly_chart(G.treemap_cout(a), key="tree")
with r3:
    st.plotly_chart(G.scatter_age(a), key="scat")

st.subheader("Résumé des données générées")
plan, res, log = (
    D.raw("08_plan_investissement.csv"),
    D.raw("01_residences.csv"),
    D.raw("03_logements.csv"),
)
ops = SC.apply_weights(SC.build_scores(plan, res, log, a), SC.POIDS_DEFAUT, 1_500_000)
reco = DEC.recommandation(a, bat, ops[ops.retenue], 1_500_000)
st.markdown(DEC.resume_md(reco, a, metr))
if st.button("Voir la décision proposée par l'outil", type="primary"):
    st.switch_page("views/6_Decision.py")
demo_note(
    "Le score est un modèle statistique simple, validé dans le passé : il recommande, l'humain décide. Les positions géographiques sont fictives."
)
