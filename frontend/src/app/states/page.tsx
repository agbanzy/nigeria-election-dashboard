"use client";

/**
 * States index — all 36 states + FCT grouped by geopolitical zone.
 * Links to /states/[code].
 */

import Link from "next/link";

import MethodologyDisclosure from "@/components/shared/MethodologyDisclosure";
import { useApiData } from "@/hooks/useApiData";
import type { StateRow } from "@/lib/api";

const ZONE_LABELS: Record<string, string> = {
  NC: "North Central",
  NE: "North East",
  NW: "North West",
  SE: "South East",
  SS: "South South",
  SW: "South West",
};

const ZONE_COLORS: Record<string, string> = {
  NC: "border-emerald-500/40 bg-emerald-500/5",
  NE: "border-orange-500/40 bg-orange-500/5",
  NW: "border-blue-500/40 bg-blue-500/5",
  SE: "border-purple-500/40 bg-purple-500/5",
  SS: "border-teal-500/40 bg-teal-500/5",
  SW: "border-rose-500/40 bg-rose-500/5",
};

export default function StatesIndex() {
  const { data: states } = useApiData<StateRow[]>("/api/states", 5 * 60_000);
  const byZone: Record<string, StateRow[]> = {};
  for (const s of states || []) {
    (byZone[s.zone] ||= []).push(s);
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-extrabold text-primary">States</h1>
        <p className="text-sm text-dim">
          {states?.length ?? "…"} states, grouped by geopolitical zone. Click any state to see
          its elections, LGAs and results.
        </p>
      </header>

      {Object.entries(ZONE_LABELS).map(([zone, label]) => (
        <section key={zone}>
          <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
            {label} <span className="text-dim font-normal">({byZone[zone]?.length ?? 0})</span>
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {(byZone[zone] || []).map((s) => (
              <Link
                key={s.code}
                href={`/states/${s.code}`}
                className={`rounded border ${ZONE_COLORS[zone]} px-3 py-2 hover:scale-[1.02] transition-transform`}
              >
                <div className="font-semibold text-primary">{s.name}</div>
                <div className="text-[10px] text-dim">{s.code} · id {s.state_id}</div>
              </Link>
            ))}
          </div>
        </section>
      ))}

      <MethodologyDisclosure />
    </div>
  );
}
