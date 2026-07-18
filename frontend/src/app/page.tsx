"use client";

/**
 * Public landing page — shows the Nigeria election choropleth map only.
 * No sidebar, no dashboard shell. The full dashboard is public; only
 * /admin requires sign-in.
 */

import dynamic from "next/dynamic";
import Link from "next/link";
import { BRAND_NAME, BRAND_TAGLINE, POWERED_BY, POWERED_BY_URL } from "@/lib/branding";

// NigeriaLeafletMap requires browser APIs — disable SSR
const NigeriaChoropleth = dynamic(
  () => import("@/components/shared/NigeriaChoropleth"),
  { ssr: false, loading: () => <div className="h-full flex items-center justify-center text-white/30 text-sm">Loading map…</div> }
);

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#070d1a] flex flex-col">
      {/* Background grid */}
      <div
        className="fixed inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage:
            "linear-gradient(rgba(16,185,129,1) 1px, transparent 1px), linear-gradient(90deg, rgba(16,185,129,1) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />

      {/* Minimal header */}
      <header className="relative z-10 flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#00a651]" />
            <span className="w-5 h-0.5 bg-[#00a651]/60" />
            <span className="w-1.5 h-1.5 rounded-full bg-[#008751]" />
          </span>
          <div>
            <h1 className="text-sm font-extrabold text-white tracking-tight leading-none">
              {BRAND_NAME}
            </h1>
            <p className="text-[10px] text-white/35 mt-0.5 hidden sm:block">{BRAND_TAGLINE}</p>
          </div>
        </div>

        <Link
          href="/dashboard"
          className="px-4 py-2 rounded-lg bg-[#00a651] hover:bg-[#008741] text-white text-[13px] font-bold transition-all duration-150 shadow-lg shadow-[#00a651]/20"
        >
          Open dashboard
        </Link>
      </header>

      {/* Hero text */}
      <div className="relative z-10 text-center pt-10 pb-4 px-4">
        <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
          Nigeria Election Results
        </h2>
        <p className="text-[13px] text-white/40 mt-2 max-w-md mx-auto">
          Pan-Nigeria, multi-cycle results, analysis and live data from INEC IReV.
          <br className="hidden sm:block" /> Free and open to everyone.
        </p>
      </div>

      {/* Map — fills the rest of the viewport */}
      <div className="relative z-10 flex-1 px-4 pb-4 min-h-[500px]">
        <div className="h-full rounded-2xl overflow-hidden border border-white/[0.08] bg-[#0c1226]" style={{ minHeight: 480 }}>
          <NigeriaChoropleth />
        </div>
      </div>

      {/* Footer */}
      <footer className="relative z-10 text-center py-4 text-[11px] text-white/20 border-t border-white/[0.05]">
        Powered by{" "}
        <a href={POWERED_BY_URL} className="text-white/35 hover:text-white/55 underline transition-colors">
          {POWERED_BY}
        </a>{" "}
        · Data source: INEC IReV ·{" "}
        <Link href="/login" className="text-white/25 hover:text-white/45 transition-colors">
          Admin
        </Link>
      </footer>
    </div>
  );
}
