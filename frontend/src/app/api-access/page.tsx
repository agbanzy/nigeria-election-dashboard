"use client";

/**
 * Public API-access page. The dashboard and its data are free for everyone;
 * programmatic API access is also free but by application — apply here, an
 * admin approves, and the key appears under "Check your application".
 */

import { useState } from "react";
import Link from "next/link";

import { BRAND_NAME } from "@/lib/branding";

const DOCS_URL =
  "https://github.com/agbanzy/nigeria-election-dashboard/blob/main/docs/API.md";

type ApplyState =
  | { phase: "idle" }
  | { phase: "busy" }
  | { phase: "done"; ref: string }
  | { phase: "error"; message: string };

type StatusState =
  | { phase: "idle" }
  | { phase: "busy" }
  | { phase: "done"; status: string; apiKey?: string }
  | { phase: "error"; message: string };

const inputCls =
  "w-full rounded-lg bg-white/[0.04] border border-white/10 px-3 py-2 text-[13px] text-white placeholder-white/25 focus:outline-none focus:border-[#00a651]/60 transition-colors";

export default function ApiAccessPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [useCase, setUseCase] = useState("");
  const [apply, setApply] = useState<ApplyState>({ phase: "idle" });

  const [ref, setRef] = useState("");
  const [status, setStatus] = useState<StatusState>({ phase: "idle" });

  async function submitApplication(e: React.FormEvent) {
    e.preventDefault();
    setApply({ phase: "busy" });
    try {
      const res = await fetch("/api/developer/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, use_case: useCase }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
      setApply({ phase: "done", ref: json.application_ref });
    } catch (err) {
      setApply({ phase: "error", message: err instanceof Error ? err.message : "failed" });
    }
  }

  async function checkStatus(e: React.FormEvent) {
    e.preventDefault();
    setStatus({ phase: "busy" });
    try {
      const res = await fetch("/api/developer/status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ application_ref: ref.trim() }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
      setStatus({ phase: "done", status: json.status, apiKey: json.api_key });
    } catch (err) {
      setStatus({ phase: "error", message: err instanceof Error ? err.message : "failed" });
    }
  }

  return (
    <div className="min-h-screen bg-[#070d1a] text-white">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
        <Link href="/" className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#00a651]" />
            <span className="w-5 h-0.5 bg-[#00a651]/60" />
            <span className="w-1.5 h-1.5 rounded-full bg-[#008751]" />
          </span>
          <span className="text-sm font-extrabold tracking-tight">{BRAND_NAME}</span>
        </Link>
        <Link
          href="/dashboard"
          className="px-4 py-2 rounded-lg bg-[#00a651] hover:bg-[#008741] text-[13px] font-bold transition-colors"
        >
          Open dashboard
        </Link>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-12">
        <h1 className="text-3xl font-extrabold tracking-tight">Free API access</h1>
        <p className="text-[14px] text-white/50 mt-3 leading-relaxed">
          The dashboard and every number on it are free for everyone, no account
          needed. Programmatic API access is <span className="text-[#00a651] font-semibold">also free</span> —
          we just ask you to apply so we know who is building on the data and can
          reach you if something changes. Approved keys go in an{" "}
          <code className="text-white/70 bg-white/[0.06] px-1.5 py-0.5 rounded text-[12px]">X-API-Key</code>{" "}
          header. Full endpoint reference:{" "}
          <a href={DOCS_URL} target="_blank" rel="noopener noreferrer" className="text-[#00a651] hover:underline">
            API documentation
          </a>
          .
        </p>

        <div className="grid sm:grid-cols-2 gap-6 mt-10">
          {/* Apply */}
          <section className="rounded-2xl border border-white/[0.08] bg-[#0c1226] p-6">
            <h2 className="text-[15px] font-bold">Apply for a key</h2>
            {apply.phase === "done" ? (
              <div className="mt-4 text-[13px] space-y-3">
                <p className="text-[#00a651] font-semibold">Application received.</p>
                <p className="text-white/60">
                  Save your application reference — it is the <em>only</em> way to
                  retrieve your key once approved:
                </p>
                <code className="block break-all bg-white/[0.06] border border-white/10 rounded-lg p-3 text-[12px] text-white/90">
                  {apply.ref}
                </code>
              </div>
            ) : (
              <form onSubmit={submitApplication} className="mt-4 space-y-3">
                <input className={inputCls} placeholder="Your name or project" value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} />
                <input className={inputCls} type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required maxLength={200} />
                <textarea className={inputCls} placeholder="What are you building? (research, newsroom graphics, an app…)" value={useCase} onChange={(e) => setUseCase(e.target.value)} required rows={3} maxLength={500} />
                <button
                  type="submit"
                  disabled={apply.phase === "busy"}
                  className="w-full rounded-lg bg-[#00a651] hover:bg-[#008741] disabled:opacity-50 py-2 text-[13px] font-bold transition-colors"
                >
                  {apply.phase === "busy" ? "Submitting…" : "Apply — it's free"}
                </button>
                {apply.phase === "error" && (
                  <p className="text-[12px] text-red-400">{apply.message}</p>
                )}
              </form>
            )}
          </section>

          {/* Status */}
          <section className="rounded-2xl border border-white/[0.08] bg-[#0c1226] p-6">
            <h2 className="text-[15px] font-bold">Check your application</h2>
            <form onSubmit={checkStatus} className="mt-4 space-y-3">
              <input className={inputCls} placeholder="Application reference" value={ref} onChange={(e) => setRef(e.target.value)} required />
              <button
                type="submit"
                disabled={status.phase === "busy"}
                className="w-full rounded-lg bg-white/[0.08] hover:bg-white/[0.14] disabled:opacity-50 py-2 text-[13px] font-bold transition-colors"
              >
                {status.phase === "busy" ? "Checking…" : "Check status"}
              </button>
            </form>
            {status.phase === "done" && (
              <div className="mt-4 text-[13px] space-y-2">
                <p>
                  Status:{" "}
                  <span
                    className={
                      status.status === "approved"
                        ? "text-[#00a651] font-bold"
                        : status.status === "pending"
                          ? "text-yellow-400 font-bold"
                          : "text-red-400 font-bold"
                    }
                  >
                    {status.status}
                  </span>
                </p>
                {status.apiKey && (
                  <>
                    <p className="text-white/60">Your API key (send as X-API-Key):</p>
                    <code className="block break-all bg-white/[0.06] border border-white/10 rounded-lg p-3 text-[12px] text-white/90">
                      {status.apiKey}
                    </code>
                  </>
                )}
              </div>
            )}
            {status.phase === "error" && (
              <p className="mt-3 text-[12px] text-red-400">{status.message}</p>
            )}
          </section>
        </div>

        <p className="text-[12px] text-white/30 mt-10">
          Example once approved:{" "}
          <code className="bg-white/[0.06] px-1.5 py-0.5 rounded">
            curl -H &quot;X-API-Key: ned_…&quot; https://elections.innoedgetech.com/api/states
          </code>
        </p>
      </main>
    </div>
  );
}
