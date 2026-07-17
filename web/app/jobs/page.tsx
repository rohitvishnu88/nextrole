"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "@/lib/api";
import type { JobMatch } from "@/lib/types";
import { useActiveProfile } from "@/lib/useActiveProfile";
import { JobCard } from "@/components/JobCard";
import { Search, Loader2 } from "lucide-react";

export default function JobsPage() {
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
          <h1 className="text-2xl font-bold text-navy">Jobs</h1>
          <p className="text-sm text-muted mt-1">{jobs.length} match{jobs.length !== 1 ? "es" : ""}</p>
        </div>
        <button
          onClick={handleSearch}
          disabled={searching || !profile}
          className="flex items-center gap-1.5 bg-accent hover:bg-accent-hover text-white rounded-xl px-4 py-2 text-sm font-semibold transition-colors disabled:opacity-50"
        >
          {searching ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
          {searching ? "Searching..." : "Search now"}
        </button>
      </div>

      {!profile && (
        <div className="bg-yellow-50 border border-yellow-100 rounded-2xl px-5 py-4 text-sm text-yellow-700">
          Select a profile first.
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-100 rounded-2xl px-5 py-4 text-sm text-red-600">
          {error}
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-muted text-sm py-4">
          <Loader2 size={14} className="animate-spin" />
          Loading jobs…
        </div>
      )}

      {profile && !loading && !searching && jobs.length === 0 && (
        <div className="bg-cream border border-warm-border rounded-2xl px-5 py-8 text-center text-sm text-muted">
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
