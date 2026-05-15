"""IReV election type IDs.

All 7 IDs discovered live from `https://dolphin-app-sleqh.ondigitalocean.app/api/v1/election-types`
(INEC's own backend, no auth required for read). Verified 2026-05-15.

The proxy responds to both forms — we use the hex `_id` for the URL query because
that's what the SPA does. The integer `election_type_id` is in the response for
convenience.
"""

from __future__ import annotations

ELECTION_TYPE_IDS: dict[str, str] = {
    "presidential": "5f129a04df41d910dcdc1d50",  # PRES,  type_id 1
    "governorship": "5f129a04df41d910dcdc1d51",  # GOV,   type_id 2
    "senate":       "5f129a04df41d910dcdc1d52",  # SEN,   type_id 3
    "reps":         "5f129a04df41d910dcdc1d53",  #        type_id 4
    "state_hoa":    "5f129a04df41d910dcdc1d54",  #        type_id 5 (State Constituency)
    "lg_chairman":  "5f129a04df41d910dcdc1d55",  #        type_id 6 (Chairmanship)
    "councillor":   "5f129a04df41d910dcdc1d56",  #        type_id 7
}

# Integer aliases (returned in /elections responses); useful for cross-referencing.
INTEGER_TYPE_IDS: dict[str, int] = {
    "presidential": 1,
    "governorship": 2,
    "senate":       3,
    "reps":         4,
    "state_hoa":    5,
    "lg_chairman":  6,
    "councillor":   7,
}

_REVERSE: dict[str, str] = {v: k for k, v in ELECTION_TYPE_IDS.items()}
_REVERSE_INT: dict[int, str] = {v: k for k, v in INTEGER_TYPE_IDS.items()}


def irev_id_to_type(irev_id: str) -> str | None:
    return _REVERSE.get(irev_id)


def integer_id_to_type(int_id: int) -> str | None:
    return _REVERSE_INT.get(int_id)


def type_to_irev_id(election_type: str) -> str | None:
    return ELECTION_TYPE_IDS.get(election_type)


LABELS: dict[str, str] = {
    "presidential": "Presidential",
    "governorship": "Governorship",
    "senate": "Senate",
    "reps": "House of Reps",
    "state_hoa": "State House of Assembly",
    "lg_chairman": "LG Chairman / Area Council Chairman",
    "councillor": "Councillor",
}
