export const PARTY_COLORS: Record<string, string> = {
  APC: "#1565c0",
  PDP: "#c62828",
  ADC: "#6a1b9a",
  LP: "#2e7d32",
  NNPP: "#e65100",
  SDP: "#ad1457",
  APGA: "#00695c",
  AA: "#4527a0",
  ADP: "#bf360c",
  APM: "#00838f",
  ZLP: "#33691e",
  YPP: "#795548",
  default: "#455a64",
};

export const ACCENT_COLORS = {
  green: "#10b981",
  blue: "#3b82f6",
  orange: "#f59e0b",
  red: "#ef4444",
  purple: "#a78bfa",
  yellow: "#fbbf24",
  cyan: "#06b6d4",
};

// These are resolved dynamically at render time via useChartTheme hook
export const CHART_GRID_COLOR = "#1f2538";
export const CHART_TEXT_COLOR = "#6b7280";

export const REFRESH_INTERVAL = 15000; // 15 seconds — fast refresh for live election day
export const SCRAPE_CYCLE = 120000; // 2 minutes

// Server-Sent Events stream URL. DISABLED by default (empty string) because
// the broadcaster is a Phase B TODO — the backend only emits heartbeats, so
// there is no live data to push and data already refreshes via SWR polling
// (REFRESH_INTERVAL). An empty URL means useSSE never opens a connection, so
// the "RECONNECTING TO SERVER" banner never fires on a dead stream and no
// long-lived request ties up Flask's sync gunicorn workers.
//
// To re-enable once the broadcaster + async (gevent) workers land, set
// NEXT_PUBLIC_SSE_URL at build time to the same-origin path "/api/live/events"
// (routed to Flask via DO ingress) or a dedicated streaming host.
export const SSE_URL =
  typeof window !== "undefined" ? process.env.NEXT_PUBLIC_SSE_URL || "" : "";

export const NAV_ITEMS = [
  { name: "Overview", href: "/", icon: "home" },
  { name: "Elections", href: "/elections", icon: "chart-bar" },
  { name: "Analytics", href: "/analytics", icon: "chart-pie" },
  { name: "Messaging", href: "/messaging", icon: "chat-bubble" },
] as const;

export function getPartyColor(party: string): string {
  return PARTY_COLORS[party] || PARTY_COLORS.default;
}
