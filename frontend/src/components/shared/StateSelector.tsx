"use client";

import { useApiData } from "@/hooks/useApiData";
import { useFilters } from "@/context/FilterContext";
import type { StateRow } from "@/lib/api";

export default function StateSelector() {
  const { data } = useApiData<StateRow[]>("/api/states", 5 * 60_000);
  const { state, setState } = useFilters();

  return (
    <select
      aria-label="Filter by state"
      value={state || ""}
      onChange={(e) => setState(e.target.value || null)}
      className="bg-dashboard-card border border-dashboard-border text-primary rounded px-2 py-1 text-xs"
    >
      <option value="">All Nigeria</option>
      {(data || []).map((s) => (
        <option key={s.code} value={s.code}>
          {s.name}
        </option>
      ))}
    </select>
  );
}
