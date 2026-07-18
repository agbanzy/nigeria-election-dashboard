"use client";

/**
 * Admin panel: API access applications (apply-and-approve free keys).
 * Reads and decides through the /admin-api proxy, which verifies the admin
 * session and injects X-Admin-Token server-side.
 */

import { useState } from "react";

import { useApiData } from "@/hooks/useApiData";

interface ApiClientRow {
  client_id: number;
  name: string;
  email: string;
  use_case: string;
  status: string;
  api_key: string | null;
  created_at: string | null;
  last_used_at: string | null;
  request_count: number;
}

const STATUS_CLS: Record<string, string> = {
  pending: "text-yellow-400",
  approved: "text-[#00a651]",
  rejected: "text-red-400",
  revoked: "text-red-400",
};

export default function ApiClientsPanel() {
  const { data, mutate } = useApiData<{ clients: ApiClientRow[] }>(
    "/admin-api/api-clients",
    60_000,
  );
  const clients = data?.clients || [];
  const [busyId, setBusyId] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function decide(id: number, action: "approve" | "reject" | "revoke") {
    setBusyId(id);
    setErr(null);
    try {
      const res = await fetch(`/admin-api/api-clients/${id}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
      mutate();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "failed");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="rounded-lg border border-dashboard-border bg-dashboard-card p-4">
      <h2 className="text-sm font-bold">API access applications</h2>
      <p className="text-xs text-dim mt-1">
        Free keys, by approval. Applicants retrieve their key on /api-access
        with their application reference once approved.
      </p>
      {err && <p className="text-xs text-red-400 mt-2">{err}</p>}
      {clients.length === 0 ? (
        <p className="text-xs text-dim mt-3">No applications yet.</p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-dim border-b border-dashboard-border">
                <th className="py-2 pr-3">Applicant</th>
                <th className="py-2 pr-3">Use case</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2 pr-3">Requests</th>
                <th className="py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {clients.map((c) => (
                <tr key={c.client_id} className="border-b border-dashboard-border/50 align-top">
                  <td className="py-2 pr-3">
                    <div className="font-semibold">{c.name}</div>
                    <div className="text-dim">{c.email}</div>
                  </td>
                  <td className="py-2 pr-3 max-w-[260px]">
                    <div className="text-dim">{c.use_case}</div>
                    {c.api_key && (
                      <code className="block mt-1 break-all text-[10px] text-white/50">
                        {c.api_key}
                      </code>
                    )}
                  </td>
                  <td className={`py-2 pr-3 font-bold capitalize ${STATUS_CLS[c.status] || ""}`}>
                    {c.status}
                  </td>
                  <td className="py-2 pr-3">{c.request_count}</td>
                  <td className="py-2 space-x-2 whitespace-nowrap">
                    {c.status === "pending" && (
                      <>
                        <button
                          onClick={() => decide(c.client_id, "approve")}
                          disabled={busyId === c.client_id}
                          className="px-2 py-1 rounded bg-[#00a651]/20 border border-[#00a651]/40 text-[#00a651] font-semibold disabled:opacity-50"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => decide(c.client_id, "reject")}
                          disabled={busyId === c.client_id}
                          className="px-2 py-1 rounded bg-red-500/10 border border-red-500/30 text-red-400 font-semibold disabled:opacity-50"
                        >
                          Reject
                        </button>
                      </>
                    )}
                    {c.status === "approved" && (
                      <button
                        onClick={() => decide(c.client_id, "revoke")}
                        disabled={busyId === c.client_id}
                        className="px-2 py-1 rounded bg-red-500/10 border border-red-500/30 text-red-400 font-semibold disabled:opacity-50"
                      >
                        Revoke
                      </button>
                    )}
                    {(c.status === "rejected" || c.status === "revoked") && (
                      <button
                        onClick={() => decide(c.client_id, "approve")}
                        disabled={busyId === c.client_id}
                        className="px-2 py-1 rounded bg-[#00a651]/20 border border-[#00a651]/40 text-[#00a651] font-semibold disabled:opacity-50"
                      >
                        Re-approve
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
