"use client";

/**
 * Per-state landing. Header + election-type breakdown + elections list + LGA grid.
 */

import Link from "next/link";
import { useParams } from "next/navigation";

import MethodologyDisclosure from "@/components/shared/MethodologyDisclosure";
import { useApiData } from "@/hooks/useApiData";
import type { ElectionRow, StateRow } from "@/lib/api";

interface LgaRow {
  lga_id: number;
  name: string;
  kind: string;
  irev_lga_id: number | null;
}

export default function StatePage() {
  const params = useParams<{ stateCode: string }>();
  const code = (params.stateCode || "").toUpperCase();

  const { data: state } = useApiData<StateRow>(`/api/states/${code}`, 60_000);
  const { data: elections } = useApiData<ElectionRow[]>(`/api/elections?state=${code}`, 60_000);
  const { data: lgas } = useApiData<LgaRow[]>(`/api/states/${code}/lgas`, 60_000);

  // Group elections by type
  const byType: Record<string, ElectionRow[]> = {};
  for (const e of elections || []) {
    (byType[e.election_type] ||= []).push(e);
  }
  const sortedTypes = Object.keys(byType).sort();

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-extrabold text-primary">{state?.name || code}</h1>
        <p className="text-sm text-dim">
          {state?.zone ? `${state.zone} geopolitical zone · ` : ""}
          {elections?.length ?? 0} elections · {lgas?.length ?? 0} LGAs
        </p>
      </header>

      {/* Election-type cards */}
      {sortedTypes.length > 0 && (
        <section className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {sortedTypes.map((t) => (
            <div
              key={t}
              className="rounded-lg border border-dashboard-border bg-dashboard-card p-3"
            >
              <div className="text-[10px] uppercase tracking-wider text-dim">
                {byType[t][0].election_type_label}
              </div>
              <div className="text-2xl font-extrabold text-primary mt-1">
                {byType[t].length}
              </div>
              <div className="text-[10px] text-dim mt-1">
                {byType[t].map((e) => e.cycle).sort().reverse().slice(0, 3).join(", ")}
              </div>
            </div>
          ))}
        </section>
      )}

      <section>
        <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
          Elections
        </h2>
        {(!elections || elections.length === 0) && (
          <div className="text-sm text-dim italic border border-dashboard-border rounded p-4">
            No elections for {state?.name || code} ingested yet.
          </div>
        )}
        <div className="overflow-x-auto rounded border border-dashboard-border">
          <table className="w-full text-sm">
            <thead className="bg-black/20 text-[11px] uppercase tracking-wider text-dim">
              <tr>
                <th className="text-left py-2 px-3">Cycle</th>
                <th className="text-left py-2 px-3">Type</th>
                <th className="text-left py-2 px-3">Date</th>
                <th className="text-right py-2 px-3"></th>
              </tr>
            </thead>
            <tbody>
              {(elections || []).map((e) => (
                <tr key={e.election_id} className="border-t border-dashboard-border/40">
                  <td className="py-2 px-3 font-semibold">{e.cycle}</td>
                  <td className="py-2 px-3">{e.election_type_label}</td>
                  <td className="py-2 px-3 text-dim font-mono text-xs">{e.election_date || "—"}</td>
                  <td className="py-2 px-3 text-right">
                    <Link href={`/elections/${e.election_id}`} className="text-xs text-accent-green underline">
                      view →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
          LGAs <span className="text-dim font-normal">({lgas?.length ?? 0})</span>
        </h2>
        {(!lgas || lgas.length === 0) && (
          <div className="text-sm text-dim italic">
            LGA structure not synced yet — the daemon will pick this state up shortly.
          </div>
        )}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
          {(lgas || []).map((l) => (
            <div
              key={l.lga_id}
              className="rounded border border-dashboard-border bg-dashboard-card px-2 py-1.5 text-xs"
            >
              <div className="font-semibold text-primary">{l.name}</div>
              <div className="text-[10px] text-dim">{l.kind}</div>
            </div>
          ))}
        </div>
      </section>

      <MethodologyDisclosure />
    </div>
  );
}
