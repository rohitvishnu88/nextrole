"use client";
import { useCallback, useEffect, useState } from "react";
import * as api from "@/lib/api";
import type { Application } from "@/lib/types";
import { ApplicationTable } from "@/components/ApplicationTable";
import { ApplicationKanban } from "@/components/ApplicationKanban";
import { AddApplicationModal } from "@/components/AddApplicationModal";
import { useActiveProfile } from "@/lib/useActiveProfile";
import { LayoutGrid, List, Plus } from "lucide-react";

export default function ApplicationsPage() {
  const profile = useActiveProfile();
  const [apps, setApps] = useState<Application[]>([]);
  const [view, setView] = useState<"table" | "kanban">("table");
  const [showAdd, setShowAdd] = useState(false);

  const refresh = useCallback(() => {
    if (!profile) return;
    api.listApplications(profile).then(setApps).catch(() => {});
  }, [profile]);

  useEffect(() => { refresh(); }, [refresh]);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">applications</h1>
          <p className="text-sm text-ink-muted mt-1">{apps.length} role{apps.length !== 1 ? "s" : ""} tracked</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex bg-surface border border-rule-soft p-1 gap-0.5">
            <button
              onClick={() => setView("table")}
              className={`p-1.5 transition-colors ${view === "table" ? "bg-paper text-ink" : "text-ink-muted hover:text-ink"}`}
            >
              <List size={15} />
            </button>
            <button
              onClick={() => setView("kanban")}
              className={`p-1.5 transition-colors ${view === "kanban" ? "bg-paper text-ink" : "text-ink-muted hover:text-ink"}`}
            >
              <LayoutGrid size={15} />
            </button>
          </div>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 bg-ink hover:bg-ink/80 text-paper px-4 py-2 text-sm font-bold transition-colors"
          >
            <Plus size={14} />
            add application
          </button>
        </div>
      </div>

      {!profile && (
        <div className="bg-yellow/10 border border-yellow px-5 py-4 text-sm text-ink">
          Select a profile first.
        </div>
      )}

      {profile && view === "table" && <ApplicationTable apps={apps} onRefresh={refresh} />}
      {profile && view === "kanban" && <ApplicationKanban apps={apps} onRefresh={refresh} />}

      {showAdd && profile && (
        <AddApplicationModal
          profileId={profile}
          onClose={() => setShowAdd(false)}
          onCreated={() => { setShowAdd(false); refresh(); }}
        />
      )}
    </div>
  );
}
