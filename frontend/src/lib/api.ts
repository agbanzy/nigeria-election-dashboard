/**
 * API base URL helpers.
 *
 * Same-origin in production (Next.js static site sits behind the same DO App
 * Platform router as the Flask backend; the `routes` block in `.do/app.yaml`
 * maps `/api` to the backend service).
 *
 * Local dev: NEXT_PUBLIC_API_URL overrides. Defaults to http://localhost:8080.
 */

export const API_BASE: string =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_URL) || "";

export function apiUrl(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${p}`;
}

export async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(apiUrl(path), { ...init, headers: { Accept: "application/json", ...(init?.headers || {}) } });
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
  return resp.json() as Promise<T>;
}

export interface CalendarEvent {
  id: number;
  election_date: string;
  election_type: string;
  election_type_label: string;
  state_id: number | null;
  state_code: string | null;
  state_name: string | null;
  status: "scheduled" | "live" | "completed" | "cancelled";
  notes: string | null;
  seconds_until?: number | null;
}

export interface StateRow {
  state_id: number;
  code: string;
  name: string;
  zone: string;
}

export interface ElectionRow {
  election_id: number;
  cycle: number;
  election_type: string;
  election_type_label: string;
  state_id: number | null;
  election_date: string | null;
  status: string;
  irev_election_id: string | null;
}

export interface MethodologyResponse {
  statistical_definitions: Array<{
    key: string;
    name: string;
    formula: string;
    description: string;
    reference?: string;
  }>;
  known_gaps: Array<{ scope: string; coverage: string; reason: string }>;
  sources: Array<{
    name: string;
    url: string | null;
    license: string | null;
    notes: string | null;
    ingested_at: string | null;
  }>;
  takedown_contact: string;
}
