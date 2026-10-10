"""Build the team briefing PDF for the Enedis hackathon (problem, model, algorithm, roadmap)."""
import csv, math, statistics as S, collections as C, os
from datetime import datetime as D
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table,
                                TableStyle, Image, PageBreak, KeepTogether, Preformatted)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "docs", "Enedis_Hackathon_Team_Brief.pdf")
TMP = __import__("tempfile").mkdtemp()
os.makedirs(os.path.dirname(OUT), exist_ok=True)

NAVY, TEAL, ORANGE, GREY, LIGHT = "#1F3A5F", "#2A9D8F", "#E76F51", "#6B7280", "#EEF3F8"

# ---------------------------------------------------------------- data stats (real numbers only)
rd = lambda f: list(csv.DictReader(open(os.path.join(RAW, f), encoding="utf-8-sig"), delimiter=";"))
agents, coup, postes, insee = rd("agents_v2.csv"), rd("coupures_v2_100_crises.csv"), rd("poste_v2.csv"), rd("insee_v2.csv")
pid = {p["id_poste"]: p for p in postes}
n_teams = sum(int(a["nb_equipes"]) for a in agents)
crises = C.defaultdict(list)
for x in coup:
    crises[x["numero_crise"]].append(x)
load = []; sizes = []; spans = []
for L in crises.values():
    t = [D.strptime(x["dateHeureIncident"], "%d/%m/%Y %H:%M") for x in L]
    load.append(sum(int(x["dureeDepannage"][:-1]) for x in L) / n_teams)
    sizes.append(len(L)); spans.append((max(t) - min(t)).total_seconds() / 3600)
over12 = sum(l > 12 for l in load)
orphans = sum(x["id_poste"] not in pid for x in coup)
dups = sum(len(L) - len({x["id_poste"] for x in L}) for L in crises.values())
sens = sum(p["poste_avec_client_sensible"] == "1" for p in postes)
dur = C.Counter(x["dureeDepannage"] for x in coup)
inc_dep = C.Counter(pid[x["id_poste"]]["departement"] for x in coup if x["id_poste"] in pid)
team_dep = C.Counter()
for a in agents:
    team_dep[a["departement"]] += int(a["nb_equipes"])

def hav(la1, lo1, la2, lo2):
    r = math.radians
    return 2 * 6371 * math.asin(math.sqrt(math.sin(r(la2 - la1) / 2) ** 2 + math.cos(r(la1)) * math.cos(r(la2)) * math.sin(r(lo2 - lo1) / 2) ** 2))
dn = sorted(min(hav(float(pid[x["id_poste"]]["latitude"]), float(pid[x["id_poste"]]["longitude"]),
                    float(s["latitude"]), float(s["longitude"])) for s in agents)
            for x in coup if x["id_poste"] in pid)
km_med, km_p90 = S.median(dn), dn[int(0.9 * len(dn))]

# ---------------------------------------------------------------- figures
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})

def fig_example():
    inc = {"A": (150, 8, NAVY), "B": (60, 2, TEAL), "C": (100, 4, ORANGE)}
    orders = [("Biggest first (A, C, B)", "ACB"), ("Smith's rule: highest customers/hour first (B, C, A)", "BCA")]
    fig, ax = plt.subplots(figsize=(7.2, 2.3))
    for row, (label, order) in enumerate(orders):
        t = 0; score = 0
        y = 1 - row
        for k in order:
            n, p, col = inc[k]
            ax.barh(y, p, left=t, color=col, edgecolor="white", height=0.55)
            ax.text(t + p / 2, y, f"{k}\n{n} cust.", ha="center", va="center", color="white", fontsize=8, fontweight="bold")
            t += p; score += n * t
        ax.text(14.3, y, f"score = {score:,} customer-hours".replace(",", " "), va="center", fontsize=9,
                fontweight="bold", color=ORANGE if row == 0 else TEAL)
        ax.text(0, y + 0.38, label, fontsize=8.5, color=GREY)
    ax.set_xlim(0, 20.5); ax.set_ylim(-0.5, 1.6); ax.set_yticks([])
    ax.set_xticks(range(0, 15, 2)); ax.set_xlabel("hours since the crisis started (one team, travel ignored)")
    ax.spines["left"].set_visible(False)
    fig.tight_layout(); f = os.path.join(TMP, "fig_example.png"); fig.savefig(f, dpi=200); plt.close(fig); return f

def fig_load():
    fig, ax = plt.subplots(figsize=(7.2, 2.4))
    ax.hist(load, bins=20, color=TEAL, edgecolor="white")
    ax.axvline(12, color=ORANGE, lw=2)
    ax.set_ylim(0, ax.get_ylim()[1] * 1.25); ax.text(12.2, ax.get_ylim()[1] * 0.92, "one 12 h shift", color=ORANGE, fontsize=9, fontweight="bold")
    ax.set_xlabel(f"repair hours per team in a crisis (total repair hours / {n_teams} teams, travel not included)")
    ax.set_ylabel("number of crises")
    fig.tight_layout(); f = os.path.join(TMP, "fig_load.png"); fig.savefig(f, dpi=200); plt.close(fig); return f

def fig_dep():
    deps = ["Haute-Garonne", "Gers", "Ariège"]
    ti, tt = sum(inc_dep.values()), sum(team_dep.values())
    a = [100 * inc_dep[d] / ti for d in deps]; b = [100 * team_dep[d] / tt for d in deps]
    fig, ax = plt.subplots(figsize=(7.2, 2.2))
    x = range(len(deps)); w = 0.38
    ax.bar([i - w / 2 for i in x], a, w, color=NAVY, label="share of incidents")
    ax.bar([i + w / 2 for i in x], b, w, color=TEAL, label="share of teams")
    for i in x:
        ax.text(i - w / 2, a[i] + 1, f"{a[i]:.0f}%", ha="center", fontsize=8)
        ax.text(i + w / 2, b[i] + 1, f"{b[i]:.0f}%", ha="center", fontsize=8)
    ax.set_xticks(list(x)); ax.set_xticklabels(deps); ax.set_ylabel("%"); ax.set_ylim(0, 68)
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout(); f = os.path.join(TMP, "fig_dep.png"); fig.savefig(f, dpi=200); plt.close(fig); return f

def fig_shift():
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.5), sharey=True)
    for ax, (title, starts) in zip(axes, [("Everyone starts at H0", [0] * 6), ("Staggered: half held in reserve until H8", [0, 0, 0, 8, 8, 8])]):
        for i, s in enumerate(starts):
            t = s
            while t < 40:
                ax.barh(i, min(12, 40 - t), left=t, color=TEAL, height=0.6)
                if t + 12 < 40:
                    ax.barh(i, min(11, 40 - t - 12), left=t + 12, color="#D1D5DB", height=0.6)
                t += 23
            if s:
                ax.barh(i, s, left=0, color="#FCE7E1", height=0.6)
        ax.axvspan(12, 20, color=ORANGE, alpha=0.12 if starts[3] == 0 else 0)
        if starts[3] == 0:
            ax.text(16, -1.1, "nobody working",ha="center", va="center", color=ORANGE, fontsize=8, fontweight="bold")
        ax.set_title(title, fontsize=9, pad=4); ax.set_xlim(0, 40); ax.set_ylim(-1.7, 5.6); ax.set_xlabel("hours"); ax.set_yticks(range(6))
        ax.set_yticklabels([f"team {i+1}" for i in range(6)])
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(color=TEAL, label="working (12 h)"), Patch(color="#D1D5DB", label="rest (11 h)"),
                        Patch(color="#FCE7E1", label="held in reserve")], loc="lower center", ncol=3, frameon=False, fontsize=8)
    fig.tight_layout(rect=(0, 0.1, 1, 1)); f = os.path.join(TMP, "fig_shift.png"); fig.savefig(f, dpi=200); plt.close(fig); return f

F_EX, F_LOAD, F_DEP, F_SHIFT = fig_example(), fig_load(), fig_dep(), fig_shift()

# ---------------------------------------------------------------- styles
FD = r"C:\Windows\Fonts"
pdfmetrics.registerFont(TTFont("Ar", os.path.join(FD, "arial.ttf")))
pdfmetrics.registerFont(TTFont("Ar-B", os.path.join(FD, "arialbd.ttf")))
pdfmetrics.registerFont(TTFont("Ar-I", os.path.join(FD, "ariali.ttf")))
pdfmetrics.registerFont(TTFont("Ar-BI", os.path.join(FD, "arialbi.ttf")))
pdfmetrics.registerFont(TTFont("Mono", os.path.join(FD, "consola.ttf")))
addMapping("Ar", 0, 0, "Ar"); addMapping("Ar", 1, 0, "Ar-B"); addMapping("Ar", 0, 1, "Ar-I"); addMapping("Ar", 1, 1, "Ar-BI")

st = {
    "body": ParagraphStyle("body", fontName="Ar", fontSize=9.6, leading=13.6, spaceAfter=5),
    "h1": ParagraphStyle("h1", fontName="Ar-B", fontSize=16, leading=20, textColor=colors.HexColor(NAVY), spaceBefore=4, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName="Ar-B", fontSize=11.5, leading=15, textColor=colors.HexColor(TEAL), spaceBefore=9, spaceAfter=4),
    "cell": ParagraphStyle("cell", fontName="Ar", fontSize=8.6, leading=11),
    "cellb": ParagraphStyle("cellb", fontName="Ar-B", fontSize=8.6, leading=11, textColor=colors.white),
    "bul": ParagraphStyle("bul", fontName="Ar", fontSize=9.6, leading=13.6, leftIndent=12, bulletIndent=2, spaceAfter=2),
    "box": ParagraphStyle("box", fontName="Ar", fontSize=9.4, leading=13.2),
    "cap": ParagraphStyle("cap", fontName="Ar-I", fontSize=8.3, leading=11, textColor=colors.HexColor(GREY), spaceAfter=8),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=8.2, leading=10.6),
}

def P(t, s="body"): return Paragraph(t, st[s] if isinstance(s, str) else s)
def H1(t): return P(t, "h1")
def H2(t): return P(t, "h2")
def B(items): return [Paragraph(i, st["bul"], bulletText="•") for i in items]

def T(rows, widths, head=True, zebra=True):
    data = [[Paragraph(str(c), st["cellb"] if (head and r == 0) else st["cell"]) for c in row] for r, row in enumerate(rows)]
    t = Table(data, colWidths=[w * cm for w in widths], repeatRows=1 if head else 0)
    cmds = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if head:
        cmds.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)))
    if zebra:
        for r in range(1 if head else 0, len(rows)):
            if r % 2 == 0:
                cmds.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#F8FAFC")))
    t.setStyle(TableStyle(cmds)); return t

def BOX(html, color=TEAL, bg=LIGHT, title=None):
    inner = [P(f"<b>{title}</b>", "box")] if title else []
    inner.append(P(html, "box"))
    t = Table([[inner]], colWidths=[17 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg)),
                           ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(color)),
                           ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return KeepTogether([Spacer(1, 3), t, Spacer(1, 6)])

def CODE(txt):
    t = Table([[Preformatted(txt, st["code"])]], colWidths=[17 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F4F6")),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return KeepTogether([t, Spacer(1, 6)])

def IMG(path, w=17, cap=None):
    from PIL import Image as PI
    iw, ih = PI.open(path).size
    out = [Image(path, width=w * cm, height=w * cm * ih / iw)]
    if cap: out.append(P(cap, "cap"))
    return KeepTogether(out)

def sub(v, s): return f"{v}<sub>{s}</sub>"
w_i, n_i, s_i, p_i, r_i, C_i = sub("w", "i"), sub("n", "i"), sub("s", "i"), sub("p", "i"), sub("r", "i"), sub("C", "i")

# ---------------------------------------------------------------- content
story = []

# Cover
story += [Spacer(1, 2.2 * cm),
          P("HACKATHON LA MÊLÉE 2026 · DÉFI ENEDIS", ParagraphStyle("k", fontName="Ar-B", fontSize=10, textColor=colors.HexColor(TEAL))),
          Spacer(1, 6),
          P("Crisis dispatch: team brief", ParagraphStyle("t", fontName="Ar-B", fontSize=26, leading=31, textColor=colors.HexColor(NAVY))),
          P("Problem, data, objective function, constraints, algorithm and roadmap",
            ParagraphStyle("st", fontName="Ar", fontSize=13, leading=17, textColor=colors.HexColor(GREY))),
          Spacer(1, 0.6 * cm),
          P("Version 1 · 9 October 2026 · Working document: items marked <b>TO DECIDE</b> need a team decision before coding.", "cap"),
          Spacer(1, 0.6 * cm),
          BOX("<br/>".join([
              "1. We build a <b>decision-support demonstrator</b>: it replays a crisis, recommends <b>which team goes to which "
              "incident and in what order</b>, and explains why. A human always makes the final decision.",
              "2. We minimise one score: <b>Σ (weighted customers × hours without power)</b>, summed over incidents.",
              f"3. The core difficulty: in big crises there is <b>more work than the {n_teams} teams can absorb in one 12 h shift</b>. "
              "Choosing the <b>order</b> of repairs matters far more than travel distance.",
              "4. The approach: a <b>simulator</b> plus a <b>priority-based greedy plan improved by local search</b>, re-planned at "
              "every event and compared against simple baselines on <b>all 100 crises</b>.",
              "5. <b>MVP first</b> (replay, plan, score, map, benchmark), <b>then differentiators</b> (cost of an override, "
              "hindsight bound, staggered shifts, pre-positioning, LLM copilot)."]), title="The brief in 5 lines"),
          Spacer(1, 0.4 * cm),
          T([["#", "Section", "#", "Section"],
             ["1", "The challenge in plain words", "7", "Code architecture and interfaces"],
             ["2", "What the data tells us", "8", "MVP vs differentiators"],
             ["3", "The model: objects and their life cycle", "9", "Roadmap and division of work"],
             ["4", "Objective function", "10", "Decisions to settle"],
             ["5", "Constraints", "11", "Limits and risks"],
             ["6", "Algorithm", "12", "Glossary FR / EN"]], [1, 7.5, 1, 7.5]),
          PageBreak()]

# 1
story += [H1("1. The challenge in plain words"),
          P("During a climate crisis (storm, lightning, strong wind), many outages happen at once. Enedis has a fixed number of "
            "field teams, already positioned at operational sites. Today, the choice of which team goes to which outage is made "
            "by hand. We build a tool that <b>recommends</b>, as the crisis unfolds, which team should go where and in what order, "
            "so that power comes back <b>as fast as possible for as many customers as possible</b>, with priority for sensitive "
            "customers. The crisis manager stays in charge: they accept, modify or reject every recommendation."),
          T([["It IS", "It is NOT"],
             ["A logistics / scheduling problem at the moment of the crisis", "A weather or outage forecasting problem"],
             ["A simulation of the crisis as incidents arrive over time", "A tool that already knows the future"],
             ["A recommendation system with explanations", "An autopilot that sends teams on its own"],
             ["Measured against simple reference strategies", "Judged on visuals alone"]], [8.5, 8.5]),
          H2("The three modes described in the README"),
          T([["Mode", "What it means", "Our plan"],
             ["Jour J (crisis day)", "Incidents arrive; the tool assigns teams and recomputes as things change", "<b>MVP core</b>"],
             ["Rejeu (replay)", "Replay a historical crisis and compare several strategies", "<b>MVP</b>: it is how we prove performance"],
             ["Préparation", "Before the storm: suggest where to pre-position teams", "Differentiator (section 6.10)"]], [3.2, 9, 4.8]),
          H2("How we will be judged (README section 9)"),
          T([["Criterion", "What the jury looks at", "What we will show"],
             ["Business relevance", "Answers the challenge, respects the human decision", "Accept / modify / reject on every recommendation"],
             ["Performance", "Beats a reference strategy on the N×T indicator", "One chart: our score vs baselines on 100 crises"],
             ["Robustness", "Handles shocks: 50% of teams gone after 48 h, 2 successive crises, saturation", "Scenario switches in the simulator"],
             ["Explainability", "Recommendations are understandable and contestable", "Decisive factors + cost of the alternative"],
             ["Technical quality", "Structured, reproducible, configurable, documented", "Git repo, README, one config file"],
             ["User experience", "The visualisation helps understand and steer", "Map + timeline + recommendation panel, in French"]],
            [3.3, 6.7, 7]),
          PageBreak()]

# 2
story += [H1("2. What the data tells us"),
          P("We received four CSV files (semicolon-separated, UTF-8) plus the README and the pitch deck. All numbers below are "
            "computed from the files themselves."),
          T([["File", "Rows", "Key columns", "Meaning"],
             ["poste_v2.csv", f"{len(postes):,}".replace(",", " "), "id_poste, commune, lat/lon, nb_clients, poste_avec_client_sensible",
              "One substation. Customers 5 to 150 (generated). Sensitive is a 0/1 flag."],
             ["coupures_v2_100_crises.csv", f"{len(coup):,}".replace(",", " "), "numero_crise, id_incident, id_poste, causeInterruption, dateHeureIncident, dureeDepannage",
              "One incident = one substation down, at a given time, with a repair duration of 2, 4 or 8 h."],
             ["agents_v2.csv", str(len(agents)), "id_site, commune, departement, lat/lon, nb_equipes",
              f"{len(agents)} operational sites holding {n_teams} teams in total."],
             ["insee_v2.csv", str(len(insee)), "code_insee, commune, lat/lon, nb_postes", "Commune reference (for display / aggregation)."]],
            [3.8, 1.4, 6.3, 5.5]),
          P("Links: <font name='Mono'>coupures.id_poste → poste.id_poste</font>, <font name='Mono'>poste.code_insee → insee.code_insee</font>; "
            "distances are computed from site coordinates to substation coordinates.", "cap"),
          H2("Key numbers and what they imply"),
          T([["Finding", "Consequence for our design"],
             [f"100 crises (2016-2018), {min(sizes)}-{max(sizes)} incidents each (median {S.median(sizes):.0f}), arriving over "
              f"{min(spans):.0f}-{max(spans):.0f} h. Crises never overlap.",
              "We have a full test bench: every strategy can be scored on 100 crises, not one demo. Two successive crises can be simulated by chaining two."],
             [f"Work per crisis: median {S.median(load):.1f} h of repair per team, max {max(load):.1f} h. {over12} crises exceed 12 h per team.",
              "Teams get saturated and a queue forms. The 12 h / 11 h work rule really bites on big crises."],
             [f"Repairs last 2, 4 or 8 h. Median distance to the nearest site is {km_med:.0f} km (90% under {km_p90:.0f} km), i.e. about 15-30 min by road.",
              "Repair time dominates travel. The decision is mostly about <b>order</b> and about balancing load between sites. Straight-line distance × detour factor is enough."],
             ["Repair duration does not depend on the cause (every cause appears with 2, 4 and 8 h).",
              "Cause is a label only; we cannot predict duration from it. Duration uncertainty can be modelled as noise (bonus)."],
             [f"Customers per substation are uniform 5-150. {sens:,} substations ({100*sens/len(postes):.0f}%) are flagged sensitive.".replace(",", " "),
              "Weight = customers × (1 + β × sensitive). β is a visible setting."],
             ["Gers holds about a third of incidents but under a quarter of teams (see chart below).",
              "Pre-positioning teams before the storm has measurable value (differentiator)."]], [8, 9]),
          Spacer(1, 6),
          IMG(F_LOAD, cap=f"Figure 1. Load per team in each of the 100 crises. Right of the orange line, the teams cannot finish the work in one 12 h shift even if it were perfectly balanced and travel were free ({over12} crises)."),
          IMG(F_DEP, cap="Figure 2. Share of incidents vs share of teams per department. Gers is under-resourced relative to the incidents it gets; Ariège has more teams than its share of incidents."),
          H2("Data quality points to handle (and mention as limits)"),
          *B([f"{orphans} incidents reference a substation that does not exist in poste.csv: drop them and log it.",
              f"{dups} cases of the same substation failing twice within one crisis: treat as separate incidents (or merge: TO DECIDE).",
              f"The README says 20 sites; the file has {len(agents)}. We use the file.",
              "Customer counts and incident locations are synthetic (stated by the README); no personal data is involved."]),
          Spacer(1, 10)]

# 3
story += [H1("3. The model: objects and their life cycle"),
          P("The README recommends an object-oriented model. These are the objects we will code, with the attributes we use."),
          T([["Object", "Source", "Attributes we use"],
             ["Poste (substation)", "poste.csv", "id, position (lat/lon), customers, sensitive flag, commune, department"],
             ["Incident", "coupures.csv", "id, substation, arrival time, cause, repair duration, status, restoration time"],
             ["Site", "agents.csv", "id, position, number of teams based there"],
             ["Équipe (team)", "derived from agents.csv", "id, home site, current position, status, current job, work time used in this shift, next rest"],
             ["Scénario", "assembled", "one crisis = substations + its incidents + teams + configuration"],
             ["Plan / Décision", "computed", "for each team, an ordered list of incidents; each decision is assign, reassign, hold in reserve or reposition"]],
            [3.2, 3.3, 10.5]),
          H2("Life cycle"),
          T([["Incident", "Arrived → Waiting → Team en route → Being repaired → <b>Restored</b>"],
             ["Team", "Available → Travelling → Repairing → (Available or Idle) → Resting 11 h after 12 h of work → Available …"]],
            [3, 14], head=False),
          H2("Notation used in the rest of the document"),
          T([["Symbol", "Meaning", "Where it comes from"],
             ["i", "an incident", "coupures.csv"],
             ["k", "a team", "agents.csv (nb_equipes per site)"],
             [r_i, "arrival time of incident i", "dateHeureIncident"],
             [p_i, "repair duration of incident i (2, 4 or 8 h)", "dureeDepannage"],
             [n_i, "customers cut off by incident i", "nb_clients of its substation"],
             [s_i, "1 if the substation has sensitive customers, else 0", "poste_avec_client_sensible"],
             ["β", "extra weight for sensitive customers (setting, default 3)", "our choice"],
             [w_i, f"weight of incident i = {n_i} × (1 + β × {s_i})", "computed"],
             ["τ(a, b)", "travel time from point a to point b", "distance × 1.3 / average speed"],
             [C_i, "time at which repair of i ends = customers restored", "computed by the plan"],
             [f"{C_i} − {r_i}", "total outage time of i = waiting + travel + repair", "computed"]],
            [2.6, 9, 5.4]),
          PageBreak()]

# 4
story += [H1("4. Objective function"),
          H2("4.1 The main objective, in words"),
          P("From the moment an incident appears until its repair ends, its customers are in the dark. Each incident therefore "
            "accumulates <b>customer-hours without power</b>. We want the <b>total</b> over all incidents to be as small as possible, "
            "giving extra weight to sensitive customers."),
          CODE("minimise   SCORE = Σ over incidents i of   w_i × (C_i − r_i)\n\n"
               "           w_i       = n_i × (1 + β × s_i)          customers, boosted if sensitive\n"
               "           C_i − r_i = waiting + travel + repair    hours without power"),
          BOX("The README writes the formula as <i>maximiser Σ Nbclients × Temps de coupure</i>. Taken literally, that would reward "
              "long outages. The intent is clearly to <b>minimise</b> it, and the README itself says the objective is "
              "\"to be adjusted and justified\". We state this reading explicitly in our README.", color=ORANGE, bg="#FDF2EE",
              title="Note on the README formula"),
          P(f"<b>Example of the weight:</b> with β = 3, a sensitive substation with 50 customers weighs 50 × (1 + 3) = 200, "
            "the same as a normal substation with 200 customers."),
          H2("4.2 Worked example: why order matters"),
          P("One team, three incidents known at time 0, travel ignored. A: 150 customers, 8 h repair. B: 60 customers, 2 h. "
            "C: 100 customers, 4 h. The score is the sum of customers × time at which each one is restored."),
          IMG(F_EX, cap="Figure 3. Repairing the biggest incident first looks natural but scores worse. Serving the best customers-per-hour ratio first (B: 30/h, C: 25/h, A: 18.75/h) restores 13% fewer customer-hours of outage."),
          BOX("For a single team with no travel, serving incidents in decreasing order of <b>w<sub>i</sub> / p<sub>i</sub></b> "
              "(customers restored per hour of work) is <b>provably optimal</b>. This is known as Smith's rule (1956). Our "
              "priority index (section 6.2) extends it with travel time. It also gives a simple explanation for the manager: "
              "<i>\"this incident goes first because it brings back the most customers per hour of work\"</i>.",
              title="Smith's rule: the core intuition"),
          H2("4.3 The full objective (configurable)"),
          P("The README invites us to enrich the objective with business penalties. We use a weighted sum where every weight "
            "λ is visible in the configuration and in the interface:"),
          CODE("minimise   Σ w_i × (C_i − r_i)                    customer impact (main term)\n"
               "         + λ_stab × number of teams re-routed while en route      plan stability\n"
               "         + λ_trav × total travel time                             safety / cost, tie-breaker\n"
               "         + λ_eq   × max over i of (C_i − r_i)                     fairness: no forgotten incident"),
          T([["Term", "Why it is there", "Default"],
             ["Stability", "A manager will not trust a plan that reshuffles everything at every update. Re-routing a team already on the road must be worth it.", "on, moderate"],
             ["Travel", "Less driving in storm conditions is safer. Mostly breaks ties between equal options.", "small"],
             ["Fairness", "Without it, a small remote substation (e.g. mountain Ariège) could wait forever behind bigger ones.", "small"]],
            [2.4, 12, 2.6]),
          H2("4.4 Indicators we report (but do not optimise directly)"),
          *B(["Weighted customer-hours (the score) and unweighted customer-hours (the README's N×T)",
              "Restoration time of sensitive customers",
              "% of customers restored after 4 h, 8 h, 12 h, 24 h",
              "Saturation: number of incidents waiting with no team available, over time",
              "Team utilisation and maximum outage per department"]),
          PageBreak()]

# 5
story += [H1("5. Constraints"),
          P("Hard constraints must always hold (safety and work rules come first, as the README insists). Every rule is a "
            "parameter in the configuration, never a hard-coded assumption, because the organisers may change it."),
          T([["#", "Constraint", "In plain words", "Setting (default)"],
             ["C1", "Every incident is served", f"Each incident gets exactly q<sub>i</sub> teams. Today q<sub>i</sub> = 1. If q<sub>i</sub> > 1, repair starts when the last team arrives.", "teams_per_incident = 1"],
             ["C2", "One job at a time, in sequence", "A team does one incident, then travels to the next. Next start ≥ previous end + travel time. The first trip starts from the home site.", "fixed"],
             ["C3", "No anticipation", "A team cannot leave for an incident before the incident is known. Replays must not peek at the future.", "fixed"],
             ["C4", "No interruption", "Once a repair starts, it runs until it is finished.", "fixed"],
             ["C5", "Work window", "A team works at most 12 h in a row, then rests 11 h. Travel + repair must fit <b>entirely</b> in the window: never start a job you cannot finish.", "shift_h = 12, rest_h = 11, travel_counts = True, allow_split = False"],
             ["C6", "Where the team rests", "The team rests where it is and restarts from there (or goes back to base).", "rest_at = 'site' (TO DECIDE)"],
             ["C7", "Locked decisions", "Teams already travelling or repairing keep their job. An operator choice forces (or forbids) an assignment.", "from the interface"],
             ["C8", "Unavailability shocks", "A team becomes unavailable from some time onward (README stress test: 50% of teams after 48 h).", "unavailability = []"],
             ["C9", "Sensitive deadline (optional)", "Sensitive incidents must start within D hours.", "off"]],
            [1, 3.3, 8.7, 4]),
          Spacer(1, 6),
          BOX(f"If all {n_teams} teams start their shift at the start of the crisis, <b>they all go to rest at the same time</b>, at hour 12, "
              "and nobody is in the field for 11 hours. That is exactly when big crises still have a queue (Figure 1). The fix is a "
              "<b>mobilisation time per team</b>: hold some teams in reserve and start them later, so that the work is covered "
              "around the clock. The README calls this <i>maintien en réserve</i>. The MVP starts everyone at hour 0; staggered "
              "mobilisation is one of our levers (section 6.9).", color=ORANGE, bg="#FDF2EE", title="The trap hidden in C5"),
          IMG(F_SHIFT, cap="Figure 4. Schematic with 6 teams. Left: everyone starts together and the field is empty between hours 12 and 23. Right: staggering keeps teams working through the night."),
          H2("Questions to settle on the constraints (TO DECIDE)"),
          *B(["Does travel count as work time? Our default: yes.",
              "Can a repair cross the end of a shift? Our default: no (safety).",
              "Does a team rest on site or back at base? Our default: on site.",
              "Can idle teams reposition towards busy areas while waiting? The README's step T5 mentions <i>repositionner</i>. Our default: yes, as a recommendation.",
              "Do all teams start at hour 0, or do we allow staggered mobilisation? MVP: hour 0; lever later."]),
          Spacer(1, 10)]

# 6
story += [H1("6. Algorithm"),
          H2("6.1 Why not an exact solver"),
          P("In scheduling terms, the problem is <i>parallel machines with release dates, sequence-dependent set-up times and "
            "weighted completion time</i>, written R | r<sub>j</sub>, s<sub>ij</sub> | Σ w<sub>j</sub>C<sub>j</sub>, plus work windows. "
            "Even the single-team version with release dates is NP-hard. With about 165 incidents and 63 teams, re-solved every "
            "few seconds, an exact solver is out of reach. We use a <b>heuristic</b>, and an exact solver only offline on small "
            "cases to measure how good the heuristic is."),
          H2("6.2 The priority index"),
          CODE("priority(i, k) = w_i / ( τ(position of team k, i) + p_i )\n\n"
               "   = weighted customers brought back per hour that team k spends on incident i"),
          P("This extends Smith's rule (section 4.2) to travel. High priority means many customers, a short repair and a team close by."),
          H2("6.3 Reference strategies (baselines), required by the README"),
          T([["Baseline", "Rule"],
             ["B0-a First come, first served", "The oldest waiting incident gets the nearest available team."],
             ["B0-b Nearest", "Each team that becomes free takes the nearest waiting incident."],
             ["B0-c Business rule", "The incident with the most customers (sensitive first) gets the nearest available team."]], [5, 12]),
          H2("6.4 Our online policy (MVP): plan everything, commit only the next step"),
          P("The README describes a T1-T5 decision loop. We implement it as an <b>event-driven</b> loop. It recomputes the plan "
            "whenever something happens: a new incident, a team becomes free, a shift ends, or the operator overrides."),
          CODE("on every event at time t:\n"
               "  T1  update the list of unresolved incidents (new arrivals included)\n"
               "  T2  snapshot the teams: position, status, work time left in the shift\n"
               "      lock everything already committed (C7)\n"
               "  T3  GREEDY: repeatedly insert the (team, incident) pair with the best priority\n"
               "      that still fits in the team's shift (C5), until all incidents are placed\n"
               "      IMPROVE: local search for N milliseconds on the full objective\n"
               "  T4  dispatch only the NEXT job of each idle team  -> shown as recommendations\n"
               "  T5  when a repair ends: customers restored, team freed, loop again"),
          P("Because we only commit the next step, the rest of the plan stays flexible and re-planning is natural. The stability "
            "term (λ<sub>stab</sub>) prevents useless reshuffles."),
          H2("6.5 Local search moves"),
          T([["Move", "What it does"],
             ["Relocate", "Move one incident from team A's list to team B's list (any position)."],
             ["Swap", "Exchange two incidents between two teams."],
             ["Reorder", "Change the position of an incident inside one team's list."]], [3, 14]),
          P("A move is kept only if it lowers the full objective and respects every hard constraint. The search stops after a fixed "
            "time budget (for example 200 ms), so the tool stays real-time."),
          H2("6.6 Hindsight bound (differentiator)"),
          P("Offline, we solve each crisis <b>knowing all incidents in advance</b>, with a longer time budget (exact CP-SAT on small "
            "crises). No real policy can beat this, so it is a lower bound on the score. That lets us say: <i>\"our policy closes X% "
            "of the gap between the baseline and the best achievable\"</i>. Few teams will show this."),
          H2("6.7 Counterfactuals: the cost of an override and contrastive explanations"),
          P("To answer \"what if team 7 goes to Muret instead?\", we force that assignment (C7), re-solve the rest, and compare "
            "the two scores. The same mechanism powers three features:"),
          *B(["<b>Override cost:</b> when the operator changes a recommendation, show \"this choice costs +X customer-hours\".",
              "<b>Contrastive explanation:</b> \"team 3 goes to A rather than B; the alternative would cost +Y\".",
              "<b>LLM copilot tools:</b> the LLM calls this function; it never computes numbers itself."]),
          H2("6.8 Explanation of each recommendation"),
          P("Every recommendation shows the factors behind it: customers affected, sensitive or not, travel time, repair time, "
            "work time left for the team, its priority rank, and the cost of the best alternative. A confidence or limits line "
            "is included where relevant, as the README asks."),
          H2("6.9 Staggered mobilisation (differentiator)"),
          P("Choose a start time for each team (all at hour 0, or some held in reserve) so that the field is never empty during "
            "rest periods. We evaluate by simulation: try a few patterns (0 %, 25 %, 50 % held back for 4, 6 or 8 h) and keep the "
            "best average score over the 100 crises."),
          H2("6.10 Pre-positioning (differentiator, README preparation mode)"),
          P("Before the storm, move teams between sites (for example from Toulouse towards Gers). We search over moves of one team "
            "from one site to another and evaluate each layout by simulating our policy on historical crises. To be honest, we "
            "evaluate on crises <b>not used</b> to choose the layout (train / test split)."),
          H2("6.11 Travel-time model"),
          P(f"τ = straight-line distance × 1.3 (road detour) ÷ average speed (default 50 km/h, slower for mountain sites such as "
            f"Ariège and Luchon). This is justified because the median trip is about {km_med:.0f} km while repairs take 2-8 h. "
            "Real road routing (OSRM) is a possible later upgrade."),
          PageBreak()]

# 7
story += [H1("7. Code architecture and interfaces"),
          T([["Layer", "Responsibility", "Rule"],
             ["DATA", "Load and clean CSVs, build Poste / Incident / Team / Site / Scenario, compute travel times", "The only code that knows the CSV format"],
             ["SIMULATOR", "Event clock; applies constraints C2-C8; computes the score and KPIs", "The single source of truth for numbers"],
             ["ENGINE", "Policies (baselines, ours), counterfactuals, hindsight bound", "The only source of decisions"],
             ["INTERFACE", "Map, timeline, recommendation panel (French), LLM copilot", "Never computes; only displays and asks the engine"]],
            [2.6, 9.4, 5]),
          H2("The three contracts that let us work in parallel"),
          CODE("load_scenario(crisis_id, config)        -> Scenario\n"
               "policy.decide(state, locks)             -> Plan            # ordered jobs per team\n"
               "simulate(scenario, policy, config)      -> Result          # timeline of events\n"
               "score(result, weights)                  -> Score + KPIs\n"
               "counterfactual(state, forced, policy)   -> Plan + delta score"),
          H2("Proposed repository layout"),
          CODE("enedis-hackathon/\n"
               "  data/raw/            original files (never edited)\n"
               "  config/default.yaml  β, λ weights, shift rules, speeds, time budget\n"
               "  src/data/            loaders, cleaning, travel times\n"
               "  src/sim/             simulator, events, score, KPIs\n"
               "  src/engine/          baselines, greedy, local search, counterfactual, bound\n"
               "  src/app/             Streamlit app (map, timeline, recommendations)\n"
               "  src/copilot/         LLM layer (tools that call the engine)\n"
               "  bench/               100-crisis benchmark, robustness scenarios\n"
               "  docs/                this brief, hypotheses and limits"),
          H2("Technology"),
          *B(["Python everywhere (recommended by the README).",
              "Streamlit for the interface: fastest path to a working demo in 48 h (suggested by the README). Map with pydeck or folium.",
              "OR-Tools CP-SAT only for the offline hindsight bound on small crises.",
              "An LLM API for the copilot, calling engine functions as tools."]),
          PageBreak()]

# 8
story += [H1("8. MVP vs differentiators"),
          H2("MVP: must work end-to-end before anything else"),
          T([["#", "Item", "Done when…", "Criterion served"],
             ["M1", "Data loaders + domain objects", "One crisis loads into a Scenario; orphans logged", "Technical quality"],
             ["M2", "Simulator + score + KPIs", "A replay runs with constraints C1-C8 and prints the score", "Performance"],
             ["M3", "3 baselines + our greedy policy", "Both run on the same crisis through the same simulator", "Performance"],
             ["M4", "Benchmark on 100 crises", "One chart: our score vs baselines, average and spread", "Performance, robustness"],
             ["M5", "Interface v1 (French)", "Map of the 3 departments, time slider, recommendation list with accept / reject", "UX, business relevance"],
             ["M6", "Explanation factors", "Each recommendation shows its factors and its rank", "Explainability"],
             ["M7", "README + hypotheses + limits", "Someone outside the team can run it", "Technical quality"]],
            [1, 4.5, 7.2, 4.3]),
          H2("Differentiators, in order of value for effort"),
          T([["#", "Feature", "Why it stands out", "Depends on"],
             ["D1", "Override cost + contrastive explanations", "Makes the tool contestable, which is exactly the explainability criterion", "M3"],
             ["D2", "Local search on top of greedy", "Better scores, still real-time", "M3"],
             ["D3", "Hindsight bound", "\"We close X% of the gap to the best possible\": a strong, rare argument", "M4"],
             ["D4", "Robustness scenarios", "50% of teams lost, 2 successive crises, few teams: one switch each", "M2"],
             ["D5", "Staggered mobilisation", "Solves the everyone-rests-at-once trap; a real operational insight", "M2"],
             ["D6", "Pre-positioning mode", "Covers the README's preparation mode with a data-backed result", "M4"],
             ["D7", "Levers analysis", "\"One more team at Auch saves X customer-hours\": what a manager acts on", "M4"],
             ["D8", "LLM copilot (French)", "Questions and what-if in natural language, numbers always from the engine", "D1"]],
            [1, 4.4, 8.4, 3.2]),
          PageBreak()]

# 9
story += [H1("9. Roadmap and division of work"),
          P("Hours are counted from the moment we start coding (H0). Adjust to the real hackathon schedule; the order matters more "
            "than the exact times."),
          T([["Phase", "When", "Goal", "Milestone (definition of done)"],
             ["0. Align", "H0 - H1", "Read this brief, settle the TO DECIDE items, create the repo skeleton, assign owners", "Repo exists, config file agreed, owners named"],
             ["1. MVP core", "H1 - H8", "M1, M2, M3", "One crisis replayed end-to-end; our score vs one baseline printed"],
             ["2. MVP complete", "H8 - H16", "M4, M5, M6 + D2", "100-crisis chart; Streamlit replay with recommendations and factors"],
             ["3. Differentiators", "H16 - H30", "D1, D3, D4, D5, then D6 / D7 / D8 as time allows", "Each feature visible in the demo, or dropped cleanly"],
             ["4. Freeze and pitch", "last ~6 h", "M7, pitch deck, demo rehearsal, backup video", "Feature freeze; demo runs twice without errors"]],
            [2.6, 2, 6.2, 6.2]),
          H2("Workstreams"),
          T([["Stream", "Contents", "Can start", "Owner"],
             ["A. Data", "Loaders, cleaning, travel times, Scenario objects", "Now", ""],
             ["B. Simulator + score", "Event clock, constraints, KPIs", "Now (on a mock Scenario)", ""],
             ["C. Engine", "Baselines, greedy, local search, counterfactual", "Now (on the State / Plan contract)", ""],
             ["D. Benchmark", "100 crises, hindsight bound, robustness scenarios", "After B + C", ""],
             ["E. Interface", "Streamlit map, timeline, recommendation panel", "Now (on a mock Result)", ""],
             ["F. Explanations / LLM", "Factor display, override cost, copilot", "After C (counterfactual)", ""]],
            [3.4, 6.6, 4.5, 2.5]),
          P("With 4 people, one possible split: (1) A + B, (2) C, (3) E, (4) D + F. Agree on the contracts in section 7 first, "
            "so nobody waits on anybody."),
          H2("Demo script (target: 5 minutes)"),
          *B(["The map at crisis start: sites, teams, first incidents appearing.",
              "Recommendations stream in with their factors; the manager accepts them.",
              "The manager overrides one: the tool re-plans and shows what the override costs.",
              "The benchmark chart: our policy vs baselines on 100 crises (and the gap to the hindsight bound).",
              "Stress test: half the teams disappear; the plan adapts.",
              "Copilot question in French, answered with figures taken from the engine."]),
          PageBreak()]

# 10-12
story += [H1("10. Decisions to settle (with our proposed default)"),
          T([["Decision", "Proposed default", "Why"],
             ["Reading of the README formula", "Minimise Σ w(C − r)", "Maximising outage time makes no sense"],
             ["β (sensitive weight)", "3, with a slider", "Visible and adjustable; the organisers gave no value"],
             ["Travel counts as work", "Yes", "Safety and work-time rules"],
             ["Job crossing the end of a shift", "Forbidden", "Safety first"],
             ["Rest location", "On site", "Simplest; base return is an option"],
             ["Shift start", "All at hour 0 (MVP); staggered as a lever", "Keep the MVP simple, then show the gain"],
             ["Idle teams may reposition", "Yes, as a recommendation", "README step T5"],
             ["Duplicate incidents on one substation", "Separate incidents", "Keeps data as given"],
             ["Travel model", "Straight line × 1.3 at 50 km/h", "Trips (~15-30 min) are much shorter than repairs (2-8 h)"],
             ["Interface technology", "Streamlit", "Speed of delivery; suggested by the README"]], [5.2, 5.6, 6.2]),
          H1("11. Limits and risks"),
          *B(["Synthetic customer counts and relocated incidents: results show the method's value, not real-world gains.",
              "Repair durations are taken as known; in reality they are uncertain (the bonus can address this with noise).",
              "No road blockages and no network topology: repairing one substation restores only that substation.",
              "All teams are interchangeable: the README mentions skills, but the data has none.",
              "Risk: spending too long on the interface or the LLM before the benchmark exists. Mitigation: phase gates in section 9."]),
          H1("12. Glossary FR / EN"),
          T([["Français", "English", "Français", "English"],
             ["poste", "substation", "dépannage", "repair"],
             ["coupure / incident", "outage / incident", "durée de dépannage (gamme)", "standard repair duration"],
             ["client sensible", "sensitive customer (e.g. medical, critical site)", "réalimentation", "power restoration"],
             ["équipe / agent", "field team", "prépositionnement", "pre-positioning"],
             ["site opérationnel", "operational base", "maintien en réserve", "holding teams in reserve"],
             ["rejeu", "replay", "saturation", "no team available for waiting incidents"]], [3.6, 4.9, 3.8, 4.7]),
          ]

# ---------------------------------------------------------------- page template
def on_page(c, doc):
    c.saveState()
    if doc.page > 1:
        c.setFont("Ar", 7.5); c.setFillColor(colors.HexColor(GREY))
        c.drawString(2 * cm, A4[1] - 1.2 * cm, "Défi Enedis · Crisis dispatch: team brief · v1")
        c.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"{doc.page}")
        c.setStrokeColor(colors.HexColor("#CBD5E1")); c.setLineWidth(0.4)
        c.line(2 * cm, A4[1] - 1.35 * cm, A4[0] - 2 * cm, A4[1] - 1.35 * cm)
    else:
        c.setFillColor(colors.HexColor(NAVY)); c.rect(0, A4[1] - 0.9 * cm, A4[0], 0.9 * cm, fill=1, stroke=0)
    c.restoreState()

doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.7 * cm,
                      title="Défi Enedis: crisis dispatch team brief", author="Hackathon team")
doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(2 * cm, 1.7 * cm, A4[0] - 4 * cm, A4[1] - 3.5 * cm, id="f")], onPage=on_page)])
doc.build(story)
print("written", OUT)
