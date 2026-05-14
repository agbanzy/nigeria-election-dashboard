"use client";

import { useSearchParams } from "next/navigation";

import { useApiData } from "@/hooks/useApiData";
import SwingArrow from "@/components/shared/SwingArrow";
import MethodologyDisclosure from "@/components/shared/MethodologyDisclosure";

interface SwingResponse {
  cycle_a: number;
  cycle_b: number;
  type: string;
  state_code: string | null;
  swings: {
    party_id: number;
    share_prior: number;
    share_current: number;
    delta: number;
  }[];
}

export default function CompareCyclesPage() {
  const params = useSearchParams();
  const a = params.get("a");
  const b = params.get("b");
  const type = params.get("type") || "presidential";
  const state = params.get("state") || "";

  const apiPath =
    a && b
      ? `/api/analysis/swing?a=${a}&b=${b}&type=${type}${state ? `&state=${state}` : ""}`
      : null;
  const { data, error } = useApiData<SwingResponse>(apiPath ?? "", 5 * 60_000);

  return (
    <div className="p-5 lg:p-7 max-w-7xl mx-auto space-y-6">
      <header>
        <h1 className="text-2xl font-extrabold text-primary">
          Compare {a || "?"} → {b || "?"}
        </h1>
        <p className="text-sm text-dim">
          Election type: {type}
          {state ? ` · ${state}` : " · National"}
        </p>
      </header>

      {!apiPath && (
        <div className="text-sm text-dim italic">
          Pass <code>?a=2019&amp;b=2023&amp;type=presidential</code> in the URL to compare cycles.
        </div>
      )}
      {error && (
        <div className="text-sm text-accent-red">Comparison unavailable: {String(error)}</div>
      )}

      {data?.swings && (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wider text-dim border-b border-dashboard-border">
              <th className="py-2 pr-3">Party</th>
              <th className="py-2 pr-3 text-right">{data.cycle_a} share</th>
              <th className="py-2 pr-3 text-right">{data.cycle_b} share</th>
              <th className="py-2 text-right">Swing</th>
            </tr>
          </thead>
          <tbody>
            {data.swings.map((s) => (
              <tr key={s.party_id} className="border-b border-dashboard-border/40">
                <td className="py-2 pr-3 font-semibold">#{s.party_id}</td>
                <td className="py-2 pr-3 text-right font-mono tabular-nums">
                  {(s.share_prior * 100).toFixed(2)}%
                </td>
                <td className="py-2 pr-3 text-right font-mono tabular-nums">
                  {(s.share_current * 100).toFixed(2)}%
                </td>
                <td className="py-2 text-right">
                  <SwingArrow delta={s.delta} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <MethodologyDisclosure />
    </div>
  );
}
