import streamlit as st
from batia.services import data as D, scoring as SC, decision as DEC
from batia.ui import charts as G
from batia.ui.theme import header, kpi, demo_note

header(
    "Priorisation des rénovations",
    "29 opérations · scoring multicritère explicable · enveloppe annuelle plafonnée",
)
a = D.equipements()
base = SC.build_scores(
    D.raw("08_plan_investissement.csv"),
    D.raw("01_residences.csv"),
    D.raw("03_logements.csv"),
    a,
)

st.markdown(
    "##### Réglez l'importance de chaque critère (pondération de départ : 40 / 30 / 20 / 10)"
)
c = st.columns(5)
w = {
    k: c[i].slider(lab, 0, 100, SC.POIDS_DEFAUT[k], key=f"w_{k}")
    for i, (k, lab) in enumerate(SC.CRITERES.items())
}
budget = c[4].number_input("Enveloppe (€)", 100_000, 10_000_000, 1_500_000, 100_000)
p = SC.apply_weights(base, w, budget)

k = st.columns(3)
k[0].markdown(
    kpi("Opérations retenues", str(int(p.retenue.sum())), f"sur {len(p)}"),
    unsafe_allow_html=True,
)
k[1].markdown(
    kpi(
        "Budget engagé",
        DEC.fmt_eur(p[p.retenue].cout_estime_ttc.sum()),
        f"enveloppe {DEC.fmt_eur(budget)}",
        "#FF7A1A",
    ),
    unsafe_allow_html=True,
)
k[2].markdown(
    kpi(
        "Opération n°1",
        p.iloc[0].operation_id,
        p.iloc[0].type_operation[:42],
        "#12B76A",
    ),
    unsafe_allow_html=True,
)
st.write("")
l, r = st.columns(2)
l.plotly_chart(G.contributions(p), key="contrib")
r.plotly_chart(G.rang_compare(p), key="rang")

p = p.assign(statut=p.retenue.map({True: "✅ Retenue", False: "⏳ Hors enveloppe"}))
st.dataframe(
    p[
        [
            "rang_score",
            "rang_actuel_chronologique",
            "operation_id",
            "residence_id",
            "type_operation",
            "cout_estime_ttc",
            "gain_conso_ep_estime_kwh_m2_an",
            "origine_demande",
            "score",
            "statut",
        ]
    ],
    hide_index=True,
    width="stretch",
    column_config={
        "rang_score": "Rang BâtIA",
        "rang_actuel_chronologique": "Rang actuel",
        "cout_estime_ttc": st.column_config.NumberColumn("Coût (€)", format="%d"),
        "score": st.column_config.ProgressColumn(
            "Score", min_value=0, max_value=1, format="%.2f"
        ),
        "gain_conso_ep_estime_kwh_m2_an": "Gain kWh/m²/an",
        "origine_demande": "Origine de la demande",
    },
)
st.session_state["ops_retenues"], st.session_state["budget"] = p[p.retenue], budget
demo_note(
    "Le critère « état technique » vient du modèle de risque ; l'énergie, le coût et l'urgence (DPE F/G, interdictions de location, pannes répétées) viennent des fichiers."
)
