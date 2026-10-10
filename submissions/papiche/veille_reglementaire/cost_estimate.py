# SPDX-License-Identifier: AGPL-3.0-or-later
"""Estimation du coût : service d'IA local (RTX 3090) comparé aux API payantes au token et aux forfaits.

Les volumes de tokens viennent du benchmark (tokens réellement consommés par passage, essais et contrôles inclus).
Les tarifs viennent de config/pricing.json (relevés sur les pages officielles, avec source et date).
Les hypothèses locales (prix de la carte, électricité…) sont dans config/local_cost_assumptions.json : à ajuster.
Tout est exprimé en dollars US, comme les tarifs publics.
"""
from __future__ import annotations

import json

from . import config

SCENARIOS = [
    ("Démonstration (corpus actuel)", None),          # nombre de passages lu dans le benchmark
    ("Mise à jour quotidienne pendant 1 an (hypothèse : 500 passages par jour)", 500 * 365),
    ("Chargement initial FR + CA + US", 400_000),
    ("Monde (≈ 10 pays)", 1_000_000),
]


def load_json(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def local_cost_per_passage(seconds_per_passage: float, assumptions: dict) -> dict:
    """Coût d'un passage sur la carte locale : électricité (coût marginal) et amortissement de la carte."""
    kilowatt_hours = assumptions["gpu_power_watts"] / 1000 * seconds_per_passage / 3600
    electricity = kilowatt_hours * assumptions["electricity_usd_per_kwh"]
    busy_hours_over_lifetime = assumptions["lifetime_years"] * 8760 * assumptions["utilization"]
    hardware = assumptions["gpu_purchase_usd"] / busy_hours_over_lifetime * seconds_per_passage / 3600
    return {"electricity": electricity, "hardware": hardware, "kwh": kilowatt_hours}


def api_cost_per_passage(model: dict, prompt_tokens: float, generated_tokens: float, batch_discount: float = 1.0) -> float:
    cost = prompt_tokens * model["input"] / 1e6 + generated_tokens * model["output"] / 1e6
    return cost * batch_discount


def build_report(bench_report: dict) -> dict:
    pricing = load_json(config.CONFIG / "pricing.json")
    assumptions = load_json(config.CONFIG / "local_cost_assumptions.json")
    chosen = bench_report["recommendation"]["model"]
    measured = bench_report["results"][chosen]
    prompt_tokens, generated_tokens = measured["prompt_tokens_per_passage"], measured["gen_tokens_per_passage"]
    demo_passages = bench_report["storage"]["passages_now"]
    scenarios = [(name, demo_passages if n is None else n) for name, n in SCENARIOS]

    local = local_cost_per_passage(measured["s_per_passage_mean"], assumptions)
    options = [
        {"kind": "local", "label": f"Service local : RTX 3090, {chosen} (électricité seule)", "per_passage": local["electricity"]},
        {"kind": "local", "label": f"Service local : RTX 3090, {chosen} (électricité + amortissement)",
         "per_passage": local["electricity"] + local["hardware"]},
    ]
    for model in pricing["api_models"]:
        full_name = model["model"] if model["model"].startswith(model["vendor"]) else f"{model['vendor']} {model['model']}"
        options.append({"kind": "api", "label": full_name, "tier": model["tier"], "note": model.get("note"),
                        "source": model["source"], "price_in": model["input"], "price_out": model["output"],
                        "per_passage": api_cost_per_passage(model, prompt_tokens, generated_tokens)})
        options.append({"kind": "api_batch", "label": f"{full_name} (Batch, −50 %)", "tier": model["tier"],
                        "source": model["source"], "per_passage": api_cost_per_passage(model, prompt_tokens, generated_tokens, pricing["batch_discount"])})
    for option in options:
        option["totals"] = {name: round(option["per_passage"] * count, 2) for name, count in scenarios}
        option["per_1000_passages"] = round(option["per_passage"] * 1000, 4)

    return {
        "checked_on": pricing["checked_on"], "model_measured": chosen,
        "tokens_per_passage": {"prompt": prompt_tokens, "generated": generated_tokens},
        "seconds_per_passage": measured["s_per_passage_mean"], "scenarios": [{"name": n, "passages": c} for n, c in scenarios],
        "local_assumptions": assumptions, "local_per_passage": local, "options": options,
        "subscriptions": pricing["subscriptions"], "subscription_facts": pricing["subscription_facts"],
        "caveats": [
            "Les tokens par passage sont ceux du modèle local mesuré (tokenizer différent chez chaque fournisseur : écart possible de quelques dizaines de %).",
            "Seuls les modèles locaux ont été mesurés en qualité : le coût d'une API ne dit rien de sa qualité sur cette tâche.",
            "Les coûts locaux supposent le service déjà en place ; hors maintenance, réseau et temps d'exploitation.",
            "Le prix d'achat de la carte, l'électricité et le taux d'utilisation sont des hypothèses (config/local_cost_assumptions.json).",
        ],
    }


def format_money(value: float) -> str:
    """Format français : 1 030,76 $ (espace insécable entre milliers)."""
    if value < 0.01:
        return "< 0,01 $"
    return f"{value:,.2f}".replace(",", "\u202f").replace(".", ",") + " $"


def format_count(number: int) -> str:
    return f"{number:,}".replace(",", "\u202f")


def render_markdown(report: dict) -> str:
    names = [s["name"] for s in report["scenarios"]]
    lines = [
        "# Coût : service d'IA local, API au token, forfaits", "",
        f"Tarifs relevés le {report['checked_on']} (sources dans `config/pricing.json`). Montants en dollars US, hors taxes.",
        f"Volume mesuré sur `{report['model_measured']}` : **{report['tokens_per_passage']['prompt']} tokens lus + "
        f"{report['tokens_per_passage']['generated']} tokens écrits par passage** (essais et contrôles inclus), "
        f"{report['seconds_per_passage']} s par passage sur la RTX 3090.", "",
        "## Coût total par scénario", "",
        "| Option | " + " | ".join(f"{s['name']} ({format_count(s['passages'])} passages)" for s in report["scenarios"]) + " |",
        "|---|" + "---|" * len(names)]
    for option in report["options"]:
        lines.append(f"| {option['label']} | " + " | ".join(format_money(option["totals"][n]) for n in names) + " |")
    a = report["local_assumptions"]
    lines += ["", "## Hypothèses du coût local", "",
              f"Carte {a['gpu_purchase_usd']} $ amortie sur {a['lifetime_years']} ans à {int(a['utilization'] * 100)} % d'utilisation ; "
              f"{a['gpu_power_watts']} W ; électricité {a['electricity_usd_per_kwh']} $/kWh. "
              f"Énergie par passage : {report['local_per_passage']['kwh'] * 1000:.2f} Wh.", "",
              "## Forfaits (abonnements par personne)", "", "| Fournisseur | Forfait | Prix mensuel | Remarque |", "|---|---|---|---|"]
    lines += [f"| {s['vendor']} | {s['plan']} | {s['usd_per_month']} $ | {s.get('note', '')} |" for s in report["subscriptions"]]
    lines += [""] + [f"- {fact}" for fact in report["subscription_facts"]]
    lines += ["", "## Réserves", ""] + [f"- {c}" for c in report["caveats"]]
    return "\n".join(lines) + "\n"


def run() -> dict:
    bench_path = config.PROCESSED / "bench" / "report.json"
    if not bench_path.exists():
        raise SystemExit("Lancer d'abord `./veille bench` : le coût part des tokens mesurés.")
    report = build_report(load_json(bench_path))
    folder = config.PROCESSED / "cost"
    folder.mkdir(exist_ok=True)
    (folder / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    (config.ROOT / "docs").mkdir(exist_ok=True)
    (config.ROOT / "docs" / "COUT.md").write_text(render_markdown(report), encoding="utf-8")
    return report
