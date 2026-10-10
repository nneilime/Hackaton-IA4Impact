import plotly.express as px
import streamlit as st
from batia.services import data as D
from batia.ui import charts as G
from batia.ui.theme import header, kpi

header(
    "Rapports du prestataire & voix des locataires",
    "Rapports trimestriels PDF (T2-T4 2025) lus automatiquement · demandes des locataires",
)
a = D.equipements()
t1, t2, t3 = st.tabs(
    [
        "📑 Synthèse trimestrielle",
        "🔎 Observations du technicien",
        "🗣️ Voix des locataires",
    ]
)

with t1:
    dm, dr, ab = (
        D.table("rapports_depannages_metier"),
        D.table("rapports_depannages_res"),
        D.table("rapports_absences"),
    )
    tris = sorted(dm.trimestre.unique())
    k = st.columns(len(tris))
    for col, t in zip(k, tris):
        x = dm[dm.trimestre == t]
        col.markdown(
            kpi(
                t,
                f"{int(x.depannages.sum())} dépannages",
                f"dont {int(x.arrets_totaux.sum())} arrêts totaux",
                "#FF7A1A",
            ),
            unsafe_allow_html=True,
        )
    st.write("")
    l, r = st.columns(2)
    dr = dr.assign(residence=dr.residence_id.str.replace("RES-", "Rés. "))
    l.plotly_chart(
        G.barres_trimestre(
            dr,
            "residence",
            "total",
            "trimestre",
            "Dépannages par résidence et par trimestre",
        ),
        key="dep",
    )
    ab = ab.assign(residence=ab.residence_id.str.replace("RES-", "Rés. "))
    if len(ab):
        r.plotly_chart(
            G.barres_trimestre(
                ab,
                "residence",
                "taux_absence",
                "trimestre",
                "Locataires absents lors des visites (%)",
                ".0f",
            ),
            key="abs",
        )
    st.caption(
        "Plus le taux d'absence est élevé, moins les équipements sont entretenus, donc davantage de pannes : une relance des locataires est un levier simple."
    )
    st.dataframe(dm, hide_index=True, width="stretch")

with t2:
    o = D.table("rapports_observations").merge(
        a[["equipement_id", "proba", "statut_equip", "remonte_par_rapport"]],
        on="equipement_id",
        how="left",
    )
    c = st.columns(3)
    c[0].markdown(
        kpi("Observations lues", str(len(o)), "sur 3 trimestres"),
        unsafe_allow_html=True,
    )
    c[1].markdown(
        kpi(
            "Équipements distincts",
            str(o.equipement_id.nunique()),
            "signalés par le technicien",
            "#2E6FC4",
        ),
        unsafe_allow_html=True,
    )
    c[2].markdown(
        kpi(
            "Remontés au moins en orange",
            str(int(o.drop_duplicates("equipement_id").remonte_par_rapport.sum())),
            "faible score modèle mais signal fort",
            "#FF7A1A",
        ),
        unsafe_allow_html=True,
    )
    st.write("")
    q = st.multiselect(
        "Trimestre", sorted(o.trimestre.unique()), default=sorted(o.trimestre.unique())
    )
    oo = o[o.trimestre.isin(q)].assign(
        risque_modele=lambda d: d.proba * 100,
        signal=lambda d: d.statut_equip.map(
            {"rouge": "🔴", "orange": "🟠", "vert": "🟢"}
        ),
    )
    st.dataframe(
        oo[
            [
                "trimestre",
                "signal",
                "equipement_id",
                "lieu",
                "famille_libelle",
                "nb_interventions",
                "nb_arrets_totaux",
                "constat",
                "recommandation",
                "risque_modele",
            ]
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "risque_modele": st.column_config.ProgressColumn(
                "Risque modèle", min_value=0, max_value=100, format="%.0f %%"
            )
        },
    )
    st.info(
        "Comment c'est intégré : `pipelines/parse_reports.py` lit les PDF (texte natif), chaque équipement cité est rapproché du modèle par son identifiant, "
        "et un signal fort (« remplacement à étudier », « diagnostic approfondi » ou au moins 2 arrêts totaux) remonte l'équipement au moins en orange."
    )

with t3:
    d = D.demandes()
    pannes = d[
        d.motif.str.contains(
            "panne|fuite|Température|Condensation|Infiltration|VMC|chauffage",
            case=False,
            regex=True,
        )
    ]
    c = st.columns(3)
    c[0].markdown(
        kpi("Demandes (2019-2025)", f"{len(d):,}".replace(",", " "), "tous motifs"),
        unsafe_allow_html=True,
    )
    c[1].markdown(
        kpi(
            "Demandes liées à des pannes",
            f"{len(pannes):,}".replace(",", " "),
            f"{len(pannes) / len(d) * 100:.0f} % du total",
            "#FF7A1A",
        ),
        unsafe_allow_html=True,
    )
    c[2].markdown(
        kpi(
            "Délai moyen de résolution",
            f"{pannes.delai_resolution_h.mean():.0f} h",
            "demandes de pannes",
            "#2E6FC4",
        ),
        unsafe_allow_html=True,
    )
    st.write("")
    l, r = st.columns(2)
    top = (
        pannes.groupby("objet").size().nlargest(10).sort_values().reset_index(name="n")
    )
    l.plotly_chart(
        G._style(
            px.bar(
                top,
                x="n",
                y="objet",
                orientation="h",
                color_discrete_sequence=["#0B3C7D"],
            ),
            380,
            "Ce dont se plaignent le plus les locataires (pannes)",
        ),
        key="obj",
    )
    par = (
        pannes.groupby([pannes.date_creation.dt.year, "residence_id"])
        .size()
        .reset_index(name="n")
        .rename(columns={"date_creation": "annee"})
    )
    r.plotly_chart(
        G._style(
            px.line(par, x="annee", y="n", color="residence_id", markers=True),
            380,
            "Demandes de pannes par résidence et par année",
        ),
        key="par",
    )
    st.caption(
        "Les textes libres des demandes peuvent servir de signaux précoces (« la pression de la chaudière baisse »…) : piste d'amélioration du modèle."
    )
