"use client";

/**
 * Elections list. Uses the new /api/elections endpoint with the active
 * FilterContext (state / cycle / type). Click a row → /elections/[id].
 */

import Link from "next/link";

import MethodologyDisclosure from "@/components/shared/MethodologyDisclosure";
import { useFilters } from "@/context/FilterContext";
import { useApiData } from "@/hooks/useApiData";
import type { ElectionRow, StateRow } from "@/lib/api";

export default function ElectionsPage() {
  const { state, cycle, electionType } = useFilters();
  const qs = new URLSearchParams();
  if (state) qs.set("state", state);
  if (cycle) qs.set("cycle", String(cycle));
  if (electionType) qs.set("type", electionType);
  const path = `/api/elections${qs.toString() ? `?${qs}` : ""}`;

  const { data: elections, error, isLoading } = useApiData<ElectionRow[]>(path, 60_000);
  const { data: states } = useApiData<StateRow[]>("/api/states", 5 * 60_000);
  const stateById = new Map((states || []).map((s) => [s.state_id, s] as const));

  return (
    <div className="space-y-5">
      {error && (
        <div className="bg-accent-red/10 border border-accent-red/30 rounded-xl px-4 py-3 text-[13px] text-accent-red font-semibold">
          Failed to load elections. Retrying…
        </div>
      )}

      <header className="flex items-baseline justify-between">
        <h2 className="text-xl font-extrabold text-primary">Elections</h2>
        <span className="text-xs text-dim">
          {elections ? `${elections.length} matching` : isLoading ? "loading…" : ""}
        </span>
      </header>

      {elections && elections.length === 0 && !isLoading && (
        <div className="text-sm text-dim italic border border-dashboard-border rounded p-4">
          No elections match the active filters. Try clearing them.
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-dashboard-border">
        <table className="w-full text-sm">
          <thead className="bg-black/20 text-[11px] uppercase tracking-wider text-dim">
            <tr>
              <th className="text-left py-2 px-3">Cycle</th>
              <th className="text-left py-2 px-3">Type</th>
              <th className="text-left py-2 px-3">State</th>
              <th className="text-left py-2 px-3">Date</th>
              <th className="text-left py-2 px-3">Status</th>
              <th className="text-right py-2 px-3"></th>
            </tr>
          </thead>
          <tbody>
            {(elections || []).map((e) => {
              const s = e.state_id ? stateById.get(e.state_id) : null;
              return (
                <tr
                  key={e.election_id}
                  className="border-t border-dashboard-border/40 hover:bg-dashboard-card-hover"
                >
                  <td className="py-2 px-3 font-semibold text-primary">{e.cycle}</td>
                  <td className="py-2 px-3">{e.election_type_label}</td>
                  <td className="py-2 px-3 text-dim">
                    {s ? s.name : e.state_id ? "—" : "National"}
                  </td>
                  <td className="py-2 px-3 text-dim font-mono text-xs">{e.election_date || "—"}</td>
                  <td className="py-2 px-3 text-xs">{e.status}</td>
                  <td className="py-2 px-3 text-right">
                    <Link
                      href={`/elections/${e.election_id}`}
                      className="text-xs text-accent-green underline"
                    >
                      view →
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <MethodologyDisclosure />
    </div>
  );
}
