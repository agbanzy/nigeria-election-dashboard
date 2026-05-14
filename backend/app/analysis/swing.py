"""Swing analysis — Δ in party share between two cycles, same election_type + state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class PartySwing:
    party: str | int
    share_prior: float
    share_current: float
    delta: float


def compute_swings(
    prior: Mapping[str | int, int],
    current: Mapping[str | int, int],
) -> list[PartySwing]:
    total_prior = sum(prior.values())
    total_current = sum(current.values())
    parties = set(prior) | set(current)
    out: list[PartySwing] = []
    for p in parties:
        sp = prior.get(p, 0) / total_prior if total_prior else 0.0
        sc = current.get(p, 0) / total_current if total_current else 0.0
        out.append(PartySwing(party=p, share_prior=sp, share_current=sc, delta=sc - sp))
    out.sort(key=lambda s: s.delta, reverse=True)
    return out
