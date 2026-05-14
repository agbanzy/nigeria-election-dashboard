"use client";

import { useFilters } from "@/context/FilterContext";

const CYCLES = [2026, 2023, 2020, 2019, 2015];

export default function CycleSelector() {
  const { cycle, setCycle } = useFilters();
  return (
    <select
      aria-label="Filter by election cycle"
      value={cycle ?? ""}
      onChange={(e) => setCycle(e.target.value ? Number(e.target.value) : null)}
      className="bg-dashboard-card border border-dashboard-border text-primary rounded px-2 py-1 text-xs"
    >
      <option value="">All cycles</option>
      {CYCLES.map((c) => (
        <option key={c} value={c}>
          {c}
        </option>
      ))}
    </select>
  );
}
