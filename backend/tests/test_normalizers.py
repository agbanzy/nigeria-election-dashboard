"""Tests for party-code normalization — no DB needed for the pure-mapping bits."""

from __future__ import annotations

from app.importer.normalizers import HISTORICAL_MAPPING


def test_historical_mapping_keys_are_uppercase():
    for (code, cycle) in HISTORICAL_MAPPING:
        assert code == code.upper(), f"code {code!r} must be uppercase"
        assert 1999 <= cycle <= 2050, f"cycle {cycle} out of expected range"


def test_apc_predecessor_codes_present():
    # APC formed in 2013 from CPC + ACN + ANPP. For 2011 results, these must
    # remain distinct, not auto-collapsed to APC.
    assert HISTORICAL_MAPPING[("CPC", 2011)] == "CPC"
    assert HISTORICAL_MAPPING[("ACN", 2011)] == "ACN"
    assert HISTORICAL_MAPPING[("ANPP", 2011)] == "ANPP"
