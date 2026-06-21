"""Build per-state LGA + ward GeoJSON assets for the drill-down map.

Sources boundaries from geoBoundaries (open data, CC-BY):
  - ADM2 = LGAs
  - ADM3 = wards

Filters to a target state by spatial containment against the state polygon in
frontend/public/ng-states.geojson, simplifies to keep file size small, and
writes frontend/public/maps/<code>-lgas.geojson and <code>-wards.geojson.

Pure-stdlib point-in-polygon + Douglas–Peucker so it runs without shapely.

Usage:
    python backend/tools/build_state_geojson.py EK Ekiti
    python backend/tools/build_state_geojson.py EK Ekiti --hasc NG.EK
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

GEOB = "https://www.geoboundaries.org/api/current/{tier}/NGA/{adm}/"
TIERS = ("gbOpen", "gbHumanitarian", "gbAuthoritative")
# GRID3 authoritative Nigeria operational ward boundaries (ADM3, 9410 wards),
# pre-tagged with wardname + lganame + statename.
GRID3_WARDS = (
    "https://services3.arcgis.com/BU6Aadhn6tbBEdyk/arcgis/rest/services/"
    "NGA_Ward_Boundaries/FeatureServer/0/query"
)
ROOT = Path(__file__).resolve().parents[2]
STATES_GEOJSON = ROOT / "frontend" / "public" / "ng-states.geojson"
OUT_DIR = ROOT / "frontend" / "public" / "maps"


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "ng-election-dashboard/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r:  # noqa: S310
        return json.loads(r.read().decode())


def _download_geojson(adm: str) -> dict:
    last = None
    for tier in TIERS:
        try:
            meta = _get_json(GEOB.format(tier=tier, adm=adm))
            url = meta.get("gjDownloadURL")
            if not url:
                continue
            print(f"  {adm}: downloading {tier} {url}")
            return _get_json(url)
        except Exception as exc:  # noqa: BLE001
            last = exc
            continue
    raise RuntimeError(f"{adm} not available in any tier ({last})")


def _rings(geom: dict) -> list[list[list[float]]]:
    """Flatten Polygon/MultiPolygon to a list of rings ([[lng,lat],...])."""
    t, c = geom.get("type"), geom.get("coordinates", [])
    if t == "Polygon":
        return c
    if t == "MultiPolygon":
        return [ring for poly in c for ring in poly]
    return []


def _bbox(rings: list) -> tuple[float, float, float, float]:
    xs = [p[0] for ring in rings for p in ring]
    ys = [p[1] for ring in rings for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def _centroid(rings: list) -> tuple[float, float]:
    pts = [p for ring in rings for p in ring]
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def _point_in_ring(x: float, y: float, ring: list) -> bool:
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def _point_in_state(x: float, y: float, state_rings: list) -> bool:
    return any(_point_in_ring(x, y, ring) for ring in state_rings)


def _perp_dist(p, a, b) -> float:
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
    t = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)
    t = max(0, min(1, t))
    px, py = x1 + t * dx, y1 + t * dy
    return ((x - px) ** 2 + (y - py) ** 2) ** 0.5


def _simplify(ring: list, tol: float) -> list:
    if len(ring) < 5:
        return ring
    dmax, idx = 0.0, 0
    for i in range(1, len(ring) - 1):
        d = _perp_dist(ring[i], ring[0], ring[-1])
        if d > dmax:
            dmax, idx = d, i
    if dmax > tol:
        left = _simplify(ring[: idx + 1], tol)
        right = _simplify(ring[idx:], tol)
        return left[:-1] + right
    return [ring[0], ring[-1]]


def _simplify_geom(geom: dict, tol: float) -> dict:
    t = geom.get("type")
    if t == "Polygon":
        return {"type": "Polygon", "coordinates": [_simplify(r, tol) for r in geom["coordinates"]]}
    if t == "MultiPolygon":
        return {
            "type": "MultiPolygon",
            "coordinates": [[_simplify(r, tol) for r in poly] for poly in geom["coordinates"]],
        }
    return geom


def _name(props: dict) -> str:
    for k in ("shapeName", "NAME_2", "NAME_3", "name", "ADM2_EN", "ADM3_EN"):
        if props.get(k):
            return str(props[k])
    return ""


def build(code: str, state_name: str, hasc: str | None) -> None:
    states = json.loads(STATES_GEOJSON.read_text())
    target = None
    for f in states["features"]:
        p = f["properties"]
        if (hasc and p.get("HASC_1") == hasc) or p.get("NAME_1", "").lower() == state_name.lower():
            target = f
            break
    if not target:
        raise SystemExit(f"state {state_name} ({hasc}) not found in ng-states.geojson")
    state_rings = _rings(target["geometry"])
    sx0, sy0, sx1, sy1 = _bbox(state_rings)
    print(f"state {state_name} bbox=({sx0:.3f},{sy0:.3f})-({sx1:.3f},{sy1:.3f})")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    def _in_state(rings: list) -> tuple[float, float] | None:
        cx, cy = _centroid(rings)
        if not (sx0 <= cx <= sx1 and sy0 <= cy <= sy1):
            return None
        return (cx, cy) if _point_in_state(cx, cy, state_rings) else None

    # ADM2 = LGAs. Keep both the simplified output AND the full rings (for
    # spatially assigning wards to their parent LGA).
    lga_polys: list[tuple[str, list]] = []
    lga_feats = []
    for feat in _download_geojson("ADM2")["features"]:
        rings = _rings(feat["geometry"])
        if not rings or _in_state(rings) is None:
            continue
        nm = _name(feat["properties"])
        lga_polys.append((nm, rings))
        feat["geometry"] = _simplify_geom(feat["geometry"], 0.002)
        feat["properties"] = {"name": nm, "state": code}
        lga_feats.append(feat)
    _write(code, "lgas", lga_feats)

    # Wards from GRID3 (authoritative ADM3), pre-tagged with parent LGA.
    try:
        from urllib.parse import urlencode

        params = urlencode(
            {
                "where": f"statename='{state_name}'",
                "outFields": "wardname,lganame,statename",
                "outSR": "4326",
                "f": "geojson",
                "geometryPrecision": "5",
            }
        )
        fc = _get_json(f"{GRID3_WARDS}?{params}")
    except Exception as exc:  # noqa: BLE001
        print(f"  wards: GRID3 unavailable ({exc}) — skipping ward layer")
        return
    ward_feats = []
    for feat in fc.get("features", []):
        if not _rings(feat.get("geometry") or {}):
            continue
        p = feat.get("properties", {})
        feat["geometry"] = _simplify_geom(feat["geometry"], 0.0008)
        feat["properties"] = {
            "name": p.get("wardname", ""),
            "lga": p.get("lganame", ""),
            "state": code,
        }
        ward_feats.append(feat)
    _write(code, "wards", ward_feats)


def _write(code: str, suffix: str, feats: list) -> None:
    dest = OUT_DIR / f"{code.lower()}-{suffix}.geojson"
    dest.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    kb = dest.stat().st_size / 1024
    print(f"  {suffix}: {len(feats)} features -> {dest.name} ({kb:.0f} KB)")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    hasc = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--hasc=")), None)
    if len(args) < 2:
        raise SystemExit("usage: build_state_geojson.py <CODE> <StateName> [--hasc=NG.XX]")
    build(args[0], args[1], hasc)
