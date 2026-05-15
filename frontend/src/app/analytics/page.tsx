"use client";

/**
 * Analytics — pan-Nigeria ENP, turnout, competitiveness. Uses the new
 * /api/analysis/* endpoints with active filters.
 */

import { useFilters } from "@/context/FilterContext";
import { useApiData } from "@/hooks/useApiData";
import EnpBadge from "@/components/shared/EnpBadge";
import MarginBar from "@/components/shared/MarginBar";
import MethodologyDisclosure from "@/components/shared/MethodologyDisclosure";

interface EnpRow {
  election_id: number;
  cycle: number;
  type: string;
  state_id: number | null;
  enp: number;
  margin: number | null;
}

interface TurnoutRow {
  state_code: string;
  state_name: string;
  accredited: number | null;
  registered: number | null;
  turnout: number | null;
}

interface CompetitivenessRow {
  election_id: number;
  state_id: number | null;
  cycle: number;
  type: string;
  competitiveness: number | null;
}

export default function AnalyticsPage() {
  const { cycle, electionType } = useFilters();
  const qs = new URLSearchParams();
  if (cycle) qs.set("cycle", String(cycle));
  if (electionType) qs.set("type", electionType);
  const suffix = qs.toString() ? `?${qs}` : "";

  const { data: turnout } = useApiData<TurnoutRow[]>(`/api/analysis/turnout${suffix}`, 5 * 60_000);
  const { data: enp } = useApiData<EnpRow[]>(`/api/analysis/enp${suffix}`, 5 * 60_000);
  const { data: comp } = useApiData<CompetitivenessRow[]>(
    `/api/analysis/competitiveness${suffix}`,
    5 * 60_000,
  );

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-extrabold text-primary">Analytics</h1>
        <p className="text-sm text-dim">Cross-cycle, cross-state metrics. Filters above apply.</p>
      </header>

      <section>
        <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
          Turnout by state {cycle ? `(cycle ${cycle})` : ""}
        </h2>
        {turnout && turnout.length === 0 && (
          <div className="text-sm text-dim italic">No turnout data yet for these filters.</div>
        )}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {(turnout || []).map((row) => (
            <div
              key={row.state_code}
              className="rounded border border-dashboard-border bg-dashboard-card px-3 py-2 text-sm"
            >
              <div className="font-semibold text-primary">{row.state_name}</div>
              <div className="font-mono">
                {row.turnout != null ? `${(row.turnout * 100).toFixed(1)}%` : "—"}
              </div>
              <div className="text-[10px] text-dim">
                {row.accredited?.toLocaleString() || "—"} / {row.registered?.toLocaleString() || "—"}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
          ENP &amp; margin per election
        </h2>
        {enp && enp.length === 0 && (
          <div className="text-sm text-dim italic">
            No ENP data yet — needs PU-level vote results (Phase D).
          </div>
        )}
        <div className="overflow-x-auto rounded border border-dashboard-border">
          <table className="w-full text-sm">
            <thead className="text-[11px] uppercase text-dim border-b border-dashboard-border bg-black/20">
              <tr>
                <th className="text-left py-2 px-3">Cycle</th>
                <th className="text-left py-2 px-3">Type</th>
                <th className="text-left py-2 px-3">State</th>
                <th className="text-left py-2 px-3">ENP</th>
                <th className="text-left py-2 px-3">Margin</th>
              </tr>
            </thead>
            <tbody>
              {(enp || []).slice(0, 100).map((row) => (
                <tr key={row.election_id} className="border-t border-dashboard-border/40">
                  <td className="py-2 px-3">{row.cycle}</td>
                  <td className="py-2 px-3">{row.type}</td>
                  <td className="py-2 px-3 text-dim">{row.state_id ?? "national"}</td>
                  <td className="py-2 px-3">
                    <EnpBadge value={row.enp} />
                  </td>
                  <td className="py-2 px-3">
                    <MarginBar value={row.margin} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
          Competitiveness index
        </h2>
        {comp && comp.length === 0 && (
          <div className="text-sm text-dim italic">
            No competitiveness scores yet — needs vote results.
          </div>
        )}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {(comp || []).slice(0, 40).map((row) => (
            <div
              key={row.election_id}
              className="rounded border border-dashboard-border bg-dashboard-card p-2 text-xs"
            >
              <div className="text-dim">
                {row.type} · {row.cycle}
              </div>
              <div className="font-mono font-bold text-primary">
                {row.competitiveness != null ? row.competitiveness.toFixed(3) : "—"}
              </div>
            </div>
          ))}
        </div>
      </section>

      <MethodologyDisclosure />
    </div>
  );
}
