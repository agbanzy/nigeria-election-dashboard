"""IReV election type IDs.

CHAIRMAN/COUNCILLOR were inherited from the legacy `election_dashboard.py` (line 60).
The other 5 are placeholders pending discovery in Phase B — either via the proxy's
`/election-types` endpoint or by inspecting `/elections?year=2023` and harvesting IDs.

Until Phase B fills these, the scraper will skip elections with `election_type` IDs
that aren't in the resolved map.
"""

from __future__ import annotations

# IReV ObjectIds (hex strings). Keys are stable across our codebase.
ELECTION_TYPE_IDS: dict[str, str | None] = {
    "lg_chairman": "5f129a04df41d910dcdc1d55",  # confirmed via legacy
    "councillor": "5f129a04df41d910dcdc1d56",  # confirmed via legacy
    "presidential": None,  # discover in Phase B
    "governorship": None,  # discover in Phase B
    "senate": None,  # discover in Phase B
    "reps": None,  # discover in Phase B
    "state_hoa": None,  # discover in Phase B
}

# Reverse map for IReV → our enum name
_REVERSE: dict[str, str] = {v: k for k, v in ELECTION_TYPE_IDS.items() if v}


def irev_id_to_type(irev_id: str) -> str | None:
    return _REVERSE.get(irev_id)


def type_to_irev_id(election_type: str) -> str | None:
    return ELECTION_TYPE_IDS.get(election_type)


# Human-readable labels for UI / logs
LABELS: dict[str, str] = {
    "presidential": "Presidential",
    "governorship": "Governorship",
    "senate": "Senate",
    "reps": "House of Reps",
    "state_hoa": "State House of Assembly",
    "lg_chairman": "LG Chairman / Area Council Chairman",
    "councillor": "Councillor",
}
