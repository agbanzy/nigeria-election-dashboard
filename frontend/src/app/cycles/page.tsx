"use client";

/**
 * Cycles index — every cycle the dashboard knows about, with election counts.
 * Links to /cycles/[year]. Pulls live from /api/overview.
 */

import Link from "next/link";

import MethodologyDisclosure from "@/components/shared/MethodologyDisclosure";
import { useApiData } from "@/hooks/useApiData";

interface OverviewResponse {
  cycles: { cycle: number; elections: number }[];
  election_types: { type: string; count: number }[];
}

export default function CyclesIndex() {
  const { data } = useApiData<OverviewResponse>("/api/overview", 60_000);
  const cycles = (data?.cycles || []).slice().sort((a, b) => b.cycle - a.cycle);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-extrabold text-primary">Cycles</h1>
        <p className="text-sm text-dim">
          Election cycles in the dataset. Click any cycle to drill into races for that year.
        </p>
      </header>

      {cycles.length === 0 ? (
        <div className="text-sm text-dim italic">
          No cycles synced yet. The daemon is in the middle of header discovery.
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
          {cycles.map((c) => (
            <Link
              key={c.cycle}
              href={`/cycles/${c.cycle}`}
              className="rounded-lg border border-dashboard-border bg-dashboard-card p-4 hover:scale-[1.02] transition-transform"
            >
              <div className="text-3xl font-extrabold text-primary">{c.cycle}</div>
              <div className="text-xs text-dim mt-1">{c.elections} elections</div>
            </Link>
          ))}
        </div>
      )}

      <section>
        <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
          Compare cycles
        </h2>
        <p className="text-xs text-dim mb-2">
          Pick two cycles + an election type to see vote-share swings.
        </p>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/cycles/compare?a=2019&b=2023&type=presidential"
            className="text-xs rounded border border-dashboard-border px-3 py-1.5 hover:bg-dashboard-card-hover"
          >
            2019 → 2023 Presidential
          </Link>
          <Link
            href="/cycles/compare?a=2019&b=2023&type=governorship"
            className="text-xs rounded border border-dashboard-border px-3 py-1.5 hover:bg-dashboard-card-hover"
          >
            2019 → 2023 Governorship
          </Link>
          <Link
            href="/cycles/compare"
            className="text-xs rounded border border-dashboard-border px-3 py-1.5 hover:bg-dashboard-card-hover"
          >
            Custom →
          </Link>
        </div>
      </section>

      <MethodologyDisclosure />
    </div>
  );
}
