"""Loop 3 (between crises): learn objective weights from the manager's choices (inverse optimisation).

Each time plan B is chosen over recommended plan A: P(B preferred) = σ(θ · (f(A) − f(B))),
with f = [weighted customer-hours, sensitive customer-hours, travel h, max wait, plan changes].
Fit θ by logistic regression and PROPOSE new β / λ values to the manager.
"""
from __future__ import annotations


def fit_weights(pairs: list[tuple[dict, dict]]) -> dict[str, float]:
    """pairs = [(features_of_rejected_A, features_of_chosen_B), ...] -> proposed weights."""
    raise NotImplementedError
