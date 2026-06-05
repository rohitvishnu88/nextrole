"use client";
import { useState } from "react";
import { X } from "lucide-react";
import type { ApplicationStatus } from "@/lib/types";
import * as api from "@/lib/api";

interface Props {
  profileId: string;
  prefillUrl?: string;
  onClose: () => void;
  onCreated: () => void;
}

const STATUSES: ApplicationStatus[] = ["saved", "applied", "interview", "offer", "rejected"];

export function AddApplicationModal({ profileId, prefillUrl, onClose, onCreated }: Props) {
  const [form, setForm] = useState({
    job_title: "", company: "", location: "", url: prefillUrl ?? "", status: "applied" as ApplicationStatus, notes: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit() {
    if (!form.job_title || !form.company) return;
    setLoading(true);
    setError("");
    try {
      await api.createApplication({
        ...form,
        profile_id: profileId,
        location: form.location || undefined,
        url: form.url || undefined,
        notes: form.notes || undefined,
      });
      onCreated();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 relative">
        <button onClick={onClose} className="absolute top-4 right-4 text-gray-400 hover:text-gray-600">
          <X size={18} />
        </button>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Add Application</h2>
        <div className="space-y-3">
          {(["job_title", "company", "location", "url"] as const).map(field => (
            <input
              key={field}
              value={form[field]}
              onChange={e => setForm(f => ({ ...f, [field]: e.target.value }))}
              placeholder={field === "job_title" ? "Job Title *" : field.charAt(0).toUpperCase() + field.slice(1)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
            />
          ))}
          <select
            value={form.status}
            onChange={e => setForm(f => ({ ...f, status: e.target.value as ApplicationStatus }))}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          >
            {STATUSES.map(s => (
              <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
            ))}
          </select>
          <textarea
            value={form.notes}
            onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
            placeholder="Notes (optional)"
            rows={3}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent resize-none"
          />
          {error && <p className="text-sm text-red-500">{error}</p>}
          <button
            onClick={handleSubmit}
            disabled={!form.job_title || !form.company || loading}
            className="w-full bg-accent text-white rounded-lg py-2 text-sm font-medium disabled:opacity-50 hover:bg-accent/90 transition-colors"
          >
            {loading ? "Saving..." : "Add Application"}
          </button>
        </div>
      </div>
    </div>
  );
}
