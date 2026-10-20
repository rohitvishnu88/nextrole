"use client";
import { useState } from "react";
import type { Application } from "@/lib/types";
import { StatusMarker } from "./ui/StatusMarker";
import { ScoreMarker } from "./ui/ScoreMarker";
import { Trash2 } from "lucide-react";
import * as api from "@/lib/api";

interface Props {
  apps: Application[];
  onRefresh: () => void;
}

type SortKey = "company" | "job_title" | "status" | "applied_date" | "follow_up_date";

export function ApplicationTable({ apps, onRefresh }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("applied_date");
  const [sortAsc, setSortAsc] = useState(false);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortAsc(a => !a);
    else { setSortKey(key); setSortAsc(true); }
  }

  const sorted = [...apps].sort((a, b) => {
    const av = a[sortKey] ?? "";
    const bv = b[sortKey] ?? "";
    return sortAsc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
  });

  const Th = ({ label, k }: { label: string; k: SortKey }) => (
    <th
      onClick={() => toggleSort(k)}
      className="pr-4 py-3 text-left text-xs font-bold text-ink-muted cursor-pointer hover:text-ink select-none"
    >
      {label} {sortKey === k ? (sortAsc ? "↑" : "↓") : ""}
    </th>
  );

  async function handleFollowedUp(id: string) {
    await api.markFollowedUp(id);
    onRefresh();
  }

  async function handleFollowUpDate(id: string, value: string) {
    await api.updateApplication(id, { follow_up_date: value || null });
    onRefresh();
  }

  async function handleClearFollowUp(id: string) {
    await api.updateApplication(id, { follow_up_date: null });
    onRefresh();
  }

  async function handleDelete(id: string) {
    await api.deleteApplication(id);
    onRefresh();
  }

  return (
    <div className="border-t-[1.5px] border-ink overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b-[1.5px] border-ink">
            <Th label="company" k="company" />
            <Th label="role" k="job_title" />
            <th className="pr-4 py-3 text-left text-xs font-bold text-ink-muted">location</th>
            <Th label="status" k="status" />
            <Th label="applied" k="applied_date" />
            <th className="pr-4 py-3 text-left text-xs font-bold text-ink-muted">match</th>
            <Th label="follow up" k="follow_up_date" />
            <th className="py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-rule-soft">
          {sorted.map(app => (
            <tr key={app.id} className="hover:bg-paper transition-colors">
              <td className="pr-4 py-3.5 font-medium text-ink">{app.company}</td>
              <td className="pr-4 py-3.5 text-ink">{app.job_title}</td>
              <td className="pr-4 py-3.5 text-ink-muted">{app.location ?? "—"}</td>
              <td className="pr-4 py-3.5"><StatusMarker status={app.status} /></td>
              <td className="pr-4 py-3.5 text-ink-muted">{app.applied_date ?? "—"}</td>
              <td className="pr-4 py-3.5"><ScoreMarker score={app.match_score} /></td>
              <td className="pr-4 py-3.5">
                <div className="flex flex-col gap-1">
                  <span className={`flex items-center gap-2 ${app.overdue ? "font-bold" : "text-ink-muted"}`}>
                    {app.overdue && <span aria-hidden className="w-2.5 h-2.5 bg-red shrink-0" />}
                    <input
                      type="date"
                      aria-label={`follow-up date for ${app.company}`}
                      value={app.follow_up_date ?? ""}
                      onChange={e => handleFollowUpDate(app.id, e.target.value)}
                      className="bg-transparent border-b border-rule-soft text-sm focus:outline-none focus:border-ink"
                    />
                    {app.overdue ? "overdue" : ""}
                  </span>
                  {app.follow_up_date && (
                    <span className="flex gap-3 text-xs">
                      <button onClick={() => handleFollowedUp(app.id)} className="underline">followed up</button>
                      <button onClick={() => handleClearFollowUp(app.id)} className="underline text-ink-muted">clear</button>
                    </span>
                  )}
                </div>
              </td>
              <td className="pr-4 py-3.5 text-right">
                <button onClick={() => handleDelete(app.id)} className="text-rule-soft hover:text-ink transition-colors">
                  <Trash2 size={14} />
                </button>
              </td>
            </tr>
          ))}
          {sorted.length === 0 && (
            <tr>
              <td colSpan={8} className="py-12 text-center text-ink-muted text-sm">No applications yet</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
