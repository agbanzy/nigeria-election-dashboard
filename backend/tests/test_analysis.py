"""Tests for the statistical analysis layer — no DB needed, pure functions."""

from __future__ import annotations

import math

from app.analysis.competitiveness import competitiveness_index
from app.analysis.descriptive import margin_of_victory, turnout
from app.analysis.enp import effective_number_of_parties, enp_from_shares
from app.analysis.swing import compute_swings


def test_enp_synthetic_50_30_20():
    # ENP for 50/30/20 split = 1 / (0.25 + 0.09 + 0.04) ≈ 2.63
    enp = effective_number_of_parties({"A": 50, "B": 30, "C": 20})
    assert math.isclose(enp, 1 / (0.25 + 0.09 + 0.04), rel_tol=1e-9)
    assert 2.62 < enp < 2.64


def test_enp_zero_votes_returns_zero():
    assert effective_number_of_parties({"A": 0, "B": 0}) == 0.0


def test_enp_single_party_equals_one():
    assert math.isclose(effective_number_of_parties({"A": 100}), 1.0)


def test_enp_from_shares_two_party_even_split():
    assert math.isclose(enp_from_shares([0.5, 0.5]), 2.0)


def test_margin_of_victory():
    # 60% vs 40% on a 100-vote race => 20% margin
    assert math.isclose(margin_of_victory({"A": 60, "B": 40}), 0.20)


def test_margin_returns_none_when_lt_2_parties():
    assert margin_of_victory({"A": 100}) is None


def test_turnout():
    assert math.isclose(turnout(700, 1000) or 0, 0.7)
    assert turnout(0, 0) is None
    assert turnout(None, 1000) is None


def test_competitiveness_index_bounded():
    score = competitiveness_index(
        votes_by_party={"A": 55, "B": 45},
        accredited=80,
        registered=100,
    )
    assert score is not None
    assert 0.0 <= score <= 1.0


def test_competitiveness_zero_turnout_yields_zero():
    score = competitiveness_index(
        votes_by_party={"A": 55, "B": 45},
        accredited=0,
        registered=100,
    )
    assert score == 0.0


def test_swing_simple_two_party():
    prior = {"A": 60, "B": 40}
    current = {"A": 45, "B": 55}
    swings = {s.party: s.delta for s in compute_swings(prior, current)}
    assert math.isclose(swings["A"], -0.15)
    assert math.isclose(swings["B"], 0.15)


def test_swing_handles_new_party():
    prior = {"A": 60, "B": 40}
    current = {"A": 30, "B": 30, "C": 40}
    swings = {s.party: s.delta for s in compute_swings(prior, current)}
    assert math.isclose(swings["C"], 0.40)
