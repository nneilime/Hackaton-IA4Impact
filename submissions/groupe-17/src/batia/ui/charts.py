"""Graphiques Plotly au style commun."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from batia import config as C
from batia.ui.theme import BLEU, ACCENT

COL = C.COULEURS
COL_GRIS = "#98A2B3"
ECHELLE = [[0, "#12B76A"], [0.35, "#FEDF89"], [0.65, "#F79009"], [1, "#D92D20"]]


def _style(fig: go.Figure, h: int = 360, titre: str | None = None) -> go.Figure:
    fig.update_layout(
        height=h,
        title=dict(text=titre, x=0.01, font=dict(size=16, color=BLEU))
        if titre
        else None,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, sans-serif", size=12),
        margin=dict(l=10, r=10, t=50 if titre else 10, b=10),
        legend=dict(orientation="h", y=-0.15),
        hoverlabel=dict(bgcolor="white", font_size=12),
    )
    return fig


def donut_statuts(bat: pd.DataFrame) -> go.Figure:
    c = bat.statut.value_counts().reindex(["rouge", "orange", "vert"]).fillna(0)
    fig = go.Figure(
        go.Pie(
            labels=["Danger", "Risque", "Safe"],
            values=c.values,
            hole=0.62,
            sort=False,
            marker=dict(
                colors=[COL["rouge"], COL["orange"], COL["vert"]],
                line=dict(color="white", width=3),
            ),
            textinfo="value+percent",
            hovertemplate="%{label} : %{value} bâtiments<extra></extra>",
        )
    )
    fig.add_annotation(
        text=f"<b>{int(c.sum())}</b><br>bâtiments",
        showarrow=False,
        font=dict(size=18, color=BLEU),
    )
    return _style(fig, 330, "Signal par bâtiment")


def heatmap(a: pd.DataFrame) -> go.Figure:
    p = a.pivot_table(
        index="libelle_famille", columns="residence_id", values="proba", aggfunc="mean"
    )
    p.columns = [c.replace("RES-", "Rés. ") for c in p.columns]
    fig = px.imshow(
        p * 100,
        color_continuous_scale=ECHELLE,
        aspect="auto",
        text_auto=".0f",
        zmin=0,
        zmax=25,
    )
    fig.update_traces(
        hovertemplate="%{y}<br>%{x} : %{z:.1f} % de risque moyen<extra></extra>"
    )
    fig.update_layout(coloraxis_colorbar=dict(title="%"))
    return _style(fig, 330, "Risque moyen (%) par résidence et type d'équipement")


def top_risque(a: pd.DataFrame, n: int = 15) -> go.Figure:
    t = a.nlargest(n, "proba").sort_values("proba").copy()
    t["etiquette"] = (
        t.equipement_id
        + " · "
        + t.libelle_famille
        + " · "
        + t.logement_id.fillna("parties communes")
    )
    fig = go.Figure(
        go.Bar(
            x=t.proba * 100,
            y=t.etiquette,
            orientation="h",
            marker=dict(color=[COL[s] for s in t.statut_equip]),
            customdata=t.raisons,
            hovertemplate="<b>%{y}</b><br>Risque : %{x:.0f} %<br>%{customdata}<extra></extra>",
        )
    )
    fig.update_xaxes(title="Probabilité de panne bloquante (%)")
    return _style(fig, 430, f"Top {n} des équipements à risque")


def timeline(iv: pd.DataFrame, mois: int = 36) -> go.Figure:
    t = iv.groupby(["mois", "type_intervention"]).size().reset_index(name="n")
    t = t[t.mois > t.mois.max() - pd.DateOffset(months=mois)]
    fig = px.area(
        t,
        x="mois",
        y="n",
        color="type_intervention",
        color_discrete_map={
            "Dépannage": ACCENT,
            "Entretien préventif": "#2E6FC4",
            "Remplacement": "#D92D20",
        },
    )
    fig.update_traces(line=dict(width=1.5))
    fig.update_yaxes(title="Interventions / mois")
    fig.update_xaxes(title=None)
    return _style(fig, 330, "Activité de maintenance (36 derniers mois)")


def treemap_cout(a: pd.DataFrame) -> go.Figure:
    t = a[a.statut_equip != "vert"].copy()
    t["residence"] = t.residence_id.str.replace("RES-", "Résidence ")
    fig = px.treemap(
        t,
        path=["residence", "libelle_famille"],
        values="cout_remplacement",
        color="proba",
        color_continuous_scale=ECHELLE,
        range_color=(0, 0.6),
    )
    fig.update_traces(
        hovertemplate="%{label}<br>Coût exposé : %{value:,.0f} €<extra></extra>"
    )
    return _style(
        fig, 380, "Où se concentre le coût exposé (équipements orange / rouge)"
    )


def scatter_age(a: pd.DataFrame) -> go.Figure:
    fig = px.scatter(
        a,
        x="ratio_vie",
        y="proba",
        color="statut_equip",
        color_discrete_map=COL,
        size="cout_remplacement",
        size_max=22,
        opacity=0.65,
        hover_data=["equipement_id", "libelle_famille"],
        labels={
            "ratio_vie": "Âge / durée de vie de référence",
            "proba": "Probabilité de panne",
        },
    )
    fig.update_yaxes(tickformat=".0%")
    fig.update_xaxes(tickformat=".0%")
    return _style(
        fig, 380, "Âge de l'équipement vs risque (taille = coût de remplacement)"
    )


def carte(
    df: pd.DataFrame, centre: dict, zoom: float, taille: int = 12, hover=None
) -> go.Figure:
    cmap = {**COL, "non suivi": COL_GRIS}
    fig = px.scatter_map(
        df,
        lat="lat",
        lon="lon",
        color="statut",
        color_discrete_map=cmap,
        category_orders={"statut": ["rouge", "orange", "vert", "non suivi"]},
        hover_name=hover[0] if hover else None,
        hover_data={c: True for c in (hover or [])[1:]} | {"lat": False, "lon": False},
        zoom=zoom,
        center=centre,
        map_style="carto-positron",
        height=620,
    )
    fig.update_traces(marker=dict(size=taille, opacity=0.9))
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(orientation="h", y=1.02, x=0, bgcolor="rgba(255,255,255,.8)"),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def contributions(p: pd.DataFrame, n: int = 12) -> go.Figure:
    from batia.services.scoring import CRITERES

    t = p.head(n).iloc[::-1]
    cols = ["#0B3C7D", "#2E6FC4", "#8CB6E8", "#FF7A1A"]
    fig = go.Figure()
    for (k, lab), c in zip(CRITERES.items(), cols):
        fig.add_bar(
            y=t.operation_id + " · " + t.residence_id.str.replace("RES-", "R."),
            x=t[f"p_{k}"],
            name=lab,
            orientation="h",
            marker_color=c,
        )
    fig.update_layout(barmode="stack")
    return _style(
        fig,
        460,
        f"Pourquoi ces {n} opérations sont en tête (contribution de chaque critère)",
    )


def rang_compare(p: pd.DataFrame, n: int = 15) -> go.Figure:
    t = p.head(n)
    fig = go.Figure()
    for _, r in t.iterrows():
        fig.add_trace(
            go.Scatter(
                x=[r.rang_actuel_chronologique, r.rang_score],
                y=[r.operation_id] * 2,
                mode="lines",
                line=dict(color="#D0D5DD", width=3),
                showlegend=False,
                hoverinfo="skip",
            )
        )
    fig.add_trace(
        go.Scatter(
            x=t.rang_actuel_chronologique,
            y=t.operation_id,
            mode="markers",
            name="Rang chronologique actuel",
            marker=dict(size=12, color="#98A2B3"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t.rang_score,
            y=t.operation_id,
            mode="markers",
            name="Rang BâtIA",
            marker=dict(size=14, color=ACCENT, line=dict(color="white", width=2)),
        )
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title="Rang (1 = prioritaire)")
    return _style(
        fig, 460, "Ce que change le score par rapport à l'ordre chronologique"
    )


def barres_trimestre(
    df: pd.DataFrame, x: str, y: str, couleur: str, titre: str, fmt: str = ""
) -> go.Figure:
    fig = px.bar(
        df,
        x=x,
        y=y,
        color=couleur,
        barmode="group",
        color_discrete_sequence=["#0B3C7D", "#2E6FC4", ACCENT],
        text_auto=fmt or True,
    )
    return _style(fig, 340, titre)
