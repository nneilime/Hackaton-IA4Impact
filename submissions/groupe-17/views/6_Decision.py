import streamlit as st
from batia.services import data as D, decision as DEC, scoring as SC
from batia.ui.theme import header, demo_note

header(
    "Décision proposée par l'outil",
    "L'IA recommande, l'humain décide : rien n'est appliqué sans validation enregistrée",
)
a, bat, metr = D.equipements(), D.batiments(), D.metriques()
ops = st.session_state.get("ops_retenues")
budget = st.session_state.get("budget", 1_500_000)
if ops is None:
    p = SC.apply_weights(
        SC.build_scores(
            D.raw("08_plan_investissement.csv"),
            D.raw("01_residences.csv"),
            D.raw("03_logements.csv"),
            a,
        ),
        SC.POIDS_DEFAUT,
        budget,
    )
    ops = p[p.retenue]
r = DEC.recommandation(a, bat, ops, budget)

st.markdown("### 1. Résumé")
st.markdown(DEC.resume_md(r, a, metr))

st.markdown("### 2. Actions recommandées")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Bâtiments à traiter en priorité**")
    rg = r["rouges"].assign(signal="🔴", cout=lambda d: d.cout_expose)
    st.dataframe(
        rg[["signal", "batiment_id", "equip_critique", "motif", "cout"]].head(10),
        hide_index=True,
        width="stretch",
        column_config={
            "batiment_id": "Bâtiment",
            "equip_critique": "Équipement clé",
            "motif": "Motif",
            "cout": st.column_config.NumberColumn("Coût exposé (€)", format="%d"),
        },
    )
with c2:
    st.markdown(f"**Top 10 % des équipements à inspecter ({r['top_k']})**")
    t = r["top"].assign(
        risque_pct=r["top"].proba * 100,
        lieu=r["top"].logement_id.fillna("Parties communes"),
    )
    st.dataframe(
        t[["equipement_id", "lieu", "libelle_famille", "risque_pct", "raisons"]].head(
            10
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "risque_pct": st.column_config.ProgressColumn(
                "Risque", min_value=0, max_value=100, format="%.0f %%"
            ),
            "libelle_famille": "Équipement",
        },
    )
st.markdown("**Opérations de rénovation retenues dans l'enveloppe**")
st.dataframe(
    ops[
        [
            "rang_score",
            "operation_id",
            "residence_id",
            "type_operation",
            "cout_estime_ttc",
            "score",
        ]
    ],
    hide_index=True,
    width="stretch",
    column_config={
        "cout_estime_ttc": st.column_config.NumberColumn("Coût (€)", format="%d"),
        "score": st.column_config.ProgressColumn(
            "Score", min_value=0, max_value=1, format="%.2f"
        ),
    },
)


@st.dialog("Confirmer la décision")
def confirmer(choix: str, justification_obligatoire: bool):
    st.write(f"Vous allez enregistrer : **{choix}**")
    nom = st.text_input("Nom du décideur")
    com = st.text_area(
        "Justification"
        + (" (obligatoire)" if justification_obligatoire else " (facultative)")
    )
    manque = (not nom.strip()) or (justification_obligatoire and not com.strip())
    if st.button("Enregistrer", type="primary", disabled=manque):
        DEC.log_decision(choix, nom.strip(), com.strip(), r)
        st.session_state["derniere_decision"] = f"{choix} — {nom.strip()}"
        st.rerun()


st.markdown("### 3. Votre décision")
b = st.columns(3)
if b[0].button("✅ Valider la recommandation", type="primary", width="stretch"):
    confirmer("Recommandation validée", False)
if b[1].button("✏️ Valider avec ajustements", width="stretch"):
    confirmer("Validée avec ajustements", True)
if b[2].button("⛔ Rejeter", width="stretch"):
    confirmer("Recommandation rejetée", True)
if "derniere_decision" in st.session_state:
    st.success(f"Décision enregistrée : {st.session_state['derniere_decision']}")
h = DEC.read_log()
if len(h):
    st.markdown("#### Historique des décisions")
    st.dataframe(h.iloc[::-1], hide_index=True, width="stretch")
demo_note(
    "Chaque décision est tracée dans data/outputs/decisions_log.csv (horodatage, décideur, choix, justification). Un écart avec la recommandation doit être justifié."
)
