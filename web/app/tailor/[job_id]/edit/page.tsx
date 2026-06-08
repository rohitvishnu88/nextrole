"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import * as api from "@/lib/api";
import type { TailoredResume } from "@/lib/types";
import { Save, ChevronDown, ChevronRight } from "lucide-react";

export default function EditTailorPage() {
  const { job_id } = useParams<{ job_id: string }>();
  const router = useRouter();

  const [resume, setResume] = useState<TailoredResume | null>(null);
  const [coverLetter, setCoverLetter] = useState("");
  const [expanded, setExpanded] = useState<Set<number>>(new Set([0]));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getTailorData(job_id),
      api.getTailorCoverLetterText(job_id),
    ])
      .then(([resumeData, clData]) => {
        setResume(resumeData);
        setCoverLetter(clData.text);
      })
      .catch(() => setError("Failed to load tailored resume."))
      .finally(() => setLoading(false));
  }, [job_id]);

  function updateSummary(value: string) {
    setResume(prev => prev ? { ...prev, summary: value } : prev);
  }

  function updateBullet(expIdx: number, bulletIdx: number, value: string) {
    setResume(prev => {
      if (!prev) return prev;
      const experience = prev.experience.map((exp, i) =>
        i === expIdx
          ? {
              ...exp,
              description: exp.description.map((b, j) =>
                j === bulletIdx ? value : b
              ),
            }
          : exp
      );
      return { ...prev, experience };
    });
  }

  function toggleExpand(idx: number) {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(idx) ? next.delete(idx) : next.add(idx);
      return next;
    });
  }

  async function handleSave() {
    if (!resume) return;
    setSaving(true);
    setError("");
    try {
      await api.patchTailorData(job_id, resume, coverLetter);
      router.push(`/tailor?job=${job_id}`);
    } catch {
      setError("Failed to save. Please try again.");
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="max-w-3xl">
        <p className="text-sm text-muted animate-pulse">Loading tailored resume…</p>
      </div>
    );
  }

  if (error && !resume) {
    return (
      <div className="max-w-3xl">
        <p className="text-sm text-red-500">{error}</p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl space-y-4 pb-16">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-navy">Edit Tailored Resume</h1>
          <p className="text-sm text-muted mt-1">
            Changes only affect this tailored version — your base profile is unchanged
          </p>
        </div>
        <button
          onClick={() => router.back()}
          className="text-sm text-muted hover:text-navy transition-colors mt-1"
        >
          ← Back without saving
        </button>
      </div>

      {/* Summary */}
      <div className="bg-white rounded-2xl border border-warm-border p-5 space-y-2">
        <p className="text-xs font-semibold text-muted uppercase tracking-wide">Summary</p>
        <textarea
          value={resume?.summary ?? ""}
          onChange={e => updateSummary(e.target.value)}
          rows={4}
          className="w-full border border-warm-border rounded-xl px-4 py-2.5 text-sm text-navy bg-cream focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition resize-y"
        />
      </div>

      {/* Experience */}
      {resume?.experience.map((exp, expIdx) => (
        <div key={expIdx} className="bg-white rounded-2xl border border-warm-border overflow-hidden">
          <button
            onClick={() => toggleExpand(expIdx)}
            className="w-full flex items-center justify-between px-5 py-4 hover:bg-cream transition-colors text-left"
          >
            <div>
              <p className="text-sm font-semibold text-navy">{exp.title}</p>
              <p className="text-xs text-muted mt-0.5">
                {exp.company}{exp.highlight ? ` — ${exp.highlight}` : ""} · {exp.start_date} – {exp.end_date}
                {!expanded.has(expIdx) && (
                  <span className="ml-2 text-muted">· {exp.description.length} bullets</span>
                )}
              </p>
            </div>
            {expanded.has(expIdx)
              ? <ChevronDown size={16} className="text-muted shrink-0" />
              : <ChevronRight size={16} className="text-muted shrink-0" />
            }
          </button>

          {expanded.has(expIdx) && (
            <div className="px-5 pb-5 space-y-2">
              {exp.description.map((bullet, bulletIdx) => (
                <div key={bulletIdx} className="flex gap-3 items-start">
                  <span className="text-muted mt-2.5 text-base leading-none shrink-0">•</span>
                  <textarea
                    value={bullet}
                    onChange={e => updateBullet(expIdx, bulletIdx, e.target.value)}
                    rows={2}
                    className="flex-1 border border-warm-border rounded-xl px-3 py-2 text-sm text-navy bg-cream focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition resize-y"
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      ))}

      {/* Cover Letter */}
      <div className="bg-white rounded-2xl border border-warm-border p-5 space-y-2">
        <p className="text-xs font-semibold text-muted uppercase tracking-wide">Cover Letter</p>
        <textarea
          value={coverLetter}
          onChange={e => setCoverLetter(e.target.value)}
          rows={10}
          className="w-full border border-warm-border rounded-xl px-4 py-2.5 text-sm text-navy bg-cream focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition resize-y"
        />
      </div>

      {/* Save actions */}
      {error && <p className="text-sm text-red-500">{error}</p>}
      <div className="flex items-center justify-end gap-4">
        <button
          onClick={() => router.back()}
          className="text-sm text-muted hover:text-navy transition-colors"
        >
          ← Back without saving
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 bg-navy hover:bg-navy/90 disabled:opacity-50 text-white rounded-xl px-5 py-2.5 text-sm font-semibold transition-colors"
        >
          <Save size={15} />
          {saving ? "Saving…" : "Save & Regenerate PDF"}
        </button>
      </div>
    </div>
  );
}
