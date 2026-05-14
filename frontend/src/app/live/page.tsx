"use client";

import ElectionCountdown from "@/components/shared/ElectionCountdown";

export default function LivePage() {
  return (
    <div className="p-5 lg:p-7 max-w-4xl mx-auto space-y-6">
      <header>
        <h1 className="text-2xl font-extrabold text-primary">Live</h1>
        <p className="text-sm text-dim">
          When an election is underway this page becomes the live polling-unit feed.
        </p>
      </header>
      <ElectionCountdown />
      <div className="text-sm text-dim italic">
        No live elections currently. Backend scraper is idle (24h check-in cycle).
      </div>
    </div>
  );
}
