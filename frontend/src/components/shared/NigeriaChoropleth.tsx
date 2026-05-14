"use client";

/**
 * Placeholder for the state-level choropleth.
 *
 * Phase B will wire this up with react-leaflet + GADM level-1 GeoJSON
 * (36 states + FCT). Until then, this renders a clickable state grid as a
 * functional fallback — every state is reachable from the home page even
 * before the map ships.
 */

import Link from "next/link";

import { useApiData } from "@/hooks/useApiData";
import type { StateRow } from "@/lib/api";

const ZONE_COLORS: Record<string, string> = {
  NC: "bg-emerald-500/10 border-emerald-500/30",
  NE: "bg-orange-500/10 border-orange-500/30",
  NW: "bg-blue-500/10 border-blue-500/30",
  SE: "bg-purple-500/10 border-purple-500/30",
  SS: "bg-teal-500/10 border-teal-500/30",
  SW: "bg-rose-500/10 border-rose-500/30",
};

export default function NigeriaChoropleth() {
  const { data } = useApiData<StateRow[]>("/api/states", 5 * 60_000);
  const states = data || [];

  return (
    <div className="rounded-lg border border-dashboard-border bg-dashboard-card p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-bold text-primary text-sm">Nigeria · 36 states + FCT</h3>
        <span className="text-[10px] text-dim italic">Map renders Phase B (Leaflet)</span>
      </div>
      <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
        {states.map((s) => (
          <Link
            key={s.code}
            href={`/states/${s.code}`}
            className={`rounded px-2 py-1.5 text-xs font-semibold border hover:scale-[1.02] transition-transform ${
              ZONE_COLORS[s.zone] || "bg-black/20 border-white/10"
            }`}
          >
            <div className="text-primary">{s.name}</div>
            <div className="text-[10px] text-dim">{s.zone}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
