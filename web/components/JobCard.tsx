"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import type { JobMatch } from "@/lib/types";
import * as api from "@/lib/api";
import { ExternalLink, Wand2, Check, X } from "lucide-react";

const SOURCE_LABEL: Record<JobMatch["source"], string> = {
  linkedin: "LinkedIn",
  greenhouse: "Greenhouse",
  lever: "Lever",
  yc: "Y Combinator",
};

const SOURCE_COLOUR: Record<JobMatch["source"], string> = {
  linkedin: "bg-accent-light text-accent",
  greenhouse: "bg-green-soft text-green-text",
  lever: "bg-yellow-50 text-yellow-700",
  yc: "bg-cream text-navy border border-warm-border",
};

export function JobCard({
  job,
  profile,
  onRemove,
}: {
  job: JobMatch;
  profile: string;
  onRemove: (id: string) => void;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleApply() {
    setBusy(true);
    setError("");
    try {
      await api.applyToJob(profile, job.id);
      onRemove(job.id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to apply");
    } finally {
      setBusy(false);
    }
  }

  async function handleDismiss() {
    setBusy(true);
    setError("");
    try {
      await api.dismissJob(profile, job.id);
      onRemove(job.id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to dismiss");
    } finally {
      setBusy(false);
    }
  }

  async function handleTailor() {
    setBusy(true);
    setError("");
    try {
      const res = await api.startTailor(profile, job.url);
      router.push(`/tailor?job=${res.job_id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start tailoring");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-white border border-warm-border rounded-2xl p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-navy">{job.title}</h3>
            {job.status === "new" && (
              <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-accent text-white">New</span>
            )}
          </div>
          <p className="text-sm text-muted">{job.company} · {job.location}</p>
        </div>
        <span className={`text-xs font-medium px-2.5 py-0.5 rounded-full shrink-0 ${SOURCE_COLOUR[job.source]}`}>
          {SOURCE_LABEL[job.source]}
        </span>
      </div>

      <p className="text-sm text-navy">{job.match_reason}</p>
      <p className="text-xs text-muted">Match score: {job.relevance_score}/10</p>

      {error && <p className="text-sm text-red-500">{error}</p>}

      <div className="flex items-center gap-2 pt-1">
        <a
          href={job.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-sm font-medium text-navy hover:text-accent transition-colors"
        >
          <ExternalLink size={14} /> View
        </a>
        <button
          onClick={handleTailor}
          disabled={busy}
          className="flex items-center gap-1.5 text-sm font-medium text-navy hover:text-accent transition-colors disabled:opacity-50"
        >
          <Wand2 size={14} /> Tailor
        </button>
        <button
          onClick={handleApply}
          disabled={busy}
          className="flex items-center gap-1.5 text-sm font-medium text-green-text hover:opacity-80 transition-opacity disabled:opacity-50 ml-auto"
        >
          <Check size={14} /> Applied
        </button>
        <button
          onClick={handleDismiss}
          disabled={busy}
          className="flex items-center gap-1.5 text-sm font-medium text-muted hover:text-red-600 transition-colors disabled:opacity-50"
        >
          <X size={14} /> Dismiss
        </button>
      </div>
    </div>
  );
}
