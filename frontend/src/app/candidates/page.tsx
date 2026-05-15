"use client";

/**
 * Candidates listing — all candidates across all elections, filterable by
 * cycle / state / type / party / incumbent-only.
 */

import { useMemo, useState } from "react";
import Link from "next/link";

import MethodologyDisclosure from "@/components/shared/MethodologyDisclosure";
import { useApiData } from "@/hooks/useApiData";
import type { StateRow } from "@/lib/api";
import { ELECTION_LABELS, ELECTION_TYPES, type ElectionType } from "@/lib/electionTypeConfig";

interface Candidate {
  candidate_id: number;
  full_name: string;
  is_incumbent: boolean;
  party_code: string;
  party_name: string;
  party_color: string | null;
  election_id: number;
  election_type: string;
  election_type_label: string;
  cycle: number;
  state_code: string | null;
  state_name: string | null;
  lga_name: string | null;
  ward_name: string | null;
}

interface Summary {
  total_candidates: number;
  distinct_elections: number;
  incumbents: number;
  by_party: { party_code: string; count: number }[];
}

const CYCLES = ["", "2026", "2025", "2024", "2023", "2019", "2015"];

export default function CandidatesPage() {
  const [cycle, setCycle] = useState("");
  const [state, setStateCode] = useState("");
  const [etype, setEtype] = useState<ElectionType | "">("");
  const [party, setParty] = useState("");
  const [incumbent, setIncumbent] = useState(false);

  const { data: states } = useApiData<StateRow[]>("/api/states", 5 * 60_000);
  const { data: summary } = useApiData<Summary>("/api/candidates/summary", 60_000);

  const qs = useMemo(() => {
    const p = new URLSearchParams();
    if (cycle) p.set("cycle", cycle);
    if (state) p.set("state", state);
    if (etype) p.set("type", etype);
    if (party) p.set("party", party);
    if (incumbent) p.set("incumbent", "true");
    p.set("limit", "1000");
    return p.toString();
  }, [cycle, state, etype, party, incumbent]);

  const { data: candidates, isLoading } = useApiData<Candidate[]>(
    `/api/candidates?${qs}`,
    60_000,
  );

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-extrabold text-primary">Candidates</h1>
        <p className="text-sm text-dim">
          Every candidate the dashboard knows about, across cycles + states + election types.
        </p>
      </header>

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="Total candidates" value={summary.total_candidates} />
          <Stat label="Elections covered" value={summary.distinct_elections} />
          <Stat label="Incumbents" value={summary.incumbents} />
          <Stat label="Parties represented" value={summary.by_party.length} />
        </div>
      )}

      <div className="flex flex-wrap gap-2 items-center bg-dashboard-card border border-dashboard-border rounded p-3">
        <Selector label="Cycle" value={cycle} onChange={setCycle}>
          {CYCLES.map((c) => (
            <option key={c} value={c}>{c || "All"}</option>
          ))}
        </Selector>
        <Selector label="State" value={state} onChange={setStateCode}>
          <option value="">All Nigeria</option>
          {(states || []).map((s) => (
            <option key={s.code} value={s.code}>{s.name}</option>
          ))}
        </Selector>
        <Selector label="Type" value={etype} onChange={(v) => setEtype(v as ElectionType | "")}>
          <option value="">All types</option>
          {ELECTION_TYPES.map((t) => (
            <option key={t} value={t}>{ELECTION_LABELS[t]}</option>
          ))}
        </Selector>
        <Selector label="Party" value={party} onChange={setParty}>
          <option value="">All parties</option>
          {(summary?.by_party || []).map((p) => (
            <option key={p.party_code} value={p.party_code}>{p.party_code} ({p.count})</option>
          ))}
        </Selector>
        <label className="flex items-center gap-1.5 text-xs">
          <input
            type="checkbox"
            checked={incumbent}
            onChange={(e) => setIncumbent(e.target.checked)}
          />
          <span className="text-dim">Incumbents only</span>
        </label>
        <span className="text-xs text-dim ml-auto">
          {candidates ? `${candidates.length} matching` : isLoading ? "loading…" : ""}
        </span>
      </div>

      {summary && summary.by_party.length > 0 && (
        <section>
          <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
            Top parties by candidate count
          </h2>
          <div className="flex flex-wrap gap-2">
            {summary.by_party.slice(0, 12).map((p) => (
              <button
                key={p.party_code}
                onClick={() => {
                  // No party filter param yet; visual cue only
                }}
                className="rounded border border-dashboard-border bg-dashboard-card px-3 py-1 text-xs"
              >
                <span className="font-semibold text-primary">{p.party_code}</span>
                <span className="text-dim ml-2">{p.count}</span>
              </button>
            ))}
          </div>
        </section>
      )}

      {candidates && candidates.length === 0 && (
        <div className="text-sm text-dim italic border border-dashboard-border rounded p-4">
          No candidates match the active filters.
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-dashboard-border">
        <table className="w-full text-sm">
          <thead className="bg-black/20 text-[11px] uppercase tracking-wider text-dim">
            <tr>
              <th className="text-left py-2 px-3">Candidate</th>
              <th className="text-left py-2 px-3">Party</th>
              <th className="text-left py-2 px-3">Race</th>
              <th className="text-left py-2 px-3">Cycle</th>
              <th className="text-left py-2 px-3">Scope</th>
              <th className="text-right py-2 px-3"></th>
            </tr>
          </thead>
          <tbody>
            {(candidates || []).map((c) => (
              <tr key={c.candidate_id} className="border-t border-dashboard-border/40">
                <td className="py-2 px-3 font-semibold">
                  {c.full_name}
                  {c.is_incumbent && (
                    <span className="ml-1 text-[10px] uppercase text-accent-orange">(i)</span>
                  )}
                </td>
                <td className="py-2 px-3">
                  <span
                    className="inline-block w-2 h-2 rounded-full mr-2 align-middle"
                    style={{ background: c.party_color || "#94a3b8" }}
                  />
                  {c.party_code}
                </td>
                <td className="py-2 px-3">{c.election_type_label}</td>
                <td className="py-2 px-3">{c.cycle}</td>
                <td className="py-2 px-3 text-dim text-xs">
                  {c.ward_name ? `${c.lga_name} → ${c.ward_name}` : c.lga_name || c.state_name || "National"}
                </td>
                <td className="py-2 px-3 text-right">
                  <Link
                    href={`/elections/${c.election_id}`}
                    className="text-xs text-accent-green underline"
                  >
                    view race →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <MethodologyDisclosure />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-dashboard-border bg-dashboard-card p-3">
      <div className="text-[10px] uppercase tracking-wider text-dim">{label}</div>
      <div className="text-2xl font-extrabold text-primary font-mono">
        {value.toLocaleString()}
      </div>
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
