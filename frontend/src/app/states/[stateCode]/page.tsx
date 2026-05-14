"use client";

import { useParams } from "next/navigation";

import { useApiData } from "@/hooks/useApiData";
import MethodologyDisclosure from "@/components/shared/MethodologyDisclosure";
import EnpBadge from "@/components/shared/EnpBadge";
import MarginBar from "@/components/shared/MarginBar";
import type { ElectionRow, StateRow } from "@/lib/api";

interface StateOverview {
  state: StateRow;
  elections: ElectionRow[];
  lgas: { lga_id: number; name: string; kind: string }[];
}

export default function StatePage() {
  const params = useParams<{ stateCode: string }>();
  const code = (params.stateCode || "").toUpperCase();

  const { data: state } = useApiData<StateRow>(`/api/states/${code}`, 60_000);
  const { data: elections } = useApiData<ElectionRow[]>(
    `/api/elections?state=${code}`,
    60_000,
  );
  const { data: lgas } = useApiData<{ lga_id: number; name: string; kind: string }[]>(
    `/api/states/${code}/lgas`,
    60_000,
  );

  return (
    <div className="p-5 lg:p-7 max-w-7xl mx-auto space-y-6">
      <header>
        <h1 className="text-2xl font-extrabold text-primary">{state?.name || code}</h1>
        <p className="text-sm text-dim">{state?.zone} geopolitical zone</p>
      </header>

      <section>
        <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
          Elections on record
        </h2>
        {elections && elections.length === 0 && (
          <div className="text-sm text-dim italic">
            No elections ingested yet for {state?.name || code}. Phase C will backfill historical
            cycles.
          </div>
        )}
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wider text-dim border-b border-dashboard-border">
              <th className="py-2 pr-3">Cycle</th>
              <th className="py-2 pr-3">Type</th>
              <th className="py-2 pr-3">Date</th>
              <th className="py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {(elections || []).map((e) => (
              <tr key={e.election_id} className="border-b border-dashboard-border/40">
                <td className="py-2 pr-3 font-semibold">{e.cycle}</td>
                <td className="py-2 pr-3">{e.election_type_label}</td>
                <td className="py-2 pr-3 text-dim">{e.election_date || "—"}</td>
                <td className="py-2">{e.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <MethodologyDisclosure />
      </section>

      <section>
        <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
          LGAs ({lgas?.length ?? 0})
        </h2>
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
    </div>
  );
}
