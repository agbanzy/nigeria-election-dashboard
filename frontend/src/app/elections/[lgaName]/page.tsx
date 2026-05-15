"use client";

/**
 * Legacy /elections/[lgaName] route. New shape uses numeric election IDs;
 * if the param is numeric we render standings, otherwise we point the user
 * at the new /states/[code] route.
 */

import Link from "next/link";
import { useParams } from "next/navigation";

import EnpBadge from "@/components/shared/EnpBadge";
import MarginBar from "@/components/shared/MarginBar";
import MethodologyDisclosure from "@/components/shared/MethodologyDisclosure";
import { useApiData } from "@/hooks/useApiData";
import type { ElectionRow } from "@/lib/api";

interface PartyRow {
  party_id: number;
  party_code: string;
  party_name: string;
  party_color: string | null;
  candidate: string | null;
  candidate_count?: number;
  is_incumbent: boolean;
  votes: number;
  share: number;
}

interface Standings {
  election: ElectionRow;
  standings: PartyRow[];
  stats: {
    total_votes: number;
    accredited: number | null;
    registered: number | null;
    turnout: number | null;
    margin: number | null;
    enp: number;
    competitiveness: number | null;
  };
}

interface ByLga {
  election: ElectionRow;
  by_lga: {
    lga_id: number;
    lga_name: string;
    total_votes: number;
    winner_party: string | null;
    winner_candidate: string | null;
    standings: PartyRow[];
  }[];
}

export default function ElectionDetailPage() {
  const params = useParams<{ lgaName: string }>();
  const raw = (params.lgaName || "").trim();
  const numeric = /^\d+$/.test(raw) ? Number(raw) : null;
  const { data, error } = useApiData<Standings>(
    numeric ? `/api/elections/${numeric}/standings` : null,
    60_000,
  );
  const { data: byLga } = useApiData<ByLga>(
    numeric ? `/api/elections/${numeric}/by-lga` : null,
    60_000,
  );

  if (!numeric) {
    return (
      <div className="max-w-2xl mx-auto p-6 space-y-4">
        <h1 className="text-xl font-extrabold text-primary">Route changed</h1>
        <p className="text-sm text-dim">
          The dashboard now uses numeric election IDs. Browse by state at{" "}
          <Link className="underline text-accent-green" href="/states/FC">
            /states/[state-code]
          </Link>
          {" "}or the full election list at{" "}
          <Link className="underline text-accent-green" href="/elections">
            /elections
          </Link>
          .
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {error && <div className="text-accent-red text-sm">Standings unavailable.</div>}
      {!data ? (
        <div className="text-sm text-dim">Loading…</div>
      ) : (
        <>
          <header>
            <h1 className="text-xl font-extrabold text-primary">
              {data.election.election_type_label} · {data.election.cycle}
            </h1>
            <p className="text-sm text-dim">
              State ID {data.election.state_id ?? "national"} · {data.election.election_date || "date unknown"}
            </p>
          </header>

          <div className="flex flex-wrap gap-3 text-sm">
            <div className="bg-dashboard-card rounded p-3 border border-dashboard-border">
              <div className="text-[10px] uppercase text-dim">Total votes</div>
              <div className="font-mono font-bold">{data.stats.total_votes.toLocaleString()}</div>
            </div>
            <div className="bg-dashboard-card rounded p-3 border border-dashboard-border">
              <div className="text-[10px] uppercase text-dim">Turnout</div>
              <div className="font-mono">
                {data.stats.turnout != null ? `${(data.stats.turnout * 100).toFixed(1)}%` : "—"}
              </div>
            </div>
            <div className="bg-dashboard-card rounded p-3 border border-dashboard-border">
              <div className="text-[10px] uppercase text-dim">Margin</div>
              <MarginBar value={data.stats.margin ?? null} />
            </div>
            <div className="bg-dashboard-card rounded p-3 border border-dashboard-border">
              <div className="text-[10px] uppercase text-dim">ENP</div>
              <EnpBadge value={data.stats.enp} />
            </div>
          </div>

          {data.standings.length === 0 ? (
            <div className="text-sm text-dim border border-dashboard-border rounded p-4 space-y-2">
              <p>No vote tallies for this election yet.</p>
              <p className="text-xs">
                INEC&apos;s IReV API exposes scanned EC8A result-sheet images, not parsed
                vote counts. Numbers arrive in this dashboard via:
              </p>
              <ul className="text-xs list-disc pl-5 space-y-1">
                <li>Curated historical CSVs (top-of-ticket races already loaded)</li>
                <li>OCR pipeline over the EC8A scans (Phase D)</li>
                <li>External datasets (Stears, Dataphyte) for state aggregates</li>
              </ul>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-[11px] uppercase text-dim border-b border-dashboard-border">
                <tr>
                  <th className="text-left py-2 pr-3">Party</th>
                  <th className="text-left py-2 pr-3">Candidate</th>
                  <th className="text-right py-2 pr-3">Votes</th>
                  <th className="text-right py-2">Share</th>
                </tr>
              </thead>
              <tbody>
                {data.standings.map((s) => (
                  <tr key={s.party_id} className="border-b border-dashboard-border/40">
                    <td className="py-2 pr-3">
                      <span
                        className="inline-block w-2 h-2 rounded-full mr-2"
                        style={{ background: s.party_color || "#94a3b8" }}
                      />
                      {s.party_code}
                    </td>
                    <td className="py-2 pr-3">
                      {s.candidate || "—"}
                      {s.is_incumbent && " (i)"}
                    </td>
                    <td className="py-2 pr-3 text-right font-mono">{s.votes.toLocaleString()}</td>
                    <td className="py-2 text-right font-mono">{(s.share * 100).toFixed(2)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {/* Per-LGA breakdown when this election has LGA-keyed results */}
          {byLga && byLga.by_lga.length > 0 && (
            <section>
              <h2 className="text-sm font-bold uppercase tracking-wider text-dim mt-6 mb-3">
                Results by LGA / Area Council
              </h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {byLga.by_lga.map((block) => (
                  <div
                    key={block.lga_id}
                    className="rounded-lg border border-dashboard-border bg-dashboard-card p-3"
                  >
                    <div className="flex items-baseline justify-between mb-2">
                      <h3 className="font-bold text-primary">{block.lga_name}</h3>
                      <span className="text-[11px] text-dim font-mono">
                        {block.total_votes.toLocaleString()} votes
                      </span>
                    </div>
                    {block.winner_party && (
                      <div className="text-xs text-accent-green mb-2">
                        Winner: <span className="font-bold">{block.winner_party}</span>
                        {block.winner_candidate && ` · ${block.winner_candidate}`}
                      </div>
                    )}
                    <table className="w-full text-xs">
                      <tbody>
                        {block.standings.slice(0, 8).map((s) => (
                          <tr key={s.party_id} className="border-t border-dashboard-border/30">
                            <td className="py-1 pr-2">
                              <span
                                className="inline-block w-1.5 h-1.5 rounded-full mr-1.5 align-middle"
                                style={{ background: s.party_color || "#94a3b8" }}
                              />
                              {s.party_code}
                            </td>
                            <td className="py-1 pr-2 text-dim">
                              {s.candidate || "—"}
                              {s.is_incumbent && " (i)"}
                            </td>
                            <td className="py-1 pr-2 text-right font-mono">
                              {s.votes.toLocaleString()}
                            </td>
                            <td className="py-1 text-right font-mono text-dim">
                              {(s.share * 100).toFixed(1)}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ))}
              </div>
            </section>
          )}

          <MethodologyDisclosure />
        </>
      )}
    </div>
  );
}
