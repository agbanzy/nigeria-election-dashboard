"use client";

import { useParams } from "next/navigation";

import { useApiData } from "@/hooks/useApiData";
import MethodologyDisclosure from "@/components/shared/MethodologyDisclosure";
import type { ElectionRow } from "@/lib/api";

export default function CyclePage() {
  const params = useParams<{ year: string }>();
  const year = Number(params.year);

  const { data: elections } = useApiData<ElectionRow[]>(
    `/api/elections?cycle=${year}`,
    60_000,
  );

  return (
    <div className="p-5 lg:p-7 max-w-7xl mx-auto space-y-6">
      <header>
        <h1 className="text-2xl font-extrabold text-primary">{year} cycle</h1>
        <p className="text-sm text-dim">All elections recorded for the {year} cycle.</p>
      </header>

      {elections && elections.length === 0 && (
        <div className="text-sm text-dim italic">
          No data ingested for {year} yet. See <a className="underline" href="/methodology">methodology</a>{" "}
          for the ingestion plan.
        </div>
      )}

      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wider text-dim border-b border-dashboard-border">
            <th className="py-2 pr-3">Type</th>
            <th className="py-2 pr-3">State</th>
            <th className="py-2 pr-3">Date</th>
            <th className="py-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {(elections || []).map((e) => (
            <tr key={e.election_id} className="border-b border-dashboard-border/40">
              <td className="py-2 pr-3">{e.election_type_label}</td>
              <td className="py-2 pr-3 text-dim">{e.state_id ?? "national"}</td>
              <td className="py-2 pr-3 text-dim">{e.election_date || "—"}</td>
              <td className="py-2">{e.status}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <MethodologyDisclosure />
    </div>
  );
}
