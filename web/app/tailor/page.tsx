"use client";
import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import * as api from "@/lib/api";
import type { TailorJob } from "@/lib/types";
import { useActiveProfile } from "@/lib/useActiveProfile";
import { AddApplicationModal } from "@/components/AddApplicationModal";
import { Wand2, Download, Plus, Pencil } from "lucide-react";

function TailorPageInner() {
  const profile = useActiveProfile();
  const searchParams = useSearchParams();
  const [mode, setMode] = useState<"url" | "jd">("url");
  const [input, setInput] = useState("");
  const [job, setJob] = useState<TailorJob | null>(null);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState("");
  const [showAddToTracker, setShowAddToTracker] = useState(false);

  // Restore completed job when redirected back from the edit page
  useEffect(() => {
    const jobParam = searchParams.get("job");
    if (!jobParam || job) return;
    api.getTailorStatus(jobParam).then(setJob).catch(() => {});
  }, [searchParams, job]);

  async function handleSubmit() {
    if (!input.trim() || !profile) return;
    setError("");
    setJob(null);
    try {
      const res = await api.startTailor(
        profile,
        mode === "url" ? input.trim() : undefined,
        mode === "jd" ? input.trim() : undefined,
      );
      setJob({ job_id: res.job_id, status: "running", message: "Starting..." });
      setPolling(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start");
    }
  }

  useEffect(() => {
    if (!polling || !job) return;
    const interval = setInterval(async () => {
      try {
        const status = await api.getTailorStatus(job.job_id);
        setJob(status);
        if (status.status !== "running") setPolling(false);
      } catch {
        setPolling(false);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [polling, job]);

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-navy">Tailor a Resume</h1>
        <p className="text-sm text-muted mt-1">Paste a job URL or description — get a tailored PDF and cover letter</p>
      </div>

      {!profile && (
        <div className="bg-yellow-50 border border-yellow-100 rounded-2xl px-5 py-4 text-sm text-yellow-700">
          Select or create a profile first from the top-right.
        </div>
      )}

      <div className="bg-white rounded-2xl border border-warm-border p-6 space-y-4">
        <div className="flex gap-2">
          {(["url", "jd"] as const).map(m => (
            <button
              key={m}
              onClick={() => { setMode(m); setInput(""); }}
              className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
                mode === m
                  ? "bg-accent text-white"
                  : "bg-cream text-muted hover:text-navy"
              }`}
            >
              {m === "url" ? "Job URL" : "Paste JD"}
            </button>
          ))}
        </div>

        {mode === "url" ? (
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="https://linkedin.com/jobs/view/..."
            className="w-full border border-warm-border rounded-xl px-4 py-2.5 text-sm text-navy placeholder-muted bg-cream focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition"
          />
        ) : (
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Paste the full job description here..."
            rows={8}
            className="w-full border border-warm-border rounded-xl px-4 py-2.5 text-sm text-navy placeholder-muted bg-cream focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition resize-none"
          />
        )}

        {error && <p className="text-sm text-red-500">{error}</p>}

        <button
          onClick={handleSubmit}
          disabled={!input.trim() || !profile || polling}
          className="flex items-center gap-2 bg-accent hover:bg-accent-hover disabled:opacity-50 text-white rounded-xl px-5 py-2.5 text-sm font-semibold transition-colors"
        >
          <Wand2 size={15} />
          {polling ? "Working…" : "Tailor Resume"}
        </button>
      </div>

      {job && (
        <div className="bg-white rounded-2xl border border-warm-border p-6 space-y-4">
          <div className="flex items-center gap-2.5">
            <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${
              job.status === "running" ? "bg-yellow-400 animate-pulse" :
              job.status === "completed" ? "bg-green-500" : "bg-red-400"
            }`} />
            <p className="text-sm font-medium text-navy">{job.message}</p>
          </div>

          {job.status === "completed" && (
            <div className="flex flex-wrap gap-2 pt-1">
              <a
                href={`/api/tailor/${job.job_id}/pdf`}
                download
                className="flex items-center gap-2 bg-navy hover:bg-navy/90 text-white rounded-xl px-4 py-2 text-sm font-medium transition-colors"
              >
                <Download size={14} />
                Download PDF
              </a>
              <a
                href={`/api/tailor/${job.job_id}/cover-letter`}
                download
                className="flex items-center gap-2 border border-warm-border text-navy hover:bg-cream rounded-xl px-4 py-2 text-sm font-medium transition-colors"
              >
                <Download size={14} />
                Cover Letter
              </a>
              <a
                href={`/tailor/${job.job_id}/edit`}
                className="flex items-center gap-2 border border-warm-border text-navy hover:bg-cream rounded-xl px-4 py-2 text-sm font-medium transition-colors"
              >
                <Pencil size={14} />
                Edit Resume
              </a>
              <button
                onClick={() => setShowAddToTracker(true)}
                className="flex items-center gap-2 border border-accent text-accent hover:bg-accent-light rounded-xl px-4 py-2 text-sm font-medium transition-colors"
              >
                <Plus size={14} />
                Add to Tracker
              </button>
            </div>
          )}
        </div>
      )}

      {showAddToTracker && profile && (
        <AddApplicationModal
          profileId={profile}
          prefillUrl={job?.url}
          onClose={() => setShowAddToTracker(false)}
          onCreated={() => setShowAddToTracker(false)}
        />
      )}
    </div>
  );
}

// useSearchParams() requires a Suspense boundary in Next.js App Router
export default function TailorPage() {
  return (
    <Suspense fallback={null}>
      <TailorPageInner />
    </Suspense>
  );
}
