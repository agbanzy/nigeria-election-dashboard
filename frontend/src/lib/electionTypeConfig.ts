/**
 * Election type taxonomy — mirrors backend `app/scraper/election_types.py`.
 * Keep in sync if either side changes.
 */

export type ElectionType =
  | "presidential"
  | "governorship"
  | "senate"
  | "reps"
  | "state_hoa"
  | "lg_chairman"
  | "councillor";

export const ELECTION_TYPES: ElectionType[] = [
  "presidential",
  "governorship",
  "senate",
  "reps",
  "state_hoa",
  "lg_chairman",
  "councillor",
];

export const ELECTION_LABELS: Record<ElectionType, string> = {
  presidential: "Presidential",
  governorship: "Governorship",
  senate: "Senate",
  reps: "House of Reps",
  state_hoa: "State Assembly",
  lg_chairman: "LG / Area Council Chairman",
  councillor: "Councillor",
};

export const ELECTION_TIER: Record<ElectionType, "federal" | "state" | "local"> = {
  presidential: "federal",
  governorship: "state",
  senate: "federal",
  reps: "federal",
  state_hoa: "state",
  lg_chairman: "local",
  councillor: "local",
};
