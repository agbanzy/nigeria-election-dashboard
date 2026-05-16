"use client";

/**
 * Nigeria state choropleth. Defaults to coloring by the 2023 Presidential
 * winner per state. Users can pick another (cycle, type) combo.
 *
 * Falls back to per-state grid below the map.
 */

import dynamic from "next/dynamic";
import Link from "next/link";
import { useMemo, useState } from "react";

import { useApiData } from "@/hooks/useApiData";
import type { StateRow } from "@/lib/api";

const LeafletMap = dynamic(() => import("./NigeriaLeafletMap"), {
  ssr: false,
  loading: () => (
    <div className="rounded-lg border border-dashboard-border bg-dashboard-card p-8 text-center text-sm text-dim">
      Loading map…
    </div>
  ),
});

interface Winner {
  state_code: string;
  state_name: string;
  winner_party_code: string;
  winner_party_color: string | null;
  winner_candidate: string | null;
  winner_votes: number;
  winner_share: number;
  margin: number | null;
  total_votes: number;
}

interface WinnersResp {
  [code: string]: Winner;
}

const COMMON_PICKS: { label: string; cycle: number; type: string }[] = [
  { label: "2023 Presidential", cycle: 2023, type: "presidential" },
  { label: "2023 Governorship", cycle: 2023, type: "governorship" },
  { label: "2024 Governorship", cycle: 2024, type: "governorship" },
  { label: "2026 LG Chairman", cycle: 2026, type: "lg_chairman" },
];

const ZONE_COLORS: Record<string, string> = {
  NC: "bg-emerald-500/10 border-emerald-500/30",
  NE: "bg-orange-500/10 border-orange-500/30",
  NW: "bg-blue-500/10 border-blue-500/30",
  SE: "bg-purple-500/10 border-purple-500/30",
  SS: "bg-teal-500/10 border-teal-500/30",
  SW: "bg-rose-500/10 border-rose-500/30",
};

export default function NigeriaChoropleth() {
  const [pick, setPick] = useState(COMMON_PICKS[0]);
  const { data: states } = useApiData<StateRow[]>("/api/states", 5 * 60_000);
  const { data: winners } = useApiData<WinnersResp>(
    `/api/analysis/winners?cycle=${pick.cycle}&type=${pick.type}`,
    5 * 60_000,
  );

  const winnersCount = useMemo(
    () => (winners ? Object.keys(winners).length : 0),
    [winners],
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-dim">Color by:</span>
        {COMMON_PICKS.map((p) => {
          const active = p.label === pick.label;
          return (
            <button
              key={p.label}
              onClick={() => setPick(p)}
              className={`text-xs rounded-full px-3 py-1 border transition-all ${
                active
                  ? "border-accent-green bg-accent-green/10 text-accent-green font-bold"
                  : "border-dashboard-border bg-dashboard-card text-dim hover:text-primary"
              }`}
            >
              {p.label}
            </button>
          );
        })}
        {winners && (
          <span className="text-[11px] text-dim ml-auto">
            {winnersCount} state{winnersCount === 1 ? "" : "s"} with data
          </span>
        )}
      </div>

      <LeafletMap
        mode="winner"
        winnersByState={winners || {}}
        title={`${pick.label} winners · click a state to drill`}
      />

      <div className="rounded-lg border border-dashboard-border bg-dashboard-card p-3">
        <div className="text-[11px] uppercase tracking-wider text-dim mb-2">
          Direct nav · grouped by geopolitical zone
        </div>
        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-1.5">
          {(states || []).map((s) => {
            const w = winners?.[s.code];
            return (
              <Link
                key={s.code}
                href={`/states/${s.code}`}
                className={`rounded px-2 py-1 text-xs font-semibold border ${
                  ZONE_COLORS[s.zone] || "bg-black/20 border-white/10"
                } hover:scale-[1.03] transition-transform`}
                title={
                  w
                    ? `${s.name}: ${w.winner_party_code} (${(w.winner_share * 100).toFixed(1)}%)`
                    : `${s.name}: no data`
                }
              >
                <div className="text-primary">{s.name}</div>
                <div className="text-[10px] flex items-center justify-between mt-0.5">
                  <span className="text-dim">{s.zone}</span>
                  {w && (
                    <span
                      className="font-mono"
                      style={{ color: w.winner_party_color || undefined }}
                    >
                      {w.winner_party_code}
                    </span>
                  )}
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
