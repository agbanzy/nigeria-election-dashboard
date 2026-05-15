"use client";

/**
 * Nigeria state choropleth. Loads the Leaflet map client-side (via
 * `next/dynamic` because Leaflet touches `window` globals). Falls back to a
 * simple state grid while the bundle/GeoJSON load.
 *
 * Coloring metric = number of elections on record per state, pulled from
 * /api/elections. Click a state to drill into /states/<code>.
 */

import dynamic from "next/dynamic";
import Link from "next/link";
import { useMemo } from "react";

import { useApiData } from "@/hooks/useApiData";
import type { ElectionRow, StateRow } from "@/lib/api";

const LeafletMap = dynamic(() => import("./NigeriaLeafletMap"), {
  ssr: false,
  loading: () => (
    <div className="rounded-lg border border-dashboard-border bg-dashboard-card p-8 text-center text-sm text-dim">
      Loading map…
    </div>
  ),
});

const ZONE_COLORS: Record<string, string> = {
  NC: "bg-emerald-500/10 border-emerald-500/30",
  NE: "bg-orange-500/10 border-orange-500/30",
  NW: "bg-blue-500/10 border-blue-500/30",
  SE: "bg-purple-500/10 border-purple-500/30",
  SS: "bg-teal-500/10 border-teal-500/30",
  SW: "bg-rose-500/10 border-rose-500/30",
};

export default function NigeriaChoropleth() {
  const { data: states } = useApiData<StateRow[]>("/api/states", 5 * 60_000);
  const { data: elections } = useApiData<ElectionRow[]>("/api/elections", 60_000);

  const metric = useMemo(() => {
    const m = new Map<string, number>();
    const byId = new Map((states || []).map((s) => [s.state_id, s.code] as const));
    for (const e of elections || []) {
      if (e.state_id == null) continue;
      const code = byId.get(e.state_id);
      if (!code) continue;
      m.set(code, (m.get(code) || 0) + 1);
    }
    return m;
  }, [states, elections]);

  return (
    <div className="space-y-3">
      <LeafletMap metricByState={metric} metricLabel="Elections" />

      {/* Compact zone-keyed grid below the map for fast direct navigation. */}
      <div className="rounded-lg border border-dashboard-border bg-dashboard-card p-3">
        <div className="text-[11px] uppercase tracking-wider text-dim mb-2">
          Direct nav · grouped by geopolitical zone
        </div>
        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-1.5">
          {(states || []).map((s) => (
            <Link
              key={s.code}
              href={`/states/${s.code}`}
              className={`rounded px-2 py-1 text-xs font-semibold border ${
                ZONE_COLORS[s.zone] || "bg-black/20 border-white/10"
              } hover:scale-[1.02] transition-transform`}
              title={`${s.name} (${metric.get(s.code) || 0} elections)`}
            >
              <div className="text-primary">{s.name}</div>
              <div className="text-[10px] text-dim">
                {s.zone} · {metric.get(s.code) || 0}
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
