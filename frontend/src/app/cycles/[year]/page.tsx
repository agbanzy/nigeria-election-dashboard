"use client";

/**
 * Per-cycle view. Groups elections by type, lists with state attribution.
 */

import Link from "next/link";
import { useParams } from "next/navigation";

import MethodologyDisclosure from "@/components/shared/MethodologyDisclosure";
import { useApiData } from "@/hooks/useApiData";
import type { ElectionRow, StateRow } from "@/lib/api";

export default function CyclePage() {
  const params = useParams<{ year: string }>();
  const year = Number(params.year);

  const { data: elections } = useApiData<ElectionRow[]>(`/api/elections?cycle=${year}`, 60_000);
  const { data: states } = useApiData<StateRow[]>("/api/states", 5 * 60_000);
  const stateById = new Map((states || []).map((s) => [s.state_id, s] as const));

  const byType: Record<string, ElectionRow[]> = {};
  for (const e of elections || []) {
    (byType[e.election_type] ||= []).push(e);
  }
  const sortedTypes = Object.keys(byType).sort();

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-extrabold text-primary">{year} cycle</h1>
        <p className="text-sm text-dim">
          {elections?.length ?? 0} elections recorded across {sortedTypes.length} election types.
        </p>
      </header>

      {(!elections || elections.length === 0) && (
        <div className="text-sm text-dim italic border border-dashboard-border rounded p-4">
          No data ingested for {year} yet.
        </div>
      )}

      {sortedTypes.length > 0 && (
        <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {sortedTypes.map((t) => (
            <div
              key={t}
              className="rounded-lg border border-dashboard-border bg-dashboard-card p-3"
            >
              <div className="text-[10px] uppercase tracking-wider text-dim">
                {byType[t][0].election_type_label}
              </div>
              <div className="text-2xl font-extrabold text-primary mt-1">{byType[t].length}</div>
            </div>
          ))}
        </section>
      )}

      {sortedTypes.map((t) => (
        <section key={t}>
          <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
            {byType[t][0].election_type_label}{" "}
            <span className="text-dim font-normal">({byType[t].length})</span>
          </h2>
          <div className="overflow-x-auto rounded border border-dashboard-border">
            <table className="w-full text-sm">
              <thead className="bg-black/20 text-[11px] uppercase tracking-wider text-dim">
                <tr>
                  <th className="text-left py-2 px-3">State</th>
                  <th className="text-left py-2 px-3">Date</th>
                  <th className="text-left py-2 px-3">Status</th>
                  <th className="text-right py-2 px-3"></th>
                </tr>
              </thead>
              <tbody>
                {byType[t].map((e) => {
                  const s = e.state_id ? stateById.get(e.state_id) : null;
                  return (
                    <tr key={e.election_id} className="border-t border-dashboard-border/40">
                      <td className="py-2 px-3 font-semibold">
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
        </section>
      ))}

      <MethodologyDisclosure />
    </div>
  );
}
