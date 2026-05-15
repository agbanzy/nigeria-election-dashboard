#!/usr/bin/env python3
"""End-to-end probe of the live Nigeria Election Dashboard.

Hits every data endpoint + page route + sample of rendered HTML, validates
the response shape + HTTP status + critical content markers, prints a
green/red summary. Pure stdlib so it runs anywhere.

Usage:
    python3 backend/tools/e2e.py [URL]    # defaults to the live DO host
    python3 backend/tools/e2e.py http://localhost:8080  # local dev
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any


DEFAULT_URL = "https://ng-election-dashboard-lkxwq.ondigitalocean.app"
URL = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("E2E_URL", DEFAULT_URL)).rstrip("/")

results: list[tuple[str, str, str]] = []  # (status, name, detail)


def fetch(path: str, *, accept: str = "application/json", timeout: int = 30) -> tuple[int, bytes]:
    req = urllib.request.Request(URL + path, headers={"Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read() if hasattr(e, "read") else b""


def fetch_json(path: str, *, timeout: int = 30) -> Any:
    code, body = fetch(path, accept="application/json", timeout=timeout)
    if code >= 400:
        raise urllib.error.HTTPError(URL + path, code, "HTTP error", {}, None)
    if not body:
        return None
    return json.loads(body)


def fetch_html(path: str, *, timeout: int = 30) -> tuple[int, str]:
    code, body = fetch(path, accept="text/html", timeout=timeout)
    return code, body.decode("utf-8", errors="replace")


def check(name: str, fn: Callable[[], str | None]) -> None:
    try:
        detail = fn() or ""
        results.append(("PASS", name, detail))
    except AssertionError as exc:
        results.append(("FAIL", name, f"assertion: {exc}"))
    except Exception as exc:
        results.append(("ERR ", name, f"{type(exc).__name__}: {exc}"))


# ────────────────────────────────────────────────────────────────────────────
# Data endpoint checks
# ────────────────────────────────────────────────────────────────────────────

def t_health() -> str:
    d = fetch_json("/api/health")
    assert d["status"] == "ok", d
    assert d["db"] == "ok", d
    return f"db={d['db']} scraper_last_run={d.get('scraper_last_run')}"


def t_overview_national() -> str:
    d = fetch_json("/api/overview")
    assert d["totals"]["states"] >= 37, d
    assert d["totals"]["elections"] > 0, d
    assert len(d["cycles"]) > 0, d
    return f"states={d['totals']['states']} elections={d['totals']['elections']} cycles={len(d['cycles'])}"


def t_overview_filtered() -> str:
    d = fetch_json("/api/overview?state=IM&cycle=2023")
    assert isinstance(d, dict), d
    return f"scope={d.get('scope')} cycle={d.get('cycle')}"


def t_states_list() -> str:
    d = fetch_json("/api/states")
    assert len(d) == 37, len(d)
    codes = {s["code"] for s in d}
    assert "FC" in codes and "LA" in codes and "IM" in codes, codes
    return f"{len(d)} states"


def t_state_detail() -> str:
    d = fetch_json("/api/states/IM")
    assert d["code"] == "IM" and d["state_id"] == 17, d
    return f"{d['name']} state_id={d['state_id']}"


def t_state_404() -> str:
    code, _ = fetch("/api/states/XX")
    assert code == 404, code
    return f"HTTP {code}"


def t_state_lgas() -> str:
    d = fetch_json("/api/states/IM/lgas")
    assert isinstance(d, list), type(d)
    return f"{len(d)} lgas for IM"


def t_calendar_next() -> str:
    d = fetch_json("/api/calendar/next")
    if d is None:
        return "no upcoming events"
    assert "election_date" in d and "seconds_until" in d, d
    return f"{d['election_date']} ({d['election_type']}) in {d['seconds_until']}s"


def t_calendar_list() -> str:
    d = fetch_json("/api/calendar")
    assert isinstance(d, list), type(d)
    return f"{len(d)} upcoming events"


def t_elections_list() -> str:
    d = fetch_json("/api/elections")
    assert isinstance(d, list) and len(d) > 100, len(d)
    for k in ("election_id", "cycle", "election_type", "election_type_label", "state_id", "election_date", "status"):
        assert k in d[0], (k, d[0])
    return f"{len(d)} elections"


def t_elections_filter_state() -> str:
    d = fetch_json("/api/elections?state=IM")
    for e in d:
        assert e["state_id"] == 17, e
    return f"{len(d)} Imo elections"


def t_elections_filter_cycle() -> str:
    d = fetch_json("/api/elections?cycle=2023")
    for e in d:
        assert e["cycle"] == 2023, e
    return f"{len(d)} 2023 elections"


def t_elections_filter_type() -> str:
    d = fetch_json("/api/elections?type=governorship")
    for e in d:
        assert e["election_type"] == "governorship", e
    return f"{len(d)} governorship elections"


def t_election_detail() -> str:
    d = fetch_json("/api/elections/6")
    assert d["election_id"] == 6 and d["state_id"] == 17, d
    return f"id={d['election_id']} {d['election_type']} {d['cycle']}"


def t_election_404() -> str:
    code, _ = fetch("/api/elections/999999")
    assert code == 404, code
    return f"HTTP {code}"


def t_standings_with_data() -> str:
    d = fetch_json("/api/elections/6/standings")
    assert len(d["standings"]) > 0, "Imo Gov 2023 should have curated standings"
    assert d["stats"]["total_votes"] > 0, d["stats"]
    assert d["stats"]["enp"] > 0, d["stats"]
    parties = {s["party_code"] for s in d["standings"]}
    assert "APC" in parties, parties
    return f"votes={d['stats']['total_votes']:,} parties={len(d['standings'])} ENP={d['stats']['enp']:.2f}"


def t_standings_no_data() -> str:
    """Pick any senate/reps race (we haven't ingested NASS results) to verify
    the empty-state path stays intact."""
    elections = fetch_json("/api/elections?type=senate")
    if not elections:
        return "no senate elections in DB to test empty path"
    eid = elections[0]["election_id"]
    d = fetch_json(f"/api/elections/{eid}/standings")
    assert d["standings"] == [], d
    assert d["stats"]["total_votes"] == 0, d
    return f"senate elec={eid} empty as expected"


def t_pres_standings_match_inec() -> str:
    """2023 Presidential national totals must match INEC-certified figures."""
    d = fetch_json("/api/elections/1/standings")
    by_party = {s["party_code"]: s for s in d["standings"]}
    assert by_party["APC"]["votes"] == 8794726, by_party["APC"]
    assert by_party["PDP"]["votes"] == 6984520, by_party["PDP"]
    assert by_party["LP"]["votes"] == 6101533, by_party["LP"]
    assert by_party["NNPP"]["votes"] == 1496687, by_party["NNPP"]
    # ENP ≈ 3.30 is the academic estimate for that race
    assert 3.2 < d["stats"]["enp"] < 3.4, d["stats"]["enp"]
    return f"4 parties, total={d['stats']['total_votes']:,}, ENP={d['stats']['enp']:.2f}"


def t_candidates() -> str:
    d = fetch_json("/api/candidates?election=6")
    assert isinstance(d, list) and len(d) >= 3, d
    return f"{len(d)} candidates for elec 6"


def t_results() -> str:
    d = fetch_json("/api/results?election=6")
    assert isinstance(d, list) and len(d) >= 3, d
    for k in ("aggregation", "party_code", "votes", "source"):
        assert k in d[0], (k, d[0])
    return f"{len(d)} result rows"


def t_analysis_turnout() -> str:
    d = fetch_json("/api/analysis/turnout?cycle=2023&type=presidential")
    assert isinstance(d, list), d
    return f"{len(d)} state turnout rows"


def t_analysis_enp() -> str:
    d = fetch_json("/api/analysis/enp?cycle=2023")
    assert isinstance(d, list), d
    with_enp = [r for r in d if r["enp"] > 0]
    assert len(with_enp) > 0, f"no rows with ENP > 0 out of {len(d)}"
    return f"{len(d)} rows, {len(with_enp)} with ENP > 0"


def t_analysis_swing_missing_args() -> str:
    code, _ = fetch("/api/analysis/swing")
    assert code == 400, code
    return f"HTTP {code} (as expected)"


def t_analysis_swing() -> str:
    d = fetch_json("/api/analysis/swing?a=2019&b=2023&type=presidential")
    assert "swings" in d, d
    return f"{len(d['swings'])} party swings"


def t_analysis_competitiveness() -> str:
    d = fetch_json("/api/analysis/competitiveness?cycle=2023")
    assert isinstance(d, list), d
    return f"{len(d)} competitiveness rows"


def t_analysis_timeline() -> str:
    d = fetch_json("/api/analysis/timeline?limit=50")
    assert isinstance(d, list), d
    return f"{len(d)} log rows"


def t_scrape_status() -> str:
    d = fetch_json("/api/scrape/status")
    assert d["mode"] in ("live", "preflight", "idle"), d
    return f"mode={d['mode']} interval={d['interval_seconds']}s"


def t_methodology() -> str:
    d = fetch_json("/api/methodology")
    assert len(d["statistical_definitions"]) == 5, d
    assert len(d["known_gaps"]) >= 4, d
    source_names = {s["name"] for s in d["sources"]}
    # We expect at least the IReV sources + 3 curated CSVs
    assert "inec_official_2023_pres" in source_names, source_names
    return f"defs={len(d['statistical_definitions'])} sources={len(d['sources'])}"


def t_sync_status() -> str:
    d = fetch_json("/api/sync/status")
    q = d["queue"]
    assert q["total"] > 0, q
    return f"total={q['total']} complete={q['complete']} pending={q['pending_total']} cache={d['cache']['rows']}"


# ────────────────────────────────────────────────────────────────────────────
# Page rendering checks (HTML shell + critical content markers)
# ────────────────────────────────────────────────────────────────────────────

PAGE_ROUTES = [
    "/",
    "/elections",
    "/elections/1",
    "/elections/6",
    "/elections/99999",
    "/elections/AMAC",
    "/states",
    "/states/IM",
    "/states/FC",
    "/cycles",
    "/cycles/2023",
    "/cycles/2026",
    "/cycles/compare",
    "/cycles/compare?a=2019&b=2023&type=presidential",
    "/analytics",
    "/live",
    "/methodology",
    "/messaging",
]


def t_page(path: str) -> str:
    code, html = fetch_html(path)
    assert code == 200, f"HTTP {code}"
    # Every page must serve the Next.js shell with the brand title (in
    # <title> tag and meta description). Client-rendered sidebar contents
    # aren't guaranteed to be in the static HTML — we don't assert those.
    assert "Nigeria Election Dashboard" in html, "brand title missing"
    assert 'id="__next"' in html or "_next/static" in html, "next.js shell missing"
    return f"HTTP {code} ({len(html):,}B)"


# ────────────────────────────────────────────────────────────────────────────
# Run
# ────────────────────────────────────────────────────────────────────────────

CHECKS: list[tuple[str, Callable[[], str | None]]] = [
    ("api/health", t_health),
    ("api/overview (national)", t_overview_national),
    ("api/overview (filtered)", t_overview_filtered),
    ("api/states (list)", t_states_list),
    ("api/states/IM", t_state_detail),
    ("api/states/XX (404)", t_state_404),
    ("api/states/IM/lgas", t_state_lgas),
    ("api/calendar/next", t_calendar_next),
    ("api/calendar (list)", t_calendar_list),
    ("api/elections (list)", t_elections_list),
    ("api/elections?state=IM", t_elections_filter_state),
    ("api/elections?cycle=2023", t_elections_filter_cycle),
    ("api/elections?type=governorship", t_elections_filter_type),
    ("api/elections/6", t_election_detail),
    ("api/elections/999999 (404)", t_election_404),
    ("api/elections/6/standings (curated)", t_standings_with_data),
    ("api/elections/26/standings (empty)", t_standings_no_data),
    ("api/elections/1/standings (2023 Pres == INEC)", t_pres_standings_match_inec),
    ("api/candidates?election=6", t_candidates),
    ("api/results?election=6", t_results),
    ("api/analysis/turnout", t_analysis_turnout),
    ("api/analysis/enp", t_analysis_enp),
    ("api/analysis/swing (missing args)", t_analysis_swing_missing_args),
    ("api/analysis/swing (valid)", t_analysis_swing),
    ("api/analysis/competitiveness", t_analysis_competitiveness),
    ("api/analysis/timeline", t_analysis_timeline),
    ("api/scrape/status", t_scrape_status),
    ("api/methodology", t_methodology),
    ("api/sync/status", t_sync_status),
]

for name, fn in CHECKS:
    check(name, fn)

for route in PAGE_ROUTES:
    check(f"page {route}", lambda r=route: t_page(r))


fails = [r for r in results if r[0] != "PASS"]

print(f"\n{'-' * 78}")
print(f"E2E against {URL}")
print(f"Ran {len(results)} checks · {len(fails)} fail(s)")
print(f"{'-' * 78}")
for status, name, detail in results:
    icon = "OK" if status == "PASS" else "XX"
    print(f"  [{icon}] {name:<50} {detail}")
print()

sys.exit(1 if fails else 0)
