"use client";

import Link from "next/link";

import { METHODOLOGY_HREF } from "@/lib/branding";

/**
 * Inline source attribution. Render under any aggregation, table, or chart
 * that's based on ingested data so users always know provenance.
 */
export default function MethodologyDisclosure({ sources }: { sources?: string[] }) {
  return (
    <div className="text-[10px] text-dim mt-2 italic">
      Sources: {sources?.length ? sources.join(", ") : "INEC IReV + curated historical datasets"}.{" "}
      <Link href={METHODOLOGY_HREF} className="underline hover:text-primary">
        methodology
      </Link>
      .
    </div>
  );
}
