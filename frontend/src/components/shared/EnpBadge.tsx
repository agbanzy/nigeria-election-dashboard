"use client";

/**
 * Effective Number of Parties — small badge with hover tooltip.
 * ENP ≈ 1.0  → one-party
 * ENP ≈ 2.0  → two-party
 * ENP > 3.5  → fragmented / multi-party
 */
export default function EnpBadge({ value }: { value: number | null | undefined }) {
  if (value == null) return null;
  const label =
    value < 1.5 ? "one-party"
    : value < 2.4 ? "two-party"
    : value < 3.5 ? "moderate"
    : "fragmented";
  const color =
    value < 1.5 ? "text-accent-red"
    : value < 2.4 ? "text-accent-orange"
    : value < 3.5 ? "text-accent-green"
    : "text-accent-purple";
  return (
    <span
      title={`Effective Number of Parties (Laakso–Taagepera). Interpretation: ${label}.`}
      className="inline-flex items-baseline gap-1.5 rounded-md bg-black/20 px-2 py-0.5 text-xs font-mono"
    >
      <span className={`font-bold ${color}`}>{value.toFixed(2)}</span>
      <span className="text-[10px] uppercase tracking-wider text-dim">ENP</span>
    </span>
  );
}
