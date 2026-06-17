"use client";

import { useCallback, useEffect, useState } from "react";
import { signOut, useSession } from "next-auth/react";
import {
  ArrowsPointingInIcon,
  ArrowsPointingOutIcon,
  ArrowRightOnRectangleIcon,
  MoonIcon,
  SpeakerWaveIcon,
  SpeakerXMarkIcon,
  SunIcon,
} from "@heroicons/react/24/outline";

import StateSelector from "@/components/shared/StateSelector";
import CycleSelector from "@/components/shared/CycleSelector";
import ElectionTypeSelector from "@/components/shared/ElectionTypeSelector";
import { useDashboard } from "@/context/DashboardContext";
import { useFilters } from "@/context/FilterContext";
import { useTheme } from "@/context/ThemeContext";
import { useApiData } from "@/hooks/useApiData";
import { useLiveClock } from "@/hooks/useLiveClock";
import { BRAND_NAME, BRAND_TAGLINE, compose } from "@/lib/branding";
import type { StateRow } from "@/lib/api";
import { ELECTION_LABELS, type ElectionType } from "@/lib/electionTypeConfig";
import { cn } from "@/lib/utils";

interface CalendarHint {
  status: "scheduled" | "live" | "completed" | "cancelled";
}

export default function Header() {
  const { data: session } = useSession();
  const { data: states } = useApiData<StateRow[]>("/api/states", 5 * 60_000);
  const { data: nextEvent } = useApiData<CalendarHint | null>("/api/calendar/next", 60_000);
  const { time, date } = useLiveClock();
  const { theme, toggleTheme } = useTheme();
  const filters = useFilters();
  const {
    isFullscreen,
    isMuted,
    toggleFullscreen,
    toggleMute,
    lastDataUpdate,
  } = useDashboard();

  const state = filters.state ? states?.find((s) => s.code === filters.state) || null : null;
  const branding = compose({
    state: state ? { code: state.code, name: state.name } : null,
    cycle: filters.cycle,
    electionType: filters.electionType,
    electionTypeLabel: filters.electionType
      ? ELECTION_LABELS[filters.electionType as ElectionType]
      : null,
  });

  const isLive = nextEvent?.status === "live";

  const [, setTick] = useState(0);
  useEffect(() => {
    if (!lastDataUpdate) return;
    const iv = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(iv);
  }, [lastDataUpdate]);

  const freshness = lastDataUpdate
    ? `${Math.floor((Date.now() - lastDataUpdate) / 1000)}s ago`
    : null;

  return (
    <header className="sticky top-0 z-30 border-b-2 border-nigeria-green bg-gradient-to-r from-[var(--header-from)] via-[var(--header-via)] to-[var(--header-to)]">
      <div className="flex items-center justify-between px-5 py-3 lg:px-7 gap-3">
        <div className={cn(isFullscreen ? "pl-0" : "lg:pl-0 pl-10")}>
          <h1
            className={cn(
              "font-extrabold text-white tracking-tight",
              isFullscreen ? "text-xl" : "text-lg",
            )}
          >
            {branding.title || BRAND_NAME}
          </h1>
          <p className="text-[11px] text-white/50 mt-0.5">
            {branding.subtitle || BRAND_TAGLINE} &bull; {date}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 justify-end">
          <StateSelector />
          <CycleSelector />
          <ElectionTypeSelector />

          <div className="hidden sm:flex items-center gap-1.5 bg-white/5 px-3 py-1.5 rounded-lg border border-white/10">
            <span className="text-[13px] font-mono font-bold text-white tabular-nums">{time}</span>
          </div>

          {isLive && (
            <div className="flex items-center gap-1.5 bg-red-500/15 px-3 py-1 rounded-full border border-red-500/30 animate-glow-pulse">
              <span className="w-1.5 h-1.5 bg-red-500 rounded-full animate-pulse" />
              <span className="text-[11px] font-bold text-red-500">LIVE</span>
            </div>
          )}

          <button
            onClick={toggleTheme}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            className="p-1.5 rounded-lg text-white/50 hover:text-white hover:bg-white/10 transition-all"
          >
            {theme === "dark" ? <SunIcon className="w-4 h-4" /> : <MoonIcon className="w-4 h-4" />}
          </button>

          <button
            onClick={toggleMute}
            aria-label={isMuted ? "Unmute alerts" : "Mute alerts"}
            className="p-1.5 rounded-lg text-white/50 hover:text-white hover:bg-white/10 transition-all"
          >
            {isMuted ? (
              <SpeakerXMarkIcon className="w-4 h-4" />
            ) : (
              <SpeakerWaveIcon className="w-4 h-4" />
            )}
          </button>

          <button
            onClick={toggleFullscreen}
            aria-label={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
            className="p-1.5 rounded-lg text-white/50 hover:text-white hover:bg-white/10 transition-all"
          >
            {isFullscreen ? (
              <ArrowsPointingInIcon className="w-4 h-4" />
            ) : (
              <ArrowsPointingOutIcon className="w-4 h-4" />
            )}
          </button>

          {session?.user && (
            <div className="hidden sm:flex items-center gap-2 ml-1 pl-3 border-l border-white/10">
              <span className="text-[12px] text-white/50 max-w-[120px] truncate">
                {session.user.name || session.user.email}
              </span>
              <button
                onClick={() => signOut({ callbackUrl: "/" })}
                aria-label="Sign out"
                title="Sign out"
                className="p-1.5 rounded-lg text-white/40 hover:text-red-400 hover:bg-red-500/10 transition-all"
              >
                <ArrowRightOnRectangleIcon className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between px-5 lg:px-7 py-1.5 bg-black/20 border-t border-white/10 text-[11px] text-white/60">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-green" />
            <span>Connected · {BRAND_NAME}</span>
          </div>
          {freshness && (
            <span className="text-accent-green/80 font-semibold">Updated {freshness}</span>
          )}
        </div>
        <span className="tabular-nums">
          {filters.state ? `Scope: ${filters.state}` : "Scope: National"}
          {filters.cycle ? ` · ${filters.cycle}` : ""}
        </span>
      </div>
    </header>
  );
}
