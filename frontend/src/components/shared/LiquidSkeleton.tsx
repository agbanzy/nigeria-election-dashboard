"use client";

/**
 * Shimmer skeleton — uses tailwind animate-shimmer (already in config).
 */

interface Props {
  className?: string;
}

export default function LiquidSkeleton({ className = "" }: Props) {
  return (
    <div
      className={`relative overflow-hidden rounded bg-dashboard-card ${className}`}
    >
      <div className="absolute inset-0 -translate-x-full animate-[shimmer_1.8s_infinite] bg-gradient-to-r from-transparent via-white/5 to-transparent" />
    </div>
  );
}
