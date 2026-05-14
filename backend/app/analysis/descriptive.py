"""Descriptive metrics — turnout and margin of victory."""

from __future__ import annotations

from collections.abc import Mapping


def turnout(accredited: int | None, registered: int | None) -> float | None:
    if not registered or registered <= 0 or accredited is None:
        return None
    return accredited / registered


def margin_of_victory(votes_by_party: Mapping[str | int, int]) -> float | None:
    """Winner share minus runner-up share, as a fraction of total valid votes.

    Returns None for elections with < 2 parties or 0 total votes.
    """
    values = sorted(votes_by_party.values(), reverse=True)
    total = sum(values)
    if total <= 0 or len(values) < 2:
        return None
    return (values[0] - values[1]) / total
