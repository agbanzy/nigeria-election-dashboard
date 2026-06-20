"use client";

/**
 * Cross-cycle comparison. Form picks cycle A, cycle B, election type, optional
 * state filter. Renders swing analysis from /api/analysis/swing.
 */

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import MethodologyDisclosure from "@/components/shared/MethodologyDisclosure";
import SwingArrow from "@/components/shared/SwingArrow";
import { useApiData } from "@/hooks/useApiData";
import type { StateRow } from "@/lib/api";
import { ELECTION_LABELS, ELECTION_TYPES, type ElectionType } from "@/lib/electionTypeConfig";

interface SwingResponse {
  cycle_a: number;
  cycle_b: number;
  type: string;
  state_code: string | null;
  swings: {
    party_id: number;
    party_code: string | null;
    party_name: string | null;
    party_color: string | null;
    share_prior: number;
    share_current: number;
    delta: number;
  }[];
}

const COMMON_CYCLES = [2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2015];

export default function CompareCyclesPage() {
  const router = useRouter();
  const params = useSearchParams();
  const { data: states } = useApiData<StateRow[]>("/api/states", 5 * 60_000);

  const [a, setA] = useState(params.get("a") || "2019");
  const [b, setB] = useState(params.get("b") || "2023");
  const [type, setType] = useState<ElectionType>(
    (params.get("type") as ElectionType) || "presidential",
  );
  const [state, setState] = useState(params.get("state") || "");

  useEffect(() => {
    const next = new URLSearchParams();
    if (a) next.set("a", a);
    if (b) next.set("b", b);
    if (type) next.set("type", type);
    if (state) next.set("state", state);
    router.replace(`/cycles/compare?${next.toString()}`);
  }, [a, b, type, state, router]);

  const apiPath = a && b ? `/api/analysis/swing?a=${a}&b=${b}&type=${type}${state ? `&state=${state}` : ""}` : null;
  const { data, error } = useApiData<SwingResponse>(apiPath ?? "", 5 * 60_000);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-extrabold text-primary">Compare cycles</h1>
        <p className="text-sm text-dim">Swing analysis: change in party vote share between two cycles.</p>
      </header>

      <div className="flex flex-wrap gap-2 items-center bg-dashboard-card border border-dashboard-border rounded p-3">
        <Selector label="Cycle A" value={a} onChange={setA}>
          {COMMON_CYCLES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </Selector>
        <span className="text-dim">→</span>
        <Selector label="Cycle B" value={b} onChange={setB}>
          {COMMON_CYCLES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </Selector>
        <Selector label="Type" value={type} onChange={(v) => setType(v as ElectionType)}>
          {ELECTION_TYPES.map((t) => (
            <option key={t} value={t}>{ELECTION_LABELS[t]}</option>
          ))}
        </Selector>
        <Selector label="State" value={state} onChange={setState}>
          <option value="">All Nigeria</option>
          {(states || []).map((s) => (
            <option key={s.code} value={s.code}>{s.name}</option>
          ))}
        </Selector>
      </div>

      {error && <div className="text-accent-red text-sm">Comparison unavailable.</div>}
      {data && data.swings.length === 0 && (
        <div className="text-sm text-dim italic">
          No vote-share data for these filters yet. Both cycles need PU-level votes to
          compare swings.
        </div>
      )}

      {data && data.swings.length > 0 && (
        <div className="overflow-x-auto rounded border border-dashboard-border">
          <table className="w-full text-sm">
            <thead className="bg-black/20 text-[11px] uppercase text-dim">
              <tr>
                <th className="text-left py-2 px-3">Party</th>
                <th className="text-right py-2 px-3">{data.cycle_a} share</th>
                <th className="text-right py-2 px-3">{data.cycle_b} share</th>
                <th className="text-right py-2 px-3">Swing</th>
              </tr>
            </thead>
            <tbody>
              {data.swings.map((s) => (
                <tr key={s.party_id} className="border-t border-dashboard-border/40">
                  <td className="py-2 px-3 font-semibold">
                    <span className="flex items-center gap-2">
                      <span
                        className="inline-block w-2.5 h-2.5 rounded-sm flex-shrink-0"
                        style={{ background: s.party_color || "#64748b" }}
                      />
                      <span title={s.party_name || undefined}>
                        {s.party_code || s.party_name || `Party #${s.party_id}`}
                      </span>
                    </span>
                  </td>
                  <td className="py-2 px-3 text-right font-mono">{(s.share_prior * 100).toFixed(2)}%</td>
                  <td className="py-2 px-3 text-right font-mono">{(s.share_current * 100).toFixed(2)}%</td>
                  <td className="py-2 px-3 text-right">
                    <SwingArrow delta={s.delta} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

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
