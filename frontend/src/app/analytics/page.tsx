"use client";

/**
 * Analytics — turnout/ENP/competitiveness with charts.
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import EnpBadge from "@/components/shared/EnpBadge";
import MarginBar from "@/components/shared/MarginBar";
import MethodologyDisclosure from "@/components/shared/MethodologyDisclosure";
import { useFilters } from "@/context/FilterContext";
import { useApiData } from "@/hooks/useApiData";

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

  const turnoutChart = (turnout || [])
    .filter((r) => r.turnout != null)
    .sort((a, b) => (b.turnout || 0) - (a.turnout || 0))
    .map((r) => ({ name: r.state_code, turnout: (r.turnout || 0) * 100 }));

  const enpScatter = (enp || [])
    .filter((r) => r.margin != null && r.enp > 0)
    .map((r) => ({
      enp: r.enp,
      margin: (r.margin || 0) * 100,
      cycle: r.cycle,
      type: r.type,
    }));

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-extrabold text-primary">Analytics</h1>
        <p className="text-sm text-dim">Cross-cycle, cross-state metrics. Filters above apply.</p>
      </header>

      <section className="rounded-lg border border-dashboard-border bg-dashboard-card p-4">
        <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
          Turnout by state {cycle ? `· cycle ${cycle}` : ""}
        </h2>
        {turnoutChart.length === 0 ? (
          <div className="text-sm text-dim italic">
            No turnout data yet for these filters. Needs PU-level accredited/registered counts.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={turnoutChart} margin={{ left: -10, right: 10, top: 10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis
                dataKey="name"
                stroke="#6b7280"
                fontSize={10}
                interval={0}
                angle={-45}
                textAnchor="end"
                height={40}
              />
              <YAxis stroke="#6b7280" fontSize={11} tickFormatter={(v) => `${v}%`} />
              <Tooltip
                contentStyle={{ background: "#0c1226", border: "1px solid #1f2538" }}
                formatter={(value) => [`${Number(value).toFixed(1)}%`, "Turnout"] as [string, string]}
              />
              <Bar dataKey="turnout" fill="#10b981" />
            </BarChart>
          </ResponsiveContainer>
        )}
      </section>

      <section className="rounded-lg border border-dashboard-border bg-dashboard-card p-4">
        <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
          ENP vs margin (each dot = one race)
        </h2>
        {enpScatter.length === 0 ? (
          <div className="text-sm text-dim italic">
            No vote-share data yet. Phase D will populate.
          </div>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={300}>
              <ScatterChart margin={{ left: 10, right: 10, top: 10, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis
                  type="number"
                  dataKey="enp"
                  name="ENP"
                  stroke="#6b7280"
                  fontSize={11}
                  label={{
                    value: "Effective Number of Parties",
                    position: "insideBottom",
                    offset: -10,
                    fill: "#6b7280",
                    fontSize: 11,
                  }}
                />
                <YAxis
                  type="number"
                  dataKey="margin"
                  name="Margin %"
                  stroke="#6b7280"
                  fontSize={11}
                  tickFormatter={(v) => `${v}%`}
                />
                <ZAxis range={[60, 60]} />
                <Tooltip
                  contentStyle={{ background: "#0c1226", border: "1px solid #1f2538" }}
                  cursor={{ strokeDasharray: "3 3" }}
                  formatter={(value, name) =>
                    [
                      name === "Margin %"
                        ? `${Number(value).toFixed(1)}%`
                        : Number(value).toFixed(2),
                      String(name),
                    ] as [string, string]
                  }
                />
                <Scatter data={enpScatter} fill="#a78bfa" />
              </ScatterChart>
            </ResponsiveContainer>
            <div className="text-[10px] text-dim italic mt-1">
              Top-left = competitive multi-party race · bottom-right = uncompetitive single-party dominance.
            </div>
          </>
        )}
      </section>

      <section>
        <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
          ENP &amp; margin per election (first 100)
        </h2>
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
        {comp && comp.length === 0 ? (
          <div className="text-sm text-dim italic">No competitiveness scores yet.</div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2">
            {(comp || []).slice(0, 60).map((row) => {
              const v = row.competitiveness ?? 0;
              const color =
                v >= 0.6
                  ? "bg-accent-green/10 border-accent-green/30"
                  : v >= 0.3
                  ? "bg-accent-orange/10 border-accent-orange/30"
                  : "bg-accent-red/10 border-accent-red/30";
              return (
                <div key={row.election_id} className={`rounded border p-2 text-xs ${color}`}>
                  <div className="text-dim">
                    {row.type} · {row.cycle}
                  </div>
                  <div className="font-mono font-bold text-primary text-base">
                    {row.competitiveness != null ? row.competitiveness.toFixed(2) : "—"}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <MethodologyDisclosure />
    </div>
  );
}
