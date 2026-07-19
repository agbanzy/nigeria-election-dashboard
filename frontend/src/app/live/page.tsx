"use client";

/**
 * Live page — countdown, full sync coverage matrix, queue stats, scrape log.
 */

import AnimatedCounter from "@/components/shared/AnimatedCounter";
import AnimatedShareBar from "@/components/shared/AnimatedShareBar";
import ElectionCountdown from "@/components/shared/ElectionCountdown";
import MethodologyDisclosure from "@/components/shared/MethodologyDisclosure";
import { useApiData } from "@/hooks/useApiData";

interface SyncStatus {
  queue: {
    total: number;
    complete: number;
    pending_structure: number;
    pending_stats: number;
    pending_total: number;
  };
  by_priority: { priority: number; total: number; complete: number }[];
  cache: { rows: number; last_fetched_at: string | null };
}

interface Coverage {
  geography: {
    states_total: number;
    states_with_data: number;
    states_pct: number;
    lgas_total: number;
    wards_total: number;
    polling_units_total: number;
  };
  elections: {
    total: number;
    headers_synced: number;
    structure_synced: number;
    stats_synced: number;
    with_votes: number;
    with_pu_votes: number;
    with_candidates: number;
    complete: number;
    headers_pct: number;
    structure_pct: number;
    stats_pct: number;
    votes_pct: number;
    pu_votes_pct: number;
    candidates_pct: number;
    complete_pct: number;
  };
  candidates: { total: number };
  cache: { rows: number; ingestion_sources: number };
  per_cycle: { cycle: number; elections: number; with_data: number; pct: number }[];
  per_type: { type: string; label: string; elections: number; with_data: number; pct: number }[];
}

interface TimelineRow {
  log_id: number;
  phase: string | null;
  state_id: number | null;
  election_id: number | null;
  status: string;
  message: string | null;
  created_at: string | null;
}

const PRIORITY_LABEL: Record<number, string> = {
  1: "Live",
  2: "Pre-flight",
  3: "Recent",
  5: "Historical",
  9: "Ignore",
};

export default function LivePage() {
  const { data: sync } = useApiData<SyncStatus>("/api/sync/status", 30_000);
  const { data: cov } = useApiData<Coverage>("/api/sync/coverage", 60_000);
  const { data: timeline } = useApiData<TimelineRow[]>(
    "/api/analysis/timeline?limit=30",
    30_000,
  );

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-extrabold text-primary">Live · Sync</h1>
        <p className="text-sm text-dim">
          Real-time scraper status + data coverage matrix. Toggle{" "}
          <code className="text-accent-green">SCRAPER_BURST_FACTOR</code> in the DO console
          (1.0 default → 5.0 for full sync) to drain the queue faster.
        </p>
      </header>

      <ElectionCountdown />

      {/* High-level coverage tiles */}
      {cov && (
        <section>
          <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
            Data coverage
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <CoverageTile
              label="States with data"
              value={cov.geography.states_with_data}
              of={cov.geography.states_total}
              pct={cov.geography.states_pct}
            />
            <CoverageTile
              label="Elections w/ votes"
              value={cov.elections.with_votes}
              of={cov.elections.total}
              pct={cov.elections.votes_pct}
            />
            <CoverageTile
              label="Elections w/ candidates"
              value={cov.elections.with_candidates}
              of={cov.elections.total}
              pct={cov.elections.candidates_pct}
            />
            <CoverageTile
              label="Structure synced"
              value={cov.elections.structure_synced}
              of={cov.elections.total}
              pct={cov.elections.structure_pct}
            />
          </div>
        </section>
      )}

      {cov && (
        <section className="rounded-lg border border-dashboard-border bg-dashboard-card p-4">
          <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-3">
            Sync pipeline · stage progress
          </h2>
          <div className="space-y-2">
            <AnimatedShareBar
              share={cov.elections.headers_pct}
              color="#3b82f6"
              label={`Headers synced (${cov.elections.headers_synced}/${cov.elections.total})`}
              delayMs={0}
            />
            <AnimatedShareBar
              share={cov.elections.structure_pct}
              color="#10b981"
              label={`Structure (LGA/ward) synced (${cov.elections.structure_synced}/${cov.elections.total})`}
              delayMs={80}
            />
            <AnimatedShareBar
              share={cov.elections.stats_pct}
              color="#a78bfa"
              label={`Stats synced (${cov.elections.stats_synced}/${cov.elections.total})`}
              delayMs={160}
            />
            <AnimatedShareBar
              share={cov.elections.votes_pct}
              color="#fbbf24"
              label={`Vote tallies present (${cov.elections.with_votes}/${cov.elections.total})`}
              delayMs={240}
            />
            <AnimatedShareBar
              share={cov.elections.pu_votes_pct}
              color="#f59e0b"
              label={`PU-level votes (${cov.elections.with_pu_votes}/${cov.elections.total})`}
              delayMs={320}
            />
            <AnimatedShareBar
              share={cov.elections.complete_pct}
              color="#06b6d4"
              label={`Fully sync_complete (${cov.elections.complete}/${cov.elections.total})`}
              delayMs={400}
            />
          </div>
        </section>
      )}

      {cov && (
        <section>
          <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
            Coverage by cycle
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
            {cov.per_cycle.map((c) => (
              <div
                key={c.cycle}
                className="rounded border border-dashboard-border bg-dashboard-card p-3"
              >
                <div className="text-base font-extrabold text-primary">{c.cycle}</div>
                <div className="text-[10px] text-dim">{c.elections} elections</div>
                <div className="text-xs font-mono mt-1">
                  <span className="text-accent-green font-bold">
                    {(c.pct * 100).toFixed(0)}%
                  </span>
                  <span className="text-dim"> with vote data</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {cov && (
        <section>
          <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
            Coverage by election type
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {cov.per_type.map((t) => (
              <div
                key={t.type}
                className="rounded border border-dashboard-border bg-dashboard-card p-3"
              >
                <div className="flex items-baseline justify-between mb-1">
                  <span className="font-bold text-primary text-sm">{t.label}</span>
                  <span className="font-mono text-xs text-dim">
                    {t.with_data}/{t.elections}
                  </span>
                </div>
                <AnimatedShareBar
                  share={t.pct}
                  color={t.pct > 0 ? "#10b981" : "#1f2538"}
                  label=""
                />
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Queue + cache */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {sync && (
          <div className="rounded border border-dashboard-border bg-dashboard-card p-4">
            <div className="text-[11px] uppercase tracking-wider text-dim mb-2">
              IReV sync queue
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <Stat label="Total" value={sync.queue.total} />
              <Stat label="Complete" value={sync.queue.complete} accent="green" />
              <Stat label="Pending structure" value={sync.queue.pending_structure} accent="orange" />
              <Stat label="Pending stats" value={sync.queue.pending_stats} accent="orange" />
            </div>
          </div>
        )}
        {cov && (
          <div className="rounded border border-dashboard-border bg-dashboard-card p-4">
            <div className="text-[11px] uppercase tracking-wider text-dim mb-2">
              Geography + cache
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <Stat label="LGAs" value={cov.geography.lgas_total} />
              <Stat label="Wards" value={cov.geography.wards_total} />
              <Stat label="Polling units" value={cov.geography.polling_units_total} />
              <Stat label="API rows cached" value={cov.cache.rows} accent="cyan" />
            </div>
            <div className="text-[10px] text-dim mt-2">
              {cov.cache.ingestion_sources} ingestion sources · {cov.candidates.total} candidates
            </div>
          </div>
        )}
      </section>

      {sync && (
        <section>
          <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
            By priority
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
            {sync.by_priority.map((p) => (
              <div
                key={p.priority}
                className="rounded border border-dashboard-border bg-dashboard-card p-2 text-xs"
              >
                <div className="text-dim">{PRIORITY_LABEL[p.priority] || `P${p.priority}`}</div>
                <div className="font-mono font-bold text-primary">
                  {p.complete}/{p.total}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
          Recent scrape log
        </h2>
        {(!timeline || timeline.length === 0) && (
          <div className="text-sm text-dim italic">Daemon hasn&apos;t logged anything yet.</div>
        )}
        <div className="rounded border border-dashboard-border overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-black/20 text-dim">
              <tr>
                <th className="text-left py-2 px-3">When</th>
                <th className="text-left py-2 px-3">Phase</th>
                <th className="text-left py-2 px-3">State</th>
                <th className="text-left py-2 px-3">Status</th>
                <th className="text-left py-2 px-3">Message</th>
              </tr>
            </thead>
            <tbody>
              {(timeline || []).map((r) => (
                <tr key={r.log_id} className="border-t border-dashboard-border/40">
                  <td className="py-1.5 px-3 font-mono">{r.created_at?.slice(11, 19)}</td>
                  <td className="py-1.5 px-3">{r.phase || "—"}</td>
                  <td className="py-1.5 px-3 text-dim">{r.state_id ?? "—"}</td>
                  <td
                    className={`py-1.5 px-3 ${
                      r.status === "ok" ? "text-accent-green" : "text-accent-red"
                    }`}
                  >
                    {r.status}
                  </td>
                  <td className="py-1.5 px-3 text-dim">{r.message || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <MethodologyDisclosure />
    </div>
  );
}

function CoverageTile({
  label,
  value,
  of,
  pct,
}: {
  label: string;
  value: number;
  of: number;
  pct: number;
}) {
  const color =
    pct > 0.7 ? "text-accent-green" : pct > 0.3 ? "text-accent-orange" : "text-accent-red";
  return (
    <div className="rounded border border-dashboard-border bg-dashboard-card p-3">
      <div className="text-[10px] uppercase tracking-wider text-dim">{label}</div>
      <div className="text-2xl font-extrabold text-primary font-mono mt-1">
        <AnimatedCounter value={value} />
        <span className="text-sm text-dim font-normal"> / {of.toLocaleString()}</span>
      </div>
      <div className={`text-xs font-mono mt-1 ${color}`}>{(pct * 100).toFixed(1)}%</div>
    </div>
  );
}

function Stat({
  label,
  value,
  accent = "blue",
}: {
  label: string;
  value: number;
  accent?: "green" | "orange" | "blue" | "red" | "cyan";
}) {
  const cls =
    accent === "green"
      ? "text-accent-green"
      : accent === "orange"
      ? "text-accent-orange"
      : accent === "red"
      ? "text-accent-red"
      : accent === "cyan"
      ? "text-accent-cyan"
      : "text-accent-blue";
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-dim">{label}</div>
      <div className={`text-xl font-extrabold font-mono ${cls}`}>
        <AnimatedCounter value={value} />
      </div>
    </div>
  );
}
