"use client";

/**
 * URL-backed filter state — shareable links survive page reload.
 *
 * Reads from / writes to the page's `?state=&cycle=&type=` search params via
 * Next.js `useRouter` + `useSearchParams`. The hook exposes typed setters so
 * the rest of the app doesn't deal with string parsing.
 */

import { ReactNode, createContext, useCallback, useContext, useMemo } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";

import type { ElectionType } from "@/lib/electionTypeConfig";

export interface Filters {
  state: string | null; // 2-letter code, uppercase
  cycle: number | null;
  electionType: ElectionType | null;
}

interface FilterContextValue extends Filters {
  setState: (code: string | null) => void;
  setCycle: (cycle: number | null) => void;
  setElectionType: (t: ElectionType | null) => void;
  clear: () => void;
}

const FilterContext = createContext<FilterContextValue | null>(null);

export function FilterProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const filters: Filters = useMemo(
    () => ({
      state: params.get("state")?.toUpperCase() || null,
      cycle: params.get("cycle") ? Number(params.get("cycle")) : null,
      electionType: (params.get("type") as ElectionType | null) || null,
    }),
    [params],
  );

  const replaceParam = useCallback(
    (key: string, value: string | null) => {
      const next = new URLSearchParams(params.toString());
      if (value === null || value === "") next.delete(key);
      else next.set(key, value);
      const search = next.toString();
      router.replace(`${pathname}${search ? `?${search}` : ""}`);
    },
    [params, pathname, router],
  );

  const setState = useCallback((code: string | null) => replaceParam("state", code), [replaceParam]);
  const setCycle = useCallback(
    (cycle: number | null) => replaceParam("cycle", cycle === null ? null : String(cycle)),
    [replaceParam],
  );
  const setElectionType = useCallback(
    (t: ElectionType | null) => replaceParam("type", t),
    [replaceParam],
  );
  const clear = useCallback(() => router.replace(pathname), [router, pathname]);

  const value: FilterContextValue = {
    ...filters,
    setState,
    setCycle,
    setElectionType,
    clear,
  };

  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>;
}

export function useFilters(): FilterContextValue {
  const ctx = useContext(FilterContext);
  if (!ctx) throw new Error("useFilters must be used inside <FilterProvider>");
  return ctx;
}
