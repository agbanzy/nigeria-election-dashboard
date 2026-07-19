"""Admin results-ingestion API.

Because INEC's 2026 IReV only publishes scanned EC8A form images + upload
counts (no transcribed votes), this blueprint gives admins four ways to get
real vote tallies into the dashboard:

  1. GET  /api/admin/live-elections — live/recent elections + upload progress.
  2. POST /api/admin/results        — manual per-party vote entry (state/LGA).
  3. POST /api/admin/ocr            — OCR a scanned EC8A image → suggested votes.
  4. POST /api/admin/import         — bulk import transcribed results (rows).

All write endpoints are gated by X-Admin-Token (ADMIN_TOKEN env). The frontend
reaches them through a server-side proxy that verifies the NextAuth admin
session and injects the token, so the token is never exposed to the browser.

Manual / OCR / imported rows are plain ElectionResult rows, so the existing
/api/analysis/winners + /api/analysis/swing aggregation picks them up and the
choropleth + comparison populate automatically.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

import requests
from flask import Blueprint, jsonify, request
from sqlalchemy import delete, func, select

from app.admin_auth import require_admin as _require_admin
from app.db import session_scope
from app.importer.normalizers import resolve_party
from app.models import Election, ElectionResult, Lga, State
from app.scraper.election_types import LABELS
from app.scraper.phases import ensure_source

bp = Blueprint("admin", __name__, url_prefix="/api/admin")

MANUAL_SOURCE = "Manual admin entry"
OCR_SOURCE = "OCR (EC8A)"
IMPORT_SOURCE_PREFIX = "External import"
VOTE_CEILING = 50_000_000  # generous per-party state-total guard
OCR_MAX_BYTES = 15 * 1024 * 1024  # cap remote EC8A downloads to 15 MB


def _unauthorized():
    return jsonify({"error": "unauthorized"}), 401


def _is_public_host(host: str) -> bool:
    """True only if every resolved address for host is a public unicast IP.

    Blocks SSRF into loopback / RFC1918 / link-local (incl. the 169.254.169.254
    cloud metadata endpoint) / reserved ranges.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


def _fetch_remote_image(url: str) -> tuple[bytes | None, str | None]:
    """Fetch a remote image with SSRF guards + a size cap.

    Returns (content, None) on success or (None, error_message) on failure.
    The error message is deliberately generic (no upstream detail) so the
    endpoint can't be used as an SSRF/port-scan oracle.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None, "image_url must be an http(s) URL"
    if not _is_public_host(parts.hostname):
        return None, "image_url host is not allowed"
    try:
        resp = requests.get(
            url, timeout=15, stream=True, headers={"User-Agent": "ned-ocr/1.0"}
        )
        resp.raise_for_status()
        chunks: list[bytes] = []
        total = 0
        for chunk in resp.iter_content(chunk_size=64 * 1024):
            total += len(chunk)
            if total > OCR_MAX_BYTES:
                return None, "image exceeds size limit"
            chunks.append(chunk)
        return b"".join(chunks), None
    except requests.RequestException:
        return None, "image fetch failed"


# ────────────────────────────────────────────────────────────────────────────
# 1. Live elections + upload progress (read)
# ────────────────────────────────────────────────────────────────────────────

@bp.get("/live-elections")
def live_elections():
    """Elections worth attention now: live/preflight/recent priority, or this
    cycle. Includes IReV upload progress + whether results have been entered."""
    if not _require_admin():
        return _unauthorized()
    with session_scope() as session:
        states = {s.state_id: s for s in session.scalars(select(State))}
        stmt = (
            select(Election)
            .where(Election.sync_priority.in_((1, 2, 3)))
            .order_by(Election.sync_priority.asc(), Election.election_date.desc().nullslast())
        )
        rows = list(session.scalars(stmt))
        # Count entered (manual/ocr/import) result rows per election in one query.
        entered = dict(
            session.execute(
                select(ElectionResult.election_id, func.count(ElectionResult.result_id))
                .where(ElectionResult.election_id.in_([e.election_id for e in rows] or [0]))
                .group_by(ElectionResult.election_id)
            ).all()
        )
        out = []
        for e in rows:
            st = states.get(e.state_id) if e.state_id else None
            exp = e.expected_pus or 0
            up = e.uploaded_pus or 0
            out.append(
                {
                    "election_id": e.election_id,
                    "cycle": e.cycle,
                    "type": e.election_type,
                    "type_label": LABELS.get(e.election_type, e.election_type),
                    "state_id": e.state_id,
                    "state_code": st.code if st else None,
                    "state_name": st.name if st else "National",
                    "irev_election_id": e.irev_election_id,
                    "priority": e.sync_priority,
                    "expected_pus": exp,
                    "uploaded_pus": up,
                    "upload_pct": (up / exp) if exp else 0.0,
                    "results_synced_at": e.results_synced_at.isoformat()
                    if e.results_synced_at
                    else None,
                    "result_rows": int(entered.get(e.election_id, 0)),
                }
            )
        return jsonify({"elections": out})


# ────────────────────────────────────────────────────────────────────────────
# 2. Manual vote entry (write)
# ────────────────────────────────────────────────────────────────────────────

@bp.post("/results")
def submit_results():
    """Upsert per-party vote tallies for one election at state or LGA level.

    Body: {
      election_id: int,
      scope: 'state' | 'lga',
      lga_id?: int,                       # required when scope='lga'
      accredited?: int, registered?: int, # optional, applied to each row
      results: [{ party_code: str, votes: int }, ...]
    }

    Idempotent: replaces any prior rows at the same (election, scope, source)
    before inserting, so re-submitting corrects rather than duplicates.
    """
    if not _require_admin():
        return _unauthorized()
    body = request.get_json(silent=True) or {}
    election_id = body.get("election_id")
    scope = (body.get("scope") or "state").lower()
    results = body.get("results") or []
    if not election_id or scope not in ("state", "lga") or not isinstance(results, list):
        return jsonify({"error": "election_id, scope (state|lga), results[] required"}), 400

    with session_scope() as session:
        election = session.get(Election, election_id)
        if election is None:
            return jsonify({"error": "election not found"}), 404
        source = ensure_source(session, MANUAL_SOURCE)

        if scope == "state":
            state_id = election.state_id
            lga_id = None
            if state_id is None:
                return jsonify({"error": "election has no state; use scope=lga"}), 400
        else:
            lga_id = body.get("lga_id")
            if not lga_id:
                return jsonify({"error": "lga_id required for scope=lga"}), 400
            lga = session.get(Lga, lga_id)
            if lga is None:
                return jsonify({"error": "lga not found"}), 404
            state_id = lga.state_id

        accredited = _as_int(body.get("accredited"))
        registered = _as_int(body.get("registered"))

        # Clear prior manual rows for this exact scope, then insert fresh.
        clear = delete(ElectionResult).where(
            ElectionResult.election_id == election_id,
            ElectionResult.source_id == source.source_id,
            ElectionResult.aggregation == scope,
        )
        if scope == "lga":
            clear = clear.where(ElectionResult.lga_id == lga_id)
        session.execute(clear)

        inserted = 0
        for r in results:
            code = str(r.get("party_code") or "").upper().strip()
            votes = _as_int(r.get("votes"))
            if not code or votes is None or votes < 0 or votes > VOTE_CEILING:
                continue
            party = resolve_party(session, code=code, cycle=election.cycle, autocreate=True)
            if party is None:
                continue
            session.add(
                ElectionResult(
                    election_id=election_id,
                    state_id=state_id,
                    lga_id=lga_id,
                    aggregation=scope,
                    party_id=party.party_id,
                    votes=votes,
                    accredited_voters=accredited,
                    registered_voters=registered,
                    source_id=source.source_id,
                )
            )
            inserted += 1

        # Mark the election as live so it surfaces as an active result set.
        if election.status == "historical":
            election.status = "live"

        return jsonify({"ok": True, "inserted": inserted, "scope": scope})


# ────────────────────────────────────────────────────────────────────────────
# 3. OCR-assist (best-effort suggestion)
# ────────────────────────────────────────────────────────────────────────────

@bp.post("/ocr")
def ocr_ec8a():
    """Download a scanned EC8A image and OCR it into suggested party votes.

    Body: { image_url: str, cycle?: int }
    Returns suggested { party_votes, accredited, registered, confidence }.
    Best-effort — handwritten forms OCR poorly, so the admin must review.
    """
    if not _require_admin():
        return _unauthorized()
    from app.ocr.ec8a import parse_ec8a_image

    body = request.get_json(silent=True) or {}
    url = body.get("image_url")
    cycle = _as_int(body.get("cycle"))
    if not url:
        return jsonify({"error": "image_url required"}), 400

    content, err = _fetch_remote_image(str(url))
    if content is None:
        # Generic message — never echo the upstream response/exception, which
        # would turn this endpoint into an SSRF oracle for internal services.
        return jsonify({"error": err or "image fetch failed"}), 502

    parsed = parse_ec8a_image(content, cycle=cycle)
    if parsed is None:
        return jsonify(
            {
                "ok": False,
                "message": "OCR unavailable or unreadable",
                "party_votes": {},
                "confidence": 0.0,
            }
        )
    return jsonify(
        {
            "ok": True,
            "party_votes": parsed.party_votes,
            "accredited": parsed.accredited_voters,
            "registered": parsed.registered_voters,
            "confidence": parsed.confidence,
        }
    )


# ────────────────────────────────────────────────────────────────────────────
# 4. Bulk import from an external transcribed source (write)
# ────────────────────────────────────────────────────────────────────────────

@bp.post("/import")
def import_results():
    """Bulk-insert transcribed results from an external source.

    Body: {
      election_id: int,
      source_label?: str,                  # e.g. 'Dataphyte', 'Partner CSV'
      scope?: 'state' | 'lga',             # default 'state'
      rows: [{ party_code, votes, lga_id? }, ...]
    }
    """
    if not _require_admin():
        return _unauthorized()
    body = request.get_json(silent=True) or {}
    election_id = body.get("election_id")
    rows = body.get("rows") or []
    scope = (body.get("scope") or "state").lower()
    label = str(body.get("source_label") or "feed").strip()[:60]
    if not election_id or not isinstance(rows, list) or not rows:
        return jsonify({"error": "election_id and rows[] required"}), 400

    with session_scope() as session:
        election = session.get(Election, election_id)
        if election is None:
            return jsonify({"error": "election not found"}), 404
        source = ensure_source(session, f"{IMPORT_SOURCE_PREFIX} · {label}")

        # Replace prior rows from this source for this election.
        session.execute(
            delete(ElectionResult).where(
                ElectionResult.election_id == election_id,
                ElectionResult.source_id == source.source_id,
            )
        )
        inserted = 0
        for r in rows:
            code = str(r.get("party_code") or "").upper().strip()
            votes = _as_int(r.get("votes"))
            if not code or votes is None or votes < 0 or votes > VOTE_CEILING:
                continue
            lga_id = _as_int(r.get("lga_id")) if scope == "lga" else None
            state_id = election.state_id
            if scope == "lga" and lga_id:
                lga = session.get(Lga, lga_id)
                state_id = lga.state_id if lga else election.state_id
            party = resolve_party(session, code=code, cycle=election.cycle, autocreate=True)
            if party is None:
                continue
            session.add(
                ElectionResult(
                    election_id=election_id,
                    state_id=state_id,
                    lga_id=lga_id,
                    aggregation=scope,
                    party_id=party.party_id,
                    votes=votes,
                    source_id=source.source_id,
                )
            )
            inserted += 1
        if election.status == "historical" and inserted:
            election.status = "live"
        return jsonify({"ok": True, "inserted": inserted, "source": source.name})


def _as_int(v):
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# ────────────────────────────────────────────────────────────────────────────
# 5. API-access applications (apply-and-approve free API keys)
# ────────────────────────────────────────────────────────────────────────────

@bp.get("/api-clients")
def api_clients():
    """All API access applications, newest first."""
    if not _require_admin():
        return _unauthorized()
    from app.models import ApiClient

    with session_scope() as session:
        rows = session.scalars(
            select(ApiClient).order_by(ApiClient.created_at.desc())
        ).all()
        return jsonify(
            {
                "clients": [
                    {
                        "client_id": c.client_id,
                        "name": c.name,
                        "email": c.email,
                        "use_case": c.use_case,
                        "status": c.status,
                        "api_key": c.api_key if c.status == "approved" else None,
                        "created_at": c.created_at.isoformat() if c.created_at else None,
                        "decided_at": c.decided_at.isoformat() if c.decided_at else None,
                        "last_used_at": c.last_used_at.isoformat() if c.last_used_at else None,
                        "request_count": c.request_count,
                    }
                    for c in rows
                ]
            }
        )


@bp.post("/api-clients/<int:client_id>/decision")
def api_client_decision(client_id: int):
    """Approve / reject / revoke an API access application."""
    if not _require_admin():
        return _unauthorized()
    from app.api.developer import _decide
    from app.models import ApiClient

    body = request.get_json(silent=True) or {}
    action = (body.get("action") or "").strip()
    status_map = {"approve": "approved", "reject": "rejected", "revoke": "revoked"}
    if action not in status_map:
        return jsonify({"error": "action must be approve, reject or revoke"}), 400

    with session_scope() as session:
        client = session.get(ApiClient, client_id)
        if not client:
            return jsonify({"error": "unknown client"}), 404
        _decide(session, client.email, status_map[action])
        return jsonify({"ok": True, "status": status_map[action]})
