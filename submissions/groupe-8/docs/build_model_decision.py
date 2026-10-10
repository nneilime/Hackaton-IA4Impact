"""Build docs/Compute_Engine_Model_Decision.pdf: the chosen compute model, its justification and prototype evidence.

Prototype result files (JSON) are read from the directory given as argv[1].
"""
import json, os, sys, statistics as S, tempfile
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle, Image,
                                PageBreak, KeepTogether, Preformatted)

DOCS = os.path.dirname(os.path.abspath(__file__))
PROTO = sys.argv[1]
OUT = os.path.join(DOCS, "Compute_Engine_Model_Decision.pdf")
TMP = tempfile.mkdtemp()
NAVY, TEAL, ORANGE, GREY, LIGHT, PURPLE = "#1F3A5F", "#2A9D8F", "#E76F51", "#6B7280", "#EEF3F8", "#7C6FD0"

summ = json.load(open(os.path.join(PROTO, "proto_summary.json")))
final = json.load(open(os.path.join(PROTO, "proto_final.json")))
online = json.load(open(os.path.join(PROTO, "proto_online.json")))
levers = json.load(open(os.path.join(PROTO, "proto_levers.json")))
hind = levers["hindsight_ls"]
online_gain = [100 * (g - o) / g for _, g, _, o, _ in online]
online_time = [t for *_, t in online]

# ------------------------------------------------------------------ figures
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})


def save(fig, name):
    f = os.path.join(TMP, name); fig.tight_layout(); fig.savefig(f, dpi=200); plt.close(fig); return f


def fig_results():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.4, 2.9), gridspec_kw={"width_ratios": [1.15, 1]})
    rules = [("fifo", "First come\nfirst served"), ("nearest", "Nearest"), ("max_customers", "Most\ncustomers"),
             ("smith_no_travel", "Smith\n(no travel)"), ("smith_travel", "Smith\nw/(τ+p)")]
    vals = [summ[f"0.0|{k}"]["mean_obj"] / 1000 for k, _ in rules]
    cols = [GREY, GREY, GREY, "#9CA3AF", TEAL]
    a1.bar(range(len(vals)), vals, color=cols)
    for i, v in enumerate(vals):
        a1.text(i, v + 2, f"{v:.0f}", ha="center", fontsize=8)
    a1.set_xticks(range(len(vals))); a1.set_xticklabels([l for _, l in rules], fontsize=7.5)
    a1.set_ylabel("customer-hours (thousands)"); a1.set_ylim(0, max(vals) * 1.15)
    a1.set_title("Construction rules alone · 100 crises", fontsize=9)
    names = [("fifo", "vs first come\nfirst served"), ("nearest", "vs nearest"), ("max_customers", "vs most\ncustomers"),
             ("smith_travel", "vs Smith rule\nalone")]
    m = [final[k][0] for k, _ in names]; lo = [final[k][1] for k, _ in names]; hi = [final[k][2] for k, _ in names]
    a2.bar(range(4), m, color=NAVY, yerr=[np.array(m) - lo, np.array(hi) - m], capsize=3, ecolor=GREY)
    for i, v in enumerate(m):
        a2.text(i + 0.12, v + 1, f"−{v:.1f}%", fontsize=8, color=NAVY, fontweight="bold")
    a2.set_xticks(range(4)); a2.set_xticklabels([l for _, l in names], fontsize=7.5)
    a2.set_ylabel("reduction of customer-hours (%)"); a2.set_ylim(0, 45)
    a2.set_title("Full engine (re-plan + 50 ms search) · 20 crises", fontsize=9)
    return save(fig, "results.png")


def fig_online():
    fig, ax = plt.subplots(figsize=(7.4, 2.3))
    xs = range(len(online))
    ax.bar(xs, online_gain, color=TEAL)
    ax.axhline(S.mean(online_gain), color=NAVY, lw=1.2, ls="--", label=f"online mean {S.mean(online_gain):.1f}% (no foresight)")
    ax.axhline(hind[0], color=ORANGE, lw=1.2, ls=":", label=f"hindsight mean {hind[0]:.1f}% (knows the future)")
    ax.legend(frameon=False, fontsize=8, loc="upper left", ncol=2)
    ax.set_xticks(list(xs)); ax.set_xticklabels([c[0][-3:] for c in online], fontsize=7)
    ax.set_xlabel("crisis"); ax.set_ylabel("gain over Smith rule (%)"); ax.set_ylim(0, 31)
    return save(fig, "online.png")


def fig_stagger():
    fs, ss = ["0.25", "0.33", "0.50"], [4, 6, 8, 10, 12]
    grid = np.array([[levers[f"stagger f={f} s={s}"][0] for s in ss] for f in fs])
    fig, ax = plt.subplots(figsize=(5.2, 1.9))
    im = ax.imshow(grid, cmap="RdBu", vmin=-21, vmax=21, aspect="auto")
    for i in range(len(fs)):
        for j in range(len(ss)):
            ax.text(j, i, f"{grid[i, j]:+.1f}%", ha="center", va="center", fontsize=8,
                    color="white" if abs(grid[i, j]) > 12 else "black")
    ax.set_xticks(range(len(ss))); ax.set_xticklabels([f"+{s} h" for s in ss])
    ax.set_yticks(range(len(fs))); ax.set_yticklabels(["1/4 of teams", "1/3 of teams", "1/2 of teams"])
    ax.set_xlabel("delay of the held-back teams' first shift")
    for s in ax.spines.values(): s.set_visible(False)
    return save(fig, "stagger.png")


def fig_decoder():
    fig, ax = plt.subplots(figsize=(7.4, 1.6))
    segs = [(0, 0.3, "#CBD5E1", ""), (0.3, 4, TEAL, "J1  4 h"), (4.3, 0.4, "#CBD5E1", ""), (4.7, 2, TEAL, "J2  2 h"),
            (6.7, 0.3, "#CBD5E1", ""), (7.0, 4, TEAL, "J3  4 h"), (11.0, 11, "#E5E7EB", "rest 11 h  (J4 = 8 h does not fit)"),
            (22.0, 0.5, "#CBD5E1", ""), (22.5, 8, NAVY, "J4  8 h")]
    for x, w, c, lab in segs:
        ax.barh(0, w, left=x, color=c, height=0.5, edgecolor="white")
        if lab:
            ax.text(x + w / 2, 0, lab, ha="center", va="center", color="white" if c in (TEAL, NAVY) else "#374151", fontsize=8)
    ax.axvline(12, color=ORANGE, lw=1.5); ax.text(12.1, 0.38, "end of 12 h window", color=ORANGE, fontsize=7.5)
    ax.set_yticks([]); ax.set_xlim(0, 31); ax.set_xlabel("hours (grey slivers = travel)")
    ax.spines["left"].set_visible(False)
    return save(fig, "decoder.png")


F_RES, F_ONL, F_STG, F_DEC = fig_results(), fig_online(), fig_stagger(), fig_decoder()
F_CYC = os.path.join(DOCS, "compute_cycle.png")

# ------------------------------------------------------------------ styles
FD = r"C:\Windows\Fonts"
for n, f in [("Ar", "arial.ttf"), ("Ar-B", "arialbd.ttf"), ("Ar-I", "ariali.ttf"), ("Ar-BI", "arialbi.ttf"), ("Mono", "consola.ttf")]:
    pdfmetrics.registerFont(TTFont(n, os.path.join(FD, f)))
addMapping("Ar", 0, 0, "Ar"); addMapping("Ar", 1, 0, "Ar-B"); addMapping("Ar", 0, 1, "Ar-I"); addMapping("Ar", 1, 1, "Ar-BI")
st = {
    "body": ParagraphStyle("body", fontName="Ar", fontSize=9.6, leading=13.6, spaceAfter=5),
    "h1": ParagraphStyle("h1", fontName="Ar-B", fontSize=16, leading=20, textColor=colors.HexColor(NAVY), spaceBefore=4, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName="Ar-B", fontSize=11.5, leading=15, textColor=colors.HexColor(TEAL), spaceBefore=9, spaceAfter=4),
    "cell": ParagraphStyle("cell", fontName="Ar", fontSize=8.5, leading=10.9),
    "cellb": ParagraphStyle("cellb", fontName="Ar-B", fontSize=8.5, leading=10.9, textColor=colors.white),
    "bul": ParagraphStyle("bul", fontName="Ar", fontSize=9.6, leading=13.6, leftIndent=12, bulletIndent=2, spaceAfter=2),
    "box": ParagraphStyle("box", fontName="Ar", fontSize=9.4, leading=13.2),
    "cap": ParagraphStyle("cap", fontName="Ar-I", fontSize=8.3, leading=11, textColor=colors.HexColor(GREY), spaceAfter=8),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=8.1, leading=10.5),
}


def P(t, s="body"): return Paragraph(t, st[s] if isinstance(s, str) else s)
def H1(t): return P(t, "h1")
def H2(t): return P(t, "h2")
def B(items): return [Paragraph(i, st["bul"], bulletText="•") for i in items]


def T(rows, widths, head=True):
    data = [[Paragraph(str(c), st["cellb"] if (head and r == 0) else st["cell"]) for c in row] for r, row in enumerate(rows)]
    t = Table(data, colWidths=[w * cm for w in widths], repeatRows=1 if head else 0)
    cmds = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if head: cmds.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)))
    for r in range(1 if head else 0, len(rows)):
        if r % 2 == 0: cmds.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#F8FAFC")))
    t.setStyle(TableStyle(cmds)); return t


def BOX(html, color=TEAL, bg=LIGHT, title=None):
    inner = ([P(f"<b>{title}</b>", "box")] if title else []) + [P(html, "box")]
    t = Table([[inner]], colWidths=[17 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg)), ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(color)),
                           ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return KeepTogether([Spacer(1, 3), t, Spacer(1, 6)])


def CODE(txt):
    t = Table([[Preformatted(txt, st["code"])]], colWidths=[17 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F4F6")), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return KeepTogether([t, Spacer(1, 6)])


def IMG(path, w=17, cap=None):
    from PIL import Image as PI
    iw, ih = PI.open(path).size
    out = [Image(path, width=w * cm, height=w * cm * ih / iw)]
    if cap: out.append(P(cap, "cap"))
    return KeepTogether(out)


g = final
story = []

# ------------------------------------------------------------------ cover + decision
story += [Spacer(1, 1.2 * cm),
          P("DÉFI ENEDIS · COMPUTE ENGINE", ParagraphStyle("k", fontName="Ar-B", fontSize=10, textColor=colors.HexColor(TEAL))),
          Spacer(1, 4),
          P("The dispatch model: decision record", ParagraphStyle("t", fontName="Ar-B", fontSize=24, leading=29, textColor=colors.HexColor(NAVY))),
          P("Which model computes the plan, why this one, and the evidence behind it",
            ParagraphStyle("s", fontName="Ar", fontSize=12.5, leading=16, textColor=colors.HexColor(GREY))),
          Spacer(1, 0.3 * cm),
          P("Version 1 · 10 October 2026 · Status: <b>proposed for team adoption</b>. Everything else (LLM, interface, learning loops) "
            "plugs into the contract defined here.", "cap"),
          BOX("<b>We fix one explicit model and one solver around it: RSLS, the Rolling-horizon Smith + Local-Search dispatcher.</b><br/><br/>"
              "<b>1. Model.</b> Crews are parallel machines. Each incident has a weight w = customers × (1 + β·sensitive), "
              "a release time, a repair time and a travel time that depends on where the crew comes from. We minimise "
              "Σ w·(C − r) (weighted outage hours), plus a stability term and an optional starvation guard. Hard rules: "
              "one job at a time, no interruption, 12 h work / 11 h rest, locks and operator rules.<br/>"
              "<b>2. Representation.</b> A plan is one ordered list of incidents per crew. A deterministic <b>decoder</b> turns "
              "the lists into times and inserts rests. Every plan it outputs is feasible by construction.<br/>"
              "<b>3. Solver.</b> Smith-rule construction (w / (travel + repair)) in milliseconds, then iterated local search "
              "(relocate, swap, reorder, ruin &amp; recreate) within a 200–500 ms budget, then robust selection over "
              "duration scenarios.<br/>"
              "<b>4. Operation.</b> Re-plan at every event from the previous plan. Commit only the next job of each idle crew. "
              "Publish a new plan only if it is clearly better.<br/>"
              "<b>5. Explanations</b> come from the model, not from the LLM: priority index, cost breakdown, counterfactual "
              "Δ, binding constraint, tipping point, uncertainty band.", title="The decision in one box"),
          Spacer(1, 4),
          T([["Evidence (prototype on the real data, official indicator Σ N·T)", "Result"],
             ["Smith rule with travel vs the 4 other construction rules, 100 crises",
              f"best on average; −{summ['0.0|gain_vs_fifo']['mean_gain_pct']:.1f}% vs first-come-first-served, "
              f"−{summ['0.0|gain_vs_nearest']['mean_gain_pct']:.1f}% vs nearest"],
             ["Full engine (re-plan at each decision + 50 ms local search, <b>no knowledge of the future</b>) vs Smith rule alone, 20 crises",
              f"<b>−{S.mean(online_gain):.1f}%</b> (range −{min(online_gain):.1f}% to −{max(online_gain):.1f}%), better on 20/20"],
             ["Full engine vs best simple baseline (most customers first), 20 crises",
              f"<b>−{g['max_customers'][0]:.1f}%</b>, better on {g['max_customers'][3]}/20"],
             ["Full engine vs first come first served / nearest, 20 crises",
              f"<b>−{g['fifo'][0]:.1f}%</b> / <b>−{g['nearest'][0]:.1f}%</b>, better on 20/20"],
             ["Share of the hindsight headroom captured online",
              f"{S.mean(online_gain):.1f}% of the {hind[0]:.1f}% achievable with perfect foresight (≈ {100*S.mean(online_gain)/hind[0]:.0f}%)"]],
            [10.5, 6.5]),
          PageBreak()]

# ------------------------------------------------------------------ 1 problem
story += [H1("1. The problem as a formal model"),
          P("This is the contract every component relies on. Every symbol below is a parameter or a data field. None is hard-coded."),
          H2("1.1 Sets and data"),
          T([["Symbol", "Meaning", "Source"],
             ["I, K", "incidents known so far; crews (teams)", "event stream; agents.csv"],
             ["r<sub>i</sub>", "time incident i is reported (release)", "dateHeureIncident"],
             ["p<sub>i</sub>", "estimated repair time (2, 4 or 8 h); the truth is revealed when the repair ends", "dureeDepannage"],
             ["n<sub>i</sub>, s<sub>i</sub>", "customers cut off; sensitive flag (0/1)", "poste.csv"],
             ["w<sub>i</sub> = n<sub>i</sub>(1 + β s<sub>i</sub>)", "weight. Official mode β = 0 (the jury's N×T); operational mode β &gt; 0", "config"],
             ["τ(a, b)", "travel time = straight-line distance × 1.3 / speed (replaceable by a road matrix)", "config / modifiers"],
             ["W = 12 h, R = 11 h", "work window length, rest length", "config"],
             ["a<sub>k</sub>, e<sub>k</sub>, o<sub>k</sub>", "time crew k becomes free, end of its current window, its position", "state"]],
            [3.4, 9.6, 4]),
          H2("1.2 Decision"),
          P("For each crew k, an ordered list π<sub>k</sub> of incidents. Start and completion times C<sub>i</sub> are <b>not</b> "
            "decision variables: the decoder (section 2) computes them from the lists. That keeps the search space purely combinatorial "
            "and guarantees feasibility."),
          H2("1.3 Objective"),
          CODE("minimise  J = Σ_i f_i(C_i)  +  λ_stab · (number of crews whose next job changes vs the published plan)\n\n"
               "          f_i(C_i) = w_i · (C_i − r_i)                         weighted outage hours\n"
               "                   + γ · n_i · max(0, C_i − r_i − D)            starvation guard (optional)"),
          T([["Mode", "Setting", "Use"],
             ["Official", "β = 0, γ = 0, λ<sub>stab</sub> = 0", "exactly Σ N<sub>i</sub>·T<sub>i</sub> from the README; used for every benchmark"],
             ["Operational", "β ≈ 3, γ &gt; 0 (D ≈ 24 h), λ<sub>stab</sub> &gt; 0", "what the manager runs; every weight visible and adjustable"]],
            [2.6, 6.2, 8.2]),
          BOX("Each f<sub>i</sub> is <b>non-decreasing</b> in its own completion time, and J is a <b>sum over incidents</b>. That gives three "
              "properties we rely on. (1) Finishing a job earlier never hurts, so the decoder can schedule as early as possible. "
              "(2) A move in local search changes only the costs of the one or two crews it touches, so evaluation is cheap. "
              "(3) The score splits per incident and per term, which is what the explanations are made of. That is why the "
              "fairness guard is a per-incident soft deadline and not a non-separable 'max wait' term.",
              title="Why this exact shape"),
          H2("1.4 Constraints and where each one is enforced"),
          T([["#", "Rule", "Enforced by"],
             ["C1", "each incident handled by q<sub>i</sub> crews (today q = 1, parameter)", "representation (an incident is in exactly one list)"],
             ["C2", "one job at a time, jobs in sequence with travel in between", "decoder"],
             ["C3", "no anticipation: a crew cannot leave for an incident that is not reported yet", "state (only known incidents are planned)"],
             ["C4", "no interruption of a repair", "decoder"],
             ["C5", "travel + repair must fit entirely in the current 12 h window; otherwise 11 h rest first", "decoder"],
             ["C6", "rest on site (or at base, parameter)", "decoder"],
             ["C7", "jobs in progress are locked; operator force / forbid rules", "move filter (locked items never move)"],
             ["C8", "crew unavailability windows (stress tests, operator)", "decoder (window removed)"],
             ["C9", "optional hard deadline for sensitive customers", "decoder check → infeasible move rejected"]],
            [1, 9.5, 6.5]),
          H2("1.5 Problem class"),
          P("In scheduling notation: parallel machines with release dates, sequence-dependent set-up times (travel) and availability windows, "
            "minimising weighted flow time. Even one machine with release dates is NP-hard, and decisions are taken <b>online</b> as incidents arrive. "
            "So we need a fast heuristic with a sound basis, an exact solver for reference only, and re-planning at every event. In the "
            "routing literature this is the <i>multi-crew minimum weighted latency problem</i> (Dey &amp; Ornik)."),
          Spacer(1, 8)]

# ------------------------------------------------------------------ 2 decoder
story += [H1("2. Representation and decoder"),
          P("The decoder is the heart of the model. Given one crew's ordered list, it returns the exact timetable and its cost, applying "
            "the work rules. Every solver, every baseline and every explanation goes through it, so the rules live in exactly one place."),
          CODE("decode(crew k, list π):\n"
               "  t ← a_k ; end ← e_k ; here ← o_k ; cost ← 0\n"
               "  for i in π:\n"
               "      d ← τ(here, i)\n"
               "      t_go ← max(t, r_i, accessible_from_i)            # never before the incident exists or is reachable\n"
               "      if t_go + d + p_i > end:                         # C5: does not fit in this window\n"
               "          t ← t + R ; end ← t + W ; t_go ← max(t, r_i)   # rest 11 h starting now, new 12 h window\n"
               "          if t_go + d + p_i > end: return INFEASIBLE    # job longer than a whole window\n"
               "      C_i ← t_go + d + p_i ; cost += f_i(C_i)\n"
               "      t ← C_i ; here ← i\n"
               "  return cost, timetable"),
          IMG(F_DEC, cap="Figure 1. Decoder rule on one crew: work while the next job fits in the window, otherwise rest 11 h first. "
                          "Here J4 (8 h) cannot start after J3, so the rest is inserted before it."),
          H2("Properties"),
          *B(["<b>Feasible by construction.</b> No solver can produce a plan that breaks C2, C4, C5, C6 or C8, because the decoder "
              "is the only way to get times. A separate validator re-checks every published plan anyway.",
              "<b>Optimal timing for a given order.</b> Because each f<sub>i</sub> is non-decreasing, starting every job as early as the rules "
              "allow is optimal for a fixed order when the crew is never idle. In real time this is the normal case: we only plan incidents "
              "that are already reported. The search then only has to find good <b>orders and assignments</b>.",
              "<b>Exception: idle time.</b> If a crew sits idle for a long time (no work in its area), resting <i>during</i> that idle "
              "period can beat working until the window ends. That is a decision about <b>when crews rest or are mobilised</b>, not about "
              "orders. We handle it as a separate lever (section 4.4), not inside the decoder.",
              "<b>Fast.</b> One call costs O(length of the list), about 3 to 6 incidents per crew in our crises."]),
          PageBreak()]

# ------------------------------------------------------------------ 3 solver
story += [H1("3. The solver"),
          IMG(F_CYC, w=9.5, cap="Figure 2. One compute cycle, run at every event. Budgets are per cycle."),
          KeepTogether([H2("3.1 Construction: Smith list scheduling (milliseconds)"), CODE("while unassigned known incidents remain:\n"
               "    k  ← crew that becomes free first\n"
               "    i* ← argmax over incidents that fit k's window of   w_i / (τ(k, i) + p_i)\n"
               "    append i* to π_k ; update k with decode()\n"
               "    (if nothing fits: k rests 11 h ; if nothing is known: k waits for the next event)")]),
          P("<b>Why this rule.</b> w/(τ + p) is <i>customers restored per hour of crew time</i>. With one crew and no travel it is exactly "
            "Smith's rule, which is optimal (Smith, 1956). On parallel machines with arrivals over time, rules of this family have proven "
            "worst-case guarantees (Megow &amp; Schulz 2004; Correa &amp; Wagner 2009). For post-disaster repairs, Tan et al. show an "
            "interpretable importance-based dispatch rule with a (2 − 1/m) approximation guarantee. These guarantees hold for "
            "simpler models (no travel, no work windows): we say our rule is <i>grounded in</i> them, not <i>guaranteed by</i> them. "
            "<b>Measured:</b> it is the best of the five construction rules tested on the 100 crises (Figure 4, left)."),
          H2("3.2 Improvement: iterated local search (200–500 ms)"),
          T([["Component", "Choice", "Why"],
             ["Neighbourhoods", "relocate (move an incident to another crew / position), swap (exchange two incidents between crews), reorder (within a crew)",
              "the moves that work for minimum-latency problems (transfers and swaps, Dey &amp; Ornik); each touches ≤ 2 crews"],
             ["Perturbation", "ruin &amp; recreate: remove 10–20% of incidents (random, a geographic cluster, or the costliest), reinsert by regret",
              "escapes local optima; the standard approach in modern routing heuristics"],
             ["Acceptance", "improve, or late-acceptance (accept if better than the cost L iterations ago)", "one parameter, robust, no temperature tuning"],
             ["Evaluation", "decoder on the 1–2 changed crews only", "thousands of moves per 100 ms in Python"],
             ["Stop", "time budget; always return the best feasible plan found", "anytime: the construction is already a valid answer"],
             ["Determinism", "seeded random generator", "same input, same plan; needed for demos and tests"]],
            [2.6, 8, 6.4]),
          P("<b>Measured:</b> a minimal version (relocate moves only, first improvement, 50 ms per decision) already cuts the Smith-rule "
            f"plan by <b>{S.mean(online_gain):.1f}%</b> on average, with <b>no knowledge of future incidents</b> (Figure 5). Re-planning "
            "<i>without</i> the search gives almost nothing. The gain comes from the improvement step, so it is not optional."),
          H2("3.3 Robust selection under duration uncertainty"),
          P("Repair times are estimates. The search keeps an elite set of about 5 good plans. Each is re-decoded on S ≈ 30 sampled "
            "duration scenarios (lognormal around the estimate), and we keep the best expected score. This costs only milliseconds, "
            "because a full decode costs microseconds per crew. The same samples give each recommendation a <b>P10–P90 restoration "
            "band</b> for the explanation."),
          H2("3.4 Timing budget per cycle (target)"),
          T([["Step", "Budget", "Notes"],
             ["State update + warm start", "&lt; 10 ms", "insert new incidents at their cheapest position"],
             ["Local search", "200–500 ms", "configurable (solver.budget_ms)"],
             ["Robust selection", "&lt; 20 ms", "5 plans × 30 scenarios"],
             ["Explanation facts", "≈ 50 ms per new recommendation", "counterfactual = short warm-started re-search"],
             ["Prototype measurement", f"{S.mean(online_time):.1f} s per whole crisis on average", "about 160 decisions × 50 ms, pure Python"]],
            [4.2, 4.3, 8.5]),
          PageBreak()]

# ------------------------------------------------------------------ 4 real time
story += [H1("4. Real-time operation"),
          H2("4.1 Rolling horizon"),
          P("At every event, the engine plans <b>all known pending incidents</b>. At our scale (≤ 250 incidents, 63 crews) no truncation is "
            "needed. It starts from the previous plan (warm start), so consecutive plans stay close and the cycle is fast."),
          H2("4.2 Commit only the next job"),
          P("Only the <b>next job of each idle crew</b> becomes a recommendation the manager validates. The following 2 jobs are shown "
            "as a provisional preview. This is the cadence of the damage-assessment allocation system used in production during live "
            "storms at Eversource (k jobs per crew, recomputed on a cadence and on operator request)."),
          H2("4.3 Stability: two safeguards"),
          *B(["<b>λ<sub>stab</sub></b> in the objective: changing a crew's next job costs a fixed number of customer-hours, so the search "
              "only reshuffles when the gain pays for it.",
              "<b>Publication threshold</b>: a new plan replaces the published one only if it is better by at least a set margin "
              "(for example 1%), or if an event forces it (crew unavailable, operator rule). Jobs in progress are never moved.",
              "Each published plan is versioned, so the interface can show what changed and why."]),
          H2("4.4 Lever outside the inner loop: when crews work and rest"),
          P("Crises last about 36 h in our prototype, so the 11 h rest is the largest single delay. The work rule does not say when the "
            "first window starts. We tested holding part of the crews back:"),
          IMG(F_STG, w=12, cap="Figure 3. Mean change in customer-hours vs everyone starting at hour 0, 100 crises. A small, short hold-back helps; "
                               "a large or long one hurts badly. Mobilisation must be decided per crisis, not set by a fixed rule."),
          P("So the model has a per-crew <b>mobilisation time</b> as an input. It is chosen by an outer loop that simulates a few patterns "
            "with the same engine and proposes the best one to the manager. The inner solver stays unchanged. The same outer loop "
            "serves pre-positioning and the 'one more crew at site X' lever analysis."),
          PageBreak()]

# ------------------------------------------------------------------ 5 explain
story += [H1("5. Explainability contract"),
          P("Explanations are computed from the model and handed to the LLM as facts. The LLM writes the text and may not state a number "
            "that is not in the facts. This follows the solver-grounded approach recommended in the literature: explanations "
            "derived from the optimisation model, not a post-hoc layer (Khan 2026; Čyras et al. 2019). The LLM's role follows "
            "OptiGuide (Microsoft) and OptiChat: it translates and calls tools, it never computes."),
          T([["Fact", "How the engine computes it", "What the manager reads"],
             ["Priority index", "w / (τ + p) for the chosen pair, and its rank", "\"brings back 31 customers per hour of work, 2nd highest\""],
             ["Cost breakdown", "f<sub>i</sub> split into waiting, travel, repair (customer-hours)", "\"most of the cost is waiting, not travel\""],
             ["Contrastive Δ", "force the best alternative crew (or incident), short warm-started re-search, compare J", "\"team 4 instead would cost +410 customer-hours\""],
             ["Binding constraint", "decoder trace (rest inserted, window end, lock, operator rule)", "\"team 9 cannot: its window ends in 1 h 40\""],
             ["Tipping point", "bisection on p<sub>i</sub> (or τ) until the decision flips", "\"if the repair takes more than 5 h, team 9 becomes better\""],
             ["Uncertainty band", "P10–P90 of C<sub>i</sub> over the duration scenarios", "\"power back between 14:10 and 16:40\""],
             ["Override cost", "re-plan with the operator's choice locked, compare J", "\"your choice costs +2% (+320 customer-hours)\""]],
            [2.7, 7.3, 7]),
          CODE('{"team": "SITE_07_E2", "incident": "INC_004211", "rank": 1,\n'
               ' "factors": {"customers": 120, "sensitive": false, "travel_min": 25, "repair_h": 4, "window_left_h": 6.1,\n'
               '             "priority_index": 27.4},\n'
               ' "alternative_team": {"team": "SITE_13_E1", "delta": 410}, "binding": null,\n'
               ' "tipping_point": {"param": "repair_h", "value": 5.2, "flips_to": "SITE_15_E3"},\n'
               ' "restoration_p10_p90": ["14:10", "16:40"]}'),
          P("<i>Example of what the LLM writes from this (illustrative values):</i> « Équipe 2 de Muret → poste de Seysses : 120 clients, "
            "25 min de route, 4 h de dépannage. Envoyer l'équipe de Saint-Gaudens coûterait 410 clients·h de plus. Si le dépannage dépasse "
            "5 h 12, l'équipe 3 de Boussens devient préférable. Rétablissement prévu entre 14 h 10 et 16 h 40. »"),
          H1("6. How the model improves without changing the solver"),
          P("Every improvement discussed (manager feedback, expert rules, calibration, learned preferences) acts on <b>data the model "
            "reads</b>, never on solver code. The solver stays one tested piece."),
          T([["What changes", "Where it enters the model", "Who changes it"],
             ["Operator rules (road cut, crew unavailable, force / forbid, priority)", "modifiers → decoder inputs or move filters", "manager, via LLM + validator"],
             ["Permanent rules (after repeated refusals)", "constraint registry (versioned)", "experts, after a replay test"],
             ["Repair / travel estimates", "p<sub>i</sub>, τ factors", "calibration from observed outcomes"],
             ["β, γ, D, λ<sub>stab</sub>, publication threshold", "objective weights", "manager / learned from chosen vs rejected plans"],
             ["Index variant w / (p + θτ)", "construction rule parameter θ", "tuned by replaying the 100 crises"],
             ["Mobilisation times, pre-positioning", "crew windows and positions (inputs)", "outer simulation loop, manager approval"],
             ["Several crews per incident, skills", "q<sub>i</sub> &gt; 1 in the decoder (start when all arrive); eligibility filter", "future data"]],
            [5.6, 6.2, 5.2]),
          PageBreak()]

# ------------------------------------------------------------------ 7 evidence
story += [H1("7. Evidence from the prototype"),
          P("<b>Setup.</b> Real data (63 crews, 100 crises), straight-line travel × 1.3 at 50 km/h, deterministic durations "
            "(estimate = actual), all crews start at hour 0, official objective Σ N·T. The engine sees an incident only once it is reported. "
            "Construction rules were run on all 100 crises. The full engine (re-plan at each decision + relocate local search, 50 ms) "
            "was run on 20 crises (every 5th one) because Python run time is longer."),
          IMG(F_RES, cap="Figure 4. Left: construction rules alone (mean customer-hours per crisis, lower is better). "
                         "Right: full engine vs each strategy on the same 20 crises (bars = mean, whiskers = min–max)."),
          IMG(F_ONL, cap="Figure 5. Gain of the full engine over the Smith rule alone, per crisis. Online (no foresight) it captures most of the gain "
                         "that local search reaches when it knows all incidents in advance."),
          T([["Comparison (same crises, paired)", "Mean", "Range", "Better on"],
             ["Full engine vs first come first served", f"−{g['fifo'][0]:.1f}%", f"−{g['fifo'][1]:.1f}% … −{g['fifo'][2]:.1f}%", f"{g['fifo'][3]}/20"],
             ["Full engine vs nearest crew", f"−{g['nearest'][0]:.1f}%", f"−{g['nearest'][1]:.1f}% … −{g['nearest'][2]:.1f}%", f"{g['nearest'][3]}/20"],
             ["Full engine vs most customers first", f"−{g['max_customers'][0]:.1f}%", f"−{g['max_customers'][1]:.1f}% … −{g['max_customers'][2]:.1f}%", f"{g['max_customers'][3]}/20"],
             ["Full engine vs Smith rule alone", f"−{g['smith_travel'][0]:.1f}%", f"−{g['smith_travel'][1]:.1f}% … −{g['smith_travel'][2]:.1f}%", f"{g['smith_travel'][3]}/20"],
             ["Smith rule vs nearest, 100 crises", f"−{summ['0.0|gain_vs_nearest']['mean_gain_pct']:.1f}%",
              f"{-summ['0.0|gain_vs_nearest']['max_gain_pct']:+.1f}% … {-summ['0.0|gain_vs_nearest']['min_gain_pct']:+.1f}%",
              f"{summ['0.0|gain_vs_nearest']['wins']}/100"]],
            [7.6, 2.4, 4.4, 2.6]),
          BOX("<b>(1)</b> The construction rule alone is only a few percent better than simple rules, and it loses to 'nearest' on about one crisis in five. "
              "<b>(2)</b> The local search is what makes the difference: about −15% on top of the rule, every time. "
              "<b>(3)</b> Re-planning without search adds almost nothing. "
              "<b>(4)</b> Rest timing is a big lever, but a risky one. "
              "<b>Caveats:</b> prototype only (relocate moves, 50 ms, no stability penalty, no duration noise, 20-crisis sample for the full engine). "
              "The stability penalty will give back part of the gain in exchange for calmer plans. Re-measure on all 100 crises once the real engine exists.",
              color=ORANGE, bg="#FDF2EE", title="What we learn"),
          PageBreak()]

# ------------------------------------------------------------------ 8 alternatives
story += [H1("8. Alternatives considered"),
          T([["Option", "Verdict", "Reason"],
             ["Exact MILP / CP-SAT as the real-time engine", "reference only",
              "travel depends on the previous job, which needs routing (circuit) constraints; seconds to minutes with no guarantee "
              "at 250 × 63; optimal on <i>estimated</i> data is false precision. Kept offline to measure the heuristic's gap."],
             ["Priority rule alone (no search)", "rejected as final engine", "measured: leaves about 15% on the table"],
             ["Genetic algorithm", "rejected", "slower and less controllable than local search at this size, no gain in explainability"],
             ["Reinforcement learning (AlphaZero-style dispatch)", "rejected", "needs training, no decision data, opaque, published tests on 8- and 123-node test grids"],
             ["LLM as planner over a validated action catalogue (LARA)", "rejected", "conflicts with 'the engine decides, the human validates'; "
              "small test grids. We keep its validated-catalogue idea for operator rules."],
             ["Pure graph algorithms (matching, flows)", "used as parts", "exact for one-step assignment or zone balancing, but blind to ordering over time "
              "and work windows. Candidates: matching for simultaneous decisions, flows for zone balancing (later)."],
             ["Off-the-shelf solvers (PyVRP, Timefold)", "not adopted", "PyVRP optimises route cost, not weighted latency. Timefold Python needs a JVM, "
              "is slower than its Java version, and its explanation features are enterprise-side. We borrow its per-constraint score analysis."],
             ["OR-Tools Routing", "offline reference", "the model maps directly (soft cumulative upper bound = Σ w·C, break intervals = rests); used for the quality gap"]],
            [4.4, 2.8, 9.8]),
          H1("9. Acceptance criteria for the real engine"),
          T([["Criterion", "Target"],
             ["Feasibility", "0 infeasible plans over all 100 crises and every stress test (validator)"],
             ["Quality", "≥ 10% fewer customer-hours than the best simple baseline, mean over the 100 crises, official mode"],
             ["Gap to reference", "measured vs OR-Tools offline (long time limit) on 10 small crises, reported in the README"],
             ["Latency", "p95 of a full compute cycle &lt; 1 s on a laptop at 250 incidents"],
             ["Stability", "mean number of next-job changes per published plan reported; ≤ 2 crews on average"],
             ["Determinism", "same input + same seed → identical plan"],
             ["Explanations", "every recommendation has the facts of section 5; Δ = 0 when forcing the recommended choice"]],
            [4, 13]),
          H1("10. Assumptions to confirm with the organisers"),
          *B(["A repair may not cross the end of a 12 h window (we assume no), and travel counts as work time (we assume yes).",
              "The rest starts as soon as the next job cannot fit (we assume yes); all crews start fresh at hour 0 unless mobilised later.",
              "After a repair, the crew stays on site (we assume yes); one crew per incident (parameter q).",
              "The official indicator Σ N·T is to be minimised (README says 'maximiser', read as a typo).",
              "Repeated incidents on the same substation are separate incidents; the 5 incidents on unknown substations are dropped."]),
          H1("References"),
          *B(["W. E. Smith (1956), Various optimizers for single-stage production, Naval Research Logistics Quarterly.",
              "N. Megow, A. S. Schulz (2004), On-line scheduling to minimize average completion time revisited, Operations Research Letters 32. "
              "J. Correa, M. Wagner (2009), LP-based online scheduling: from single to parallel machines.",
              "Y. Tan, F. Qiu, A. K. Das, D. S. Kirschen, P. Arabshahi, J. Wang, Scheduling Post-Disaster Repairs in Electricity Distribution Networks, arXiv:1702.08382.",
              "A. Dey, M. Ornik (2022), Post-Disaster Repair Crew Assignment Optimization Using Minimum Latency, arXiv:2206.00597 (code: github.com/leadcatlab/MWLP-Storm-Repair).",
              "Optimized Rolling Allocation of Outages for Damage Assessment (Eversource Energy), arXiv:2512.20719.",
              "B. Li, K. Mellou, B. Zhang, J. Pathuri, I. Menache (2023), Large Language Models for Supply Chain Optimization (OptiGuide), arXiv:2307.03875. "
              "H. Chen et al. (2025), OptiChat, INFORMS Journal on Data Science.",
              "K. Čyras et al. (2019), Argumentation for Explainable Scheduling, AAAI. Khan (2026), solver-grounded explanations for scheduling, arXiv:2603.00469 (preprint).",
              "Walsh et al., Agent Based Model to Estimate Time to Restoration of Storm-Induced Power Outages, Infrastructures 3(3).",
              "Note: several references were read as abstracts only. Read the full texts before quoting figures from them in the pitch."])]


def on_page(c, doc):
    c.saveState()
    if doc.page > 1:
        c.setFont("Ar", 7.5); c.setFillColor(colors.HexColor(GREY))
        c.drawString(2 * cm, A4[1] - 1.2 * cm, "Défi Enedis · Compute engine: model decision record · v1")
        c.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"{doc.page}")
        c.setStrokeColor(colors.HexColor("#CBD5E1")); c.setLineWidth(0.4)
        c.line(2 * cm, A4[1] - 1.35 * cm, A4[0] - 2 * cm, A4[1] - 1.35 * cm)
    else:
        c.setFillColor(colors.HexColor(NAVY)); c.rect(0, A4[1] - 0.9 * cm, A4[0], 0.9 * cm, fill=1, stroke=0)
    c.restoreState()


doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.7 * cm,
                      title="Défi Enedis: compute engine model decision", author="Hackathon team")
doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(2 * cm, 1.7 * cm, A4[0] - 4 * cm, A4[1] - 3.5 * cm, id="f")], onPage=on_page)])
doc.build(story)
print("written", OUT)
