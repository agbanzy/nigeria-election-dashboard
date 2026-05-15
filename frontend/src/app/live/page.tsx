"use client";

/**
 * Live page — election countdown + sync status (so you can see the daemon
 * is working) + recent scrape log entries.
 */

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
  const { data: timeline } = useApiData<TimelineRow[]>(
    "/api/analysis/timeline?limit=30",
    30_000,
  );

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-extrabold text-primary">Live</h1>
        <p className="text-sm text-dim">
          Real-time scraper status. When an election is underway this page becomes the
          polling-unit feed.
        </p>
      </header>

      <ElectionCountdown />

      <section>
        <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
          Sync queue
        </h2>
        {!sync ? (
          <div className="text-sm text-dim italic">Loading…</div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatTile label="Total elections" value={sync.queue.total} />
            <StatTile label="Complete" value={sync.queue.complete} accent="green" />
            <StatTile label="Pending structure" value={sync.queue.pending_structure} accent="orange" />
            <StatTile label="Pending stats" value={sync.queue.pending_stats} accent="orange" />
          </div>
        )}
        {sync && (
          <div className="mt-3 text-xs text-dim">
            Raw API responses cached: {sync.cache.rows}
            {sync.cache.last_fetched_at && ` · last fetch ${sync.cache.last_fetched_at.slice(0, 19)}Z`}
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
          <div className="text-sm text-dim italic">Daemon hasn't logged anything yet.</div>
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
                  <td className={`py-1.5 px-3 ${r.status === "ok" ? "text-accent-green" : "text-accent-red"}`}>
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

function StatTile({
  label,
  value,
  accent = "blue",
}: {
  label: string;
  value: number;
  accent?: "green" | "orange" | "blue" | "red";
}) {
  const cls =
    accent === "green" ? "text-accent-green"
    : accent === "orange" ? "text-accent-orange"
    : accent === "red" ? "text-accent-red"
    : "text-accent-blue";
  return (
    <div className="rounded border border-dashboard-border bg-dashboard-card p-3">
      <div className="text-[10px] uppercase tracking-wider text-dim">{label}</div>
      <div className={`text-2xl font-extrabold font-mono ${cls}`}>{value.toLocaleString()}</div>
    </div>
  );
}
