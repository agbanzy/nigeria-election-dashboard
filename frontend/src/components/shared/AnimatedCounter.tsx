"use client";

/**
 * Liquid number counter — interpolates from 0 → value over `durationMs`.
 * Uses requestAnimationFrame, no deps. Re-animates whenever value changes.
 */

import { useEffect, useRef, useState } from "react";

interface Props {
  value: number;
  durationMs?: number;
  format?: (n: number) => string;
  className?: string;
}

const defaultFormat = (n: number) => Math.round(n).toLocaleString();

export default function AnimatedCounter({
  value,
  durationMs = 900,
  format = defaultFormat,
  className,
}: Props) {
  const [display, setDisplay] = useState(0);
  const fromRef = useRef(0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const from = fromRef.current;
    const to = value;
    const start = performance.now();

    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      // ease-out-cubic
      const eased = 1 - Math.pow(1 - t, 3);
      const current = from + (to - from) * eased;
      setDisplay(current);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = to;
      }
    };

    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [value, durationMs]);

  return <span className={className}>{format(display)}</span>;
}
