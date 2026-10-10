# Pipeline: optimisation engine → LLM → front-end

```
 FRONT (map + cards)          API (FastAPI)                 ENGINE (RSLS)                    LLM (OpenRouter)
 ───────────────────          ─────────────                 ─────────────                    ────────────────
 clock / "next event"  ──►  POST /advance  ──► session: new incidents, repairs done
                                               re-plan: Smith rule + local search (≤ 3 s)
                                               ──► plan (ordered jobs per team + timetable + score)
 cards                 ◄──  GET /recommendations ◄── facts per recommendation ──► 2 business sentences
 map layers            ◄──  GET /map             ◄── GeoJSON (teams, incidents, routes, heat)   (template if no key /
                                                                                                 check fails)
 manager clicks ACCEPT ──►  POST /accept   ──► team dispatched, decision logged, quick re-plan (0.5 s)
 manager clicks REFUSE ──►  POST /reject   ──► reason ──────────────────────────────────────► JSON rule proposal
                                               validator checks the rule, engine prices it ◄──
 "Compris : … Appliquer ? (+X clients-heures)" ◄── proposal
 manager confirms      ──►  POST /confirm  ──► rule applied, re-plan, refusal logged (knowledge base)
 48 h check panel      ◄──  GET /service     ◄── projected % at H+48 (+ reinforcement if below 90 %)
 (monthly) expert view ◄──  GET /learning/candidates ◄── repeated refusals → candidate rule → replay test
```

## What crosses each boundary

**Engine → API (per re-plan).** The engine is the only source of numbers.
- `Plan`: for each team, its ordered incident ids; for each incident, `(depart_h, arrive_h, restored_h)`; and the score.
- **Score** = customers × hours without power, summed over incidents (the official N×T indicator). It is in
  *customer-hours*, a business unit: 100 customer-hours = 100 customers without power for 1 h, or 50 for 2 h.
- `ExplanationFacts` per recommendation: customers, sensitive, travel min, repair h, restoration time, rank,
  best alternative team and its extra cost (customer-hours), binding constraint (end of shift, operator rule…).

**API → LLM (only for wording; never for deciding).** One small JSON object per recommendation:
```json
{"customers": 138, "sensitive": false, "travel_min": 19, "repair_h": 2.0, "restored_clock": "15:18",
 "team": "SITE_01_E3", "team_site": "Foix", "incident_commune": "Saint-Jean-de-Verges", "rank": 1,
 "alternative_team": "SITE_02_E4", "extra_customer_hours": 77, "equivalent_delay": "33 min"}
```
The engine translates the score into business terms **before** the LLM sees anything:
`equivalent_delay = extra_customer_hours / customers`. That is "these 138 customers would wait 33 min longer".
The card has a deterministic **headline**. On expansion, the LLM writes the **details** in **exactly two French sentences**:
- why this choice (customers restored and when);
- what the alternative would cost.

The text is accepted only if it has ≤ 2 sentences and **every number in it is in the JSON**. Otherwise the template is used. No personal data is sent: only ids, communes and counts.

**LLM → API (refusals).** The manager's reason (`"route inondée jusqu'à 18h"`) plus the context (team, incident, commune, clock) goes to the LLM, which answers with JSON: either `{"modifiers": [...], "restatement": "..."}` or `{"question": "..."}`. The **validator** checks every rule (known type, existing ids and zones, values in range; safety rules can never be relaxed). Then the **engine** prices it before the manager confirms. Without a key, a rule parser handles the standard reasons.

**API → front-end.**
- Snapshot: clock, indicators, teams, incidents, rules.
- Recommendation cards: text + facts + past-refusal hint.
- Map layers: GeoJSON.
- The 48 h check, plus the reinforcement request.

See [API.md](API.md) for every endpoint and payload.

## Timing (target, laptop)
| Step | Time |
|---|---|
| Re-plan on a new event | ≤ 3 s (config `solver.budget_ms`) |
| Re-plan after a manager action | ≤ 0.5 s (`solver.interactive_budget_ms`) |
| Explanation facts | ~50 ms per card |
| LLM sentence (free OpenRouter model) | 1–5 s per card; falls back to the template on timeout (20 s) or rate limit |
| Rule pricing after a refusal | ≤ 3 s |

## LLM configuration (`config/default.yaml` → `llm`)
- `model: nvidia/nemotron-3-super-120b-a12b:free` (tested correct on our cards, reasoning disabled), with fallbacks `google/gemma-4-31b-it:free` and `google/gemma-4-26b-a4b-it:free`. Not `openrouter/free`: it can route to a safety classifier.
- Key: `OPENROUTER_API_KEY` in `.env`.
- Free models are rate-limited by OpenRouter. The templates guarantee the demo never depends on the LLM being up.

## Quality of the plans
Measured on 4 saturated snapshots (110–171 incidents waiting, 63 teams). The reference is OR-Tools, Google's routing
solver, started from our plan and given 60 s. `bench/gap_vs_ortools.py`:

| Our budget per decision | Mean gap to OR-Tools | Worst |
|---|---|---|
| 300 ms | +8.1 % | +11.4 % |
| 1 s | +4.4 % | +5.4 % |
| **3 s (live setting)** | **+2.3 %** | +3.7 % |

OR-Tools started from scratch does much worse within 60 s, because our objective has no travel cost to guide its
first solution. That is why it is used as a reference improver, starting from our plan.
