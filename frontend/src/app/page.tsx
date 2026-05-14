"use client";

/**
 * National overview — replaces the legacy FCT-only home.
 *
 * Reads from the NEW `/api/overview` shape (totals, cycles, types, recent
 * elections) and renders state-aware copy via `lib/branding.ts`.
 *
 * Filter changes (state / cycle / type) re-fetch with query params so the
 * same page works as a per-state landing too.
 */

import Link from "next/link";

import ElectionCountdown from "@/components/shared/ElectionCountdown";
import NigeriaChoropleth from "@/components/shared/NigeriaChoropleth";
import StatCard from "@/components/shared/StatCard";
import MethodologyDisclosure from "@/components/shared/MethodologyDisclosure";
import { useFilters } from "@/context/FilterContext";
import { useApiData } from "@/hooks/useApiData";
import { formatNumber } from "@/lib/utils";

interface OverviewResponse {
  scope: string;
  cycle: number | null;
  totals: { states: number; lgas: number; elections: number };
  cycles: { cycle: number; elections: number }[];
  election_types: { type: string; count: number }[];
  recent_elections: {
    election_id: number;
    cycle: number;
    type: string;
    state_id: number | null;
    date: string | null;
    status: string;
  }[];
}

export default function HomePage() {
  const { state, cycle } = useFilters();
  const qs = new URLSearchParams();
  if (state) qs.set("state", state);
  if (cycle) qs.set("cycle", String(cycle));
  const path = `/api/overview${qs.toString() ? `?${qs}` : ""}`;
  const { data: overview, error } = useApiData<OverviewResponse>(path, 60_000);

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-accent-red/10 border border-accent-red/30 rounded-xl px-4 py-3 text-[13px] text-accent-red">
          Failed to load overview. The backend may still be migrating — see /methodology.
        </div>
      )}

      <ElectionCountdown />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          label="States covered"
          value={overview ? formatNumber(overview.totals.states) : "—"}
          sub="of 36 + FCT"
          color="#3b82f6"
        />
        <StatCard
          label="LGAs covered"
          value={overview ? formatNumber(overview.totals.lgas) : "—"}
          sub="of 774"
          color="#10b981"
        />
        <StatCard
          label="Elections on record"
          value={overview ? formatNumber(overview.totals.elections) : "—"}
          sub="across all cycles"
          color="#a78bfa"
        />
        <StatCard
          label="Distinct cycles"
          value={overview ? String(overview.cycles.length) : "—"}
          sub={
            overview && overview.cycles.length
              ? `${overview.cycles[overview.cycles.length - 1].cycle}–${overview.cycles[0].cycle}`
              : "—"
          }
          color="#fbbf24"
        />
      </div>

      <NigeriaChoropleth />

      <section>
        <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
          Recent elections
        </h2>
        {overview && overview.recent_elections.length === 0 && (
          <div className="text-sm text-dim italic">
            No elections ingested yet. The historical importer ships in Phase C; the live scraper
            wakes for the next scheduled election.
          </div>
        )}
        <ul className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {(overview?.recent_elections || []).map((e) => (
            <li
              key={e.election_id}
              className="rounded border border-dashboard-border bg-dashboard-card px-3 py-2 text-sm flex items-center justify-between"
            >
              <div>
                <div className="font-semibold text-primary">
                  {e.type} · {e.cycle}
                </div>
                <div className="text-[11px] text-dim">{e.date || "date unknown"} · {e.status}</div>
              </div>
              <Link
                href={`/elections/${e.election_id}`}
                className="text-xs text-accent-green underline"
              >
                view →
              </Link>
            </li>
          ))}
        </ul>
        <MethodologyDisclosure />
      </section>
    </div>
  );
}
