"""Mode Jour J : recommandations arbitrées par un humain."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from app.components.carte_techniciens import render_carte_animee
from crise.preparation.jointure import derouler_equipes, preparer_pannes
from crise.simulation.explication import alternative_pour_equipe, expliquer, options_libres, ordre_priorite
from crise.simulation.pilotage import (
    avancer_temps,
    bilan_session,
    creer_session_pilotage,
    enregistrer_decision_humaine,
    liberer_equipes_reserve,
    lieux_sensibles_en_attente,
    proposer_recommandation,
    resume_operationnel,
    tout_accepter,
)
from crise.strategies.allocator import est_sensible

MOTIFS = ["Accès impossible", "Sécurité", "Priorité terrain", "Connaissance locale", "Autre"]
CHOISIR_MOTIF = "— Choisir un motif —"

# Fragment : ne recalcule qu'un bloc de la page (st.fragment depuis Streamlit 1.37,
# st.experimental_fragment avant).
_fragment = getattr(st, "fragment", None) or st.experimental_fragment


def _relancer_page() -> None:
    """Relance toute la page (et pas seulement le fragment) après une décision validée."""
    try:
        st.rerun(scope="app")
    except TypeError:  # Streamlit < 1.37 : st.rerun() relance déjà toute la page
        st.rerun()
SUITES = {
    "autre_incident": "Accepter l'autre incident proposé par le système",
    "choix_libre": "Choisir moi-même un incident",
    "disponible": "Laisser l'équipe disponible (elle rentre à son site si rien d'autre)",
}


def _demarrer(numero: str, strategie: str, pas_min: int, agents_df: pd.DataFrame, postes_df: pd.DataFrame, coupures_df: pd.DataFrame, params: dict[str, Any]) -> None:
    pannes, nb_ecartes, nb_illisible = preparer_pannes(coupures_df, postes_df, numero)
    equipes = derouler_equipes(agents_df)
    plan = st.session_state.get("plan_preparation")
    if plan and plan.get("numero_crise") != numero:
        plan = None
    session = creer_session_pilotage(pannes, equipes, strategie, pas_min, float(params["geo"]["coeff_detour"]), float(params["geo"]["vitesse_moyenne_kmh"]), params["priorite"], float(params["agents"]["duree_max_travail_h"]), float(params["agents"]["duree_min_repos_h"]), plan)
    sites = agents_df[[c for c in ("id_site", "commune", "latitude", "longitude") if c in agents_df.columns]]
    session.update({"numero_crise": numero, "nb_ecartes": nb_ecartes, "nb_illisible": nb_illisible, "sites": sites, "explications": {}})
    st.session_state["jour_j_session"] = session


def render_jour_j(agents_df: pd.DataFrame, postes_df: pd.DataFrame, coupures_df: pd.DataFrame, params: dict[str, Any], libelles: dict[str, str]) -> None:
    st.header("Jour J — centre de décision")
    st.markdown('<div class="human-banner"><strong>Décision sous contrôle humain</strong><span>Le système recommande. Aucune équipe ne part sans validation du responsable.</span></div>', unsafe_allow_html=True)
    crises = sorted(coupures_df["numero_crise"].dropna().unique().tolist())
    session = st.session_state.get("jour_j_session")
    with st.expander("Paramètres de la session", expanded=session is None):
        c1, c2, c3 = st.columns([2, 2, 1])
        numero = c1.selectbox("Crise", crises, key="jj_crise")
        strategie = c2.selectbox("Stratégie de recommandation", list(libelles), format_func=lambda cle: libelles[cle], index=2, key="jj_strategie")
        pas_min = c3.selectbox("Pas", [15, 30, 45, 60], index=1, format_func=lambda x: f"{x} min")
        if st.button("Démarrer le pilotage" if session is None else "Redémarrer la session", type="primary"):
            _demarrer(numero, strategie, pas_min, agents_df, postes_df, coupures_df, params)
            st.rerun()
    session = st.session_state.get("jour_j_session")
    if session is None:
        st.info("Démarrez une session. Un plan de préparation validé pour cette crise sera automatiquement rattaché.")
        return
    if session["termine"]:
        _render_bilan(session, libelles)
        return

    resume = resume_operationnel(session)
    instant = session["instant"]
    st.markdown(f"**Crise {session['numero_crise']}** · pas {session['pas'] + 1} · {instant:%d/%m/%Y %H:%M} · {libelles.get(session['strategie'], session['strategie'])}")
    if session.get("plan_preparation"):
        st.caption("✓ Plan de préparation validé par le responsable et appliqué à cette session.")
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Clients coupés", resume["clients_coupes"])
    k2.metric("Incidents en attente", len(resume["en_attente"]))
    k3.metric("Incidents en cours", len(resume["en_cours"]))
    k4.metric("Équipes libres", resume["equipes_libres"])
    k5.metric("Équipes au repos", resume["equipes_au_repos"])
    k6.metric("Acceptées ce pas", resume["acceptees_ce_pas"])
    equipes_reserve = [equipe["id_equipe"] for equipe in session["equipes"] if equipe["etat"] == "en_reserve"]
    if equipes_reserve:
        with st.expander(f"Réserve opérationnelle — {len(equipes_reserve)} équipe(s)", expanded=False):
            a_liberer = st.multiselect("Équipes à rendre disponibles", equipes_reserve)
            if st.button("Libérer les équipes sélectionnées", disabled=not a_liberer):
                liberer_equipes_reserve(session, a_liberer)
                st.rerun()

    recommandation = proposer_recommandation(session)
    _render_alerte_sensibles(session)
    carte_col, decision_col = st.columns([3, 2], gap="large")
    with carte_col:
        st.subheader("Situation opérationnelle")
        _render_carte(session, recommandation)
        st.subheader("File des incidents")
        if resume["en_attente"]:
            _render_file_incidents(session, resume["en_attente"])
        else:
            st.success("Aucun incident connu en attente.")
    with decision_col:
        st.subheader("Décision requise")
        if recommandation is None:
            _render_pas_arbitre(session, resume)
        else:
            _render_recommandation(session, recommandation)
        st.divider()
        if st.button("🏁 Terminer la crise et voir le bilan", use_container_width=True, disabled=session["pas"] == 0):
            session["termine"] = True
            st.rerun()
        with st.expander("Journal de décision", expanded=False):
            journal = pd.DataFrame(session["journal"])
            st.caption("Aucun arbitrage enregistré.") if journal.empty else st.dataframe(journal.tail(50), hide_index=True, use_container_width=True)


# ── Lieux sensibles ──────────────────────────────────────────────────────────

STATUTS_SENSIBLES = {
    "recommande": "recommandation en cours ↘",
    "a_traiter": "sera recommandé à ce pas",
    "hors_atteinte": "⚠️ aucune équipe disponible ne peut l'atteindre dans ses 12 h — libérez la réserve ou attendez une relève",
    "retenu": "équipe retenue, départ au pas suivant",
}


def _rangs(session: dict[str, Any]) -> dict[str, int]:
    """Rang de traitement de chaque incident en attente selon la stratégie (1 = le prochain)."""
    ordre = ordre_priorite(session["simulation"])
    return dict(zip(ordre["id_incident"].astype(str), ordre["rang"])) if not ordre.empty else {}


def _render_alerte_sensibles(session: dict[str, Any]) -> None:
    """Alerte rouge en haut de l'écran tant qu'un lieu sensible attend une équipe."""
    rangs = _rangs(session)
    lieux = sorted(lieux_sensibles_en_attente(session), key=lambda lieu: rangs.get(lieu["id_incident"], 10**6))
    sans_equipe = [lieu for lieu in lieux if lieu["statut"] != "retenu"]
    if not lieux:
        return
    lignes = [
        f"- **{lieu['id_incident']}** · {lieu['clients']} clients · attend depuis {lieu['attente_h']:g} h · "
        f"{STATUTS_SENSIBLES[lieu['statut']]}" + (f" (équipe {lieu['equipe']})" if lieu["equipe"] else "")
        for lieu in lieux
    ]
    if sans_equipe:
        st.error(
            f"🚨 **{len(sans_equipe)} LIEU(X) SENSIBLE(S) EN ATTENTE D'ÉQUIPE** (hôpital, EHPAD…) — "
            "ils sont traités en priorité absolue.\n" + "\n".join(lignes)
        )
    else:
        st.warning("🏥 Lieux sensibles : une équipe est retenue pour chacun.\n" + "\n".join(lignes))


def _render_file_incidents(session: dict[str, Any], en_attente: list[str]) -> None:
    """
    File des incidents dans l'ordre où la stratégie les traite : le haut de la liste est le
    prochain incident recommandé (les lieux sensibles d'abord, en rouge).
    """
    instant = session["instant"]
    pannes = session["pannes"].copy()
    pannes["id_incident"] = pannes["id_incident"].astype(str)
    file_df = pannes.loc[pannes["id_incident"].isin(en_attente)].copy()
    file_df["sensible"] = est_sensible(file_df)
    file_df["anciennete_h"] = ((instant - file_df["date_incident"]).dt.total_seconds() / 3600).clip(lower=0).round(1)
    rangs = _rangs(session)
    file_df["rang"] = file_df["id_incident"].map(rangs)
    # Sans rang (déjà retenu par ailleurs) : après les autres, lieux sensibles d'abord.
    file_df = file_df.sort_values(["rang", "sensible", "anciennete_h"], ascending=[True, False, False],
                                  na_position="last", kind="mergesort")
    affichage = pd.DataFrame(
        {
            "Priorité": file_df["rang"].map(lambda r: "" if pd.isna(r) else int(r)),
            "Lieu sensible": file_df["sensible"].map({True: "🏥 OUI", False: ""}),
            "Incident": file_df["id_incident"],
            "Clients": file_df["nb_clients"],
            "Réparation (h)": file_df["duree_heures"],
            "En attente depuis (h)": file_df["anciennete_h"],
        }
    )
    rouge = "background-color: #FDE2E2; color: #B91C1C; font-weight: 700"
    st.dataframe(
        affichage.style.apply(
            lambda ligne: [rouge if ligne["Lieu sensible"] else ""] * len(ligne), axis=1
        ),
        hide_index=True,
        use_container_width=True,
    )


# ── Carte ────────────────────────────────────────────────────────────────────

def _render_carte(session: dict[str, Any], recommandation: dict[str, Any] | None) -> None:
    """Carte animée du pas précédent à maintenant, avec les affectations du pas tracées en vert."""
    simulation = session["simulation"]
    contexte = simulation.contexte()
    positions = {str(e["id_equipe"]): (e["latitude"], e["longitude"]) for e in contexte["equipes"]}
    pannes = session["pannes_par_id"]
    a_tracer = list(session["retenues"]) + ([recommandation] if recommandation else [])
    traits = []
    for n, decision in enumerate(a_tracer, start=1):
        depart = positions.get(str(decision["id_equipe"]))
        panne = pannes.get(str(decision["id_incident"]))
        if depart is None or panne is None:
            continue
        traits.append({
            "n": n, "equipe": str(decision["id_equipe"]), "incident": str(decision["id_incident"]),
            "lat0": float(depart[0]), "lon0": float(depart[1]),
            "lat1": float(panne["latitude"]), "lon1": float(panne["longitude"]),
        })
    instant = session["instant"]
    render_carte_animee(
        {"pannes": session["pannes"], "sites": session.get("sites")},
        simulation.resultat(),
        fenetre=(session.get("instant_precedent") or instant, instant),
        propositions=traits,
    )
    st.caption(
        f"Traits verts : {len(session['retenues'])} affectation(s) déjà acceptée(s) à ce pas"
        + (f", et la recommandation en cours (n° {len(traits)})." if recommandation else ".")
    )


# ── Décision ─────────────────────────────────────────────────────────────────

def _render_pas_arbitre(session: dict[str, Any], resume: dict[str, Any]) -> None:
    st.success("Toutes les recommandations de ce pas ont été arbitrées.")
    if session["retenues"]:
        st.markdown(f"**{len(session['retenues'])} équipe(s) partiront** en avançant au pas suivant :")
        st.dataframe(
            pd.DataFrame(session["retenues"])[["id_equipe", "id_incident", "nb_clients", "origine"]].rename(
                columns={"id_equipe": "Équipe", "id_incident": "Incident", "nb_clients": "Clients", "origine": "Décision"}
            ),
            hide_index=True,
            use_container_width=True,
        )
    if resume["crise_terminee"]:
        st.info("Tous les incidents connus sont résolus et aucun nouvel incident n'est attendu.")
    st.write("Le temps ne progresse qu'à votre demande.")
    if st.button("Avancer au pas suivant", type="primary", use_container_width=True):
        avancer_temps(session)
        st.rerun()


def _explication(session: dict[str, Any], id_equipe: str, id_incident: str, cle: str) -> dict[str, Any]:
    """Explication d'un couple équipe → incident, calculée une fois."""
    if cle not in session["explications"]:
        session["explications"][cle] = expliquer(
            session["simulation"], id_equipe, id_incident,
            [session["recommandation"]] if session.get("recommandation") else [],
            session["paires_interdites"],
        )
    return session["explications"][cle]


@_fragment
def _render_recommandation(session: dict[str, Any], recommandation: dict[str, Any]) -> None:
    """
    Bloc de décision. C'est un fragment : ouvrir le refus ou remplir ses champs ne recalcule
    que ce bloc. Seule une décision validée relance toute la page (carte, compteurs).
    """
    id_decision = recommandation["id_decision"]
    id_equipe, id_incident = str(recommandation["id_equipe"]), str(recommandation["id_incident"])
    incident = session["pannes_par_id"][id_incident]
    sensible = "Oui" if bool(incident.get("poste_avec_client_sensible")) else "Non"
    if sensible == "Oui":
        refus = recommandation.get("repropose_apres_refus")
        st.error(
            "🏥 **LIEU SENSIBLE (hôpital, EHPAD…) — INTERVENTION PRIORITAIRE.** "
            "Cet incident passe avant tous les incidents non sensibles."
            + (
                f"\n\n↻ **Reproposé à une autre équipe** après le refus de l'équipe {refus['equipe_refusee']}"
                f" ({refus['motif']})."
                if refus else ""
            )
        )
    st.markdown(f'''<div class="decision-card"><div class="decision-eyebrow">PROPOSITION DU SYSTÈME — NON EXÉCUTÉE</div><h3>Incident {id_incident}</h3><div class="decision-team">Équipe proposée : <strong>{id_equipe}</strong></div><div class="decision-grid"><span><small>Clients</small><strong>{int(incident.get('nb_clients') or 0)}</strong></span><span><small>Trajet</small><strong>{recommandation['temps_estime_trajet_heures']:.2f} h</strong></span><span><small>Dépannage</small><strong>{float(incident.get('duree_heures') or 0):.1f} h</strong></span><span><small>Poste sensible</small><strong>{sensible}</strong></span></div></div>''', unsafe_allow_html=True)

    with st.expander("💡 Pourquoi cette recommandation ?", expanded=True):
        _carte_explication(_explication(session, id_equipe, id_incident, id_decision))

    cle_refus = f"refus_{id_decision}"
    if not st.session_state.get(cle_refus):
        b1, b2 = st.columns(2)
        if b1.button("✅ Accepter", type="primary", use_container_width=True, key=f"accepter_{id_decision}"):
            enregistrer_decision_humaine(session, "accepter")
            _relancer_page()
        # Ouvrir le refus ne recalcule que ce bloc (le clic relance le fragment, pas la page).
        b2.button("❌ Refuser", use_container_width=True, key=f"refuser_{id_decision}",
                  on_click=_ouvrir_refus, args=(cle_refus, True))
        if st.button("👍 Tout accepter pour ce pas", use_container_width=True, key=f"tout_{id_decision}",
                     help="Accepte cette recommandation et toutes les suivantes de ce pas."):
            tout_accepter(session)
            _relancer_page()
    else:
        _render_refus(session, id_equipe, id_incident, id_decision)


def _ouvrir_refus(cle: str, ouvert: bool) -> None:
    st.session_state[cle] = ouvert


def _render_refus(session: dict[str, Any], id_equipe: str, id_incident: str, id_decision: str) -> None:
    simulation = session["simulation"]
    with st.container(border=True):
        st.markdown(f"**❌ Refus : équipe {id_equipe} ✗ incident {id_incident}**")
        st.caption(f"L'incident {id_incident} restera dans la file : il sera recommandé à une autre équipe à ce pas.")
        motif = st.selectbox("Motif du refus (obligatoire)", [CHOISIR_MOTIF] + MOTIFS, key=f"motif_{id_decision}")
        motif = None if motif == CHOISIR_MOTIF else motif
        commentaire = st.text_input("Précision (facultatif)", key=f"comm_{id_decision}")

        exclus = session["incidents_pris"] | {id_incident}
        interdites = session["paires_interdites"] | {(id_equipe, id_incident)}
        alternative = alternative_pour_equipe(simulation, id_equipe, exclus, interdites)
        suites = (["autre_incident"] if alternative else []) + ["choix_libre", "disponible"]
        suite = st.radio(f"Et pour l'équipe {id_equipe} ?", suites, format_func=SUITES.get, key=f"suite_{id_decision}")

        choisi = None
        if suite == "autre_incident":
            choisi = str(alternative["id_incident"])
            st.markdown(f"Le système propose l'incident **{choisi}** :")
            _carte_explication(_explication(session, id_equipe, choisi, f"{id_decision}_alt_{choisi}"), compacte=True)
        elif suite == "choix_libre":
            options = options_libres(simulation, id_equipe, exclus)
            faisables = options.loc[options["faisable"]].set_index("id_incident")
            if faisables.empty:
                st.warning("Aucun incident en attente n'est compatible avec l'amplitude de cette équipe.")
            else:
                choisi = st.selectbox(
                    "Incident (seuls ceux compatibles avec la règle des 12 h sont sélectionnables)",
                    faisables.index.tolist(),
                    format_func=lambda i: _libelle_option(faisables.loc[i], i),
                    key=f"libre_{id_decision}",
                )
            hors_regle = options.loc[~options["faisable"]]
            if not hors_regle.empty:
                with st.expander(f"🔒 {len(hors_regle)} incident(s) non sélectionnable(s) : hors amplitude"):
                    st.dataframe(
                        hors_regle[["id_incident", "clients", "trajet_h", "raison"]].rename(
                            columns={"id_incident": "Incident", "clients": "Clients", "trajet_h": "Trajet (h)", "raison": "Raison"}
                        ),
                        hide_index=True,
                        use_container_width=True,
                    )

        b1, b2 = st.columns(2)
        # Toujours cliquable : s'il manque une information, on dit laquelle.
        if b1.button("Valider le refus", type="primary", use_container_width=True, key=f"valider_refus_{id_decision}"):
            manquants = []
            if motif is None:
                manquants.append("un motif de refus")
            if suite != "disponible" and choisi is None:
                manquants.append("l'incident confié à l'équipe")
            if manquants:
                st.error("Pour valider le refus, choisissez " + " et ".join(manquants) + ".")
            else:
                justification = motif + (f" — {commentaire.strip()}" if commentaire.strip() else "")
                try:
                    enregistrer_decision_humaine(session, "refuser", justification, suite=suite, id_incident=choisi)
                except ValueError as erreur:
                    st.error(str(erreur))
                else:
                    _relancer_page()
        b2.button("↩️ Annuler le refus", use_container_width=True, key=f"annuler_{id_decision}",
                  on_click=_ouvrir_refus, args=(f"refus_{id_decision}", False))


def _carte_explication(e: dict[str, Any], compacte: bool = False) -> None:
    eng = e["engagement"]
    sensible = " · 🏥 clients sensibles" if e["panne"]["sensible"] else ""
    st.markdown(
        f"**Équipe {e['id_equipe']} → incident {e['id_incident']}** — "
        f"{e['panne']['clients']} clients coupés{sensible}, réparation {e['panne']['reparation_h']:g} h"
    )
    st.markdown(f"🎯 **Pourquoi cet incident** : {e['pourquoi_panne']}")
    if e["composantes_score"] and not compacte:
        st.dataframe(
            pd.DataFrame({"Critère": list(e["composantes_score"]), "Contribution": list(e["composantes_score"].values())}),
            hide_index=True,
            use_container_width=True,
            column_config={"Contribution": st.column_config.ProgressColumn("Contribution au score (sur 1)", min_value=0.0, max_value=1.0, format="%.2f")},
        )
    st.markdown(f"👷 **Pourquoi cette équipe** : {e['pourquoi_equipe']}")
    if e["explication_strategie"] and not compacte:
        st.caption(e["explication_strategie"])
    st.markdown(
        f"⏱️ **Engagement** : arrivée {eng['arrivee']:%H:%M}, fin de réparation {eng['fin_reparation']:%H:%M}, "
        f"retour au site possible à {eng['retour_site']:%H:%M}. Amplitude : {eng['amplitude_avant_h']:.1f} h → "
        f"**{eng['amplitude_apres_h']:.1f} h** sur {eng['amplitude_max_h']:g} h (retour compris)."
    )
    if e["equipes_ecartees"] and not compacte:
        st.markdown("🚫 **Équipes plus proches non retenues**")
        st.dataframe(
            pd.DataFrame(e["equipes_ecartees"]).rename(columns={"id_equipe": "Équipe", "trajet_h": "Trajet (h)", "raison": "Raison"}),
            hide_index=True,
            use_container_width=True,
        )


def _libelle_option(option: pd.Series, identifiant: str) -> str:
    sensible = " · 🏥" if option["sensible"] else ""
    return (
        f"{identifiant} — {option['clients']} clients{sensible} · {round(option['trajet_h'] * 60)} min · "
        f"réparation {option['reparation_h']:g} h · priorité {option['rang']}"
    )


# ── Bilan ────────────────────────────────────────────────────────────────────

def _render_bilan(session: dict[str, Any], libelles: dict[str, str]) -> None:
    cle = ("bilan", session["pas"])
    if session.get("bilan_cle") != cle:
        with st.spinner("Calcul de la stratégie automatique de référence…"):
            session["bilan"], session["bilan_cle"] = bilan_session(session), cle
    bilan = session["bilan"]
    libelle = libelles.get(session["strategie"], session["strategie"])
    st.subheader(f"🏁 Bilan — crise {session['numero_crise']} ({bilan['pas_joues']} pas pilotés)")

    d = bilan["decisions"]
    c = st.columns(6)
    c[0].metric("Recommandations", d["recommandations"])
    c[1].metric("Acceptées", d["acceptees"])
    c[2].metric("Refusées", d["refusees"])
    c[3].metric("→ autre incident", d["autre_incident"])
    c[4].metric("→ choix libre", d["choix_libres"])
    c[5].metric("→ laissées disponibles", d["laissees_disponibles"])

    st.markdown(f"#### ⚖️ Pilotage humain vs stratégie automatique « {libelle} »")
    ip = bilan["pilotage"].get("indicateurs", {})
    ir = bilan["reference"].get("indicateurs", {})
    lignes = {
        "Pannes résolues": (len(bilan["pilotage"].get("resolutions", [])), len(bilan["reference"].get("resolutions", []))),
        "Clients rétablis": (ip.get("clients_retablis", 0), ir.get("clients_retablis", 0)),
        "Temps moyen de coupure par client (h)": (ip.get("temps_moyen_coupure_h", 0), ir.get("temps_moyen_coupure_h", 0)),
        "Score objectif : Σ clients × heures de coupure (pannes résolues)": (ip.get("score_objectif", 0), ir.get("score_objectif", 0)),
    }
    comparaison = pd.DataFrame(lignes, index=["Pilotage humain", "Automatique"]).T
    comparaison["Écart"] = comparaison["Pilotage humain"] - comparaison["Automatique"]
    st.dataframe(comparaison, use_container_width=True)
    st.caption(
        "Même crise, mêmes pas de temps. Le score objectif ne compte que les pannes résolues : plus bas = mieux "
        "seulement à nombre de pannes résolues égal. La référence automatique n'applique pas la réserve opérationnelle."
    )

    st.markdown("#### 🗺️ Rejouer la crise pilotée")
    render_carte_animee({"pannes": session["pannes"], "sites": session.get("sites")}, bilan["pilotage"])

    st.markdown("#### 📒 Journal des décisions")
    journal = pd.DataFrame(session["journal"])
    st.dataframe(journal, hide_index=True, use_container_width=True)
    st.download_button(
        "⬇️ Exporter le journal (CSV)",
        journal.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name=f"journal_jour_j_{session['numero_crise']}.csv",
        mime="text/csv",
    )
    if st.button("↩️ Reprendre le pilotage"):
        session["termine"] = False
        st.rerun()
