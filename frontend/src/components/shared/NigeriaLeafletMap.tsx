"use client";

/**
 * React-Leaflet choropleth of Nigeria's 36 states + FCT.
 *
 * Two coloring modes:
 *   - "winner"  : color each state by its winning party's hex
 *   - "metric"  : intensity ramp on a numeric metric (election count, turnout, etc.)
 *
 * Click a state → /states/<code>.
 */

import { useEffect, useState } from "react";
import {
  GeoJSON,
  MapContainer,
  TileLayer,
} from "react-leaflet";
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

interface Props {
  mode?: "winner" | "metric";
  metricByState?: Map<string, number>;
  winnersByState?: WinnerByState;
  title?: string;
  metricLabel?: string;
}

interface FeatureProps {
  NAME_1: string;
  HASC_1: string;
  GID_1: string;
}

function hascToCode(hasc: string): string {
  const parts = hasc.split(".");
  return parts[parts.length - 1].toUpperCase();
}

function metricColor(value: number, max: number): string {
  if (max === 0 || value === 0) return "#1f2538";
  const t = Math.min(1, value / max);
  const r = Math.round(16 + t * 16);
  const g = Math.round(70 + t * 110);
  const b = Math.round(40 + t * 50);
  return `rgb(${r}, ${g}, ${b})`;
}

export default function NigeriaLeafletMap({
  mode = "winner",
  metricByState,
  winnersByState,
  title = "Nigeria · 36 states + FCT",
  metricLabel = "Elections",
}: Props) {
  const [geojson, setGeojson] = useState<GeoJsonObject | null>(null);
  const router = useRouter();

  useEffect(() => {
    fetch("/ng-states.geojson")
      .then((r) => r.json())
      .then(setGeojson)
      .catch(() => setGeojson(null));
  }, []);

  const max = metricByState ? Math.max(0, ...Array.from(metricByState.values())) : 0;

  const styleFn = (feature?: Feature) => {
    if (!feature) return { fillColor: "#1f2538", color: "#444", weight: 1 };
    const code = hascToCode((feature.properties as FeatureProps).HASC_1);
    let fill = "#1f2538";
    if (mode === "winner" && winnersByState) {
      const w = winnersByState[code];
      if (w?.winner_party_color) fill = w.winner_party_color;
    } else if (metricByState) {
      const v = metricByState.get(code) || 0;
      fill = metricColor(v, max);
    }
    return {
      fillColor: fill,
      color: "#1f2538",
      weight: 1,
      fillOpacity: 0.85,
    };
  };

  const onEach = (feature: Feature, layer: L.Layer) => {
    const props = feature.properties as FeatureProps;
    const code = hascToCode(props.HASC_1);
    let tooltipText: string;
    if (mode === "winner" && winnersByState) {
      const w = winnersByState[code];
      if (w) {
        tooltipText =
          `${props.NAME_1.replace(/([a-z])([A-Z])/g, "$1 $2")} (${code})\n` +
          `Winner: ${w.winner_party_code} · ${w.winner_candidate || "—"}\n` +
          `${w.winner_votes.toLocaleString()} (${(w.winner_share * 100).toFixed(1)}%)\n` +
          `Total: ${w.total_votes.toLocaleString()}`;
      } else {
        tooltipText = `${props.NAME_1} (${code})\nNo data`;
      }
    } else {
      const v = metricByState?.get(code) || 0;
      tooltipText = `${props.NAME_1.replace(
        /([a-z])([A-Z])/g,
        "$1 $2",
      )} (${code})\n${metricLabel}: ${v}`;
    }
    if ("bindTooltip" in layer) {
      (layer as L.GeoJSON).bindTooltip(tooltipText, { sticky: true });
    }
    if ("on" in layer) {
      layer.on({
        click: () => router.push(`/states/${code}`),
        mouseover: (e) => {
          const target = e.target as L.Path;
          target.setStyle({ weight: 2.5, color: "#10b981" });
        },
        mouseout: (e) => {
          const target = e.target as L.Path;
          target.setStyle({ weight: 1, color: "#1f2538" });
        },
      });
    }
  };

  if (!geojson) {
    return (
      <div className="rounded-lg border border-dashboard-border bg-dashboard-card p-8 text-center text-sm text-dim">
        Loading map…
      </div>
    );
  }

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
          {mode === "winner" ? "click to drill in" : "hover · click to drill"}
        </span>
      </div>
      <MapContainer
        center={[9.082, 8.6753]}
        zoom={6}
        style={{ height: 520, width: "100%", background: "#0c1226" }}
        scrollWheelZoom={false}
      >
        <TileLayer
          attribution='&copy; OpenStreetMap &copy; CARTO &copy; GADM 4.1'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        <GeoJSON data={geojson} style={styleFn} onEachFeature={onEach} />
      </MapContainer>
    </div>
  );
}
