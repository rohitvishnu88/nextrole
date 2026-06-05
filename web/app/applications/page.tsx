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
          <h1 className="text-2xl font-bold text-navy">Applications</h1>
          <p className="text-sm text-muted mt-1">{apps.length} role{apps.length !== 1 ? "s" : ""} tracked</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex bg-white border border-warm-border rounded-xl p-1 gap-0.5">
            <button
              onClick={() => setView("table")}
              className={`p-1.5 rounded-lg transition-colors ${view === "table" ? "bg-cream text-navy" : "text-muted hover:text-navy"}`}
            >
              <List size={15} />
            </button>
            <button
              onClick={() => setView("kanban")}
              className={`p-1.5 rounded-lg transition-colors ${view === "kanban" ? "bg-cream text-navy" : "text-muted hover:text-navy"}`}
            >
              <LayoutGrid size={15} />
            </button>
          </div>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 bg-accent hover:bg-accent-hover text-white rounded-xl px-4 py-2 text-sm font-semibold transition-colors"
          >
            <Plus size={14} />
            Add Application
          </button>
        </div>
      </div>

      {!profile && (
        <div className="bg-yellow-50 border border-yellow-100 rounded-2xl px-5 py-4 text-sm text-yellow-700">
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
