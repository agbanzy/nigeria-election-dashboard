"use client";

export default function SwingArrow({ delta }: { delta: number }) {
  const sign = delta > 0 ? "+" : "";
  const arrow = delta > 0 ? "▲" : delta < 0 ? "▼" : "■";
  const color = delta > 0 ? "text-accent-green" : delta < 0 ? "text-accent-red" : "text-dim";
  return (
    <span className={`inline-flex items-baseline gap-1 font-mono text-xs ${color}`}>
      <span>{arrow}</span>
      <span className="tabular-nums">
        {sign}
        {(delta * 100).toFixed(2)}%
      </span>
    </span>
  );
}
