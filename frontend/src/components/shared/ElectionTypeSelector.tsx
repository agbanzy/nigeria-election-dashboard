"use client";

import { useFilters } from "@/context/FilterContext";
import {
  ELECTION_LABELS,
  ELECTION_TYPES,
  type ElectionType,
} from "@/lib/electionTypeConfig";

export default function ElectionTypeSelector() {
  const { electionType, setElectionType } = useFilters();
  return (
    <select
      aria-label="Filter by election type"
      value={electionType ?? ""}
      onChange={(e) => setElectionType((e.target.value as ElectionType) || null)}
      className="bg-dashboard-card border border-dashboard-border text-primary rounded px-2 py-1 text-xs"
    >
      <option value="">All types</option>
      {ELECTION_TYPES.map((t) => (
        <option key={t} value={t}>
          {ELECTION_LABELS[t]}
        </option>
      ))}
    </select>
  );
}
