"""Effective Number of Parties — Laakso–Taagepera index.

ENP = 1 / Σ(share²) where share_i is party i's share of valid votes.

Reference: Laakso, M., & Taagepera, R. (1979). "Effective" Number of Parties:
A Measure with Application to West Europe. Comparative Political Studies, 12(1).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping


def effective_number_of_parties(votes_by_party: Mapping[str | int, int | float]) -> float:
    """Compute ENP from a {party: votes} mapping.

    Returns 0.0 if total votes == 0.
    """
    total = sum(votes_by_party.values())
    if total <= 0:
        return 0.0
    shares = [v / total for v in votes_by_party.values()]
    sum_sq = sum(s * s for s in shares)
    if sum_sq == 0:
        return 0.0
    return 1.0 / sum_sq


def enp_from_shares(shares: Iterable[float]) -> float:
    """Compute ENP directly from a sequence of party shares (each in [0, 1])."""
    sq = sum(s * s for s in shares)
    if sq == 0:
        return 0.0
    return 1.0 / sq
