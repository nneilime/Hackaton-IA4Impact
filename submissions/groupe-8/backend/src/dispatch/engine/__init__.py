"""Optimisation engine: the only source of decisions and numbers. Owner: RO workstream.

Build order (docs/RO_ENGINE_BRIEF.md §6): evaluate -> baselines -> construct -> local_search -> planner
-> counterfactual / explain -> reference_ortools.
"""
