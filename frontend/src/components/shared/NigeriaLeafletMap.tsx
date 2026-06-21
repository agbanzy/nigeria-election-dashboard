"use client";

/**
 * React-Leaflet choropleth of Nigeria's 36 states + FCT.
 *
 * Two coloring modes:
 *   - "winner"  : color each state by its winning party's hex
 *   - "metric"  : intensity ramp on a numeric metric (election count, turnout, etc.)
 *
 * Click a state → the map zooms (expands) into that state and opens a detail
 * panel. From there "View full results" drills to /states/<code>. State names
 * come from the authoritative DB list (statesByCode) so labels read "FCT",
 * "Akwa Ibom" etc. rather than the raw GADM "FederalCapitalTerritory".
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { GeoJSON, MapContainer, TileLayer, useMap } from "react-leaflet";
import type { Feature, GeoJsonObject } from "geojson";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useRouter } from "next/navigation";

export interface WinnerByState {
  [stateCode: string]: {
    winner_party_code: string;
    winner_party_color: string | null;
    winner_candidate: string | null;
    winner_votes: number;
    winner_share: number;
    margin: number | null;
    total_votes: number;
  };
}

export interface StateMeta {
  name: string;
  zone: string;
}

interface Props {
  mode?: "winner" | "metric";
  metricByState?: Map<string, number>;
  winnersByState?: WinnerByState;
  statesByCode?: Record<string, StateMeta>;
  liveStateCodes?: string[];
  title?: string;
  metricLabel?: string;
}

interface FeatureProps {
  NAME_1: string;
  HASC_1: string;
  GID_1: string;
}

const NG_CENTER: [number, number] = [9.082, 8.6753];
const NG_ZOOM = 6;

function hascToCode(hasc: string): string {
  const parts = hasc.split(".");
  return parts[parts.length - 1].toUpperCase();
}

/** Display name for a state code — prefers the DB name, falls back to a
 *  de-camel-cased GADM name (AkwaIbom → Akwa Ibom). */
function displayName(code: string, gadmName: string, statesByCode?: Record<string, StateMeta>): string {
  return statesByCode?.[code]?.name || gadmName.replace(/([a-z])([A-Z])/g, "$1 $2");
}

function metricColor(value: number, max: number): string {
  if (max === 0 || value === 0) return "#1f2538";
  const t = Math.min(1, value / max);
  const r = Math.round(16 + t * 16);
  const g = Math.round(70 + t * 110);
  const b = Math.round(40 + t * 50);
  return `rgb(${r}, ${g}, ${b})`;
}

/** Drives imperative camera moves: fly into the selected state, or back out. */
function MapCamera({ selectedFeature }: { selectedFeature: Feature | null }) {
  const map = useMap();
  useEffect(() => {
    if (selectedFeature) {
      const bounds = L.geoJSON(selectedFeature).getBounds();
      if (bounds.isValid()) {
        map.flyToBounds(bounds, { padding: [48, 48], maxZoom: 9, duration: 0.7 });
      }
    } else {
      map.flyTo(NG_CENTER, NG_ZOOM, { duration: 0.6 });
    }
  }, [selectedFeature, map]);
  return null;
}

export default function NigeriaLeafletMap({
  mode = "winner",
  metricByState,
  winnersByState,
  statesByCode,
  liveStateCodes,
  title = "Nigeria · 36 states + FCT",
  metricLabel = "Elections",
}: Props) {
  const liveSet = useMemo(() => new Set(liveStateCodes || []), [liveStateCodes]);
  const [geojson, setGeojson] = useState<GeoJsonObject | null>(null);
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const router = useRouter();
  const geoRef = useRef<L.GeoJSON | null>(null);
  // Keep the latest selection reachable inside leaflet event closures.
  const selectedRef = useRef<string | null>(null);
  selectedRef.current = selectedCode;

  useEffect(() => {
    fetch("/ng-states.geojson")
      .then((r) => r.json())
      .then(setGeojson)
      .catch(() => setGeojson(null));
  }, []);

  const max = metricByState ? Math.max(0, ...Array.from(metricByState.values())) : 0;

  const baseStyle = (code: string): L.PathOptions => {
    let fill = "#1f2538";
    let hasData = false;
    if (mode === "winner" && winnersByState) {
      const w = winnersByState[code];
      if (w?.winner_party_color) {
        fill = w.winner_party_color;
        hasData = true;
      }
    } else if (metricByState) {
      fill = metricColor(metricByState.get(code) || 0, max);
    }
    const isLive = liveSet.has(code);
    // A live election with no reported winner yet → amber "counting" tint so
    // the current election stands out instead of looking like an empty state.
    if (isLive && !hasData) fill = "#78350f";
    const sel = selectedRef.current;
    const isSelected = sel === code;
    const dimmed = sel !== null && !isSelected;
    return {
      fillColor: fill,
      color: isSelected ? "#10b981" : isLive ? "#f59e0b" : "#0c1226",
      weight: isSelected ? 3 : isLive ? 2.5 : 1,
      fillOpacity: dimmed ? 0.2 : isLive && !hasData ? 0.75 : 0.88,
    };
  };

  const styleFn = (feature?: Feature): L.PathOptions => {
    if (!feature) return { fillColor: "#1f2538", color: "#444", weight: 1 };
    return baseStyle(hascToCode((feature.properties as FeatureProps).HASC_1));
  };

  // Re-apply styling when selection or data changes (without recreating layers).
  useEffect(() => {
    const gj = geoRef.current;
    if (!gj) return;
    gj.setStyle((feature) => styleFn(feature as Feature));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCode, winnersByState, metricByState, mode, liveStateCodes]);

  const tooltipHtml = (code: string, name: string): string => {
    if (mode === "winner" && winnersByState) {
      const w = winnersByState[code];
      if (w) {
        return (
          `<div style="font-weight:700;margin-bottom:2px">${name} <span style="opacity:.5">${code}</span></div>` +
          `<div><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${w.winner_party_color || "#94a3b8"};margin-right:5px"></span>` +
          `${w.winner_party_code}${w.winner_candidate ? ` · ${w.winner_candidate}` : ""}</div>` +
          `<div style="opacity:.7;font-size:11px">${w.winner_votes.toLocaleString()} votes · ${(w.winner_share * 100).toFixed(1)}%</div>` +
          `<div style="opacity:.5;font-size:11px">Total ${w.total_votes.toLocaleString()}</div>`
        );
      }
      if (liveSet.has(code)) {
        return `<div style="font-weight:700">${name} <span style="opacity:.5">${code}</span></div><div style="color:#f59e0b;font-weight:600">● LIVE — counting</div><div style="opacity:.6;font-size:11px">Results pending</div>`;
      }
      return `<div style="font-weight:700">${name} <span style="opacity:.5">${code}</span></div><div style="opacity:.6">No data</div>`;
    }
    const v = metricByState?.get(code) || 0;
    return `<div style="font-weight:700">${name} <span style="opacity:.5">${code}</span></div><div style="opacity:.7">${metricLabel}: ${v}</div>`;
  };

  const onEach = (feature: Feature, layer: L.Layer) => {
    const props = feature.properties as FeatureProps;
    const code = hascToCode(props.HASC_1);
    const name = displayName(code, props.NAME_1, statesByCode);

    if ("bindTooltip" in layer) {
      (layer as L.GeoJSON).bindTooltip(tooltipHtml(code, name), {
        sticky: true,
        className: "ng-map-tip",
        direction: "top",
      });
    }
    if ("on" in layer) {
      layer.on({
        click: () => setSelectedCode((prev) => (prev === code ? null : code)),
        mouseover: (e) => {
          const t = e.target as L.Path;
          t.setStyle({ weight: 3, color: "#34d399" });
          t.bringToFront();
        },
        mouseout: (e) => {
          (e.target as L.Path).setStyle(baseStyle(code));
        },
      });
    }
  };

  const selectedFeature = useMemo(() => {
    if (!geojson || !selectedCode) return null;
    const fc = geojson as unknown as { features: Feature[] };
    return (
      fc.features.find(
        (f) => hascToCode((f.properties as FeatureProps).HASC_1) === selectedCode,
      ) || null
    );
  }, [geojson, selectedCode]);

  if (!geojson) {
    return (
      <div className="rounded-lg border border-dashboard-border bg-dashboard-card p-8 text-center text-sm text-dim">
        Loading map…
      </div>
    );
  }

  const selectedWinner = selectedCode ? winnersByState?.[selectedCode] : undefined;
  const selectedName = selectedCode
    ? statesByCode?.[selectedCode]?.name ||
      displayName(
        selectedCode,
        ((selectedFeature?.properties as FeatureProps)?.NAME_1) || selectedCode,
        statesByCode,
      )
    : null;
  const selectedZone = selectedCode ? statesByCode?.[selectedCode]?.zone : null;

  // Rebuild the GeoJSON layer (re-runs onEachFeature → fresh tooltips +
  // handlers) when the underlying data changes — the winner data usually
  // arrives AFTER the layer first mounts, and switching the "Color by" preset
  // swaps the whole winners set. Selection changes are NOT in this key (they're
  // handled by the setStyle effect) so expanding a state never rebuilds.
  const geoKey = `${title}|${mode}|${
    winnersByState ? Object.keys(winnersByState).length : 0
  }|${metricByState ? metricByState.size : 0}|${
    statesByCode ? Object.keys(statesByCode).length : 0
  }`;

  const legendEntries =
    mode === "winner" && winnersByState
      ? Array.from(
          new Map(
            Object.values(winnersByState).map((w) => [
              w.winner_party_code,
              w.winner_party_color || "#94a3b8",
            ]),
          ).entries(),
        )
      : [];

  return (
    <div className="rounded-lg border border-dashboard-border bg-dashboard-card overflow-hidden">
      <div className="px-4 py-2 border-b border-dashboard-border flex items-center justify-between gap-3 flex-wrap">
        <h3 className="text-sm font-bold text-primary">{title}</h3>
        {legendEntries.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            {legendEntries.map(([code, color]) => (
              <span key={code} className="flex items-center gap-1 text-xs">
                <span
                  className="inline-block w-2.5 h-2.5 rounded-sm"
                  style={{ background: color }}
                />
                <span className="text-dim">{code}</span>
              </span>
            ))}
          </div>
        )}
        <span className="text-[10px] text-dim">
          {selectedCode ? "click state again to zoom out" : "click a state to expand"}
        </span>
      </div>

      <div className="relative">
        <MapContainer
          center={NG_CENTER}
          zoom={NG_ZOOM}
          style={{ height: 520, width: "100%", background: "#0c1226" }}
          scrollWheelZoom={false}
        >
          <TileLayer
            attribution="&copy; OpenStreetMap &copy; CARTO &copy; GADM 4.1"
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          />
          <GeoJSON
            key={geoKey}
            ref={geoRef}
            data={geojson}
            style={styleFn}
            onEachFeature={onEach}
          />
          <MapCamera selectedFeature={selectedFeature} />
        </MapContainer>

        {/* Detail panel for the expanded state */}
        {selectedCode && (
          <div className="absolute top-3 right-3 z-[1000] w-[260px] max-w-[calc(100%-1.5rem)] rounded-xl border border-dashboard-border bg-dashboard-card/95 backdrop-blur shadow-2xl shadow-black/40 p-4 animate-fade-in">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-base font-extrabold text-primary leading-tight">
                  {selectedName}
                </div>
                <div className="text-[11px] text-dim mt-0.5">
                  {selectedCode}
                  {selectedZone ? ` · ${selectedZone}` : ""}
                </div>
              </div>
              <button
                onClick={() => setSelectedCode(null)}
                aria-label="Close and zoom out"
                className="text-dim hover:text-primary text-lg leading-none px-1"
              >
                ×
              </button>
            </div>

            {selectedWinner ? (
              <div className="mt-3 space-y-2">
                <div className="flex items-center gap-2">
                  <span
                    className="inline-block w-3 h-3 rounded-sm flex-shrink-0"
                    style={{ background: selectedWinner.winner_party_color || "#94a3b8" }}
                  />
                  <span className="text-sm font-bold text-primary">
                    {selectedWinner.winner_party_code}
                  </span>
                  <span className="text-xs text-dim truncate">
                    {selectedWinner.winner_candidate || ""}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div className="rounded bg-black/20 px-2 py-1.5">
                    <div className="text-dim">Votes</div>
                    <div className="font-bold text-primary tabular-nums">
                      {selectedWinner.winner_votes.toLocaleString()}
                    </div>
                  </div>
                  <div className="rounded bg-black/20 px-2 py-1.5">
                    <div className="text-dim">Share</div>
                    <div className="font-bold text-primary tabular-nums">
                      {(selectedWinner.winner_share * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div className="rounded bg-black/20 px-2 py-1.5">
                    <div className="text-dim">Margin</div>
                    <div className="font-bold text-primary tabular-nums">
                      {selectedWinner.margin != null
                        ? `${(selectedWinner.margin * 100).toFixed(1)}%`
                        : "—"}
                    </div>
                  </div>
                  <div className="rounded bg-black/20 px-2 py-1.5">
                    <div className="text-dim">Total</div>
                    <div className="font-bold text-primary tabular-nums">
                      {selectedWinner.total_votes.toLocaleString()}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="mt-3 text-xs text-dim italic">
                No results for this selection.
              </div>
            )}

            <div className="mt-3 flex items-center gap-2">
              <button
                onClick={() => router.push(`/states/${selectedCode}`)}
                className="flex-1 text-xs font-bold rounded-lg bg-accent-green/15 border border-accent-green/30 text-accent-green px-3 py-2 hover:bg-accent-green/25 transition-all"
              >
                View full results →
              </button>
              <button
                onClick={() => setSelectedCode(null)}
                className="text-xs rounded-lg border border-dashboard-border text-dim px-3 py-2 hover:text-primary transition-all"
                title="Zoom back out to Nigeria"
              >
                ← Back
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
