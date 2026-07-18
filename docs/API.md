# Public API

The dashboard's backing API is **open and free** — the same JSON endpoints the
UI consumes. No API key, no login, no rate cards. Please be polite (cache on
your side, no hammering) so it stays that way.

```
Base URL (production):  https://elections.innoedgetech.com/api
Base URL (local dev):   http://localhost:8080/api
```

All endpoints are `GET` and return JSON unless noted. Write/admin endpoints
are token-gated and not part of the public surface.

## Quick taste

```bash
curl https://elections.innoedgetech.com/api/states
```

```json
[
  { "code": "AB", "name": "Abia", "state_id": 1, "zone": "SE" },
  ...
]
```

```bash
curl "https://elections.innoedgetech.com/api/elections?cycle=2023&type=presidential"
```

```json
[
  {
    "cycle": 2023,
    "election_date": "2023-02-25",
    "election_id": 1,
    "election_type": "presidential",
    "election_type_label": "Presidential",
    "status": "historical",
    ...
  }
]
```

## Common query parameters

| Param | Meaning | Example |
|---|---|---|
| `state` | State code | `state=LA` (Lagos), `state=FC` (FCT) |
| `cycle` | Election year | `cycle=2023` |
| `type` | Election type | `presidential`, `governorship`, `senate`, `house_of_reps`, `state_assembly`, `chairman`, `councillor` |
| `election` | Election id | `election=1` |
| `limit` | Cap result count | `limit=10` |
| `a`, `b` | Two cycles to compare (swing) | `a=2019&b=2023` |
| `aggregation` | Result granularity | `state`, `lga`, `ward` |
| `party` | Party code | `party=APC` |

## Endpoints

### Service & meta

| Endpoint | Returns |
|---|---|
| `/health` | Service, DB, and scraper heartbeat |
| `/overview` | National overview — headline numbers for the landing state |
| `/methodology` | Data provenance, known gaps, metric definitions |

### Reference data

| Endpoint | Returns |
|---|---|
| `/states` | All 36 states + FCT, with geopolitical zone |
| `/states/{code}` | One state |
| `/states/{code}/lgas` | LGAs in a state |
| `/states/lgas/{lga_id}/wards` | Wards in an LGA |
| `/calendar` | Election calendar (filter with `state`, `cycle`, `type`) |
| `/calendar/next` | The next upcoming election |

### Elections & results

| Endpoint | Returns |
|---|---|
| `/elections` | Elections list (filter with `state`, `cycle`, `type`) |
| `/elections/{id}` | One election |
| `/elections/{id}/standings` | Party standings for an election |
| `/elections/{id}/by-lga` | Results broken down by LGA |
| `/candidates` | Candidates (filter with `election`) |
| `/candidates/summary` | Candidate counts and breakdowns |
| `/results` | Raw result rows (filter with `election`, `aggregation`) |

### Analysis

All under `/analysis/…`, filterable with `state` / `cycle` / `type` where it
makes sense:

| Endpoint | Metric |
|---|---|
| `/analysis/turnout` | Turnout = accredited / registered |
| `/analysis/enp` | Effective number of parties (Laakso–Taagepera) |
| `/analysis/swing` | Vote-share swing between two cycles (`a`, `b`) |
| `/analysis/competitiveness` | (1 − margin) × turnout × min(ENP/3, 1) |
| `/analysis/winners` | Winner per state/LGA (drives the choropleth) |
| `/analysis/party-totals` | Party vote totals |
| `/analysis/party-trajectory` | A party's share across cycles (`party`) |
| `/analysis/zone-summary` | Results rolled up by geopolitical zone |
| `/analysis/biggest-swings` | Largest swings (`limit`) |
| `/analysis/timeline` | Results over time |

Metric definitions and formulas: see `/api/methodology` or the
[methodology page](https://elections.innoedgetech.com/methodology).

### Live & sync

| Endpoint | Returns |
|---|---|
| `/live/events` | **Server-Sent Events** stream during live elections |
| `/scrape/status` | What the IReV scraper is doing right now |
| `/sync/status` | Ingestion status |
| `/sync/coverage` | How complete the dataset is, per election |

```bash
# Watch a live election from your terminal
curl -N https://elections.innoedgetech.com/api/live/events
```

## Data licensing

The API serves election-result **facts** compiled from INEC IReV, Stears,
Dataphyte, and INEC archives — see [README § Data sources](../README.md#data-sources--licensing).
Cite your sources when you republish, and verify the original terms before
bulk redistribution.

## Building something with this?

Open an issue or say hello — see
[README § Contributing & collaboration](../README.md#contributing--collaboration).
