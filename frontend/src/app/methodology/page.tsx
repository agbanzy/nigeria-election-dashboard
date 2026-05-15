"use client";

import { useApiData } from "@/hooks/useApiData";
import type { MethodologyResponse } from "@/lib/api";

export default function MethodologyPage() {
  const { data, error } = useApiData<MethodologyResponse>("/api/methodology", 5 * 60_000);

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-8">
      <header>
        <h1 className="text-2xl font-extrabold text-primary">Methodology &amp; transparency</h1>
        <p className="text-sm text-dim mt-2">
          Every aggregation on this dashboard is traceable to a source. Statistical metrics
          have explicit formulas. Known data gaps are listed openly.
        </p>
      </header>

      {error && (
        <div className="text-accent-red text-sm">Methodology unavailable: {String(error)}</div>
      )}

      <section>
        <h2 className="text-lg font-bold text-primary mb-3">Statistical definitions</h2>
        <div className="space-y-3">
          {(data?.statistical_definitions || []).map((d) => (
            <div key={d.key} className="rounded-lg border border-dashboard-border bg-dashboard-card p-4">
              <div className="font-bold text-primary">{d.name}</div>
              <div className="text-xs font-mono text-accent-green mt-1">{d.formula}</div>
              <div className="text-sm text-dim mt-2">{d.description}</div>
              {d.reference && <div className="text-[11px] text-dim mt-1 italic">{d.reference}</div>}
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-lg font-bold text-primary mb-3">Known data gaps</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wider text-dim border-b border-dashboard-border">
              <th className="py-2 pr-3">Scope</th>
              <th className="py-2 pr-3">Coverage</th>
              <th className="py-2">Reason</th>
            </tr>
          </thead>
          <tbody>
            {(data?.known_gaps || []).map((g) => (
              <tr key={g.scope} className="border-b border-dashboard-border/40">
                <td className="py-2 pr-3 font-semibold text-primary">{g.scope}</td>
                <td className="py-2 pr-3 text-dim">{g.coverage}</td>
                <td className="py-2 text-dim">{g.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2 className="text-lg font-bold text-primary mb-3">Ingested sources</h2>
        {(data?.sources || []).length === 0 && (
          <div className="text-sm text-dim italic">
            No historical sources ingested yet — Phase C will populate this list.
          </div>
        )}
        <ul className="space-y-2 text-sm">
          {(data?.sources || []).map((s) => (
            <li key={s.name} className="rounded border border-dashboard-border bg-dashboard-card p-3">
              <div className="font-bold text-primary">{s.name}</div>
              {s.url && (
                <a
                  className="text-xs text-accent-green underline"
                  href={s.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {s.url}
                </a>
              )}
              <div className="text-[11px] text-dim mt-1">
                License: {s.license || "unknown"} · ingested {s.ingested_at?.slice(0, 10) || "—"}
              </div>
              {s.notes && <div className="text-xs text-dim mt-1">{s.notes}</div>}
            </li>
          ))}
        </ul>
      </section>

      <footer className="text-xs text-dim border-t border-dashboard-border pt-4 space-y-2">
        <p>Data correction or takedown requests: {data?.takedown_contact || "—"}</p>
        <p>
          Powered by{" "}
          <a
            href="https://innoedgetech.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="font-bold text-accent-green underline"
          >
            Innoedge
          </a>{" "}
          · Innoedge Technologies Ltd
        </p>
      </footer>
    </div>
  );
}
