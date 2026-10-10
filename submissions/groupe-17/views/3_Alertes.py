import streamlit as st
from batia import config as C
from batia.services import data as D
from batia.ui.theme import header, kpi

header(
    "Alertes équipements",
    f"Qui risque une panne bloquante ({C.WINDOW_LABEL}) ? Classement explicable par équipement",
)
a = D.equipements()
f1, f2, f3, f4 = st.columns(4)
res = f1.multiselect(
    "Résidence",
    sorted(a.residence_id.unique()),
    format_func=lambda x: x.replace("RES-", "Résidence "),
)
fam = f2.multiselect("Type d'équipement", sorted(a.libelle_famille.unique()))
stat = f3.multiselect(
    "Signal", ["rouge", "orange", "vert"], default=["rouge", "orange"]
)
seuil = f4.slider("Risque minimum (%)", 0, 100, 5)

d = a[a.statut_equip.isin(stat) & (a.proba * 100 >= seuil)]
if res:
    d = d[d.residence_id.isin(res)]
if fam:
    d = d[d.libelle_famille.isin(fam)]
d = d.sort_values("proba", ascending=False)
k = st.columns(3)
k[0].markdown(
    kpi("Alertes affichées", str(len(d)), "après filtres"), unsafe_allow_html=True
)
k[1].markdown(
    kpi(
        "Coût de remplacement exposé",
        f"{d.cout_remplacement.sum():,.0f} €".replace(",", " "),
        "équipements affichés",
        "#FF7A1A",
    ),
    unsafe_allow_html=True,
)
k[2].markdown(
    kpi(
        "Signalés par le prestataire",
        str(int(d.signal_rapport.sum())),
        "rapports T2-T4 2025",
        "#2E6FC4",
    ),
    unsafe_allow_html=True,
)
st.write("")
d = d.assign(
    signal=d.statut_equip.map(
        {"rouge": "🔴 Danger", "orange": "🟠 Risque", "vert": "🟢 Safe"}
    ),
    risque_pct=d.proba * 100,
    lieu=d.logement_id.fillna("Parties communes") + " · " + d.batiment_id,
    rapport=d.signal_rapport.map({True: "📑 oui", False: ""}),
)
st.dataframe(
    d[
        [
            "signal",
            "equipement_id",
            "lieu",
            "libelle_famille",
            "risque_pct",
            "raisons",
            "rapport",
            "cout_remplacement",
        ]
    ],
    hide_index=True,
    width="stretch",
    height=560,
    column_config={
        "risque_pct": st.column_config.ProgressColumn(
            "Risque", min_value=0, max_value=100, format="%.0f %%"
        ),
        "libelle_famille": "Équipement",
        "equipement_id": "ID",
        "lieu": "Logement · bâtiment",
        "raisons": st.column_config.TextColumn(
            "Pourquoi (facteurs principaux)", width="large"
        ),
        "cout_remplacement": st.column_config.NumberColumn(
            "Remplacement (€)", format="%d"
        ),
    },
)
st.download_button(
    "⬇️ Exporter les alertes (CSV)",
    d.drop(columns=["signal", "rapport", "lieu"]).to_csv(index=False).encode("utf-8"),
    "alertes_batia.csv",
)
