/**
 * Central branding strings. Used by Header / Sidebar / layout.tsx metadata so
 * the dashboard's identity is not scattered across 10 files.
 *
 * As the dashboard expands beyond FCT, `compose()` derives the active title +
 * subtitle from the current FilterContext scope (state / cycle / type).
 */

export const BRAND_NAME = "Nigeria Election Dashboard";
export const BRAND_TAGLINE = "Pan-Nigeria, multi-cycle election results + analysis";
export const DATA_PROVIDER = "INEC IReV + curated historical datasets";
export const METHODOLOGY_HREF = "/methodology";

// Innoedge attribution
export const POWERED_BY = "Innoedge";
export const POWERED_BY_URL = "https://innoedgetech.com/";
export const POWERED_BY_TAGLINE = "Innoedge Technologies Ltd";

export interface BrandScope {
  state?: { code: string; name: string } | null;
  cycle?: number | null;
  electionType?: string | null;
  electionTypeLabel?: string | null;
}

export function compose(scope: BrandScope = {}): { title: string; subtitle: string } {
  const parts: string[] = [];
  if (scope.state) parts.push(scope.state.name);
  if (scope.electionTypeLabel) parts.push(scope.electionTypeLabel);
  if (scope.cycle) parts.push(String(scope.cycle));
  const focus = parts.length ? parts.join(" · ") : "Nigeria";
  return {
    title: parts.length ? `${focus} — ${BRAND_NAME}` : BRAND_NAME,
    subtitle: parts.length ? BRAND_TAGLINE : `${BRAND_TAGLINE} · ${DATA_PROVIDER}`,
  };
}
