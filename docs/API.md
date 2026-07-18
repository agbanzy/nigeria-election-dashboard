# Public API

The dashboard's backing API is **free** — the same JSON endpoints the UI
consumes, no rate cards, no billing. Programmatic access is by application:
you apply (free), we approve, you get a key. That keeps usage attributable
and lets us reach you if the data or the API changes.

```
Base URL (production):  https://elections.innoedgetech.com/api
Base URL (local dev):   http://localhost:8080/api
```

All endpoints are `GET` and return JSON unless noted. Write/admin endpoints
are token-gated and not part of the public surface.

## Getting a key

1. Apply at **[elections.innoedgetech.com/api-access](https://elections.innoedgetech.com/api-access)**
   — name, email, and a line on what you're building.
2. Save the `application_ref` shown after applying — it is the only way to
   retrieve your key.
3. Once approved, retrieve your key on the same page and send it as a header:

```bash
curl -H "X-API-Key: ned_..." https://elections.innoedgetech.com/api/states
```

Keyless requests get a `401` with a pointer back to the application page.
`/api/health` and `/api/methodology` are open to everyone, and the dashboard
itself never needs a key. Please still be polite — cache on your side.

## Quick taste

```bash
curl -H "X-API-Key: ned_..." https://elections.innoedgetech.com/api/states
```

```json
[
  { "code": "AB", "name": "Abia", "state_id": 1, "zone": "SE" },
  ...
]
```

```bash
curl -H "X-API-Key: ned_..." \
  "https://elections.innoedgetech.com/api/elections?cycle=2023&type=presidential"
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
curl -N -H "X-API-Key: ned_..." https://elections.innoedgetech.com/api/live/events
```

## Data licensing

The API serves election-result **facts** compiled from INEC IReV, Stears,
Dataphyte, and INEC archives — see [README § Data sources](../README.md#data-sources--licensing).
Cite your sources when you republish, and verify the original terms before
bulk redistribution.

## Building something with this?

Open an issue or say hello — see
[README § Contributing & collaboration](../README.md#contributing--collaboration).
