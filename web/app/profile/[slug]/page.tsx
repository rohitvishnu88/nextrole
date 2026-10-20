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

  if (error) return <p className="text-sm text-red-500">{error}</p>;
  if (!resume) return <p className="text-sm text-gray-400">Loading...</p>;

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">{resume.name ?? slug} — Resume Data</h1>
        <div className="flex items-center gap-2">
          <Link
            href={`/profile/${slug}/edit`}
            className="flex items-center gap-1.5 text-xs text-gray-500 border border-gray-200 rounded-lg px-2.5 py-1.5 hover:bg-gray-50 transition-colors"
          >
            <Pencil size={13} />
            Edit
          </Link>
          <a
            href={`/api/profiles/${slug}/resume/pdf`}
            download
            className="flex items-center gap-1.5 text-xs text-gray-500 border border-gray-200 rounded-lg px-2.5 py-1.5 hover:bg-gray-50 transition-colors"
          >
            <Download size={13} />
            Download PDF
          </a>
          {view === "json" && (
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 text-xs text-gray-500 border border-gray-200 rounded-lg px-2.5 py-1.5 hover:bg-gray-50 transition-colors"
            >
              {copied ? <Check size={13} className="text-green-500" /> : <Copy size={13} />}
              {copied ? "Copied" : "Copy"}
            </button>
          )}
          <div className="flex bg-surface rounded-lg p-1 gap-1">
            <button
              onClick={() => setView("structured")}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-colors ${view === "structured" ? "bg-white shadow-sm text-gray-800" : "text-gray-400"}`}
            >
              <LayoutList size={13} />
              Structured
            </button>
            <button
              onClick={() => setView("json")}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-colors ${view === "json" ? "bg-white shadow-sm text-gray-800" : "text-gray-400"}`}
            >
              <Code2 size={13} />
              Raw JSON
            </button>
          </div>
        </div>
      </div>

      {view === "json" && raw && (
        <pre className="bg-gray-950 text-green-400 text-xs rounded-xl p-5 overflow-x-auto overflow-y-auto max-h-[70vh] leading-relaxed">
          {JSON.stringify(raw, null, 2)}
        </pre>
      )}

      {view === "structured" && <>

      {(resume.designation || resume.email || resume.phone || resume.website || resume.work_right) && (
        <section className="text-sm text-gray-600 space-y-0.5">
          {resume.designation && <p className="font-medium text-gray-800">{resume.designation}</p>}
          <p>
            {[resume.email, resume.phone, resume.website].filter(Boolean).join(" · ")}
          </p>
          {resume.work_right && <p>{resume.work_right}</p>}
        </section>
      )}

      {resume.summary && (
        <section>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Summary</h2>
          <p className="text-sm text-gray-700 leading-relaxed">{resume.summary}</p>
        </section>
      )}

      {resume.experience && resume.experience.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Experience</h2>
          <div className="space-y-4">
            {resume.experience.map((exp, i) => (
              <div key={i} className="bg-surface rounded-lg p-4">
                <p className="text-sm font-semibold text-gray-900">{exp.title}</p>
                <p className="text-xs text-gray-500 mb-2">{exp.company} · {exp.start_date} – {exp.end_date}</p>
                <ul className="list-disc list-inside space-y-0.5">
                  {(exp.description ?? []).map((b, j) => (
                    <li key={j} className="text-xs text-gray-600">{b}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>
      )}

      {resume.skills && Object.keys(resume.skills).length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Skills</h2>
          <div className="space-y-1">
            {Object.entries(resume.skills).map(([group, items]) => (
              <p key={group} className="text-sm text-gray-700">
                <span className="font-medium">{group}:</span>{" "}
                {Array.isArray(items) ? items.join(", ") : String(items)}
              </p>
            ))}
          </div>
        </section>
      )}

      {resume.education && resume.education.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Education</h2>
          {resume.education.map((e, i) => (
            <p key={i} className="text-sm text-gray-700">{e.degree} — {e.school}</p>
          ))}
        </section>
      )}

      {resume.certifications && resume.certifications.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Certifications</h2>
          {resume.certifications.map((c, i) => (
            <p key={i} className="text-sm text-gray-700">{c.name} — {c.issuer}</p>
          ))}
        </section>
      )}

      {resume.languages && resume.languages.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Languages</h2>
          <p className="text-sm text-gray-700">{resume.languages.join(", ")}</p>
        </section>
      )}

      </>}
    </div>
  );
}
