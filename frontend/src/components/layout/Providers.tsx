"use client";

import { Suspense } from "react";
import { SessionProvider } from "next-auth/react";
import { usePathname } from "next/navigation";

import { DashboardProvider, useDashboard } from "@/context/DashboardContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { FilterProvider } from "@/context/FilterContext";
import ErrorBoundary from "@/components/shared/ErrorBoundary";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import ConnectionBanner from "@/components/shared/ConnectionBanner";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { cn } from "@/lib/utils";

// Routes that render without the dashboard shell
const PUBLIC_ROUTES = new Set(["/", "/login", "/api-access"]);

function DashboardShell({ children }: { children: React.ReactNode }) {
  const { isFullscreen, isOnline, sseConnected } = useDashboard();
  useKeyboardShortcuts();

  return (
    <div className={cn("flex h-screen overflow-hidden", isFullscreen && "tv-mode")}>
      {!isFullscreen && <Sidebar />}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <ConnectionBanner isOnline={isOnline} sseConnected={sseConnected} />
        <Header />
        <main className="flex-1 overflow-y-auto p-5 lg:p-6">
          <ErrorBoundary>
            <div className={cn("mx-auto", isFullscreen ? "max-w-full" : "max-w-[1500px]")}>
              {children}
            </div>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}

function ConditionalShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  if (PUBLIC_ROUTES.has(pathname)) {
    return <>{children}</>;
  }

  return (
    <DashboardProvider>
      <Suspense fallback={null}>
        <FilterProvider>
          <DashboardShell>{children}</DashboardShell>
        </FilterProvider>
      </Suspense>
    </DashboardProvider>
  );
}

export default function Providers({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SessionProvider>
      <ThemeProvider>
        <ConditionalShell>{children}</ConditionalShell>
      </ThemeProvider>
    </SessionProvider>
  );
}
