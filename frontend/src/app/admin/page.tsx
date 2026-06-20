"use client";

/**
 * Admin · Results ingestion.
 *
 * Because INEC's 2026 IReV publishes only scanned EC8A form images + upload
 * counts (no transcribed votes), admins get vote tallies into the dashboard
 * here: pick a live election, then enter party votes manually, OCR a scanned
 * form to pre-fill, or paste a transcribed feed. Submissions become
 * ElectionResult rows, so the choropleth + comparison update immediately.
 *
 * Admin-only: gated by middleware (auth) + the /admin-api proxy (role check).
 */

import { useEffect, useMemo, useState } from "react";
import { useSession } from "next-auth/react";

import { useApiData } from "@/hooks/useApiData";

interface LiveElection {
  election_id: number;
  cycle: number;
  type: string;
  type_label: string;
  state_id: number | null;
  state_code: string | null;
  state_name: string;
  irev_election_id: string | null;
  priority: number;
  expected_pus: number;
  uploaded_pus: number;
  upload_pct: number;
  results_synced_at: string | null;
  result_rows: number;
}

interface PartyRow {
  party_code: string;
  votes: string;
}

const SEED_PARTIES = ["APC", "PDP", "LP", "NNPP", "APGA", "ADC", "SDP", "YPP"];
const PRIORITY_LABEL: Record<number, string> = { 1: "LIVE", 2: "Pre-flight", 3: "Recent" };

export default function AdminPage() {
  const { data: session } = useSession();
  const isAdmin = (session?.user as { role?: string } | undefined)?.role === "admin";

  const { data, error, mutate } = useApiData<{ elections: LiveElection[] }>(
    isAdmin ? "/admin-api/live-elections" : null,
    30_000,
  );
  const elections = data?.elections || [];

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = useMemo(
    () => elections.find((e) => e.election_id === selectedId) || null,
    [elections, selectedId],
  );

  const [rows, setRows] = useState<PartyRow[]>(
    SEED_PARTIES.map((p) => ({ party_code: p, votes: "" })),
  );
  const [accredited, setAccredited] = useState("");
  const [registered, setRegistered] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [importText, setImportText] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    if (selectedId === null && elections.length) setSelectedId(elections[0].election_id);
  }, [elections, selectedId]);

  if (!isAdmin) {
    return (
      <div className="rounded-lg border border-accent-red/30 bg-accent-red/10 p-6 text-sm text-accent-red">
        Admin access required. Sign in with an admin account.
      </div>
    );
  }

  function setRow(i: number, patch: Partial<PartyRow>) {
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  }
  function addRow() {
    setRows((rs) => [...rs, { party_code: "", votes: "" }]);
  }
  function removeRow(i: number) {
    setRows((rs) => rs.filter((_, j) => j !== i));
  }

  async function post(path: string, body: unknown) {
    const res = await fetch(`/admin-api/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
    return json;
  }

  async function submitManual() {
    if (!selected) return;
    setBusy("manual");
    setMsg(null);
    try {
      const results = rows
        .filter((r) => r.party_code.trim() && r.votes.trim())
        .map((r) => ({ party_code: r.party_code.trim().toUpperCase(), votes: Number(r.votes) }));
      const out = await post("results", {
        election_id: selected.election_id,
        scope: "state",
        accredited: accredited ? Number(accredited) : undefined,
        registered: registered ? Number(registered) : undefined,
        results,
      });
      setMsg({ kind: "ok", text: `Saved ${out.inserted} party tallies for ${selected.state_name}.` });
      mutate();
    } catch (e) {
      setMsg({ kind: "err", text: (e as Error).message });
    } finally {
      setBusy(null);
    }
  }

  async function runOcr() {
    if (!selected || !imageUrl.trim()) return;
    setBusy("ocr");
    setMsg(null);
    try {
      const out = await post("ocr", { image_url: imageUrl.trim(), cycle: selected.cycle });
      const votes = out.party_votes || {};
      const keys = Object.keys(votes);
      if (!keys.length) {
        setMsg({ kind: "err", text: out.message || "OCR found no readable party votes." });
      } else {
        setRows((rs) => {
          const next = [...rs];
          for (const [code, v] of Object.entries(votes)) {
            const i = next.findIndex((r) => r.party_code.toUpperCase() === code.toUpperCase());
            if (i >= 0) next[i] = { ...next[i], votes: String(v) };
            else next.push({ party_code: code, votes: String(v) });
          }
          return next;
        });
        if (out.accredited) setAccredited(String(out.accredited));
        if (out.registered) setRegistered(String(out.registered));
        setMsg({
          kind: "ok",
          text: `OCR pre-filled ${keys.length} parties (confidence ${(out.confidence * 100).toFixed(0)}%). Review before saving.`,
        });
      }
    } catch (e) {
      setMsg({ kind: "err", text: (e as Error).message });
    } finally {
      setBusy(null);
    }
  }

  async function runImport() {
    if (!selected || !importText.trim()) return;
    setBusy("import");
    setMsg(null);
    try {
      const rowsParsed = importText
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean)
        .map((l) => {
          const [code, votes] = l.split(/[,\t]/).map((s) => s.trim());
          return { party_code: (code || "").toUpperCase(), votes: Number(votes) };
        })
        .filter((r) => r.party_code && Number.isFinite(r.votes));
      const out = await post("import", {
        election_id: selected.election_id,
        source_label: "pasted feed",
        rows: rowsParsed,
      });
      setMsg({ kind: "ok", text: `Imported ${out.inserted} rows.` });
      mutate();
    } catch (e) {
      setMsg({ kind: "err", text: (e as Error).message });
    } finally {
      setBusy(null);
    }
  }

  const irevUrl = selected?.irev_election_id
    ? `https://www.inecelectionresults.ng/elections/${selected.irev_election_id}`
    : null;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-extrabold text-primary">Admin · Results ingestion</h1>
        <p className="text-sm text-dim max-w-2xl">
          INEC&apos;s 2026 IReV publishes scanned EC8A form images + upload counts, not
          transcribed votes. Enter tallies here — manually, OCR-assisted, or pasted from a
          feed. Saved tallies populate the map &amp; comparison instantly.
        </p>
      </header>

      {error && (
        <div className="rounded border border-accent-red/30 bg-accent-red/10 px-4 py-2 text-sm text-accent-red">
          Couldn&apos;t load elections (admin proxy). {String(error)}
        </div>
      )}

      {/* Live election picker with upload progress */}
      <section>
        <h2 className="text-sm font-bold uppercase tracking-wider text-dim mb-2">
          Live &amp; recent elections · IReV upload progress
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
          {elections.map((e) => {
            const active = e.election_id === selectedId;
            return (
              <button
                key={e.election_id}
                onClick={() => setSelectedId(e.election_id)}
                className={`text-left rounded-lg border p-3 transition-all ${
                  active
                    ? "border-accent-green bg-accent-green/10"
                    : "border-dashboard-border bg-dashboard-card hover:border-accent-green/40"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-bold text-primary text-sm">
                    {e.state_name} · {e.type_label}
                  </span>
                  {e.priority === 1 && (
                    <span className="text-[9px] font-bold text-accent-red bg-accent-red/15 px-1.5 py-0.5 rounded-full">
                      LIVE
                    </span>
                  )}
                </div>
                <div className="text-[10px] text-dim mt-0.5">
                  {e.cycle} · {PRIORITY_LABEL[e.priority] || `P${e.priority}`} ·{" "}
                  {e.result_rows} result rows
                </div>
                <div className="mt-2 h-1.5 rounded-full bg-black/30 overflow-hidden">
                  <div
                    className="h-full bg-accent-green rounded-full transition-all"
                    style={{ width: `${Math.min(100, e.upload_pct * 100)}%` }}
                  />
                </div>
                <div className="text-[10px] text-dim mt-1 font-mono">
                  {e.uploaded_pus.toLocaleString()} / {e.expected_pus.toLocaleString()} forms (
                  {(e.upload_pct * 100).toFixed(1)}%)
                </div>
              </button>
            );
          })}
          {elections.length === 0 && !error && (
            <div className="text-sm text-dim italic">No live or recent elections right now.</div>
          )}
        </div>
      </section>

      {selected && (
        <section className="rounded-lg border border-dashboard-border bg-dashboard-card p-4 space-y-4">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <h2 className="text-base font-bold text-primary">
              {selected.state_name} · {selected.type_label} · {selected.cycle}
            </h2>
            {irevUrl && (
              <a
                href={irevUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-accent-green underline"
              >
                View scanned forms on IReV →
              </a>
            )}
          </div>

          {msg && (
            <div
              className={`rounded px-3 py-2 text-[13px] ${
                msg.kind === "ok"
                  ? "bg-accent-green/10 border border-accent-green/30 text-accent-green"
                  : "bg-accent-red/10 border border-accent-red/30 text-accent-red"
              }`}
            >
              {msg.text}
            </div>
          )}

          {/* OCR-assist */}
          <div className="rounded border border-dashboard-border/60 p-3 space-y-2">
            <div className="text-[11px] uppercase tracking-wider text-dim">OCR-assist (best-effort)</div>
            <div className="flex gap-2 flex-wrap">
              <input
                value={imageUrl}
                onChange={(e) => setImageUrl(e.target.value)}
                placeholder="Paste a scanned EC8A image URL…"
                className="flex-1 min-w-[240px] bg-black/20 border border-dashboard-border rounded px-3 py-1.5 text-sm"
              />
              <button
                onClick={runOcr}
                disabled={busy !== null || !imageUrl.trim()}
                className="px-3 py-1.5 rounded bg-accent-blue/20 border border-accent-blue/40 text-accent-blue text-sm font-semibold disabled:opacity-50"
              >
                {busy === "ocr" ? "Reading…" : "Suggest votes"}
              </button>
            </div>
            <p className="text-[10px] text-dim">
              Handwritten forms OCR imperfectly — always review the numbers before saving.
            </p>
          </div>

          {/* Manual entry */}
          <div className="space-y-2">
            <div className="text-[11px] uppercase tracking-wider text-dim">
              Party tallies (state total)
            </div>
            <div className="space-y-1.5">
              {rows.map((r, i) => (
                <div key={i} className="flex gap-2 items-center">
                  <input
                    value={r.party_code}
                    onChange={(e) => setRow(i, { party_code: e.target.value })}
                    placeholder="PARTY"
                    className="w-24 bg-black/20 border border-dashboard-border rounded px-2 py-1.5 text-sm font-mono uppercase"
                  />
                  <input
                    value={r.votes}
                    onChange={(e) => setRow(i, { votes: e.target.value.replace(/[^0-9]/g, "") })}
                    placeholder="votes"
                    inputMode="numeric"
                    className="flex-1 bg-black/20 border border-dashboard-border rounded px-3 py-1.5 text-sm font-mono"
                  />
                  <button
                    onClick={() => removeRow(i)}
                    className="text-dim hover:text-accent-red px-2 text-lg leading-none"
                    aria-label="Remove row"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
            <button onClick={addRow} className="text-xs text-accent-green">
              + add party
            </button>

            <div className="flex gap-2 flex-wrap pt-2">
              <input
                value={accredited}
                onChange={(e) => setAccredited(e.target.value.replace(/[^0-9]/g, ""))}
                placeholder="Accredited (optional)"
                inputMode="numeric"
                className="w-44 bg-black/20 border border-dashboard-border rounded px-3 py-1.5 text-sm font-mono"
              />
              <input
                value={registered}
                onChange={(e) => setRegistered(e.target.value.replace(/[^0-9]/g, ""))}
                placeholder="Registered (optional)"
                inputMode="numeric"
                className="w-44 bg-black/20 border border-dashboard-border rounded px-3 py-1.5 text-sm font-mono"
              />
            </div>

            <button
              onClick={submitManual}
              disabled={busy !== null}
              className="mt-1 px-4 py-2 rounded bg-accent-green text-white text-sm font-bold disabled:opacity-50"
            >
              {busy === "manual" ? "Saving…" : "Save tallies"}
            </button>
          </div>

          {/* Bulk import */}
          <details className="rounded border border-dashboard-border/60 p-3">
            <summary className="text-[11px] uppercase tracking-wider text-dim cursor-pointer">
              Paste a transcribed feed (CODE,VOTES per line)
            </summary>
            <textarea
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              rows={5}
              placeholder={"APC,123456\nPDP,98765\nLP,45000"}
              className="w-full mt-2 bg-black/20 border border-dashboard-border rounded px-3 py-2 text-sm font-mono"
            />
            <button
              onClick={runImport}
              disabled={busy !== null || !importText.trim()}
              className="mt-2 px-3 py-1.5 rounded bg-accent-purple/20 border border-accent-purple/40 text-accent-purple text-sm font-semibold disabled:opacity-50"
            >
              {busy === "import" ? "Importing…" : "Import rows"}
            </button>
          </details>
        </section>
      )}
    </div>
  );
}
