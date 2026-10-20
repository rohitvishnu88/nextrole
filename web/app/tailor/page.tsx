"use client";
import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import * as api from "@/lib/api";
import type { TailorFit, TailorJob, TailoredResume } from "@/lib/types";
import { useActiveProfile } from "@/lib/useActiveProfile";
import { AddApplicationModal } from "@/components/AddApplicationModal";
import { Wand2, Download, Plus, Pencil } from "lucide-react";
import { VerdictSection } from "@/components/fit/VerdictSection";
import { RequirementsTable } from "@/components/fit/RequirementsTable";
import { ChangesList } from "@/components/fit/ChangesList";
import { AtsView } from "@/components/fit/AtsView";
import { AboutJob, LeftOff } from "@/components/fit/AboutJob";
import { LimitNote, useUsage } from "@/lib/useUsage";

function TailorPageInner() {
  const { blockedReason, refresh: refreshUsage } = useUsage();
  const profile = useActiveProfile();
  const searchParams = useSearchParams();
  const [mode, setMode] = useState<"url" | "jd">("url");
  const [input, setInput] = useState("");
  const [job, setJob] = useState<TailorJob | null>(null);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState("");
  const [showAddToTracker, setShowAddToTracker] = useState(false);
  const [tailoredResume, setTailoredResume] = useState<TailoredResume | null>(null);
  const [fit, setFit] = useState<TailorFit | null>(null);

  useEffect(() => {
    if (job?.status !== "completed") {
      setTailoredResume(null);
      setFit(null);
      return;
    }
    api.getTailorData(job.job_id).then(setTailoredResume).catch(() => {});
    api.getTailorFit(job.job_id).then(setFit).catch(() => {});
  }, [job?.status, job?.job_id]);

  // Restore a job when arriving via ?job= — either completed (redirect back from
  // the edit page) or still running (started from the Jobs page's Tailor button).
  useEffect(() => {
    const jobParam = searchParams.get("job");
    if (!jobParam || job) return;
    api.getTailorStatus(jobParam).then((status) => {
      setJob(status);
      if (status.status === "running") setPolling(true);
    }).catch(() => {});
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
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-5xl font-bold text-ink leading-none">tailor a resume</h1>
        <p className="text-sm text-ink-muted mt-3">Paste a job URL or description — get a tailored PDF and cover letter</p>
      </div>

      {!profile && (
        <div className="bg-yellow/10 border-l-[3px] border-yellow px-4 py-3 text-sm text-ink">
          Select or create a profile first from the top-right.
        </div>
      )}

      <div className="border-t-[1.5px] border-ink pt-5 space-y-4">
        <div className="flex gap-2">
          {(["url", "jd"] as const).map(m => (
            <button
              key={m}
              onClick={() => { setMode(m); setInput(""); }}
              className={`px-4 py-1.5 text-sm font-medium transition-colors ${
                mode === m
                  ? "bg-ink text-paper"
                  : "border-[1.5px] border-ink text-ink hover:bg-surface"
              }`}
            >
              {m === "url" ? "job url" : "paste jd"}
            </button>
          ))}
        </div>

        {mode === "url" ? (
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="https://linkedin.com/jobs/view/..."
            className="w-full border-[1.5px] border-ink px-4 py-2.5 text-sm text-ink bg-surface focus:outline-none focus:ring-2 focus:ring-ink focus:border-ink transition"
          />
        ) : (
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Paste the full job description here..."
            rows={8}
            className="w-full border-[1.5px] border-ink px-4 py-2.5 text-sm text-ink bg-surface focus:outline-none focus:ring-2 focus:ring-ink focus:border-ink transition resize-none"
          />
        )}

        {error && <p className="text-sm text-ink border-l-[3px] border-red pl-3">{error}</p>}

        <button
          onClick={async () => { await handleSubmit(); refreshUsage(); }}
          disabled={!input.trim() || !profile || polling || !!blockedReason("tailor")}
          className="flex items-center gap-2 bg-ink hover:bg-ink/80 disabled:opacity-50 text-paper px-5 py-2.5 text-sm font-bold transition-colors"
        >
          <Wand2 size={15} />
          {polling ? "Working…" : "Tailor Resume"}
        </button>

        <LimitNote action="tailor" />
      </div>

      {job && (
        <div className="border-t-[1.5px] border-ink pt-5 space-y-4">
          <div className="flex items-center gap-2.5">
            <span className={`w-2.5 h-2.5 shrink-0 ${
              job.status === "running" ? "bg-yellow animate-pulse" :
              job.status === "completed" ? "bg-blue" : "bg-red"
            }`} />
            <p className="text-sm font-medium text-ink">{job.message}</p>
          </div>

          {job.status === "completed" && tailoredResume && (
            <div className="space-y-4 pt-1 border-t border-rule-soft">
              <div className="pt-3">
                <p className="text-xs font-bold text-ink-muted mb-1.5">Summary</p>
                <p className="text-sm text-ink leading-relaxed">{tailoredResume.summary}</p>
              </div>
              <div className="space-y-3">
                {tailoredResume.experience.map((exp, i) => (
                  <div key={i} className="border-l-[3px] border-ink pl-4">
                    <p className="text-sm font-bold text-ink">{exp.title}</p>
                    <p className="text-xs text-ink-muted mb-2">
                      {exp.company}{exp.highlight ? ` — ${exp.highlight}` : ""} · {exp.start_date} – {exp.end_date}
                    </p>
                    <ul className="list-disc list-inside space-y-1">
                      {exp.description.map((bullet, j) => (
                        <li key={j} className="text-xs text-ink">{bullet}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          )}

          {job.status === "completed" && (
            <div className="flex flex-wrap gap-2 pt-1">
              <a
                href={`/api/tailor/${job.job_id}/pdf`}
                download
                className="flex items-center gap-2 bg-ink hover:bg-ink/80 text-paper px-4 py-2 text-sm font-medium transition-colors"
              >
                <Download size={14} />
                download pdf
              </a>
              <a
                href={`/api/tailor/${job.job_id}/cover-letter`}
                download
                className="flex items-center gap-2 border-[1.5px] border-ink text-ink hover:bg-ink hover:text-paper px-4 py-2 text-sm font-medium transition-colors"
              >
                <Download size={14} />
                cover letter
              </a>
              <a
                href={`/tailor/${job.job_id}/edit`}
                className="flex items-center gap-2 border-[1.5px] border-ink text-ink hover:bg-ink hover:text-paper px-4 py-2 text-sm font-medium transition-colors"
              >
                <Pencil size={14} />
                edit resume
              </a>
              <button
                onClick={() => setShowAddToTracker(true)}
                className="flex items-center gap-2 border-[1.5px] border-ink text-ink hover:bg-ink hover:text-paper px-4 py-2 text-sm font-medium transition-colors"
              >
                <Plus size={14} />
                add to tracker
              </button>
            </div>
          )}
        </div>
      )}

      {job?.status === "completed" && fit && (
        <div className="space-y-10 pt-4">
          {fit.analysis ? (
            <VerdictSection analysis={fit.analysis} />
          ) : (
            <p className="text-sm border-l-[3px] border-red pl-3">
              job analysis unavailable — the full ad couldn&apos;t be read.
            </p>
          )}
          {fit.analysis && <RequirementsTable requirements={fit.analysis.requirements} />}
          <ChangesList changes={fit.changes} flags={fit.fabrication_flags} />
          {fit.analysis && <LeftOff items={fit.analysis.left_off} />}
          <AtsView ats={fit.ats} />
          {fit.analysis && <AboutJob analysis={fit.analysis} />}
        </div>
      )}

      {showAddToTracker && profile && (
        <AddApplicationModal
          profileId={profile}
          prefillUrl={job?.url}
          matchScore={fit?.analysis?.match_score ?? null}
          analysisId={fit?.analysis?.analysis_id ?? null}
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
