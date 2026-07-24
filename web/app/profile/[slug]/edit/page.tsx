"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import * as api from "@/lib/api";
import { ArrowLeft, Upload } from "lucide-react";
import { ReplaceResumeModal } from "@/components/ReplaceResumeModal";

interface ResumeData {
  name?: string;
  designation?: string;
  work_right?: string;
  email?: string;
  phone?: string;
  website?: string;
  summary?: string;
  experience?: Record<string, unknown>[];
  skills?: Record<string, string[]>;
  education?: Record<string, unknown>[];
  certifications?: Record<string, unknown>[];
  languages?: string[];
  [key: string]: unknown;
}

export default function ResumeEditPage() {
  const { slug } = useParams<{ slug: string }>();
  const [resume, setResume] = useState<ResumeData | null>(null);
  const [error, setError] = useState("");
  const [showReplace, setShowReplace] = useState(false);

  const loadResume = useCallback(() => {
    if (!slug) return;
    api.getResume(slug)
      .then(data => {
        setResume(data as ResumeData);
        setError("");
      })
      .catch(() => setError("No resume data found for this profile."));
  }, [slug]);

  useEffect(() => { loadResume(); }, [loadResume]);

  if (error) return <p className="text-sm text-red-500">{error}</p>;
  if (!resume) return <p className="text-sm text-gray-400">Loading...</p>;

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <Link href={`/profile/${slug}`} className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800">
          <ArrowLeft size={14} />
          Back to {resume.name ?? slug}
        </Link>
        <button
          onClick={() => setShowReplace(true)}
          className="flex items-center gap-1.5 text-xs text-gray-500 border border-gray-200 rounded-lg px-2.5 py-1.5 hover:bg-gray-50 transition-colors"
        >
          <Upload size={13} />
          Replace Resume
        </button>
      </div>

      <h1 className="text-xl font-bold text-gray-900">Edit Resume</h1>

      {/* Section editors are added in later tasks */}
      <p className="text-sm text-gray-400">Sections: Experience, Education, Certifications, Languages, Skills, and contact fields will render here.</p>

      {showReplace && slug && (
        <ReplaceResumeModal
          slug={slug}
          onClose={() => setShowReplace(false)}
          onReplaced={loadResume}
        />
      )}
    </div>
  );
}
