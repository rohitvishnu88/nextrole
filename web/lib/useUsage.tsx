"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import * as api from "@/lib/api";
import type { MeteredAction, UsageMe } from "@/lib/types";

interface UsageState {
  usage: UsageMe | null;
  refresh: () => void;
  remaining: (action: MeteredAction) => number | null;
  blockedReason: (action: MeteredAction) => string | null;
}

const UsageContext = createContext<UsageState>({
  usage: null,
  refresh: () => {},
  remaining: () => null,
  blockedReason: () => null,
});

export function formatResetDate(isoDate: string): string {
  return new Date(`${isoDate}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
}

export function UsageProvider({ children }: { children: React.ReactNode }) {
  const [usage, setUsage] = useState<UsageMe | null>(null);
  const refresh = useCallback(() => {
    api.getUsageMe().then(setUsage).catch(() => {});
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const remaining = (action: MeteredAction) => {
    const a = usage?.actions[action];
    return a && a.limit !== null ? Math.max(0, a.limit - a.used) : null;
  };
  const blockedReason = (action: MeteredAction) => {
    if (!usage) return null;
    const resets = formatResetDate(usage.resets_on);
    if (usage.paused) return `AI features paused until ${resets}`;
    return remaining(action) === 0 ? `limit reached — resets ${resets}` : null;
  };

  return (
    <UsageContext.Provider value={{ usage, refresh, remaining, blockedReason }}>
      {children}
    </UsageContext.Provider>
  );
}

export function useUsage(): UsageState {
  return useContext(UsageContext);
}

export function LimitNote({ action }: { action: MeteredAction }) {
  const reason = useUsage().blockedReason(action);
  return reason ? <span className="text-xs text-ink-muted">{reason}</span> : null;
}
