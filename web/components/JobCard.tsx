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
    <div className="border-t-[1.5px] border-ink pt-5 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-bold text-ink">{job.title}</h3>
            {job.status === "new" && (
              <span className="text-xs font-medium px-2 py-0.5 bg-ink text-paper">new</span>
            )}
          </div>
          <p className="text-sm text-ink-muted">{job.company} · {job.location}</p>
        </div>
        <span className={`text-xs font-medium px-2.5 py-0.5 shrink-0 border border-ink text-ink`}>
          {SOURCE_LABEL[job.source]}
        </span>
      </div>

      <p className="text-sm text-ink">{job.match_reason}</p>
      <p className="text-xs text-ink-muted">Match score: {job.relevance_score}/10</p>

      {error && <p className="text-sm text-ink border-l-[3px] border-red pl-3">{error}</p>}

      <div className="flex items-center gap-2 pt-1">
        <a
          href={job.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-sm font-medium text-ink hover:text-ink transition-colors"
        >
          <ExternalLink size={14} /> view
        </a>
        <button
          onClick={handleTailor}
          disabled={busy}
          className="flex items-center gap-1.5 text-sm font-medium text-ink hover:text-ink transition-colors disabled:opacity-50"
        >
          <Wand2 size={14} /> tailor
        </button>
        <button
          onClick={handleApply}
          disabled={busy}
          className="flex items-center gap-1.5 text-sm font-medium text-ink hover:opacity-80 transition-opacity disabled:opacity-50 ml-auto"
        >
          <Check size={14} /> applied
        </button>
        <button
          onClick={handleDismiss}
          disabled={busy}
          className="flex items-center gap-1.5 text-sm font-medium text-ink-muted hover:text-ink transition-colors disabled:opacity-50"
        >
          <X size={14} /> dismiss
        </button>
      </div>
    </div>
  );
}
