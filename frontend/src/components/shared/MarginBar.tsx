"use client";

export default function MarginBar({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-dim text-xs">—</span>;
  const pct = Math.max(0, Math.min(1, value));
  const barColor =
    pct < 0.05 ? "bg-accent-red"
    : pct < 0.15 ? "bg-accent-orange"
    : "bg-accent-green";
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-mono tabular-nums">{(value * 100).toFixed(1)}%</span>
      <div className="flex-1 h-1.5 bg-black/20 rounded-full overflow-hidden min-w-[60px] max-w-[120px]">
        <div className={`h-full ${barColor}`} style={{ width: `${pct * 100}%` }} />
      </div>
    </div>
  );
}
