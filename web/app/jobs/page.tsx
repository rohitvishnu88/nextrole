"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "@/lib/api";
import type { JobMatch } from "@/lib/types";
import { useActiveProfile } from "@/lib/useActiveProfile";
import { JobCard } from "@/components/JobCard";
import { Search, Loader2 } from "lucide-react";
import { LimitNote, useUsage } from "@/lib/useUsage";

export default function JobsPage() {
  const { blockedReason, refresh: refreshUsage } = useUsage();
  const profile = useActiveProfile();
  const [jobs, setJobs] = useState<JobMatch[]>([]);
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const requestIdRef = useRef(0);

  const load = useCallback(async () => {
    if (!profile) return;
    const requestId = ++requestIdRef.current;
    setLoading(true);
    try {
      const result = await api.getJobMatches(profile);
      if (requestIdRef.current !== requestId) return;
      if (result.status === "searching") {
        setSearching(true);
      } else {
        setSearching(false);
        setJobs(result.jobs ?? []);
        setError(result.error ?? "");
      }
    } catch {
      if (requestIdRef.current !== requestId) return;
      setError("Failed to load job matches.");
    } finally {
      if (requestIdRef.current === requestId) setLoading(false);
    }
  }, [profile]);

  useEffect(() => {
    setJobs([]);
    setError("");
    setSearching(false);
  }, [profile]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!searching) {
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }
    pollRef.current = setInterval(load, 3000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [searching, load]);

  async function handleSearch() {
    if (!profile) return;
    setError("");
    try {
      await api.searchJobs(profile);
      setSearching(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start search");
    }
  }

  function handleRemove(id: string) {
    setJobs((prev) => prev.filter((j) => j.id !== id));
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-5xl font-bold text-ink leading-none">jobs</h1>
          <p className="text-sm text-ink-muted mt-3">{jobs.length} match{jobs.length !== 1 ? "es" : ""}</p>
        </div>
        <button
          onClick={async () => { await handleSearch(); refreshUsage(); }}
          disabled={searching || !profile || !!blockedReason("job_search")}
          className="flex items-center gap-1.5 bg-ink hover:bg-ink/80 text-paper px-4 py-2 text-sm font-bold transition-colors disabled:opacity-50"
        >
          {searching ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
          {searching ? "Searching..." : "Search now"}
        </button>
        <LimitNote action="job_search" />
      </div>

      {!profile && (
        <div className="bg-yellow/10 border-l-[3px] border-yellow px-4 py-3 text-sm text-ink">
          Select a profile first.
        </div>
      )}

      {error && (
        <div className="bg-red/10 border-l-[3px] border-red px-4 py-3 text-sm text-ink">
          {error}
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-ink-muted text-sm py-4">
          <Loader2 size={14} className="animate-spin" />
          Loading jobs…
        </div>
      )}

      {profile && !loading && !searching && jobs.length === 0 && (
        <div className="border-t border-rule-soft py-8 text-sm text-ink-muted">
          No matches yet — click Search now.
        </div>
      )}

      <div className="space-y-3">
        {jobs.map((job) => (
          <JobCard key={job.id} job={job} profile={profile} onRemove={handleRemove} />
        ))}
      </div>
    </div>
  );
}
