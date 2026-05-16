"use client";

/**
 * Liquid horizontal share bar — fills smoothly to `share` (0..1).
 * Uses CSS transition for cheap GPU-driven width animation.
 */

import { useEffect, useState } from "react";

interface Props {
  share: number;            // 0..1
  color: string | null | undefined;
  label?: string;
  value?: number;
  delayMs?: number;
}

export default function AnimatedShareBar({ share, color, label, value, delayMs = 0 }: Props) {
  const [width, setWidth] = useState(0);

  useEffect(() => {
    // Defer to next paint so the transition is observable
    const id = window.setTimeout(() => setWidth(Math.max(0, Math.min(1, share))), 30 + delayMs);
    return () => window.clearTimeout(id);
  }, [share, delayMs]);

  return (
    <div className="w-full">
      <div className="flex items-baseline justify-between text-xs mb-1">
        <span className="font-semibold">{label}</span>
        <span className="font-mono text-dim">
          {value != null && <>{value.toLocaleString()} · </>}
          {(share * 100).toFixed(1)}%
        </span>
      </div>
      <div className="h-2 rounded-full bg-black/30 overflow-hidden">
        <div
          className="h-full rounded-full transition-[width] duration-[900ms] ease-out"
          style={{
            width: `${width * 100}%`,
            background: color || "#94a3b8",
            boxShadow: color ? `0 0 8px ${color}55` : undefined,
          }}
        />
      </div>
    </div>
  );
}
