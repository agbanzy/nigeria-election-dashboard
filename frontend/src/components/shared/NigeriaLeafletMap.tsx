"use client";

/**
 * React-Leaflet choropleth of Nigeria's 36 states + FCT.
 *
 * GeoJSON: GADM v4.1 admin-1 (committed at /public/ng-states.geojson).
 * Maps GADM HASC_1 codes (e.g. "NG.AB") to our 2-letter state code ("AB").
 *
 * Coloring: number of elections on record per state (live from /api/overview
 * via the parent component). States with no data get a muted background.
 *
 * Client-only because Leaflet uses `window` globals. Parent `NigeriaChoropleth`
 * does the `next/dynamic(... { ssr: false })` boundary.
 */

import { useEffect, useState } from "react";
import {
  GeoJSON,
  MapContainer,
  TileLayer,
  Tooltip as LeafletTooltip,
} from "react-leaflet";
import type { Feature, GeoJsonObject } from "geojson";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import { apiUrl } from "@/lib/api";
import { useRouter } from "next/navigation";

interface Props {
  /** state-code → election count (or any other metric) */
  metricByState: Map<string, number>;
  /** title shown above the map */
  metricLabel?: string;
}

interface FeatureProps {
  NAME_1: string;
  HASC_1: string; // e.g. "NG.AB"
  GID_1: string;
}

function hascToCode(hasc: string): string {
  const parts = hasc.split(".");
  return parts[parts.length - 1].toUpperCase();
}

function colorScale(value: number, max: number): string {
  if (max === 0 || value === 0) return "#1f2538";
  const t = Math.min(1, value / max);
  // Green ramp from dim → bright
  const r = Math.round(16 + t * 16);
  const g = Math.round(70 + t * 110);
  const b = Math.round(40 + t * 50);
  return `rgb(${r}, ${g}, ${b})`;
}

export default function NigeriaLeafletMap({ metricByState, metricLabel = "Elections" }: Props) {
  const [geojson, setGeojson] = useState<GeoJsonObject | null>(null);
  const router = useRouter();

  useEffect(() => {
    fetch("/ng-states.geojson")
      .then((r) => r.json())
      .then(setGeojson)
      .catch(() => setGeojson(null));
  }, []);

  const max = Math.max(0, ...Array.from(metricByState.values()));

  const styleFn = (feature?: Feature) => {
    if (!feature) return { fillColor: "#1f2538", color: "#444", weight: 1 };
    const code = hascToCode((feature.properties as FeatureProps).HASC_1);
    const v = metricByState.get(code) || 0;
    return {
      fillColor: colorScale(v, max),
      color: "#1f2538",
      weight: 1,
      fillOpacity: 0.85,
    };
  };

  const onEach = (feature: Feature, layer: L.Layer) => {
    const props = feature.properties as FeatureProps;
    const code = hascToCode(props.HASC_1);
    const v = metricByState.get(code) || 0;
    const tooltipText = `${props.NAME_1.replace(/([a-z])([A-Z])/g, "$1 $2")} (${code})\n${metricLabel}: ${v}`;
    if ("bindTooltip" in layer) {
      (layer as L.GeoJSON).bindTooltip(tooltipText, { sticky: true });
    }
    if ("on" in layer) {
      layer.on({
        click: () => router.push(`/states/${code}`),
        mouseover: (e) => {
          const target = e.target as L.Path;
          target.setStyle({ weight: 2, color: "#10b981" });
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

  return (
    <div className="rounded-lg border border-dashboard-border bg-dashboard-card overflow-hidden">
      <div className="px-4 py-2 border-b border-dashboard-border flex items-center justify-between">
        <h3 className="text-sm font-bold text-primary">Nigeria · 36 states + FCT</h3>
        <span className="text-[10px] text-dim">
          Hover for {metricLabel.toLowerCase()} · click to drill into a state
        </span>
      </div>
      <MapContainer
        center={[9.082, 8.6753]}
        zoom={6}
        style={{ height: 500, width: "100%", background: "#0c1226" }}
        scrollWheelZoom={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · &copy; GADM 4.1'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        <GeoJSON data={geojson} style={styleFn} onEachFeature={onEach} />
      </MapContainer>
    </div>
  );
}
