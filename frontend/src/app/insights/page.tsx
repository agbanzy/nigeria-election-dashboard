"use client";

/**
 * Insights — cross-cycle, cross-state party trajectories, zone summaries,
 * biggest swings. Animated bars + counters.
 */

import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import AnimatedCounter from "@/components/shared/AnimatedCounter";
import AnimatedShareBar from "@/components/shared/AnimatedShareBar";
import MethodologyDisclosure from "@/components/shared/MethodologyDisclosure";
import { useApiData } from "@/hooks/useApiData";

interface ZoneSummary {
  zone: string;
  total: number;
  winner: string;
  parties: { party_code: string; party_color: string | null; votes: number; share: number }[];
}

interface TrajCycle {
  cycle: number;
  parties: { party_code: string; party_color: string | null; votes: number; share: number }[];
}

interface Swing {
  state_code: string;
  state_name: string;
  party_code: string;
  party_color: string | null;
  share_a: number;
  share_b: number;
  delta: number;
}

interface SwingsResp {
  cycle_a: number;
  cycle_b: number;
  type: string;
  swings: Swing[];
}

const ZONE_LABELS: Record<string, string> = {
  NC: "North Central",
  NE: "North East",
  NW: "North West",
  SE: "South East",
  SS: "South South",
  SW: "South West",
};

const COMMON_PARTIES = ["APC", "PDP", "LP", "NNPP", "APGA", "ADC"];

export default function InsightsPage() {
  const [etype, setEtype] = useState("presidential");
  const [a, setA] = useState("2019");
  const [b, setB] = useState("2023");

  const { data: zones } = useApiData<ZoneSummary[]>(
    `/api/analysis/zone-summary?cycle=${b}&type=${etype}`,
    5 * 60_000,
  );
  const { data: traj } = useApiData<TrajCycle[]>(
    `/api/analysis/party-trajectory?type=${etype}`,
    5 * 60_000,
  );
  const { data: swings } = useApiData<SwingsResp>(
    `/api/analysis/biggest-swings?a=${a}&b=${b}&type=${etype}&limit=30`,
    5 * 60_000,
  );

  // Re-shape party trajectory for line chart
  const trajData = (traj || []).map((c) => {
    const row: Record<string, number | string> = { cycle: c.cycle };
    for (const p of c.parties) {
      if (COMMON_PARTIES.includes(p.party_code)) {
        row[p.party_code] = Number((p.share * 100).toFixed(2));
      }
    }
    return row;
  });

  // Party colors lookup
  const partyColors: Record<string, string> = {};
  for (const c of traj || []) {
    for (const p of c.parties) {
      if (p.party_color) partyColors[p.party_code] = p.party_color;
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-extrabold text-primary">Insights</h1>
        <p className="text-sm text-dim">
          Cross-state, cross-cycle patterns. Swings, geopolitical-zone splits, party
          trajectories.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-2 bg-dashboard-card border border-dashboard-border rounded p-3">
        <Selector label="Election type" value={etype} onChange={setEtype}>
          <option value="presidential">Presidential</option>
          <option value="governorship">Governorship</option>
        </Selector>
        <Selector label="Compare cycle A" value={a} onChange={setA}>
          {["2026", "2025", "2024", "2023", "2019", "2015"].map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </Selector>
        <span className="text-dim">→</span>
        <Selector label="Cycle B" value={b} onChange={setB}>
          {["2026", "2025", "2024", "2023", "2019", "2015"].map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </Selector>
      </div>

      {/* Party trajectory line chart */}
      <section className="rounded-lg border border-dashboard-border bg-dashboard-card p-4">
        <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
          Party vote-share trajectory · {etype}
        </h2>
        {trajData.length === 0 ? (
          <div className="text-sm text-dim italic">No trajectory data yet.</div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trajData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey="cycle" stroke="#6b7280" fontSize={11} />
              <YAxis stroke="#6b7280" fontSize={11} tickFormatter={(v) => `${v}%`} />
              <Tooltip
                contentStyle={{ background: "#0c1226", border: "1px solid #1f2538" }}
                formatter={(value, name) => [`${Number(value).toFixed(2)}%`, String(name)] as [string, string]}
              />
              {COMMON_PARTIES.map((code) => (
                <Line
                  key={code}
                  type="monotone"
                  dataKey={code}
                  stroke={partyColors[code] || "#94a3b8"}
                  strokeWidth={2.5}
                  dot={{ r: 4 }}
                  activeDot={{ r: 6 }}
                  isAnimationActive
                  animationDuration={1200}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </section>

      {/* Zone summary tiles */}
      <section>
        <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
          By geopolitical zone · {b} {etype}
        </h2>
        {!zones || zones.length === 0 ? (
          <div className="text-sm text-dim italic">No zone data for these filters.</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {zones.map((z) => (
              <div
                key={z.zone}
                className="rounded-lg border border-dashboard-border bg-dashboard-card p-4"
              >
                <div className="flex items-baseline justify-between mb-3">
                  <h3 className="font-bold text-primary text-sm">
                    {ZONE_LABELS[z.zone] || z.zone}{" "}
                    <span className="text-[10px] text-dim ml-1">{z.zone}</span>
                  </h3>
                  <span className="text-[10px] text-dim font-mono">
                    <AnimatedCounter value={z.total} /> votes
                  </span>
                </div>
                <div className="space-y-2">
                  {z.parties.slice(0, 5).map((p, i) => (
                    <AnimatedShareBar
                      key={p.party_code}
                      share={p.share}
                      color={p.party_color}
                      label={p.party_code}
                      value={p.votes}
                      delayMs={i * 80}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Biggest swings */}
      <section>
        <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
          Biggest swings · {a} → {b}
        </h2>
        {!swings || swings.swings.length === 0 ? (
          <div className="text-sm text-dim italic">
            No swings to show — both cycles need vote data for the chosen election type.
          </div>
        ) : (
          <div className="overflow-x-auto rounded border border-dashboard-border">
            <table className="w-full text-sm">
              <thead className="bg-black/20 text-[11px] uppercase tracking-wider text-dim">
                <tr>
                  <th className="text-left py-2 px-3">State</th>
                  <th className="text-left py-2 px-3">Party</th>
                  <th className="text-right py-2 px-3">{a}</th>
                  <th className="text-right py-2 px-3">{b}</th>
                  <th className="text-right py-2 px-3">Δ share</th>
                </tr>
              </thead>
              <tbody>
                {swings.swings.slice(0, 25).map((s, i) => {
                  const dir = s.delta > 0 ? "▲" : s.delta < 0 ? "▼" : "■";
                  const color =
                    s.delta > 0 ? "text-accent-green" : s.delta < 0 ? "text-accent-red" : "text-dim";
                  return (
                    <tr
                      key={`${s.state_code}-${s.party_code}-${i}`}
                      className="border-t border-dashboard-border/40"
                    >
                      <td className="py-2 px-3 font-semibold">{s.state_name}</td>
                      <td className="py-2 px-3">
                        <span
                          className="inline-block w-2 h-2 rounded-full mr-1.5 align-middle"
                          style={{ background: s.party_color || "#94a3b8" }}
                        />
                        {s.party_code}
                      </td>
                      <td className="py-2 px-3 text-right font-mono text-dim">
                        {(s.share_a * 100).toFixed(1)}%
                      </td>
                      <td className="py-2 px-3 text-right font-mono">
                        {(s.share_b * 100).toFixed(1)}%
                      </td>
                      <td className={`py-2 px-3 text-right font-mono font-bold ${color}`}>
                        {dir} {(Math.abs(s.delta) * 100).toFixed(1)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <MethodologyDisclosure />
    </div>
  );
}

function Selector({
  label,
  value,
  onChange,
  children,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
}) {
  return (
    <label className="flex items-center gap-1.5 text-xs">
      <span className="text-dim">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="bg-black/20 border border-dashboard-border rounded px-2 py-1"
      >
        {children}
      </select>
    </label>
  );
}
