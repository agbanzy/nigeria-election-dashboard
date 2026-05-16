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
            <NoStandingsBlock
              electionId={data.election.election_id}
              cycle={data.election.cycle}
              stateId={data.election.state_id}
              electionType={data.election.election_type}
            />
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


/* ----------------------------------------------------------------------- */
/* Empty-state block: instead of a dead end, surface related useful data   */
/* ----------------------------------------------------------------------- */

interface RelatedElection {
  election_id: number;
  cycle: number;
  election_type: string;
  election_type_label: string;
  state_id: number | null;
  election_date: string | null;
  has_data?: boolean;
}

function NoStandingsBlock({
  electionId,
  cycle,
  stateId,
  electionType,
}: {
  electionId: number;
  cycle: number;
  stateId: number | null;
  electionType: string;
}) {
  // Get the state code for nav
  const { data: states } = useApiData<{ state_id: number; code: string; name: string }[]>(
    "/api/states",
    5 * 60_000,
  );
  const state = stateId ? (states || []).find((s) => s.state_id === stateId) : null;

  // Related races in the same state (any cycle/type) — pick a few that have data
  const { data: stateRaces } = useApiData<RelatedElection[]>(
    state ? `/api/elections?state=${state.code}` : null,
    60_000,
  );
  const { data: cycleRaces } = useApiData<RelatedElection[]>(
    `/api/elections?cycle=${cycle}`,
    60_000,
  );

  // We don't know which have data without querying each; cap the list and
  // let the user click through.
  const sameState = (stateRaces || []).filter((e) => e.election_id !== electionId).slice(0, 6);
  const sameCycle = (cycleRaces || [])
    .filter((e) => e.election_id !== electionId && e.election_type !== electionType)
    .slice(0, 6);

  const dropCsvCommand = `# In backend/data/historical/, drop a CSV with columns:
#   state_code, party_code, votes, candidate_name, is_incumbent
# Add an entry to seed_historical.DATASETS pointing at it, then re-deploy.
python -m app.importer.cli load \\
  --file data/historical/${cycle}_${electionType}_state.csv \\
  --cycle ${cycle} --type ${electionType} --aggregation state \\
  --source curated_${cycle}_${electionType}`;

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-dashboard-border bg-dashboard-card p-4 space-y-2">
        <div className="flex items-baseline gap-2">
          <span className="inline-block w-2 h-2 rounded-full bg-accent-orange animate-pulse" />
          <h3 className="font-bold text-primary text-sm">No vote tallies for this race yet</h3>
        </div>
        <p className="text-xs text-dim">
          INEC&apos;s IReV API exposes scanned EC8A result-sheet images for this election but no
          parsed vote tallies. The daemon will ingest them once they appear in IReV&apos;s
          per-PU JSON, or we can drop a curated CSV.
        </p>
      </div>

      {state && sameState.length > 0 && (
        <section>
          <h3 className="text-xs uppercase tracking-wider text-dim font-bold mb-2">
            Other races in {state.name}
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {sameState.map((e) => (
              <Link
                key={e.election_id}
                href={`/elections/${e.election_id}`}
                className="rounded border border-dashboard-border bg-dashboard-card hover:border-accent-green/40 hover:bg-dashboard-card-hover transition-all p-3 text-sm"
              >
                <div className="font-semibold text-primary">{e.election_type_label}</div>
                <div className="text-[11px] text-dim">
                  {e.cycle} · {e.election_date || "date unknown"}
                </div>
              </Link>
            ))}
          </div>
          <Link
            href={`/states/${state.code}`}
            className="text-xs text-accent-green underline mt-2 inline-block"
          >
            All {state.name} races →
          </Link>
        </section>
      )}

      {sameCycle.length > 0 && (
        <section>
          <h3 className="text-xs uppercase tracking-wider text-dim font-bold mb-2">
            Other {cycle} races
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {sameCycle.map((e) => (
              <Link
                key={e.election_id}
                href={`/elections/${e.election_id}`}
                className="rounded border border-dashboard-border bg-dashboard-card hover:border-accent-green/40 hover:bg-dashboard-card-hover transition-all p-3 text-sm"
              >
                <div className="font-semibold text-primary">{e.election_type_label}</div>
                <div className="text-[11px] text-dim">
                  state {e.state_id ?? "national"} · {e.election_date || "—"}
                </div>
              </Link>
            ))}
          </div>
          <Link
            href={`/cycles/${cycle}`}
            className="text-xs text-accent-green underline mt-2 inline-block"
          >
            All {cycle} races →
          </Link>
        </section>
      )}

      <details className="rounded border border-dashboard-border bg-dashboard-card p-3">
        <summary className="text-xs font-bold text-primary cursor-pointer">
          How to add this data
        </summary>
        <p className="text-xs text-dim mt-2 mb-2">
          The data plane accepts CSVs directly. Drop a file and re-deploy — the seed
          loader picks it up idempotently.
        </p>
        <pre className="text-[10px] bg-black/40 p-2 rounded overflow-x-auto font-mono text-dim">
{dropCsvCommand}
        </pre>
      </details>
    </div>
  );
}
