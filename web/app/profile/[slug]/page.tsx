"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import * as api from "@/lib/api";
import { Code2, LayoutList, Copy, Check, Pencil, Download } from "lucide-react";
import { setActiveProfile } from "@/lib/useActiveProfile";

interface Experience {
  title: string;
  company: string;
  start_date: string;
  end_date: string;
  description: string[];
}

interface ResumeData {
  name?: string;
  designation?: string;
  work_right?: string;
  email?: string;
  phone?: string;
  website?: string;
  summary?: string;
  experience?: Experience[];
  skills?: Record<string, string[]>;
  education?: Array<{ degree?: string; school?: string }>;
  certifications?: Array<{ name?: string; issuer?: string }>;
  languages?: string[];
}

export default function ProfilePage() {
  const { slug } = useParams<{ slug: string }>();
  const [resume, setResume] = useState<ResumeData | null>(null);
  const [raw, setRaw] = useState<Record<string, unknown> | null>(null);
  const [view, setView] = useState<"structured" | "json">("structured");
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  const loadResume = useCallback(() => {
    if (!slug) return;
    api.getResume(slug)
      .then(data => {
        setRaw(data);
        setResume(data as ResumeData);
        setError("");
      })
      .catch(() => setError("No resume data found for this profile."));
  }, [slug]);

  useEffect(() => { loadResume(); }, [loadResume]);

  // Set synchronously on mount, before any network round-trip - ProfileSwitcher's
  // own localStorage read races against this on navigation, and whichever finishes
  // last wins. An effect keyed on `slug` alone (no fetch in between) always commits
  // before a fetch initiated elsewhere can resolve, so this side wins the race.
  useEffect(() => { if (slug) setActiveProfile(slug); }, [slug]);

  function handleCopy() {
    if (!raw) return;
    navigator.clipboard.writeText(JSON.stringify(raw, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (error) return <p className="text-sm text-ink">{error}</p>;
  if (!resume) return <p className="text-sm text-ink-muted">Loading...</p>;

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-ink">{resume.name ?? slug} — Resume Data</h1>
        <div className="flex items-center gap-2">
          <Link
            href={`/profile/${slug}/edit`}
            className="flex items-center gap-1.5 text-xs text-ink-muted border border-rule-soft px-2.5 py-1.5 hover:bg-paper transition-colors"
          >
            <Pencil size={13} />
            edit
          </Link>
          <a
            href={`/api/profiles/${slug}/resume/pdf`}
            download
            className="flex items-center gap-1.5 text-xs text-ink-muted border border-rule-soft px-2.5 py-1.5 hover:bg-paper transition-colors"
          >
            <Download size={13} />
            download pdf
          </a>
          {view === "json" && (
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 text-xs text-ink-muted border border-rule-soft px-2.5 py-1.5 hover:bg-paper transition-colors"
            >
              {copied ? <Check size={13} className="text-blue" /> : <Copy size={13} />}
              {copied ? "Copied" : "Copy"}
            </button>
          )}
          <div className="flex bg-surface p-1 gap-1">
            <button
              onClick={() => setView("structured")}
              className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium transition-colors ${view === "structured" ? "bg-surface  text-ink" : "text-ink-muted"}`}
            >
              <LayoutList size={13} />
              structured
            </button>
            <button
              onClick={() => setView("json")}
              className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium transition-colors ${view === "json" ? "bg-surface  text-ink" : "text-ink-muted"}`}
            >
              <Code2 size={13} />
              raw json
            </button>
          </div>
        </div>
      </div>

      {view === "json" && raw && (
        <pre className="bg-ink text-blue text-xs p-5 overflow-x-auto overflow-y-auto max-h-[70vh] leading-relaxed">
          {JSON.stringify(raw, null, 2)}
        </pre>
      )}

      {view === "structured" && <>

      {(resume.designation || resume.email || resume.phone || resume.website || resume.work_right) && (
        <section className="text-sm text-ink-muted space-y-0.5">
          {resume.designation && <p className="font-medium text-ink">{resume.designation}</p>}
          <p>
            {[resume.email, resume.phone, resume.website].filter(Boolean).join(" · ")}
          </p>
          {resume.work_right && <p>{resume.work_right}</p>}
        </section>
      )}

      {resume.summary && (
        <section>
          <h2 className="text-sm font-bold text-ink-muted mb-2">summary</h2>
          <p className="text-sm text-ink leading-relaxed">{resume.summary}</p>
        </section>
      )}

      {resume.experience && resume.experience.length > 0 && (
        <section>
          <h2 className="text-sm font-bold text-ink-muted mb-3">experience</h2>
          <div className="space-y-4">
            {resume.experience.map((exp, i) => (
              <div key={i} className="bg-surface p-4">
                <p className="text-sm font-bold text-ink">{exp.title}</p>
                <p className="text-xs text-ink-muted mb-2">{exp.company} · {exp.start_date} – {exp.end_date}</p>
                <ul className="list-disc list-inside space-y-0.5">
                  {(exp.description ?? []).map((b, j) => (
                    <li key={j} className="text-xs text-ink-muted">{b}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>
      )}

      {resume.skills && Object.keys(resume.skills).length > 0 && (
        <section>
          <h2 className="text-sm font-bold text-ink-muted mb-2">skills</h2>
          <div className="space-y-1">
            {Object.entries(resume.skills).map(([group, items]) => (
              <p key={group} className="text-sm text-ink">
                <span className="font-medium">{group}:</span>{" "}
                {Array.isArray(items) ? items.join(", ") : String(items)}
              </p>
            ))}
          </div>
        </section>
      )}

      {resume.education && resume.education.length > 0 && (
        <section>
          <h2 className="text-sm font-bold text-ink-muted mb-2">education</h2>
          {resume.education.map((e, i) => (
            <p key={i} className="text-sm text-ink">{e.degree} — {e.school}</p>
          ))}
        </section>
      )}

      {resume.certifications && resume.certifications.length > 0 && (
        <section>
          <h2 className="text-sm font-bold text-ink-muted mb-2">certifications</h2>
          {resume.certifications.map((c, i) => (
            <p key={i} className="text-sm text-ink">{c.name} — {c.issuer}</p>
          ))}
        </section>
      )}

      {resume.languages && resume.languages.length > 0 && (
        <section>
          <h2 className="text-sm font-bold text-ink-muted mb-2">languages</h2>
          <p className="text-sm text-ink">{resume.languages.join(", ")}</p>
        </section>
      )}

      </>}
    </div>
  );
}
