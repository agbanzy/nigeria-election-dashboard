"""Tests for the EC8A text parser — pure functions, no tesseract needed."""

from __future__ import annotations

from app.ocr.ec8a import _parse_text


def test_parse_typical_ec8a_text():
    sample = """
    POLLING UNIT RESULT
    Registered Voters: 543
    Accredited Voters: 412
    Total Valid Votes: 397
    Rejected: 15

    APC 187
    PDP 102
    LP 88
    NNPP 20
    """
    parsed = _parse_text(sample, cycle=2023)
    assert parsed.registered_voters == 543
    assert parsed.accredited_voters == 412
    assert parsed.total_valid_votes == 397
    assert parsed.total_rejected_votes == 15
    assert parsed.party_votes["APC"] == 187
    assert parsed.party_votes["PDP"] == 102
    assert parsed.party_votes["LP"] == 88
    assert parsed.party_votes["NNPP"] == 20
    assert parsed.confidence == 1.0


def test_parser_tolerates_ocr_noise():
    sample = """
    Reg!stered: 500
    APC: 250
    PDP  150
    LP : 80
    Garbled XYZ stuff in between
    Accredited 410
    """
    parsed = _parse_text(sample, cycle=2023)
    # 'Registered' is misspelled with !; should miss
    assert parsed.registered_voters is None
    assert parsed.accredited_voters == 410
    assert parsed.party_votes["APC"] == 250
    assert parsed.party_votes["PDP"] == 150
    assert parsed.party_votes["LP"] == 80


def test_parser_caps_implausible_values():
    sample = """
    APC 9999999
    PDP 250
    """
    parsed = _parse_text(sample, cycle=2023)
    # 7-digit APC value should be rejected (> 100,000 ceiling)
    assert "APC" not in parsed.party_votes
    assert parsed.party_votes["PDP"] == 250


def test_parser_empty_text():
    parsed = _parse_text("", cycle=None)
    assert parsed.party_votes == {}
    assert parsed.confidence == 0.0
