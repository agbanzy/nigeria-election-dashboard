"""Competitiveness index = (1 - margin) * turnout * min(ENP/3, 1), clamped to [0, 1].

Three components, each bounded in [0, 1], multiplied together so the index
penalizes lopsided races (high margin), low-turnout races, and uncompetitive
party systems (low ENP). Cited as adapted from Cox (1997) on Effective Number
of Parties and Blais & Lago (2009) on competitiveness operationalization.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.analysis.descriptive import margin_of_victory, turnout
from app.analysis.enp import effective_number_of_parties


def competitiveness_index(
    *,
    votes_by_party: Mapping[str | int, int],
    accredited: int | None,
    registered: int | None,
) -> float | None:
    margin = margin_of_victory(votes_by_party)
    to = turnout(accredited, registered)
    enp = effective_number_of_parties(votes_by_party)
    if margin is None or to is None or enp <= 0:
        return None
    enp_component = min(enp / 3.0, 1.0)
    value = (1.0 - margin) * to * enp_component
    return max(0.0, min(1.0, value))
