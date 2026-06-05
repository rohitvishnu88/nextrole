"use client";
import { useState } from "react";
import type { Application } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";
import { Trash2 } from "lucide-react";
import * as api from "@/lib/api";

interface Props {
  apps: Application[];
  onRefresh: () => void;
}

type SortKey = "company" | "job_title" | "status" | "applied_date";

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
      className="px-5 py-3 text-left text-xs font-semibold text-muted uppercase tracking-wide cursor-pointer hover:text-navy select-none"
    >
      {label} {sortKey === k ? (sortAsc ? "↑" : "↓") : ""}
    </th>
  );

  async function handleDelete(id: string) {
    await api.deleteApplication(id);
    onRefresh();
  }

  return (
    <div className="bg-white rounded-2xl border border-warm-border overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-warm-border bg-cream">
            <Th label="Company" k="company" />
            <Th label="Role" k="job_title" />
            <th className="px-5 py-3 text-left text-xs font-semibold text-muted uppercase tracking-wide">Location</th>
            <Th label="Status" k="status" />
            <Th label="Applied" k="applied_date" />
            <th className="px-5 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-warm-border">
          {sorted.map(app => (
            <tr key={app.id} className="hover:bg-cream transition-colors">
              <td className="px-5 py-3.5 font-medium text-navy">{app.company}</td>
              <td className="px-5 py-3.5 text-navy">{app.job_title}</td>
              <td className="px-5 py-3.5 text-muted">{app.location ?? "—"}</td>
              <td className="px-5 py-3.5"><StatusBadge status={app.status} /></td>
              <td className="px-5 py-3.5 text-muted">{app.applied_date ?? "—"}</td>
              <td className="px-5 py-3.5 text-right">
                <button onClick={() => handleDelete(app.id)} className="text-warm-border hover:text-red-400 transition-colors">
                  <Trash2 size={14} />
                </button>
              </td>
            </tr>
          ))}
          {sorted.length === 0 && (
            <tr>
              <td colSpan={6} className="px-5 py-12 text-center text-muted text-sm">No applications yet</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
