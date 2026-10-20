"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { JobAnalysis, JobMatch } from "@/lib/types";
import * as api from "@/lib/api";
import { ExternalLink, Wand2, Check, X, ScanSearch, Loader2 } from "lucide-react";
import { ScoreMarker } from "@/components/ui/ScoreMarker";
import { VerdictSection } from "@/components/fit/VerdictSection";
import { RequirementsTable } from "@/components/fit/RequirementsTable";
import { AboutJob } from "@/components/fit/AboutJob";
import { Square } from "@/components/fit/shared";

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
  const [analysing, setAnalysing] = useState(false);
  const [analysis, setAnalysis] = useState<JobAnalysis | null>(null);
  const [analysisError, setAnalysisError] = useState("");
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!job.analysis_id) return;
    api.getJobAnalysis(profile, job.id).then(r => {
      if (r.status === "ready") setAnalysis(r.analysis);
    }).catch(() => {});
  }, [profile, job.id, job.analysis_id]);

  useEffect(() => {
    if (!analysing) return;
    const interval = setInterval(async () => {
      try {
        const r = await api.getJobAnalysis(profile, job.id);
        if (r.status === "ready") { setAnalysis(r.analysis); setAnalysing(false); }
        else if (r.status === "failed") { setAnalysisError(r.error); setAnalysing(false); }
        // "none" after we started means the run ended without a saved result (server
        // restart, or a search overwrote the job list): stop so the button works again.
        else if (r.status === "none") { setAnalysing(false); }
      } catch {
        setAnalysing(false);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [analysing, profile, job.id]);

  async function handleAnalyse() {
    setAnalysisError("");
    try {
      await api.analyseJob(profile, job.id);
      setAnalysing(true);
    } catch (e: unknown) {
      setAnalysisError(e instanceof Error ? e.message : "Failed to start analysis");
    }
  }

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
      <p className="text-xs text-ink-muted">
        search score: {job.relevance_score}/10 · {job.text_basis === "full" ? "page read" : "snippet only"}
      </p>

      {(job.red_flags ?? []).length > 0 && (
        <ul className="space-y-1">
          {job.red_flags.map((flag, i) => (
            <li key={i} className="flex gap-2 text-sm"><Square colour="red" />{flag}</li>
          ))}
        </ul>
      )}

      {analysis && (
        <div className="flex items-center gap-4">
          <ScoreMarker score={analysis.match_score} />
          <span className="text-sm font-bold">{analysis.verdict}</span>
          <button onClick={() => setExpanded(e => !e)} className="text-sm underline">
            {expanded ? "hide analysis" : "show analysis"}
          </button>
        </div>
      )}
      {analysisError && <p className="text-sm text-ink bg-red/10 border-l-[3px] border-red px-3 py-2">{analysisError}</p>}
      {analysis && expanded && (
        <div className="space-y-8 border-l-[3px] border-ink pl-4 py-2">
          <VerdictSection analysis={analysis} />
          <RequirementsTable requirements={analysis.requirements} />
          <AboutJob analysis={analysis} />
        </div>
      )}

      {error && <p className="text-sm text-ink border-l-[3px] border-red pl-3">{error}</p>}

      <div className="flex flex-wrap items-center gap-2 pt-1">
        <a
          href={job.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-sm font-medium text-ink hover:text-ink transition-colors"
        >
          <ExternalLink size={14} /> view
        </a>
        {!analysis && (
          <button
            onClick={handleAnalyse}
            disabled={analysing}
            className="flex items-center gap-1.5 text-sm font-medium border-[1.5px] border-ink px-2.5 py-1 hover:bg-ink hover:text-paper transition-colors disabled:opacity-50"
          >
            {analysing ? <Loader2 size={14} className="animate-spin" /> : <ScanSearch size={14} />}
            {analysing ? "analysing…" : "analyse"}
          </button>
        )}
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
